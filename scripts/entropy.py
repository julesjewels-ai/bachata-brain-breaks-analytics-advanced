import ast
import json
import os
import subprocess
import logging
from typing import List, Literal, Optional, Dict, Set
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("entropy")

# Configuration for Entropy Protocol
class EntropyConfig(BaseModel):
    maxTokenContext: int = 2000
    maxMockDensity: float = 0.55
    minUniqueCoverageThreshold: int = 5
    executionMode: Literal['PR_SUGGESTION', 'REPORT_ONLY'] = 'PR_SUGGESTION'
    coverageCliffThreshold: float = 0.5
    vibeCheckMaxFiles: int = 20

entropyConfig = EntropyConfig()

# Domain Models
class TestFileHealth(BaseModel):
    filePath: str
    associatedSourceFiles: List[str] = Field(default_factory=list)
    loc: int = 0
    mockDensity: float = 0.0
    churnRate: int = 0
    tokenCost: int = 0
    uniqueCoverageLines: int = 0
    isCriticalPath: bool = False

class RotVerdict(BaseModel):
    file: str
    score: int
    tags: List[Literal['BRITTLE_MOCKING', 'CONTEXT_BLOAT', 'REDUNDANT_COVERAGE', 'TAUTOLOGY']]
    suggestedAction: Literal['QUARANTINE', 'COMPACT_SNAPSHOTS', 'DELETE', 'NONE']

def get_critical_paths() -> List[str]:
    if os.path.exists("critical_paths.json"):
        try:
            with open("critical_paths.json", "r") as f:
                data = json.load(f)
                return data.get("critical_paths", [])
        except Exception:
            pass
    return []

def get_test_files(tests_dir: str = "tests") -> List[str]:
    test_files = []
    for root, _, files in os.walk(tests_dir):
        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                test_files.append(os.path.join(root, file))
    return test_files

def map_import_graph() -> Dict[str, List[str]]:
    """Uses pydeps to map test files to the source files they import."""
    mapping = {}
    try:
        # pydeps requires graphviz and outputs json with --show-deps
        result = subprocess.run(
            ["pydeps", "--noshow", "--show-deps", "."],
            capture_output=True, text=True, check=False
        )
        if result.returncode == 0 and result.stdout:
            try:
                # The output might have other logs before the JSON, find the first '{'
                stdout = result.stdout
                start_idx = stdout.find('{')
                if start_idx != -1:
                    deps_data = json.loads(stdout[start_idx:])
                    for module_name, data in deps_data.items():
                        path = data.get("path", "")
                        if path and "tests/" in path and path.endswith(".py"):
                            # Normalize path relative to repo root
                            norm_path = os.path.relpath(path, start=os.getcwd())
                            imported = data.get("imports", [])
                            # Find matching source files for the imports
                            src_deps = []
                            for imp_mod in imported:
                                imp_data = deps_data.get(imp_mod, {})
                                imp_path = imp_data.get("path", "")
                                if imp_path and "src/" in imp_path:
                                    src_deps.append(os.path.relpath(imp_path, start=os.getcwd()))
                            mapping[norm_path] = src_deps
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse pydeps JSON output: {e}")
    except Exception as e:
        logger.error(f"Failed to run pydeps: {e}")
    return mapping

def calculate_unique_coverage(test_files: List[str]) -> Dict[str, Set[str]]:
    # 1. Run all tests first to get the global coverage and ensure tests pass
    subprocess.run(["python3", "-m", "pytest", "tests/", "--cov=src", "--cov-report=json", "--cov-report=term"], check=False)

    # 2. Iterate each test file to get its specific coverage lines
    coverage_map: Dict[str, Set[str]] = {}
    for test_file in test_files:
        logger.info(f"Running coverage for {test_file}")
        # Run pytest for the single file
        result = subprocess.run(["python3", "-m", "pytest", test_file, "--cov=src", "--cov-report=json"], capture_output=True, text=True)

        covered_lines = set()
        if os.path.exists("coverage.json"):
            with open("coverage.json", "r") as f:
                try:
                    cov_data = json.load(f)
                    files = cov_data.get("files", {})
                    for src_file, data in files.items():
                        # data.get('executed_lines') contains array of lines executed
                        lines = data.get("executed_lines", [])
                        for line in lines:
                            covered_lines.add(f"{src_file}:{line}")
                except Exception as e:
                    logger.error(f"Error parsing coverage for {test_file}: {e}")

        coverage_map[test_file] = covered_lines

    # Calculate unique coverage
    unique_coverage: Dict[str, int] = {}
    for test_file in test_files:
        current_lines = coverage_map.get(test_file, set())
        other_lines = set()
        for other_file, lines in coverage_map.items():
            if other_file != test_file:
                other_lines.update(lines)

        unique_lines = current_lines - other_lines
        unique_coverage[test_file] = len(unique_lines)

    return unique_coverage

