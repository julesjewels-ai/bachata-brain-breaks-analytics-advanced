import json
import logging
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
import pandas as pd

from src.core.models import ArchiveMetadata
from src.core.interfaces import ArchiveRepository, DataArchivalService

logger = logging.getLogger(__name__)

class ArchivalError(Exception):
    """Domain exception for archival operations."""
    pass


class FileArchiveRepository(ArchiveRepository):
    """
    File-based implementation of ArchiveRepository.
    Stores metadata as JSON and data as CSV.
    """
    def __init__(self, archive_dir: str):
        self.archive_dir = Path(archive_dir)
        try:
            self.archive_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error("Failed to create archive directory %s: %s", archive_dir, e)
            raise ArchivalError(f"Failed to create archive directory: {e}") from e

    def _get_metadata_path(self, archive_id: str) -> Path:
        return self.archive_dir / f"{archive_id}_meta.json"

    def _get_data_path(self, archive_id: str) -> Path:
        return self.archive_dir / f"{archive_id}_data.csv"

    def save(self, entity: ArchiveMetadata) -> None:
        """Saves archive metadata to JSON."""
        filepath = self._get_metadata_path(entity.archive_id)
        try:
            with open(filepath, 'w') as f:
                event_dict = entity.model_dump()
                event_dict['archived_at'] = event_dict['archived_at'].isoformat()
                json.dump(event_dict, f)
        except Exception as e:
            logger.error("Failed to save metadata for %s: %s", entity.archive_id, e)
            raise ArchivalError(f"Failed to save metadata: {e}") from e

    def get(self, id: str) -> Optional[ArchiveMetadata]:
        """Retrieves archive metadata by ID."""
        filepath = self._get_metadata_path(id)
        if not filepath.exists():
            return None
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                return ArchiveMetadata(**data)
        except Exception as e:
            logger.error("Failed to load metadata for %s: %s", id, e)
            return None

    def save_data(self, archive_id: str, df: pd.DataFrame) -> None:
        """Saves dataframe as CSV."""
        filepath = self._get_data_path(archive_id)
        try:
            df.to_csv(filepath, index=False)
        except Exception as e:
            logger.error("Failed to save data for %s: %s", archive_id, e)
            raise ArchivalError(f"Failed to save data: {e}") from e


class StandardDataArchivalService(DataArchivalService):
    """
    Standard implementation of DataArchivalService.
    """
    def __init__(self, repository: ArchiveRepository):
        self.repository = repository

    def archive(self, df: pd.DataFrame) -> ArchiveMetadata:
        """
        Archives the dataframe and returns metadata.
        """
        archive_id = str(uuid.uuid4())

        metadata = ArchiveMetadata(
            archive_id=archive_id,
            record_count=len(df),
            archived_at=datetime.now(timezone.utc),
            source_type="system"
        )

        try:
            # Save data first
            self.repository.save_data(archive_id, df)
            # Save metadata if data saved successfully
            self.repository.save(metadata)
        except Exception as e:
            raise ArchivalError(f"Archival failed for {archive_id}: {e}") from e

        return metadata
