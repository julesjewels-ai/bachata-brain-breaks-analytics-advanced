"""
Entropy: The Context Guardian & Coverage Auditor.

This script implements the Entropy protocol for identifying and mitigating Test Inflation.
It is adapted for a Python repository environment, utilizing pytest, coverage.py, and AST analysis.
Although the original mission profile references TypeScript/Jest concepts (mock, spyOn, etc.),
this implementation maps them to their Python equivalents (unittest.mock, Mock, MagicMock, patch, etc.).
"""

import os
import sys
import ast
import json
import shutil
import hashlib
import subprocess
import coverage
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
from git import Repo, GitCommandError

# --- Safety Check ---
REQUIRED_MODULES = ["coverage", "pytest", "git", "radon"]
missing_modules = []
for m in REQUIRED_MODULES:
    try:
        __import__(m)
    except ImportError:
        # git is provided by gitpython
        if m == "git":
            try:
                import git
            except ImportError:
                missing_modules.append("gitpython")
        else:
            missing_modules.append(m)

if missing_modules:
    print(f"ERROR: Missing dependencies: {', '.join(missing_modules)}")
    print("Please install them via: pip install " + " ".join(missing_modules))
    sys.exit(1)

# --- Configuration ---
CONFIG = {
    "maxTokenContext": 2000,
    "maxMockDensity": 0.55,
    "minUniqueCoverageThreshold": 5,
    "executionMode": "PR_SUGGESTION",  # 'PR_SUGGESTION' or 'REPORT_ONLY'
    "churnThreshold": 5, # changes per month
    "coverageDropThreshold": 0.5, # percentage
    "vibeCheckThreshold": 20, # files
    "largeObjectThreshold": 200 # characters, for snapshot extraction
}

CRITICAL_PATHS_FILE = "critical_paths.json"
QUARANTINE_DIR = "tests/quarantine"
SNAPSHOTS_DIR = "tests/snapshots"
REPORT_FILE = "entropy_report.md"

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
    suggested_action: str = "NONE"
    rationale: str = ""

class RotVisitor(ast.NodeVisitor):
    def __init__(self):
        self.mock_lines = set()
        self.tautologies = 0
        self.total_lines = 0

    def visit_Call(self, node):
        # Check for Mock usage
        if hasattr(node.func, 'attr'):
            if node.func.attr in ['Mock', 'MagicMock', 'patch', 'spy', 'mockReturnValue']:
                self.mock_lines.add(node.lineno)
        elif hasattr(node.func, 'id'):
             if node.func.id in ['Mock', 'MagicMock', 'patch', 'spy']:
                self.mock_lines.add(node.lineno)

        # Check for Tautologies: assert True, assertEqual(x, x)
        # This is a simplified check
        if isinstance(node.func, ast.Name):
            if node.func.id == 'assert': # Python assert is a keyword, usually handles by Assert node
                pass
        if hasattr(node.func, 'attr') and 'assert' in node.func.attr:
             # unittest style: self.assertEqual(a, b)
             if node.func.attr in ['assertEqual', 'toBe', 'is']:
                 if len(node.args) == 2:
                     # Check if args are literally the same node structure
                     if ast.dump(node.args[0]) == ast.dump(node.args[1]):
                         self.tautologies += 1

        self.generic_visit(node)

    def visit_Assert(self, node):
        # assert True
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            self.tautologies += 1
        # assert x == x
        if isinstance(node.test, ast.Compare):
            if len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq):
                 if ast.dump(node.test.left) == ast.dump(node.test.comparators[0]):
                     self.tautologies += 1
        self.generic_visit(node)

