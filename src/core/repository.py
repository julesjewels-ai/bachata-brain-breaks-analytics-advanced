"""
Repository implementation.
"""
import json
from typing import Sequence, TypeVar, Generic
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel, contravariant=True)

class RepositoryError(Exception):
    """Domain-specific exception for repository operations."""
    pass

class JsonlRepository(Generic[T]):
    """
    Concrete implementation of the generic Repository protocol
    for persisting Pydantic models to JSONL files.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def save_all(self, items: Sequence[T]) -> None:
        """
        Saves a sequence of items to a JSONL file.
        """
        try:
            with open(self.filepath, 'a') as f:
                for item in items:
                    # Use model_dump_json() for proper serialization of complex types
                    # like datetime objects.
                    f.write(item.model_dump_json() + '\n')
        except Exception as e:
            raise RepositoryError(f"Failed to persist models to {self.filepath}: {e}") from e
