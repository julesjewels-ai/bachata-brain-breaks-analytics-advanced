import json
import os
import subprocess
import ast
import math
from pathlib import Path
from typing import Dict, List, Any, Optional

MAX_TOKEN_CONTEXT = 2000
MAX_MOCK_DENSITY = 0.55
MIN_UNIQUE_COVERAGE = 5
EXECUTION_MODE = "PR_SUGGESTION"

class TestFileHealth:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.associated_source_files: List[str] = []
        self.loc = 0
        self.mock_density = 0.0
        self.churn_rate = 0
        self.token_cost = 0
        self.unique_coverage_lines = 0
        self.is_critical_path = False

class RotVerdict:
    def __init__(self, file: str):
        self.file = file
        self.score = 0
        self.tags: List[str] = []
        self.suggested_action = "NONE"
        self.rationale = ""
        self.unique_coverage_lines = 0

def get_git_churn(file_path: str) -> int:
    try:
        # Number of commits in the last 30 days
        cmd = ["git", "log", "--since=30.days", "--oneline", "--", file_path]
        output = subprocess.check_output(cmd, text=True).strip()
        if not output:
            return 0
        return len(output.split(''))
    except Exception:
        return 0

def run_coverage() -> Dict[str, Any]:
    subprocess.run(["pytest", "--cov=src", "--cov-report=json", "tests/"], capture_output=True)
    with open("coverage.json", "r") as f:
        return json.load(f)

def run_coverage_without_file(file_to_exclude: str) -> float:
    # Run coverage excluding the file to find unique coverage
    # Actually, a simpler approximation is used here:
    # We will just see if there's any lines hit ONLY by this file.
    # To do this accurately with pytest-cov requires --cov-context=test
    # But for this script we will use a simplified approach since context coverage requires pytest-cov context support.

    # We'll use pytest-cov context feature if possible, but fallback to running without the file and comparing total lines covered.

    # Run baseline
    # base_cov = run_coverage()

    # Move file temporarily
    tmp_path = file_to_exclude + ".bak"
    os.rename(file_to_exclude, tmp_path)

    try:
        subprocess.run(["pytest", "--cov=src", "--cov-report=json", "tests/"], capture_output=True)
        with open("coverage.json", "r") as f:
            cov_data = json.load(f)
            return cov_data.get("totals", {}).get("covered_lines", 0)
    finally:
        os.rename(tmp_path, file_to_exclude)


def map_imports(file_path: str) -> List[str]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("src."):
                        imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("src."):
                    imports.append(node.module)
        return imports
    except Exception:
        return []

def parse_ast_for_rot(file_path: str) -> tuple[float, bool]:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split('\n')
    loc = len(lines)

    # Count mock lines roughly
    mock_lines = sum(1 for line in lines if "mock(" in line or "spyOn(" in line or ".mockReturnValue(" in line or "Mock(" in line or "patch(" in line or "MagicMock(" in line or "AsyncMock(" in line)

    mock_density = mock_lines / max(1, loc)

    # Parse AST for tautologies
    try:
        tree = ast.parse(content)
    except Exception:
        return mock_density, False

    state = {'has_tautology': False}

    class TautologyVisitor(ast.NodeVisitor):
        def visit_Assert(self, node):
            # check if asserting a literal
            if isinstance(node.test, ast.Constant):
                state['has_tautology'] = True
            elif isinstance(node.test, ast.Compare):
                # check if comparing two constants like assert True == True
                if isinstance(node.test.left, ast.Constant) and len(node.test.comparators) == 1 and isinstance(node.test.comparators[0], ast.Constant):
                    if node.test.left.value == node.test.comparators[0].value:
                        state['has_tautology'] = True
            self.generic_visit(node)

    TautologyVisitor().visit(tree)

    return mock_density, state['has_tautology']

def get_critical_paths() -> List[str]:
    try:
        if os.path.exists("critical_paths.json"):
            with open("critical_paths.json", "r") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def estimate_token_cost(file_path: str) -> int:
    # rough approximation: 1 token = 4 chars
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return len(f.read()) // 4
    except Exception:
        return 0