def analyze_rot_patterns(test_file: str) -> Dict[str, any]:
    loc = 0
    mock_lines = 0
    token_cost = 0
    tautology_count = 0

    try:
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
            loc = len(lines)
            token_cost = len(content) // 4

            for line in lines:
                line = line.strip()
                if line.startswith("mock") or line.startswith("@patch") or "Mock(" in line or "MagicMock(" in line or ".return_value" in line:
                    mock_lines += 1

            # Simple AST parsing for tautologies
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assert):
                    if isinstance(node.test, ast.Constant):
                        tautology_count += 1
                    elif isinstance(node.test, ast.Compare):
                        # Example: assert True == True
                        if isinstance(node.test.left, ast.Constant) and len(node.test.comparators) == 1 and isinstance(node.test.comparators[0], ast.Constant):
                            if node.test.left.value == node.test.comparators[0].value:
                                tautology_count += 1
    except Exception as e:
        logger.error(f"Error analyzing AST for {test_file}: {e}")

    mock_density = mock_lines / loc if loc > 0 else 0

    # Git churn
    churn_rate = 0
    try:
        result = subprocess.run(["git", "log", "--since=30.days", "--oneline", "--", test_file], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout:
            churn_rate = len([line for line in result.stdout.strip().split('\n') if line])
    except Exception as e:
        logger.error(f"Error calculating churn for {test_file}: {e}")

    return {
        "loc": loc,
        "mockDensity": mock_density,
        "tokenCost": token_cost,
        "tautologyCount": tautology_count,
        "churnRate": churn_rate
    }

def get_global_coverage() -> float:
    subprocess.run(["python3", "-m", "pytest", "tests/", "--cov=src", "--cov-report=json"], capture_output=True, text=True, check=False)
    if os.path.exists("coverage.json"):
        try:
            with open("coverage.json", "r") as f:
                cov_data = json.load(f)
                return cov_data.get("totals", {}).get("percent_covered", 0.0)
        except Exception as e:
            logger.error(f"Error reading coverage.json for baseline: {e}")
    return 0.0

def run_entropy_protocol():
    logger.info("Starting Entropy Protocol...")
    test_files = get_test_files()
    critical_paths = get_critical_paths()

    # Calculate baseline coverage before any actions
    baseline_coverage = get_global_coverage()
    logger.info(f"Baseline Coverage: {baseline_coverage:.2f}%")

    import_mapping = map_import_graph()
    unique_coverage = calculate_unique_coverage(test_files)
    verdicts: List[RotVerdict] = []

    for test_file in test_files:
        health_data = analyze_rot_patterns(test_file)
        health_data["associatedSourceFiles"] = import_mapping.get(test_file, [])

        is_critical = any(cp in test_file for cp in critical_paths)
        unq_cov = unique_coverage.get(test_file, 0)
        if is_critical:
            unq_cov = float('inf') # Immune

        tags = []
        if health_data["mockDensity"] > entropyConfig.maxMockDensity:
            tags.append("BRITTLE_MOCKING")
        if health_data["tokenCost"] > entropyConfig.maxTokenContext:
            tags.append("CONTEXT_BLOAT")
        if health_data["tautologyCount"] > 0:
            tags.append("TAUTOLOGY")
        if unq_cov == 0 and not is_critical:
            tags.append("REDUNDANT_COVERAGE")

        action = "NONE"
        score = min(100, (len(tags) * 25) + (health_data["churnRate"] * 5))

        if "CONTEXT_BLOAT" in tags:
            action = "COMPACT_SNAPSHOTS"
        elif ("BRITTLE_MOCKING" in tags or "TAUTOLOGY" in tags) and unq_cov == 0:
            action = "DELETE"
        elif health_data["churnRate"] > 5 and score > 50:
            action = "QUARANTINE"

        verdicts.append(RotVerdict(
            file=test_file,
            score=score,
            tags=tags, # type: ignore
            suggestedAction=action # type: ignore
        ))

    # Guardrails: Vibe Check
    files_to_modify = [v for v in verdicts if v.suggestedAction in ["DELETE", "QUARANTINE"]]
    if len(files_to_modify) > entropyConfig.vibeCheckMaxFiles:
        logger.error(f"VIBE CHECK FAILED: {len(files_to_modify)} files flagged, exceeding limit of {entropyConfig.vibeCheckMaxFiles}. Aborting.")
        print("VIBE CHECK FAILED. @LeadArchitect review required.")
        return

    # Execute Actions
    quarantine_added = False
    for verdict in verdicts:
        if verdict.suggestedAction == "DELETE":
            logger.info(f"Deleting {verdict.file} (Liability Prune)")
            os.remove(verdict.file)
        elif verdict.suggestedAction == "QUARANTINE":
            logger.info(f"Quarantining {verdict.file}")
            os.makedirs("tests/quarantine", exist_ok=True)
            new_path = os.path.join("tests/quarantine", os.path.basename(verdict.file))
            os.rename(verdict.file, new_path)

            # Add to .gitignore
            if not quarantine_added:
                with open(".gitignore", "a+") as f:
                    f.seek(0)
                    content = f.read()
                    if "tests/quarantine/" not in content:
                        f.write("\ntests/quarantine/\n")
                quarantine_added = True

        elif verdict.suggestedAction == "COMPACT_SNAPSHOTS":
            logger.info(f"Compacting Snapshots for {verdict.file}")
            try:
                with open(verdict.file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Use AST to find large Dict or List in asserts/mock returns
                tree = ast.parse(content)
                snapshot_data = {}
                snapshot_id = 0

                class SnapshotTransformer(ast.NodeTransformer):
                    def visit_Dict(self, node):
                        self.generic_visit(node)
                        # Check if dict is "large" based on rough line count in original text, but we'll approximate with AST complexity
                        if len(node.keys) > 10:  # arbitrary threshold for "large"
                            nonlocal snapshot_id
                            key_name = f"snapshot_{snapshot_id}"
                            try:
                                val = ast.literal_eval(node)
                                snapshot_data[key_name] = val
                                snapshot_id += 1
                                # Return replacement code: snapshot_data['snapshot_X']
                                return ast.Subscript(
                                    value=ast.Name(id='_snapshot_data', ctx=ast.Load()),
                                    slice=ast.Constant(value=key_name),
                                    ctx=ast.Load()
                                )
                            except ValueError:
                                pass # not a literal dict
                        return node

                transformer = SnapshotTransformer()
                new_tree = transformer.visit(tree)

                if snapshot_data:
                    # Write snapshots to file
                    snap_dir = os.path.join(os.path.dirname(verdict.file), "snapshots")
                    os.makedirs(snap_dir, exist_ok=True)
                    snap_file = os.path.join(snap_dir, os.path.basename(verdict.file).replace('.py', '.json'))

                    with open(snap_file, 'w', encoding='utf-8') as f:
                        json.dump(snapshot_data, f, indent=2)

                    # We would need to unparse and add the loading logic at the top of the file.
                    # ast.unparse is available in Python 3.9+
                    try:
                        new_code = ast.unparse(new_tree)
                        # Inject loading code
                        load_code = f"import json\nimport os\nwith open(os.path.join(os.path.dirname(__file__), 'snapshots', '{os.path.basename(snap_file)}')) as _f:\n    _snapshot_data = json.load(_f)\n\n"
                        with open(verdict.file, 'w', encoding='utf-8') as f:
                            f.write(load_code + new_code)
                        logger.info(f"Successfully compacted {len(snapshot_data)} snapshots for {verdict.file}")
                    except Exception as unparse_e:
                        logger.error(f"Failed to unparse AST for {verdict.file}: {unparse_e}")
                else:
                    logger.info(f"No large snapshots found to compact in {verdict.file}")
            except Exception as e:
                logger.error(f"Failed to compact snapshots for {verdict.file}: {e}")

    # Guardrail: Coverage Cliff
    logger.info("Running final coverage check...")
    final_coverage = get_global_coverage()
    logger.info(f"Final Coverage: {final_coverage:.2f}%")

    if (baseline_coverage - final_coverage) > entropyConfig.coverageCliffThreshold:
        logger.error(f"COVERAGE CLIFF FAILED: Coverage dropped by {baseline_coverage - final_coverage:.2f}% (Threshold: {entropyConfig.coverageCliffThreshold}%). Rolling back changes.")
        print("COVERAGE CLIFF FAILED. Rolling back.")
        subprocess.run(["git", "restore", "tests/"], check=False)
        subprocess.run(["git", "restore", "scripts/"], check=False)
        return

    # Generate Output
    print("## Entropy Protocol: Liability Reduction Report")
    print("| File | Rot Type | Unique Coverage | Action Taken | Rationale |")
    print("|---|---|---|---|---|")
    for v in verdicts:
        if v.suggestedAction != "NONE":
            unq = unique_coverage.get(v.file, 0)
            if any(cp in v.file for cp in critical_paths): unq = "Immune"
            print(f"| {v.file} | {', '.join(v.tags)} | {unq} lines | {v.suggestedAction} | Score {v.score} |")

if __name__ == "__main__":
    run_entropy_protocol()
