import uuid
from pathlib import Path

import pytest

from src.core.archive import ArchiveError, FileSystemRepository
from src.core.models import AnalyticsRun


@pytest.fixture
def temp_archive_dir(tmp_path: Path) -> str:
    """Fixture providing a temporary directory for archives."""
    archive_dir = tmp_path / "archives"
    return str(archive_dir)

def test_repository_lifecycle(temp_archive_dir: str):
    """
    Tests the complete lifecycle of saving, retrieving, and listing
    domain models using the FileSystemRepository.
    """
    # 1. Initialize Repository
    repo = FileSystemRepository(temp_archive_dir, AnalyticsRun)

    # 2. Create Domain Models
    run1 = AnalyticsRun(
        strategy_output="Strategy A",
        anomalies_summary={"Shorts": 2}
    )
    run2 = AnalyticsRun(
        strategy_output="Strategy B",
        anomalies_summary={"Long": 1, "Shorts": 5}
    )

    # 3. Save
    repo.save(run1)
    repo.save(run2)

    # Verify files created
    dir_path = Path(temp_archive_dir)
    files = list(dir_path.glob("*.json"))
    assert len(files) == 2, "Expected 2 JSON files to be created"

    # 4. Retrieve and verify integrity
    retrieved_run1 = repo.get(run1.id)
    assert retrieved_run1 is not None
    assert retrieved_run1.id == run1.id
    assert retrieved_run1.strategy_output == "Strategy A"
    assert retrieved_run1.anomalies_summary == {"Shorts": 2}

    # 5. List all
    all_runs = repo.list_all()
    assert len(all_runs) == 2
    ids = {r.id for r in all_runs}
    assert run1.id in ids
    assert run2.id in ids

def test_repository_get_nonexistent(temp_archive_dir: str):
    """Retrieving a non-existent ID should return None."""
    repo = FileSystemRepository(temp_archive_dir, AnalyticsRun)
    assert repo.get(str(uuid.uuid4())) is None

def test_repository_invalid_dir():
    """Testing error handling when archive dir cannot be created."""
    with pytest.raises(ArchiveError):
        # /root should be unwritable and trigger OSError -> ArchiveError
        FileSystemRepository("/root/invalid_archive_dir", AnalyticsRun)

def test_repository_save_without_id(temp_archive_dir: str):
    """Saving an entity missing an 'id' should raise an error."""
    repo = FileSystemRepository(temp_archive_dir, AnalyticsRun)

    class BadEntity:
        pass

    bad_entity = BadEntity()

    with pytest.raises(ArchiveError, match="Entity must have an 'id' attribute"):
        # We bypass type checking purely for runtime error verification
        repo.save(bad_entity)  # type: ignore
