import pytest
import asyncio
from unittest.mock import MagicMock
from typing import List, AsyncGenerator
from src.core.interfaces import AIService
from src.core.models import VideoAnalysisInput
from src.core.caching import InMemoryCacheBackend, CacheService, CachedAIService

# Mock AIService Implementation
class MockAIService:
    def __init__(self):
        self.call_count_semantics = 0
        self.call_count_stream = 0

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        self.call_count_semantics += 1
        return "Analysis Result"

    async def analyze_stream(self, videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        self.call_count_stream += 1
        yield "Analysis "
        yield "Result "

def test_cached_semantics():
    # Setup
    backend = InMemoryCacheBackend()
    service = CacheService(backend)
    mock_ai = MockAIService()
    # Explicitly cast to AIService if using strict mypy locally, but for runtime it's duck typing
    cached_ai = CachedAIService(mock_ai, service, ttl=60)  # type: ignore

    videos = [
        VideoAnalysisInput(
            video_id="vid_1",
            title="Test Video",
            views=100,
            retention_avg_pct=50.0,
            type="Shorts"
        )
    ]

    # First call - cache miss
    result1 = cached_ai.analyze_semantics(videos)
    assert result1 == "Analysis Result"
    assert mock_ai.call_count_semantics == 1

    # Second call - cache hit
    result2 = cached_ai.analyze_semantics(videos)
    assert result2 == "Analysis Result"
    assert mock_ai.call_count_semantics == 1  # Still 1

def test_cached_stream():
    async def run_test():
        # Setup
        backend = InMemoryCacheBackend()
        service = CacheService(backend)
        mock_ai = MockAIService()
        cached_ai = CachedAIService(mock_ai, service, ttl=60) # type: ignore

        videos = [
            VideoAnalysisInput(
                video_id="vid_1",
                title="Test Video",
                views=100,
                retention_avg_pct=50.0,
                type="Shorts"
            )
        ]

        # First call - cache miss
        chunks1 = []
        async for chunk in cached_ai.analyze_stream(videos):
            chunks1.append(chunk)

        full_text1 = "".join(chunks1)
        assert full_text1 == "Analysis Result "
        assert mock_ai.call_count_stream == 1

        # Second call - cache hit
        chunks2 = []
        async for chunk in cached_ai.analyze_stream(videos):
            chunks2.append(chunk)

        full_text2 = "".join(chunks2)

        # Verify cache marker is present
        assert "[Cached] " in chunks2[0] or "[Cached] " == chunks2[0]

        # Verify mock was NOT called again
        assert mock_ai.call_count_stream == 1

    asyncio.run(run_test())
