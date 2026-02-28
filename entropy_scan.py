import os
import json
import ast
import subprocess
import shutil

MAX_TOKEN_CONTEXT = 2000
MAX_MOCK_DENSITY = 0.55
MIN_UNIQUE_COVERAGE_THRESHOLD = 5

def run_cmd(cmd):
    return subprocess.check_output(cmd, shell=True, text=True)

def get_churn(filepath):
    try:
        out = run_cmd(f'git log --oneline --since="30 days ago" "{filepath}"')
        return len([line for line in out.strip().split('\n') if line])
    except subprocess.CalledProcessError:
        return 0

def get_critical_paths():
    try:
        with open("critical_paths.json", "r") as f:
            paths = json.load(f)
        return [os.path.abspath(p) for p in paths]
    except FileNotFoundError:
        return []

def generate_coverage():
    print("Running tests with coverage...")
    try:
        run_cmd("pytest --cov=src --cov-report=json --cov-context=test")
    except subprocess.CalledProcessError as e:
        print(f"Tests failed, but proceeding with coverage: {e}")
    try:
        run_cmd("coverage json --show-contexts")
    except subprocess.CalledProcessError as e:
        print(f"Coverage json failed: {e}")

def get_global_coverage():
    try:
        with open("coverage.json", "r") as f:
            cov_data = json.load(f)
        return cov_data.get("totals", {}).get("percent_covered", 0)
    except Exception:
        return 0

def parse_unique_coverage():
    unique_cov = {}
    try:
        with open("coverage.json", "r") as f:
            cov_data = json.load(f)
    except FileNotFoundError:
        return unique_cov

    line_contexts = {}

    for src_file, file_data in cov_data.get("files", {}).items():
        contexts = file_data.get("contexts", {})
        line_contexts[src_file] = {}
        for line, ctxs in contexts.items():
            valid_tests = set()
            for ctx in ctxs:
                if ctx and "|" in ctx:
                    test_name = ctx.split("|")[0]
                    test_file = test_name.split("::")[0]
                    if os.path.exists(test_file):
                        valid_tests.add(os.path.abspath(test_file))

            # If the only contexts are empty string (module load) and tests,
            # then we only count it as tested if there's at least one test.
            if valid_tests:
                line_contexts[src_file][line] = valid_tests

    for src_file, lines in line_contexts.items():
        for line, tests in lines.items():
            if len(tests) == 1:
                test_file = list(tests)[0]
                unique_cov[test_file] = unique_cov.get(test_file, 0) + 1

    return unique_cov

class TestAnalyzer(ast.NodeVisitor):
    def __init__(self, filepath):
        self.filepath = filepath
        with open(filepath, "r", encoding="utf-8") as f:
            self.source = f.read()
        self.lines = self.source.split('\n')
        self.tree = ast.parse(self.source)

        self.mock_calls = 0
        self.tautologies = 0
        self.large_literals = []

        # Count mock lines manually for mock density
        self.mock_lines = 0
        for line in self.lines:
            stripped = line.strip()
            if stripped.startswith('mock(') or stripped.startswith('spyOn(') or '.mockReturnValue(' in stripped:
                self.mock_lines += 1
            elif 'Mock(' in stripped or 'MagicMock(' in stripped or 'patch(' in stripped or 'Mock' in stripped or 'mock' in stripped or 'patch' in stripped or 'spy' in stripped:
                self.mock_lines += 1
            elif 'spy(' in stripped or 'AsyncMock(' in stripped:
                self.mock_lines += 1
        self.imported_src = []

        self.total_lines = len(self.lines)
        self.token_cost = len(self.source) // 4

    def analyze(self):
        self.visit(self.tree)

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name.startswith("src"):
                self.imported_src.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module and node.module.startswith("src"):
            self.imported_src.append(node.module)
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id in ["Mock", "MagicMock", "spy", "patch"]:
                self.mock_calls += 1
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in ["Mock", "MagicMock", "patch", "spy"]:
                self.mock_calls += 1
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name) and dec.id == "patch":
                self.mock_calls += 1
            elif isinstance(dec, ast.Call) and getattr(dec.func, "id", "") == "patch":
                self.mock_calls += 1
            elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr == "patch":
                self.mock_calls += 1
        self.generic_visit(node)

    def visit_Assert(self, node):
        if isinstance(node.test, ast.Constant):
            self.tautologies += 1
        elif isinstance(node.test, ast.Compare):
            if isinstance(node.test.left, ast.Constant) and all(isinstance(comp, ast.Constant) for comp in node.test.comparators):
                self.tautologies += 1
        self.generic_visit(node)

    def visit_Dict(self, node):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            if node.end_lineno - node.lineno > 10:
                self.large_literals.append((node.lineno, node.end_lineno, "dict", node))
        self.generic_visit(node)

    def visit_List(self, node):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            if node.end_lineno - node.lineno > 10:
                self.large_literals.append((node.lineno, node.end_lineno, "list", node))
        self.generic_visit(node)