def externalize_snapshots(file_path: str) -> bool:
    """Strategy A: The Bloat reducer"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)

        class SnapshotTransformer(ast.NodeTransformer):
            def __init__(self, file_path):
                self.modified = False
                self.snapshot_counter = 1
                self.file_path = file_path
                self.snapshots_dir = os.path.join(os.path.dirname(file_path), "snapshots")

            def visit_Dict(self, node):
                self.generic_visit(node)
                # Check if it's large enough (e.g. > 5 keys or token cost)
                if len(node.keys) > 3:
                    try:
                        # Attempt to evaluate to see if it's a pure literal
                        val = ast.literal_eval(node)

                        os.makedirs(self.snapshots_dir, exist_ok=True)
                        base_name = os.path.basename(self.file_path).replace('.py', '')
                        snap_name = f"{base_name}_snap_{self.snapshot_counter}.json"
                        snap_path = os.path.join(self.snapshots_dir, snap_name)

                        with open(snap_path, "w") as sf:
                            json.dump(val, sf, indent=2)

                        self.snapshot_counter += 1
                        self.modified = True

                        # Replace node with load_snapshot call
                        # Assuming a load_snapshot helper exists or we can just use json.load
                        # For simplicity, we inject: json.load(open('path/to/snap.json'))
                        new_node = ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id='json', ctx=ast.Load()),
                                attr='load',
                                ctx=ast.Load()
                            ),
                            args=[
                                ast.Call(
                                    func=ast.Name(id='open', ctx=ast.Load()),
                                    args=[
                                        ast.Call(
                                            func=ast.Attribute(
                                                value=ast.Attribute(
                                                    value=ast.Name(id='os', ctx=ast.Load()),
                                                    attr='path',
                                                    ctx=ast.Load()
                                                ),
                                                attr='join',
                                                ctx=ast.Load()
                                            ),
                                            args=[
                                                ast.Call(
                                                    func=ast.Attribute(
                                                        value=ast.Attribute(
                                                            value=ast.Name(id='os', ctx=ast.Load()),
                                                            attr='path',
                                                            ctx=ast.Load()
                                                        ),
                                                        attr='dirname',
                                                        ctx=ast.Load()
                                                    ),
                                                    args=[ast.Name(id='__file__', ctx=ast.Load())],
                                                    keywords=[]
                                                ),
                                                ast.Constant(value="snapshots"),
                                                ast.Constant(value=snap_name)
                                            ],
                                            keywords=[]
                                        ),
                                        ast.Constant(value="r")
                                    ],
                                    keywords=[]
                                )
                            ],
                            keywords=[]
                        )
                        return ast.copy_location(new_node, node)
                    except Exception:
                        pass
                return node

        transformer = SnapshotTransformer(file_path)
        new_tree = transformer.visit(tree)

        if transformer.modified:
            # We need to ensure json and os are imported
            imports_to_add = []
            has_json = any(isinstance(n, ast.Import) and any(alias.name == 'json' for alias in n.names) for n in new_tree.body)
            has_os = any(isinstance(n, ast.Import) and any(alias.name == 'os' for alias in n.names) for n in new_tree.body)

            if not has_json:
                imports_to_add.append(ast.Import(names=[ast.alias(name='json', asname=None)]))
            if not has_os:
                imports_to_add.append(ast.Import(names=[ast.alias(name='os', asname=None)]))

            if imports_to_add:
                new_tree.body = imports_to_add + new_tree.body

            ast.fix_missing_locations(new_tree)
            new_content = ast.unparse(new_tree)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return True

    except Exception as e:
        print(f"Error externalizing snapshots in {file_path}: {e}")
        return False
    return False

def delete_file(file_path: str):
    """Strategy B: The Liability Prune"""
    os.remove(file_path)

def quarantine_file(file_path: str):
    """Strategy C: The Quarantine"""
    Path("tests/quarantine").mkdir(parents=True, exist_ok=True)
    file_name = os.path.basename(file_path)
    os.rename(file_path, os.path.join("tests/quarantine", file_name))


def main():
    print("Starting Entropy Execution...")

    # Check guardrails
    critical_paths = get_critical_paths()

    # 1. Baseline Coverage
    base_cov = run_coverage()
    base_covered_lines = base_cov.get("totals", {}).get("covered_lines", 0)
    base_percent = base_cov.get("totals", {}).get("percent_covered", 0.0)

    print(f"Baseline Coverage: {base_percent:.2f}% ({base_covered_lines} lines)")

    # Get all test files
    test_files = [str(p) for p in Path("tests").rglob("test_*.py") if "quarantine" not in p.parts]

    verdicts: List[RotVerdict] = []

    # 2. Iterate through test files
    for tf in test_files:
        if tf.endswith(".md") or tf.endswith(".feature"):
            continue # Preserve Specs

        health = TestFileHealth(tf)
        health.is_critical_path = tf in critical_paths
        health.associated_source_files = map_imports(tf)
        health.churn_rate = get_git_churn(tf)
        health.token_cost = estimate_token_cost(tf)

        mock_density, has_tautology = parse_ast_for_rot(tf)
        health.mock_density = mock_density

        # Calculate unique coverage
        if health.is_critical_path:
            health.unique_coverage_lines = float('inf')
        else:
            excluded_lines = run_coverage_without_file(tf)
            health.unique_coverage_lines = base_covered_lines - excluded_lines

        verdict = RotVerdict(tf)
        verdict.unique_coverage_lines = health.unique_coverage_lines

        # Phase 2: Rot Scan
        if health.mock_density > MAX_MOCK_DENSITY:
            verdict.tags.append("BRITTLE_MOCKING")
        if health.token_cost > MAX_TOKEN_CONTEXT:
            verdict.tags.append("CONTEXT_BLOAT")
        if has_tautology:
            verdict.tags.append("TAUTOLOGY")

        # Calculate score (simple heuristic)
        verdict.score = (health.churn_rate * 5) + (health.mock_density * 50) + (10 if has_tautology else 0)

        # Phase 3: Verdict & Action
        if "CONTEXT_BLOAT" in verdict.tags:
            verdict.suggested_action = "COMPACT_SNAPSHOTS"
            verdict.rationale = f"Externalized snapshots. Token cost: {health.token_cost}"
        elif ("BRITTLE_MOCKING" in verdict.tags or "TAUTOLOGY" in verdict.tags) and health.unique_coverage_lines <= 0:
            verdict.suggested_action = "DELETE"
            verdict.rationale = f"0 Unique Coverage, tags: {','.join(verdict.tags)}"
        elif health.churn_rate > 5 and verdict.score > 30:
            verdict.suggested_action = "QUARANTINE"
            verdict.rationale = f"High Churn ({health.churn_rate}), Score ({verdict.score:.1f})"

        if verdict.suggested_action != "NONE":
            verdicts.append(verdict)

    # Guardrail: The Vibe Check
    actionable_verdicts = [v for v in verdicts if v.suggested_action in ("DELETE", "QUARANTINE")]
    if len(actionable_verdicts) > 20:
        print("VIBE CHECK FAILED: > 20 files flagged. Aborting.")
        with open("entropy_report.md", "w") as f:
            f.write("# [Entropy] Vibe Check Failed> 20 files were flagged for deletion/quarantine. Aborted to prevent catastrophic loss. Tag Lead Architect.")
        return

    # Execute Actions
    for v in verdicts:
        if v.suggested_action == "COMPACT_SNAPSHOTS":
            externalize_snapshots(v.file)
        elif v.suggested_action == "DELETE":
            delete_file(v.file)
        elif v.suggested_action == "QUARANTINE":
            quarantine_file(v.file)

    # Final Guardrail: Coverage Cliff
    final_cov = run_coverage()
    final_percent = final_cov.get("totals", {}).get("percent_covered", 0.0)

    if (base_percent - final_percent) > 0.5:
        print(f"COVERAGE CLIFF TRIGGERED: Drop from {base_percent:.2f}% to {final_percent:.2f}%. Reverting.")
        subprocess.run(["git", "restore", "."])
        subprocess.run(["git", "clean", "-fd"])
        with open("entropy_report.md", "w") as f:
            f.write(f"# [Entropy] Coverage Cliff TriggeredGlobal coverage dropped by more than 0.5% (from {base_percent:.2f}% to {final_percent:.2f}%). Actions reverted.")
        return

    # Generate Report
    report = "# [Entropy] Maintenance - Liability Reduction\n\n"
    report += "| File | Rot Type | Unique Coverage | Action Taken | Rationale |\n"
    report += "|---|---|---|---|---|\n"

    for v in verdicts:
        uc_str = "INF" if v.unique_coverage_lines == float('inf') else f"{int(v.unique_coverage_lines)} lines"
        report += f"| {v.file} | {', '.join(v.tags)} | {uc_str} | {v.suggested_action} | {v.rationale} |\n"

    with open("entropy_report.md", "w") as f:
        f.write(report)

    print("Entropy completed successfully.")

if __name__ == "__main__":
    main()

def parse_ast_for_rot(file_path: str) -> tuple[float, bool]:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split('\n')
    loc = len(lines)

    # Count mock lines roughly
    mock_lines = sum(1 for line in lines if "mock(" in line or "spyOn(" in line or ".mockReturnValue(" in line or "Mock(" in line or "patch(" in line or "MagicMock(" in line or "AsyncMock(" in line)

    mock_density = mock_lines / max(1, loc)

    # Parse AST for tautologies
    try:
        tree = ast.parse(content)
    except Exception:
        return mock_density, False

    state = {'has_tautology': False}

    class TautologyVisitor(ast.NodeVisitor):
        def visit_Assert(self, node):
            # check if asserting a literal
            if isinstance(node.test, ast.Constant):
                state['has_tautology'] = True
            elif isinstance(node.test, ast.Compare):
                # check if comparing two constants like assert True == True
                if isinstance(node.test.left, ast.Constant) and len(node.test.comparators) == 1 and isinstance(node.test.comparators[0], ast.Constant):
                    if node.test.left.value == node.test.comparators[0].value:
                        state['has_tautology'] = True
            self.generic_visit(node)

    TautologyVisitor().visit(tree)

    return mock_density, state['has_tautology']