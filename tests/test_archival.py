import pytest
import pandas as pd
import os
import json
from pathlib import Path
from src.core.archival import FileArchiveRepository, StandardDataArchivalService, ArchivalError

def test_archival_service_integration(tmp_path):
    archive_dir = tmp_path / "archives"
    repository = FileArchiveRepository(str(archive_dir))
    service = StandardDataArchivalService(repository)

    df = pd.DataFrame({
        "video_id": ["v1", "v2"],
        "views": [100, 200]
    })

    metadata = service.archive(df)

    assert metadata.record_count == 2
    assert metadata.source_type == "system"

    # Verify files
    meta_path = repository._get_metadata_path(metadata.archive_id)
    data_path = repository._get_data_path(metadata.archive_id)

    assert meta_path.exists()
    assert data_path.exists()

    with open(meta_path, 'r') as f:
        meta_json = json.load(f)
        assert meta_json["archive_id"] == metadata.archive_id
        assert meta_json["record_count"] == 2

    df_loaded = pd.read_csv(data_path)
    assert len(df_loaded) == 2
    assert "video_id" in df_loaded.columns
    assert "views" in df_loaded.columns

def test_archival_service_exception(tmp_path):
    # Mocking read-only directory
    archive_dir = tmp_path / "archives"
    archive_dir.mkdir()
    os.chmod(str(archive_dir), 0o444)

    repository = FileArchiveRepository(str(archive_dir))
    service = StandardDataArchivalService(repository)

    df = pd.DataFrame({"video_id": ["v1"]})

    with pytest.raises(ArchivalError):
        service.archive(df)

    os.chmod(str(archive_dir), 0o755)

def test_archive_repository_get(tmp_path):
    archive_dir = tmp_path / "archives"
    repository = FileArchiveRepository(str(archive_dir))
    service = StandardDataArchivalService(repository)

    df = pd.DataFrame({"video_id": ["v1"]})
    metadata = service.archive(df)

    retrieved = repository.get(metadata.archive_id)
    assert retrieved is not None
    assert retrieved.archive_id == metadata.archive_id
    assert retrieved.record_count == 1
