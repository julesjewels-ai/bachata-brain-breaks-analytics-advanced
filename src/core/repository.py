"""
Repository implementations for data persistence.
"""
import json
import logging
from typing import List, Type

from src.core.interfaces import Repository, T

logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    """Domain-specific exception for repository failures."""
    pass


class JsonLinesRepository(Repository[T]):
    """
    Generic repository for persisting BaseModel entities to a JSONL file.
    """

    def __init__(self, filepath: str, model_class: Type[T]) -> None:
        self.filepath = filepath
        self.model_class = model_class

    def add(self, entity: T) -> None:
        """
        Adds a new entity to the repository.
        """
        try:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                # Use model_dump with json mode to handle datetimes correctly
                data = entity.model_dump(mode='json')
                f.write(json.dumps(data) + '\n')
        except Exception as e:
            logger.error("Failed to add entity to %s: %s", self.filepath, e)
            raise RepositoryError(f"Failed to add entity: {e}") from e

    def get_all(self) -> List[T]:
        """
        Retrieves all entities from the repository.
        """
        entities: List[T] = []
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entity = self.model_class.model_validate(data)
                        entities.append(entity)
                    except Exception as parse_err:
                        logger.warning(
                            "Failed to parse line in %s: %s",
                            self.filepath, parse_err
                        )
            return entities
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.error(
                "Failed to retrieve entities from %s: %s", self.filepath, e
            )
            raise RepositoryError(
                f"Failed to retrieve entities: {e}"
            ) from e
