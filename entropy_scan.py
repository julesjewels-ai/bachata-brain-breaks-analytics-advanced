import sys
import os
import subprocess
import json
import ast
import shutil
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any, Tuple
from pathlib import Path
import coverage

# Configuration
ENTROPY_CONFIG = {
    "maxTokenContext": 2000,
    "maxMockDensity": 0.55,
    "minUniqueCoverageThreshold": 5,
    "executionMode": "PR_SUGGESTION",
}

@dataclass
class TestFileHealth:
    file_path: str
    associated_source_files: List[str] = field(default_factory=list)
    loc: int = 0
    mock_density: float = 0.0
    churn_rate: int = 0
    token_cost: int = 0
    unique_coverage_lines: int = 0
    is_critical_path: bool = False
    has_tautology: bool = False

@dataclass
class RotVerdict:
    file: str
    score: int
    tags: List[str]
    suggested_action: str

class EntropyScanner:
    def __init__(self):
        self.project_root = Path(os.getcwd())
        self.critical_paths = self._load_critical_paths()
        self.test_files = self._discover_test_files()
        self.health_map: Dict[str, TestFileHealth] = {}

    def _load_critical_paths(self) -> Set[str]:
        try:
            with open("critical_paths.json", "r") as f:
                paths = json.load(f)
                # Normalize to absolute paths
                return {str(self.project_root / p) for p in paths}
        except FileNotFoundError:
            return set()

    def _discover_test_files(self) -> List[str]:
        return [str(p) for p in self.project_root.glob("tests/**/test_*.py")]

    def run_coverage(self):
        print("Phase 1: The Cartography (Running Coverage)...")
        # Ensure .coverage is clean
        if os.path.exists(".coverage"):
            os.remove(".coverage")

        cmd = [
            sys.executable, "-m", "pytest",
            "--cov=src",
            "--cov-report=json",
            "--cov-context=test"
        ]
        # We allow failure (exit code 1) because tests might fail, but we still want coverage
        subprocess.run(cmd, check=False)

    def calculate_unique_coverage(self):
        print("Calculating Unique Coverage...")
        cov = coverage.Coverage()
        cov.load()
        data = cov.get_data()

        # Initialize counts
        unique_counts = {str(Path(tf).resolve()): 0 for tf in self.test_files}
        # Also keep track of relative paths for lookup
        rel_to_abs = {tf: str(Path(tf).resolve()) for tf in self.test_files}

        measured_files = data.measured_files()

        for src_file in measured_files:
            try:
                # Use contexts_by_lineno method if available (coverage 5+)
                if hasattr(data, 'contexts_by_lineno'):
                    contexts_by_lineno = data.contexts_by_lineno(src_file)
                else:
                    # Fallback or different API version check
                    print(f"Warning: Coverage data object does not have contexts_by_lineno")
                    continue
            except Exception as e:
                print(f"Warning: Could not get contexts for {src_file}: {e}")
                continue

            for lineno, contexts in contexts_by_lineno.items():
                if not contexts:
                    continue

                # Identify contributing test files
                contributors = set()
                for ctx in contexts:
                    # Context format: "tests/test_core.py::test_agent_initialization|run"
                    # We want the file part.
                    if "::" in ctx:
                        test_file = ctx.split("::")[0]
                        # Clean up path (sometimes relative, sometimes absolute)
                        test_file_path = Path(test_file).resolve()
                        contributors.add(str(test_file_path))
                    else:
                        # Sometimes context is just empty or not file-based?
                        pass

                if len(contributors) == 1:
                    sole_contributor = list(contributors)[0]
                    if sole_contributor in unique_counts:
                        unique_counts[sole_contributor] += 1

        # Update health map
        for tf in self.test_files:
            abs_path = rel_to_abs[tf]
            count = unique_counts.get(abs_path, 0)

            health = self.health_map.get(tf, TestFileHealth(file_path=tf))
            health.unique_coverage_lines = count

            # Check if critical
            if tf in self.critical_paths:
                health.is_critical_path = True
                # Critical paths have effectively infinite unique coverage to prevent deletion
                health.unique_coverage_lines = 9999

            self.health_map[tf] = health
            print(f"File: {tf}, Unique Lines: {health.unique_coverage_lines}")

    def calculate_churn(self, file_path: str) -> int:
        try:
            cmd = ["git", "log", "--since=30 days ago", "--oneline", "--", file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            lines = result.stdout.strip().splitlines()
            return len([l for l in lines if l])
        except subprocess.CalledProcessError:
            return 0

    def analyze_ast(self, file_path: str, content: str, health: TestFileHealth):
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return

        # Mock Density
        lines = content.splitlines()
        total_lines = len(lines)
        mock_lines = 0
        for line in lines:
            stripped = line.strip()
            # Heuristic for Python mocks
            if "mock" in stripped.lower() or "patch" in stripped.lower() or "magicmock" in stripped.lower():
                 mock_lines += 1

        health.loc = total_lines
        health.mock_density = mock_lines / total_lines if total_lines > 0 else 0

        # Tautology Check (AST)
        class TautologyVisitor(ast.NodeVisitor):
            def __init__(self):
                self.found = False

            def visit_Assert(self, node):
                # check if node.test is a constant True or 1
                if isinstance(node.test, ast.Constant):
                    if node.test.value is True or node.test.value == 1:
                        self.found = True
                elif isinstance(node.test, ast.Compare):
                    # Check for literal equality e.g. 1 == 1
                    if isinstance(node.test.left, ast.Constant) and \
                       len(node.test.comparators) == 1 and \
                       isinstance(node.test.comparators[0], ast.Constant):
                        if node.test.left.value == node.test.comparators[0].value:
                             self.found = True

        visitor = TautologyVisitor()
        visitor.visit(tree)
        if visitor.found:
            health.has_tautology = True

    def scan_files(self):
        print("Phase 2: The Rot Scan...")
        for tf in self.test_files:
            # Skip if file doesn't exist
            if not os.path.exists(tf):
                continue

            health = self.health_map.get(tf, TestFileHealth(file_path=tf))

            try:
                with open(tf, "r") as f:
                    content = f.read()
            except Exception:
                continue

            # Token Cost (Approximate: chars / 4)
            health.token_cost = len(content) // 4

            # Churn
            health.churn_rate = self.calculate_churn(tf)

            # AST
            self.analyze_ast(tf, content, health)

            self.health_map[tf] = health

    def evaluate_verdict(self) -> List[RotVerdict]:
        print("Phase 3: The Verdict...")
        verdicts = []
        for tf, health in self.health_map.items():
            if health.is_critical_path:
                continue

            tags = []
            suggested_action = "NONE"
            score = 0

            # Check for Rot Patterns
            if health.mock_density > ENTROPY_CONFIG["maxMockDensity"]:
                tags.append("BRITTLE_MOCKING")
                score += 40

            if health.token_cost > ENTROPY_CONFIG["maxTokenContext"]:
                tags.append("CONTEXT_BLOAT")
                score += 30

            if health.has_tautology:
                tags.append("TAUTOLOGY")
                score += 50

            if health.unique_coverage_lines == 0:
                tags.append("REDUNDANT_COVERAGE")
                score += 20

            if health.churn_rate > 5: # Threshold from prompt
                tags.append("HIGH_CHURN")
                score += 10

            # Strategies

            # Strategy B: Liability Prune
            if (("BRITTLE_MOCKING" in tags or "TAUTOLOGY" in tags) and
                health.unique_coverage_lines == 0):
                suggested_action = "DELETE"

            # Strategy C: Quarantine
            elif ("HIGH_CHURN" in tags and score >= 50): # High rot score
                suggested_action = "QUARANTINE"

            # Strategy A: Bloat Reducer
            elif "CONTEXT_BLOAT" in tags:
                # Only if not already deleting/quarantining
                if suggested_action == "NONE":
                    suggested_action = "REFACTOR" # Externalize snapshots

            if suggested_action != "NONE":
                verdicts.append(RotVerdict(
                    file=tf,
                    score=score,
                    tags=tags,
                    suggested_action=suggested_action
                ))

        return verdicts

    def perform_actions(self, verdicts: List[RotVerdict]):
        print("Phase 5: Action Execution...")

        # Safety Net: Vibe Check
        actions_to_take = [v for v in verdicts if v.suggested_action in ("DELETE", "QUARANTINE")]
        actions_count = len(actions_to_take)
        if actions_count > 20:
            print(f"SAFETY NET TRIGGERED: {actions_count} files flagged for removal/quarantine. Aborting to prevent mass deletion.")
            return

        for v in verdicts:
            if v.suggested_action == "DELETE":
                try:
                    os.remove(v.file)
                    print(f"DELETED: {v.file}")
                except OSError as e:
                    print(f"Error deleting {v.file}: {e}")

            elif v.suggested_action == "QUARANTINE":
                try:
                    # Move to tests/quarantine/ + original path structure
                    # e.g. tests/core/test_foo.py -> tests/quarantine/tests/core/test_foo.py
                    # This avoids filename collisions.
                    rel_path = os.path.relpath(v.file, self.project_root)
                    target_path = self.project_root / "tests" / "quarantine" / rel_path

                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(v.file, target_path)
                    print(f"QUARANTINED: {v.file} -> {target_path}")
                except OSError as e:
                    print(f"Error quarantining {v.file}: {e}")

            elif v.suggested_action == "REFACTOR":
                print(f"REFACTOR NEEDED: {v.file} (Action not automated yet)")

    def generate_report(self, verdicts: List[RotVerdict]):
        print("Phase 4: The Cleanse (Generating Report)...")
        if not verdicts:
            print("No rot detected.")
            with open("entropy_report.md", "w") as f:
                f.write("# Entropy Report\n\nNo issues found.")
            return

        report_lines = [
            "# [Entropy] Maintenance - Liability Reduction",
            "",
            "The following files have been flagged by the Entropy protocol.",
            "",
            "| File | Rot Type | Unique Coverage | Action Taken | Rationale |",
            "|---|---|---|---|---|"
        ]

        for v in verdicts:
            health = self.health_map[v.file]
            rot_type = ", ".join(v.tags)
            # Rationale construction
            rationale = []
            if "BRITTLE_MOCKING" in v.tags:
                rationale.append(f"{int(health.mock_density*100)}% Mocks")
            if "CONTEXT_BLOAT" in v.tags:
                rationale.append(f"{health.token_cost} tokens")
            if "TAUTOLOGY" in v.tags:
                rationale.append("Tautology detected")
            if "HIGH_CHURN" in v.tags:
                rationale.append(f"{health.churn_rate} commits/30d")

            rationale_str = ", ".join(rationale)

            line = f"| `{v.file}` | {rot_type} | {health.unique_coverage_lines} lines | **{v.suggested_action}** | {rationale_str} |"
            report_lines.append(line)

        content = "\n".join(report_lines)
        with open("entropy_report.md", "w") as f:
            f.write(content)

        print("Report generated: entropy_report.md")

if __name__ == "__main__":
    scanner = EntropyScanner()
    scanner.run_coverage()
    scanner.calculate_unique_coverage()
    scanner.scan_files()
    verdicts = scanner.evaluate_verdict()
    scanner.generate_report(verdicts)
    scanner.perform_actions(verdicts)
    print("Done Phase 5.")
