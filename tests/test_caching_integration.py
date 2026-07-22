import pytest
import pandas as pd
from src.core.caching import FileDataFrameRepository, CachedDataIngestionService
from src.core.interfaces import DataIngestionService

class MockIngestionService(DataIngestionService):
    def __init__(self, data: pd.DataFrame):
        self.data = data
        self.call_count = 0

    async def ingest_data(self) -> pd.DataFrame:
        self.call_count += 1
        return self.data

@pytest.mark.asyncio
async def test_cached_data_ingestion_service_integration(tmp_path):
    # Setup test data and temporary file
    test_filepath = tmp_path / "test_cache.json"
    test_df = pd.DataFrame({"col1": [1, 2], "col2": ["A", "B"]})

    # Initialize inner service and repository
    inner_service = MockIngestionService(data=test_df)
    repo = FileDataFrameRepository(filepath=str(test_filepath))
    cached_service = CachedDataIngestionService(inner=inner_service, repository=repo)

    # First call: cache miss, should call inner and save to repo
    assert inner_service.call_count == 0
    result1 = await cached_service.ingest_data()
    assert inner_service.call_count == 1
    pd.testing.assert_frame_equal(result1, test_df)
    assert test_filepath.exists()

    # Verify data in repository
    repo_data = repo.get()
    assert repo_data is not None
    pd.testing.assert_frame_equal(repo_data, test_df)

    # Second call: cache hit, should NOT call inner service
    result2 = await cached_service.ingest_data()
    assert inner_service.call_count == 1  # Still 1
    pd.testing.assert_frame_equal(result2, test_df)
