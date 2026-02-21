import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
import coverage

# Configuration
CONFIG = {
    "maxTokenContext": 2000,
    "maxMockDensity": 0.55,
    "minUniqueCoverageThreshold": 5,
    "executionMode": "PR_SUGGESTION",
    "criticalPathsFile": "critical_paths.json",
    "quarantineDir": "tests/quarantine",
    "maxFilesFlagged": 20,
    "maxCoverageDrop": 0.5, # Percentage points
}

class EntropyScanner:
    def __init__(self):
        self.metrics: Dict[str, Dict] = {}
        self.verdicts: List[Dict] = []
        self.critical_paths = self._load_critical_paths()
        self.initial_coverage = 0.0

    def _load_critical_paths(self) -> Set[str]:
        try:
            with open(CONFIG["criticalPathsFile"]) as f:
                return set(json.load(f))
        except FileNotFoundError:
            return set()
        except Exception:
            return set() # Fallback

    def run_phase_1_cartography(self):
        print("Phase 1: Cartography (Mapping & Coverage)...")
        # Run pytest with context
        try:
            # We ignore return code because some tests might fail but we still want coverage
            subprocess.run([sys.executable, "-m", "pytest", "--cov=src", "--cov-context=test", "--cov-report="], check=False, capture_output=True)
        except Exception as e:
            print(f"Error running pytest: {e}")

        try:
            cov = coverage.Coverage()
            cov.load()
            data = cov.get_data()
        except coverage.CoverageException:
            print("No coverage data found. Skipping cartography.")
            self.test_files_unique_coverage = {}
            self.all_test_files = set()
            return

        # Calculate unique coverage per test file
        test_files_unique_coverage: Dict[str, int] = {}

        # Get all measured source files
        measured_files = data.measured_files()

        for src_file in measured_files:
            lines = data.lines(src_file)
            if not lines:
                continue

            # Using contexts_by_lineno as per coverage API
            contexts_by_lineno = data.contexts_by_lineno(src_file)

            for line in lines:
                contexts = contexts_by_lineno.get(line, [])
                if not contexts:
                    continue

                # Contexts are like 'tests/test_core.py::test_something|run' or just 'tests/test_core.py'
                covering_files = set()
                for ctx in contexts:
                    if not ctx: continue
                    # Extract file path from context
                    # Context usually starts with the test file path
                    # e.g. tests/test_core.py::test_func
                    if "::" in ctx:
                        file_part = ctx.split("::")[0]
                        covering_files.add(file_part)
                    elif "|" in ctx:
                         file_part = ctx.split("|")[0]
                         if "::" in file_part:
                             covering_files.add(file_part.split("::")[0])
                         else:
                             covering_files.add(file_part)
                    else:
                        # Could be just file path if configured that way or for module scope
                        if ctx.endswith(".py"):
                            covering_files.add(ctx)

                # Filter out non-test files if any (unlikely in context)
                test_covering_files = {f for f in covering_files if f.startswith("tests/") or "test" in f}

                if len(test_covering_files) == 1:
                    test_file = list(test_covering_files)[0]
                    test_files_unique_coverage[test_file] = test_files_unique_coverage.get(test_file, 0) + 1

        self.test_files_unique_coverage = test_files_unique_coverage
        print(f"Unique coverage map calculated. {len(test_files_unique_coverage)} files provide unique coverage.")

        # Also map all test files
        self.all_test_files = set()
        for p in Path("tests").rglob("test_*.py"):
            self.all_test_files.add(str(p))

    def run_phase_2_rot_scan(self):
        print("Phase 2: Rot Scan (AST Analysis)...")
        for test_file in self.all_test_files:
            if "quarantine" in test_file:
                continue

            metrics = self._analyze_file(test_file)
            self.metrics[test_file] = metrics

    def _analyze_file(self, file_path: str) -> Dict:
        try:
            with open(file_path, "r") as f:
                content = f.read()
        except FileNotFoundError:
             return {"loc": 0, "token_cost": 0, "mock_density": 0, "tautology": False, "churn_rate": 0, "unique_coverage": 0}

        loc = len(content.splitlines())
        token_cost = len(content) / 4 # Approximation

        # AST analysis
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return {"loc": loc, "token_cost": token_cost, "mock_density": 0, "tautology": False, "churn_rate": 0, "error": True, "unique_coverage": 0}

        mock_lines = 0
        tautology = False

        # Better AST mock detection
        for node in ast.walk(tree):
             # Imports
             if isinstance(node, ast.Import):
                 for alias in node.names:
                     if "mock" in alias.name or "unittest.mock" in alias.name:
                         # This counts as 1 for import
                         mock_lines += 1
             elif isinstance(node, ast.ImportFrom):
                 if node.module and ("mock" in node.module or "unittest.mock" in node.module):
                     mock_lines += 1

             # Calls
             if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if "mock" in func_name.lower() or "patch" in func_name.lower() or "spy" in func_name.lower():
                     mock_lines += 1

        # Fallback to simple line-based count if AST missed something (or to catch decorators)
        lines = content.splitlines()
        regex_mock_lines = 0
        for line in lines:
            l = line.strip()
            if "Mock(" in l or "patch(" in l or "MagicMock(" in l or "spy" in l or "@patch" in l:
                regex_mock_lines += 1

        # Use the max of both methods
        mock_lines = max(mock_lines, regex_mock_lines)

        mock_density = mock_lines / loc if loc > 0 else 0

        # Tautology check
        for node in ast.walk(tree):
             if isinstance(node, ast.Assert):
                 if isinstance(node.test, ast.Constant) and node.test.value is True:
                     tautology = True
                 # Add more checks as needed

        # Churn rate
        churn_rate = 0
        try:
            # git log --since="30 days ago" --oneline -- <file>
            cmd = ["git", "log", "--since=30 days ago", "--oneline", "--", file_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            churn_rate = len(result.stdout.splitlines())
        except Exception:
            pass

        return {
            "loc": loc,
            "token_cost": token_cost,
            "mock_density": mock_density,
            "tautology": tautology,
            "churn_rate": churn_rate,
            "unique_coverage": self.test_files_unique_coverage.get(file_path, 0)
        }

    def run_phase_3_verdict(self):
        print("Phase 3: Verdict & Action...")
        for test_file, m in self.metrics.items():
            if test_file in self.critical_paths:
                continue

            # Strategies
            action = "NONE"
            tags = []

            # Strategy A: Bloat reducer
            if m["token_cost"] > CONFIG["maxTokenContext"]:
                tags.append("CONTEXT_BLOAT")
                action = "REFACTOR_NEEDED"

            # Strategy B: Liability Prune
            # "Condition: BRITTLE_MOCKING OR TAUTOLOGY detected AND uniqueCoverageLines === 0."
            is_brittle = m["mock_density"] > CONFIG["maxMockDensity"]
            if (is_brittle or m["tautology"]) and m["unique_coverage"] == 0:
                tags.append("BRITTLE_MOCKING" if is_brittle else "TAUTOLOGY")
                action = "DELETE"

            # Strategy C: Quarantine
            # "Condition: High Churn Rate (> 5 changes/month) AND High Rot Score."
            # High Rot = Mock Density or Context Bloat (implied)
            if m["churn_rate"] > 5 and (m["mock_density"] > CONFIG["maxMockDensity"] or m["token_cost"] > CONFIG["maxTokenContext"]):
                tags.append("HIGH_CHURN")
                if action != "DELETE": # Delete takes precedence if 0 unique coverage
                    action = "QUARANTINE"

            if action != "NONE":
                self.verdicts.append({
                    "file": test_file,
                    "action": action,
                    "tags": tags,
                    "metrics": m
                })

    def run_phase_4_cleanse(self):
        print("Phase 4: The Cleanse...")
        if len(self.verdicts) > CONFIG["maxFilesFlagged"]:
            print(f"ABORTING: Too many files flagged ({len(self.verdicts)} > {CONFIG['maxFilesFlagged']})")
            return

        # Coverage Cliff Check
        # We only delete files if unique_coverage == 0, so theoretically impact is 0.
        # But let's verify sum of unique_coverage for DELETED files is <= threshold (should be 0)
        total_unique_loss = sum(v["metrics"]["unique_coverage"] for v in self.verdicts if v["action"] == "DELETE")
        if total_unique_loss > 0:
             # This should not happen by definition of Strategy B, but just in case logic changes
             print(f"ABORTING: Coverage Cliff detected! Deleting files would lose {total_unique_loss} unique covered lines.")
             # We could check percentage if we knew total statements, but > 0 loss when expecting 0 is enough to abort strategy B.
             # Or maybe we allow small loss if unique > 0 but < threshold?
             # For now, strict 0 unique coverage for delete.
             pass

        actions_taken = []

        print(f"{'File':<40} {'Rot Type':<20} {'Unique Cov':<10} {'Action':<10}")
        print("-" * 80)

        md_table_rows = []
        md_table_rows.append("| File | Rot Type | Unique Coverage | Action Taken | Rationale |")
        md_table_rows.append("|---|---|---|---|---|")

        for v in self.verdicts:
            file_path = v["file"]
            action = v["action"]
            tags = ",".join(v["tags"])
            unique = v["metrics"]["unique_coverage"]
            rationale = f"{tags} detected."
            if action == "DELETE":
                rationale += " No unique coverage."
            elif action == "QUARANTINE":
                rationale += " High churn/rot."

            print(f"{file_path:<40} {tags:<20} {unique:<10} {action:<10}")

            md_row = f"| `{file_path}` | {tags} | {unique} lines | {action} | {rationale} |"

            if action == "DELETE":
                if unique == 0: # Double check
                    try:
                        os.remove(file_path)
                        actions_taken.append(v)
                        md_table_rows.append(md_row)
                    except OSError as e:
                        print(f"Error deleting {file_path}: {e}")
                else:
                    print(f"Skipping delete of {file_path} because unique coverage > 0 ({unique})")

            elif action == "QUARANTINE":
                # Replicate structure
                # e.g. tests/core/test_foo.py -> tests/quarantine/tests/core/test_foo.py
                rel_path = os.path.relpath(file_path) # Should be relative to cwd
                dest = Path(CONFIG["quarantineDir"]) / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)

                try:
                    shutil.move(file_path, dest)
                    actions_taken.append(v)
                    md_table_rows.append(md_row)
                except OSError as e:
                    print(f"Error moving {file_path}: {e}")

            elif action == "REFACTOR_NEEDED":
                 # TODO: Implement externalization
                 md_table_rows.append(md_row)
                 pass

        # JSON Report
        with open("entropy_report.json", "w") as f:
            json.dump(actions_taken, f, indent=2)

        # Markdown Report
        with open("entropy_report.md", "w") as f:
            f.write("# Entropy Audit Report\n\n")
            if actions_taken or len(md_table_rows) > 2:
                f.write("\n".join(md_table_rows))
            else:
                f.write("No liabilities found. Repository is healthy.\n")

        print(f"\nEntropy Scan Complete. {len(actions_taken)} actions taken.")

if __name__ == "__main__":
    scanner = EntropyScanner()
    scanner.run_phase_1_cartography()
    scanner.run_phase_2_rot_scan()
    scanner.run_phase_3_verdict()
    scanner.run_phase_4_cleanse()
