"""
Archive storage implementation for domain models.
"""
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from src.core.interfaces import Repository

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class ArchiveError(Exception):
    """Domain-specific exception for archive/repository operations."""

class FileSystemRepository(Repository[T]):
    """
    File-based implementation of the Repository protocol.
    Serializes Pydantic domain models to JSON and stores them in a directory.
    """
    def __init__(self, archive_dir: str, model_class: type[T]) -> None:
        self.archive_dir = Path(archive_dir)
        self.model_class = model_class
        try:
            self.archive_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error("Failed to create archive directory %s: %s", archive_dir, e)
            raise ArchiveError(f"Failed to create archive directory: {e}") from e

    def _get_filepath(self, entity_id: str) -> Path:
        """Generates the file path for a given entity ID."""
        return self.archive_dir / f"{entity_id}.json"

    def save(self, entity: T) -> None:
        """Saves an entity to the repository as a JSON file."""
        if not hasattr(entity, 'id'):
            raise ArchiveError("Entity must have an 'id' attribute to be saved.")

        filepath = self._get_filepath(str(entity.id))
        try:
            # Pydantic's model_dump_json handles datetime serialization
            json_data = entity.model_dump_json(indent=2)
            filepath.write_text(json_data, encoding='utf-8')
        except Exception as e:
            logger.error("Failed to save entity %s to %s: %s", entity.id, filepath, e)
            raise ArchiveError(f"Failed to save entity {entity.id}: {e}") from e

    def get(self, id: str) -> T | None:
        """Retrieves an entity by its ID."""
        filepath = self._get_filepath(id)
        if not filepath.exists():
            return None

        try:
            json_data = filepath.read_text(encoding='utf-8')
            return self.model_class.model_validate_json(json_data)
        except Exception as e:
            logger.error("Failed to load entity %s from %s: %s", id, filepath, e)
            raise ArchiveError(f"Failed to load entity {id}: {e}") from e

    def list_all(self) -> Sequence[T]:
        """Lists all stored entities."""
        entities = []
        try:
            for filepath in self.archive_dir.glob("*.json"):
                if filepath.is_file():
                    try:
                        json_data = filepath.read_text(encoding='utf-8')
                        entity = self.model_class.model_validate_json(json_data)
                        entities.append(entity)
                    except Exception as e:  # noqa: BLE001
                        logger.warning("Skipping invalid entity file %s: %s", filepath, e)
        except Exception as e:
            logger.error("Failed to list entities in %s: %s", self.archive_dir, e)
            raise ArchiveError(f"Failed to list entities: {e}") from e

        return entities
