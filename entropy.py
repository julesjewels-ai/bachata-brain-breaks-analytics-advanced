import os
import sys
import json
import subprocess
import ast
import sqlite3
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Any, Tuple
import coverage

# Configuration
CONFIG = {
    'maxTokenContext': 2000,
    'maxMockDensity': 0.55,
    'minUniqueCoverageThreshold': 5,
    'executionMode': 'PR_SUGGESTION',  # We will execute actions and report
    'maxActionsThreshold': 20, # The Vibe Check
}

REPORT_FILE = 'entropy_report.md'
QUARANTINE_DIR = os.path.join('tests', 'quarantine')
CRITICAL_PATHS_FILE = 'critical_paths.json'

class Entropy:
    def __init__(self):
        self.metrics = {}
        self.unique_coverage = defaultdict(int)
        self.actions = []
        self.critical_paths = self.load_critical_paths()

    def load_critical_paths(self):
        if os.path.exists(CRITICAL_PATHS_FILE):
            try:
                with open(CRITICAL_PATHS_FILE, 'r') as f:
                    return set(json.load(f))
            except json.JSONDecodeError:
                print(f"Warning: {CRITICAL_PATHS_FILE} is invalid JSON.")
                return set()
        return set()

    def run_coverage(self):
        print("Phase 1: Running Coverage...")
        # Clean previous coverage
        if os.path.exists('.coverage'):
            os.remove('.coverage')

        # Run pytest with coverage and context
        cmd = [
            sys.executable, '-m', 'pytest',
            '--cov=src',
            '--cov-report=json',
            '--cov-context=test',
            'tests/'
        ]
        try:
            subprocess.run(cmd, check=False, capture_output=True) # Don't check check=True as tests might fail, we just want coverage
        except Exception as e:
            print(f"Warning: Pytest failed: {e}")

    def analyze_unique_coverage(self):
        print("Phase 1b: Analyzing Unique Coverage...")
        cov = coverage.Coverage()
        cov.load()
        data = cov.get_data()

        # detailed_coverage: source_file -> line -> list of contexts
        # Contexts are usually "tests/test_foo.py::test_bar|run"

        measured_files = data.measured_files()

        for src_file in measured_files:
            if not data.lines(src_file):
                continue

            contexts_by_lineno = data.contexts_by_lineno(src_file)

            for line, contexts in contexts_by_lineno.items():
                if not contexts:
                    continue

                # Filter contexts to identify test files
                test_files = set()
                for ctx in contexts:
                    # Context format: "test_file.py::test_func|run" or similar
                    # We need to extract the file path.
                    if '::' in ctx:
                        test_file = ctx.split('::')[0]
                        test_files.add(test_file)
                    elif '|' in ctx: # sometimes just file|run
                        test_file = ctx.split('|')[0]
                        test_files.add(test_file)
                    else:
                        test_files.add(ctx)

                if len(test_files) == 1:
                    # Unique coverage!
                    test_file = list(test_files)[0]
                    # Normalize path
                    test_file = os.path.relpath(os.path.abspath(test_file), os.getcwd())
                    self.unique_coverage[test_file] += 1

    def get_churn(self, filepath):
        try:
            # Commits in last 30 days
            cmd = ['git', 'log', '--since=30.days', '--oneline', '--', filepath]
            result = subprocess.check_output(cmd, text=True)
            return len(result.strip().split('\n')) if result.strip() else 0
        except subprocess.CalledProcessError:
            return 0

    def analyze_file_rot(self, filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.splitlines()

        loc = len([l for l in lines if l.strip() and not l.strip().startswith('#')])
        if loc == 0:
            return {
                'loc': 0, 'mockDensity': 0, 'tokenCost': 0,
                'churnRate': 0, 'tautology': False
            }

        # Mock Density
        mock_keywords = ['mock', 'patch', 'MagicMock', 'spy', 'stub', 'call_count', 'assert_called']
        mock_lines = sum(1 for l in lines if any(k in l for k in mock_keywords))
        mock_density = mock_lines / loc

        # Token Cost (approx)
        token_cost = len(content) / 4

        # Churn
        churn_rate = self.get_churn(filepath)

        # Tautology Check (AST)
        tautology = False
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assert):
                    # assert True
                    # In Python 3.8+, ast.NameConstant is deprecated in favor of ast.Constant
                    if isinstance(node.test, ast.Constant):
                        if node.test.value is True: # explicitly True
                            tautology = True
                            break
                    # assert 1 == 1
                    if isinstance(node.test, ast.Compare):
                        if (isinstance(node.test.left, ast.Constant) and
                            len(node.test.comparators) == 1 and
                            isinstance(node.test.comparators[0], ast.Constant)):
                            if node.test.left.value == node.test.comparators[0].value:
                                tautology = True
                                break
        except SyntaxError:
            pass # Should not happen in valid python code

        return {
            'loc': loc,
            'mockDensity': mock_density,
            'tokenCost': token_cost,
            'churnRate': churn_rate,
            'tautology': tautology
        }

    def scan_tests(self):
        print("Phase 2: Scanning Tests for Rot...")
        test_dir = Path('tests')
        for path in test_dir.rglob('test_*.py'):
            if 'quarantine' in str(path):
                continue

            filepath = str(path)
            metrics = self.analyze_file_rot(filepath)
            self.metrics[filepath] = metrics

    def generate_verdict(self):
        print("Phase 3: Generating Verdict...")
        for filepath, m in self.metrics.items():
            unique_lines = self.unique_coverage.get(filepath, 0)

            # Critical Path Immunity
            is_critical = filepath in self.critical_paths or os.path.basename(filepath) in self.critical_paths
            if is_critical:
                unique_lines = float('inf') # Infinite unique coverage

            print(f"DEBUG: {filepath} -> Unique: {unique_lines}, Metrics: {m}, Critical: {is_critical}")

            action = 'NONE'
            rationale = []

            # Strategy A: Bloat Reducer
            if m['tokenCost'] > CONFIG['maxTokenContext']:
                action = 'REFACTOR'
                rationale.append(f"CONTEXT_BLOAT ({int(m['tokenCost'])} tokens)")

            # Strategy B: Liability Prune
            # "BRITTLE_MOCKING OR TAUTOLOGY detected AND uniqueCoverageLines === 0"
            is_brittle = m['mockDensity'] > CONFIG['maxMockDensity']
            if (is_brittle or m['tautology']) and unique_lines == 0:
                action = 'DELETE'
                rationale.append("Liability Prune (Brittle/Tautology & No Unique Coverage)")
                if is_brittle: rationale.append(f"Mock Density: {m['mockDensity']:.2f}")
                if m['tautology']: rationale.append("Tautology Detected")

            # Strategy C: Quarantine
            # "High Churn Rate (> 5 changes/month) AND High Rot Score"
            # Rot Score heuristic: brittle or bloat or tautology
            is_high_churn = m['churnRate'] > 5
            is_rot = is_brittle or m['tokenCost'] > CONFIG['maxTokenContext'] or m['tautology']

            if is_high_churn and is_rot and action != 'DELETE':
                action = 'QUARANTINE'
                rationale.append(f"High Churn ({m['churnRate']}) & Rot")

            if action != 'NONE':
                self.actions.append({
                    'file': filepath,
                    'action': action,
                    'metrics': m,
                    'unique_coverage': unique_lines,
                    'rationale': ", ".join(rationale)
                })

    def execute_actions(self):
        print("Phase 4: Executing Actions...")

        # The Vibe Check
        pending_changes = [a for a in self.actions if a['action'] in ('DELETE', 'QUARANTINE')]
        if len(pending_changes) > CONFIG['maxActionsThreshold']:
            print(f"ABORT: The Vibe Check failed! {len(pending_changes)} files flagged for removal (> {CONFIG['maxActionsThreshold']}). Aborting to prevent accidental mass deletion.")
            # We can still generate the report but not execute actions.
            for item in self.actions:
                item['status'] = 'ABORTED (Vibe Check)'
            return

        if not os.path.exists(QUARANTINE_DIR):
            os.makedirs(QUARANTINE_DIR)

        for item in self.actions:
            filepath = item['file']
            action = item['action']

            if action == 'DELETE':
                os.remove(filepath)
                item['status'] = 'DELETED'
            elif action == 'QUARANTINE':
                filename = os.path.basename(filepath)
                new_path = os.path.join(QUARANTINE_DIR, filename)
                shutil.move(filepath, new_path)
                item['status'] = 'QUARANTINED'
            elif action == 'REFACTOR':
                # For now, just report it as REFACTOR REQUIRED
                item['status'] = 'FLAGGED (Refactor Required)'
            else:
                item['status'] = 'SKIPPED'

    def report(self):
        print("Phase 5: Reporting...")
        lines = []
        lines.append("# [Entropy] Maintenance - Liability Reduction")
        lines.append("")
        lines.append("| File | Rot Type | Unique Coverage | Action Taken | Rationale |")
        lines.append("|---|---|---|---|---|")

        if not self.actions:
            lines.append("| - | - | - | No Action Required | - |")
            lines.append("\n**Summary:** All audited files passed the liability checks (Mock Density < 0.55, Token Cost < 2000, Unique Coverage > 0 or Not Brittle).")
        else:
            for item in self.actions:
                # Extract Rot Type from rationale for the table
                rot_type = "UNKNOWN"
                if "CONTEXT_BLOAT" in item['rationale']: rot_type = "CONTEXT_BLOAT"
                elif "Mock Density" in item['rationale']: rot_type = "BRITTLE_MOCKING"
                elif "Tautology" in item['rationale']: rot_type = "TAUTOLOGY"
                elif "High Churn" in item['rationale']: rot_type = "HIGH_CHURN"

                lines.append(f"| `{item['file']}` | {rot_type} | {item['unique_coverage']} lines | {item['status']} | {item['rationale']} |")

        report_content = "\n".join(lines)
        with open(REPORT_FILE, 'w') as f:
            f.write(report_content)

        print(f"Report generated at {REPORT_FILE}")

    def run(self):
        self.run_coverage()
        self.analyze_unique_coverage()
        self.scan_tests()
        self.generate_verdict()
        self.execute_actions()
        self.report()

if __name__ == '__main__':
    entropy = Entropy()
    entropy.run()
