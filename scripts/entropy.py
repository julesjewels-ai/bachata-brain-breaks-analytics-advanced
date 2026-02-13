import ast
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple, Any

# --- Configuration ---
CRITICAL_PATHS_FILE = "critical_paths.json"
MAX_TOKEN_CONTEXT = 2000
MAX_MOCK_DENSITY = 0.55
MIN_UNIQUE_COVERAGE_THRESHOLD = 5
EXECUTION_MODE = "PR_SUGGESTION"
QUARANTINE_DIR = "tests/quarantine"
SNAPSHOTS_DIR = "tests/snapshots"

# --- Domain Models ---
@dataclass
class TestFileHealth:
    file_path: str
    loc: int = 0
    mock_density: float = 0.0
    churn_rate: int = 0
    token_cost: int = 0
    unique_coverage_lines: int = 0
    is_critical_path: bool = False

@dataclass
class RotVerdict:
    file: str
    score: int = 0
    tags: List[str] = field(default_factory=list)
    suggested_action: str = "NONE"
    rationale: str = ""
    unique_coverage: int = 0
    bloat_nodes: List[Tuple[Any, Any]] = field(default_factory=list) # (node, data)

# --- Git Churn Helper ---
def get_churn_rate(filepath: str) -> int:
    try:
        import git
        try:
            repo = git.Repo(".", search_parent_directories=True)
            commits = list(repo.iter_commits(paths=filepath, since="30 days ago"))
            return len(commits)
        except git.exc.InvalidGitRepositoryError:
            return 0
    except ImportError:
        return 0
    except Exception as e:
        print(f"Warning: Could not get churn for {filepath}: {e}")
        return 0

# --- AST Analysis Visitors ---
class MockDensityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.mock_calls = 0

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id in ['Mock', 'MagicMock', 'patch', 'spy']:
                self.mock_calls += 1
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in ['Mock', 'MagicMock', 'patch', 'spy']:
                self.mock_calls += 1
        self.generic_visit(node)

class TautologyVisitor(ast.NodeVisitor):
    def __init__(self):
        self.tautologies = 0

    def visit_Assert(self, node):
        if isinstance(node.test, ast.Constant):
             if node.test.value is True or node.test.value == 1:
                 self.tautologies += 1
        elif isinstance(node.test, ast.Compare):
            if len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq):
                 left = node.test.left
                 right = node.test.comparators[0]
                 if isinstance(left, ast.Name) and isinstance(right, ast.Name) and left.id == right.id:
                     self.tautologies += 1
                 elif isinstance(left, ast.Constant) and isinstance(right, ast.Constant) and left.value == right.value:
                     self.tautologies += 1
        self.generic_visit(node)

class BloatVisitor(ast.NodeVisitor):
    def __init__(self):
        self.bloat_nodes = [] # List of (node, data)

    def visit_Dict(self, node):
        # Identify large dicts (arbitrary threshold > 20 keys)
        if len(node.keys) > 20:
            try:
                data = ast.literal_eval(node)
                self.bloat_nodes.append((node, data))
            except ValueError:
                pass
        self.generic_visit(node)

    def visit_List(self, node):
        if len(node.elts) > 20:
            try:
                data = ast.literal_eval(node)
                self.bloat_nodes.append((node, data))
            except ValueError:
                pass
        self.generic_visit(node)

# --- Main Logic ---

