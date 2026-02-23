import os
import sys
import json
import ast
import shutil
import subprocess
import argparse
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from pathlib import Path

# Configuration
class EntropyConfig:
    MAX_TOKEN_CONTEXT = 2000
    MAX_MOCK_DENSITY = 0.55
    MIN_UNIQUE_COVERAGE = 5
    MAX_CHURN_RATE = 5  # commits in last 30 days
    CRITICAL_PATHS_FILE = "critical_paths.json"
    QUARANTINE_DIR = "tests/quarantine"
    SNAPSHOT_DIR = "tests/snapshots"
    REPORT_FILE = "entropy_report.md"

@dataclass
class TestFileHealth:
    filepath: str
    loc: int = 0
    mock_density: float = 0.0
    churn_rate: int = 0
    token_cost: int = 0
    unique_coverage_lines: int = 0
    is_critical: bool = False
    rot_verdict: Optional['RotVerdict'] = None

@dataclass
class RotVerdict:
    score: int
    tags: List[str] = field(default_factory=list) # BRITTLE_MOCKING, CONTEXT_BLOAT, REDUNDANT_COVERAGE, TAUTOLOGY, HIGH_CHURN
    suggested_action: str = "NONE" # QUARANTINE, REFACTOR, DELETE, NONE

class EntropyScanner:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.critical_paths = self._load_critical_paths()
        self.health_map: Dict[str, TestFileHealth] = {}
        self.global_coverage_drop_check_passed = True

    def _load_critical_paths(self) -> Set[str]:
        if os.path.exists(EntropyConfig.CRITICAL_PATHS_FILE):
            with open(EntropyConfig.CRITICAL_PATHS_FILE, 'r') as f:
                return set(json.load(f))
        return set()

    def run_coverage(self):
        print("Phase 1: The Cartography (Mapping & Coverage)...")
        # clean old coverage
        if os.path.exists(".coverage"):
            os.remove(".coverage")

        # Run pytest with coverage and context
        cmd = [
            sys.executable, "-m", "pytest",
            "--cov=.",
            "--cov-context=test",
            "-q"
        ]
        print(f"Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=False) # check=False because tests might fail, but we still want coverage

        # Generate json report with contexts
        subprocess.run([sys.executable, "-m", "coverage", "json", "--show-contexts"], check=True)

        if not os.path.exists("coverage.json"):
            print("Error: coverage.json not generated.")
            sys.exit(1)

    def analyze_unique_coverage(self):
        print("Analyzing unique coverage...")
        with open("coverage.json", 'r') as f:
            cov_data = json.load(f)

        # Map: line_key (file:line) -> Set[test_context]
        line_coverage_map: Dict[str, Set[str]] = {}

        files_covered = cov_data.get("files", {})
        for filename, file_data in files_covered.items():
            contexts = file_data.get("contexts", {})
            for context, lines in contexts.items():
                # context is like "tests/test_foo.py::test_bar|run"
                # We care about the file "tests/test_foo.py"
                if "|" in context:
                    test_name = context.split("|")[0]
                    test_file = test_name.split("::")[0]
                else:
                    test_file = context

                # We only care if the test file is in tests/
                if not test_file.startswith("tests/"):
                    continue

                for line in lines:
                    key = f"{filename}:{line}"
                    if key not in line_coverage_map:
                        line_coverage_map[key] = set()
                    line_coverage_map[key].add(test_file)

        # Now count unique lines per test file
        unique_counts: Dict[str, int] = {}

        for key, test_files in line_coverage_map.items():
            if len(test_files) == 1:
                unique_test_file = list(test_files)[0]
                unique_counts[unique_test_file] = unique_counts.get(unique_test_file, 0) + 1

        # Initialize health map for all test files found in tests/ directory
        for root, _, files in os.walk("tests"):
            for file in files:
                if file.startswith("test_") and file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    # Normalize path separators
                    filepath = filepath.replace("\\", "/")

                    is_critical = filepath in self.critical_paths
                    # If critical, infinite unique coverage (handled in logic or by high number)
                    unique_lines = unique_counts.get(filepath, 0)
                    if is_critical:
                        unique_lines = 999999

                    self.health_map[filepath] = TestFileHealth(
                        filepath=filepath,
                        unique_coverage_lines=unique_lines,
                        is_critical=is_critical
                    )

    def get_git_churn(self, filepath: str) -> int:
        try:
            cmd = ["git", "log", "--since=30 days ago", "--format=oneline", "--", filepath]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return len(result.stdout.strip().splitlines())
        except subprocess.CalledProcessError:
            return 0

    def analyze_rot(self):
        print("Phase 2: The Rot Scan...")
        for filepath, health in self.health_map.items():
            if not os.path.exists(filepath):
                continue

            with open(filepath, 'r') as f:
                content = f.read()

            lines = content.splitlines()
            health.loc = len(lines)

            # Token cost (approx)
            health.token_cost = len(content) // 4

            # Mock Density
            mock_lines = 0
            for line in lines:
                if "mock" in line.lower() or "patch" in line.lower() or "spy" in line.lower():
                    mock_lines += 1

            if health.loc > 0:
                health.mock_density = mock_lines / health.loc

            # Churn
            health.churn_rate = self.get_git_churn(filepath)

            # AST Analysis for Tautologies and Bloat
            try:
                tree = ast.parse(content)
                analyzer = RotAnalyzer()
                analyzer.visit(tree)

                has_tautology = analyzer.has_tautology
                has_bloat = analyzer.has_bloat
            except SyntaxError:
                has_tautology = False
                has_bloat = False

            # Determine Verdict
            tags = []
            if health.mock_density > EntropyConfig.MAX_MOCK_DENSITY:
                tags.append("BRITTLE_MOCKING")
            if health.token_cost > EntropyConfig.MAX_TOKEN_CONTEXT:
                tags.append("CONTEXT_BLOAT")
            if has_bloat:
                tags.append("CONTEXT_BLOAT") # Bloat detected via AST
            if has_tautology:
                tags.append("TAUTOLOGY")
            if health.churn_rate > EntropyConfig.MAX_CHURN_RATE:
                tags.append("HIGH_CHURN")
            if health.unique_coverage_lines == 0 and not health.is_critical:
                 tags.append("REDUNDANT_COVERAGE")

            score = len(tags) * 20 # Simplified score

            action = "NONE"

            # Strategy Logic

            # Strategy C: Quarantine
            if "HIGH_CHURN" in tags and ("BRITTLE_MOCKING" in tags or "CONTEXT_BLOAT" in tags or "TAUTOLOGY" in tags):
                action = "QUARANTINE"

            # Strategy B: Liability Prune
            # Delete if (Brittle OR Tautology) AND 0 unique coverage
            elif ("BRITTLE_MOCKING" in tags or "TAUTOLOGY" in tags) and health.unique_coverage_lines == 0:
                 action = "DELETE"

            # Strategy A: Bloat Reducer
            elif "CONTEXT_BLOAT" in tags:
                action = "REFACTOR_NEEDED" # We will flag it, but automation for refactoring is complex.

            health.rot_verdict = RotVerdict(score=score, tags=tags, suggested_action=action)

    def _check_coverage_cliff(self, files_to_act_on: List[TestFileHealth]) -> bool:
        """
        Returns True if executing the actions would drop global coverage by > 0.5%.
        """
        # Load coverage.json
        try:
            with open("coverage.json", 'r') as f:
                cov_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return True # Fail safe

        if "totals" in cov_data:
             current_covered = cov_data["totals"]["covered_lines"]
             current_total = cov_data["totals"]["num_statements"]
             if current_total == 0:
                 return False
             current_percentage = (current_covered / current_total) * 100
        else:
             return True # Fail safe

        # Identify files being deleted
        files_to_delete_paths = {f.filepath for f in files_to_act_on if f.rot_verdict.suggested_action == "DELETE"}

        if not files_to_delete_paths:
            return False

        # Identify lost lines
        lost_lines_count = 0
        files_covered = cov_data.get("files", {})
        line_to_tests: Dict[str, Set[str]] = {}

        for filename, file_data in files_covered.items():
            contexts = file_data.get("contexts", {})
            for context, lines in contexts.items():
                if "|" in context:
                    test_name = context.split("|")[0]
                    test_file = test_name.split("::")[0]
                else:
                    test_file = context

                if not test_file.startswith("tests/"):
                    continue

                for line in lines:
                    key = f"{filename}:{line}"
                    if key not in line_to_tests:
                        line_to_tests[key] = set()
                    line_to_tests[key].add(test_file)

        for key, tests in line_to_tests.items():
            # Check if all covering tests are in files_to_delete_paths
            # Normalize paths in tests set to match filepath format
            # tests are like "tests/test_foo.py"
            # files_to_delete_paths are relative paths

            # Since my logic normalizes filepaths in health_map, ensure they match coverage contexts.
            # Coverage contexts usually match relative paths from root if run from root.

            # If tests set is a subset of files_to_delete_paths, the line is lost
            if tests and tests.issubset(files_to_delete_paths):
                lost_lines_count += 1

        new_covered = current_covered - lost_lines_count
        new_percentage = (new_covered / current_total) * 100

        drop = current_percentage - new_percentage
        print(f"Projected Coverage Drop: {drop:.4f}% (Lost {lost_lines_count} lines)")

        return drop > 0.5

    def execute_actions(self):
        print("Phase 3 & 4: Verdict & Cleanse...")

        files_to_act_on = [h for h in self.health_map.values() if h.rot_verdict and h.rot_verdict.suggested_action in ["DELETE", "QUARANTINE"]]

        # Safety Net
        aborted = False
        if len(files_to_act_on) > 20:
            print(f"SAFETY NET ABORT: {len(files_to_act_on)} files flagged. Max 20 allowed.")
            aborted = True

        # Coverage Cliff Check
        if not aborted:
             if self._check_coverage_cliff(files_to_act_on):
                 print("COVERAGE CLIFF ABORT: Global statement coverage would drop by > 0.5%.")
                 aborted = True

        report_lines = [
            "# [Entropy] Maintenance - Liability Reduction",
            "",
            "| File | Rot Type | Unique Coverage | Action Taken | Rationale |",
            "|---|---|---|---|---|"
        ]

        for health in self.health_map.values():
            if not health.rot_verdict or health.rot_verdict.suggested_action == "NONE":
                continue

            action = health.rot_verdict.suggested_action
            tags_str = ", ".join(health.rot_verdict.tags)
            rationale = f"Score: {health.rot_verdict.score}. {tags_str}"

            action_msg = "NONE"

            if aborted and action in ["DELETE", "QUARANTINE"]:
                 action_msg = f"WOULD_{action} (ABORTED)"
            elif action == "DELETE":
                if not self.dry_run:
                    try:
                        os.remove(health.filepath)
                        action_msg = "DELETED"
                    except OSError:
                        action_msg = "FAILED_DELETE"
                else:
                    action_msg = "WOULD_DELETE"

            elif action == "QUARANTINE":
                target_path = os.path.join(EntropyConfig.QUARANTINE_DIR, health.filepath)
                if not self.dry_run:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    try:
                         shutil.move(health.filepath, target_path)
                         action_msg = "QUARANTINED"
                    except OSError:
                         action_msg = "FAILED_QUARANTINE"
                else:
                    action_msg = "WOULD_QUARANTINE"

            elif action == "REFACTOR_NEEDED":
                action_msg = "REFACTOR_NEEDED"

            report_lines.append(f"| {health.filepath} | {tags_str} | {health.unique_coverage_lines} | {action_msg} | {rationale} |")

        with open(EntropyConfig.REPORT_FILE, 'w') as f:
            f.write("\n".join(report_lines))

        print(f"Report generated: {EntropyConfig.REPORT_FILE}")

class RotAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.has_tautology = False
        self.has_bloat = False

    def visit_Assert(self, node):
        # Check for assert True, assert 1, assert 'a'
        if isinstance(node.test, ast.Constant):
             if node.test.value: # assert True
                 self.has_tautology = True

        # Check for assert x == x
        if isinstance(node.test, ast.Compare):
            if len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq):
                left = node.test.left
                right = node.test.comparators[0]
                if isinstance(left, ast.Name) and isinstance(right, ast.Name):
                    if left.id == right.id:
                        self.has_tautology = True
        self.generic_visit(node)

    def visit_List(self, node):
        # Check for large lists > 20 elements
        if len(node.elts) > 20:
             self.has_bloat = True
        self.generic_visit(node)

    def visit_Dict(self, node):
         # Check for large dicts > 20 keys
        if len(node.keys) > 20:
             self.has_bloat = True
        self.generic_visit(node)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Entropy: Repository Sanitation & De-inflation")
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions without modifying files")
    args = parser.parse_args()

    scanner = EntropyScanner(dry_run=args.dry_run)
    scanner.run_coverage()
    scanner.analyze_unique_coverage()
    scanner.analyze_rot()
    scanner.execute_actions()
