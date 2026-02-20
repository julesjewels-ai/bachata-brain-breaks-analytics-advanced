import ast
import json
import os
import shutil
import subprocess
import sys
import sqlite3
import coverage
import re
from pathlib import Path
from typing import Dict, List, Set, Any, Optional, Tuple
from datetime import datetime, timedelta

# Configuration
MAX_TOKEN_CONTEXT = 2000
MAX_MOCK_DENSITY = 0.55
MIN_UNIQUE_COVERAGE = 5
MAX_CHURN_COMMITS = 5
CRITICAL_PATHS_FILE = "critical_paths.json"
QUARANTINE_DIR = "tests/quarantine"
COVERAGE_FILE = ".coverage"
REPORT_FILE = "entropy_report.md"

# Safety Guardrails
MAX_FILES_AFFECTED = 20
MAX_COVERAGE_DROP = 0.5  # Percentage points

def load_critical_paths() -> Set[str]:
    if not os.path.exists(CRITICAL_PATHS_FILE):
        return set()
    try:
        with open(CRITICAL_PATHS_FILE, "r") as f:
            # We assume paths in json are relative and posix style
            return set(json.load(f))
    except Exception as e:
        print(f"Warning: Could not load critical paths: {e}")
        return set()

def ensure_quarantine_exists():
    Path(QUARANTINE_DIR).mkdir(parents=True, exist_ok=True)
    # We explicitly do NOT add .gitignore here to ensure CI can run quarantined tests.
    # Exclusion from AI context should be handled via .cursorignore.

class CoverageMapper:
    def __init__(self):
        # Initialize coverage object pointing to the file we'll generate
        self.cov = coverage.Coverage(data_file=COVERAGE_FILE)

    def generate_coverage(self):
        """Runs pytest with coverage to generate the .coverage database."""
        # Remove existing coverage file to start fresh
        if os.path.exists(COVERAGE_FILE):
            os.remove(COVERAGE_FILE)

        # Using subprocess to run pytest ensuring context capture
        # We use 'python -m pytest' to ensure we use the same environment
        cmd = [
            sys.executable, "-m", "pytest",
            "--cov=src",
            "--cov-context=test",
            "tests/"
        ]
        print("Running tests to generate coverage map (this may take a moment)...")
        # Capture output to avoid clutter, unless error
        result = subprocess.run(cmd, capture_output=True, text=True)

        # We don't necessarily fail here if tests fail, as we might be cleaning up broken tests.
        if result.returncode != 0:
            print(f"Warning: Tests failed during coverage generation.\n{result.stderr[:500]}...")
        else:
            print("Tests passed successfully.")

        # Reload the coverage data
        self.cov.load()

    def get_unique_coverage(self) -> Dict[str, int]:
        """
        Calculates unique lines of code covered by each test file.
        Returns: { 'tests/test_foo.py': 12, ... }
        """
        unique_coverage: Dict[str, int] = {}

        # Use coverage API to get data
        try:
            data = self.cov.get_data()
            # measured_files() returns absolute paths usually, need to handle that
            files = data.measured_files()
        except Exception as e:
            print(f"Error accessing coverage data: {e}")
            return {}

        cwd = os.getcwd()

        for src_file in files:
            # We care about source files in src/, not tests themselves
            # Ensure src_file path normalization
            normalized_src = Path(src_file).as_posix()
            if "site-packages" in normalized_src or "tests/" in normalized_src:
                continue

            try:
                # contexts_by_lineno returns {lineno: [contexts]}
                # Contexts are like 'tests/test_core.py::test_fn|run'
                contexts_map = data.contexts_by_lineno(src_file)
            except AttributeError:
                print("Error: Coverage data does not support contexts.")
                return {}

            for lineno, contexts in contexts_map.items():
                if not contexts:
                    continue

                # Extract test file paths from contexts
                contributing_tests = set()
                for ctx in contexts:
                    if not ctx or ctx == "":
                        continue
                    # Context format: test_file.py::test_func|run or just test_file.py
                    # We want the file path relative to root if possible
                    parts = ctx.split("::")[0]
                    if "|" in parts:
                        parts = parts.split("|")[0]

                    # Normalize path to relative posix
                    try:
                        if os.path.isabs(parts):
                            parts = os.path.relpath(parts, cwd)
                    except ValueError:
                        pass # Path on different drive

                    contributing_tests.add(Path(parts).as_posix())

                # Filter out non-test contexts if any (like 'src/main.py')
                test_files = {t for t in contributing_tests if "tests/" in t or "test_" in t}

                if len(test_files) == 1:
                    # This line is uniquely covered by this test file
                    unique_test = list(test_files)[0]
                    unique_coverage[unique_test] = unique_coverage.get(unique_test, 0) + 1

        return unique_coverage

    def get_total_coverage_percent(self) -> float:
        """Returns the total line coverage percentage."""
        try:
            # coverage.py 5.0+ report returns a float
            val = self.cov.report(file=open(os.devnull, 'w'))
            return val
        except Exception:
             # Fallback to json output parsing via subprocess if API fails
             cmd = [sys.executable, "-m", "coverage", "json", "-o", "-"]
             result = subprocess.run(cmd, capture_output=True, text=True)
             try:
                 data = json.loads(result.stdout)
                 return data["totals"]["percent_covered"]
             except Exception:
                 return 0.0

