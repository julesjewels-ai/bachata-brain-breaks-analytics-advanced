import os
import json
import ast
import subprocess
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Set, Optional, Literal, TypedDict
from dataclasses import dataclass, asdict
from datetime import datetime

# --- Configuration ---
MAX_TOKEN_CONTEXT = 2000
MAX_MOCK_DENSITY = 0.55
MIN_UNIQUE_COVERAGE_THRESHOLD = 5
EXECUTION_MODE = 'PR_SUGGESTION' # 'PR_SUGGESTION' | 'REPORT_ONLY'
MAX_FILES_FLAGGED = 20
MAX_COVERAGE_CLIFF = 0.5
QUARANTINE_DIR = Path("tests/quarantine")
SNAPSHOTS_DIR = Path("tests/snapshots")

# --- Domain Models ---

@dataclass
class TestFileHealth:
    filePath: str
    associatedSourceFiles: List[str]
    loc: int
    mockDensity: float
    churnRate: int
    tokenCost: int
    uniqueCoverageLines: int
    isCriticalPath: bool

@dataclass
class RotVerdict:
    file: str
    score: int
    tags: List[str] # 'BRITTLE_MOCKING', 'CONTEXT_BLOAT', 'REDUNDANT_COVERAGE', 'TAUTOLOGY', 'HIGH_CHURN'
    suggestedAction: Literal['QUARANTINE', 'COMPACT_SNAPSHOTS', 'DELETE', 'NONE']

class EntropyReport(TypedDict):
    timestamp: str
    global_coverage_before: float
    global_coverage_after: float
    actions_taken: List[Dict]
    verdicts: List[Dict]

# --- Helper Functions ---

def run_command(command: str) -> str:
    try:
        result = subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command '{command}': {e.stderr}")
        return ""

def get_git_churn(filepath: str) -> int:
    # Count commits in the last 30 days
    cmd = f"git log --since='30 days ago' --oneline -- {filepath} | wc -l"
    try:
        return int(run_command(cmd))
    except ValueError:
        return 0

def estimate_tokens(text: str) -> int:
    return len(text) // 4

def get_loc(filepath: str) -> int:
    try:
        with open(filepath, 'r') as f:
            return sum(1 for line in f if line.strip())
    except FileNotFoundError:
        return 0

def parse_imports(filepath: str) -> List[str]:
    associated_files = []
    try:
        with open(filepath, "r") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    associated_files.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    associated_files.append(node.module)
    except Exception as e:
        print(f"Error parsing imports for {filepath}: {e}")

    # Filter for src modules (heuristic)
    return [f for f in associated_files if f.startswith('src')]

def analyze_ast_rot(filepath: str) -> Dict:
    metrics = {
        'mock_lines': 0,
        'tautologies': 0,
        'large_literals': [] # List of (lineno, size_in_lines, type)
    }

    try:
        with open(filepath, "r") as f:
            content = f.read()
            tree = ast.parse(content)
            lines = content.splitlines()

        # Mock Density
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Removed JS-specific patterns (spyOn, .mockReturnValue)
            if any(s in stripped for s in ["mock(", "Mock(", "patch("]):
                metrics['mock_lines'] += 1

        # Tautologies & Large Literals
        for node in ast.walk(tree):
            # Tautologies (heuristic)
            if isinstance(node, ast.Assert):
                if isinstance(node.test, ast.Constant) and node.test.value is True:
                     metrics['tautologies'] += 1
                if isinstance(node.test, ast.Compare):
                     if isinstance(node.test.left, ast.Name) and isinstance(node.test.comparators[0], ast.Name):
                         if node.test.left.id == node.test.comparators[0].id:
                             metrics['tautologies'] += 1

            # Large Literals (for Context Bloat)
            if isinstance(node, (ast.Dict, ast.List)):
                start_line = node.lineno
                end_line = node.end_lineno
                if start_line and end_line and (end_line - start_line > 10):
                     metrics['large_literals'].append({
                         'lineno': start_line,
                         'end_lineno': end_line,
                         'lines': end_line - start_line,
                         'type': 'dict' if isinstance(node, ast.Dict) else 'list'
                     })

    except Exception as e:
        print(f"Error analyzing AST for {filepath}: {e}")

    return metrics

