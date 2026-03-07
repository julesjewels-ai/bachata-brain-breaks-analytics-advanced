# Implementation Plan

- [x] Define AIService Interface in `src/core/interfaces.py`
- [x] Refactor GeminiThinkingAgent to `src/core/ai.py`
- [x] Implement Dependency Injection in `BachataAnalyticsApp`
- [x] Update Tests in `tests/test_core.py`
- [x] Update `main.py`
- [x] Implement Metrics Tracking System
- [ ] Archive selected `VideoAnalysisInput` records using the injected `Repository[VideoAnalysisInput]` instance immediately before initiating the Gemini AI stream.
