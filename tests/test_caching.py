"""
Unit tests for the Caching module.
"""
import pytest
import time
from unittest.mock import MagicMock
from src.core.caching import InMemoryCacheBackend, CachedAIService
from src.core.models import VideoAnalysisInput
from src.core.interfaces import AIService

class TestInMemoryCacheBackend:
    def test_set_get(self):
        cache = InMemoryCacheBackend()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing(self):
        cache = InMemoryCacheBackend()
        assert cache.get("missing") is None

    def test_delete(self):
        cache = InMemoryCacheBackend()
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_ttl_expiration(self):
        cache = InMemoryCacheBackend()
        cache.set("key1", "value1", ttl=0.1)
        assert cache.get("key1") == "value1"
        time.sleep(0.2)
        assert cache.get("key1") is None

class TestCachedAIService:
    @pytest.fixture
    def mock_service(self):
        service = MagicMock(spec=AIService)
        service.analyze_semantics.return_value = "Analyzed Result"

        async def mock_stream(videos):
            yield "Chunk1 "
            yield "Chunk2"

        service.analyze_stream = mock_stream
        return service

    @pytest.fixture
    def cache_backend(self):
        return InMemoryCacheBackend()

    @pytest.fixture
    def cached_service(self, mock_service, cache_backend):
        return CachedAIService(service=mock_service, cache=cache_backend)

    @pytest.fixture
    def sample_input(self):
        return [
            VideoAnalysisInput(
                video_id="vid_1",
                title="Test Video",
                views=1000,
                retention_avg_pct=50.0,
                type="Long"
            )
        ]

    def test_analyze_semantics_cache_miss(self, cached_service, mock_service, sample_input):
        # First call: Cache miss
        result = cached_service.analyze_semantics(sample_input)

        assert result == "Analyzed Result"
        mock_service.analyze_semantics.assert_called_once_with(sample_input)

        # Verify it's in cache
        key = cached_service._generate_key("semantics", sample_input)
        assert cached_service.cache.get(key) == "Analyzed Result"

    def test_analyze_semantics_cache_hit(self, cached_service, mock_service, sample_input):
        # Pre-populate cache
        key = cached_service._generate_key("semantics", sample_input)
        cached_service.cache.set(key, "Cached Result")

        # Call
        result = cached_service.analyze_semantics(sample_input)

        assert result == "Cached Result"
        mock_service.analyze_semantics.assert_not_called()

    @pytest.mark.asyncio
    async def test_analyze_stream_cache_miss(self, cached_service, mock_service, sample_input):
        # First call: Cache miss
        chunks = []
        async for chunk in cached_service.analyze_stream(sample_input):
            chunks.append(chunk)

        assert "".join(chunks) == "Chunk1 Chunk2"
        # Since analyze_stream is a generator, we can't easily assert_called_once on the function itself
        # because the fixture replaces it with an async generator function.
        # Ideally we'd wrap it in a mock object, but checking the result is sufficient.

        # Verify it's in cache
        key = cached_service._generate_key("stream", sample_input)
        assert cached_service.cache.get(key) == "Chunk1 Chunk2"

    @pytest.mark.asyncio
    async def test_analyze_stream_cache_hit(self, cached_service, mock_service, sample_input):
        # Pre-populate cache
        key = cached_service._generate_key("stream", sample_input)
        cached_service.cache.set(key, "Cached Chunk1 Cached Chunk2")

        # Override service to raise exception if called
        async def fail_stream(videos):
            raise Exception("Should not be called")
            yield "Fail"

        # We need to patch the service instance on the cached_service
        cached_service.service.analyze_stream = fail_stream

        chunks = []
        async for chunk in cached_service.analyze_stream(sample_input):
            chunks.append(chunk)

        assert "".join(chunks) == "Cached Chunk1 Cached Chunk2"
