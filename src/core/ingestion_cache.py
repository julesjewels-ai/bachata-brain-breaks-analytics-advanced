"""
Data Ingestion Cache utility.
Provides an extensible caching layer for data ingestion.
"""
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, TypeVar

import pandas as pd
from pydantic import BaseModel, Field

from src.core.interfaces import DataIngestionService

logger = logging.getLogger(__name__)

T = TypeVar('T')

class IngestionCacheError(Exception):
    """Domain-specific exception for ingestion caching errors."""

class DomainModel(BaseModel):
    """Base domain model."""

class CacheMetadata(DomainModel):
    """Metadata for cached data."""
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    version: str = Field(default="1.0")
    ttl_seconds: int = Field(default=3600)  # Default 1 hour TTL

    @property
    def is_expired(self) -> bool:
        """Checks if the cache has expired based on TTL."""
        elapsed = (datetime.now(UTC) - self.timestamp).total_seconds()
        return elapsed > self.ttl_seconds

class CacheRepository(Protocol[T]):
    """
    Generic repository interface for caching.
    Follows Dependency Inversion Principle.
    """
    def load(self) -> T | None:
        """Loads data from the cache."""
        ...

    def save(self, data: T) -> None:
        """Saves data to the cache."""
        ...

    def is_expired(self) -> bool:
        """Checks if the cached data is expired."""
        ...

class DataFrameCacheRepository(CacheRepository[pd.DataFrame]):
    """
    Concrete implementation of CacheRepository for pandas DataFrames.
    Uses pickle for serialization along with metadata.
    """
    def __init__(self, filepath: Path, ttl_seconds: int = 3600) -> None:
        self.filepath = filepath
        self.meta_filepath = self.filepath.with_suffix(".meta.json")
        self.ttl_seconds = ttl_seconds

    def is_expired(self) -> bool:
        """Checks if the cache is expired using stored metadata."""
        if not self.meta_filepath.exists():
            return True

        try:
            meta_json = self.meta_filepath.read_text(encoding="utf-8")
            metadata = CacheMetadata.model_validate_json(meta_json)
            return metadata.is_expired
        except Exception as e:
            logger.warning("Failed to read cache metadata from %s: %s", self.meta_filepath, e)
            return True

    def load(self) -> pd.DataFrame | None:
        """Loads a DataFrame from a pickle file."""
        if not self.filepath.exists() or self.is_expired():
            return None

        try:
            return pd.read_pickle(self.filepath)
        except Exception as e:
            logger.error("Failed to load cache from %s: %s", self.filepath, e)
            return None

    def save(self, data: pd.DataFrame) -> None:
        """Saves a DataFrame to a pickle file and its metadata to a JSON file."""
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            data.to_pickle(self.filepath)

            # Save metadata
            meta = CacheMetadata(ttl_seconds=self.ttl_seconds)
            self.meta_filepath.write_text(meta.model_dump_json(), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to save cache to %s: %s", self.filepath, e)
            raise IngestionCacheError(f"Failed to save cache: {e}") from e

class CachedDataIngestionService(DataIngestionService):
    """
    Decorator for DataIngestionService that adds caching capabilities.
    Complies with Open/Closed principle via extension.
    """
    def __init__(
        self,
        inner: DataIngestionService,
        repository: CacheRepository[pd.DataFrame]
    ) -> None:
        self.inner = inner
        self.repository = repository

    async def ingest_data(self) -> pd.DataFrame:
        """
        Attempts to load data from the cache repository.
        If a cache miss occurs, delegates to the inner service and saves the result.
        """
        cached_data = self.repository.load()
        if cached_data is not None:
            logger.info("Ingestion cache hit.")
            return cached_data

        logger.info("Ingestion cache miss. Fetching data from source.")
        data = await self.inner.ingest_data()

        try:
            self.repository.save(data)
        except IngestionCacheError as e:
            logger.warning("Could not cache ingested data: %s", e)

        return data
