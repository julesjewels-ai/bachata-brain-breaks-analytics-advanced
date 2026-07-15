"""
Auditing module for the core application.
Implements data persistence for auditing and a decorator for AIService.
"""
import logging
from typing import Sequence, List, AsyncGenerator
from pydantic import BaseModel

from src.core.interfaces import Repository, AIService
from src.core.models import VideoAnalysisInput

logger = logging.getLogger(__name__)


class AuditError(Exception):
    """Domain-specific exception for auditing operations."""
    pass


class JSONLinesAuditRepository(Repository[BaseModel]):
    """
    Concrete implementation of Repository that writes items to a JSONL file.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def save_all(self, items: Sequence[BaseModel]) -> None:
        """
        Saves a collection of items to the JSONL file.
        """
        try:
            with open(self.filepath, 'a') as f:
                for item in items:
                    f.write(item.model_dump_json() + '\n')
        except Exception as e:
            logger.error("Failed to write audit data to %s: %s", self.filepath, e)
            raise AuditError(f"Persistence error: {e}") from e


class AuditedAIService(AIService):
    """
    Decorator for AIService that persists VideoAnalysisInput models
    to an audit repository before calling the underlying AI service logic.
    """
    def __init__(self, ai_service: AIService, repository: Repository[VideoAnalysisInput]):
        self._ai_service = ai_service
        self._repository = repository

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Persists video input and delegates to the underlying AI service.
        """
        try:
            self._repository.save_all(videos)
        except Exception as e:
            logger.warning("Auditing failed during analyze_semantics: %s", e)
            # Proceeding without auditing failure breaking the application,
            # or optionally raise, but best practice here is usually not to break core flow.

        return self._ai_service.analyze_semantics(videos)

    async def analyze_stream(
        self, videos: List[VideoAnalysisInput]
    ) -> AsyncGenerator[str, None]:
        """
        Persists video input and streams from the underlying AI service.
        """
        try:
            self._repository.save_all(videos)
        except Exception as e:
            logger.warning("Auditing failed during analyze_stream: %s", e)

        async for chunk in self._ai_service.analyze_stream(videos):
            yield chunk
