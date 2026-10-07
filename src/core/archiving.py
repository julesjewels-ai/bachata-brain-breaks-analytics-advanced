from typing import TypeVar

import pandas as pd
from pydantic import BaseModel, ValidationError

from src.core.interfaces import DataIngestionService, Repository
from src.core.models import VideoAnalysisInput

T = TypeVar('T', bound=BaseModel)

class ArchiveError(Exception):
    """Domain-specific exception for archiving operations."""

class JsonLinesRepository(Repository[T]):
    """Persists data models to a JSON Lines file."""
    def __init__(self, filepath: str) -> None:
        if ".." in filepath:
            raise ArchiveError("Path traversal detected")
        self.filepath = filepath

    def save(self, item: T) -> None:
        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(item.model_dump_json() + "\n")
        except OSError as e:
            raise ArchiveError(f"Failed to write to archive: {e}") from e

class ArchivingDataIngestionService(DataIngestionService):
    """Decorator that archives ingested data."""
    def __init__(self, inner: DataIngestionService, repository: Repository[VideoAnalysisInput]) -> None:
        self.inner = inner
        self.repository = repository

    async def ingest_data(self) -> pd.DataFrame:
        df = await self.inner.ingest_data()

        for record in df.to_dict('records'):
            record_dict = {str(k): v for k, v in record.items()}
            try:
                model = VideoAnalysisInput(**record_dict)
                self.repository.save(model)
            except ValidationError:
                pass

        return df
