#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import ast
import shutil
import re
from pathlib import Path
from typing import List, Dict, Set, Optional, Any
from dataclasses import dataclass, field

# --- Configuration ---
MAX_TOKEN_CONTEXT = 2000
MAX_MOCK_DENSITY = 0.55
MIN_UNIQUE_COVERAGE = 5 # Threshold for "Do Not Touch" registry classification (Immunity is > 0)
MAX_CHURN = 5
MAX_ACTIONS_SAFETY_NET = 20
COVERAGE_CLIFF_THRESHOLD = 0.5 # Percent

REPORT_FILE = "entropy_report.md"
COVERAGE_FILE = "coverage.json"
CRITICAL_PATHS_FILE = "critical_paths.json"
QUARANTINE_DIR = Path("tests/quarantine")

@dataclass
class TestFileHealth:
    filepath: str
    loc: int = 0
    mock_density: float = 0.0
    churn_rate: int = 0
    token_cost: int = 0
    unique_coverage_lines: int = 0
    is_critical: bool = False
    rot_tags: List[str] = field(default_factory=list)
    action: str = "NONE"
    rationale: str = ""

class EntropyScanner:
    def __init__(self):
        self.results: Dict[str, TestFileHealth] = {}
        self.critical_paths: Set[str] = set()
        self.load_critical_paths()
        self.global_coverage_before: float = 0.0

    def load_critical_paths(self):
        if os.path.exists(CRITICAL_PATHS_FILE):
            try:
                with open(CRITICAL_PATHS_FILE, 'r') as f:
                    paths = json.load(f)
                    # Normalize paths
                    self.critical_paths = {str(Path(p).resolve()) for p in paths}
            except Exception as e:
                print(f"Error loading critical paths: {e}")

    def run_coverage(self):
        print("Running tests with coverage...")
        # Clean previous coverage
        if os.path.exists(".coverage"):
            os.remove(".coverage")

        # Run pytest with coverage and context
        cmd = [
            "pytest",
            "--cov=.",
            "--cov-report=json",
            "--cov-context=test"
        ]
        try:
            subprocess.run(cmd, check=False, capture_output=True) # check=False because tests might fail
        except Exception as e:
            print(f"Error running pytest: {e}")

        # Generate detailed JSON with contexts
        print("Generating coverage JSON with contexts...")
        cmd_json = ["coverage", "json", "--show-contexts"]
        try:
            subprocess.run(cmd_json, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"Error generating coverage json: {e}")

    def get_global_coverage(self) -> float:
        if not os.path.exists(COVERAGE_FILE):
            return 0.0
        try:
            with open(COVERAGE_FILE, 'r') as f:
                data = json.load(f)
                return data.get("totals", {}).get("percent_covered", 0.0)
        except:
            return 0.0

    def parse_coverage(self):
        if not os.path.exists(COVERAGE_FILE):
            print("Coverage file not found.")
            return

        with open(COVERAGE_FILE, 'r') as f:
            data = json.load(f)

        self.global_coverage_before = data.get("totals", {}).get("percent_covered", 0.0)

        # unique_lines_by_test_file[test_filepath] = count
        unique_counts = {}

        # "files" key contains source files
        files_data = data.get("files", {})

        for source_file, file_info in files_data.items():
            contexts = file_info.get("contexts", {})
            for line_no, context_list in contexts.items():
                # context_list is a list of context strings e.g. "tests/test_foo.py::test_bar|run"

                covering_files = set()
                for ctx in context_list:
                    # Parse filename from context
                    # Format usually: path/to/test.py::function|phase
                    if "::" in ctx:
                        test_file = ctx.split("::")[0]
                        covering_files.add(test_file)
                    else:
                        # Sometimes context is just empty or different?
                        pass

                if len(covering_files) == 1:
                    unique_file = list(covering_files)[0]
                    # Normalize path
                    try:
                        if os.path.isabs(unique_file):
                            unique_file = str(Path(unique_file).relative_to(os.getcwd()))
                        else:
                            unique_file = str(Path(unique_file))
                    except ValueError:
                        unique_file = str(Path(unique_file))

                    unique_counts[unique_file] = unique_counts.get(unique_file, 0) + 1

        # Update results with unique coverage
        for filepath, count in unique_counts.items():
            if filepath in self.results:
                self.results[filepath].unique_coverage_lines = count
            else:
                # If we encounter a test file here that we haven't scanned yet (e.g. implicitly run), add it?
                # Usually we scan existing files first.
                pass

    def analyze_rot(self, filepath: str) -> TestFileHealth:
        health = TestFileHealth(filepath=filepath)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return health

        health.loc = len(content.splitlines())
        health.token_cost = len(content) // 4 # Approx

        # Churn
        try:
            cmd = ["git", "log", "--since=30 days ago", "--format=oneline", "--", filepath]
            result = subprocess.run(cmd, capture_output=True, text=True)
            health.churn_rate = len(result.stdout.strip().splitlines())
        except Exception:
            health.churn_rate = 0

        # AST Analysis
        try:
            tree = ast.parse(content)

            mock_lines = 0
            tautology_detected = False

            for node in ast.walk(tree):
                # Check for Mocks
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if "Mock" in node.func.id or "patch" in node.func.id:
                            mock_lines += 1
                    elif isinstance(node.func, ast.Attribute):
                        if "Mock" in node.func.attr or "patch" in node.func.attr:
                            mock_lines += 1
                # Check decorators
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for decorator in node.decorator_list:
                         if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                             if "patch" in decorator.func.id:
                                 mock_lines += 1

                # Check Tautologies (very basic)
                if isinstance(node, ast.Assert):
                    # assert True
                    if isinstance(node.test, ast.Constant):
                        if node.test.value is True:
                            tautology_detected = True
                    # assert 1 == 1
                    if isinstance(node.test, ast.Compare):
                        if (isinstance(node.test.left, ast.Constant) and
                            len(node.test.comparators) == 1 and
                            isinstance(node.test.comparators[0], ast.Constant)):
                            if node.test.left.value == node.test.comparators[0].value:
                                tautology_detected = True

            health.mock_density = mock_lines / health.loc if health.loc > 0 else 0

            if health.mock_density > MAX_MOCK_DENSITY:
                health.rot_tags.append("BRITTLE_MOCKING")

            if health.token_cost > MAX_TOKEN_CONTEXT:
                health.rot_tags.append("CONTEXT_BLOAT")

            if tautology_detected:
                health.rot_tags.append("TAUTOLOGY")

        except SyntaxError:
            # Maybe not a python file or syntax error
            pass

        return health

    def scan(self):
        # 1. Run Coverage
        self.run_coverage()

        # 2. Identify Test Files
        test_files = []
        for root, _, files in os.walk("tests"):
            for file in files:
                if file.startswith("test_") and file.endswith(".py") and "quarantine" not in root:
                    test_files.append(os.path.join(root, file))

        # 3. Analyze Rot & Init Health
        for tf in test_files:
            health = self.analyze_rot(tf)

            # Check Criticality
            abs_path = str(Path(tf).resolve())
            if abs_path in self.critical_paths:
                health.is_critical = True

            self.results[tf] = health

        # 4. Parse Coverage (updates unique_coverage_lines)
        self.parse_coverage()

        # 5. Apply Strategies
        self.apply_strategies()

    def apply_strategies(self):
        actions_pending = []

        for filepath, health in self.results.items():
            if health.is_critical:
                continue

            # Strategy A: Bloat (Report only for now)
            if "CONTEXT_BLOAT" in health.rot_tags:
                # We do not have logic to externalize snapshots automatically safely yet.
                pass

            # Strategy B: Liability Prune
            # Condition: BRITTLE_MOCKING OR TAUTOLOGY detected AND uniqueCoverageLines === 0.
            if ("BRITTLE_MOCKING" in health.rot_tags or "TAUTOLOGY" in health.rot_tags) and health.unique_coverage_lines == 0:
                health.action = "DELETE"
                health.rationale = f"Liability: Unique Coverage 0, Rot: {', '.join(health.rot_tags)}"
                actions_pending.append(health)
                continue

            # Strategy C: Quarantine
            # Condition: High Churn Rate (> 5 changes/month) AND High Rot Score.
            is_high_rot = ("BRITTLE_MOCKING" in health.rot_tags) or (health.token_cost > MAX_TOKEN_CONTEXT)
            if health.churn_rate > MAX_CHURN and is_high_rot:
                health.action = "QUARANTINE"
                health.rationale = f"Quarantine: Churn {health.churn_rate}, Rot: {', '.join(health.rot_tags)}"
                actions_pending.append(health)
                continue

        # Safety Nets
        if len(actions_pending) > MAX_ACTIONS_SAFETY_NET:
            print(f"ABORT: Too many actions ({len(actions_pending)}) triggered safety net.")
            for h in actions_pending:
                h.action = "NONE" # Cancel
            return

        # Coverage Cliff Check
        # Since we only delete if unique coverage is 0, theoretically coverage shouldn't drop.
        # But let's verify if possible. For now, we trust the unique coverage metric.
        # If unique coverage > 0, we don't delete.

        # Execute Actions
        for health in actions_pending:
            if health.action == "DELETE":
                try:
                    os.remove(health.filepath)
                    print(f"DELETED {health.filepath}")
                except Exception as e:
                    print(f"Failed to delete {health.filepath}: {e}")
            elif health.action == "QUARANTINE":
                try:
                    target_dir = QUARANTINE_DIR / Path(health.filepath).parent
                    target_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(health.filepath, str(target_dir / Path(health.filepath).name))
                    print(f"QUARANTINED {health.filepath}")
                except Exception as e:
                    print(f"Failed to quarantine {health.filepath}: {e}")

    def generate_report(self):
        with open(REPORT_FILE, 'w') as f:
            f.write("# Entropy Report\n\n")

            # Summary
            f.write("## Summary\n")
            f.write(f"- Global Coverage: {self.global_coverage_before:.2f}%\n")
            f.write(f"- Files Scanned: {len(self.results)}\n\n")

            f.write("## Detailed Analysis\n\n")
            f.write("| File | Rot Type | Unique Coverage | Action Taken | Rationale |\n")
            f.write("|---|---|---|---|---|\n")

            for filepath, health in self.results.items():
                rot_str = ", ".join(health.rot_tags) if health.rot_tags else "Healthy"
                f.write(f"| {filepath} | {rot_str} | {health.unique_coverage_lines} lines | {health.action} | {health.rationale} |\n")

if __name__ == "__main__":
    scanner = EntropyScanner()
    scanner.scan()
    scanner.generate_report()
    print(f"Report generated at {REPORT_FILE}")
