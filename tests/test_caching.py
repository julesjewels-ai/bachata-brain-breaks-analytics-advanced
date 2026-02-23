"""
Integration tests for caching mechanisms.
"""
import pytest
import shutil
import asyncio
from pathlib import Path
from unittest.mock import MagicMock
from src.core.caching import FileCacheBackend, CachedAIService
from src.core.models import VideoAnalysisInput
from src.core.interfaces import AIService

TEST_CACHE_DIR = "tests/temp_cache"


@pytest.fixture
def cache_backend():
    # Setup
    backend = FileCacheBackend(TEST_CACHE_DIR)
    yield backend
    # Teardown
    if Path(TEST_CACHE_DIR).exists():
        shutil.rmtree(TEST_CACHE_DIR)


@pytest.fixture
def mock_ai_service():
    service = MagicMock(spec=AIService)
    service.analyze_semantics.return_value = "Analyzed Result"

    # Setup async generator mock
    async def async_gen(videos):
        yield "Analyzed "
        yield "Stream "
        yield "Result"

    service.analyze_stream.side_effect = async_gen
    return service


def test_file_backend_set_get(cache_backend):
    key = "test_key"
    value = "test_value"
    cache_backend.set(key, value)
    assert cache_backend.get(key) == value
    assert cache_backend.get("non_existent") is None


def test_cached_service_semantics_miss(cache_backend, mock_ai_service):
    cached_service = CachedAIService(mock_ai_service, cache_backend)
    input_data = [VideoAnalysisInput(
        video_id="vid_1", title="Test", views=100,
        retention_avg_pct=50.0, type="Shorts"
    )]

    # First call - Miss
    result = cached_service.analyze_semantics(input_data)
    assert result == "Analyzed Result"
    mock_ai_service.analyze_semantics.assert_called_once()

    # Verify cache write
    key = cached_service._hash(input_data)
    assert cache_backend.get(key) == "Analyzed Result"


def test_cached_service_semantics_hit(cache_backend, mock_ai_service):
    cached_service = CachedAIService(mock_ai_service, cache_backend)
    input_data = [VideoAnalysisInput(
        video_id="vid_1", title="Test", views=100,
        retention_avg_pct=50.0, type="Shorts"
    )]

    # Pre-populate cache
    key = cached_service._hash(input_data)
    cache_backend.set(key, "Cached Result")

    # Call - Hit
    result = cached_service.analyze_semantics(input_data)
    assert result == "Cached Result"
    mock_ai_service.analyze_semantics.assert_not_called()


def test_cached_service_stream_miss(cache_backend, mock_ai_service):
    cached_service = CachedAIService(mock_ai_service, cache_backend)
    input_data = [VideoAnalysisInput(
        video_id="vid_1", title="Test", views=100,
        retention_avg_pct=50.0, type="Shorts"
    )]

    async def run_test():
        # First call - Miss
        chunks = []
        async for chunk in cached_service.analyze_stream(input_data):
            chunks.append(chunk)

        assert "".join(chunks) == "Analyzed Stream Result"

        # Verify cache write
        key = cached_service._hash(input_data)
        assert cache_backend.get(key) == "Analyzed Stream Result"

    asyncio.run(run_test())


def test_cached_service_stream_hit(cache_backend, mock_ai_service):
    cached_service = CachedAIService(mock_ai_service, cache_backend)
    input_data = [VideoAnalysisInput(
        video_id="vid_1", title="Test", views=100,
        retention_avg_pct=50.0, type="Shorts"
    )]

    # Pre-populate cache
    key = cached_service._hash(input_data)
    cache_backend.set(key, "Cached Stream Result")

    async def run_test():
        # Call - Hit
        chunks = []
        async for chunk in cached_service.analyze_stream(input_data):
            chunks.append(chunk)

        # The cache implementation splits by space and appends space.
        # "Cached Stream Result" -> ["Cached", "Stream", "Result"]
        # -> "Cached ", "Stream ", "Result "
        assert "".join(chunks).strip() == "Cached Stream Result"

    asyncio.run(run_test())
