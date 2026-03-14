"""
Generic repository implementations.
"""
import json
import logging
from typing import Generic, TypeVar

from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    """Domain-specific exception for repository operations."""
    pass


T = TypeVar('T', bound=BaseModel)

class JsonlRepository(Generic[T]):
    """
    Concrete implementation of Repository[T] for persisting items to a JSONL file.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def record(self, event: T) -> None:
        """
        Records the given event by appending it as JSON.
        """
        try:
            with open(self.filepath, 'a') as f:
                event_dict = event.model_dump(mode='json')
                json_str = json.dumps(event_dict)
                f.write(json_str + '\n')
        except Exception as e:
            logger.error("Failed to write to %s: %s", self.filepath, e)
            raise RepositoryError(f"Persistence error: {e}") from e
