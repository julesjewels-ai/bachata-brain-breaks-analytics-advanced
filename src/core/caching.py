"""
Caching module for Bachata Brain Breaks Analytics.
Implements caching backends and service decorators.
"""
import hashlib
import json
import logging
import asyncio
from pathlib import Path
from typing import Optional, List, AsyncGenerator
from src.core.interfaces import CacheBackend, AIService
from src.core.models import VideoAnalysisInput

logger = logging.getLogger(__name__)

class CacheError(Exception):
    """Base exception for cache errors."""
    pass

class CacheReadError(CacheError):
    """Error reading from cache."""
    pass

class CacheWriteError(CacheError):
    """Error writing to cache."""
    pass

class FileCacheBackend:
    """
    File-based implementation of CacheBackend.
    """
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise CacheError(f"Failed to create cache directory: {e}")

    def get(self, key: str) -> Optional[str]:
        filepath = self.cache_dir / f"{key}.json"
        if not filepath.exists():
            return None
        try:
            return filepath.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning(f"Failed to read cache file {filepath}: {e}")
            return None

    def set(self, key: str, value: str) -> None:
        filepath = self.cache_dir / f"{key}.json"
        try:
            filepath.write_text(value, encoding="utf-8")
        except OSError as e:
            logger.error(f"Failed to write cache file {filepath}: {e}")
            # We don't raise here to allow operation to continue without cache
            pass

class CachedAIService:
    """
    Proxy service that adds caching to an AIService.
    """
    def __init__(self, service: AIService, cache: CacheBackend):
        self.service = service
        self.cache = cache

    def _generate_key(self, videos: List[VideoAnalysisInput]) -> str:
        """Generates a deterministic cache key from the input."""
        data = [v.model_dump() for v in videos]
        # Sort keys in JSON dump to ensure determinism
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        key = self._generate_key(videos)
        cached = self.cache.get(key)
        if cached:
            logger.info(f"Cache hit for key {key}")
            return cached

        logger.info(f"Cache miss for key {key}")
        result = self.service.analyze_semantics(videos)
        self.cache.set(key, result)
        return result

    async def analyze_stream(self, videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        key = self._generate_key(videos)

        # Use asyncio.to_thread for blocking cache I/O
        cached = await asyncio.to_thread(self.cache.get, key)

        if cached:
            logger.info(f"Cache hit for key {key} (stream)")
            # Simulate stream from cached string
            chunk_size = 10
            for i in range(0, len(cached), chunk_size):
                yield cached[i:i+chunk_size]
                await asyncio.sleep(0.001)
            return

        logger.info(f"Cache miss for key {key} (stream)")
        full_response = []
        async for chunk in self.service.analyze_stream(videos):
            full_response.append(chunk)
            yield chunk

        # Write back to cache in background thread
        await asyncio.to_thread(self.cache.set, key, "".join(full_response))
