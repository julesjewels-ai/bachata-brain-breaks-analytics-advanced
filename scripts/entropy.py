import json
import os
import glob
import re
from pathlib import Path
from collections import defaultdict
import subprocess
import shutil
import ast

# Config
MAX_TOKEN_CONTEXT = 2000
MAX_MOCK_DENSITY = 0.55
MIN_UNIQUE_COVERAGE = 5
EXECUTION_MODE = 'PR_SUGGESTION'
MAX_COVERAGE_DROP = 0.5

# Paths
SRC_DIR = 'src'
TESTS_DIR = 'tests'
QUARANTINE_DIR = 'tests/quarantine'
CRITICAL_PATHS_FILE = 'critical_paths.json'

def get_baseline_coverage():
    subprocess.run(["python", "-m", "pytest", "--cov=src", "--cov-report=json"], stdout=subprocess.DEVNULL)
    with open("coverage.json", "r") as f:
        cov_data = json.load(f)
    return cov_data.get("totals", {}).get("percent_covered", 0.0)

def calculate_unique_coverage():
    print("Calculating unique coverage per file...")
    test_files = glob.glob(f"{TESTS_DIR}/**/test_*.py", recursive=True)

    all_test_coverages = {}
    for test_file in test_files:
        if "quarantine" in test_file:
            continue

        subprocess.run(["python", "-m", "pytest", test_file, "--cov=src", "--cov-report=json"], stdout=subprocess.DEVNULL)
        try:
            with open("coverage.json", "r") as f:
                cov_data = json.load(f)
        except Exception:
            continue

        covered_lines = defaultdict(set)
        for src_file, data in cov_data.get("files", {}).items():
             if "executed_lines" in data:
                 covered_lines[src_file] = set(data["executed_lines"])
        all_test_coverages[test_file] = covered_lines

    line_frequency = defaultdict(lambda: defaultdict(int))
    for test_file, cov in all_test_coverages.items():
        for src_file, lines in cov.items():
            for line in lines:
                line_frequency[src_file][line] += 1

    unique_counts = {}
    for test_file, cov in all_test_coverages.items():
        count = 0
        for src_file, lines in cov.items():
            for line in lines:
                if line_frequency[src_file][line] == 1:
                    count += 1
        unique_counts[test_file] = count

    return unique_counts

def is_tautology_node(node):
    if isinstance(node, ast.Assert):
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            return True
        if isinstance(node.test, ast.Compare):
            if len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq):
                left = node.test.left
                right = node.test.comparators[0]
                if isinstance(left, ast.Constant) and isinstance(right, ast.Constant):
                    if left.value == right.value:
                        return True
    return False


class DictExtractor(ast.NodeTransformer):
    def __init__(self, threshold=5):
        self.threshold = threshold
        self.extracted_dicts = []
        self.counter = 0

    def visit_Dict(self, node):
        self.generic_visit(node)
        if len(node.keys) > self.threshold:
            try:
                val = ast.literal_eval(node)
                self.extracted_dicts.append(val)
                new_node = ast.Call(
                    func=ast.Name(id='_load_snapshot', ctx=ast.Load()),
                    args=[ast.Constant(value=self.counter)],
                    keywords=[]
                )
                self.counter += 1
                return ast.copy_location(new_node, node)
            except ValueError:
                pass
        return node

    def visit_List(self, node):
        self.generic_visit(node)
        if len(node.elts) > self.threshold:
            try:
                val = ast.literal_eval(node)
                self.extracted_dicts.append(val)
                new_node = ast.Call(
                    func=ast.Name(id='_load_snapshot', ctx=ast.Load()),
                    args=[ast.Constant(value=self.counter)],
                    keywords=[]
                )
                self.counter += 1
                return ast.copy_location(new_node, node)
            except ValueError:
                pass
        return node

def apply_compact_snapshots(filepath):
    with open(filepath, 'r') as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    extractor = DictExtractor(threshold=5)
    new_tree = extractor.visit(tree)

    if not extractor.extracted_dicts:
        return False

    snapshot_dir = os.path.join(os.path.dirname(filepath), 'snapshots')
    os.makedirs(snapshot_dir, exist_ok=True)
    base_name = os.path.basename(filepath).replace('.py', '')

    for i, data in enumerate(extractor.extracted_dicts):
        snap_path = os.path.join(snapshot_dir, f"{base_name}_{i}.json")
        with open(snap_path, 'w') as f:
            json.dump(data, f, indent=2)

    # Safely inject the helper function into the AST
    helper_ast = ast.parse(f"""
import json
import os
def _load_snapshot(idx):
    snap_path = os.path.join(os.path.dirname(__file__), 'snapshots', '{base_name}_' + str(idx) + '.json')
    with open(snap_path, 'r') as f:
        return json.load(f)
""")

    # Insert helper imports and function after any __future__ imports
    insert_idx = 0
    if new_tree.body and isinstance(new_tree.body[0], ast.ImportFrom) and new_tree.body[0].module == '__future__':
        insert_idx = 1

    for node in reversed(helper_ast.body):
        new_tree.body.insert(insert_idx, node)

    ast.fix_missing_locations(new_tree)
    new_source = ast.unparse(new_tree)

    with open(filepath, 'w') as f:
        f.write(new_source)
    return True

