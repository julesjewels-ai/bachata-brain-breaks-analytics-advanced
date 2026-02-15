import ast
import json
import os
import subprocess
import shutil
import re
from pathlib import Path
from typing import List, Dict, Set, Tuple, Any, Optional
from dataclasses import dataclass, field
from git import Repo

# Configuration
MAX_TOKEN_CONTEXT = 2000
MAX_MOCK_DENSITY = 0.55
MIN_UNIQUE_COVERAGE = 5
CRITICAL_PATHS_FILE = "critical_paths.json"
QUARANTINE_DIR = "tests/quarantine"
SNAPSHOTS_DIR = "tests/snapshots"
ENTROPY_REPORT_FILE = "entropy_report.md"

@dataclass
class TestFileHealth:
    filepath: str
    loc: int = 0
    mock_density: float = 0.0
    churn_rate: int = 0
    token_cost: int = 0
    unique_coverage_lines: int = 0
    is_critical_path: bool = False
    rot_tags: List[str] = field(default_factory=list)
    verdict: str = "NONE"

def get_churn(filepath: str) -> int:
    try:
        repo = Repo(".")
        commits = list(repo.iter_commits(paths=filepath, since="30 days ago"))
        return len(commits)
    except Exception as e:
        # print(f"Error getting churn for {filepath}: {e}")
        return 0

def analyze_ast(filepath: str) -> Tuple[int, int, List[str], List[Any]]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
             with open(filepath, "r", encoding="latin-1") as f:
                content = f.read()
        except Exception:
            return 0, 0, [], []
    except Exception:
        return 0, 0, [], []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return 0, 0, [], []

    loc = len(content.splitlines())
    mock_lines = 0
    bloat_nodes = []
    tautologies = []

    # Count mocks
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in ["Mock", "MagicMock", "patch", "spy"]:
                    mock_lines += 1
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr in ["Mock", "MagicMock", "patch", "spy", "return_value"]:
                    mock_lines += 1

    # Detect Bloat (large literals)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Dict, ast.List)):
            # rudimentary size check: end_lineno - lineno > 20
            if hasattr(node, 'end_lineno') and hasattr(node, 'lineno'):
                if node.end_lineno - node.lineno > 20:
                     bloat_nodes.append(node)

    # Detect Tautologies (assert True)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            if isinstance(node.test, ast.Constant) and node.test.value is True:
                tautologies.append(node)
            elif isinstance(node.test, ast.Compare):
                # check left == right where left and right are identical literals
                if len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq):
                    if len(node.test.comparators) == 1:
                        left = node.test.left
                        right = node.test.comparators[0]
                        if isinstance(left, ast.Constant) and isinstance(right, ast.Constant):
                            if left.value == right.value:
                                tautologies.append(node)

    return loc, mock_lines, tautologies, bloat_nodes

def calculate_token_cost(filepath: str) -> int:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return len(content.split()) # Approximation
    except Exception:
        return 0

