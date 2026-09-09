"""
Archiving service for Bachata Brain Breaks Analytics.
Provides decorators and repositories to persist AI inputs and outputs.
"""
import json
import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from src.core.interfaces import AIService, Repository
from src.core.models import AnalysisArchiveRecord, VideoAnalysisInput

logger = logging.getLogger(__name__)

class ArchiveError(Exception):
    """Domain exception for archiving failures."""

class FileArchiveRepository:
    """
    Persists AnalysisArchiveRecords to a JSONL file.
    """
    def __init__(self, filepath: str) -> None:
        self.filepath = Path(filepath)
        # Ensure parent directory exists
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

    def save(self, item: AnalysisArchiveRecord) -> None:
        """Saves a record as JSONL."""
        try:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                record_dict = item.model_dump()
                record_dict['timestamp'] = record_dict['timestamp'].isoformat()
                f.write(json.dumps(record_dict) + '\n')
        except Exception as e:
            logger.error("Failed to write archive to %s: %s", self.filepath, e)
            raise ArchiveError(f"Failed to save archive record: {e}") from e

class ArchivingAIService(AIService):
    """
    Decorator for AIService that archives inputs and generated strategy.
    """
    def __init__(
        self, inner: AIService, repository: Repository[AnalysisArchiveRecord]
    ) -> None:
        self._inner = inner
        self._repository = repository

    def analyze_semantics(self, videos: list[VideoAnalysisInput]) -> str:
        """
        Delegates to inner and archives result.
        """
        result = self._inner.analyze_semantics(videos)
        try:
            record = AnalysisArchiveRecord(
                inputs=videos, strategy_output=result
            )
            self._repository.save(record)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to archive semantics analysis: %s", e)
        return result

    async def analyze_stream(
        self, videos: list[VideoAnalysisInput]
    ) -> AsyncGenerator[str, None]:
        """
        Delegates stream to inner, accumulating chunks, then archives the
        full output before returning the last chunks.
        """
        full_response_accumulator = []
        try:
            async for chunk in self._inner.analyze_stream(videos):
                full_response_accumulator.append(chunk)
                yield chunk
        finally:
            full_response = "".join(full_response_accumulator)
            if full_response:
                try:
                    record = AnalysisArchiveRecord(
                        inputs=videos, strategy_output=full_response
                    )
                    self._repository.save(record)
                except Exception as e:  # noqa: BLE001
                    logger.warning("Failed to archive stream analysis: %s", e)
