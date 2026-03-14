"""
Metrics tracking system.
Handles recording execution telemetry and errors.
"""
from contextlib import contextmanager
import logging
from typing import Dict
import pandas as pd

from src.core.models import MetricEvent
from src.core.interfaces import DataIngestionService, ReportGenerator, Repository

# Configure logging
logger = logging.getLogger(__name__)


@contextmanager
def record_telemetry(repository: Repository[MetricEvent], metric_name: str):
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
        self, inner: DataIngestionService, repository: Repository[MetricEvent]
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
        self, inner: ReportGenerator, repository: Repository[MetricEvent]
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
