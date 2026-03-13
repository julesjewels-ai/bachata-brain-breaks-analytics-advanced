"""
Concrete implementations of the Repository protocol.
Handles persistence using JSON Lines formats.
"""
import json
import logging
from typing import Generic, TypeVar

from pydantic import BaseModel


logger = logging.getLogger(__name__)

# Note: We do not define contravariant=True for the implementation's TypeVar.
T = TypeVar('T', bound=BaseModel)

class RepositoryError(Exception):
    """Domain-specific exception for repository failures."""
    pass

class JsonlRepository(Generic[T]):
    """
    Persists generic Pydantic models to a JSONL file.
    Implements the Repository protocol.
    """

    def __init__(self, filepath: str):
        self.filepath = filepath

    def save(self, item: T) -> None:
        """
        Records the model by appending it as JSON to the file.
        """
        try:
            with open(self.filepath, 'a') as f:
                # Use mode='json' per standards for datetime serialization
                json_dict = item.model_dump(mode='json')
                json_str = json.dumps(json_dict)
                f.write(json_str + '\n')
        except Exception as e:
            logger.error("Failed to write record to %s: %s", self.filepath, e)
            raise RepositoryError(f"Persistence error: {e}") from e
