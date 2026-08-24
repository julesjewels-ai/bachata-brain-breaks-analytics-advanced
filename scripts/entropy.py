import os
import json
import ast
import subprocess
import shutil
from collections import defaultdict
from pathlib import Path
import math
from typing import List, Dict, Set, Tuple

# Entropy Configuration
CONFIG = {
    'maxTokenContext': 2000,
    'maxMockDensity': 0.55,
    'minUniqueCoverageThreshold': 5,
    'executionMode': 'PR_SUGGESTION' # we assume standard mode for script
}

def run_cmd(cmd: str) -> str:
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {cmd}\n{e.stderr}")
        return ""

def get_churn_rate(filepath: str) -> int:
    """Commits in last 30 days"""
    out = run_cmd(f"git log --since='30 days ago' --oneline -- {filepath} | wc -l")
    try:
        return int(out.strip())
    except:
        return 0

def calculate_token_cost(filepath: str) -> int:
    """Rough estimation of token cost based on character count (1 token ~= 4 chars)"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        return len(content) // 4
    except Exception:
        return 0

class ASTAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.mock_lines = 0
        self.total_lines = 0
        self.tautologies_found = 0

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id in ('mock', 'spyOn', 'patch', 'MagicMock', 'Mock'):
                self.mock_lines += 1
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in ('mock', 'spyOn', 'patch', 'mock_calls', 'return_value', 'side_effect'):
                self.mock_lines += 1
        self.generic_visit(node)

    def visit_Assert(self, node):
        if isinstance(node.test, ast.Compare):
            if len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq):
                left = node.test.left
                right = node.test.comparators[0]
                if isinstance(left, ast.Constant) and isinstance(right, ast.Constant):
                    if left.value == right.value:
                        self.tautologies_found += 1
        self.generic_visit(node)

class SnapshotExternalizer(ast.NodeTransformer):
    def __init__(self, filepath, base_dir="tests/snapshots"):
        self.filepath = filepath
        self.base_dir = base_dir
        self.snapshot_count = 0
        self.has_changes = False
        os.makedirs(self.base_dir, exist_ok=True)

    def visit_Assign(self, node):
        self.generic_visit(node)
        if isinstance(node.value, (ast.Dict, ast.List)):
            try:
                # Approximate size checking using ast.unparse
                if len(ast.unparse(node.value)) > 500:
                    self.snapshot_count += 1
                    self.has_changes = True
                    snapshot_filename = f"{Path(self.filepath).stem}_snap_{self.snapshot_count}.json"
                    snapshot_path = os.path.join(self.base_dir, snapshot_filename)

                    # Evaluate the literal and save to json
                    val = ast.literal_eval(node.value)

                    # Convert tuples to lists for json dumping to avoid modifying data types silently
                    def convert_tuples(obj):
                        if isinstance(obj, tuple):
                            return list(convert_tuples(i) for i in obj)
                        if isinstance(obj, list):
                            return [convert_tuples(i) for i in obj]
                        if isinstance(obj, dict):
                            return {k: convert_tuples(v) for k, v in obj.items()}
                        return obj

                    val_converted = convert_tuples(val)

                    with open(snapshot_path, 'w') as f:
                        json.dump(val_converted, f, indent=2)

                    # Create the replacement AST node
                    new_value = ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id='json', ctx=ast.Load()),
                            attr='load',
                            ctx=ast.Load()
                        ),
                        args=[
                            ast.Call(
                                func=ast.Name(id='open', ctx=ast.Load()),
                                args=[
                                    ast.Constant(value=snapshot_path)
                                ],
                                keywords=[]
                            )
                        ],
                        keywords=[]
                    )

                    # If it was originally a tuple, wrap it in a tuple() call
                    if isinstance(node.value, ast.Tuple):
                        new_value = ast.Call(
                            func=ast.Name(id='tuple', ctx=ast.Load()),
                            args=[new_value],
                            keywords=[]
                        )

                    node.value = new_value
            except Exception as e:
                print(f"Failed to externalize snapshot: {e}")
        return node

def analyze_ast(filepath: str) -> Tuple[float, bool]:
    try:
        with open(filepath, 'r') as f:
            source = f.read()
            tree = ast.parse(source)
            total_lines = len(source.splitlines())

        analyzer = ASTAnalyzer()
        analyzer.total_lines = total_lines
        analyzer.visit(tree)

        mock_density = analyzer.mock_lines / total_lines if total_lines > 0 else 0
        has_tautology = analyzer.tautologies_found > 0

        return mock_density, has_tautology
    except Exception as e:
        print(f"AST Analysis failed for {filepath}: {e}")
        return 0.0, False

def externalize_snapshots(filepath: str):
    """Refactoring strategy using AST rewriting"""
    try:
        with open(filepath, 'r') as f:
            source = f.read()
            tree = ast.parse(source)

        transformer = SnapshotExternalizer(filepath)
        new_tree = transformer.visit(tree)

        if transformer.has_changes:
            # Add import json if it doesn't exist
            import_json_exists = False
            for node in new_tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == 'json':
                            import_json_exists = True

            if not import_json_exists:
                import_json_node = ast.Import(names=[ast.alias(name='json', asname=None)])
                new_tree.body.insert(0, import_json_node)

            ast.fix_missing_locations(new_tree)
            new_source = ast.unparse(new_tree)
            with open(filepath, 'w') as f:
                f.write(new_source)

            print(f"Externalized {transformer.snapshot_count} snapshots in {filepath}")
    except Exception as e:
        print(f"Externalize snapshots failed for {filepath}: {e}")

def get_baseline_coverage() -> float:
    run_cmd("pytest --cov=src --cov-report=json")
    try:
        with open("coverage.json", 'r') as f:
            data = json.load(f)
            return data.get('totals', {}).get('percent_covered', 0.0)
    except:
        return 0.0

def get_unique_coverage(test_files: List[str]) -> Dict[str, int]:
    """Iteratively runs pytest to determine unique coverage lines"""
    unique_cov = defaultdict(int)

    # First, get all coverage lines for the entire test suite
    run_cmd("pytest --cov=src --cov-report=json")
    try:
        with open("coverage.json", 'r') as f:
            full_data = json.load(f)

        full_coverage_lines = set()
        for filename, file_data in full_data.get('files', {}).items():
            for line in file_data.get('executed_lines', []):
                full_coverage_lines.add((filename, line))
    except Exception as e:
        print(f"Failed to get baseline coverage data: {e}")
        return {t: 0 for t in test_files}

    for t in test_files:
        # Run test suite WITHOUT test t
        other_tests = [test for test in test_files if test != t]

        # If no other tests, unique coverage is the full coverage
        if not other_tests:
            unique_cov[t] = len(full_coverage_lines)
            continue

        other_tests_str = " ".join(other_tests)
        run_cmd(f"pytest {other_tests_str} --cov=src --cov-report=json")
        try:
            with open("coverage.json", 'r') as f:
                other_data = json.load(f)

            other_coverage_lines = set()
            for filename, file_data in other_data.get('files', {}).items():
                for line in file_data.get('executed_lines', []):
                    other_coverage_lines.add((filename, line))

            # Unique coverage is what's in full but not in other
            unique_lines = full_coverage_lines - other_coverage_lines
            unique_cov[t] = len(unique_lines)
        except Exception as e:
            print(f"Failed to parse coverage for {t}: {e}")
            unique_cov[t] = 0

    return unique_cov

def find_imports(filepath: str) -> List[str]:
    imports = []
    try:
        with open(filepath, 'r') as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
    except:
        pass
    return imports

def main():
    print("Starting Entropy Protocol...")

    # Ensure critical paths exist
    critical_paths = []
    if os.path.exists("critical_paths.json"):
        with open("critical_paths.json", 'r') as f:
            critical_paths = json.load(f)

    # Find all test files
    test_files = [str(p) for p in Path("tests").rglob("test_*.py")]

    # Exclude immune/Gherkin/Markdown files
    test_files = [f for f in test_files if not f.endswith('.md') and not f.endswith('.feature')]

    baseline_cov = get_baseline_coverage()
    print(f"Baseline Coverage: {baseline_cov}%")

    unique_coverage = get_unique_coverage(test_files)

    actions_taken = []
    delete_quarantine_count = 0

    for filepath in test_files:
        # Check immunity
        if filepath in critical_paths:
            unique_cov = float('inf')
        else:
            unique_cov = unique_coverage.get(filepath, 0)

        mock_density, has_tautology = analyze_ast(filepath)
        token_cost = calculate_token_cost(filepath)
        churn_rate = get_churn_rate(filepath)

        # Map Files: use the import graph
        imports = find_imports(filepath)
        associated_files = [imp for imp in imports if 'src' in imp or 'core' in imp]

        rot_tags = []
        if mock_density > CONFIG['maxMockDensity']:
            rot_tags.append('BRITTLE_MOCKING')
        if token_cost > CONFIG['maxTokenContext']:
            rot_tags.append('CONTEXT_BLOAT')
        if has_tautology:
            rot_tags.append('TAUTOLOGY')

        rot_score = len(rot_tags) * 33 # Simplistic score 0-100

        # Apply Strategies
        action = 'NONE'
        rationale = ""

        # Strategy A: The Bloat Reducer
        if 'CONTEXT_BLOAT' in rot_tags:
            externalize_snapshots(filepath)
            action = 'REFACTORED'
            rationale = f"Externalized snapshots ({token_cost} tokens)"

        # Strategy B: The Liability Prune
        elif ('BRITTLE_MOCKING' in rot_tags or 'TAUTOLOGY' in rot_tags) and unique_cov == 0:
            action = 'DELETED'
            rationale = f"Liability: {' '.join(rot_tags)}, 0 unique coverage"

        # Strategy C: The Quarantine
        elif churn_rate > 5 and rot_score > 50:
            action = 'QUARANTINED'
            rationale = f"High churn ({churn_rate}) and high rot ({rot_score})"

        if action in ('DELETED', 'QUARANTINED'):
            delete_quarantine_count += 1

        if action != 'NONE':
            actions_taken.append({
                'file': filepath,
                'rot_type': ', '.join(rot_tags),
                'unique_coverage': unique_cov,
                'action': action,
                'rationale': rationale
            })

    # Check Vibe Guardrail
    if delete_quarantine_count > 20:
        print("VIBE CHECK FAILED: > 20 files flagged for deletion/quarantine. Aborting.")
        return

    # Apply actions safely
    os.makedirs("tests/quarantine", exist_ok=True)

    for action_item in actions_taken:
        filepath = action_item['file']
        action = action_item['action']

        if action == 'DELETED':
            if os.path.exists(filepath):
                os.remove(filepath)
        elif action == 'QUARANTINED':
            if os.path.exists(filepath):
                shutil.move(filepath, os.path.join("tests/quarantine", os.path.basename(filepath)))

    # Final Guardrail Check: The Coverage Cliff
    final_cov = get_baseline_coverage()
    if (baseline_cov - final_cov) > 0.5:
        print(f"COVERAGE CLIFF FAILED: Coverage dropped by > 0.5% ({baseline_cov}% -> {final_cov}%).")
        print("Reverting changes...")
        run_cmd("git restore .")
        run_cmd("git clean -fd")
    else:
        print("Entropy run successful. Generating report...")
        with open("entropy_report.md", "w") as f:
            f.write("| File | Rot Type | Unique Coverage | Action Taken | Rationale |\n")
            f.write("|---|---|---|---|---|\n")
            for item in actions_taken:
                f.write(f"| {item['file']} | {item['rot_type']} | {item['unique_coverage']} | {item['action']} | {item['rationale']} |\n")

if __name__ == "__main__":
    main()
