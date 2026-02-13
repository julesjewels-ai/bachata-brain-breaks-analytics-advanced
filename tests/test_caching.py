"""
Tests for the caching module.
"""
import pytest
import asyncio
import time
from typing import List, AsyncGenerator, Any

from src.core.interfaces import AIService
from src.core.caching import InMemoryCacheBackend, CachedAIService
from src.core.models import VideoAnalysisInput

class MockAIServiceImpl:
    """Simple AIService implementation for testing call counts."""
    def __init__(self) -> None:
        self.semantics_count = 0
        self.stream_count = 0

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        self.semantics_count += 1
        return "Test Analysis"

    async def analyze_stream(self, videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        self.stream_count += 1
        yield "Test "
        yield "Stream"

@pytest.fixture
def test_ai_service() -> MockAIServiceImpl:
    return MockAIServiceImpl()

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

def test_backend_set_get() -> None:
    backend = InMemoryCacheBackend()
    backend.set("test_key", "test_value")
    assert backend.get("test_key") == "test_value"

def test_backend_expiry() -> None:
    backend = InMemoryCacheBackend()
    # Short TTL
    backend.set("short_lived", "value", ttl=1)
    assert backend.get("short_lived") == "value"
    time.sleep(1.1)
    assert backend.get("short_lived") is None

def test_backend_delete() -> None:
    backend = InMemoryCacheBackend()
    backend.set("key", "value")
    backend.delete("key")
    assert backend.get("key") is None

def test_backend_clear() -> None:
    backend = InMemoryCacheBackend()
    backend.set("k1", "v1")
    backend.set("k2", "v2")
    backend.clear()
    assert backend.get("k1") is None
    assert backend.get("k2") is None

def test_cached_service_semantics_hit_miss(test_ai_service: MockAIServiceImpl, sample_videos: List[VideoAnalysisInput]) -> None:
    backend = InMemoryCacheBackend()
    # Cast to AIService to satisfy type checker if needed, but python is dynamic here
    cached_service = CachedAIService(test_ai_service, backend) # type: ignore

    # First call - Miss
    result1 = cached_service.analyze_semantics(sample_videos)
    assert result1 == "Test Analysis"
    assert test_ai_service.semantics_count == 1

    # Second call - Hit
    result2 = cached_service.analyze_semantics(sample_videos)
    assert result2 == "Test Analysis"
    # Should still be called once because the second time it hit cache
    assert test_ai_service.semantics_count == 1

@pytest.mark.asyncio
async def test_cached_service_stream_hit_miss(test_ai_service: MockAIServiceImpl, sample_videos: List[VideoAnalysisInput]) -> None:
    backend = InMemoryCacheBackend()
    cached_service = CachedAIService(test_ai_service, backend) # type: ignore

    # First call - Miss
    chunks1 = []
    async for chunk in cached_service.analyze_stream(sample_videos):
        chunks1.append(chunk)

    assert "".join(chunks1) == "Test Stream"
    assert test_ai_service.stream_count == 1

    # Second call - Hit
    chunks2 = []
    async for chunk in cached_service.analyze_stream(sample_videos):
        chunks2.append(chunk)

    assert "".join(chunks2) == "Test Stream"
    # Should still be call_count == 1
    assert test_ai_service.stream_count == 1
