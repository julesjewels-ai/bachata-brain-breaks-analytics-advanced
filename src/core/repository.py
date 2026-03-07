"""
Generic repository for data persistence.
"""
import json
import logging
from typing import List, TypeVar
from pydantic import BaseModel
from src.core.interfaces import Repository

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class RepositoryError(Exception):
    """Domain-specific exception for repository operations."""
    pass


class JsonlRepository(Repository[T]):
    """
    Persists Pydantic models to a JSONL file.
    """

    def __init__(self, filepath: str):
        self.filepath = filepath

    def save(self, record: T) -> None:
        """
        Saves a single record by appending it as JSON.
        """
        try:
            with open(self.filepath, 'a') as f:
                event_dict = record.model_dump(mode='json')
                json_str = json.dumps(event_dict)
                f.write(json_str + '\n')
        except Exception as e:
            logger.error("Failed to write to %s: %s", self.filepath, e)
            raise RepositoryError(f"Persistence error: {e}") from e

    def save_all(self, records: List[T]) -> None:
        """
        Saves a list of records.
        """
        try:
            with open(self.filepath, 'a') as f:
                for record in records:
                    event_dict = record.model_dump(mode='json')
                    json_str = json.dumps(event_dict)
                    f.write(json_str + '\n')
        except Exception as e:
            logger.error("Failed to write to %s: %s", self.filepath, e)
            raise RepositoryError(f"Persistence error: {e}") from e