def get_unique_coverage(coverage_data: Dict) -> Dict[str, int]:
    # coverage_data is the JSON output from coverage.py
    # Returns map: {test_file_path: unique_lines_count}

    # Need to map source lines to the tests that cover them
    # Structure of coverage.json (with contexts):
    # "files": { "src/file.py": { "contexts": { "lineno": ["test_context1", "test_context2"] } } }

    file_unique_coverage = {}

    if not coverage_data or 'files' not in coverage_data:
        return {}

    # Initialize all test files with 0
    # We need a list of all test files first.
    # The contexts usually look like "tests/test_foo.py::test_bar|run"

    # We will iterate through all source files and their covered lines
    for src_file, data in coverage_data.get('files', {}).items():
        contexts_by_lineno = data.get('contexts', {})
        for lineno, contexts in contexts_by_lineno.items():
            # Filter contexts to identify unique test files
            # Contexts might be multiple for same file (different test cases)
            test_files_covering_line = set()
            for ctx in contexts:
                # Extract file path from context
                # Context format: "tests/test_file.py::test_case|run" or just "tests/test_file.py" depending on setup
                if "::" in ctx:
                    test_file = ctx.split("::")[0]
                elif "|" in ctx:
                     test_file = ctx.split("|")[0]
                else:
                    test_file = ctx # Fallback

                # Normalize relative path if needed, but coverage usually gives relative or absolute
                # Let's assume relative to root for now or check if it contains 'tests/'
                if 'tests/' in test_file:
                     test_files_covering_line.add(test_file)

            if len(test_files_covering_line) == 1:
                unique_test_file = list(test_files_covering_line)[0]
                file_unique_coverage[unique_test_file] = file_unique_coverage.get(unique_test_file, 0) + 1

    return file_unique_coverage

# --- Main Logic ---

