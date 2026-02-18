import pytest
import shutil
import json
from pathlib import Path
from typing import AsyncGenerator, List, Any
from unittest.mock import Mock, AsyncMock, MagicMock

from src.core.caching import FileCacheBackend, CachedAIService, CacheReadError
from src.core.models import VideoAnalysisInput
from src.core.interfaces import AIService

# Fixture for temporary cache directory
@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> str:
    cache_dir = tmp_path / ".cache_test"
    yield str(cache_dir)
    if cache_dir.exists():
        shutil.rmtree(cache_dir)

# Fixture for FileCacheBackend
@pytest.fixture
def file_cache(temp_cache_dir: str) -> FileCacheBackend:
    return FileCacheBackend(cache_dir=temp_cache_dir)

# Fixture for Mock AIService
@pytest.fixture
def mock_ai_service(mocker: Any) -> Mock:
    service = Mock(spec=AIService)
    service.analyze_semantics.return_value = "Analyzed Content"

    # Mocking async generator
    async def async_gen(videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        yield "Analyzed "
        yield "Content"

    service.analyze_stream = MagicMock(side_effect=async_gen)
    return service

# Fixture for VideoAnalysisInput
@pytest.fixture
def sample_videos() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="vid_1",
            title="Test Video",
            views=1000,
            retention_avg_pct=50.0,
            type="Long"
        )
    ]

def test_file_cache_backend_integration(file_cache: FileCacheBackend, temp_cache_dir: str) -> None:
    key = "test_key"
    value = "test_value"

    # Test Set
    file_cache.set(key, value)

    # Verify file exists
    cache_path = Path(temp_cache_dir)
    assert any(cache_path.iterdir())

    # Test Get
    retrieved = file_cache.get(key)
    assert retrieved == value

    # Test Miss
    assert file_cache.get("non_existent") is None

def test_cached_ai_service_semantics_miss(
    file_cache: FileCacheBackend,
    mock_ai_service: Mock,
    sample_videos: List[VideoAnalysisInput]
) -> None:
    cached_service = CachedAIService(service=mock_ai_service, cache=file_cache)

    # First call (Miss)
    result = cached_service.analyze_semantics(sample_videos)

    assert result == "Analyzed Content"
    mock_ai_service.analyze_semantics.assert_called_once()

    # Verify it was written to cache
    key = cached_service._generate_key(sample_videos)
    assert file_cache.get(key) == "Analyzed Content"

def test_cached_ai_service_semantics_hit(
    file_cache: FileCacheBackend,
    mock_ai_service: Mock,
    sample_videos: List[VideoAnalysisInput]
) -> None:
    cached_service = CachedAIService(service=mock_ai_service, cache=file_cache)

    # Pre-populate cache
    key = cached_service._generate_key(sample_videos)
    file_cache.set(key, "Cached Result")

    # Call service
    result = cached_service.analyze_semantics(sample_videos)

    assert result == "Cached Result"
    mock_ai_service.analyze_semantics.assert_not_called()

@pytest.mark.asyncio
async def test_cached_ai_service_stream_miss(
    file_cache: FileCacheBackend,
    mock_ai_service: Mock,
    sample_videos: List[VideoAnalysisInput]
) -> None:
    cached_service = CachedAIService(service=mock_ai_service, cache=file_cache)

    # Consume stream
    chunks = []
    async for chunk in cached_service.analyze_stream(sample_videos):
        chunks.append(chunk)

    assert "".join(chunks) == "Analyzed Content"
    mock_ai_service.analyze_stream.assert_called_once()

    # Verify cache write
    key = cached_service._generate_key(sample_videos)
    assert file_cache.get(key) == "Analyzed Content"

@pytest.mark.asyncio
async def test_cached_ai_service_stream_hit(
    file_cache: FileCacheBackend,
    mock_ai_service: Mock,
    sample_videos: List[VideoAnalysisInput]
) -> None:
    cached_service = CachedAIService(service=mock_ai_service, cache=file_cache)

    # Pre-populate cache
    key = cached_service._generate_key(sample_videos)
    file_cache.set(key, "Cached Result")

    # Consume stream
    chunks = []
    async for chunk in cached_service.analyze_stream(sample_videos):
        chunks.append(chunk)

    # Result might be split differently but should join to same string
    assert "".join(chunks) == "Cached Result"
    mock_ai_service.analyze_stream.assert_not_called()
