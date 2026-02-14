"""
Unit tests for the Caching Module.
"""
import pytest
import asyncio
from typing import AsyncGenerator, List
from unittest.mock import Mock, AsyncMock, call
from datetime import datetime, timedelta
from src.core.caching import InMemoryCacheBackend, CachedAIService, SerializationError
from src.core.interfaces import AIService
from src.core.models import VideoAnalysisInput

# --- Fixtures ---

@pytest.fixture
def mock_video_input() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="vid_1",
            title="Bachata Demo",
            views=1000,
            retention_avg_pct=85.5,
            type="Long"
        )
    ]

@pytest.fixture
def cache_backend():
    return InMemoryCacheBackend()

@pytest.fixture
def mock_ai_service():
    service = Mock(spec=AIService)
    service.analyze_semantics.return_value = "Analyzed Content"

    async def stream_gen(videos):
        yield "Chunk 1"
        yield "Chunk 2"

    # Use side_effect to return the generator when called
    service.analyze_stream = Mock(side_effect=stream_gen)
    return service

@pytest.fixture
def cached_service(mock_ai_service, cache_backend):
    return CachedAIService(mock_ai_service, cache_backend)

# --- InMemoryCacheBackend Tests ---

def test_cache_set_get(cache_backend):
    """Test basic set and get operations."""
    cache_backend.set("key1", "value1")
    assert cache_backend.get("key1") == "value1"
    assert cache_backend.get("non_existent") is None

def test_cache_expiration(cache_backend, mocker):
    """Test that expired items are not returned."""
    # Freeze time
    mock_now = datetime(2023, 1, 1, 12, 0, 0)

    # Patch the imported datetime in src.core.caching
    mock_datetime = mocker.patch('src.core.caching.datetime')
    mock_datetime.now.return_value = mock_now

    # Set with 60s TTL
    cache_backend.set("key_ttl", "value_ttl", ttl=60)

    # Immediate check (time hasn't changed)
    assert cache_backend.get("key_ttl") == "value_ttl"

    # Advance time past TTL
    mock_datetime.now.return_value = mock_now + timedelta(seconds=61)
    assert cache_backend.get("key_ttl") is None

def test_cache_delete(cache_backend):
    """Test deleting items."""
    cache_backend.set("key_del", "value_del")
    cache_backend.delete("key_del")
    assert cache_backend.get("key_del") is None

def test_cache_clear(cache_backend):
    """Test clearing the cache."""
    cache_backend.set("k1", "v1")
    cache_backend.set("k2", "v2")
    cache_backend.clear()
    assert cache_backend.get("k1") is None
    assert cache_backend.get("k2") is None

# --- CachedAIService Tests ---

def test_analyze_semantics_miss(cached_service, mock_ai_service, mock_video_input):
    """Test cache miss calls inner service and caches result."""
    result = cached_service.analyze_semantics(mock_video_input)

    assert result == "Analyzed Content"
    mock_ai_service.analyze_semantics.assert_called_once_with(mock_video_input)

    # Check it was cached (key generation is internal detail, but we can check if a key exists)
    assert any(k.startswith("semantics:") for k in cached_service.cache._store.keys())

def test_analyze_semantics_hit(cached_service, mock_ai_service, mock_video_input):
    """Test cache hit returns cached value without calling inner service."""
    # Prime cache
    cached_service.analyze_semantics(mock_video_input)
    mock_ai_service.analyze_semantics.reset_mock()

    # Call again
    result = cached_service.analyze_semantics(mock_video_input)

    assert result == "Analyzed Content"
    mock_ai_service.analyze_semantics.assert_not_called()

@pytest.mark.asyncio
async def test_analyze_stream_miss(cached_service, mock_video_input):
    """Test async stream cache miss accumulates and caches."""
    chunks = []
    async for chunk in cached_service.analyze_stream(mock_video_input):
        chunks.append(chunk)

    assert chunks == ["Chunk 1", "Chunk 2"]

    # Verify it is cached as full string
    cached_keys = list(cached_service.cache._store.keys())
    stream_key = next(k for k in cached_keys if k.startswith("stream:"))
    assert cached_service.cache.get(stream_key) == "Chunk 1Chunk 2"

@pytest.mark.asyncio
async def test_analyze_stream_hit(cached_service, mock_ai_service, mock_video_input):
    """Test async stream cache hit replays from cache."""
    # Prime cache by calling it once
    async for _ in cached_service.analyze_stream(mock_video_input):
        pass

    # Reset mock
    mock_ai_service.analyze_stream.reset_mock()

    # Call again (Hit)
    chunks = []
    async for chunk in cached_service.analyze_stream(mock_video_input):
        chunks.append(chunk)

    assert "".join(chunks) == "Chunk 1Chunk 2"

    # Should NOT have called inner service again
    mock_ai_service.analyze_stream.assert_not_called()

def test_generate_key_consistency(cached_service, mock_video_input):
    """Test that key generation is consistent."""
    key1 = cached_service._generate_key(mock_video_input)
    key2 = cached_service._generate_key(mock_video_input)
    assert key1 == key2

    v1 = mock_video_input[0]
    v2 = VideoAnalysisInput(video_id="vid_2", title="Other", views=10, retention_avg_pct=10.0, type="Shorts")

    input_a = [v1, v2]
    input_b = [v1, v2]

    assert cached_service._generate_key(input_a) == cached_service._generate_key(input_b)
