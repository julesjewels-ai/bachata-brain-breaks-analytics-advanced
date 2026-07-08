"""
Archival module.
Handles persistent archival of domain models.
"""
import logging
from typing import Generic, Sequence
from src.core.interfaces import Repository, ArchivalService, T
from src.core.models import VideoAnalysisInput

logger = logging.getLogger(__name__)


class ArchivalError(Exception):
    """Domain-specific exception for archival failures."""
    pass


class JSONLRepository(Repository[T], Generic[T]):
    """
    Persists generic models to a JSONL file.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def save_all(self, items: Sequence[T]) -> None:
        """
        Appends models as JSON lines to the configured filepath.
        """
        try:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                for item in items:
                    f.write(item.model_dump_json() + '\n')
        except Exception as e:
            logger.error("Failed to archive data to %s: %s", self.filepath, e)
            raise ArchivalError(f"Persistence error: {e}") from e


class DataArchivalService(ArchivalService):
    """
    Service for orchestrating the archival of video input records.
    """
    def __init__(self, repository: Repository[VideoAnalysisInput]):
        self.repository = repository

    def archive_videos(self, videos: Sequence[VideoAnalysisInput]) -> None:
        """
        Archives the provided video records using the injected repository.
        """
        try:
            self.repository.save_all(videos)
            logger.info("Successfully archived %d videos.", len(videos))
        except ArchivalError as e:
            logger.error("Archival service failed: %s", e)
            raise
