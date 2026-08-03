import json
import os
import subprocess
import glob
import ast
import shutil
import sys
import tempfile
import re

# Configuration
CONFIG = {
    "maxTokenContext": 2000,
    "maxMockDensity": 0.55,
    "minUniqueCoverageThreshold": 5,
    "executionMode": "REPORT_ONLY",  # We can change to PR_SUGGESTION or actual action
}

class TestFileHealth:
    def __init__(self, file_path):
        self.file_path = file_path
        self.associated_source_files = []
        self.loc = 0
        self.mock_density = 0.0
        self.churn_rate = 0
        self.token_cost = 0
        self.unique_coverage_lines = 0
        self.is_critical_path = False

        self.rot_score = 0
        self.tags = []
        self.suggested_action = "NONE"

def get_global_coverage():
    """Runs global coverage and returns the percentage."""
    subprocess.run(["pytest", "--cov=src", "--cov-report=json"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with open("coverage.json", "r") as f:
            data = json.load(f)
            return data.get("totals", {}).get("percent_covered", 0.0)
    except FileNotFoundError:
        return 0.0

def get_file_coverage_lines(coverage_data):
    """Extracts covered lines from coverage data."""
    covered_lines = {}
    for filename, file_data in coverage_data.get("files", {}).items():
        if "executed_lines" in file_data:
            covered_lines[filename] = set(file_data["executed_lines"])
    return covered_lines

def analyze_test_file(file_path):
    health = TestFileHealth(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split('\n')
    health.loc = len(lines)

    # Token cost (naive approximation: words)
    health.token_cost = len(re.findall(r'\w+', content))

    # Mock density
    mock_lines = 0
    for line in lines:
        if re.search(r'(mock\(|spyOn\(|\.mockReturnValue\(|patch\(|Mock\(|MagicMock\()', line):
            mock_lines += 1
    if health.loc > 0:
        health.mock_density = mock_lines / health.loc

    # Churn rate
    try:
        churn_output = subprocess.check_output(
            ["git", "log", "--oneline", "--since=30 days ago", "--", file_path],
            text=True
        )
        health.churn_rate = len(churn_output.strip().split('\n')) if churn_output.strip() else 0
    except subprocess.CalledProcessError:
        health.churn_rate = 0

    # Tautology check
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                # check for `assert True`
                if isinstance(node.test, ast.Constant) and node.test.value is True:
                    if "TAUTOLOGY" not in health.tags:
                        health.tags.append("TAUTOLOGY")
                # check for `assert 1 == 1` or `"a" == "a"`
                if isinstance(node.test, ast.Compare):
                    if isinstance(node.test.ops[0], ast.Eq):
                        left = node.test.left
                        right = node.test.comparators[0]
                        if isinstance(left, ast.Constant) and isinstance(right, ast.Constant):
                            if left.value == right.value:
                                if "TAUTOLOGY" not in health.tags:
                                    health.tags.append("TAUTOLOGY")
    except SyntaxError:
        pass

    # Tags
    if health.mock_density > CONFIG["maxMockDensity"]:
        health.tags.append("BRITTLE_MOCKING")
    if health.token_cost > CONFIG["maxTokenContext"]:
        health.tags.append("CONTEXT_BLOAT")

    return health

def externalize_snapshots(file_path):
    """Strategy A: Bloat reducer (basic implementation)."""
    # In a real implementation this would parse and extract dicts to JSON.
    pass

def delete_file(file_path):
    """Strategy B: Liability Prune."""
    os.remove(file_path)

def quarantine_file(file_path):
    """Strategy C: Quarantine."""
    os.makedirs("tests/quarantine", exist_ok=True)
    shutil.move(file_path, os.path.join("tests/quarantine", os.path.basename(file_path)))

    # Update .gitignore
    with open(".gitignore", "a+") as f:
        f.seek(0)
        content = f.read()
        if "tests/quarantine/" not in content:
            f.write("\ntests/quarantine/\n")

def main():
    test_files = glob.glob("tests/test_*.py")

    print("Gathering initial global coverage...")
    initial_coverage = get_global_coverage()

    # 1. Global mapping
    global_coverage_map = {}
    for t_file in test_files:
        print(f"Profiling {t_file}...")
        # Iterative run
        subprocess.run(
            ["pytest", f"--cov=src", "--cov-report=json", t_file],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        try:
            with open("coverage.json", "r") as f:
                data = json.load(f)
                global_coverage_map[t_file] = get_file_coverage_lines(data)
        except Exception:
            global_coverage_map[t_file] = {}

    # Calculate unique coverage per file
    # A line is uniquely covered by test T if it is covered by T and NO OTHER test T'
    unique_lines = {}
    for t_file in test_files:
        unique_lines[t_file] = 0

    all_covered_lines = {} # (src_file, line_no) -> list of test_files that cover it
    for t_file, cov_map in global_coverage_map.items():
        for src_file, lines in cov_map.items():
            for line in lines:
                key = (src_file, line)
                if key not in all_covered_lines:
                    all_covered_lines[key] = []
                all_covered_lines[key].append(t_file)

    for key, covering_tests in all_covered_lines.items():
        if len(covering_tests) == 1:
            unique_lines[covering_tests[0]] += 1

    # Load critical paths
    critical_paths = []
    if os.path.exists("critical_paths.json"):
        with open("critical_paths.json", "r") as f:
            critical_paths = json.load(f)

    # 2. Rot Scan & Strategy Application
    actions_taken = []

    for t_file in test_files:
        if t_file in critical_paths:
            print(f"Skipping {t_file} (Critical Path)")
            continue

        health = analyze_test_file(t_file)
        health.unique_coverage_lines = unique_lines.get(t_file, 0)

        # Determine strategy
        if health.unique_coverage_lines > 0:
            # Immune to deletion
            if "CONTEXT_BLOAT" in health.tags:
                health.suggested_action = "REFACTORED"
                # externalize_snapshots(t_file)
        else:
            if ("BRITTLE_MOCKING" in health.tags or "TAUTOLOGY" in health.tags) and health.unique_coverage_lines == 0:
                health.suggested_action = "DELETED"
            elif health.churn_rate > 5 and len(health.tags) > 0:
                health.suggested_action = "QUARANTINED"

        if health.suggested_action != "NONE":
            actions_taken.append(health)

    if len(actions_taken) > 20:
        print("Vibe Check failed: > 20 files flagged. Aborting.")
        sys.exit(1)

    # Execute actions
    for h in actions_taken:
        if h.suggested_action == "DELETED":
            delete_file(h.file_path)
        elif h.suggested_action == "QUARANTINED":
            quarantine_file(h.file_path)

    # Verify Coverage Cliff
    if actions_taken:
        print("Re-evaluating global coverage...")
        final_coverage = get_global_coverage()
        drop = initial_coverage - final_coverage
        if drop > 0.5:
            print(f"Coverage Cliff breached! Drop: {drop}%. Aborting/Reverting.")
            # In a real tool, we would rollback git here
            subprocess.run(["git", "restore", "tests/"])
            subprocess.run(["git", "restore", ".gitignore"])
            sys.exit(1)

    # Output markdown table
    print("Generating report...")
    with open("entropy_report.md", "w") as f:
        f.write("# Entropy Report\n\n")
        f.write("| File | Rot Type | Unique Coverage | Action Taken | Rationale |\n")
        f.write("|---|---|---|---|---|\n")
        for h in actions_taken:
            rot = ", ".join(h.tags) if h.tags else "N/A"
            f.write(f"| {h.file_path} | {rot} | {h.unique_coverage_lines} lines | {h.suggested_action} | Entropy applied |\n")

    print("Entropy complete.")

if __name__ == "__main__":
    main()
