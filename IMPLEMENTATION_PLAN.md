# Implementation Plan

## Current Status: Stale
All previous tasks have been completed. Initiating Gap Analysis per protocols.

## Gap Analysis: Anomaly Archival Feature
**Identified Need:** The system currently detects and displays viral anomalies (outliers) and generates reports, but lacks historical anomaly tracking. We need an Anomaly Archival Feature to persist these outliers for long-term pattern analysis and auditing.
**GRASP/SCP Risk Assessment:** Low risk. High cohesion achieved by utilizing the Decorator pattern on the `ReportGenerator` interface. This allows us to intercept the report generation process, extract the anomalies, and archive them without mutating the existing core business logic or the underlying report generation itself (Open/Closed Principle).

## New Tasks
- [ ] Define `AnomalyRecord` model in `src/core/models.py`.
- [ ] Define generic `Repository[T]` and `AnomalyRepository` interfaces in `src/core/interfaces.py`.
- [ ] Implement `FileAnomalyRepository` and `ArchivalReportGenerator` decorator in `src/core/archival.py`.
- [ ] Integrate `ArchivalReportGenerator` into the dependency container in `main.py`.
- [ ] Write integration test `tests/test_archival_integration.py`.
- [ ] Run quality gates (mypy, ruff, pytest).
