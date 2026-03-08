"""
Concrete implementations of the Repository protocol.
"""
import json
import logging
from typing import Type, List, Generic
from src.core.interfaces import T

logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    """Domain-specific exception for repository failures."""
    pass


class JsonlRepository(Generic[T]):
    """
    Concrete implementation of the Repository protocol that persists data to JSONL files.
    """

    def __init__(self, filepath: str, model_cls: Type[T]):
        self.filepath = filepath
        self.model_cls = model_cls

    def save(self, entity: T) -> None:
        """
        Saves a single entity by appending to the JSONL file.
        """
        try:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                json_str = json.dumps(entity.model_dump(mode='json'))
                f.write(json_str + '\n')
        except Exception as e:
            logger.error("Failed to write entity to %s: %s", self.filepath, e)
            raise RepositoryError(f"Persistence error: {e}") from e

    def save_all(self, entities: List[T]) -> None:
        """
        Saves a list of entities by appending them to the JSONL file.
        """
        if not entities:
            return

        try:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                for entity in entities:
                    json_str = json.dumps(entity.model_dump(mode='json'))
                    f.write(json_str + '\n')
        except Exception as e:
            logger.error(
                "Failed to write %d entities to %s: %s",
                len(entities), self.filepath, e
            )
            raise RepositoryError(f"Persistence error: {e}") from e

    def get_all(self) -> List[T]:
        """
        Retrieves all entities from the JSONL file.
        Returns an empty list if the file does not exist.
        """
        results: List[T] = []
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    results.append(self.model_cls.model_validate(data))
            return results
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.error("Failed to read from %s: %s", self.filepath, e)
            raise RepositoryError(f"Read error: {e}") from e