def externalize_snapshots(filepath, large_literals):
    os.makedirs("tests/snapshots", exist_ok=True)
    with open(filepath, "r", encoding="utf-8") as f:
        source_code = f.read()

    large_literals.sort(key=lambda x: x[0], reverse=True)

    modified = False
    source_lines = source_code.split('\n')

    for lineno, end_lineno, lit_type, node in large_literals:
        try:
            segment = ast.get_source_segment(source_code, node)
            if not segment: continue

            val = ast.literal_eval(segment)
            snapshot_name = f"{os.path.basename(filepath).split('.')[0]}_{lineno}.json"
            snapshot_path = os.path.join("tests/snapshots", snapshot_name)
            with open(snapshot_path, "w", encoding="utf-8") as sf:
                json.dump(val, sf, indent=2)

            inline_replace = f"json.load(open('{snapshot_path}'))"

            start_line = source_lines[lineno-1]
            end_line = source_lines[end_lineno-1]

            prefix = start_line[:node.col_offset]
            suffix = end_line[node.end_col_offset:]

            if lineno == end_lineno:
                source_lines[lineno-1] = prefix + inline_replace + suffix
            else:
                source_lines[lineno-1] = prefix + inline_replace + suffix
                for i in range(lineno, end_lineno):
                    source_lines[i] = None

            # re-join to update source_code for subsequent get_source_segment calls?
            # actually get_source_segment uses the original source_code
            # since we iterate bottom-to-top, line indices above the current change are unaffected
            modified = True

        except Exception:
            pass

    if modified:
        source_lines = [line for line in source_lines if line is not None]
        if not any("import json" in line for line in source_lines[:20]):
            source_lines.insert(0, "import json")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write('\n'.join(source_lines))

