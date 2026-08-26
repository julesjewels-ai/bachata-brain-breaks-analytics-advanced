"""
Archival module for storing and processing anomalies.
Implements the utility feature for logging viral anomalies persistently.
"""
import json
import logging

import pandas as pd

from src.core.interfaces import ReportGenerator, Repository
from src.core.models import AnomalyRecord

logger = logging.getLogger(__name__)


class ArchivalError(Exception):
    """Domain-specific exception for archival failures."""


class FileAnomalyRepository:
    """
    Concrete implementation of Repository[AnomalyRecord] that stores records in a JSONL file.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def save(self, item: AnomalyRecord) -> None:
        try:
            with open(self.filepath, 'a') as f:
                event_dict = item.model_dump()
                event_dict['timestamp'] = event_dict['timestamp'].isoformat()
                json_str = json.dumps(event_dict)
                f.write(json_str + '\n')
        except Exception as e:
            logger.error("Failed to archive anomaly to %s: %s", self.filepath, e)
            raise ArchivalError(f"Persistence error: {e}") from e


class ArchivalReportGeneratorDecorator:
    """
    Decorator for ReportGenerator that intercepts anomaly generation
    and persists them to an archival repository.
    """
    def __init__(
        self, inner: ReportGenerator, repository: Repository[AnomalyRecord]
    ):
        self.inner = inner
        self.repository = repository

    def generate_report(
        self, anomalies: dict[str, pd.DataFrame], strategy: str, filepath: str
    ) -> None:
        """
        Interprets anomalies and archives them before passing to the inner generator.
        """
        for v_type, df in anomalies.items():
            records = df.to_dict(orient='records')
            for record in records:
                # pandas to_dict('records') returns Dict[Any, Any] which mypy complains about
                # so we cast or ensure string keys explicitly
                try:
                    record_dict = {str(k): v for k, v in record.items()}
                    record_dict['type'] = v_type
                    anomaly_model = AnomalyRecord(**record_dict)
                    self.repository.save(anomaly_model)
                except Exception as e:
                    logger.warning("Failed to parse/archive anomaly record: %s", e)

        self.inner.generate_report(anomalies, strategy, filepath)
