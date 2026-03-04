"""
Metrics tracking system.
Handles recording execution telemetry and errors.
"""
import json
import logging
from typing import Dict
import pandas as pd

from src.core.models import MetricEvent
from src.core.interfaces import DataIngestionService, ReportGenerator

# Configure logging
logger = logging.getLogger(__name__)


from contextlib import contextmanager

class MetricsError(Exception):
    """Domain-specific exception for metrics operations."""
    pass


class FileMetricsRepository:
    """
    Persists metric events to a JSONL file.
    """

    def __init__(self, filepath: str):
        self.filepath = filepath

    def record(self, event: MetricEvent) -> None:
        """
        Records a metric event by appending it as JSON.
        """
        try:
            with open(self.filepath, 'a') as f:
                # Use timezone-aware timestamp explicitly per standards
                event_dict = event.model_dump()
                event_dict['timestamp'] = event_dict['timestamp'].isoformat()
                json_str = json.dumps(event_dict)
                f.write(json_str + '\n')
        except Exception as e:
            logger.error("Failed to write metric to %s: %s", self.filepath, e)
            raise MetricsError(f"Persistence error: {e}") from e


@contextmanager
def record_telemetry(repository: FileMetricsRepository, metric_name: str):
    """
    A context manager to wrap execution and record success/failure telemetry.
    """
    try:
        yield
        repository.record(MetricEvent(
            metric_name=metric_name,
            value=1.0,
            unit="count",
            tags={"status": "success"}
        ))
    except BaseException as e:
        repository.record(MetricEvent(
            metric_name=metric_name,
            value=1.0,
            unit="count",
            tags={
                "status": "failure",
                "base_error": type(e).__name__
            }
        ))
        raise


class MetricsDataIngestionService:
    """
    Decorator for DataIngestionService that records execution telemetry.
    """

    def __init__(
        self, inner: DataIngestionService, repository: FileMetricsRepository
    ):
        self.inner = inner
        self.repository = repository

    async def ingest_data(self) -> pd.DataFrame:
        """
        Wraps the inner ingestion service with telemetry tracking.
        """
        with record_telemetry(self.repository, "ingestion_execution"):
            return await self.inner.ingest_data()


class MetricsReportGenerator:
    """
    Decorator for ReportGenerator that records execution telemetry.
    """

    def __init__(
        self, inner: ReportGenerator, repository: FileMetricsRepository
    ):
        self.inner = inner
        self.repository = repository

    def generate_report(
        self, anomalies: Dict[str, pd.DataFrame], strategy: str, filepath: str
    ) -> None:
        """
        Wraps the inner report generation with telemetry tracking.
        """
        with record_telemetry(self.repository, "report_generation_execution"):
            self.inner.generate_report(anomalies, strategy, filepath)
