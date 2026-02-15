"""
Caching mechanisms for the application.
Implements the CacheBackend protocol and provides a cached wrapper for AIService.
"""
import os
import time
import json
import hashlib
import logging
import asyncio
from pathlib import Path
from typing import Any, Optional, List, AsyncGenerator
from src.core.interfaces import CacheBackend, AIService
from src.core.models import VideoAnalysisInput

logger = logging.getLogger(__name__)

class CacheError(Exception):
    """Base exception for caching errors."""
    pass

class CacheReadError(CacheError):
    """Raised when reading from cache fails."""
    pass

class CacheWriteError(CacheError):
    """Raised when writing to cache fails."""
    pass

class FileCacheBackend(CacheBackend):
    """
    A file-based implementation of the CacheBackend protocol.
    Stores cached items as JSON files in a specified directory.
    """
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Ensures the cache directory exists."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            msg = f"Failed to create cache directory {self.cache_dir}: {e}"
            logger.error(msg)
            raise CacheWriteError(msg) from e

    def _get_file_path(self, key: str) -> Path:
        """Generates a safe file path for a given key."""
        safe_key = "".join(c for c in key if c.isalnum() or c in ('-', '_'))
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str) -> Optional[Any]:
        """Retrieves a value from the cache if it exists and hasn't expired."""
        file_path = self._get_file_path(key)
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            value = data.get("value")
            expiry = data.get("expiry")

            if expiry and time.time() > expiry:
                # Cache expired
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                return None

            return value
        except (json.JSONDecodeError, OSError, ValueError) as e:
            msg = f"Failed to read cache key {key}: {e}"
            logger.warning(msg)
            raise CacheReadError(msg) from e

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Sets a value in the cache with a Time-To-Live (TTL)."""
        # Ensure dir exists (might have been deleted)
        try:
            self._ensure_cache_dir()
        except CacheWriteError:
            raise

        file_path = self._get_file_path(key)
        expiry = time.time() + ttl

        data = {
            "value": value,
            "expiry": expiry
        }

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except (OSError, TypeError) as e:
            msg = f"Failed to write cache key {key}: {e}"
            logger.error(msg)
            raise CacheWriteError(msg) from e


class CachedAIService(AIService):
    """
    A wrapper around an AIService that caches results using a CacheBackend.
    """
    def __init__(self, delegate: AIService, cache: CacheBackend):
        self.delegate = delegate
        self.cache = cache

    def _generate_key(self, videos: List[VideoAnalysisInput]) -> str:
        """Generates a deterministic cache key based on the input videos."""
        # Use Pydantic's model_dump to create list of dicts
        data = [v.model_dump(mode='json') for v in videos]
        # Sort keys to ensure consistent JSON representation
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode("utf-8")).hexdigest()

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Analyzes video metadata, utilizing cache if available.
        """
        key = self._generate_key(videos)

        try:
            cached_result = self.cache.get(key)
            if cached_result is not None and isinstance(cached_result, str):
                logger.info(f"Cache hit for analyze_semantics: {key}")
                return cached_result
        except CacheReadError as e:
            logger.warning(f"Cache read error: {e}")

        logger.info(f"Cache miss for analyze_semantics: {key}")
        result = self.delegate.analyze_semantics(videos)

        try:
            self.cache.set(key, result)
        except CacheWriteError as e:
             logger.warning(f"Cache write error: {e}")

        return result

    async def analyze_stream(self, videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        """
        Stream analysis of video metadata.
        If cached result exists, streams from cache. Otherwise delegates and caches the full result.
        Uses asyncio.to_thread to prevent blocking the event loop during file I/O.
        """
        key = self._generate_key(videos)

        try:
            # Run blocking cache read in a separate thread
            cached_result = await asyncio.to_thread(self.cache.get, key)
            if cached_result is not None and isinstance(cached_result, str):
                logger.info(f"Cache hit for analyze_stream: {key}")
                chunk_size = 5
                for i in range(0, len(cached_result), chunk_size):
                    yield cached_result[i:i+chunk_size]
                return
        except CacheReadError as e:
            logger.warning(f"Cache read error: {e}")

        logger.info(f"Cache miss for analyze_stream: {key}")

        full_result_buffer = []
        async for token in self.delegate.analyze_stream(videos):
            full_result_buffer.append(token)
            yield token

        # Write to cache after successful stream completion
        try:
            full_result = "".join(full_result_buffer)
            if full_result:
                # Run blocking cache write in a separate thread
                await asyncio.to_thread(self.cache.set, key, full_result)
        except CacheWriteError as e:
            logger.warning(f"Cache write error after stream: {e}")
