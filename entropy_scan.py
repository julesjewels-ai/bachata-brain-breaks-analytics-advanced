import os
import json
import subprocess
import sys
import ast
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

def run_pytest_coverage():
    print("Running pytest with coverage...")
    subprocess.run([
        "pytest",
        "--cov=src",
        "--cov-report=json",
        "--cov-context=test"
    ], capture_output=True, text=True)
    subprocess.run([
        "coverage",
        "json",
        "--show-contexts"
    ], capture_output=True, text=True)

def parse_coverage_json() -> Tuple[Dict[str, int], float]:
    """Returns a dict mapping test file path to number of unique lines covered, and the overall global coverage percentage."""
    coverage_file = Path("coverage.json")
    if not coverage_file.exists():
        print("coverage.json not found.")
        return {}, 0.0

    with open(coverage_file, "r") as f:
        cov_data = json.load(f)

    global_coverage = cov_data.get("totals", {}).get("percent_statements_covered", 0.0)

    unique_coverage_lines: Dict[str, int] = defaultdict(int)

    for filename, file_data in cov_data.get("files", {}).items():
        contexts = file_data.get("contexts", {})
        for line_num, context_list in contexts.items():
            test_files_for_line = set()
            for ctx in context_list:
                if "|" in ctx:
                    ctx = ctx.split("|")[0]
                if "::" in ctx:
                    test_file = ctx.split("::")[0]
                    test_files_for_line.add(test_file)
                elif ctx.endswith(".py"):
                    test_files_for_line.add(ctx)

            if len(test_files_for_line) == 1:
                test_file = test_files_for_line.pop()
                unique_coverage_lines[test_file] += 1

    return dict(unique_coverage_lines), global_coverage

def get_test_files() -> List[Path]:
    return list(Path("tests").rglob("test_*.py"))

def map_test_to_source_files() -> Dict[str, List[str]]:
    """Maps test files to associated source files by import parsing."""
    test_to_source = defaultdict(list)
    src_files = [str(p) for p in Path("src").rglob("*.py") if p.is_file() and p.name != "__init__.py"]

    for test_file in get_test_files():
        try:
            with open(test_file, "r") as f:
                tree = ast.parse(f.read(), filename=str(test_file))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("src."):
                    module_parts = node.module.split(".")
                    src_path = "/".join(module_parts) + ".py"
                    if src_path in src_files:
                        test_to_source[str(test_file)].append(src_path)
    return dict(test_to_source)

def phase_1() -> Tuple[Dict[str, any], float]:
    run_pytest_coverage()
    unique_cov, global_cov = parse_coverage_json()
    test_to_src = map_test_to_source_files()

    health_metrics = {}
    for test_file in get_test_files():
        path_str = str(test_file)
        unique_lines = 0
        for k, v in unique_cov.items():
            if path_str in k:
                unique_lines += v

        health_metrics[path_str] = {
            "filePath": path_str,
            "associatedSourceFiles": test_to_src.get(path_str, []),
            "uniqueCoverageLines": unique_lines,
            "isCriticalPath": False # set later
        }
    return health_metrics, global_cov

def analyze_ast_for_rot(file_path: str) -> Dict[str, any]:
    with open(file_path, "r") as f:
        content = f.read()

    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError:
        return {"mockDensity": 0.0, "tokenCost": 0, "tautology": False, "loc": 0}

    lines = content.split("\n")
    loc = len(lines)

    token_cost = len(content) // 4

    mock_lines = set()
    tautology = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in ("Mock", "MagicMock", "patch", "spy"):
                mock_lines.add(node.lineno)

        # Also include `.return_value` and `.side_effect`
        if isinstance(node, ast.Attribute):
            if node.attr in ("return_value", "side_effect"):
                mock_lines.add(node.lineno)

        if isinstance(node, ast.Assert):
            if isinstance(node.test, ast.Compare):
                if isinstance(node.test.left, ast.Constant) and all(isinstance(c, ast.Constant) for c in node.test.comparators):
                    if len(node.test.comparators) == 1:
                        if getattr(node.test.left, "value", None) == getattr(node.test.comparators[0], "value", None):
                            tautology = True

            elif isinstance(node.test, ast.Constant):
                if node.test.value is True:
                    tautology = True

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ("assertTrue", "assertEqual"):
                    if node.func.attr == "assertTrue" and len(node.args) == 1 and isinstance(node.args[0], ast.Constant) and node.args[0].value is True:
                        tautology = True
                    if node.func.attr == "assertEqual" and len(node.args) == 2 and isinstance(node.args[0], ast.Constant) and isinstance(node.args[1], ast.Constant):
                        if node.args[0].value == node.args[1].value:
                            tautology = True

    mock_density = len(mock_lines) / loc if loc > 0 else 0.0

    return {
        "mockDensity": mock_density,
        "tokenCost": token_cost,
        "tautology": tautology,
        "loc": loc
    }