def analyze_test_files():
    unique_counts = calculate_unique_coverage()

    critical_paths = []
    if os.path.exists(CRITICAL_PATHS_FILE):
        with open(CRITICAL_PATHS_FILE, "r") as f:
            critical_paths = json.load(f)

    results = []

    for test_file, unique_cov in unique_counts.items():
        if test_file in critical_paths:
            unique_cov = float('inf')

        # Preserve specs constraint
        if test_file.endswith('.md') or test_file.endswith('.feature'):
            continue

        with open(test_file, 'r') as f:
            lines = f.readlines()

        total_lines = len(lines)
        if total_lines == 0: continue

        # Token cost (approx)
        token_cost = sum(len(line.split()) for line in lines)

        # Mock density
        mock_lines = 0
        for line in lines:
            if re.search(r'mock\(|spyOn\(|\.mockReturnValue\(|Mock\(|patch\(|AsyncMock\(', line):
                mock_lines += 1
        mock_density = mock_lines / total_lines if total_lines > 0 else 0

        # Tautology via AST
        tautology = False
        try:
            tree = ast.parse("".join(lines))
            for node in ast.walk(tree):
                if is_tautology_node(node):
                    tautology = True
                    break
        except SyntaxError:
            pass

        # Churn rate (approx placeholder, use git log)
        git_log = subprocess.run(["git", "log", "--oneline", "--since=30.days", "--", test_file], capture_output=True, text=True)
        churn_rate = len(git_log.stdout.splitlines())

        tags = []
        if mock_density > MAX_MOCK_DENSITY:
            tags.append('BRITTLE_MOCKING')
        if token_cost > MAX_TOKEN_CONTEXT:
            tags.append('CONTEXT_BLOAT')
        if tautology:
            tags.append('TAUTOLOGY')

        score = (mock_density * 50) + (min(token_cost / MAX_TOKEN_CONTEXT, 1) * 20) + (churn_rate * 5)
        if tautology: score += 25

        action = 'NONE'
        rationale = 'Healthy test file'

        if ('BRITTLE_MOCKING' in tags or 'TAUTOLOGY' in tags) and unique_cov == 0:
            action = 'DELETE'
            rationale = 'Test is brittle or a tautology and provides 0 unique coverage'
        elif churn_rate > 5 and score > 50:
            action = 'QUARANTINE'
            rationale = 'High churn and high rot score'
        elif 'CONTEXT_BLOAT' in tags:
            action = 'COMPACT_SNAPSHOTS'
            rationale = 'Test exceeds max token context limit'

        if unique_cov > 0 and action == 'DELETE':
            action = 'NONE'
            rationale = 'Retained due to unique coverage'

        results.append({
            'file': test_file,
            'score': min(score, 100),
            'tags': tags,
            'action': action,
            'rationale': rationale,
            'unique_coverage': unique_cov
        })

    return results

def execute_actions(results):
    baseline_cov = get_baseline_coverage()

    actions_taken = []

    # Check Vibe Check
    delete_quarantine_count = sum(1 for r in results if r['action'] in ['DELETE', 'QUARANTINE'])
    if delete_quarantine_count > 20:
        print("VIBE CHECK FAILED: > 20 files flagged for deletion/quarantine. Aborting.")
        return actions_taken

    for res in results:
        file = res['file']
        action = res['action']

        if action == 'DELETE':
            os.remove(file)
            actions_taken.append((file, 'DELETED', res['tags'], res['unique_coverage'], res['rationale']))
        elif action == 'QUARANTINE':
            os.makedirs(QUARANTINE_DIR, exist_ok=True)
            shutil.move(file, os.path.join(QUARANTINE_DIR, os.path.basename(file)))
            actions_taken.append((file, 'QUARANTINED', res['tags'], res['unique_coverage'], res['rationale']))
        elif action == 'COMPACT_SNAPSHOTS':
            if apply_compact_snapshots(file):
                actions_taken.append((file, 'REFACTORED', res['tags'], res['unique_coverage'], 'Externalized large JSON snapshots'))
            else:
                actions_taken.append((file, 'FAILED_REFACTOR', res['tags'], res['unique_coverage'], 'Could not extract snapshots'))

    # Check Coverage Cliff
    if actions_taken:
        new_cov = get_baseline_coverage()
        if baseline_cov - new_cov > MAX_COVERAGE_DROP:
            print(f"COVERAGE CLIFF FAILED: Coverage dropped from {baseline_cov}% to {new_cov}%. Reverting.")
            subprocess.run(["git", "checkout", TESTS_DIR])
            if os.path.exists(QUARANTINE_DIR):
                shutil.rmtree(QUARANTINE_DIR)
            return []

    return actions_taken

def generate_report(actions_taken):
    report = "# [Entropy] Maintenance - Liability Reduction\n\n"
    report += "| File | Rot Type | Unique Coverage | Action Taken | Rationale |\n"
    report += "| --- | --- | --- | --- | --- |\n"
    for file, action, tags, cov, rationale in actions_taken:
        tag_str = ", ".join(tags) if tags else "NONE"
        cov_str = f"{cov} lines" if cov != float('inf') else "Infinite (Critical Path)"
        report += f"| {file} | {tag_str} | {cov_str} | {action} | {rationale} |\n"

    with open("entropy_report.md", "w") as f:
        f.write(report)
    print(report)

if __name__ == "__main__":
    results = analyze_test_files()
    actions_taken = execute_actions(results)
    generate_report(actions_taken)
