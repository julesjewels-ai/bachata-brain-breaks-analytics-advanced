"""
Archiving module for saving generated report metadata.
Demonstrates the Open/Closed Principle via decorators and the Repository pattern.
"""
import json
import logging
from typing import Dict
import pandas as pd

from src.core.models import ReportMetadata
from src.core.interfaces import Repository, ReportGenerator

logger = logging.getLogger(__name__)


class ArchiverException(Exception):
    """Domain-specific exception for archiving operations."""
    pass


class JSONLReportMetadataRepository(Repository[ReportMetadata]):
    """
    Persists ReportMetadata to a JSONL file.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def save(self, item: ReportMetadata) -> None:
        """
        Saves the ReportMetadata object as a JSON line.
        """
        try:
            with open(self.filepath, 'a') as f:
                item_dict = item.model_dump()
                item_dict['timestamp'] = item_dict['timestamp'].isoformat()
                f.write(json.dumps(item_dict) + '\n')
        except Exception as e:
            logger.error("Failed to write to archive %s: %s", self.filepath, e)
            raise ArchiverException(f"Failed to write to archive: {e}") from e


class ArchivedReportGenerator:
    """
    Decorator for ReportGenerator that archives metadata after generation.
    """
    def __init__(
        self,
        inner: ReportGenerator,
        repository: Repository[ReportMetadata]
    ):
        self.inner = inner
        self.repository = repository

    def generate_report(
        self, anomalies: Dict[str, pd.DataFrame], strategy: str, filepath: str
    ) -> None:
        """
        Generates the report and then archives the metadata.
        """
        self.inner.generate_report(anomalies, strategy, filepath)

        # Calculate total anomaly count safely
        total_anomalies = sum(
            len(df) for df in anomalies.values() if not df.empty
        )

        # Truncate strategy string for the preview
        preview = strategy[:100] + "..." if len(strategy) > 100 else strategy

        metadata = ReportMetadata(
            filepath=filepath,
            strategy_preview=preview,
            anomaly_count=total_anomalies
        )

        self.repository.save(metadata)