def load_critical_paths() -> Set[str]:
    if os.path.exists(CRITICAL_PATHS_FILE):
        with open(CRITICAL_PATHS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def run_coverage():
    print("Running coverage...")
    subprocess.run(["coverage", "erase"])
    result = subprocess.run(
        ["pytest", "--cov=src", "--cov-report=json", "--cov-context=test"],
        capture_output=True, text=True
    )
    if result.returncode != 0 and result.returncode != 5:
        print(f"Pytest warning/error:\n{result.stderr}")

    if not os.path.exists("coverage.json"):
        print("Error: coverage.json not found.")
        return None

    with open("coverage.json", 'r') as f:
        return json.load(f)

def get_total_executable_lines(coverage_data):
    if not coverage_data: return 0
    if "totals" in coverage_data:
        return coverage_data["totals"].get("num_statements", 0)

    total = 0
    for f, data in coverage_data.get("files", {}).items():
        summary = data.get("summary", {})
        total += summary.get("num_statements", 0)
    return total

def analyze_unique_coverage(coverage_data, test_files: List[str]) -> Dict[str, int]:
    line_coverage_map = defaultdict(set)

    if not coverage_data:
        return {tf: 0 for tf in test_files}

    for src_file, data in coverage_data.get("files", {}).items():
        contexts = data.get("contexts", {})
        for context_id, lines in contexts.items():
            test_file = context_id.split("::")[0]
            if "|" in test_file:
                 test_file = test_file.split("|")[0]

            test_file = os.path.relpath(test_file)

            for line in lines:
                line_coverage_map[f"{src_file}:{line}"].add(test_file)

    unique_coverage = defaultdict(int)
    for line_id, covering_tests in line_coverage_map.items():
        if len(covering_tests) == 1:
            test_file = list(covering_tests)[0]
            unique_coverage[test_file] += 1

    return unique_coverage

def analyze_file_metrics(filepath: str, unique_cov: int, is_critical: bool) -> TestFileHealth:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return TestFileHealth(filepath)

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return TestFileHealth(filepath, loc=len(content.splitlines()))

    loc = len(content.splitlines())

    mock_visitor = MockDensityVisitor()
    mock_visitor.visit(tree)
    mock_density = mock_visitor.mock_calls / loc if loc > 0 else 0

    token_cost = len(content) // 4
    churn_rate = get_churn_rate(filepath)

    return TestFileHealth(
        file_path=filepath,
        loc=loc,
        mock_density=mock_density,
        churn_rate=churn_rate,
        token_cost=token_cost,
        unique_coverage_lines=unique_cov,
        is_critical_path=is_critical
    )

def determine_verdict(health: TestFileHealth) -> RotVerdict:
    tags = []
    score = 0
    bloat_nodes = []

    if health.mock_density > MAX_MOCK_DENSITY:
        tags.append("BRITTLE_MOCKING")
        score += 40

    if health.token_cost > MAX_TOKEN_CONTEXT:
        tags.append("CONTEXT_BLOAT")
        score += 20
        try:
            with open(health.file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
            bloat_visitor = BloatVisitor()
            bloat_visitor.visit(tree)
            bloat_nodes = bloat_visitor.bloat_nodes
        except Exception:
            pass

    try:
        with open(health.file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        taut_visitor = TautologyVisitor()
        taut_visitor.visit(tree)
        if taut_visitor.tautologies > 0:
            tags.append("TAUTOLOGY")
            score += 30
    except Exception:
        pass

    if health.churn_rate > 5:
        tags.append("HIGH_CHURN")
        score += 20

    action = "NONE"
    rationale = ""

    if "CONTEXT_BLOAT" in tags:
        if bloat_nodes:
            action = "COMPACT_SNAPSHOTS"
            rationale = f"File is bloated ({health.token_cost} tokens). Identified {len(bloat_nodes)} large structures."
        else:
            rationale = f"File is bloated ({health.token_cost} tokens) but no clear structures to extract."

    if (("BRITTLE_MOCKING" in tags or "TAUTOLOGY" in tags) and
        health.unique_coverage_lines == 0 and
        not health.is_critical_path):
        action = "DELETE"
        rationale = "High maintenance liability with no unique coverage."

    if "HIGH_CHURN" in tags and score > 50:
        action = "QUARANTINE"
        rationale = f"High churn ({health.churn_rate}) and high rot score ({score})."

    if health.unique_coverage_lines > MIN_UNIQUE_COVERAGE_THRESHOLD:
        if action == "DELETE":
            action = "NONE"
            rationale = "Saved by unique coverage immunity."

    if health.is_critical_path:
        if action == "DELETE":
            action = "NONE"
            rationale = "Critical path immunity."

    return RotVerdict(
        file=health.file_path,
        score=score,
        tags=tags,
        suggested_action=action,
        rationale=rationale,
        unique_coverage=health.unique_coverage_lines,
        bloat_nodes=bloat_nodes
    )

def perform_snapshot_externalization(file_path, bloat_nodes):
    try:
        with open(file_path, 'rb') as f:
            content_bytes = f.read()

        replacements = []
        lines = content_bytes.splitlines(keepends=True)

        for node, data in bloat_nodes:
            start_offset = 0
            for i in range(node.lineno - 1):
                start_offset += len(lines[i])
            start_offset += node.col_offset

            if not hasattr(node, 'end_lineno') or not hasattr(node, 'end_col_offset'):
                continue

            end_offset = 0
            for i in range(node.end_lineno - 1):
                end_offset += len(lines[i])
            end_offset += node.end_col_offset

            snapshot_filename = f"{os.path.basename(file_path).replace('.py', '')}_snap_{len(replacements)+1}.json"
            snapshot_path = os.path.join(SNAPSHOTS_DIR, snapshot_filename)

            os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
            with open(snapshot_path, 'w') as f:
                json.dump(data, f, indent=2)

            replacement_str = f"__import__('json').load(open('{snapshot_path}'))"
            replacement_bytes = replacement_str.encode('utf-8')
            replacements.append((start_offset, end_offset, replacement_bytes))

        replacements.sort(key=lambda x: x[0], reverse=True)

        modified_bytes = content_bytes
        for start, end, rep in replacements:
            modified_bytes = modified_bytes[:start] + rep + modified_bytes[end:]

        with open(file_path, 'wb') as f:
            f.write(modified_bytes)

        return f"REFACTORED (Extracted {len(replacements)} snapshots)"

    except Exception as e:
        print(f"Error refactoring {file_path}: {e}")
        return f"REFACTOR_FAILED ({e})"

def perform_actions_safely(verdicts: List[RotVerdict], total_lines: int):
    # Safety Check 1: Vibe Check
    actions_to_take = [v for v in verdicts if v.suggested_action in ["DELETE", "QUARANTINE"]]
    if len(actions_to_take) > 20:
        print(f"ABORT: Vibe Check Failed. {len(actions_to_take)} files flagged for removal/quarantine (Limit: 20).")
        return

    # Safety Check 2: Coverage Cliff
    files_to_delete = [v for v in verdicts if v.suggested_action == "DELETE"]
    lines_lost = sum(v.unique_coverage for v in files_to_delete)

    drop_percentage = (lines_lost / total_lines) if total_lines > 0 else 0
    if drop_percentage > 0.005:
        print(f"ABORT: Coverage Cliff. Projected drop {drop_percentage:.2%} > 0.5%.")
        return

    # Execute
    report_lines = ["# Entropy Scan Report", "", "| File | Rot Type | Unique Coverage | Action Taken | Rationale |", "|---|---|---|---|---|"]

    for v in verdicts:
        if v.suggested_action == "NONE" and not v.tags:
            continue

        action_taken = v.suggested_action

        if v.suggested_action == "DELETE":
            if EXECUTION_MODE == "PR_SUGGESTION":
                try:
                    os.remove(v.file)
                    action_taken = "DELETED"
                except OSError as e:
                    action_taken = f"DELETE_FAILED ({e})"

        elif v.suggested_action == "QUARANTINE":
             if EXECUTION_MODE == "PR_SUGGESTION":
                os.makedirs(QUARANTINE_DIR, exist_ok=True)
                dest = os.path.join(QUARANTINE_DIR, os.path.basename(v.file))
                try:
                    shutil.move(v.file, dest)
                    action_taken = "QUARANTINED"
                except OSError as e:
                    action_taken = f"QUARANTINE_FAILED ({e})"

        elif v.suggested_action == "COMPACT_SNAPSHOTS":
             if EXECUTION_MODE == "PR_SUGGESTION":
                 action_taken = perform_snapshot_externalization(v.file, v.bloat_nodes)

        report_lines.append(f"| {v.file} | {', '.join(v.tags)} | {v.unique_coverage} | {action_taken} | {v.rationale} |")

    with open("entropy_report.md", "w") as f:
        f.write("\n".join(report_lines))

def main():
    critical_paths = load_critical_paths()
    coverage_data = run_coverage()
    total_lines = get_total_executable_lines(coverage_data)

    test_files = []
    for root, dirs, files in os.walk("tests"):
        if "quarantine" in root: continue
        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                test_files.append(os.path.join(root, file))

    unique_cov_map = analyze_unique_coverage(coverage_data, test_files)

    verdicts = []
    for tf in test_files:
        is_crit = tf in critical_paths
        uc = unique_cov_map.get(tf, 0)
        health = analyze_file_metrics(tf, uc, is_crit)
        verdict = determine_verdict(health)
        verdicts.append(verdict)

    perform_actions_safely(verdicts, total_lines)

    if os.path.exists("coverage.json"):
        os.remove("coverage.json")
    if os.path.exists(".coverage"):
        os.remove(".coverage")

    print("Entropy scan complete. See entropy_report.md")

if __name__ == "__main__":
    main()
