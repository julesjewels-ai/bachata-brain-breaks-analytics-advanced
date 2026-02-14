import os
import sys
import ast
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Set, Any, Optional
import git
import coverage

# Configuration
CONFIG = {
    "maxTokenContext": 2000,
    "maxMockDensity": 0.55,
    "minUniqueCoverageThreshold": 5,
    "executionMode": "PR_SUGGESTION",
    "churnThreshold": 5, # Commits in last 30 days
}

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"
SRC_DIR = REPO_ROOT / "src"
CRITICAL_PATHS_FILE = REPO_ROOT / "critical_paths.json"
QUARANTINE_DIR = TESTS_DIR / "quarantine"
SNAPSHOTS_DIR = TESTS_DIR / "snapshots"

class TestFileHealth:
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.loc = 0
        self.mock_density = 0.0
        self.churn_rate = 0
        self.token_cost = 0
        self.unique_coverage_lines = 0
        self.is_critical_path = False
        self.associated_source_files = []
        self.tags = []

class RotVerdict:
    def __init__(self, file: str):
        self.file = file
        self.score = 0
        self.tags = []
        self.suggested_action = 'NONE'
        self.rationale = ""
        self.unique_coverage_lines = 0

def ensure_dirs():
    QUARANTINE_DIR.mkdir(exist_ok=True, parents=True)
    SNAPSHOTS_DIR.mkdir(exist_ok=True, parents=True)
    if not CRITICAL_PATHS_FILE.exists():
        with open(CRITICAL_PATHS_FILE, 'w') as f:
            json.dump([], f)

