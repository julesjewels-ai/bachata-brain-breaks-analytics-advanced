# Implementation Plan - Bachata Brain Breaks Analytics

## Gap Analysis
- **Missing Service Layer**: `src/core/services.py` is missing.
- **Hardcoded Agent**: `src/core/app.py` uses a local `GeminiThinkingAgent` instead of a service.
- **Missing Interface**: `AIService` is not defined in `src/core/interfaces.py`.
- **Missing Dependency**: `google-generativeai` is missing from `requirements.txt`.

## Roadmap
1. Add dependencies.
2. Define Interfaces.
3. Implement Service.
4. Refactor App.
5. Update Main.
6. Verify with Tests.
