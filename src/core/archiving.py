"""
Archiving service for domain models.
Provides persistence of records to JSONL files.
"""
import logging
from typing import Generic, Dict
import pandas as pd
from pydantic import ValidationError

from src.core.interfaces import Repository, T_contra, ReportGenerator
from src.core.models import AnomalyRecord

logger = logging.getLogger(__name__)


class ArchivalError(Exception):
    """Domain-specific exception for archiving operations."""
    pass


class JSONLRepository(Repository[T_contra], Generic[T_contra]):
    """
    Persists generic domain models to a JSONL file.
    """
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath

    def save(self, item: T_contra) -> None:
        """
        Saves the item by appending it as JSON.
        """
        try:
            with open(self.filepath, 'a') as f:
                json_str = item.model_dump_json()
                f.write(json_str + '\n')
        except Exception as e:
            logger.error("Failed to write to archive %s: %s", self.filepath, e)
            raise ArchivalError(f"Persistence error: {e}") from e


class ArchivingReportGenerator:
    """
    Decorator for ReportGenerator that persists anomalies before delegating report generation.
    """
    def __init__(self, inner: ReportGenerator, repository: Repository[AnomalyRecord]) -> None:
        self.inner = inner
        self.repository = repository

    def generate_report(
        self, anomalies: Dict[str, pd.DataFrame], strategy: str, filepath: str
    ) -> None:
        """
        Persists anomalies then wraps the inner report generation.
        """
        # Iterate and persist anomalies
        for v_type, df in anomalies.items():
            for record_dict in df.to_dict('records'):
                try:
                    # Pass the dict as kwargs, casting keys to strings
                    anomaly = AnomalyRecord(**{str(k): v for k, v in record_dict.items()})
                    self.repository.save(anomaly)
                except ValidationError as e:
                    logger.warning("Failed to validate anomaly record for archiving: %s", e)
                except ArchivalError as e:
                    # Log but continue to allow report generation to succeed
                    logger.warning("Failed to archive anomaly record: %s", e)

        self.inner.generate_report(anomalies, strategy, filepath)
