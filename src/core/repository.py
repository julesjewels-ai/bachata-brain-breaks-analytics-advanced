"""
Repository implementations for data persistence.
"""
import logging
from typing import Sequence, TypeVar, Generic

from pydantic import BaseModel

from src.core.interfaces import Repository

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel, contravariant=True)

class RepositoryError(Exception):
    """Domain exception for repository operations."""
    pass

class JsonlRepository(Generic[T], Repository[T]):
    """
    Repository implementation that persists items to a JSONL file.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def save_all(self, items: Sequence[T]) -> None:
        """
        Persists a sequence of items by appending JSON serialized rows to a file.
        """
        try:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                for item in items:
                    json_str = item.model_dump_json()
                    f.write(json_str + '\n')
            logger.info("Saved %d items to %s", len(items), self.filepath)
        except OSError as e:
            logger.error("Failed to write to %s: %s", self.filepath, e)
            raise RepositoryError(f"Persistence error: {e}") from e
