# Implementation Plan

- [x] Define AIService Interface in `src/core/interfaces.py`
- [x] Refactor GeminiThinkingAgent to `src/core/ai.py`
- [x] Implement Dependency Injection in `BachataAnalyticsApp`
- [x] Update Tests in `tests/test_core.py`
- [x] Update `main.py`
- [x] Implement Metrics Tracking System
- [ ] Test `GeminiThinkingAgent.analyze_stream` in `src/core/ai.py`

## Gap Analysis & Risk Assessment
- **Target:** `GeminiThinkingAgent.analyze_stream` from `src/core/ai.py` (Complexity 6, Coverage 44%).
- **GRASP/SCP Risk:** Secret Leakage (Score 5) due to testing with API keys.
- **Control:** Use mocked configuration and fake API keys (`TEST_API_KEY`) in the tests to prevent secret leakage. Ensure pure unit tests without I/O calls.