def get_churn_rate(file_path: str) -> int:
    try:
        result = subprocess.run([
            "git", "log", "--since=30.days.ago", "--format=%h", "--", file_path
        ], capture_output=True, text=True, check=True)
        return len([line for line in result.stdout.split("\n") if line.strip()])
    except Exception:
        return 0

def phase_2(health_metrics: Dict[str, any]):
    max_token_context = 2000
    max_mock_density = 0.55

    rot_verdicts = []

    for file_path, metrics in health_metrics.items():
        ast_metrics = analyze_ast_for_rot(file_path)
        metrics.update(ast_metrics)
        metrics["churnRate"] = get_churn_rate(file_path)

        tags = []
        if metrics["mockDensity"] > max_mock_density:
            tags.append("BRITTLE_MOCKING")
        if metrics["tokenCost"] > max_token_context:
            tags.append("CONTEXT_BLOAT")
        if metrics["tautology"]:
            tags.append("TAUTOLOGY")

        score = min(100, len(tags) * 33)

        action = "NONE"
        if metrics["churnRate"] > 5 and len(tags) > 0:
            action = "QUARANTINE"
        elif ("BRITTLE_MOCKING" in tags or "TAUTOLOGY" in tags) and metrics["uniqueCoverageLines"] == 0 and not metrics["isCriticalPath"]:
            action = "DELETE"
        elif "CONTEXT_BLOAT" in tags:
            action = "COMPACT_SNAPSHOTS"

        rot_verdicts.append({
            "file": file_path,
            "score": score,
            "tags": tags,
            "suggestedAction": action,
            "metrics": metrics
        })

    return rot_verdicts

def extract_snapshots(file_path: str):
    """Strategy A: Externalize Snapshots (large dicts/lists > 10 lines)."""
    with open(file_path, "r") as f:
        content = f.read()

    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError:
        return

    lines = content.split('\n')

    class LiteralExtractor(ast.NodeVisitor):
        def __init__(self):
            self.nodes_to_extract = []

        def visit_Dict(self, node):
            if hasattr(node, "end_lineno") and node.end_lineno - node.lineno > 10:
                self.nodes_to_extract.append(node)
            self.generic_visit(node)

        def visit_List(self, node):
            if hasattr(node, "end_lineno") and node.end_lineno - node.lineno > 10:
                self.nodes_to_extract.append(node)
            self.generic_visit(node)

    extractor = LiteralExtractor()
    extractor.visit(tree)

    if not extractor.nodes_to_extract:
        return

    # Create snapshot directory
    snapshot_dir = Path("tests/snapshots")
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    file_name = Path(file_path).stem

    # Process from bottom to top so line numbers don't change
    extractor.nodes_to_extract.sort(key=lambda n: n.lineno, reverse=True)

    new_lines = list(lines)
    snapshot_count = 0
    imports_needed = set()

    for idx, node in enumerate(extractor.nodes_to_extract):
        try:
            val = ast.literal_eval(node)
        except Exception:
            # Not a pure literal, can't easily externalize
            continue

        snapshot_count += 1
        snapshot_file = snapshot_dir / f"{file_name}_snap_{snapshot_count}.json"

        with open(snapshot_file, "w") as sf:
            json.dump(val, sf, indent=2)

        # Replace the node with a json.load call
        start_line = node.lineno - 1
        end_line = node.end_lineno

        # We need the indentation of the first line
        indent = len(lines[start_line]) - len(lines[start_line].lstrip())
        indent_str = " " * indent

        replacement = f"json.load(open('{snapshot_file}'))"

        # We need to replace only the exact columns if it's inline, but to simplify
        # we can replace the lines if it spans multiple lines. The problem is what if it's
        # x = {
        #   ...
        # }
        # Then ast gives lineno for { and end_lineno for }.
        # Doing exact string replacement by byte offset is safer but ast in 3.12 doesn't always have easy byte offsets.
        # Let's use ast.unparse ? No, unparse unparses the whole tree.
        # Actually we can do text replacement if we're careful.

        # More robust text replacement using col_offset
        start_col = node.col_offset
        end_col = node.end_col_offset

        if start_line == end_line - 1:
            # Same line
            new_lines[start_line] = new_lines[start_line][:start_col] + replacement + new_lines[start_line][end_col:]
        else:
            # Multi-line
            first_line = new_lines[start_line][:start_col] + replacement
            last_line = new_lines[end_line - 1][end_col:]

            # Remove intermediate lines
            del new_lines[start_line + 1 : end_line]

            new_lines[start_line] = first_line + last_line

        imports_needed.add("import json")

    if imports_needed:
        # insert import at top
        new_lines.insert(0, "import json")

    with open(file_path, "w") as f:
        f.write("\n".join(new_lines))


def delete_file(file_path: str):
    """Strategy B: Delete."""
    try:
        os.remove(file_path)
    except OSError:
        pass

