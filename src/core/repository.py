"""
Generic repository implementation.
"""
import json
import logging
from typing import Generic, Sequence, TypeVar
from pydantic import BaseModel

from src.core.interfaces import Repository

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel, contravariant=True)

class RepositoryError(Exception):
    """Domain-specific exception for repository operations."""
    pass


class JsonlRepository(Generic[T]):
    """
    Persists generic Pydantic domain models to a JSONL file.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def save(self, item: T) -> None:
        """Saves a single item to the file."""
        try:
            with open(self.filepath, 'a') as f:
                f.write(item.model_dump_json() + '\n')
        except IOError as e:
            logger.error("Failed to write to %s: %s", self.filepath, e)
            raise RepositoryError(f"Persistence error: {e}") from e

    def save_all(self, items: Sequence[T]) -> None:
        """Saves a sequence of items to the file."""
        try:
            with open(self.filepath, 'a') as f:
                for item in items:
                    f.write(item.model_dump_json() + '\n')
        except IOError as e:
            logger.error("Failed to write to %s: %s", self.filepath, e)
            raise RepositoryError(f"Persistence error: {e}") from e
