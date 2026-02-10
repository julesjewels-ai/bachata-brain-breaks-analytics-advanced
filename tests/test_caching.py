"""
Unit tests for Caching Service.
"""
import pytest
import asyncio
from typing import List, AsyncGenerator
from src.core.caching import InMemoryCacheBackend, CachedAIService
from src.core.models import VideoAnalysisInput
from src.core.interfaces import AIService

class MockAIService(AIService):
    def __init__(self):
        self.semantics_call_count = 0
        self.stream_call_count = 0

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        self.semantics_call_count += 1
        return "Mock Analysis Result"

    async def analyze_stream(self, videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        self.stream_call_count += 1
        yield "Mock "
        yield "Stream "
        yield "Result"

@pytest.fixture
def mock_videos():
    return [
        VideoAnalysisInput(
            video_id="vid_1",
            title="Test Video",
            views=1000,
            retention_avg_pct=75.5,
            type="Shorts"
        )
    ]

def test_cache_backend_basic_operations():
    backend = InMemoryCacheBackend()

    # Set & Get
    backend.set("key1", "value1")
    assert backend.get("key1") == "value1"

    # Delete
    backend.delete("key1")
    assert backend.get("key1") is None

    # Miss
    assert backend.get("non_existent") is None

def test_cache_backend_expiration():
    backend = InMemoryCacheBackend()

    # Set with short TTL
    backend.set("key_ttl", "value_ttl", ttl=0.1) # 100ms
    assert backend.get("key_ttl") == "value_ttl"

    # Wait for expiration
    import time
    time.sleep(0.2)
    assert backend.get("key_ttl") is None

def test_cached_ai_service_semantics(mock_videos):
    inner_service = MockAIService()
    backend = InMemoryCacheBackend()
    cached_service = CachedAIService(inner_service, backend)

    # First call: Should hit inner service
    result1 = cached_service.analyze_semantics(mock_videos)
    assert result1 == "Mock Analysis Result"
    assert inner_service.semantics_call_count == 1

    # Second call: Should hit cache
    result2 = cached_service.analyze_semantics(mock_videos)
    assert result2 == "Mock Analysis Result"
    assert inner_service.semantics_call_count == 1  # Still 1

def test_cached_ai_service_stream(mock_videos):
    inner_service = MockAIService()
    backend = InMemoryCacheBackend()
    cached_service = CachedAIService(inner_service, backend)

    async def run_stream():
        # First call: Should hit inner service
        chunks1 = []
        async for chunk in cached_service.analyze_stream(mock_videos):
            chunks1.append(chunk)

        assert "".join(chunks1) == "Mock Stream Result"
        assert inner_service.stream_call_count == 1

        # Second call: Should hit cache
        chunks2 = []
        async for chunk in cached_service.analyze_stream(mock_videos):
            chunks2.append(chunk)

        # Verify content matches exactly (cache should be transparent)
        assert "".join(chunks2) == "Mock Stream Result"
        assert inner_service.stream_call_count == 1

    asyncio.run(run_stream())

def test_cached_ai_service_different_inputs(mock_videos):
    inner_service = MockAIService()
    backend = InMemoryCacheBackend()
    cached_service = CachedAIService(inner_service, backend)

    # Call with video 1
    cached_service.analyze_semantics(mock_videos)
    assert inner_service.semantics_call_count == 1

    # Call with modified video 2
    videos2 = [
        VideoAnalysisInput(
            video_id="vid_2",
            title="Another Video",
            views=500,
            retention_avg_pct=60.0,
            type="Long"
        )
    ]
    cached_service.analyze_semantics(videos2)
    assert inner_service.semantics_call_count == 2