def main():
    print("📉 Entropy: Initializing Scan...")

    # 1. Setup & Cartography

    # Load Critical Paths
    critical_paths = []
    if os.path.exists("critical_paths.json"):
        with open("critical_paths.json", "r") as f:
            critical_paths = json.load(f)
            # Normalize paths
            critical_paths = [str(Path(p).resolve().relative_to(Path.cwd())) for p in critical_paths if os.path.exists(p)]

    # Generate Coverage
    print("Running tests with coverage...")
    # Clean previous coverage
    run_command("coverage erase")
    # Run pytest with coverage context
    # We need context to know which test covered which line
    run_command("pytest --cov=. --cov-report=json --cov-context=test")

    if not os.path.exists("coverage.json"):
        print("Error: coverage.json not found. Aborting.")
        return

    with open("coverage.json", "r") as f:
        coverage_data = json.load(f)

    # Get global coverage percentage
    global_coverage_before = coverage_data.get("totals", {}).get("percent_covered", 0.0)
    print(f"Global Coverage Before: {global_coverage_before}%")

    # Calculate Unique Coverage
    # Need to use 'coverage json --show-contexts' output which is structured differently?
    # standard 'coverage json' might not have contexts if not configured?
    # Actually, `coverage json` output structure depends on version.
    # To get contexts in JSON, we might need to rely on the .coverage db or ensure json has it.
    # Let's check if 'contexts' key is present in 'files' elements.
    # If not, we might need to use `coverage json --show-contexts` command specifically if CLI supports it,
    # or rely on `coverage.Coverage` API.
    # Simpler: run `coverage json --show-contexts` now.
    run_command("coverage json --show-contexts")
    with open("coverage.json", "r") as f:
        coverage_data_context = json.load(f)

    unique_coverage_map = get_unique_coverage(coverage_data_context)

    # Scan Test Files
    test_files = [str(p) for p in Path("tests").rglob("test_*.py") if "quarantine" not in str(p)]

    health_reports: List[TestFileHealth] = []
    verdicts: List[RotVerdict] = []

    print(f"Scanning {len(test_files)} test files...")

    for filepath in test_files:
        # Metrics
        loc = get_loc(filepath)
        if loc == 0: continue

        churn = get_git_churn(filepath)
        with open(filepath, 'r') as f:
            content = f.read()
            token_cost = estimate_tokens(content)

        ast_metrics = analyze_ast_rot(filepath)
        mock_density = ast_metrics['mock_lines'] / loc

        unique_lines = unique_coverage_map.get(filepath, 0)
        is_critical = filepath in critical_paths

        # Override unique coverage for critical paths
        if is_critical:
            unique_lines = 9999

        health = TestFileHealth(
            filePath=filepath,
            associatedSourceFiles=parse_imports(filepath),
            loc=loc,
            mockDensity=mock_density,
            churnRate=churn,
            tokenCost=token_cost,
            uniqueCoverageLines=unique_lines,
            isCriticalPath=is_critical
        )
        health_reports.append(health)

        # Verdict Logic
        score = 0
        tags = []
        suggested_action = 'NONE'

        if mock_density > MAX_MOCK_DENSITY:
            tags.append('BRITTLE_MOCKING')
            score += 40

        if token_cost > MAX_TOKEN_CONTEXT:
            tags.append('CONTEXT_BLOAT')
            score += 30

        if ast_metrics['tautologies'] > 0:
            tags.append('TAUTOLOGY')
            score += 20

        if churn > 5:
            tags.append('HIGH_CHURN')
            score += 20

        if unique_lines == 0 and not is_critical:
            tags.append('REDUNDANT_COVERAGE')
            score += 30

        # Strategy Selection

        # Strategy A: Bloat Reducer
        if 'CONTEXT_BLOAT' in tags and ast_metrics['large_literals']:
            suggested_action = 'COMPACT_SNAPSHOTS'

        # Strategy B: Liability Prune
        # Delete if (Brittle OR Tautology) AND (Unique Coverage < Threshold)
        elif (('BRITTLE_MOCKING' in tags or 'TAUTOLOGY' in tags) and unique_lines < MIN_UNIQUE_COVERAGE_THRESHOLD and not is_critical):
            suggested_action = 'DELETE'

        # Strategy C: Quarantine
        # Move if (High Churn) AND (Rot Score > 50)
        elif ('HIGH_CHURN' in tags and score > 50 and not is_critical):
            suggested_action = 'QUARANTINE'

        verdicts.append(RotVerdict(
            file=filepath,
            score=score,
            tags=tags,
            suggestedAction=suggested_action
        ))

    # 4. Action Execution Phase

    actions_taken = []
    files_to_delete = [v.file for v in verdicts if v.suggestedAction == 'DELETE']
    files_to_quarantine = [v.file for v in verdicts if v.suggestedAction == 'QUARANTINE']

    # Safety Guards
    total_flagged = len(files_to_delete) + len(files_to_quarantine)
    if total_flagged > MAX_FILES_FLAGGED:
        print(f"🚨 VIBE CHECK FAILED: {total_flagged} files flagged. Aborting.")
        return

    # Coverage Cliff Check (Simulation)
    # If we delete/quarantine these files, does coverage drop > 0.5%?
    # We can estimate this by summing unique coverage of affected files / total statements
    # But for 'DELETE' unique coverage is 0, so no drop.
    # For 'QUARANTINE', unique coverage might be > 0.

    potential_loss = 0
    total_statements = coverage_data.get("totals", {}).get("num_statements", 1) # avoid div/0

    for v in verdicts:
        if v.suggestedAction in ['DELETE', 'QUARANTINE']:
             # Find health record
             h = next((h for h in health_reports if h.filePath == v.file), None)
             if h:
                 potential_loss += h.uniqueCoverageLines

    coverage_drop_percent = (potential_loss / total_statements) * 100
    if coverage_drop_percent > MAX_COVERAGE_CLIFF:
         print(f"🚨 COVERAGE CLIFF: Action would drop coverage by {coverage_drop_percent:.2f}%. Aborting.")
         return

    # Execute Actions
    for v in verdicts:
        if v.suggestedAction == 'DELETE':
            print(f"🗑️ Deleting {v.file}")
            os.remove(v.file)
            actions_taken.append({"file": v.file, "action": "DELETED", "reason": f"{v.tags}"})

        elif v.suggestedAction == 'QUARANTINE':
            print(f"☣️ Quarantining {v.file}")
            # Ensure quarantine directory exists
            if not QUARANTINE_DIR.exists():
                QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

            dest = QUARANTINE_DIR / Path(v.file).name
            shutil.move(v.file, dest)
            actions_taken.append({"file": v.file, "action": "QUARANTINED", "reason": f"Score {v.score}, High Churn"})

        elif v.suggestedAction == 'COMPACT_SNAPSHOTS':
            print(f"📦 Compacting snapshots for {v.file}")
            # Identify literals again to be safe and replace them
            # This is complex to do robustly with just AST, usually needs a proper refactoring tool (LibCST)
            # For this simplified version, we will just Log it as TODO or perform a very simple replacement if safe.
            # To avoid breaking code, we will skip actual code modification for snapshots in this strict environment
            # unless we implement a robust transformer.
            # Let's implement a safe externalizer:
            try:
                result = externalize_snapshots(v.file)
                if result:
                    actions_taken.append({"file": v.file, "action": "REFACTORED", "reason": "Context Bloat"})
                else:
                    print(f"Skipping externalization for {v.file} due to complexity.")
            except Exception as e:
                print(f"Failed to externalize snapshots for {v.file}: {e}")

    # Generate Report
    report_md = "# 📉 Entropy Scan Report\n\n"
    report_md += f"**Date:** {datetime.now().isoformat()}\n"
    report_md += f"**Global Coverage:** {global_coverage_before}%\n\n"

    report_md += "## 📋 Actions Taken\n\n"
    if actions_taken:
        report_md += "| File | Action | Rationale |\n"
        report_md += "|------|--------|-----------|\n"
        for action in actions_taken:
            report_md += f"| {action['file']} | {action['action']} | {action['reason']} |\n"
    else:
        report_md += "No actions taken.\n"

    report_md += "\n## 🏥 Health Scan\n\n"
    report_md += "| File | Score | Tags | Unique Coverage |\n"
    report_md += "|------|-------|------|-----------------|\n"
    for v in verdicts:
        h = next((h for h in health_reports if h.filePath == v.file), None)
        unique = h.uniqueCoverageLines if h else "?"
        report_md += f"| {v.file} | {v.score} | {', '.join(v.tags)} | {unique} |\n"

    with open("entropy_report.md", "w") as f:
        f.write(report_md)

    print("✅ Scan Complete. Report generated: entropy_report.md")

def externalize_snapshots(filepath: str) -> bool:
    # Simplistic implementation:
    # 1. Read file
    # 2. Find large dict/list definitions in AST
    # 3. Dump them to json file
    # 4. Replace in code with json.load

    # Return True if modified, False if skipped

    if not SNAPSHOTS_DIR.exists():
        SNAPSHOTS_DIR.mkdir(parents=True)

    with open(filepath, 'r') as f:
        content = f.read()

    tree = ast.parse(content)
    # We need to process in reverse order of line numbers to avoid offsetting
    # However, AST doesn't give us easy replacement.
    # We will use string manipulation based on line numbers.

    lines = content.splitlines()
    metrics = analyze_ast_rot(filepath)
    literals = sorted(metrics['large_literals'], key=lambda x: x['lineno'], reverse=True)

    if not literals:
        return False

    # NOTE: Due to complexity of robust AST transformation without LibCST,
    # we will SKIP the actual file modification for Strategy A in this iteration
    # to avoid breaking code. We will just report it.

    # Return False to indicate no action was taken
    return False

if __name__ == "__main__":
    main()
