#!/usr/bin/env python3
"""
Entropy: Automation for Repository Sanitation & De-inflation.
"""
import ast
import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("entropy")

# Configuration
MAX_TOKEN_CONTEXT = 2000
MAX_MOCK_DENSITY = 0.55
MIN_UNIQUE_COVERAGE = 5
EXECUTION_MODE = 'PR_SUGGESTION' # 'PR_SUGGESTION' or 'REPORT_ONLY'
CRITICAL_PATHS_FILE = "critical_paths.json"
QUARANTINE_DIR = "tests/quarantine"
REPORT_FILE = "entropy_report.md"

@dataclass
class TestFileHealth:
    file_path: str
    loc: int = 0
    mock_density: float = 0.0
    churn_rate: int = 0
    token_cost: int = 0
    unique_coverage_lines: int = 0
    is_critical_path: bool = False
    associated_source_files: List[str] = field(default_factory=list)

@dataclass
class RotVerdict:
    file_path: str
    score: float = 0.0
    tags: List[str] = field(default_factory=list)
    suggested_action: str = "NONE"

class Entropy:
    def __init__(self):
        self.files_health: Dict[str, TestFileHealth] = {}
        self.verdicts: Dict[str, RotVerdict] = {}
        self.critical_paths = self._load_critical_paths()

    def _load_critical_paths(self) -> List[str]:
        if os.path.exists(CRITICAL_PATHS_FILE):
            with open(CRITICAL_PATHS_FILE, 'r') as f:
                return json.load(f)
        return []

    def get_git_churn(self, filepath: str) -> int:
        """Counts commits in the last 30 days for a file."""
        try:
            cmd = [
                "git", "log", "--oneline", "--since=30.days.ago", "--", filepath
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return len(result.stdout.strip().splitlines())
        except subprocess.CalledProcessError:
            logger.warning(f"Could not get git churn for {filepath}")
            return 0
        except FileNotFoundError:
            # git not installed?
            return 0

    def analyze_file_metrics(self, filepath: str) -> TestFileHealth:
        with open(filepath, 'r') as f:
            content = f.read()

        lines = content.splitlines()
        loc = len([l for l in lines if l.strip() and not l.strip().startswith('#')])

        # Mock Density
        mock_lines = 0
        for line in lines:
            stripped = line.strip()
            if (stripped.startswith("mock") or
                stripped.startswith("patch") or
                "MagicMock" in stripped or
                "unittest.mock" in stripped or
                stripped.startswith("@patch")):
                mock_lines += 1

        mock_density = mock_lines / loc if loc > 0 else 0.0

        # Token Cost (Approx 4 chars per token)
        token_cost = len(content) / 4

        # Churn
        churn = self.get_git_churn(filepath)

        # Critical Path Check
        is_critical = filepath in self.critical_paths

        return TestFileHealth(
            file_path=filepath,
            loc=loc,
            mock_density=mock_density,
            churn_rate=churn,
            token_cost=int(token_cost),
            is_critical_path=is_critical
        )

    def _run_coverage(self, ignore_files: Optional[List[str]] = None) -> Set[Tuple[str, int]]:
        """Runs coverage and returns a set of (file, line) tuples covered."""
        cmd = ["coverage", "run", "--source=src", "-m", "pytest"]
        if ignore_files:
            for f in ignore_files:
                cmd.append(f"--ignore={f}")

        # Suppress output for cleaner logs
        subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Generate JSON report
        try:
            subprocess.run(["coverage", "json", "-o", "coverage.json"], check=True, stdout=subprocess.DEVNULL)
            with open("coverage.json", "r") as f:
                data = json.load(f)

            covered_lines = set()
            for filename, file_data in data["files"].items():
                for line_num in file_data["executed_lines"]:
                    covered_lines.add((filename, line_num))
            return covered_lines
        except Exception as e:
            logger.error(f"Coverage run failed: {e}")
            return set()

    def calculate_unique_coverage(self):
        """Calculates unique coverage for each test file."""
        logger.info("Calculating unique coverage (this may take a while)...")

        # 1. Full Coverage
        self.full_coverage_lines = self._run_coverage()
        logger.info(f"Full suite coverage: {len(self.full_coverage_lines)} lines.")

        # 2. Per-file exclusion
        for filepath, health in self.files_health.items():
            # Skip if critical path (save time, assume infinite unique coverage)
            if health.is_critical_path:
                logger.info(f"Skipping coverage check for critical path: {filepath}")
                health.unique_coverage_lines = 9999
                continue

            subset_coverage = self._run_coverage(ignore_files=[filepath])
            unique_lines = self.full_coverage_lines - subset_coverage
            health.unique_coverage_lines = len(unique_lines)
            logger.info(f"Unique coverage for {filepath}: {len(unique_lines)} lines.")

    def scan_tests(self):
        """Scans all test files for metrics."""
        test_dir = "tests"
        test_files_found = []
        for root, _, files in os.walk(test_dir):
            if "quarantine" in root:
                continue
            for file in files:
                if file.startswith("test_") and file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    test_files_found.append(filepath)

        for filepath in test_files_found:
            health = self.analyze_file_metrics(filepath)
            self.files_health[filepath] = health
            logger.info(f"Analyzed {filepath}: LOC={health.loc}, MockDensity={health.mock_density:.2f}")

        self.calculate_unique_coverage()
        self.apply_verdicts()
        self.generate_report()

    def check_tautology(self, filepath: str) -> bool:
        """Checks for tautological assertions using AST."""
        try:
            with open(filepath, "r") as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.Assert):
                    # assert True
                    if isinstance(node.test, ast.Constant) and node.test.value is True:
                        return True
                    # assert 1 == 1
                    if isinstance(node.test, ast.Compare):
                        if (isinstance(node.test.left, ast.Constant) and
                            len(node.test.comparators) == 1 and
                            isinstance(node.test.comparators[0], ast.Constant) and
                            node.test.left.value == node.test.comparators[0].value):
                            return True
            return False
        except Exception:
            return False

    def detect_rot(self, health: TestFileHealth) -> RotVerdict:
        verdict = RotVerdict(file_path=health.file_path)
        tags = []
        score = 0

        # 1. Mock Abuse
        if health.mock_density > MAX_MOCK_DENSITY:
            tags.append("BRITTLE_MOCKING")
            score += 40

        # 2. Context Bloat
        if health.token_cost > MAX_TOKEN_CONTEXT:
            tags.append("CONTEXT_BLOAT")
            score += 30

        # 3. Tautology
        if self.check_tautology(health.file_path):
            tags.append("TAUTOLOGY")
            score += 20

        # 4. High Churn
        if health.churn_rate > 5:
            tags.append("HIGH_CHURN")
            score += 10

        verdict.tags = tags
        verdict.score = score

        # Strategy Selection
        # Strategy B: Liability Prune
        if (("BRITTLE_MOCKING" in tags or "TAUTOLOGY" in tags) and
            health.unique_coverage_lines == 0):
            verdict.suggested_action = "DELETE"

        # Strategy A: Bloat Reducer
        elif "CONTEXT_BLOAT" in tags:
            # We prefer Refactor over Quarantine for Bloat
            verdict.suggested_action = "REFACTOR"

        # Strategy C: Quarantine
        elif "HIGH_CHURN" in tags and score > 50:
            verdict.suggested_action = "QUARANTINE"

        else:
            verdict.suggested_action = "NONE"

        return verdict

    def verify_safety(self, files_to_delete: List[str]) -> bool:
        """Checks if deleting these files violates the coverage cliff (< 0.5% drop)."""
        if not files_to_delete:
            return True

        logger.info(f"Verifying safety for deleting {len(files_to_delete)} files...")

        # Check Vibe Check (> 20 files)
        if len(files_to_delete) > 20:
            logger.error(f"VIBE CHECK FAILED: Too many files flagged for deletion ({len(files_to_delete)}). Aborting.")
            return False

        current_lines = len(self.full_coverage_lines)
        if current_lines == 0:
            return True # No coverage initially, safe? Or unsafe? Assume safe if nothing covered.

        # Run coverage excluding ALL candidates
        new_coverage = self._run_coverage(ignore_files=files_to_delete)
        new_lines = len(new_coverage)

        drop_pct = (current_lines - new_lines) / current_lines
        logger.info(f"Projected coverage drop: {drop_pct:.4%} ({current_lines} -> {new_lines})")

        if drop_pct > 0.005: # 0.5%
            logger.error(f"SAFETY CHECK FAILED: Coverage drop {drop_pct:.2%} exceeds 0.5% threshold.")
            return False

        return True

    def cleanup(self):
        """Removes temporary coverage files."""
        if os.path.exists("coverage.json"):
            os.remove("coverage.json")
        if os.path.exists(".coverage"):
            os.remove(".coverage")

    def apply_verdicts(self):
        logger.info("Applying verdicts...")

        actions = [] # List of (verdict, filepath)
        files_to_delete = []

        for filepath, health in self.files_health.items():
            if health.is_critical_path:
                continue

            verdict = self.detect_rot(health)
            self.verdicts[filepath] = verdict

            if verdict.suggested_action != "NONE":
                logger.info(f"Verdict for {filepath}: {verdict.suggested_action} (Tags: {verdict.tags})")
                actions.append((verdict, filepath))
                if verdict.suggested_action == "DELETE":
                    files_to_delete.append(filepath)

        # Safety Check
        if files_to_delete:
            if not self.verify_safety(files_to_delete):
                logger.warning("Aborting all deletions due to safety check failure.")
                # Downgrade DELETE actions to NONE or log error
                for i, (v, f) in enumerate(actions):
                    if v.suggested_action == "DELETE":
                        v.suggested_action = "NONE" # Cancel deletion
                        # Update verdict in self.verdicts
                        self.verdicts[f].suggested_action = "NONE"
                files_to_delete = []

        if EXECUTION_MODE == 'PR_SUGGESTION':
            for verdict, filepath in actions:
                if verdict.suggested_action == "DELETE" and filepath in files_to_delete:
                    self.delete_file(filepath)
                elif verdict.suggested_action == "QUARANTINE":
                    self.quarantine_file(filepath)
                elif verdict.suggested_action == "REFACTOR":
                    self.refactor_bloat(filepath)

        self.cleanup()

    def delete_file(self, filepath: str):
        logger.info(f"Deleting {filepath}...")
        os.remove(filepath)

    def quarantine_file(self, filepath: str):
        logger.info(f"Quarantining {filepath}...")
        filename = os.path.basename(filepath)
        dest = os.path.join(QUARANTINE_DIR, filename)
        shutil.move(filepath, dest)

    def refactor_bloat(self, filepath: str):
        # Implementation of JSON extraction is complex and risky.
        # For this version, we will just log it.
        # In a real scenario, this would use a robust refactoring tool.
        logger.warning(f"Refactoring suggested for {filepath} but skipped for safety.")

    def generate_report(self):
        logger.info("Generating report...")
        lines = []
        lines.append("# [Entropy] Maintenance - Liability Reduction")
        lines.append("")
        lines.append("| File | Rot Type | Unique Coverage | Action Taken | Rationale |")
        lines.append("|---|---|---|---|---|")

        for filepath, verdict in self.verdicts.items():
            if verdict.suggested_action == "NONE":
                continue

            health = self.files_health[filepath]
            rot_type = ", ".join(verdict.tags)
            action = verdict.suggested_action

            rationale = ""
            if action == "DELETE":
                rationale = f"Brittle/Tautology & 0 Unique Coverage"
            elif action == "QUARANTINE":
                rationale = f"High Churn ({health.churn_rate}) & High Risk"
            elif action == "REFACTOR":
                rationale = f"Context Bloat ({health.token_cost} tokens)"

            lines.append(f"| `{filepath}` | {rot_type} | {health.unique_coverage_lines} lines | {action} | {rationale} |")

        with open(REPORT_FILE, "w") as f:
            f.write("\n".join(lines))

        logger.info(f"Report written to {REPORT_FILE}")

if __name__ == "__main__":
    entropy = Entropy()
    entropy.scan_tests()
