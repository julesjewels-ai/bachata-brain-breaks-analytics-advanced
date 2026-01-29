# Implementation Plan - Refactoring to Clean Architecture

## Gap Analysis
1. **Architecture Violation**: `src/core/app.py` contains domain models (`VideoAnalysisInput`), business logic (`detect_outliers`), and orchestration. It needs to be split.
2. **Missing Service Layer**: `src/core/services.py` is missing.
3. **Missing Models Layer**: `src/core/models.py` is missing.
4. **Missing API**: `src/api` is missing (Deferred to future task).

## Roadmap
1. [ ] Refactor Domain Models (`src/core/models.py`)
2. [ ] Refactor Services (`src/core/services.py`)
3. [ ] Refactor App (`src/core/app.py`)
4. [ ] Update Tests (`tests/test_core.py`)
