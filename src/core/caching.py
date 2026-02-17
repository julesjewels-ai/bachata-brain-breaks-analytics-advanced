"""
Caching module for AI services.
Implements the Proxy pattern to cache expensive AI operations.
"""
import hashlib
import json
import logging
import asyncio
from pathlib import Path
from typing import Optional, List, AsyncGenerator
from src.core.interfaces import AIService, CacheBackend
from src.core.models import VideoAnalysisInput

logger = logging.getLogger(__name__)

class CacheError(Exception):
    """Base class for cache exceptions."""
    pass

class CacheReadError(CacheError):
    """Raised when reading from cache fails."""
    pass

class CacheWriteError(CacheError):
    """Raised when writing to cache fails."""
    pass

class FileCacheBackend(CacheBackend):
    """
    File-based implementation of CacheBackend.
    """
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise CacheError(f"Failed to create cache directory: {e}")

    def _get_path(self, key: str) -> Path:
        # Sanitize key to be safe for filenames if needed,
        # but here we assume key is a hash which is safe.
        return self.cache_dir / f"{key}.cache"

    def get(self, key: str) -> Optional[str]:
        path = self._get_path(key)
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError as e:
            raise CacheReadError(f"Failed to read cache file {path}: {e}")

    def set(self, key: str, value: str) -> None:
        path = self._get_path(key)
        try:
            path.write_text(value, encoding="utf-8")
        except OSError as e:
            raise CacheWriteError(f"Failed to write cache file {path}: {e}")

class CachedAIService(AIService):
    """
    Proxy service that caches results from an underlying AIService.
    """
    def __init__(self, service: AIService, cache: CacheBackend):
        self._service = service
        self._cache = cache

    def _generate_key(self, videos: List[VideoAnalysisInput]) -> str:
        """Generates a deterministic cache key from the input."""
        # Serialize list of models to JSON string
        data = [v.model_dump() for v in videos]
        # Sort keys ensures deterministic JSON
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        key = self._generate_key(videos)
        try:
            cached_result = self._cache.get(key)
            if cached_result:
                logger.info("Cache hit for analyze_semantics.")
                return cached_result
        except CacheReadError as e:
            logger.warning(f"Cache read failed: {e}. Proceeding without cache.")

        logger.info("Cache miss. Calling inner service.")
        result = self._service.analyze_semantics(videos)

        try:
            self._cache.set(key, result)
        except CacheWriteError as e:
            logger.warning(f"Cache write failed: {e}.")

        return result

    async def analyze_stream(self, videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        key = self._generate_key(videos)
        cached_full_response: Optional[str] = None

        try:
            cached_full_response = self._cache.get(key)
        except CacheReadError as e:
            logger.warning(f"Cache read failed: {e}. Proceeding without cache.")

        if cached_full_response:
            logger.info("Cache hit for analyze_stream.")
            # Simulate streaming from cached result
            tokens = cached_full_response.split(' ')
            for token in tokens:
                yield token + " "
                # Minimal delay to simulate async generation without blocking
                await asyncio.sleep(0.01)
            return

        logger.info("Cache miss for analyze_stream. Calling inner service.")
        full_response_accumulator = []

        async for chunk in self._service.analyze_stream(videos):
            full_response_accumulator.append(chunk)
            yield chunk

        # Accumulate the response to cache it
        # Since the chunks often contain " ", we just join them.
        # But if we want to store the clean text, we might need to handle the fact that
        # GeminiThinkingAgent yields "token + ' '".
        # If we just join, we get "token1 token2 ".
        # When we read it back, we split by " " and get ["token1", "token2", ""]
        # And yield "token1 ", "token2 ", " " (if we are not careful).

        # Let's clean it up slightly before storing.
        full_response = "".join(full_response_accumulator).strip()

        try:
            self._cache.set(key, full_response)
        except CacheWriteError as e:
            logger.warning(f"Cache write failed: {e}.")
