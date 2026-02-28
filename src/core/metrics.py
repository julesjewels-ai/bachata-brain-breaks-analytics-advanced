"""
Metrics Tracking System using the Decorator pattern.
Allows recording telemetry without mutating core business logic.
"""
import time
from pathlib import Path
from typing import Dict
import pandas as pd

from src.core.interfaces import (
    MetricsRepository,
    DataIngestionService,
    ReportGenerator
)
from src.core.models import MetricEvent


class FileMetricsRepository(MetricsRepository):
    """
    Persists metric events to a JSONL file.
    """

    def __init__(self, filepath: str = "metrics.jsonl"):
        self.filepath = Path(filepath)

    def record(self, event: MetricEvent) -> None:
        """
        Records the metric event by appending it to a JSONL file.
        """
        try:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                f.write(event.model_dump_json() + '\n')
        except Exception:
            # Silently fail if we cannot write metrics
            pass


class MetricsDataIngestionService(DataIngestionService):
    """
    Decorator for DataIngestionService that records execution metrics.
    """

    def __init__(
        self,
        base_service: DataIngestionService,
        metrics_repo: MetricsRepository
    ):
        self._base_service = base_service
        self._metrics_repo = metrics_repo

    def ingest_data(self) -> pd.DataFrame:
        start_time = time.perf_counter()
        status = "success"
        row_count = 0
        try:
            df = self._base_service.ingest_data()
            row_count = len(df)
            return df
        except Exception:
            status = "failure"
            raise
        finally:
            duration = time.perf_counter() - start_time
            event = MetricEvent(
                metric_name="ingestion_duration",
                value=duration,
                unit="seconds",
                tags={"status": status, "row_count": row_count}
            )
            self._metrics_repo.record(event)


class MetricsReportGenerator(ReportGenerator):
    """
    Decorator for ReportGenerator that records execution metrics.
    """

    def __init__(
        self,
        base_service: ReportGenerator,
        metrics_repo: MetricsRepository
    ):
        self._base_service = base_service
        self._metrics_repo = metrics_repo

    def generate_report(
        self, anomalies: Dict[str, pd.DataFrame], strategy: str, filepath: str
    ) -> None:
        start_time = time.perf_counter()
        status = "success"
        try:
            self._base_service.generate_report(anomalies, strategy, filepath)
        except Exception:
            status = "failure"
            raise
        finally:
            duration = time.perf_counter() - start_time
            # Calculate total anomalies reported
            anomaly_count = sum(len(df) for df in anomalies.values())
            event = MetricEvent(
                metric_name="report_generation_duration",
                value=duration,
                unit="seconds",
                tags={
                    "status": status,
                    "anomaly_count": anomaly_count,
                    "filepath": filepath
                }
            )
            self._metrics_repo.record(event)
