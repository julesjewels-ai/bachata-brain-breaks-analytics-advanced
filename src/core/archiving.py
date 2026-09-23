"""
Data archiving mechanisms.
Implements a service to persist ingested data to long-term storage.
"""
import logging
from datetime import datetime, timezone
from typing import Protocol, TypeVar

import pandas as pd

from src.core.interfaces import DataIngestionService

logger = logging.getLogger(__name__)

T_contra = TypeVar('T_contra', contravariant=True)

class ArchivingError(Exception):
    """Domain-specific exception for archiving operations."""


class ArchiveRepository(Protocol[T_contra]):
    """
    Protocol for data archiving.
    """
    def save(self, data: T_contra) -> None:
        """
        Persists data to the underlying storage.
        """
        ...


class JSONLArchiveRepository:
    """
    Persists data to a JSONL file format.
    """
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath

    def save(self, data: pd.DataFrame) -> None:
        """
        Saves DataFrame records to a JSONL file.
        """
        try:
            timestamp = datetime.now(timezone.utc).isoformat()

            # Add a timestamp to track when the batch was archived
            archive_df = data.copy()
            archive_df['archived_at'] = timestamp

            # Ensure lines are written atomically by using to_json directly
            # with lines=True and orient='records'
            with open(self.filepath, 'a') as f:
                # pandas to_json can write directly to file objects
                archive_df.to_json(f, orient='records', lines=True)
                # Ensure newline is present after each batch to avoid corruption
                f.write('\n')

        except Exception as e:
            logger.error("Failed to archive data to %s: %s", self.filepath, e)
            raise ArchivingError(f"Archiving persistence error: {e}") from e


class ArchivingDataIngestionService:
    """
    Decorator for DataIngestionService that automatically archives ingested data.
    """
    def __init__(
        self, inner: DataIngestionService, repository: ArchiveRepository[pd.DataFrame]
    ) -> None:
        self.inner = inner
        self.repository = repository

    async def ingest_data(self) -> pd.DataFrame:
        """
        Wraps the inner ingestion service, saving the results to the repository.
        """
        data = await self.inner.ingest_data()

        try:
            self.repository.save(data)
        except ArchivingError as e:
            # We log the error but allow ingestion to proceed.
            # Archiving failures should not break the core application flow.
            logger.warning("Data ingestion archiving failed, proceeding anyway: %s", e)

        return data
