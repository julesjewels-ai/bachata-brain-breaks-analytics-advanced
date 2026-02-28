"""
Metrics and telemetry tracking for Bachata Brain Breaks Analytics.
"""
from typing import List, Dict, Any
import json
import logging
import time
import pandas as pd
from pathlib import Path

from src.core.models import MetricEvent
from src.core.interfaces import (
    MetricsRepository, MetricsService, DataIngestionService, ReportGenerator
)

logger = logging.getLogger(__name__)


class MetricsException(Exception):
    """Base exception for metrics-related errors."""
    pass


class MetricsStorageError(MetricsException):
    """Raised when metrics cannot be saved or loaded from storage."""
    pass


class FileMetricsRepository:
    """
    Repository for storing metrics data in a JSONL file.
    """

    def __init__(self, filepath: str = "metrics.jsonl"):
        self.filepath = Path(filepath)

    def save(self, event: MetricEvent) -> None:
        """Saves a single metric event to the file in JSON Lines format."""
        try:
            with open(self.filepath, 'a') as f:
                f.write(event.model_dump_json() + '\n')
        except Exception as e:
            raise MetricsStorageError(
                f"Failed to save metric event: {e}") from e

    def get_all(self) -> List[MetricEvent]:
        """Retrieves all metric events from the file."""
        if not self.filepath.exists():
            return []

        events = []
        try:
            with open(self.filepath, 'r') as f:
                for line in f:
                    if line.strip():
                        events.append(MetricEvent.model_validate_json(line))
        except Exception as e:
            raise MetricsStorageError(
                f"Failed to read metric events: {e}") from e

        return events


class StandardMetricsService:
    """
    Standard implementation for collecting and exporting metrics.
    """

    def __init__(self, repository: MetricsRepository):
        self.repository = repository

    def record(self, event: MetricEvent) -> None:
        """Records a new metric event using the underlying repository."""
        self.repository.save(event)

    def export(self, filepath: str) -> None:
        """
        Exports all recorded metrics to a single JSON array file.
        Useful for aggregating the final run statistics.
        """
        try:
            events = self.repository.get_all()
            export_data = [event.model_dump() for event in events]

            # Using custom encoder to handle datetime objects
            def json_serial(obj: Any) -> Any:
                if isinstance(obj, pd.Timestamp):
                    return obj.isoformat()
                from datetime import datetime
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")

            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2, default=json_serial)
        except Exception as e:
            raise MetricsStorageError(
                f"Failed to export metrics to {filepath}: {e}") from e


class MetricsDataIngestionService:
    """
    Decorator for DataIngestionService that tracks execution time
    and row count.
    """

    def __init__(
        self,
        inner_service: DataIngestionService,
        metrics_service: MetricsService
    ):
        self.inner_service = inner_service
        self.metrics_service = metrics_service

    def ingest_data(self) -> pd.DataFrame:
        """
        Executes inner ingestion logic and records metrics.
        """
        start_time = time.time()
        df = self.inner_service.ingest_data()
        duration = time.time() - start_time

        # Record ingestion duration
        self.metrics_service.record(MetricEvent(
            metric_name="ingestion_duration_seconds",
            value=duration,
            unit="seconds",
            tags={"service": "MetricsDataIngestionService"}
        ))

        # Record data volume
        self.metrics_service.record(MetricEvent(
            metric_name="ingestion_row_count",
            value=float(len(df)),
            unit="rows",
            tags={"service": "MetricsDataIngestionService"}
        ))

        return df


class MetricsReportGenerator:
    """
    Decorator for ReportGenerator that tracks execution time.
    """

    def __init__(
        self,
        inner_generator: ReportGenerator,
        metrics_service: MetricsService
    ):
        self.inner_generator = inner_generator
        self.metrics_service = metrics_service

    def generate_report(
        self, anomalies: Dict[str, pd.DataFrame], strategy: str, filepath: str
    ) -> None:
        """
        Executes inner report generation and records metrics.
        """
        start_time = time.time()
        self.inner_generator.generate_report(anomalies, strategy, filepath)
        duration = time.time() - start_time

        # Record generation duration
        self.metrics_service.record(MetricEvent(
            metric_name="report_generation_duration_seconds",
            value=duration,
            unit="seconds",
            tags={"service": "MetricsReportGenerator", "filepath": filepath}
        ))
