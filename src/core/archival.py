"""
Data archival mechanisms for Bachata Brain Breaks Analytics.
Provides a repository pattern for persisting ingested data.
"""
import logging
import pandas as pd

from src.core.interfaces import DataIngestionService, Repository

logger = logging.getLogger(__name__)


class ArchivalError(Exception):
    """Domain-specific exception for archival operations."""
    pass


class JsonFileRepository:
    """
    Persists data to a JSON file.
    Implements the Repository[pd.DataFrame] protocol.
    """
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath

    def save(self, item: pd.DataFrame) -> None:
        """
        Saves a pandas DataFrame to a JSON file (orient='records').
        """
        try:
            item.to_json(self.filepath, orient='records')
        except Exception as e:
            logger.error("Failed to archive data to %s: %s", self.filepath, e)
            raise ArchivalError(f"Archival failed: {e}") from e


class ArchivingDataIngestionService(DataIngestionService):
    """
    Decorator for DataIngestionService that archives the ingested data.
    """
    def __init__(
        self, inner: DataIngestionService, repository: Repository[pd.DataFrame]
    ) -> None:
        self.inner = inner
        self.repository = repository

    async def ingest_data(self) -> pd.DataFrame:
        """
        Ingests data using the inner service and archives it.
        """
        df = await self.inner.ingest_data()
        self.repository.save(df)
        return df
