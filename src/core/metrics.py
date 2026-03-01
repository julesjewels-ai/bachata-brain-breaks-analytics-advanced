"""
Metrics utility feature.
Implements the MetricsRepository interface to store telemetry.
Decorators to wrap ingestion and reporting services for execution tracking.
"""
import time
import logging
from typing import Dict
import pandas as pd
from pathlib import Path

from src.core.interfaces import (
    MetricsRepository, DataIngestionService, ReportGenerator
)
from src.core.models import MetricEvent

logger = logging.getLogger(__name__)


class MetricsError(Exception):
    """
    Exception raised for errors in the metrics domain.
    """
    pass


class FileMetricsRepository(MetricsRepository):
    """
    File-based metrics repository storing events in a JSONL file.
    """

    def __init__(self, filepath: str):
        """
        Initializes the FileMetricsRepository.

        Args:
            filepath: The path to the JSONL file.
        """
        self.filepath = Path(filepath)

    def save(self, event: MetricEvent) -> None:
        """
        Saves a metric event to the JSONL file.

        Args:
            event: The metric event to save.

        Raises:
            MetricsError: If there's an issue writing to the file.
        """
        try:
            with self.filepath.open('a', encoding='utf-8') as f:
                f.write(event.model_dump_json() + '\n')
        except IOError as e:
            logger.error(
                f"Failed to write metric event to {
                    self.filepath}: {e}")
            raise MetricsError(f"Failed to write metric event: {e}") from e


class MetricsDataIngestionService(DataIngestionService):
    """
    Decorator for DataIngestionService tracking execution time and row counts.
    """

    def __init__(
        self, service: DataIngestionService, repository: MetricsRepository
    ):
        """
        Initializes the MetricsDataIngestionService.

        Args:
            service: The underlying DataIngestionService to wrap.
            repository: The MetricsRepository for telemetry storage.
        """
        self.service = service
        self.repository = repository

    def ingest_data(self) -> pd.DataFrame:
        """
        Ingests video data and records telemetry.

        Returns:
            The ingested DataFrame.
        """
        start_time = time.perf_counter()
        status = "unknown"
        row_count = 0

        try:
            df = self.service.ingest_data()
            row_count = len(df)
            status = "success"
        except Exception as e:
            status = f"error: {type(e).__name__}"
            raise e
        except BaseException as e:
            status = f"base_error: {type(e).__name__}"
            raise e
        finally:
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000

            self.repository.save(
                MetricEvent(
                    metric_name="data_ingestion",
                    value=duration_ms,
                    unit="ms",
                    tags={"status": status, "row_count": str(row_count)}
                )
            )

        return df


class MetricsReportGenerator(ReportGenerator):
    """
    Decorator for ReportGenerator tracking generation execution time.
    """

    def __init__(self, generator: ReportGenerator,
                 repository: MetricsRepository):
        """
        Initializes the MetricsReportGenerator.

        Args:
            generator: The underlying ReportGenerator to wrap.
            repository: The MetricsRepository for telemetry storage.
        """
        self.generator = generator
        self.repository = repository

    def generate_report(
        self, anomalies: Dict[str, pd.DataFrame], strategy: str, filepath: str
    ) -> None:
        """
        Generates a report and records telemetry.

        Args:
            anomalies: Dictionary of anomaly DataFrames.
            strategy: Reporting strategy used.
            filepath: Path to the generated report.
        """
        start_time = time.perf_counter()
        status = "unknown"

        try:
            self.generator.generate_report(anomalies, strategy, filepath)
            status = "success"
        except Exception as e:
            status = f"error: {type(e).__name__}"
            raise e
        except BaseException as e:
            status = f"base_error: {type(e).__name__}"
            raise e
        finally:
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000

            self.repository.save(
                MetricEvent(
                    metric_name="report_generation",
                    value=duration_ms,
                    unit="ms",
                    tags={"strategy": strategy, "status": status}
                )
            )
