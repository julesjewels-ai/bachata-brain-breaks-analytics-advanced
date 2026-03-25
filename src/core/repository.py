"""
Repository utility feature for data persistence.
Provides a generic Repository protocol and a JsonlRepository implementation.
"""
import json
from typing import Protocol, TypeVar, Generic, Sequence
from pydantic import BaseModel

class RepositoryError(Exception):
    """Domain-specific exception for repository operations."""
    pass

T = TypeVar('T', bound=BaseModel, contravariant=True)

class Repository(Protocol[T]):
    """
    Generic Repository protocol for persisting domain models.
    """
    def save(self, items: Sequence[T]) -> None:
        """
        Saves a sequence of items.

        Args:
            items: Sequence of items to save.
        """
        ...

class JsonlRepository(Generic[T]):
    """
    Concrete implementation of Repository that persists items to a JSONL file.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def save(self, items: Sequence[T]) -> None:
        """
        Saves items to the JSONL file.
        """
        try:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                for item in items:
                    json_str = json.dumps(item.model_dump(mode='json'))
                    f.write(json_str + '\n')
        except (IOError, OSError) as e:
            raise RepositoryError(f"Failed to save items to {self.filepath}: {e}") from e
