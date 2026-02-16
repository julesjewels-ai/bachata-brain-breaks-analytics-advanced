"""
Caching module for Bachata Brain Breaks Analytics.
Implements the CacheBackend protocol and provides a CachedAIService decorator.
"""
import json
import hashlib
import asyncio
from pathlib import Path
from typing import Optional, List, AsyncGenerator
import logging
from src.core.interfaces import CacheBackend, AIService
from src.core.models import VideoAnalysisInput

logger = logging.getLogger(__name__)

class CacheError(Exception):
    """Base exception for cache operations."""
    pass

class CacheReadError(CacheError):
    """Raised when reading from cache fails."""
    pass

class CacheWriteError(CacheError):
    """Raised when writing to cache fails."""
    pass

class FileCacheBackend:
    """
    File-based implementation of CacheBackend.
    Stores cache entries as JSON files in a specified directory.
    """
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise CacheError(f"Failed to create cache directory: {e}")

    def get(self, key: str) -> Optional[str]:
        """Retrieves a value from the cache."""
        cache_file = self.cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None

        try:
            return cache_file.read_text(encoding="utf-8")
        except OSError as e:
            raise CacheReadError(f"Failed to read cache {key}: {e}")

    def set(self, key: str, value: str) -> None:
        """Stores a value in the cache."""
        cache_file = self.cache_dir / f"{key}.json"
        try:
            cache_file.write_text(value, encoding="utf-8")
        except OSError as e:
            raise CacheWriteError(f"Failed to write cache {key}: {e}")

class CachedAIService:
    """
    Decorator/Proxy for AIService that adds caching capabilities.
    """
    def __init__(self, service: AIService, backend: CacheBackend):
        self._service = service
        self._backend = backend

    def _generate_key(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Generates a deterministic cache key based on the input data.
        """
        # Serialize list of models to JSON string with sorted keys
        data = [v.model_dump() for v in videos]
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Analyzes semantics with caching.
        """
        key = self._generate_key(videos)

        try:
            cached_value = self._backend.get(key)
            if cached_value:
                logger.info(f"Cache hit for key {key[:8]}")
                return cached_value
        except CacheReadError as e:
            logger.warning(f"Cache read failed: {e}")

        # Cache miss
        logger.info(f"Cache miss for key {key[:8]}")
        result = self._service.analyze_semantics(videos)

        try:
            self._backend.set(key, result)
        except CacheWriteError as e:
            logger.warning(f"Cache write failed: {e}")

        return result

    async def analyze_stream(self, videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        """
        Streams analysis with caching.
        """
        key = self._generate_key(videos)

        # Check cache (blocking operation wrapped in thread)
        cached_value: Optional[str] = None
        try:
            cached_value = await asyncio.to_thread(self._backend.get, key)
        except CacheReadError as e:
            logger.warning(f"Cache read failed during stream: {e}")

        if cached_value:
            logger.info(f"Cache hit for key {key[:8]}")
            # Simulate streaming from cache
            # We assume the cached value is the full text.
            # We split by space to simulate token streaming, similar to the mock agent.
            tokens = cached_value.split(' ')
            for i, token in enumerate(tokens):
                # Add space back if it wasn't the last token, or just append space to all like the agent does
                yield token + " "
                # Simulate small delay
                await asyncio.sleep(0.01)
            return

        # Cache miss
        logger.info(f"Cache miss for key {key[:8]}")
        full_response_chunks = []

        async for chunk in self._service.analyze_stream(videos):
            full_response_chunks.append(chunk)
            yield chunk

        full_response = "".join(full_response_chunks)

        try:
            await asyncio.to_thread(self._backend.set, key, full_response)
        except CacheWriteError as e:
             logger.warning(f"Cache write failed during stream: {e}")
