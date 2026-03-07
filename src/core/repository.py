"""
Generic JSONL Repository implementation for data persistence.
"""
import json
import logging
from typing import List, Generic, TypeVar
from pydantic import BaseModel
from src.core.interfaces import Repository

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class RepositoryError(Exception):
    """Domain exception for repository operations."""
    pass

class JsonlRepository(Generic[T]):
    """
    Persists generic domain models to a JSONL file.
    Implements the Repository[T] protocol.
    """
    def __init__(self, filepath: str, model_cls: type[T]) -> None:
        self.filepath = filepath
        self.model_cls = model_cls

    def save(self, item: T) -> None:
        """Saves a single item to the JSONL file."""
        try:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                json_str = json.dumps(item.model_dump(mode='json'))
                f.write(json_str + '\n')
        except Exception as e:
            logger.error("Failed to write item to %s: %s", self.filepath, e)
            raise RepositoryError(f"Persistence error: {e}") from e

    def save_all(self, items: List[T]) -> None:
        """Saves a list of items to the JSONL file."""
        try:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                for item in items:
                    json_str = json.dumps(item.model_dump(mode='json'))
                    f.write(json_str + '\n')
        except Exception as e:
            logger.error("Failed to write items to %s: %s", self.filepath, e)
            raise RepositoryError(f"Persistence error: {e}") from e

    def get_all(self) -> List[T]:
        """Retrieves all items from the JSONL file."""
        items: List[T] = []
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        items.append(self.model_cls(**data))
        except FileNotFoundError:
            # If the file doesn't exist, return an empty list
            return []
        except Exception as e:
            logger.error("Failed to read items from %s: %s", self.filepath, e)
            raise RepositoryError(f"Read error: {e}") from e
        return items
