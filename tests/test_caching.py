"""
Tests for the caching module.
"""
import pytest
import asyncio
from unittest.mock import Mock, MagicMock
from src.core.caching import FileCacheBackend, CachedAIService
from src.core.models import VideoAnalysisInput
from src.core.interfaces import AIService, CacheBackend

# Test Data
@pytest.fixture
def sample_videos():
    return [
        VideoAnalysisInput(
            video_id="vid_1", title="Test Video", views=100, retention_avg_pct=50.0, type="Long"
        )
    ]

# FileCacheBackend Tests
def test_file_cache_backend_init(tmp_path):
    cache_dir = tmp_path / ".cache"
    backend = FileCacheBackend(cache_dir=str(cache_dir))
    assert cache_dir.exists()

def test_file_cache_backend_set_get(tmp_path):
    cache_dir = tmp_path / ".cache"
    backend = FileCacheBackend(cache_dir=str(cache_dir))

    key = "test_key"
    value = "test_value"

    backend.set(key, value)
    assert backend.get(key) == value

    # Check file content
    assert (cache_dir / f"{key}.json").read_text(encoding="utf-8") == value

def test_file_cache_backend_get_miss(tmp_path):
    cache_dir = tmp_path / ".cache"
    backend = FileCacheBackend(cache_dir=str(cache_dir))
    assert backend.get("missing_key") is None

# CachedAIService Tests
@pytest.fixture
def mock_ai_service():
    service = Mock(spec=AIService)
    service.analyze_semantics.return_value = "AI Analysis Result"

    # Mock async generator for analyze_stream
    async def stream_gen(videos):
        yield "AI "
        yield "Stream "
        yield "Result"

    # We need to mock the method to return the async generator
    service.analyze_stream = MagicMock(side_effect=stream_gen)
    return service

@pytest.fixture
def mock_cache_backend():
    return Mock(spec=CacheBackend)

def test_cached_ai_service_semantics_miss(mock_ai_service, mock_cache_backend, sample_videos):
    mock_cache_backend.get.return_value = None
    service = CachedAIService(service=mock_ai_service, cache=mock_cache_backend)

    result = service.analyze_semantics(sample_videos)

    assert result == "AI Analysis Result"
    mock_ai_service.analyze_semantics.assert_called_once_with(sample_videos)
    mock_cache_backend.set.assert_called_once()

def test_cached_ai_service_semantics_hit(mock_ai_service, mock_cache_backend, sample_videos):
    mock_cache_backend.get.return_value = "Cached Result"
    service = CachedAIService(service=mock_ai_service, cache=mock_cache_backend)

    result = service.analyze_semantics(sample_videos)

    assert result == "Cached Result"
    mock_ai_service.analyze_semantics.assert_not_called()

@pytest.mark.asyncio
async def test_cached_ai_service_stream_miss(mock_ai_service, mock_cache_backend, sample_videos):
    mock_cache_backend.get.return_value = None
    service = CachedAIService(service=mock_ai_service, cache=mock_cache_backend)

    chunks = []
    async for chunk in service.analyze_stream(sample_videos):
        chunks.append(chunk)

    assert "".join(chunks) == "AI Stream Result"
    mock_cache_backend.set.assert_called_once()
    args, _ = mock_cache_backend.set.call_args
    assert args[1] == "AI Stream Result"

@pytest.mark.asyncio
async def test_cached_ai_service_stream_hit(mock_ai_service, mock_cache_backend, sample_videos):
    mock_cache_backend.get.return_value = "Cached Stream Result"
    service = CachedAIService(service=mock_ai_service, cache=mock_cache_backend)

    chunks = []
    async for chunk in service.analyze_stream(sample_videos):
        chunks.append(chunk)

    assert "".join(chunks) == "Cached Stream Result"
    mock_ai_service.analyze_stream.assert_not_called()
