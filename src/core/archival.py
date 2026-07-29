"""
Archival service for persisting viral anomalies.
Implements the Decorator pattern on ReportGenerator to intercept and save outliers.
"""
import logging

import pandas as pd

from src.core.interfaces import AnomalyRepository, ReportGenerator
from src.core.models import AnomalyRecord

logger = logging.getLogger(__name__)


class ArchivalError(Exception):
    """Domain exception for archival failures."""


class FileAnomalyRepository(AnomalyRepository):
    """
    Persists AnomalyRecords to a JSONL file.
    Follows memory rule: use model.model_dump_json() for accurate serialization.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def save(self, entity: AnomalyRecord) -> None:
        """Saves an anomaly record to the configured file."""
        try:
            with open(self.filepath, 'a') as f:
                f.write(entity.model_dump_json() + '\n')
        except Exception as e:
            logger.error(f"Failed to persist anomaly to {self.filepath}: {e}")
            raise ArchivalError(f"Persistence error: {e}") from e


class ArchivalReportGenerator(ReportGenerator):
    """
    Decorator for ReportGenerator that archives anomalies before generating the report.
    Adheres to Open/Closed Principle.
    """
    def __init__(self, inner: ReportGenerator, repository: AnomalyRepository):
        self.inner = inner
        self.repository = repository

    def generate_report(
        self, anomalies: dict[str, pd.DataFrame], strategy: str, filepath: str
    ) -> None:
        """
        Archives the anomalies, then delegates to the inner report generator.
        """
        for v_type, df in anomalies.items():
            for _, row in df.iterrows():
                try:
                    record = AnomalyRecord(
                        video_id=str(row['video_id']),
                        title=str(row['title']),
                        views=int(row['views']),
                        retention_avg_pct=float(row['retention_avg_pct']),
                        video_type=v_type
                    )
                    self.repository.save(record)
                except Exception as e:
                    logger.warning(f"Failed to archive anomaly record for video_id {row.get('video_id', 'unknown')}: {e}")

        # Delegate to the inner report generator
        self.inner.generate_report(anomalies, strategy, filepath)
