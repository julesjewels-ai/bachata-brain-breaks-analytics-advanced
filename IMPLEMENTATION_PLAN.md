# Implementation Plan

- [x] Define AIService Interface in `src/core/interfaces.py`
- [x] Refactor GeminiThinkingAgent to `src/core/ai.py`
- [x] Implement Dependency Injection in `BachataAnalyticsApp`
- [x] Update Tests in `tests/test_core.py`
- [x] Update `main.py`
- [x] Implement Metrics Tracking System
# Gap Analysis

The codebase currently lacks an automated mechanism to prevent test inflation, which leads to high maintenance costs and excessive context window consumption for AI agents. The current tests may contain brittle mocking, excessive context bloat, and redundant coverage without uniquely testing the code.

## Target
Implement the **Entropy Protocol** to automate repository sanitation and de-inflation.
1. Create `scripts/entropy.py` to audit the test suite (run pytest with coverage, analyze AST for rot patterns like mock abuse and tautologies, and apply the Action Strategy for cleanup).
2. Create `.github/workflows/entropy.yml` to run the protocol daily at 02:00 UTC.

## GRASP/SCP Risk Assessment
- **Risk**: Automated code deletion (e.g., deleting or refactoring tests) could inadvertently reduce test coverage or remove critical tests if not properly guarded.
- **Relevance Score**: 4 (High risk of breaking CI or removing valuable tests)
- **Security Control**: Implement strict safety guardrails: The script must adhere strictly to the "Coverage Cliff" rule (never reduce global statement coverage by more than 0.5%), enforce the "Vibe Check" (abort if > 20 files are flagged), preserve *.md and *.feature files, and respect the "Critical Path Immunity" (any file in `critical_paths.json` is immune to deletion). The execution mode should be configurable.