def run_scan():
    generate_coverage()
    unique_cov = parse_unique_coverage()
    initial_coverage = get_global_coverage()
    critical_paths = get_critical_paths()

    actions = []

    test_files = []
    for root, _, files in os.walk("tests"):
        if "quarantine" in root or "snapshots" in root:
            continue
        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                test_files.append(os.path.join(root, file))

    deletion_count = 0
    quarantine_count = 0

    for filepath in test_files:
        abs_path = os.path.abspath(filepath)
        try:
            analyzer = TestAnalyzer(filepath)
            analyzer.analyze()
        except Exception as e:
            print(f"Failed to analyze {filepath}: {e}")
            continue

        mock_density = analyzer.mock_lines / max(analyzer.total_lines, 1)
        churn = get_churn(filepath)
        token_cost = analyzer.token_cost

        rot_tags = []
        # Update MAX_MOCK_DENSITY threshold calculation slightly for test stability if needed
        # Actually just relying on the configured threshold
        if mock_density > MAX_MOCK_DENSITY:
            rot_tags.append("BRITTLE_MOCKING")
        if token_cost > MAX_TOKEN_CONTEXT:
            rot_tags.append("CONTEXT_BLOAT")
        if analyzer.tautologies > 0:
            rot_tags.append("TAUTOLOGY")

        unique_lines = unique_cov.get(abs_path, 0)
        is_immune = unique_lines > 0 or abs_path in critical_paths

        rot_score = len(rot_tags) * 33

        action = "NONE"
        rationale = ""
        rot_type_str = ", ".join(rot_tags) if rot_tags else "NONE"

        # Verify import mapping logic. Phase 1 says map via import graph.
        # Ensure test has an import from src.
        has_src_import = bool(analyzer.imported_src)

        if "CONTEXT_BLOAT" in rot_tags and analyzer.large_literals:
            action = "SNAPSHOTS"
            rationale = f"Externalized {len(analyzer.large_literals)} large literals"
        elif ("BRITTLE_MOCKING" in rot_tags or "TAUTOLOGY" in rot_tags) and unique_lines == 0 and not is_immune:
            action = "DELETE"
            rationale = f"Liability: 0 unique coverage, tags: {rot_type_str}"
            deletion_count += 1
        elif not has_src_import and not is_immune:
            # Phase 1 says Map Files via import graph: "If auth.test.ts imports auth.ts, they are linked."
            # A test file not importing from 'src' provides no valid coverage map
            # Unless it is in critical paths
            pass
        elif churn > 5 and rot_score > 0:
            action = "QUARANTINE"
            rationale = f"High churn ({churn}) & rot. Moved to quarantine"
            quarantine_count += 1

        if action != "NONE":
            actions.append({
                "File": filepath,
                "Rot Type": rot_type_str,
                "Unique Coverage": str(unique_lines) if not is_immune else "IMMUNE",
                "Action Taken": action,
                "Rationale": rationale,
                "Analyzer": analyzer
            })

    if deletion_count + quarantine_count > 20:
        print("VIBE CHECK FAILED: > 20 files flagged for Deletion/Quarantine. Aborting.")
        return

    # Apply actions temporarily to check Coverage Cliff
    # Actually, we can move files, check coverage, and revert if failed
    backed_up = []

    for a in actions:
        filepath = a["File"]
        action = a["Action Taken"]
        analyzer = a["Analyzer"]

        if action == "SNAPSHOTS":
            # Snapshot externalization doesn't delete tests, so it shouldn't affect coverage
            externalize_snapshots(filepath, analyzer.large_literals)
        elif action == "DELETE":
            backup_path = filepath + ".bak"
            shutil.copy2(filepath, backup_path)
            backed_up.append((filepath, backup_path))
            os.remove(filepath)
        elif action == "QUARANTINE":
            backup_path = filepath + ".bak"
            shutil.copy2(filepath, backup_path)
            backed_up.append((filepath, backup_path))
            os.makedirs("tests/quarantine", exist_ok=True)
            shutil.move(filepath, os.path.join("tests/quarantine", os.path.basename(filepath)))

    # Check Coverage Cliff
    if backed_up:
        print("Checking Coverage Cliff...")
        generate_coverage()
        new_coverage = get_global_coverage()

        if initial_coverage - new_coverage > 0.5:
            print(f"COVERAGE CLIFF FAILED: Coverage dropped from {initial_coverage}% to {new_coverage}%. Reverting...")
            for orig_path, bak_path in backed_up:
                quarantine_path = os.path.join("tests/quarantine", os.path.basename(orig_path))
                if os.path.exists(quarantine_path):
                    shutil.move(quarantine_path, orig_path)
                elif not os.path.exists(orig_path) and os.path.exists(bak_path):
                    shutil.move(bak_path, orig_path)
            for _, bak_path in backed_up:
                if os.path.exists(bak_path):
                    os.remove(bak_path)
            return

        # If passed, cleanup backups
        for _, bak_path in backed_up:
            if os.path.exists(bak_path):
                os.remove(bak_path)

    with open("entropy_report.md", "w", encoding="utf-8") as f:
        f.write("# [Entropy] Maintenance - Liability Reduction\n\n")
        f.write("| File | Rot Type | Unique Coverage | Action Taken | Rationale |\n")
        f.write("|---|---|---|---|---|\n")
        for a in actions:
            f.write(f"| {a['File']} | {a['Rot Type']} | {a['Unique Coverage']} | {a['Action Taken']} | {a['Rationale']} |\n")

if __name__ == '__main__':
    run_scan()
