"""
Repository implementations for data persistence.
"""
import json
import logging
from typing import Generic, Sequence, TypeVar
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class RepositoryError(Exception):
    """Domain-specific exception for repository operations."""
    pass

T2 = TypeVar('T2', bound=BaseModel)

class JsonlRepository(Generic[T2]):
    """
    Concrete implementation of the Repository protocol that persists
    data models to a JSONL file.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def save(self, record: T2) -> None:
        """
        Persists a single record to the JSONL file.
        """
        try:
            with open(self.filepath, 'a') as f:
                json_str = json.dumps(record.model_dump(mode='json'))
                f.write(json_str + '\n')
        except Exception as e:
            logger.error("Failed to write to %s: %s", self.filepath, e)
            raise RepositoryError(f"Persistence error: {e}") from e

    def save_all(self, records: Sequence[T2]) -> None:
        """
        Persists multiple records to the JSONL file.
        """
        try:
            with open(self.filepath, 'a') as f:
                for record in records:
                    json_str = json.dumps(record.model_dump(mode='json'))
                    f.write(json_str + '\n')
        except Exception as e:
            logger.error("Failed to write to %s: %s", self.filepath, e)
            raise RepositoryError(f"Persistence error: {e}") from e