class SnapshotExtractor(ast.NodeVisitor):
    def __init__(self, source_code: str):
        self.source_code = source_code
        self.replacements = [] # List of (start_line, start_col, end_line, end_col, replacement_text, json_data)

    def visit_Dict(self, node):
        self._check_node(node)
        self.generic_visit(node)

    def visit_List(self, node):
        self._check_node(node)
        self.generic_visit(node)

    def _check_node(self, node):
        # Only target large literals
        # Get source segment
        try:
            segment = ast.get_source_segment(self.source_code, node)
            if segment and len(segment) > CONFIG["largeObjectThreshold"]:
                # Convert AST node to Python object safely
                try:
                    # literal_eval is safe for literals
                    val = ast.literal_eval(node)
                    self.replacements.append((node, val))
                except ValueError:
                    # It might contain calls or other non-literals, skip
                    pass
        except Exception:
            pass

class Entropy:
    def __init__(self):
        self.repo_root = os.getcwd()
        self.health_report: Dict[str, TestFileHealth] = {}
        self.critical_paths = self._load_critical_paths()
        try:
            self.repo = Repo(self.repo_root)
        except:
            self.repo = None

    def _load_critical_paths(self) -> List[str]:
        if os.path.exists(CRITICAL_PATHS_FILE):
            with open(CRITICAL_PATHS_FILE, 'r') as f:
                return json.load(f)
        return []

    def run_coverage(self):
        print("Phase 1: The Cartography (Running Tests with Coverage)...")
        # Run pytest with context enabled via pytest-cov
        cmd = [
            "pytest",
            "--cov=.",
            "--cov-context=test",
            "--cov-report=" # suppress terminal report
        ]
        subprocess.run(cmd, check=False)

    def analyze_coverage(self):
        print("Phase 1: Analyzing Coverage Map...")
        cov = coverage.Coverage()
        cov.load()
        data = cov.get_data()

        test_files = self._get_all_test_files()

        for tf in test_files:
            if tf not in self.health_report:
                 self.health_report[tf] = TestFileHealth(filepath=tf)
            if tf in self.critical_paths:
                self.health_report[tf].is_critical_path = True

        measured_files = data.measured_files()

        for measured_file in measured_files:
            if not os.path.exists(measured_file):
                continue

            # Skip test files from unique coverage calculation
            if "tests" in measured_file or "test_" in os.path.basename(measured_file):
                continue

            try:
                line_contexts = data.contexts_by_lineno(measured_file)
            except Exception:
                continue

            for lineno, contexts in line_contexts.items():
                if not contexts:
                    continue

                covering_test_files = set()
                for ctx in contexts:
                    for tf in test_files:
                        rel_tf = os.path.relpath(tf, self.repo_root)
                        if ctx.startswith(rel_tf):
                            covering_test_files.add(tf)
                            break

                if len(covering_test_files) == 1:
                    unique_file = list(covering_test_files)[0]
                    if unique_file in self.health_report:
                        self.health_report[unique_file].unique_coverage_lines += 1

    def _get_all_test_files(self):
        test_files = []
        for root, _, files in os.walk("tests"):
            for file in files:
                if file.startswith("test_") and file.endswith(".py"):
                    test_files.append(os.path.join(root, file))
        return test_files

    def analyze_rot(self):
        print("Phase 2: The Rot Scan...")
        for tf, health in self.health_report.items():
            if health.is_critical_path:
                continue

            try:
                with open(tf, 'r', encoding='utf-8') as f:
                    content = f.read()
            except:
                continue

            # LOC
            lines = content.splitlines()
            health.loc = len(lines)

            # Token Cost
            health.token_cost = len(content) // 4
            if health.token_cost > CONFIG["maxTokenContext"]:
                health.rot_tags.append("CONTEXT_BLOAT")

            # AST Analysis
            try:
                tree = ast.parse(content)
                visitor = RotVisitor()
                visitor.visit(tree)

                mock_lines = len(visitor.mock_lines)
                if health.loc > 0:
                    health.mock_density = mock_lines / health.loc

                if health.mock_density > CONFIG["maxMockDensity"]:
                    health.rot_tags.append("BRITTLE_MOCKING")

                if visitor.tautologies > 0:
                    health.rot_tags.append("TAUTOLOGY")
            except Exception as e:
                print(f"Error parsing {tf}: {e}")

            # Churn
            health.churn_rate = self._get_churn(tf)
            if health.churn_rate > CONFIG["churnThreshold"]:
                health.rot_tags.append("HIGH_CHURN")

    def _get_churn(self, filepath):
        if not self.repo:
            return 0
        try:
            commits = list(self.repo.iter_commits(paths=filepath, since="30.days.ago"))
            return len(commits)
        except Exception:
            return 0

    def decide_actions(self):
        print("Phase 3: The Verdict...")
        for tf, health in self.health_report.items():
            # Immunity Check
            if health.is_critical_path or health.unique_coverage_lines > CONFIG["minUniqueCoverageThreshold"]:
                # Immune to Deletion
                pass
            else:
                if "BRITTLE_MOCKING" in health.rot_tags or "TAUTOLOGY" in health.rot_tags:
                    if health.unique_coverage_lines == 0:
                        health.suggested_action = "DELETE"
                        health.rationale = f"Brittle/Tautology & 0 Unique Coverage. Mock Density: {health.mock_density:.2f}"

            # Quarantine Check
            if health.suggested_action == "NONE":
                if "HIGH_CHURN" in health.rot_tags and len(health.rot_tags) > 1:
                     health.suggested_action = "QUARANTINE"
                     health.rationale = f"High Churn ({health.churn_rate}) & Rot: {', '.join(health.rot_tags)}"

            # Refactor Check (Bloat)
            if health.suggested_action == "NONE":
                if "CONTEXT_BLOAT" in health.rot_tags:
                    health.suggested_action = "REFACTOR"
                    health.rationale = f"Context Bloat ({health.token_cost} tokens)"

    def execute_actions(self):
        print("Phase 4: The Cleanse...")

        actions = [h for h in self.health_report.values() if h.suggested_action != "NONE"]

        # Vibe Check
        if len([a for a in actions if a.suggested_action in ["DELETE", "QUARANTINE"]]) > CONFIG["vibeCheckThreshold"]:
            print(f"ABORT: Vibe Check Failed. Too many files ({len(actions)}) flagged.")
            return

        deleted_files = []
        quarantined_files = []
        refactored_files = []

        for health in actions:
            if health.suggested_action == "DELETE":
                if CONFIG["executionMode"] == "PR_SUGGESTION":
                    try:
                        os.remove(health.filepath)
                        deleted_files.append(health)
                    except Exception as e:
                        print(f"Failed to delete {health.filepath}: {e}")

            elif health.suggested_action == "QUARANTINE":
                if CONFIG["executionMode"] == "PR_SUGGESTION":
                    dest = os.path.join(QUARANTINE_DIR, os.path.basename(health.filepath))
                    os.makedirs(QUARANTINE_DIR, exist_ok=True)
                    try:
                        shutil.move(health.filepath, dest)
                        quarantined_files.append(health)
                    except Exception as e:
                        print(f"Failed to move {health.filepath}: {e}")

            elif health.suggested_action == "REFACTOR":
                if CONFIG["executionMode"] == "PR_SUGGESTION":
                    success = self._apply_refactor(health.filepath)
                    if success:
                        health.rationale += " (Snapshots externalized)"
                        refactored_files.append(health)

        self._generate_markdown(deleted_files, quarantined_files, refactored_files)

    def _apply_refactor(self, filepath: str) -> bool:
        """
        Externalizes large literals to JSON files.
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source)
            extractor = SnapshotExtractor(source)
            extractor.visit(tree)

            if not extractor.replacements:
                return False

            # Sort replacements by start line descending to avoid offset issues
            # Node locations: lineno is 1-based, col_offset is 0-based
            # We need strictly safe replacements.
            # Given complexity of exact character replacement without CST, we will try a simpler approach.
            # We will use string slicing based on lines.

            lines = source.splitlines(keepends=True)
            new_lines = lines[:] # Copy

            os.makedirs(SNAPSHOTS_DIR, exist_ok=True)

            replacements_made = 0

            # Sort by line number descending
            sorted_replacements = sorted(extractor.replacements, key=lambda x: x[0].lineno, reverse=True)

            # We need to add 'import json' if not present
            needs_json_import = True
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == 'json':
                            needs_json_import = False
                elif isinstance(node, ast.ImportFrom):
                    if node.module == 'json':
                        needs_json_import = False

            if needs_json_import:
                # Naively add to top
                new_lines.insert(0, "import json\n")

            modified_lines = set()

            for node, val in sorted_replacements:
                start_line = node.lineno - 1
                end_line = node.end_lineno - 1

                # Verify we haven't touched these lines yet
                # Since we sort reverse, checking if we already modified this line is safe for single-line overlaps
                # But for safety, if we have multiple replacements on the same line, we skip the subsequent ones (which are actually earlier in file but processed later due to reverse sort? No.
                # Reverse sort means we process bottom of file first.
                # So if we process line 100, then line 50. Safe.
                # If we have two on line 100?
                # We process the one with higher lineno? They have same lineno.
                # Stable sort preserves order? No, key is lineno.
                # We should sort by lineno DESC, col_offset DESC.

                # If we encounter a line already modified, it means we have a collision or overlap we can't handle safely with this naive approach.
                if any(i in modified_lines for i in range(start_line, end_line + 1)):
                    continue

                # Generate snapshot filename
                h = hashlib.md5(str(val).encode()).hexdigest()[:8]
                snapshot_name = f"{os.path.basename(filepath).replace('.py', '')}_{h}.json"
                snapshot_path = os.path.join(SNAPSHOTS_DIR, snapshot_name)

                # Save JSON
                with open(snapshot_path, 'w') as f:
                    json.dump(val, f, indent=2)

                # Replace code
                start_col = node.col_offset
                end_col = node.end_col_offset

                replacement_code = f"json.load(open('{snapshot_path}'))"

                # Handle single line vs multi line
                if start_line == end_line:
                    line = new_lines[start_line]
                    pre = line[:start_col]
                    post = line[end_col:]
                    new_lines[start_line] = pre + replacement_code + post
                else:
                    # Multi-line replacement
                    # First line
                    new_lines[start_line] = new_lines[start_line][:start_col] + replacement_code
                    # Last line
                    last_line_remainder = new_lines[end_line][end_col:]
                    new_lines[start_line] += last_line_remainder

                    # Clear intermediate lines
                    for i in range(start_line + 1, end_line + 1):
                         new_lines[i] = ""

                for i in range(start_line, end_line + 1):
                    modified_lines.add(i)

                replacements_made += 1

            if replacements_made > 0:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write("".join(new_lines))
                return True

        except Exception as e:
            print(f"Failed to refactor {filepath}: {e}")
            return False

        return False

    def _generate_markdown(self, deleted, quarantined, refactored):
        with open(REPORT_FILE, 'w') as f:
            f.write("# [Entropy] Maintenance - Liability Reduction\n\n")
            f.write("| File | Rot Type | Unique Coverage | Action Taken | Rationale |\n")
            f.write("|------|----------|-----------------|--------------|-----------|\n")

            for item in deleted + quarantined + refactored:
                rot_str = ", ".join(item.rot_tags)
                f.write(f"| {os.path.basename(item.filepath)} | {rot_str} | {item.unique_coverage_lines} lines | {item.suggested_action} | {item.rationale} |\n")

            f.write("\n\n**Generated by Entropy Protocol**")

def main():
    entropy = Entropy()
    entropy.run_coverage()
    entropy.analyze_coverage()
    entropy.analyze_rot()
    entropy.decide_actions()
    entropy.execute_actions()

if __name__ == "__main__":
    main()