def run_per_test_coverage(test_files: List[str]) -> Dict[str, Set[str]]:
    coverage_map = {} # test_file -> set of "file:line" strings

    # Check if .coverage exists and remove it
    if os.path.exists(".coverage"):
        os.remove(".coverage")

    for test_file in test_files:
        print(f"Running coverage for {test_file}...")
        # Run pytest for single file with coverage
        cmd = [
            "coverage", "run", "--source=src", "-m", "pytest", test_file
        ]
        # Run and capture output to avoid spamming unless error
        subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Generate JSON report
        subprocess.run(["coverage", "json", "-o", "coverage.json"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Parse JSON
        covered_lines = set()
        if os.path.exists("coverage.json"):
            try:
                with open("coverage.json", "r") as f:
                    data = json.load(f)
                    files = data.get("files", {})
                    for src_file, metrics in files.items():
                        for line in metrics.get("executed_lines", []):
                            covered_lines.add(f"{src_file}:{line}")
            except Exception as e:
                print(f"Error parsing coverage.json for {test_file}: {e}")

        coverage_map[test_file] = covered_lines

        # Cleanup
        if os.path.exists(".coverage"):
            os.remove(".coverage")
        if os.path.exists("coverage.json"):
            os.remove("coverage.json")

    return coverage_map

def calculate_unique_coverage(coverage_map: Dict[str, Set[str]]) -> Dict[str, int]:
    unique_counts = {}
    all_files = list(coverage_map.keys())

    for i, test_file in enumerate(all_files):
        my_coverage = coverage_map[test_file]
        other_coverage = set()
        for j, other_file in enumerate(all_files):
            if i != j:
                other_coverage.update(coverage_map[other_file])

        unique_lines = my_coverage - other_coverage
        unique_counts[test_file] = len(unique_lines)

    return unique_counts

def externalize_snapshots(filepath: str, bloat_nodes: List[ast.AST]) -> bool:
    # We need to process from bottom to top to keep line numbers valid
    bloat_nodes.sort(key=lambda x: x.lineno, reverse=True)

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    modified = False

    for i, node in enumerate(bloat_nodes):
        # Extract content
        start_line = node.lineno - 1
        end_line = node.end_lineno - 1
        start_col = node.col_offset
        end_col = node.end_col_offset

        # Check bounds
        if start_line >= len(lines) or end_line >= len(lines):
             continue

        # Extract the literal text
        original_text_lines = lines[start_line:end_line+1]

        if not original_text_lines:
            continue

        # Adjust first and last line
        # Create a copy to modify
        extracted_lines = list(original_text_lines)
        extracted_lines[-1] = extracted_lines[-1][:end_col]
        extracted_lines[0] = extracted_lines[0][start_col:]

        literal_text = "".join(extracted_lines)

        try:
            # Evaluate safely to get the object
            obj = ast.literal_eval(literal_text)

            # Save to JSON
            snapshot_name = f"{Path(filepath).stem}_snapshot_{i}.json"
            snapshot_path = os.path.join(SNAPSHOTS_DIR, snapshot_name)
            with open(snapshot_path, "w") as f:
                json.dump(obj, f, indent=2)

            # Create replacement code
            replacement = f"__import__('json').load(open('{snapshot_path}'))"

            # Replace in lines
            if start_line == end_line:
                lines[start_line] = lines[start_line][:start_col] + replacement + lines[start_line][end_col:]
            else:
                # Clear lines in between
                for l in range(start_line + 1, end_line):
                    lines[l] = ""

                # Retrieve the tail from end_line
                tail = lines[end_line][end_col:]

                # Set start line
                lines[start_line] = lines[start_line][:start_col] + replacement + tail

                # Clear end line (since its tail was moved to start_line)
                lines[end_line] = ""

            modified = True
            print(f"Externalized snapshot to {snapshot_path}")

        except Exception as e:
            print(f"Failed to externalize snapshot in {filepath}: {e}")
            continue

    if modified:
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)

    return modified

def main():
    print("Starting Entropy Protocol...")

    # Load Critical Paths
    critical_paths = []
    if os.path.exists(CRITICAL_PATHS_FILE):
        with open(CRITICAL_PATHS_FILE, "r") as f:
            try:
                critical_paths = json.load(f)
            except:
                critical_paths = []

    # 1. Identify Test Files
    test_files = []
    for root, dirs, files in os.walk("tests"):
        if "quarantine" in root:
            continue
        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                test_files.append(os.path.join(root, file))

    print(f"Found {len(test_files)} test files.")

    # 2. Phase 1: Cartography (Coverage)
    coverage_map = run_per_test_coverage(test_files)
    unique_coverage = calculate_unique_coverage(coverage_map)

    # 3. Phase 2: Rot Scan
    health_map = {}

    for filepath in test_files:
        loc, mock_lines, tautologies, bloat_nodes = analyze_ast(filepath)
        token_cost = calculate_token_cost(filepath)
        churn = get_churn(filepath)

        mock_density = mock_lines / loc if loc > 0 else 0

        health = TestFileHealth(
            filepath=filepath,
            loc=loc,
            mock_density=mock_density,
            churn_rate=churn,
            token_cost=token_cost,
            unique_coverage_lines=unique_coverage.get(filepath, 0),
            is_critical_path=(filepath in critical_paths)
        )

        # Rot Tags
        if mock_density > MAX_MOCK_DENSITY:
            health.rot_tags.append("BRITTLE_MOCKING")
        if token_cost > MAX_TOKEN_CONTEXT:
            health.rot_tags.append("CONTEXT_BLOAT")
        if len(tautologies) > 0:
            health.rot_tags.append("TAUTOLOGY")

        # Decide Verdict
        if "CONTEXT_BLOAT" in health.rot_tags and bloat_nodes:
             health.verdict = "REFACTOR_BLOAT"

        if ("BRITTLE_MOCKING" in health.rot_tags or "TAUTOLOGY" in health.rot_tags):
            if health.unique_coverage_lines == 0 and not health.is_critical_path:
                 health.verdict = "DELETE"

        if churn > 5 and len(health.rot_tags) > 0:
             if health.unique_coverage_lines > 0:
                  health.verdict = "QUARANTINE"

        health_map[filepath] = (health, bloat_nodes)

    # 4. Phase 3 & 4: Execution & Safety
    actions_taken = []

    # Calculate global coverage before
    all_covered_lines_before = set()
    for lines in coverage_map.values():
        all_covered_lines_before.update(lines)

    total_covered_lines = len(all_covered_lines_before)
    print(f"Total covered lines before: {total_covered_lines}")

    # Simulate Actions
    kept_test_files = set(test_files)
    files_to_delete = []
    files_to_quarantine = []
    files_to_refactor = []

    for filepath, (health, bloat_nodes) in health_map.items():
        if health.verdict == "DELETE":
            files_to_delete.append(filepath)
            kept_test_files.discard(filepath)
        elif health.verdict == "QUARANTINE":
            files_to_quarantine.append(filepath)
            kept_test_files.discard(filepath)
        elif health.verdict == "REFACTOR_BLOAT":
            files_to_refactor.append((filepath, bloat_nodes))

    # Calculate predicted coverage drop
    all_covered_lines_after = set()
    for filepath in kept_test_files:
        all_covered_lines_after.update(coverage_map[filepath])

    total_covered_lines_after = len(all_covered_lines_after)
    drop_percentage = 0
    if total_covered_lines > 0:
        drop_percentage = (total_covered_lines - total_covered_lines_after) / total_covered_lines

    print(f"Predicted coverage drop: {drop_percentage:.2%}")

    if drop_percentage > 0.005:
        print("ABORT: Coverage drop exceeds 0.5%. No actions taken.")
        return

    if len(files_to_delete) + len(files_to_quarantine) > 20:
         print("ABORT: More than 20 files flagged. Vibe Check failed.")
         return

    # Execute Actions
    for filepath in files_to_delete:
        print(f"Deleting {filepath}")
        os.remove(filepath)
        actions_taken.append({"file": filepath, "action": "DELETED", "reason": "Liability Prune"})

    for filepath in files_to_quarantine:
        print(f"Quarantining {filepath}")
        dest = os.path.join(QUARANTINE_DIR, os.path.basename(filepath))
        shutil.move(filepath, dest)
        actions_taken.append({"file": filepath, "action": "QUARANTINED", "reason": "High Churn & Rot"})

    for filepath, bloat_nodes in files_to_refactor:
        print(f"Refactoring {filepath}")
        if externalize_snapshots(filepath, bloat_nodes):
             actions_taken.append({"file": filepath, "action": "REFACTORED", "reason": "Context Bloat"})

    # Generate Report
    with open(ENTROPY_REPORT_FILE, "w") as f:
        f.write("# Entropy Report\n\n")
        f.write("| File | Rot Type | Unique Coverage | Action Taken | Rationale |\n")
        f.write("|---|---|---|---|---|\n")
        for action in actions_taken:
            filepath = action["file"]
            health, _ = health_map.get(filepath, (None, None))
            rot_type = ", ".join(health.rot_tags) if health else "N/A"
            unique = health.unique_coverage_lines if health else "N/A"
            f.write(f"| {filepath} | {rot_type} | {unique} | {action['action']} | {action['reason']} |\n")

    print(f"Report generated at {ENTROPY_REPORT_FILE}")

if __name__ == "__main__":
    main()
