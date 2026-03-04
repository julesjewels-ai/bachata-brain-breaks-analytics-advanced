"""
Archival system for persisting domain models.
Implements Generic Repository pattern and Anomaly Archiver service.
"""
import logging
from typing import Generic, TypeVar, List, Protocol, Dict
import pandas as pd
from pydantic import BaseModel

from src.core.models import AnomalyRecord

logger = logging.getLogger(__name__)


class ArchivalError(Exception):
    """Domain-specific exception for archival failures."""
    pass


T = TypeVar('T', bound=BaseModel)


class Repository(Protocol[T]):
    """
    Generic Repository interface for persisting domain models.
    """

    def save_bulk(self, records: List[T]) -> None:
        """Saves a batch of records."""
        ...


class FileRepository(Generic[T]):
    """
    Concrete implementation of Repository[T] that appends JSON lines to a file.
    """

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath

    def save_bulk(self, records: List[T]) -> None:
        """
        Saves records to the file in JSONL format.
        """
        try:
            with open(self.filepath, 'a') as f:
                for record in records:
                    f.write(record.model_dump_json() + '\n')
            logger.info(
                "Successfully archived %d records to %s",
                len(records),
                self.filepath)
        except Exception as e:
            logger.error(
                "Failed to archive records to %s: %s",
                self.filepath,
                e)
            raise ArchivalError(f"Failed to persist records: {e}") from e


class AnomalyArchiver(Protocol):
    """
    Service interface for archiving identified anomalies.
    """

    def archive(self, anomalies: Dict[str, pd.DataFrame]) -> None:
        """
        Archives the provided anomalies.
        """
        ...


class DefaultAnomalyArchiver(AnomalyArchiver):
    """
    Concrete service that transforms DataFrame anomalies into Domain Models
    and persists them via a generic repository.
    """

    def __init__(self, repository: Repository[AnomalyRecord]) -> None:
        self.repository = repository

    def archive(self, anomalies: Dict[str, pd.DataFrame]) -> None:
        """
        Transforms and archives anomalies.
        """
        records_to_archive: List[AnomalyRecord] = []

        try:
            for v_type, df in anomalies.items():
                if df.empty:
                    continue

                # Convert DataFrame rows to Pydantic models
                records = df.to_dict(orient='records')
                for record in records:
                    records_to_archive.append(
                        AnomalyRecord(
                            video_id=str(record.get('video_id', '')),
                            title=str(record.get('title', '')),
                            views=int(record.get('views', 0)),
                            retention_avg_pct=float(
                                record.get('retention_avg_pct', 0.0)),
                            type=str(v_type)
                        )
                    )

            if records_to_archive:
                self.repository.save_bulk(records_to_archive)
            else:
                logger.info("No anomalies to archive.")

        except Exception as e:
            if isinstance(e, ArchivalError):
                raise
            raise ArchivalError(
                f"Failed to transform and archive anomalies: {e}") from e
