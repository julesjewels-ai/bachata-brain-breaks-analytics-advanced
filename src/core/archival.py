"""
Archival mechanisms for data ingestion.
Implements a file-based archival repository and a decorator for DataIngestionService.
"""
import json
import logging
from pathlib import Path

import pandas as pd

from src.core.interfaces import ArchivalRepository, DataIngestionService
from src.core.models import ArchivalMetadata

logger = logging.getLogger(__name__)


class ArchivalError(Exception):
    """Domain-specific exception for archival operations."""


class FileArchivalRepository(ArchivalRepository):
    """
    Persists dataframes and metadata to the filesystem.
    """

    def __init__(self, archive_dir: str):
        self.archive_dir = Path(archive_dir)
        try:
            self.archive_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error("Failed to create archive directory %s: %s", archive_dir, e)
            raise ArchivalError(f"Failed to create archive directory: {e}") from e

    def save_dataframe(self, name: str, df: pd.DataFrame, metadata: ArchivalMetadata) -> None:
        """
        Saves a DataFrame as CSV and its metadata as JSON.
        """
        timestamp_str = metadata.timestamp.strftime("%Y%m%d_%H%M%S")
        base_name = f"{name}_{timestamp_str}"
        csv_path = self.archive_dir / f"{base_name}.csv"
        json_path = self.archive_dir / f"{base_name}.json"

        try:
            df.to_csv(csv_path, index=False)

            metadata_dict = metadata.model_dump()
            metadata_dict['timestamp'] = metadata_dict['timestamp'].isoformat()

            with open(json_path, 'w') as f:
                json.dump(metadata_dict, f, indent=4)

            logger.info("Archived data to %s and %s", csv_path, json_path)
        except Exception as e:
            logger.error("Failed to archive data for %s: %s", name, e)
            raise ArchivalError(f"Archival failed: {e}") from e


class ArchivalDataIngestionService(DataIngestionService):
    """
    Decorator for DataIngestionService that archives the ingested data.
    """

    def __init__(
        self, inner: DataIngestionService, repository: ArchivalRepository, source_name: str
    ):
        self.inner = inner
        self.repository = repository
        self.source_name = source_name

    async def ingest_data(self) -> pd.DataFrame:
        """
        Wraps the inner ingestion service, then archives the result.
        """
        df = await self.inner.ingest_data()

        metadata = ArchivalMetadata(
            source=self.source_name,
            record_count=len(df)
        )

        try:
            self.repository.save_dataframe(self.source_name, df, metadata)
        except ArchivalError as e:
             # We log the error but don't fail the ingestion if archival fails
             logger.warning("Data was ingested but archival failed: %s", e)

        return df
