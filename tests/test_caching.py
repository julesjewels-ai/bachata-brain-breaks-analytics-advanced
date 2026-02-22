"""
Tests for caching services.
"""
import pytest
import shutil
import asyncio
from pathlib import Path
from unittest.mock import MagicMock
from src.core.caching import FileCacheBackend, CachedAIService
from src.core.models import VideoAnalysisInput
from src.core.interfaces import AIService

# --- Fixtures ---

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Provides a temporary directory for cache testing."""
    cache_dir = tmp_path / "cache_test"
    yield cache_dir
    # Cleanup
    if cache_dir.exists():
        shutil.rmtree(cache_dir)

@pytest.fixture
def mock_ai_service():
    """Mocks the AIService."""
    service = MagicMock(spec=AIService)
    return service

@pytest.fixture
def sample_videos():
    """Provides sample video inputs."""
    return [
        VideoAnalysisInput(
            video_id="vid_1",
            title="Test Video",
            views=100,
            retention_avg_pct=50.0,
            type="Long"
        )
    ]

# --- FileCacheBackend Tests ---

def test_file_cache_backend_init(temp_cache_dir):
    """Test cache directory creation."""
    FileCacheBackend(cache_dir=str(temp_cache_dir))
    assert temp_cache_dir.exists()

def test_file_cache_backend_set_get(temp_cache_dir):
    """Test setting and getting values."""
    backend = FileCacheBackend(cache_dir=str(temp_cache_dir))
    key = "test_key"
    value = "test_value"

    # Should result in None initially
    assert backend.get(key) is None

    # Set value
    backend.set(key, value)

    # Get value
    assert backend.get(key) == value

def test_file_cache_backend_hashing(temp_cache_dir):
    """Test that keys are hashed."""
    backend = FileCacheBackend(cache_dir=str(temp_cache_dir))
    key = "complex_key_with_special_chars_!@#"
    value = "data"

    backend.set(key, value)

    files = list(temp_cache_dir.glob("*.txt"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8") == value

# --- CachedAIService Tests ---

def test_cached_ai_service_semantics_miss(temp_cache_dir, mock_ai_service, sample_videos):
    """Test analyze_semantics on cache miss."""
    backend = FileCacheBackend(cache_dir=str(temp_cache_dir))
    cached_service = CachedAIService(service=mock_ai_service, cache=backend)

    expected_response = "AI Analysis Result"
    mock_ai_service.analyze_semantics.return_value = expected_response

    # First call - Miss
    result = cached_service.analyze_semantics(sample_videos)

    assert result == expected_response
    mock_ai_service.analyze_semantics.assert_called_once_with(sample_videos)

def test_cached_ai_service_semantics_hit(temp_cache_dir, mock_ai_service, sample_videos):
    """Test analyze_semantics on cache hit."""
    backend = FileCacheBackend(cache_dir=str(temp_cache_dir))
    cached_service = CachedAIService(service=mock_ai_service, cache=backend)

    expected_response = "AI Analysis Result"
    mock_ai_service.analyze_semantics.return_value = expected_response

    # Prime cache
    cached_service.analyze_semantics(sample_videos)
    mock_ai_service.analyze_semantics.reset_mock()

    # Second call - Hit
    result = cached_service.analyze_semantics(sample_videos)

    assert result == expected_response
    mock_ai_service.analyze_semantics.assert_not_called()

@pytest.mark.asyncio
async def test_cached_ai_service_stream_miss(temp_cache_dir, mock_ai_service, sample_videos):
    """Test analyze_stream on cache miss."""
    backend = FileCacheBackend(cache_dir=str(temp_cache_dir))
    cached_service = CachedAIService(service=mock_ai_service, cache=backend)

    # Mock async generator
    async def mock_gen(videos):
        yield "Part 1"
        yield "Part 2"

    mock_ai_service.analyze_stream.side_effect = mock_gen

    chunks = []
    async for chunk in cached_service.analyze_stream(sample_videos):
        chunks.append(chunk)

    assert chunks == ["Part 1", "Part 2"]

@pytest.mark.asyncio
async def test_cached_ai_service_stream_hit(temp_cache_dir, mock_ai_service, sample_videos):
    """Test analyze_stream on cache hit."""
    backend = FileCacheBackend(cache_dir=str(temp_cache_dir))
    cached_service = CachedAIService(service=mock_ai_service, cache=backend)

    # Mock async generator for first call
    async def mock_gen(videos):
        yield "Hello "
        yield "World"

    mock_ai_service.analyze_stream.side_effect = mock_gen

    # Prime cache
    async for _ in cached_service.analyze_stream(sample_videos):
        pass

    mock_ai_service.analyze_stream.reset_mock()

    # Second call - Hit
    chunks = []
    async for chunk in cached_service.analyze_stream(sample_videos):
        chunks.append(chunk)

    full_text = "".join(chunks)
    assert full_text == "Hello World"
    mock_ai_service.analyze_stream.assert_not_called()
