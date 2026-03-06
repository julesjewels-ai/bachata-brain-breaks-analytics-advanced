"""
Generic Repository implementation.
"""
import json
import logging
from typing import List, Type
from pydantic import ValidationError
from src.core.interfaces import T, Repository

logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    """Domain-specific exception for repository operations."""
    pass


class JsonlRepository(Repository[T]):
    """
    Generic repository for persisting Pydantic models to JSONL format.
    """
    def __init__(self, filepath: str, model_class: Type[T]):
        self.filepath = filepath
        self.model_class = model_class

    def save(self, entity: T) -> None:
        """
        Saves the entity as a JSON line.
        """
        try:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                # Use model_dump(mode='json') to handle datetime serialization
                json_str = json.dumps(entity.model_dump(mode='json'))
                f.write(json_str + '\n')
        except Exception as e:
            logger.error("Failed to write to %s: %s", self.filepath, e)
            raise RepositoryError(f"Persistence error: {e}") from e

    def get_all(self) -> List[T]:
        """
        Retrieves all entities from the JSONL file.
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
                        entities.append(self.model_class.model_validate(data))
                    except (json.JSONDecodeError, ValidationError) as e:
                        logger.warning(
                            "Failed to parse or validate line in %s: %s",
                            self.filepath, e
                        )
                        continue
            return entities
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.error("Failed to read from %s: %s", self.filepath, e)
            raise RepositoryError(f"Read error: {e}") from e
