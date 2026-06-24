"""
Repository implementations for data persistence.
"""
import logging
from typing import Generic, Sequence, TypeVar
from pydantic import BaseModel

from src.core.interfaces import Repository

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel, contravariant=True)


class RepositoryError(Exception):
    """Domain-specific exception for repository data persistence failures."""
    pass


class JsonlRepository(Generic[T]):
    """
    Concrete implementation of Repository[T] that persists objects
    to a JSONL (JSON Lines) file.
    """

    def __init__(self, filepath: str):
        self.filepath = filepath

    def save_all(self, items: Sequence[T]) -> None:
        """
        Saves a sequence of items to the JSONL file.
        Each item is serialized using Pydantic's model_dump_json().
        """
        try:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                for item in items:
                    f.write(item.model_dump_json() + '\n')
        except Exception as e:
            logger.error("Failed to write items to %s: %s", self.filepath, e)
            raise RepositoryError(f"Persistence error: {e}") from e
