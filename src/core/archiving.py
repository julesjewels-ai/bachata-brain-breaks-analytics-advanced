"""
Data archiving service and infrastructure layer components.
Handles automated archiving of analysis data into JSONL formats for audit logs and historical analysis.
"""
import json
import logging
from typing import Generic, TypeVar

import pandas as pd
from pydantic import BaseModel

from src.core.interfaces import DataArchiver, DataIngestionService, Repository

logger = logging.getLogger(__name__)

T_bound = TypeVar('T_bound', bound=BaseModel)

class ArchiveError(Exception):
    """Domain-specific exception for archiving operations."""


class JsonlRepository(Repository[T_bound], Generic[T_bound]):
    """
    Persists generic pydantic domain models to a JSONL file.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def save(self, item: T_bound) -> None:
        """Saves a single item to the repository."""
        self.save_all([item])

    def save_all(self, items: list[T_bound]) -> None:
        """Saves multiple items to the repository."""
        try:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                for item in items:
                    item_dict = item.model_dump(mode='json')
                    f.write(json.dumps(item_dict) + '\n')
        except Exception as e:
            logger.error("Failed to write to %s: %s", self.filepath, e)
            raise ArchiveError(f"Persistence error: {e}") from e


class AutomatedDataArchiver(DataArchiver):
    """
    Implementation of DataArchiver that saves pandas DataFrames as JSONL strings.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def archive(self, df: pd.DataFrame) -> None:
        """
        Archives a DataFrame for long-term storage or analysis.
        Avoids pydantic model overhead by serializing directly to JSONL.
        """
        try:
            # orient='records' with lines=True outputs NDJSON
            df.to_json(self.filepath, orient='records', lines=True, mode='a')
        except Exception as e:
            logger.error("Failed to archive dataframe to %s: %s", self.filepath, e)
            raise ArchiveError(f"Archiving error: {e}") from e


class DataArchivingIngestionService(DataIngestionService):
    """
    Decorator for DataIngestionService that records historical data copies.
    """
    def __init__(
        self, inner: DataIngestionService, archiver: DataArchiver
    ):
        self.inner = inner
        self.archiver = archiver

    async def ingest_data(self) -> pd.DataFrame:
        """
        Wraps the inner ingestion service and archives data.
        Silently consumes ArchiveError to prevent breaking ingestion flow.
        """
        df = await self.inner.ingest_data()
        try:
            self.archiver.archive(df)
        except ArchiveError:
            # We already logged this in the archiver, safe to consume
            pass
        return df
