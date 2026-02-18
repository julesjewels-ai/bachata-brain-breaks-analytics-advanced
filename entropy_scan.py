import os
import sys
import json
import ast
import subprocess
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
import git
import coverage

@dataclass
class RotVerdict:
    score: int
    tags: List[str]
    suggested_action: str

@dataclass
class TestFileHealth:
    filepath: str
    loc: int = 0
    mock_density: float = 0.0
    churn_rate: int = 0
    token_cost: int = 0
    unique_coverage_lines: int = 0
    is_critical_path: bool = False
    rot_verdict: Optional[RotVerdict] = None

class EntropyScanner:
    def __init__(self):
        self.config = {
            "maxTokenContext": 2000,
            "maxMockDensity": 0.55,
            "minUniqueCoverageThreshold": 5,
        }
        try:
            self.repo = git.Repo(".", search_parent_directories=True)
        except (git.InvalidGitRepositoryError, git.NoSuchPathError):
            self.repo = None
            print("Warning: Not a valid git repository. Churn metrics will be 0.")

        self.critical_paths = self._load_critical_paths()
        self.health_report: Dict[str, TestFileHealth] = {}
        self.global_initial_coverage = 0.0
        self.cov = None

    def _load_critical_paths(self) -> List[str]:
        if os.path.exists("critical_paths.json"):
            try:
                with open("critical_paths.json", "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return []
        return []

    def run_coverage(self):
        print("Phase 1: Cartography (Mapping & Coverage)...")
        # Clean previous coverage
        if os.path.exists(".coverage"):
            os.remove(".coverage")
        if os.path.exists("coverage.json"):
            os.remove("coverage.json")

        # Run pytest with coverage and context
        cmd = [
            sys.executable, "-m", "pytest",
            "--cov=src",
            "--cov-report=json",
            "--cov-context=test",
            "tests/"
        ]
        print(f"Running command: {' '.join(cmd)}")
        # We allow check=False because some tests might fail, but we still want to analyze coverage where possible.
        # However, if tests fail, coverage might be incomplete. The prompt assumes "Run the full test suite".
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()
        subprocess.run(cmd, env=env, check=False)

        # Load coverage data
        self.cov = coverage.Coverage()
        try:
            self.cov.load()
        except coverage.misc.CoverageException:
            print("Warning: No coverage data found.")

    def calculate_unique_coverage(self) -> Dict[str, int]:
        print("Calculating Unique Coverage...")
        if not self.cov:
            return {}

        # Get data from .coverage sqlite db
        try:
            data = self.cov.get_data()
        except coverage.misc.CoverageException:
            return {}

        # Map: line -> set of contexts (tests)
        line_contexts: Dict[str, Set[str]] = {} # "file:line" -> {contexts}

        for filename in data.measured_files():
            for line in data.lines(filename):
                contexts = data.contexts_by_lineno(filename).get(line, [])
                if contexts:
                    key = f"{filename}:{line}"
                    # Filter contexts to only include test contexts (start with "tests/" or "tests.")
                    # Pytest contexts are usually "tests/test_file.py::test_func" or similar
                    test_contexts = set()
                    for c in contexts:
                        # Context structure depends on pytest-cov configuration.
                        # Usually: "tests/test_foo.py::test_bar"
                        if "tests/" in c or "tests." in c:
                             test_contexts.add(c)

                    if test_contexts:
                        line_contexts[key] = test_contexts

        # Count unique lines per test file
        test_file_unique_counts: Dict[str, int] = {}

        for key, contexts in line_contexts.items():
            if len(contexts) == 1:
                ctx = list(contexts)[0]
                # Extract filename from context
                # "tests/test_file.py::test_func" -> "tests/test_file.py"
                if "::" in ctx:
                    test_file = ctx.split("::")[0]
                elif "|" in ctx:
                    test_file = ctx.split("|")[0]
                else:
                    test_file = ctx # Fallback

                # Normalize path
                try:
                    test_file = os.path.relpath(test_file)
                except ValueError:
                    pass # Keep as is if relpath fails

                test_file_unique_counts[test_file] = test_file_unique_counts.get(test_file, 0) + 1

        return test_file_unique_counts

    def analyze_rot(self):
        print("Phase 2: The Rot Scan (AST Analysis)...")
        test_files = list(Path("tests").rglob("test_*.py"))
        unique_counts = self.calculate_unique_coverage()
        print(f"Unique Coverage Counts: {unique_counts}")

        if not unique_counts and test_files:
             print("Warning: No unique coverage data found. Coverage might have failed. Aborting analysis to prevent accidental deletions.")
             return

        for test_file in test_files:
            filepath = str(test_file)
            try:
                content = test_file.read_text(encoding='utf-8')
            except Exception:
                continue

            lines = content.splitlines()
            loc = len(lines)

            # Mock Density
            mock_lines = sum(1 for line in lines if "mock" in line.lower() or "patch" in line.lower())
            mock_density = mock_lines / loc if loc > 0 else 0

            # Token Cost (Approx)
            token_cost = len(content) // 4

            # Churn
            churn = 0
            if self.repo:
                try:
                    # git log --oneline --since="30 days ago" -- <file> | wc -l
                    commits = list(self.repo.iter_commits(paths=filepath, max_count=100, since="30.days.ago"))
                    churn = len(commits)
                except Exception:
                    pass

            # Tautology Check
            has_tautology = self._check_tautology(content)

            # Bloat Check
            is_bloated = token_cost > self.config["maxTokenContext"]

            # Unique Coverage
            unique_cov = unique_counts.get(filepath, 0)
            if filepath in self.critical_paths:
                unique_cov = 999999

            # Verdict
            tags = []
            if mock_density > self.config["maxMockDensity"]:
                tags.append("BRITTLE_MOCKING")
            if is_bloated:
                tags.append("CONTEXT_BLOAT")
            if has_tautology:
                tags.append("TAUTOLOGY")

            action = "NONE"

            # Strategy A: Bloat
            # Implemented as flagging for now

            # Strategy B: Liability Prune
            if (("BRITTLE_MOCKING" in tags or "TAUTOLOGY" in tags) and unique_cov == 0):
                action = "DELETE"

            # Strategy C: Quarantine
            elif churn > 5 and len(tags) > 0:
                 action = "QUARANTINE"

            verdict = RotVerdict(score=len(tags)*10, tags=tags, suggested_action=action)

            health = TestFileHealth(
                filepath=filepath,
                loc=loc,
                mock_density=mock_density,
                churn_rate=churn,
                token_cost=token_cost,
                unique_coverage_lines=unique_cov,
                is_critical_path=filepath in self.critical_paths,
                rot_verdict=verdict
            )
            self.health_report[filepath] = health

    def _check_tautology(self, content):
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assert):
                    # assert True
                    if isinstance(node.test, ast.Constant) and node.test.value is True:
                        return True
                    # assert x == x
                    if isinstance(node.test, ast.Compare):
                        left = node.test.left
                        if len(node.test.comparators) == 1:
                            right = node.test.comparators[0]
                            # Simple name check
                            if isinstance(left, ast.Name) and isinstance(right, ast.Name) and left.id == right.id:
                                return True
                            # Simple constant check
                            if isinstance(left, ast.Constant) and isinstance(right, ast.Constant) and left.value == right.value:
                                return True
        except:
            pass
        return False

    def execute_actions(self):
        print("Phase 3: The Verdict & Action...")

        # Guardrail: Count actions first
        actions = []
        for filepath, health in self.health_report.items():
            if health.rot_verdict.suggested_action in ["DELETE", "QUARANTINE"]:
                actions.append((filepath, health.rot_verdict.suggested_action))

        if len(actions) > 20:
            print(f"ABORTING: Too many files flagged ({len(actions)} > 20). Guardrail activated.")
            return

        for filepath, action in actions:
            if action == "DELETE":
                print(f"Deleting {filepath} (Liability Prune)")
                try:
                    os.remove(filepath)
                except OSError as e:
                    print(f"Error deleting {filepath}: {e}")
            elif action == "QUARANTINE":
                print(f"Quarantining {filepath}")
                try:
                    dest_dir = Path("tests/quarantine")
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest = dest_dir / Path(filepath).name
                    shutil.move(filepath, dest)
                except OSError as e:
                    print(f"Error quarantining {filepath}: {e}")

    def generate_report(self):
        print("Phase 4: The Cleanse (Output)...")
        report_lines = []
        report_lines.append("| File | Rot Type | Unique Coverage | Action Taken | Rationale |")
        report_lines.append("|---|---|---|---|---|")

        flagged = False
        for filepath, health in self.health_report.items():
            if health.rot_verdict.suggested_action != "NONE" or health.rot_verdict.tags:
                flagged = True
                tags = ", ".join(health.rot_verdict.tags)
                action = health.rot_verdict.suggested_action
                unique = health.unique_coverage_lines
                rationale = f"MockDensity: {health.mock_density:.2f}, Churn: {health.churn_rate}, Tokens: {health.token_cost}"
                report_lines.append(f"| {filepath} | {tags} | {unique} | {action} | {rationale} |")

        if not flagged:
            report_lines.append("| None | None | - | None | No issues found |")

        report_content = "\n".join(report_lines)
        print(report_content)

        with open("entropy_report.md", "w") as f:
            f.write("# Entropy Report\n\n")
            f.write(report_content)

if __name__ == "__main__":
    scanner = EntropyScanner()
    scanner.run_coverage()
    scanner.analyze_rot()
    scanner.execute_actions()
    scanner.generate_report()
