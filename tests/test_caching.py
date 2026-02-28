"""
Tests for caching mechanisms.
"""
import pytest
import asyncio
import json
import hashlib
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from src.core.caching import FileCacheBackend, CachedAIService, CacheError
from src.core.models import VideoAnalysisInput

# Sample input data for tests


@pytest.fixture
def sample_videos():
    return [
        VideoAnalysisInput(
            video_id="vid_123",
            title="Test Video",
            views=100,
            retention_avg_pct=50.0,
            type="Long"
        )
    ]

# Helper for async generator


async def async_gen_from_list(items):
    for item in items:
        yield item


class TestFileCacheBackend:
    def test_init_creates_directory(self, tmp_path):
        cache_dir = tmp_path / "cache"
        backend = FileCacheBackend(str(cache_dir))
        assert cache_dir.exists()

    def test_set_get(self, tmp_path):
        cache_dir = tmp_path / "cache"
        backend = FileCacheBackend(str(cache_dir))
        key = "test_key"
        value = "test_value"

        backend.set(key, value)
        assert backend.get(key) == value

        # Verify file content
        hashed_key = hashlib.md5(key.encode("utf-8")).hexdigest()
        assert (
            cache_dir /
            f"{hashed_key}.txt").read_text(
            encoding="utf-8") == value

    def test_get_missing(self, tmp_path):
        cache_dir = tmp_path / "cache"
        backend = FileCacheBackend(str(cache_dir))
        assert backend.get("missing_key") is None

    def test_init_error(self):
        # Trying to create cache in a read-only location or invalid path
        # In a sandbox, permissions are tricky. We can mock Path.mkdir
        with patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")):
            with pytest.raises(CacheError):
                FileCacheBackend("/invalid/path")


class TestCachedAIService:
    @pytest.fixture
    def mock_ai_service(self):
        service = Mock()
        service.analyze_semantics.return_value = "AI Response"
        service.analyze_stream.return_value = async_gen_from_list(
            ["AI ", "Stream "])
        return service

    @pytest.fixture
    def mock_cache_backend(self):
        backend = Mock()
        backend.get.return_value = None
        return backend

    def test_analyze_semantics_cache_miss(
            self,
            mock_ai_service,
            mock_cache_backend,
            sample_videos):
        cached_service = CachedAIService(mock_ai_service, mock_cache_backend)

        result = cached_service.analyze_semantics(sample_videos)

        assert result == "AI Response"
        mock_ai_service.analyze_semantics.assert_called_once_with(
            sample_videos)
        mock_cache_backend.get.assert_called_once()
        mock_cache_backend.set.assert_called_once()

    def test_analyze_semantics_cache_hit(
            self,
            mock_ai_service,
            mock_cache_backend,
            sample_videos):
        mock_cache_backend.get.return_value = "Cached Response"
        cached_service = CachedAIService(mock_ai_service, mock_cache_backend)

        result = cached_service.analyze_semantics(sample_videos)

        assert result == "Cached Response"
        mock_ai_service.analyze_semantics.assert_not_called()
        mock_cache_backend.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_analyze_stream_cache_miss(
            self,
            mock_ai_service,
            mock_cache_backend,
            sample_videos):
        # Setup mock stream
        async def mock_stream(videos):
            yield "AI "
            yield "Stream "
        # Use side_effect so we can assert called
        mock_ai_service.analyze_stream = Mock(side_effect=mock_stream)

        cached_service = CachedAIService(mock_ai_service, mock_cache_backend)

        chunks = []
        async for chunk in cached_service.analyze_stream(sample_videos):
            chunks.append(chunk)

        assert "".join(chunks) == "AI Stream "
        mock_ai_service.analyze_stream.assert_called_once()
        mock_cache_backend.get.assert_called_once()

        # Verify it caches the full response stripped
        # "AI Stream " -> "AI Stream"
        mock_cache_backend.set.assert_called_once()
        args, _ = mock_cache_backend.set.call_args
        assert args[1] == "AI Stream"

    @pytest.mark.asyncio
    async def test_analyze_stream_cache_hit(
            self,
            mock_ai_service,
            mock_cache_backend,
            sample_videos):
        mock_cache_backend.get.return_value = "Cached Stream"
        cached_service = CachedAIService(mock_ai_service, mock_cache_backend)

        chunks = []
        async for chunk in cached_service.analyze_stream(sample_videos):
            chunks.append(chunk)

        # Implementation splits by regex to preserve whitespace
        # "Cached Stream" -> ["Cached", " ", "Stream"]
        assert "".join(chunks) == "Cached Stream"

        # Original service not called
        # We replaced analyze_stream on mock_ai_service in previous test,
        # but here we use a fresh fixture or just check it wasn't called.
        # Wait, if I modify the fixture object in previous test, does it persist?
        # Pytest fixtures are recreated if scope is function (default).
        # But mock_ai_service is created via fixture.
        # Actually, I didn't verify mock_ai_service calls in this test.
        # Let's assume standard behavior.
        # The mock_ai_service from fixture has return_value set to async_gen_from_list.
        # But CachedAIService calls it only on miss.
        # Since we have a hit, it shouldn't be called.
        # However, AsyncMock/Mock verification for async calls is specific.
        # Since analyze_stream is async generator, standard Mock return_value usage:
        # service.analyze_stream(videos) returns the generator.
        # CachedAIService only calls it if miss.
        # So we can assert not called.
        mock_ai_service.analyze_stream.assert_not_called()
