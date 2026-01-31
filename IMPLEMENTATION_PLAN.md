# Implementation Plan - Bachata Brain Breaks Analytics

## Phase 1: AI Service Architecture (High Priority)
- [ ] Refactor Domain: Extract `VideoAnalysisInput` from `src/core/app.py` to `src/core/domain.py`
- [ ] Define `AIService` Protocol in `src/core/interfaces.py`
- [ ] Implement `GeminiStreamingService` in `src/core/services/ai.py`
- [ ] Refactor `BachataAnalyticsApp` to use Dependency Injection for `AIService`
- [ ] Add unit tests for `GeminiStreamingService` and updated `BachataAnalyticsApp`

## Phase 2: API Layer (Medium Priority)
- [ ] Create `src/api/main.py` (FastAPI entry point)
- [ ] Create `src/api/routes.py` (Endpoints)
- [ ] Add integration tests for API endpoints

## Phase 3: Advanced Features (Low Priority)
- [ ] Implement actual Gemini API integration (if keys provided)
- [ ] Enhance Visualization with interactive Plotly charts in Streamlit (if Streamlit is used)
- [ ] Complete pre commit steps
