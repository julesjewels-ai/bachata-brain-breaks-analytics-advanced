"""
Repository pattern for domain models.
Provides abstract interfaces and concrete implementations for persistence.
"""
import json
import logging
from typing import Protocol, TypeVar
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel, contravariant=True)


class RepositoryError(Exception):
    """
    Domain-specific exception for repository failures.
    Ensures that persistence errors are handled gracefully.
    """
    pass


class Repository(Protocol[T]):
    """
    Generic Repository protocol for data persistence.
    """
    def save(self, entity: T) -> None:
        """
        Persists a single domain model entity.
        """
        ...


class JsonlRepository(Repository[T]):
    """
    Concrete repository implementation that appends Pydantic models to a JSONL file.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def save(self, entity: T) -> None:
        """
        Appends the model to the JSONL file.
        Raises RepositoryError on file IO failures.
        """
        try:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                # Use mode='json' to ensure proper serialization of complex types like datetime
                json_str = json.dumps(entity.model_dump(mode='json'))
                f.write(json_str + '\n')
        except IOError as e:
            logger.error(f"File IO error while saving to {self.filepath}: {e}")
            raise RepositoryError(f"Failed to save entity to {self.filepath}") from e
        except Exception as e:
            logger.error(f"Unexpected error while saving entity: {e}")
            raise RepositoryError(f"Unexpected error: {e}") from e
