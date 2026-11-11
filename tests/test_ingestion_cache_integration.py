"""
Integration tests for the Data Ingestion Cache utility.
"""
from pathlib import Path
from unittest.mock import AsyncMock

import pandas as pd
import pytest

from src.core.ingestion_cache import (
    CachedDataIngestionService,
    DataFrameCacheRepository,
)


@pytest.mark.asyncio
async def test_ingestion_cache_integration(tmp_path: Path) -> None:
    # 1. Setup mock inner service
    mock_inner_service = AsyncMock()

    # Mock data to be returned by the inner service
    mock_data = pd.DataFrame({
        "video_id": ["v1", "v2"],
        "title": ["Test 1", "Test 2"],
        "views": [100, 200]
    })
    mock_inner_service.ingest_data.return_value = mock_data

    # 2. Setup the cache repository and decorator
    cache_filepath = tmp_path / "test_ingestion.pkl"
    repository = DataFrameCacheRepository(cache_filepath)
    cached_service = CachedDataIngestionService(
        inner=mock_inner_service,
        repository=repository
    )

    # 3. First call: Cache miss. Should call inner service and save to cache.
    result_miss = await cached_service.ingest_data()

    assert mock_inner_service.ingest_data.call_count == 1
    pd.testing.assert_frame_equal(result_miss, mock_data)
    assert cache_filepath.exists()

    # 4. Modify inner mock to prove it won't be called on cache hit
    mock_inner_service.ingest_data.reset_mock()
    mock_inner_service.ingest_data.return_value = pd.DataFrame()

    # 5. Second call: Cache hit. Should NOT call inner service, and load from cache.
    result_hit = await cached_service.ingest_data()

    assert mock_inner_service.ingest_data.call_count == 0
    pd.testing.assert_frame_equal(result_hit, mock_data)
