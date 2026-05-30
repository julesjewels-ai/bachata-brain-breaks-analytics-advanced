"""
Concrete implementation of the Repository protocol.
"""
import json
import logging
from typing import Sequence, TypeVar
from pydantic import BaseModel
from src.core.interfaces import Repository

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel, contravariant=True)

class RepositoryError(Exception):
    """Domain-specific exception for repository errors."""
    pass

class JsonlRepository(Repository[T]):
    """
    Persists entities to a JSONL file.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def save_all(self, entities: Sequence[T]) -> None:
        """
        Saves a collection of entities.
        """
        try:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                for entity in entities:
                    json_str = json.dumps(entity.model_dump(mode='json'))
                    f.write(json_str + '\n')
        except Exception as e:
            logger.error(f"Failed to write to repository {self.filepath}: {e}")
            raise RepositoryError(f"Persistence error: {e}") from e
