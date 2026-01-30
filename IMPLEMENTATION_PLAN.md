# Implementation Plan - Bachata Brain Breaks Analytics

## Gap Analysis
The current codebase has a basic implementation of `BachataAnalyticsApp` in `src/core/app.py` which violates the Single Responsibility Principle and Dependency Injection.
- **Missing Domain Layer**: `VideoAnalysisInput` is coupled with `app.py`.
- **Missing Service Layer**: Logic for ingestion, anomaly detection, and AI analysis is hardcoded in the controller.
- **Missing Dependency Injection**: The app instantiates its own dependencies.
- **Missing API**: The API layer is completely missing (although not in scope for this immediate refactor, it's a known gap).

## Roadmap
1.  **Refactor Domain Layer**: Extract DTOs to `src/core/domain.py`.
2.  **Refactor Service Layer**: Create `AnalyticsService` and `AIService`.
3.  **Refactor Application Layer**: Implement Dependency Injection in `BachataAnalyticsApp`.
4.  **Update Entry Point**: Wire dependencies in `main.py`.