class RotScanner(ast.NodeVisitor):
    def __init__(self):
        self.mock_lines = 0
        self.total_lines = 0
        self.tautologies = 0
        self.assertions = 0
        self.large_literals = 0  # Number of large dict/list literals (potential Bloat)

    def visit_Call(self, node):
        # Check for mock usage
        # e.g., patch('...'), Mock(), MagicMock(), spyOn()
        is_mock = False
        if isinstance(node.func, ast.Name):
            if node.func.id in ['patch', 'Mock', 'MagicMock', 'spyOn']:
                is_mock = True
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in ['patch', 'Mock', 'MagicMock', 'spyOn']:
                is_mock = True

        if is_mock:
            self.mock_lines += 1

        # Check for tautologies in assertions
        # e.g., assertEqual(x, x)
        if isinstance(node.func, ast.Attribute) and node.func.attr.startswith("assert"):
            if len(node.args) >= 2:
                arg1 = node.args[0]
                arg2 = node.args[1]
                if self._are_nodes_equal(arg1, arg2):
                    self.tautologies += 1

        self.generic_visit(node)

    def visit_Assert(self, node):
        # Check for assert True
        if isinstance(node.test, ast.Constant):
             if node.test.value is True:
                 self.tautologies += 1
        # Check for assert x == x
        if isinstance(node.test, ast.Compare):
             if len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq):
                 if len(node.test.comparators) > 0 and self._are_nodes_equal(node.test.left, node.test.comparators[0]):
                     self.tautologies += 1
        self.generic_visit(node)

    def visit_Dict(self, node):
        self._check_large_literal(node)
        self.generic_visit(node)

    def visit_List(self, node):
        self._check_large_literal(node)
        self.generic_visit(node)

    def _check_large_literal(self, node):
        # Check if literal spans many lines (Snapshot candidate)
        if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
             lines = node.end_lineno - node.lineno + 1
             if lines > 20: # Threshold for "Large" -> Snapshot candidate
                 self.large_literals += 1

    def _are_nodes_equal(self, n1, n2):
        if type(n1) != type(n2):
            return False
        if isinstance(n1, ast.Name):
            return n1.id == n2.id
        if isinstance(n1, ast.Constant):
            return n1.value == n2.value
        return False

    @classmethod
    def scan_file(cls, filepath: str) -> Dict[str, Any]:
        try:
            with open(filepath, "r", encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
             return {"mock_density": 0, "tautologies": 0, "token_cost": 0, "loc": 0, "large_literals": 0}

        try:
            tree = ast.parse(content)
        except SyntaxError:
             return {"mock_density": 0, "tautologies": 0, "token_cost": 0, "loc": 0, "large_literals": 0}

        scanner = cls()
        scanner.total_lines = len(content.splitlines())
        scanner.visit(tree)

        mock_density = scanner.mock_lines / scanner.total_lines if scanner.total_lines > 0 else 0
        token_cost = len(content) / 4.0 # Approximation

        return {
            "mock_density": mock_density,
            "tautologies": scanner.tautologies,
            "token_cost": token_cost,
            "loc": scanner.total_lines,
            "large_literals": scanner.large_literals
        }

def get_git_churn(filepath: str) -> int:
    """Returns number of commits in the last 30 days for the file."""
    try:
        # Check if git is available
        subprocess.run(["git", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        cmd = ["git", "log", "--since=30.days", "--oneline", "--", filepath]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return 0
        lines = result.stdout.strip().splitlines()
        return len(lines)
    except Exception:
        return 0

class SafetyNet:
    def __init__(self, mapper: CoverageMapper):
        self.mapper = mapper
        self.backups = {}
        self.initial_coverage = 0.0

    def capture_baseline(self):
        self.initial_coverage = self.mapper.get_total_coverage_percent()
        print(f"Initial Coverage: {self.initial_coverage:.2f}%")

    def backup_files(self, files: List[str]):
        for f in files:
             if os.path.exists(f):
                 shutil.copy2(f, f + ".bak")
                 self.backups[f] = f + ".bak"

    def restore_backups(self):
        print("🚨 Restoring backups due to safety violation...")
        for original, backup in self.backups.items():
            if os.path.exists(backup):
                shutil.move(backup, original)
        self.backups.clear()

    def verify_coverage_drop(self) -> bool:
        """Returns True if drop is acceptable, False if violation."""
        # Re-run coverage
        self.mapper.generate_coverage()
        new_coverage = self.mapper.get_total_coverage_percent()
        drop = self.initial_coverage - new_coverage
        print(f"New Coverage: {new_coverage:.2f}% (Drop: {drop:.2f}%)")

        if drop > MAX_COVERAGE_DROP:
            return False
        return True

    def cleanup_backups(self):
        for backup in self.backups.values():
            if os.path.exists(backup):
                os.remove(backup)
        self.backups.clear()

def main():
    print("📉 Entropy Protocol Initiated...")

    # Setup
    critical_paths = load_critical_paths()
    ensure_quarantine_exists()

    # 1. Cartography (Coverage)
    mapper = CoverageMapper()
    mapper.generate_coverage()
    unique_coverage = mapper.get_unique_coverage()

    safety = SafetyNet(mapper)
    safety.capture_baseline()

    # 2. Rot Scan & Verdict
    # Use glob to find all tests, normalize to POSIX relative paths
    test_files = [p.as_posix() for p in Path("tests").rglob("test_*.py")]
    actions = []

    print(f"Scanning {len(test_files)} test files...")

    for filepath in test_files:
        # Check immunity
        if filepath in critical_paths:
            print(f"Skipping critical path: {filepath}")
            continue

        rot_metrics = RotScanner.scan_file(filepath)
        churn = get_git_churn(filepath)

        # Get unique coverage (default 0 if not found)
        u_cov = unique_coverage.get(filepath, 0)

        # Determine Action
        action = "NONE"
        rationale = ""

        # Strategy A: Bloat Reducer (Snapshot Externalization)
        if rot_metrics["large_literals"] > 0:
            # We flag for manual refactoring or future automation
            action = "REFACTOR_NEEDED"
            rationale = f"Detected {rot_metrics['large_literals']} Large Literals (Potential Snapshot). Manual refactoring recommended for safety."

        # Strategy B: Liability Prune
        # Delete if brittle/tautological AND covers nothing unique
        if u_cov == 0:
            if rot_metrics["mock_density"] > MAX_MOCK_DENSITY:
                action = "DELETE"
                rationale = f"Brittle Mocking ({rot_metrics['mock_density']:.2f}), 0 Unique Coverage"
            elif rot_metrics["tautologies"] > 0:
                action = "DELETE"
                rationale = f"Tautologies detected ({rot_metrics['tautologies']}), 0 Unique Coverage"

        # Strategy C: Quarantine
        # High Churn (> 5 changes/month) AND High Rot Score.
        if action == "NONE":
             # We use mock density as a proxy for "Rot Score" if not explicit
             is_high_rot = rot_metrics["mock_density"] > 0.4 or rot_metrics["tautologies"] > 0
             if churn > MAX_CHURN_COMMITS and is_high_rot:
                 action = "QUARANTINE"
                 rationale = f"High Churn ({churn}) & Rot ({rot_metrics['mock_density']:.2f})"

        if action != "NONE":
            actions.append({
                "file": filepath,
                "action": action,
                "rationale": rationale,
                "metrics": rot_metrics,
                "unique_coverage": u_cov,
                "churn": churn
            })

    # Safety Guardrails (Quantity)
    if len(actions) > MAX_FILES_AFFECTED:
        print(f"🚨 ABORTING: Too many files flagged ({len(actions)} > {MAX_FILES_AFFECTED}). Review manually.")
        sys.exit(1)

    if not actions:
        print("✅ No actions needed. Repository is healthy.")
        sys.exit(0)

    # Backup files (only for destructive actions)
    destructive_actions = [a for a in actions if a["action"] in ("DELETE", "QUARANTINE")]
    files_to_touch = [a["file"] for a in destructive_actions]
    safety.backup_files(files_to_touch)

    # Execute Actions
    report_lines = []
    deleted_count = 0
    quarantined_count = 0
    refactor_count = 0

    print("\nExecuting Actions...")
    for item in actions:
        filepath = item["file"]
        action = item["action"]
        rationale = item["rationale"]

        if action == "DELETE":
            try:
                os.remove(filepath)
                deleted_count += 1
                print(f"❌ DELETED {filepath}: {rationale}")
            except OSError as e:
                print(f"Error deleting {filepath}: {e}")

        elif action == "QUARANTINE":
            try:
                filename = os.path.basename(filepath)
                dest = os.path.join(QUARANTINE_DIR, filename)
                shutil.move(filepath, dest)
                quarantined_count += 1
                print(f"☣️  QUARANTINED {filepath}: {rationale}")
            except OSError as e:
                print(f"Error moving {filepath}: {e}")

        elif action == "REFACTOR_NEEDED":
            refactor_count += 1
            print(f"⚠️  REFACTOR NEEDED {filepath}: {rationale}")

        report_lines.append(f"| {filepath} | {action} | {item['unique_coverage']} lines | {rationale} |")

    # Verify Coverage Drop (only if destructive actions occurred)
    if destructive_actions:
        print("\nVerifying Coverage Impact...")
        if not safety.verify_coverage_drop():
            safety.restore_backups()
            print("🚨 Safety Check Failed: Coverage dropped too much. Reverting changes.")
            sys.exit(1)

    safety.cleanup_backups()

    # Generate Report
    print(f"\n📉 Entropy Scan Complete. Deleted: {deleted_count}, Quarantined: {quarantined_count}, Refactor Needed: {refactor_count}")

    if report_lines:
        report_content = (
            "## [Entropy] Maintenance - Liability Reduction\n\n"
            "| File | Action | Unique Coverage | Rationale |\n"
            "|---|---|---|---|\n"
            + "\n".join(report_lines)
        )
        with open(REPORT_FILE, "w") as f:
            f.write(report_content)
        print(f"Report saved to {REPORT_FILE}")
        # Also print to stdout for PR description
        print("\n--- PR Description ---\n")
        print(report_content)

if __name__ == "__main__":
    main()
