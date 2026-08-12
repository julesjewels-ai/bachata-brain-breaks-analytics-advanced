"""
Archiving module for video data persistence.
Provides a JSONL repository for saving data and a decorator for ingestion.
"""
import json
import logging
from typing import Dict, Any, List
import pandas as pd

from src.core.interfaces import Repository, DataIngestionService
from src.core.models import VideoAnalysisInput

logger = logging.getLogger(__name__)


class ArchivingError(Exception):
    """Domain-specific exception for archiving operations."""
    pass


class JsonlVideoRepository(Repository[VideoAnalysisInput]):
    """
    Concrete repository implementation that saves VideoAnalysisInput items to a JSONL file.
    """
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath

    def save(self, item: VideoAnalysisInput) -> None:
        """
        Saves a single VideoAnalysisInput to the JSONL file.
        """
        try:
            with open(self.filepath, 'a') as f:
                json_str = item.model_dump_json()
                f.write(json_str + '\n')
        except OSError as e:
            logger.error("Failed to write to archive %s: %s", self.filepath, e)
            raise ArchivingError(f"Persistence error: {e}") from e


class ArchivingDataIngestionService(DataIngestionService):
    """
    Decorator for DataIngestionService that archives the ingested data.
    """
    def __init__(
        self, inner: DataIngestionService, repository: Repository[VideoAnalysisInput]
    ) -> None:
        self.inner = inner
        self.repository = repository

    async def ingest_data(self) -> pd.DataFrame:
        """
        Wraps the inner ingestion service, saving the results to the repository.
        """
        df = await self.inner.ingest_data()

        # Save each row to the repository if possible
        if not df.empty:
            records: List[Dict[str, Any]] = df.to_dict(orient="records")
            for record in records:
                try:
                    # Validate and convert back to model to use save properly
                    # This adds a validation step to ensure archived data is clean
                    model = VideoAnalysisInput(**record)
                    self.repository.save(model)
                except Exception as e:
                    logger.warning(
                        "Could not archive record %s: %s",
                        record.get("video_id", "unknown"), e
                    )

        return df
