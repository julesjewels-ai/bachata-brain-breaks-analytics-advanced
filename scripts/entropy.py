
import os
import sys
import json
import ast
import shutil
import coverage
import git
import re
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple

# Configuration
CONFIG = {
    "maxTokenContext": 2000,
    "maxMockDensity": 0.55,
    "minUniqueCoverageThreshold": 5,
    "churnThreshold": 5,
    "executionMode": "PR_SUGGESTION",
    "criticalPathsFile": "critical_paths.json",
    "snapshotDir": "tests/snapshots",
    "quarantineDir": "tests/quarantine",
}

class EntropyScanner:
    def __init__(self):
        self.repo = git.Repo(os.getcwd())
        self.coverage_data = None
        self.test_files = []
        self.verdicts = []
        self.critical_paths = self._load_critical_paths()
        self.unique_coverage = {}  # test_file -> count

    def _load_critical_paths(self) -> Set[str]:
        if os.path.exists(CONFIG["criticalPathsFile"]):
            with open(CONFIG["criticalPathsFile"], 'r') as f:
                return set(json.load(f))
        return set()

    def run_coverage(self):
        print("Running coverage...")
        # Clean previous coverage
        if os.path.exists(".coverage"):
            os.remove(".coverage")

        # Run pytest with context
        exit_code = os.system("pytest --cov=src --cov-context=test --cov-report=json")
        if exit_code != 0 and exit_code != 1: # 1 is tests failed, which is okay for analysis potentially, but 0 is better
            print(f"Warning: Pytest exited with code {exit_code}")

        self.coverage_data = coverage.CoverageData()
        self.coverage_data.read()
        print("Coverage data loaded.")

    def analyze_unique_coverage(self):
        print("Analyzing unique coverage...")
        # Map source line -> set of test files that cover it
        line_coverage: Dict[str, Dict[int, Set[str]]] = {}

        measured_files = self.coverage_data.measured_files()

        for src_file in measured_files:
            contexts_by_lineno = self.coverage_data.contexts_by_lineno(src_file)
            for lineno, contexts in contexts_by_lineno.items():
                test_files_covering = set()
                for context in contexts:
                    if '::' in context:
                        test_file = context.split('::')[0]
                        test_files_covering.add(test_file)
                    elif context == '': # Empty context (setup/teardown sometimes)
                        pass
                    else:
                        # Sometimes context is just file path if configured differently
                        test_files_covering.add(context)

                if test_files_covering:
                    if src_file not in line_coverage:
                        line_coverage[src_file] = {}
                    line_coverage[src_file][lineno] = test_files_covering

        # Calculate unique coverage per test file
        # Initialize counts
        for root, dirs, files in os.walk("tests"):
            if "__pycache__" in dirs:
                dirs.remove("__pycache__")

            for file in files:
                if (file.startswith("test_") or file.endswith("_test.py")) and file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    self.unique_coverage[filepath] = 0
                    self.test_files.append(filepath)

        # Iterate over all covered lines
        for src_file, lines in line_coverage.items():
            for lineno, covering_files in lines.items():
                if len(covering_files) == 1:
                    test_file = list(covering_files)[0]
                    # Normalize path
                    test_file = os.path.relpath(os.path.abspath(test_file), os.getcwd())
                    if test_file in self.unique_coverage:
                        self.unique_coverage[test_file] += 1
                    else:
                        # Maybe test file is not in self.unique_coverage (e.g. not in tests/)
                        pass

    def get_git_churn(self, filepath):
        try:
            commits = list(self.repo.iter_commits(paths=filepath, since='30.days.ago'))
            return len(commits)
        except Exception as e:
            print(f"Error getting churn for {filepath}: {e}")
            return 0

    def check_tautology(self, filepath):
        with open(filepath, 'r') as f:
            try:
                tree = ast.parse(f.read())
            except:
                return False

        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                # assert True
                if isinstance(node.test, ast.Constant) and node.test.value is True:
                    return True
                # assert x == x
                if isinstance(node.test, ast.Compare):
                    if len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq):
                        left = node.test.left
                        right = node.test.comparators[0]
                        if isinstance(left, ast.Name) and isinstance(right, ast.Name):
                            if left.id == right.id:
                                return True
        return False

    def scan_files(self):
        print("Scanning files for rot...")
        for filepath in self.test_files:
            if not os.path.exists(filepath): continue

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(filepath, 'r', encoding='latin-1') as f:
                        content = f.read()
                except Exception:
                    print(f"Skipping {filepath} due to encoding issues.")
                    continue

            lines = content.splitlines()

            loc = len(lines)
            if loc == 0: continue

            # Mock Density
            mock_lines = 0
            mock_patterns = [r"Mock\(", r"MagicMock\(", r"patch\(", r"spy\(", r"\.return_value", r"\.side_effect"]
            for line in lines:
                if any(re.search(p, line) for p in mock_patterns):
                    mock_lines += 1

            mock_density = mock_lines / loc

            # Token Cost
            token_cost = len(content) / 4

            # Churn
            churn = self.get_git_churn(filepath)

            # Tautology
            is_tautology = self.check_tautology(filepath)

            # Unique Coverage
            unique_lines = self.unique_coverage.get(filepath, 0)

            # Verdict
            tags = []
            if mock_density > CONFIG["maxMockDensity"]:
                tags.append("BRITTLE_MOCKING")
            if token_cost > CONFIG["maxTokenContext"]:
                tags.append("CONTEXT_BLOAT")
            if is_tautology:
                tags.append("TAUTOLOGY")
            if churn > CONFIG["churnThreshold"]:
                tags.append("HIGH_CHURN")

            action = "NONE"
            rationale = ""

            is_immune = unique_lines > 0 or filepath in self.critical_paths

            if "CONTEXT_BLOAT" in tags:
                action = "REFACTOR" # Externalize Snapshots
                rationale = f"Token cost {token_cost} > {CONFIG['maxTokenContext']}"
            elif ("BRITTLE_MOCKING" in tags or "TAUTOLOGY" in tags) and unique_lines == 0:
                if not is_immune:
                    action = "DELETE"
                    rationale = f"Brittle/Tautological and 0 unique coverage"
                else:
                    rationale = "Immune due to unique coverage"
            elif "HIGH_CHURN" in tags and len(tags) > 1: # High Churn + other rot
                action = "QUARANTINE"
                rationale = f"High churn ({churn}) and rot {tags}"

            self.verdicts.append({
                "file": filepath,
                "tags": tags,
                "unique_lines": unique_lines,
                "action": action,
                "rationale": rationale,
                "score": len(tags) * 25 # Dummy score
            })

    def execute_actions(self):
        print("Executing actions...")
        # Sort verdicts to prioritize deletions?

        # Check constraints
        flagged_count = sum(1 for v in self.verdicts if v["action"] != "NONE")
        if flagged_count > 20:
            print(f"ABORT: Vibe Check failed. {flagged_count} files flagged.")
            return

        actions_taken = []

        for v in self.verdicts:
            filepath = v["file"]
            action = v["action"]

            if action == "DELETE":
                print(f"Deleting {filepath}...")
                os.remove(filepath)
                actions_taken.append(v)

            elif action == "QUARANTINE":
                print(f"Quarantining {filepath}...")
                if not os.path.exists(CONFIG["quarantineDir"]):
                    os.makedirs(CONFIG["quarantineDir"])
                filename = os.path.basename(filepath)
                shutil.move(filepath, os.path.join(CONFIG["quarantineDir"], filename))
                actions_taken.append(v)

            elif action == "REFACTOR":
                print(f"Refactoring {filepath}...")
                self.refactor_bloat(filepath)
                actions_taken.append(v)

        self.generate_report(actions_taken)

    def refactor_bloat(self, filepath):
        # Identify large dicts/lists and extract to JSON
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(filepath, 'r', encoding='latin-1') as f:
                content = f.read()

        try:
            tree = ast.parse(content)
        except:
            print(f"Failed to parse {filepath} for refactoring")
            return

        replacements = [] # (start_idx, end_idx, new_text)

        class BloatFinder(ast.NodeVisitor):
            def visit_Dict(self, node):
                self._check_node(node)
                self.generic_visit(node)

            def visit_List(self, node):
                self._check_node(node)
                self.generic_visit(node)

            def _check_node(self, node):
                # Heuristic: check source length
                # AST nodes don't have source text directly, we need to extract from content
                # node.lineno, node.col_offset, node.end_lineno, node.end_col_offset
                if not hasattr(node, 'end_lineno'): return

                start_line = node.lineno - 1
                end_line = node.end_lineno - 1
                start_col = node.col_offset
                end_col = node.end_col_offset

                # Extract text
                lines = content.splitlines()
                if start_line == end_line:
                    text = lines[start_line][start_col:end_col]
                else:
                    text = lines[start_line][start_col:]
                    for i in range(start_line + 1, end_line):
                        text += "\n" + lines[i]
                    text += "\n" + lines[end_line][:end_col]

                if len(text) > 500: # Threshold for extraction (chars)
                    # Extract
                    filename = os.path.basename(filepath).replace('.py', '')
                    snapshot_name = f"{filename}_snapshot_{node.lineno}.json"
                    snapshot_path = os.path.join(CONFIG["snapshotDir"], snapshot_name)

                    try:
                        # Evaluate to get python object
                        # This is risky if code has side effects, but it's a list/dict literal
                        obj = ast.literal_eval(text)

                        with open(snapshot_path, 'w') as snap_f:
                            json.dump(obj, snap_f, indent=2)

                        replacements.append((node, snapshot_path))
                    except Exception as e:
                        print(f"Failed to extract snapshot: {e}")

        finder = BloatFinder()
        finder.visit(tree)

        # Apply replacements in reverse order to preserve offsets?
        # Actually, simpler: just regex replace the text? No, use string slicing.
        # But if we have multiple, offsets change.
        # So reverse order of start position is best.

        replacements.sort(key=lambda x: (x[0].lineno, x[0].col_offset), reverse=True)

        new_content = content.splitlines() # Use list of lines for easier replacement? No, full string.
        # Re-read content to be safe or use what we have.

        # We need byte offsets or careful line/col manipulation.
        # Let's reconstruct the file string.

        lines = content.splitlines(keepends=True)
        # Replacing based on line/col is tricky with multiple replacements.
        # Just do one replacement per run? Or all.

        # For simplicity, if we find multiple, we do them all.
        # Since we sorted reverse, we can modify lines without affecting earlier lines?
        # But modifying a line might affect subsequent lines if we change line count.
        # Replacing a multi-line dict with one line `json.load` changes line counts.
        # So reverse sort is good.

        modified = False
        for node, snap_path in replacements:
            # We need to inject "import json" if not present.
            # Assuming we do it later.

            start_line = node.lineno - 1
            end_line = node.end_lineno - 1
            start_col = node.col_offset
            end_col = node.end_col_offset

            # Construct replacement text
            # We need to make sure the path is relative or absolute.
            # `json.load(open('tests/snapshots/...'))`
            rel_path = os.path.relpath(snap_path, os.getcwd())
            replacement_code = f"json.load(open('{rel_path}'))"

            # Replace in lines list
            if start_line == end_line:
                old_line = lines[start_line]
                lines[start_line] = old_line[:start_col] + replacement_code + old_line[end_col:]
            else:
                # Multi-line
                lines[start_line] = lines[start_line][:start_col] + replacement_code + "\n"
                # Remove intermediate lines
                for i in range(start_line + 1, end_line):
                    lines[i] = "" # Mark for removal
                # Handle end line
                lines[end_line] = lines[end_line][end_col:]

            modified = True

        if modified:
            final_content = "".join(lines)
            # Add import json if needed
            if "import json" not in final_content:
                final_content = "import json\n" + final_content

            with open(filepath, 'w') as f:
                f.write(final_content)

    def generate_report(self, actions):
        print("Generating report...")
        report = "# [Entropy] Maintenance - Liability Reduction\n\n"
        report += "| File | Rot Type | Unique Coverage | Action Taken | Rationale |\n"
        report += "|---|---|---|---|---|\n"

        for action in actions:
            file = os.path.basename(action["file"])
            rot = ", ".join(action["tags"])
            cov = f"{action['unique_lines']} lines"
            act = action["action"]
            rat = action["rationale"]
            report += f"| {file} | {rot} | {cov} | {act} | {rat} |\n"

        print(report)
        with open("entropy_report.md", "w") as f:
            f.write(report)

if __name__ == "__main__":
    scanner = EntropyScanner()
    try:
        scanner.run_coverage()
        scanner.analyze_unique_coverage()
        scanner.scan_files()
        scanner.execute_actions()
    finally:
        # Cleanup
        if os.path.exists(".coverage"):
            os.remove(".coverage")
        if os.path.exists("coverage.json"):
            os.remove("coverage.json")
        print("Cleanup complete.")
