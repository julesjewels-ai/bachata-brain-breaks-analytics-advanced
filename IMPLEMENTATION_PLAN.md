# Implementation Plan

- [ ] Fix `security.yml` Gitleaks permissions (grant `contents: read`, `pull-requests: read`)
- [ ] Fix `security.yml` SAST job Bandit arguments (target B602, B603, B604)
- [ ] Create tests for `SimulationDataIngestionService` (`tests/test_ingestion.py`)
- [ ] Create tests for `FileMetricsRepository` and Metrics Tracking (`tests/test_metrics.py`)
- [ ] Ensure `python -m pytest`, `mypy .`, and `ruff check .` pass cleanly.