def get_critical_paths() -> Set[str]:
    if CRITICAL_PATHS_FILE.exists():
        with open(CRITICAL_PATHS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def run_coverage():
    print("Running coverage...")
    # Run pytest with coverage and context
    # Use -m pytest to ensure we use the same python env
    cmd = [
        sys.executable, "-m", "pytest",
        "--cov=src",
        "--cov-report=json",
        "--cov-context=test"
    ]
    # We allow failure because we want to analyze even if some tests fail
    subprocess.run(cmd, cwd=REPO_ROOT, check=False)

def get_unique_coverage(health_map: Dict[Path, TestFileHealth]):
    print("Analyzing unique coverage...")
    cov_file = REPO_ROOT / ".coverage"
    if not cov_file.exists():
        print("No .coverage file found.")
        return

    cov = coverage.Coverage(data_file=str(cov_file))
    cov.load()
    data = cov.get_data()

    for filename in data.measured_files():
        contexts = data.contexts_by_lineno(filename)
        for lineno, context_list in contexts.items():
            covering_test_files = set()
            for ctx in context_list:
                # context format: "test_file_path::test_name|run" or just "test_file_path"
                if "::" in ctx:
                    test_rel_path = ctx.split("::")[0]
                elif "|" in ctx:
                    test_rel_path = ctx.split("|")[0]
                else:
                    test_rel_path = ctx

                # Check if this path maps to a known test file
                try:
                    # Resolve relative to repo root
                    # test_rel_path might be absolute or relative
                    candidate = (REPO_ROOT / test_rel_path).resolve()
                    if candidate in health_map:
                        covering_test_files.add(candidate)
                except Exception:
                    pass

            if len(covering_test_files) == 1:
                unique_file = list(covering_test_files)[0]
                health_map[unique_file].unique_coverage_lines += 1

def analyze_ast_rot(health: TestFileHealth):
    try:
        with open(health.filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
             with open(health.filepath, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception:
            return

    health.loc = len(content.splitlines())
    health.token_cost = len(content) // 4 # Rough estimation

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return

    # Mock Density
    mock_lines = 0
    lines = content.splitlines()
    for line in lines:
        stripped = line.strip()
        if any(x in stripped for x in ["Mock(", "MagicMock(", "patch(", "spy(", "return_value="]):
            mock_lines += 1

    if health.loc > 0:
        health.mock_density = mock_lines / health.loc

    if health.mock_density > CONFIG["maxMockDensity"]:
        health.tags.append('BRITTLE_MOCKING')

    if health.token_cost > CONFIG["maxTokenContext"]:
        health.tags.append('CONTEXT_BLOAT')

    # Tautology Check (AST)
    class TautologyVisitor(ast.NodeVisitor):
        def __init__(self):
            self.found_tautology = False

        def visit_Assert(self, node):
            # check for `assert True` or `assert <Constant>`
            if isinstance(node.test, ast.Constant):
                # Only if truthy constant? Or any constant usually implies bad test
                self.found_tautology = True

            # Check comparisons of literals: `assert 1 == 1`
            if isinstance(node.test, ast.Compare):
                if isinstance(node.test.left, ast.Constant):
                     # check all comparators are constants
                     if all(isinstance(c, ast.Constant) for c in node.test.comparators):
                         self.found_tautology = True
            self.generic_visit(node)

    visitor = TautologyVisitor()
    visitor.visit(tree)
    if visitor.found_tautology:
        health.tags.append('TAUTOLOGY')

def calculate_churn(health: TestFileHealth, repo: git.Repo):
    try:
        # Commits in last 30 days affecting this file
        commits = list(repo.iter_commits(paths=str(health.filepath.relative_to(REPO_ROOT)), since="30.days.ago"))
        health.churn_rate = len(commits)
        if health.churn_rate > CONFIG["churnThreshold"]:
            health.tags.append('HIGH_CHURN')
    except Exception as e:
        # File might be untracked
        health.churn_rate = 0

def externalize_bloat(health: TestFileHealth) -> bool:
    # Attempt to extract large dict/list literals
    try:
        with open(health.filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return False

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return False

    bloat_candidates = []

    class BloatFinder(ast.NodeVisitor):
        def visit_Dict(self, node):
            self.check_node(node)
            self.generic_visit(node)

        def visit_List(self, node):
            self.check_node(node)
            self.generic_visit(node)

        def check_node(self, node):
            try:
                # get_source_segment requires python 3.8+
                segment = ast.get_source_segment(content, node)
                if segment and len(segment) > 500: # Arbitrary threshold for "large"
                    bloat_candidates.append((node, segment))
            except Exception:
                pass

    finder = BloatFinder()
    finder.visit(tree)

    if not bloat_candidates:
        return False

    # Process largest candidate
    bloat_candidates.sort(key=lambda x: len(x[1]), reverse=True)
    node, segment = bloat_candidates[0]

    # Validate it's literal eval safe
    try:
        data = ast.literal_eval(segment)
    except Exception:
        # Not a pure literal (might contain variable references)
        return False

    snapshot_name = f"{health.filepath.stem}_snapshot_{int(time.time())}.json"
    snapshot_path = SNAPSHOTS_DIR / snapshot_name

    try:
        with open(snapshot_path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        return False

    # Replace in file
    # Use string replacement carefully.
    # To be safe, we replace only the first occurrence of this exact segment string?
    # Or rely on AST location? AST location is safer but requires reconstructing code.
    # String replacement of exact segment is okay if segment is large and unique.

    if content.count(segment) == 1:
        # Construct replacement code
        # We need to import json if not present, but using __import__ is safer for one-line replacement
        rel_path = snapshot_path.relative_to(REPO_ROOT)
        replacement = f"__import__('json').load(open('{rel_path}'))"

        new_content = content.replace(segment, replacement)

        with open(health.filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True

    return False

def main():
    ensure_dirs()

    # Phase 1: Cartography
    run_coverage()

    # Identify test files
    test_files = list(TESTS_DIR.rglob("test_*.py"))
    # Exclude files in quarantine or snapshots if they match pattern (unlikely but safe)
    test_files = [f for f in test_files if QUARANTINE_DIR not in f.parents and SNAPSHOTS_DIR not in f.parents]

    health_map = {f.resolve(): TestFileHealth(f.resolve()) for f in test_files}

    # Critical paths immunity
    critical_paths = get_critical_paths()
    for f, h in health_map.items():
        if f.name in critical_paths:
            h.is_critical_path = True
            h.unique_coverage_lines = 999999

    get_unique_coverage(health_map)

    try:
        repo = git.Repo(REPO_ROOT)
    except git.InvalidGitRepositoryError:
        repo = None
        print("Warning: Not a valid git repository. Churn calculation skipped.")

    verdicts = []

    # Phase 2 & 3: Rot Scan & Actions
    for f, h in health_map.items():
        analyze_ast_rot(h)
        if repo:
            calculate_churn(h, repo)

        verdict = RotVerdict(str(f.relative_to(REPO_ROOT)))
        verdict.tags = h.tags
        verdict.unique_coverage_lines = h.unique_coverage_lines

        action_taken = False

        # Strategy A: Bloat Reducer
        if 'CONTEXT_BLOAT' in h.tags:
            if externalize_bloat(h):
                verdict.suggested_action = 'REFACTORED'
                verdict.rationale = f"Externalized large literals. Original size: {h.token_cost}"
                action_taken = True

        # Strategy B: Liability Prune
        # Delete if Brittle/Tautology AND 0 Unique Coverage
        if not action_taken and ('BRITTLE_MOCKING' in h.tags or 'TAUTOLOGY' in h.tags):
            if h.unique_coverage_lines == 0 and not h.is_critical_path:
                verdict.suggested_action = 'DELETED'
                verdict.rationale = "Brittle/Tautology with 0 unique coverage."
                # Delete file
                try:
                    f.unlink()
                    action_taken = True
                except Exception as e:
                    print(f"Failed to delete {f}: {e}")

        # Strategy C: Quarantine
        # High Churn (>5/month) AND High Rot (detected by having tags)
        if not action_taken and 'HIGH_CHURN' in h.tags:
            # "High Rot Score" -> assume > 0 other tags or mock density?
            # Prompt says "High Rot Score". Let's assume having *any* rot tag + High Churn.
            # Or mock density > 0.
            if len(h.tags) > 1: # HIGH_CHURN + at least one other tag
                verdict.suggested_action = 'QUARANTINED'
                verdict.rationale = "High Churn and Rot."
                try:
                    shutil.move(str(f), str(QUARANTINE_DIR / f.name))
                    action_taken = True
                except Exception as e:
                    print(f"Failed to quarantine {f}: {e}")

        if action_taken:
            verdicts.append(verdict)

    # Phase 4: Cleanse (Report)
    # Generate Markdown Table
    report_lines = []
    report_lines.append(f"Entropy Scan Report - {time.strftime('%Y-%m-%d')}")
    report_lines.append("")
    report_lines.append("| File | Rot Type | Unique Coverage | Action Taken | Rationale |")
    report_lines.append("|---|---|---|---|---|")

    for v in verdicts:
        tags_str = ", ".join(v.tags)
        report_lines.append(f"| {v.file} | {tags_str} | {v.unique_coverage_lines} lines | {v.suggested_action} | {v.rationale} |")

    if not verdicts:
        report_lines.append("| No actions taken. | | | | |")

    report_content = "\n".join(report_lines)
    report_path = REPO_ROOT / "entropy_report.md"
    with open(report_path, "w") as f:
        f.write(report_content)

    print(f"Entropy Scan Complete. Report written to {report_path}")

    # Clean up coverage files to avoid pollution
    if (REPO_ROOT / "coverage.json").exists():
        (REPO_ROOT / "coverage.json").unlink()
    if (REPO_ROOT / ".coverage").exists():
        (REPO_ROOT / ".coverage").unlink()

if __name__ == "__main__":
    main()