def quarantine_file(file_path: str):
    """Strategy C: Quarantine."""
    quarantine_dir = Path("tests/quarantine")
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    file_path_obj = Path(file_path)
    dest = quarantine_dir / file_path_obj.name

    try:
        file_path_obj.rename(dest)
    except OSError:
        pass

    # Update .cursorignore
    cursorignore = Path(".cursorignore")
    if cursorignore.exists():
        with open(cursorignore, "r") as f:
            content = f.read()
    else:
        content = ""

    if "tests/quarantine/" not in content:
        with open(cursorignore, "a") as f:
            f.write("\ntests/quarantine/\n")

def phase_3(rot_verdicts: List[Dict[str, any]]):
    actions_taken = []

    for verdict in rot_verdicts:
        action = verdict["suggestedAction"]
        file_path = verdict["file"]

        if action == "COMPACT_SNAPSHOTS":
            extract_snapshots(file_path)
            actions_taken.append({**verdict, "actionTaken": "REFACTORED", "rationale": "Externalized JSON snapshots"})
        elif action == "DELETE":
            delete_file(file_path)
            actions_taken.append({**verdict, "actionTaken": "DELETED", "rationale": "Brittle/Tautology and 0 unique coverage"})
        elif action == "QUARANTINE":
            quarantine_file(file_path)
            actions_taken.append({**verdict, "actionTaken": "QUARANTINED", "rationale": "Moved to /quarantine to reduce AI context noise"})
        else:
            actions_taken.append({**verdict, "actionTaken": "NONE", "rationale": "Healthy"})

    return actions_taken


def load_critical_paths() -> Set[str]:
    critical_paths = set()
    cp_file = Path("critical_paths.json")
    if cp_file.exists():
        with open(cp_file, "r") as f:
            try:
                paths = json.load(f)
                for p in paths:
                    critical_paths.add(str(Path(p).resolve()))
            except Exception:
                pass
    return critical_paths

def phase_4(health_metrics: Dict[str, any], global_cov: float) -> str:
    # We must apply constraints before Phase 3 executes actions.
    # Wait, Phase 2 just generated verdicts, Phase 3 executes them.
    # So we need to orchestrate them in main().
    pass

def generate_report(actions_taken: List[Dict[str, any]]):
    report_lines = [
        "# [Entropy] Maintenance - Liability Reduction\n",
        "## Executed Actions\n",
        "| File | Rot Type | Unique Coverage | Action Taken | Rationale |",
        "|---|---|---|---|---|"
    ]

    for action in actions_taken:
        if action["actionTaken"] == "NONE":
            continue

        file_path = Path(action["file"]).name
        rot_type = ", ".join(action["tags"])
        unique_cov = f'{action["metrics"]["uniqueCoverageLines"]} lines'
        action_taken = action["actionTaken"]
        rationale = action["rationale"]

        report_lines.append(f"| {file_path} | {rot_type} | {unique_cov} | {action_taken} | {rationale} |")

    report = "\n".join(report_lines)
    with open("entropy_report.md", "w") as f:
        f.write(report)

    return report

def main():
    critical_paths = load_critical_paths()

    # Phase 1
    health_metrics, global_cov = phase_1()

    # Apply critical paths constraint
    for path_str, metric in health_metrics.items():
        if str(Path(path_str).resolve()) in critical_paths:
            metric["isCriticalPath"] = True

    # Phase 2
    verdicts = phase_2(health_metrics)

    # Operational Constraints Before Phase 3
    # 1. Vibe Check: > 20 files flagged
    flagged_count = sum(1 for v in verdicts if v["suggestedAction"] in ("DELETE", "QUARANTINE"))
    if flagged_count > 20:
        print("Vibe Check Failed: > 20 files flagged for Deletion/Quarantine. Aborting and tagging Lead Architect.")
        sys.exit(1)

    # 2. Preserve Specs (handled by getting only test_*.py in get_test_files())
    # 3. The Coverage Cliff: aborted if global coverage drops by > 0.5%
    # We estimate coverage cliff by sum of unique coverage lines of DELETED tests
    # global coverage = lines_covered / total_lines. We have unique coverage lines, and total percent.
    # Let's read coverage.json for exact lines.
    cov_file = Path("coverage.json")
    if cov_file.exists():
        with open(cov_file, "r") as f:
            cov_data = json.load(f)
            total_statements = cov_data.get("totals", {}).get("num_statements", 1)

        lines_lost = sum(v["metrics"]["uniqueCoverageLines"] for v in verdicts if v["suggestedAction"] == "DELETE")
        cov_drop = (lines_lost / total_statements) * 100

        if cov_drop > 0.5:
            print(f"Coverage Cliff Triggered: Estimated coverage drop of {cov_drop:.2f}% exceeds 0.5%. Aborting.")
            sys.exit(1)

    # Phase 3
    actions_taken = phase_3(verdicts)

    # Phase 4 Output
    generate_report(actions_taken)
    print("Entropy Scan complete. Report generated at entropy_report.md")

if __name__ == "__main__":
    main()
