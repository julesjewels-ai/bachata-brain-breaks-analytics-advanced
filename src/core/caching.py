"""
Caching module for AI services.
Implements the Cache Pattern to reduce latency and costs.
"""
import asyncio
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Optional, List, Protocol, AsyncGenerator, Any
from src.core.interfaces import AIService
from src.core.models import VideoAnalysisInput

logger = logging.getLogger(__name__)

class CacheError(Exception):
    """Base exception for cache errors."""
    pass

class CacheReadError(CacheError):
    """Raised when reading from cache fails."""
    pass

class CacheWriteError(CacheError):
    """Raised when writing to cache fails."""
    pass

class CacheBackend(Protocol):
    """
    Protocol for cache backends.
    """
    def get(self, key: str) -> Optional[str]:
        """Retrieves a value from the cache."""
        ...

    def set(self, key: str, value: str) -> None:
        """Sets a value in the cache."""
        ...

class FileCacheBackend:
    """
    File-based cache implementation using JSON storage.
    """
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise CacheWriteError(f"Failed to create cache directory: {e}")

    def _get_path(self, key: str) -> Path:
        # Sanitize key to be safe for filenames
        safe_key = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str) -> Optional[str]:
        path = self._get_path(key)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("value")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Cache read error for key {key}: {e}")
            raise CacheReadError(f"Failed to read cache: {e}")

    def set(self, key: str, value: str) -> None:
        path = self._get_path(key)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"value": value}, f)
        except OSError as e:
            logger.error(f"Cache write error for key {key}: {e}")
            raise CacheWriteError(f"Failed to write to cache: {e}")

class CachedAIService(AIService):
    """
    Proxy service that adds caching to an existing AIService.
    """
    def __init__(self, service: AIService, cache: CacheBackend):
        self._service = service
        self._cache = cache

    def _generate_key(self, videos: List[VideoAnalysisInput]) -> str:
        """Generates a consistent cache key from input data."""
        # Convert Pydantic models to dicts and sort/serialize deterministically
        data = [v.model_dump() for v in videos]
        # Use sort_keys=True to ensure consistent JSON representation
        serialized = json.dumps(data, sort_keys=True)
        return serialized

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        key = self._generate_key(videos)

        try:
            cached = self._cache.get(key)
            if cached:
                logger.info("Cache hit for analyze_semantics")
                return cached
        except CacheReadError:
            logger.warning("Cache read failed, falling back to service")

        result = self._service.analyze_semantics(videos)

        try:
            self._cache.set(key, result)
        except CacheWriteError:
             logger.warning("Cache write failed")

        return result

    async def analyze_stream(self, videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        key = self._generate_key(videos)

        # Check cache first
        try:
            # Use asyncio.to_thread for potentially blocking I/O
            cached = await asyncio.to_thread(self._cache.get, key)
            if cached:
                logger.info("Cache hit for analyze_stream")
                # Stream cached content
                # Split by space to simulate token stream, preserving spaces
                tokens = re.split(r'(\s+)', cached)
                for token in tokens:
                    if token:
                        yield token
                        # Very short delay to simulate fast streaming
                        await asyncio.sleep(0.001)
                return
        except Exception as e:
            logger.warning(f"Cache check failed: {e}")

        # Cache miss: Consume inner stream and build full response
        full_response_parts = []
        async for chunk in self._service.analyze_stream(videos):
            full_response_parts.append(chunk)
            yield chunk

        full_response = "".join(full_response_parts)

        try:
            await asyncio.to_thread(self._cache.set, key, full_response)
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")
