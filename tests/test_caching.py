"""
Tests for the caching module.
"""
import pytest
import time
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, call
from src.core.caching import FileCacheBackend, CachedAIService, CacheReadError, CacheWriteError
from src.core.models import VideoAnalysisInput
from src.core.interfaces import AIService, CacheBackend

# --- FileCacheBackend Tests ---

def test_file_cache_backend_set_get(tmp_path):
    """Test setting and getting a value from the file cache."""
    cache = FileCacheBackend(cache_dir=str(tmp_path))
    key = "test_key"
    value = {"data": 123}

    cache.set(key, value)
    retrieved = cache.get(key)

    assert retrieved == value

def test_file_cache_backend_expiry(tmp_path):
    """Test that expired cache items are not returned."""
    cache = FileCacheBackend(cache_dir=str(tmp_path))
    key = "expired_key"
    value = "data"

    # Set with a very short TTL
    cache.set(key, value, ttl=0.1)

    # Wait for expiry
    time.sleep(0.2)

    retrieved = cache.get(key)
    assert retrieved is None

def test_file_cache_backend_miss(tmp_path):
    """Test getting a non-existent key."""
    cache = FileCacheBackend(cache_dir=str(tmp_path))
    assert cache.get("missing_key") is None

def test_file_cache_backend_corrupted_file(tmp_path):
    """Test that corrupted JSON raises CacheReadError."""
    cache = FileCacheBackend(cache_dir=str(tmp_path))
    key = "corrupt_key"

    # Create corrupted file
    file_path = tmp_path / f"{key}.json"
    file_path.write_text("{invalid_json")

    with pytest.raises(CacheReadError):
        cache.get(key)

# --- CachedAIService Tests ---

@pytest.fixture
def mock_delegate():
    """Mock for AIService."""
    delegate = Mock(spec=AIService)
    delegate.analyze_semantics.return_value = "Delegate Result"

    # Setup async generator for analyze_stream
    async def async_gen(videos):
        yield "Stream"
        yield " "
        yield "Result"
    delegate.analyze_stream = async_gen

    return delegate

@pytest.fixture
def mock_cache():
    """Mock for CacheBackend."""
    return Mock(spec=CacheBackend)

@pytest.fixture
def sample_videos():
    """Sample video input data."""
    return [
        VideoAnalysisInput(
            video_id="vid_123",
            title="Test Video",
            views=1000,
            retention_avg_pct=50.0,
            type="Long"
        )
    ]

def test_analyze_semantics_cache_miss(mock_delegate, mock_cache, sample_videos):
    """Test analyze_semantics when cache is empty."""
    service = CachedAIService(delegate=mock_delegate, cache=mock_cache)
    mock_cache.get.return_value = None

    result = service.analyze_semantics(sample_videos)

    assert result == "Delegate Result"
    mock_delegate.analyze_semantics.assert_called_once_with(sample_videos)
    # Verify cache was set
    mock_cache.set.assert_called_once()
    args, _ = mock_cache.set.call_args
    assert args[1] == "Delegate Result"

def test_analyze_semantics_cache_hit(mock_delegate, mock_cache, sample_videos):
    """Test analyze_semantics when cache has value."""
    service = CachedAIService(delegate=mock_delegate, cache=mock_cache)
    mock_cache.get.return_value = "Cached Result"

    result = service.analyze_semantics(sample_videos)

    assert result == "Cached Result"
    mock_delegate.analyze_semantics.assert_not_called()
    mock_cache.set.assert_not_called()

def test_analyze_semantics_cache_error(mock_delegate, mock_cache, sample_videos):
    """Test graceful degradation when cache raises error."""
    service = CachedAIService(delegate=mock_delegate, cache=mock_cache)
    mock_cache.get.side_effect = CacheReadError("Read Failed")
    mock_cache.set.side_effect = CacheWriteError("Write Failed")

    # Should not raise, but call delegate and return result
    result = service.analyze_semantics(sample_videos)

    assert result == "Delegate Result"
    mock_delegate.analyze_semantics.assert_called_once()

@pytest.mark.asyncio
async def test_analyze_stream_cache_miss_write_through(mock_delegate, mock_cache, sample_videos):
    """Test analyze_stream when cache is empty (delegates and caches)."""
    service = CachedAIService(delegate=mock_delegate, cache=mock_cache)
    mock_cache.get.return_value = None

    results = []
    async for token in service.analyze_stream(sample_videos):
        results.append(token)

    assert "".join(results) == "Stream Result"

    # Verify cache was set with full result
    mock_cache.set.assert_called_once()
    args, _ = mock_cache.set.call_args
    assert args[1] == "Stream Result"

@pytest.mark.asyncio
async def test_analyze_stream_cache_hit(mock_delegate, mock_cache, sample_videos):
    """Test analyze_stream when cache has value (streams from cache)."""
    service = CachedAIService(delegate=mock_delegate, cache=mock_cache)
    mock_cache.get.return_value = "Cached Stream Result"

    results = []
    async for token in service.analyze_stream(sample_videos):
        results.append(token)

    assert "".join(results) == "Cached Stream Result"

    # Verify delegate was NOT used
    # Since we replaced the method with a function, we can check if that function was used?
    # No, we can't easily check 'called' on a function unless we wrap it.
    # But result differs ("Cached..." vs "Stream..."), so we know correct path was taken.
    mock_cache.set.assert_not_called()

@pytest.mark.asyncio
async def test_analyze_stream_cache_error(mock_delegate, mock_cache, sample_videos):
    """Test graceful degradation when cache raises error during stream."""
    service = CachedAIService(delegate=mock_delegate, cache=mock_cache)
    mock_cache.get.side_effect = CacheReadError("Read Failed")
    mock_cache.set.side_effect = CacheWriteError("Write Failed")

    results = []
    async for token in service.analyze_stream(sample_videos):
        results.append(token)

    assert "".join(results) == "Stream Result"
    # Should not crash despite cache errors
