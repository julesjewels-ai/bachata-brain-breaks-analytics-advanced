import json
import ast
import os
import sys
import subprocess
import glob
import shutil
from pathlib import Path
from collections import defaultdict

MAX_TOKEN_CONTEXT = 2000
MAX_MOCK_DENSITY = 0.55
MIN_UNIQUE_COVERAGE = 5
MAX_CHURN = 5
ROTS_THRESHOLD_FOR_QUARANTINE = 50
MAX_DELETIONS_ALLOWED = 20

def get_churn(filepath):
    try:
        # Use git log to count commits touching the file
        result = subprocess.run(
            ['git', 'log', '--oneline', '--follow', '--', filepath],
            capture_output=True, text=True, check=True
        )
        output = result.stdout.strip()
        if not output:
            return 0
        return len(output.split('\n'))
    except subprocess.CalledProcessError:
        return 0
    except FileNotFoundError:
        return 0

def analyze_ast(filepath):
    try:
        with open(filepath, 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return {'mock_density': 0, 'token_cost': 0, 'tautologies': 0, 'loc': 0}

    try:
        tree = ast.parse(content)
    except SyntaxError:
        print(f"SyntaxError in {filepath}")
        return {'mock_density': 0, 'token_cost': 0, 'tautologies': 0, 'loc': 0}

    lines = content.splitlines()
    total_lines = len(lines)
    mock_lines = 0
    tautologies = 0

    # Simple line-based check for mocks as per prompt instruction
    # "Count lines starting with mock(, spyOn(, or .mockReturnValue(."
    # Adapted to Python: mock., patch(, MagicMock(
    for line in lines:
        stripped = line.strip()
        if 'mock' in stripped.lower() or 'patch' in stripped.lower() or 'spy' in stripped.lower():
            mock_lines += 1

    for node in ast.walk(tree):
        # Tautologies
        if isinstance(node, ast.Assert):
            if isinstance(node.test, ast.Constant) and node.test.value is True:
                tautologies += 1
            elif isinstance(node.test, ast.Compare):
                if isinstance(node.test.left, ast.Constant) and \
                   len(node.test.comparators) > 0 and \
                   isinstance(node.test.comparators[0], ast.Constant) and \
                   node.test.left.value == node.test.comparators[0].value:
                     tautologies += 1

    mock_density = mock_lines / total_lines if total_lines > 0 else 0
    token_cost = len(content) / 4 # Rough estimate

    large_literals = []
    for node in ast.walk(tree):
         if isinstance(node, (ast.List, ast.Dict)):
            start = node.lineno
            end = node.end_lineno
            if end and (end - start > 20):
                large_literals.append((start, end))

    return {
        'mock_density': mock_density,
        'token_cost': token_cost,
        'tautologies': tautologies,
        'loc': total_lines,
        'large_literals': large_literals
    }

def get_coverage_map(test_files):
    cov_map = {}
    for tf in test_files:
        print(f"Running coverage for {tf}...")
        # Ensure source path exists to avoid silent failures
        if not os.path.exists('src/core'):
             print("Error: src/core does not exist. Aborting coverage check.")
             return {}

        subprocess.run(
            [sys.executable, '-m', 'pytest', f'--cov=src.core', '--cov-report=json:cov_temp.json', '-q', tf],
            capture_output=True, text=True
        )
        if os.path.exists('cov_temp.json'):
            try:
                with open('cov_temp.json', 'r') as f:
                    data = json.load(f)
                    file_cov = set()
                    for src_file, metrics in data['files'].items():
                        # We use absolute paths to be safe, then maybe simplified?
                        # Or just stick to the file path as key.
                        # Using (src_file, line_number) tuple
                        for line in metrics['executed_lines']:
                            file_cov.add((src_file, line))
                    cov_map[tf] = file_cov
            except Exception as e:
                print(f"Error parsing coverage for {tf}: {e}")
                cov_map[tf] = set()
            os.remove('cov_temp.json')
        else:
            print(f"Warning: No coverage generated for {tf}")
            cov_map[tf] = set()

    return cov_map

def calculate_unique_coverage(cov_map):
    # Count how many files cover each line
    line_coverage_counts = defaultdict(int)
    for tf, covered_lines in cov_map.items():
        for line_key in covered_lines:
            line_coverage_counts[line_key] += 1

    # Now count unique lines for each file
    unique_counts = {}
    for tf, covered_lines in cov_map.items():
        unique_lines = 0
        for line_key in covered_lines:
            if line_coverage_counts[line_key] == 1:
                unique_lines += 1
        unique_counts[tf] = unique_lines

    return unique_counts

def get_global_coverage():
    if not os.path.exists('src/core'):
        return 0.0

    subprocess.run(
        [sys.executable, '-m', 'pytest', '--cov=src.core', '--cov-report=json:cov_global.json', '-q'],
        capture_output=True, text=True
    )
    if os.path.exists('cov_global.json'):
        with open('cov_global.json', 'r') as f:
            data = json.load(f)
            total_stmts = data['totals']['num_statements']
            covered_stmts = data['totals']['covered_lines'] # Usually correct key
            # Or use 'percent_covered' directly
            percent = data['totals']['percent_covered']
        os.remove('cov_global.json')
        return percent
    return 0.0

def load_critical_paths():
    if os.path.exists('critical_paths.json'):
        try:
            with open('critical_paths.json', 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def main():
    test_files = glob.glob('tests/test_*.py')
    print(f"Found test files: {test_files}")

    # Check paths
    if not os.path.exists('tests/quarantine'):
        os.makedirs('tests/quarantine')
    if not os.path.exists('tests/snapshots'):
        os.makedirs('tests/snapshots')

    critical_paths = load_critical_paths()

    # Baseline Coverage
    print("Calculating baseline global coverage...")
    baseline_coverage = get_global_coverage()
    print(f"Baseline Coverage: {baseline_coverage}%")

    # 1. Coverage Map
    cov_map = get_coverage_map(test_files)

    # 2. Unique Coverage
    unique_counts = calculate_unique_coverage(cov_map)

    # 3. Analyze Rot
    report_data = []
    actions_to_take = []

    print("\n--- ROT ANALYSIS ---")

    for tf in test_files:
        metrics = analyze_ast(tf)
        churn = get_churn(tf)
        unique = unique_counts.get(tf, 0)

        rot_tags = []
        rot_score = 0

        # Determine Rot Tags
        if metrics['mock_density'] > MAX_MOCK_DENSITY:
            rot_tags.append('BRITTLE_MOCKING')
            rot_score += 50

        if metrics['token_cost'] > MAX_TOKEN_CONTEXT:
            rot_tags.append('CONTEXT_BLOAT')
            rot_score += 30

        if metrics['tautologies'] > 0:
            rot_tags.append('TAUTOLOGY')
            rot_score += 20

        if churn > MAX_CHURN:
            rot_tags.append('HIGH_CHURN')
            rot_score += 20

        # Determine Action
        action = 'NONE'

        is_immune = (unique > 0) or (tf in critical_paths)

        # Strategy B: Liability Prune
        # Condition: (BRITTLE_MOCKING OR TAUTOLOGY) AND uniqueCoverage == 0
        if ('BRITTLE_MOCKING' in rot_tags or 'TAUTOLOGY' in rot_tags) and not is_immune:
            action = 'DELETE'

        # Strategy C: Quarantine
        # Condition: HIGH_CHURN AND High Rot Score
        elif 'HIGH_CHURN' in rot_tags and rot_score >= ROTS_THRESHOLD_FOR_QUARANTINE:
            action = 'QUARANTINE'

        # Strategy A: Bloat Reducer
        elif 'CONTEXT_BLOAT' in rot_tags:
            action = 'REFACTOR_BLOAT'

        entry = {
            'file': tf,
            'metrics': {
                'loc': metrics['loc'],
                'mock_density': round(metrics['mock_density'], 2),
                'churn': churn,
                'token_cost': int(metrics['token_cost']),
                'unique_lines': unique,
                'large_literals': metrics.get('large_literals', [])
            },
            'rot_tags': rot_tags,
            'rot_score': rot_score,
            'action': action
        }
        report_data.append(entry)
        if action != 'NONE':
            actions_to_take.append((tf, action))

    # Safety Guard: Vibe Check
    files_to_delete_or_move = [a for a in actions_to_take if a[1] in ('DELETE', 'QUARANTINE')]
    if len(files_to_delete_or_move) > MAX_DELETIONS_ALLOWED:
        print(f"CRITICAL: Too many files flagged for removal ({len(files_to_delete_or_move)}). Aborting operation.")
        sys.exit(1)

    # Output Report
    print(json.dumps(report_data, indent=2))
    with open('entropy_report.json', 'w') as f:
        json.dump(report_data, f, indent=2)

    # 4. Execute Actions
    print("\n--- EXECUTING ACTIONS ---")
    deleted_files = []
    quarantined_files = []

    for tf, action in actions_to_take:
        if action == 'DELETE':
            print(f"Action: DELETING {tf}")
            if os.path.exists(tf):
                # Back up just in case
                shutil.copy(tf, tf + ".bak")
                os.remove(tf)
                deleted_files.append(tf)
        elif action == 'QUARANTINE':
            print(f"Action: QUARANTINING {tf}")
            dest = os.path.join('tests/quarantine', os.path.basename(tf))
            if os.path.exists(tf):
                shutil.move(tf, dest)
                quarantined_files.append(tf)
        elif action == 'REFACTOR_BLOAT':
            print(f"Action: Flagged {tf} for Refactoring (Manual Step)")

    # 5. Safety Guard: Coverage Cliff
    if deleted_files or quarantined_files:
        print("Verifying global coverage...")
        new_coverage = get_global_coverage()
        print(f"New Coverage: {new_coverage}%")

        if baseline_coverage - new_coverage > 0.5:
            print(f"CRITICAL: Coverage dropped by more than 0.5% ({baseline_coverage} -> {new_coverage}). Rolling back changes.")
            # Rollback deletions
            for tf in deleted_files:
                if os.path.exists(tf + ".bak"):
                    shutil.move(tf + ".bak", tf)
                    print(f"Restored {tf}")
            # Rollback quarantine
            for tf in quarantined_files:
                dest = os.path.join('tests/quarantine', os.path.basename(tf))
                if os.path.exists(dest):
                    shutil.move(dest, tf)
                    print(f"Restored {tf}")
            sys.exit(1)
        else:
            # Cleanup backups
            for tf in deleted_files:
                if os.path.exists(tf + ".bak"):
                    os.remove(tf + ".bak")
            print("Coverage check passed.")

if __name__ == '__main__':
    main()
