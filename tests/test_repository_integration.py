"""
Integration tests for the JsonlRepository.
"""
import os
import json
import pytest
from unittest.mock import patch
from pydantic import BaseModel

from src.core.repository import JsonlRepository, RepositoryError

class DummyModel(BaseModel):
    id: int
    name: str

@pytest.fixture
def temp_filepath(tmp_path):
    return str(tmp_path / "test_repo.jsonl")

def test_jsonl_repository_saves_all(temp_filepath):
    repo = JsonlRepository[DummyModel](temp_filepath)

    items = [
        DummyModel(id=1, name="Item 1"),
        DummyModel(id=2, name="Item 2"),
    ]

    repo.save_all(items)

    assert os.path.exists(temp_filepath)

    with open(temp_filepath, 'r') as f:
        lines = f.readlines()

    assert len(lines) == 2
    assert json.loads(lines[0]) == {"id": 1, "name": "Item 1"}
    assert json.loads(lines[1]) == {"id": 2, "name": "Item 2"}

def test_jsonl_repository_raises_repository_error_on_failure(temp_filepath):
    # Pass a directory path to force an OSError when trying to open it as a file
    # or patch open to raise OSError
    repo = JsonlRepository[DummyModel](temp_filepath)
    items = [DummyModel(id=1, name="Test")]

    with patch("builtins.open", side_effect=OSError("Permission denied")):
        with pytest.raises(RepositoryError, match="Persistence error: Permission denied"):
            repo.save_all(items)
