"""
Metrics tracking for Bachata Brain Breaks Analytics.
Provides decoupled domain telemetry using the Decorator pattern.
"""
import time
import json
from typing import Protocol, Any, Dict
import pandas as pd
from src.core.interfaces import DataIngestionService, ReportGenerator
from src.core.models import MetricEvent

class MetricsError(Exception):
    """Domain-specific error for metrics operations."""
    pass


class MetricsRepository(Protocol):
    """
    Protocol for metric persistence.
    """
    def save(self, event: MetricEvent) -> None:
        """Saves a metric event."""
        ...


class FileMetricsRepository(MetricsRepository):
    """
    Persists metric events to a JSONL file.
    """
    def __init__(self, filepath: str = "metrics.jsonl"):
        self.filepath = filepath

    def save(self, event: MetricEvent) -> None:
        try:
            with open(self.filepath, 'a') as f:
                # model_dump_json handles datetime serialization
                f.write(event.model_dump_json() + '\n')
        except Exception as e:
            raise MetricsError(f"Failed to write metric: {e}")


class MetricsDataIngestionService(DataIngestionService):
    """
    Decorator for DataIngestionService that records telemetry.
    """
    def __init__(
        self,
        base_service: DataIngestionService,
        repository: MetricsRepository
    ):
        self.base_service = base_service
        self.repository = repository

    def ingest_data(self) -> pd.DataFrame:
        start_time = time.time()
        status = "success"
        base_error = None
        result = None

        try:
            result = self.base_service.ingest_data()
            return result
        except BaseException as e:
            status = "error"
            base_error = type(e).__name__
            raise e
        finally:
            duration = time.time() - start_time
            tags = {"status": status}
            if base_error:
                tags["base_error"] = base_error

            if status == "success" and result is not None:
                tags["records"] = str(len(result))

            event = MetricEvent(
                metric_name="ingestion_duration",
                value=duration,
                unit="seconds",
                tags=tags
            )
            self.repository.save(event)


class MetricsReportGenerator(ReportGenerator):
    """
    Decorator for ReportGenerator that records telemetry.
    """
    def __init__(
        self,
        base_service: ReportGenerator,
        repository: MetricsRepository
    ):
        self.base_service = base_service
        self.repository = repository

    def generate_report(
        self, anomalies: Dict[str, pd.DataFrame], strategy: str, filepath: str
    ) -> None:
        start_time = time.time()
        status = "success"
        base_error = None

        try:
            self.base_service.generate_report(anomalies, strategy, filepath)
        except BaseException as e:
            status = "error"
            base_error = type(e).__name__
            raise e
        finally:
            duration = time.time() - start_time
            tags = {"status": status, "filepath": filepath}
            if base_error:
                tags["base_error"] = base_error

            event = MetricEvent(
                metric_name="report_generation_duration",
                value=duration,
                unit="seconds",
                tags=tags
            )
            self.repository.save(event)
