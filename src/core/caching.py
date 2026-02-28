"""
Caching mechanisms for AI services.
Implements a file-based cache backend and a caching decorator for AIService.
"""
import hashlib
import json
import asyncio
import logging
import re
from pathlib import Path
from typing import Optional, List, AsyncGenerator
from src.core.interfaces import CacheBackend, AIService
from src.core.models import VideoAnalysisInput

logger = logging.getLogger(__name__)


class CacheError(Exception):
    """Base exception for caching errors."""
    pass


class FileCacheBackend(CacheBackend):
    """
    File-based implementation of CacheBackend.
    Stores cached values in a specified directory using hashed keys as filenames.
    """

    def __init__(self, cache_dir: str) -> None:
        self.cache_dir = Path(cache_dir)
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create cache directory {cache_dir}: {e}")
            raise CacheError(f"Failed to create cache directory: {e}") from e

    def _get_filepath(self, key: str) -> Path:
        """Generates a file path from a cache key using MD5 hashing."""
        hashed_key = hashlib.md5(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{hashed_key}.txt"

    def get(self, key: str) -> Optional[str]:
        """Retrieves a value from the cache if it exists."""
        filepath = self._get_filepath(key)
        if filepath.exists():
            try:
                return filepath.read_text(encoding="utf-8")
            except OSError as e:
                logger.warning(f"Failed to read cache file {filepath}: {e}")
                return None
        return None

    def set(self, key: str, value: str) -> None:
        """Stores a value in the cache."""
        filepath = self._get_filepath(key)
        try:
            filepath.write_text(value, encoding="utf-8")
        except OSError as e:
            logger.warning(f"Failed to write cache file {filepath}: {e}")
            # We log but don't raise here to avoid interrupting the flow on cache write failure
            # unless strict caching is required. Assuming soft failure is
            # acceptable.


class CachedAIService(AIService):
    """
    Decorator/Proxy for AIService that adds caching capabilities.
    """

    def __init__(
            self,
            ai_service: AIService,
            cache_backend: CacheBackend) -> None:
        self._ai_service = ai_service
        self._cache = cache_backend

    def _generate_key(self, videos: List[VideoAnalysisInput]) -> str:
        """Generates a unique, deterministic cache key from the input data."""
        # Convert list of models to list of dicts, sorted by video_id to ensure
        # consistency
        data = [v.model_dump() for v in videos]
        # Sort data to ensure order doesn't affect key if content is same
        # Assuming we want to cache based on the *set* of videos.
        # But analyze_semantics takes a List, so order might matter?
        # The interface says `analyze_semantics(videos: List[...])`.
        # Usually order implies context. I will preserve order.
        return json.dumps(data, sort_keys=True)

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Analyzes semantics, checking cache first.
        """
        key = self._generate_key(videos)
        cached_response = self._cache.get(key)
        if cached_response:
            logger.info("Cache hit for analyze_semantics.")
            return cached_response

        logger.info("Cache miss for analyze_semantics. Calling AI service.")
        response = self._ai_service.analyze_semantics(videos)
        self._cache.set(key, response)
        return response

    async def analyze_stream(
        self, videos: List[VideoAnalysisInput]
    ) -> AsyncGenerator[str, None]:
        """
        Stream analysis with caching.
        On cache hit, simulates streaming from the cached full response.
        On cache miss, accumulates the stream and caches the result.
        """
        key = self._generate_key(videos)
        cached_response = self._cache.get(key)

        if cached_response:
            logger.info("Cache hit for analyze_stream.")
            # Simulate streaming by splitting by whitespace boundaries to preserve structure
            # re.split(r'(\s+)', text) keeps separators (spaces, newlines)
            tokens = re.split(r'(\s+)', cached_response)
            for token in tokens:
                if token:  # Skip empty strings if any
                    yield token
                    # Simulate latency
                    await asyncio.sleep(0.01)
            return

        logger.info("Cache miss for analyze_stream. Calling AI service.")
        full_response_accumulator = []
        async for chunk in self._ai_service.analyze_stream(videos):
            full_response_accumulator.append(chunk)
            yield chunk

        # Reconstruct full response
        full_response = "".join(full_response_accumulator)

        # We strip strictly to avoid leading/trailing whitespace accumulation issues if any,
        # but re.split handles whitespace well so it's safer now.
        self._cache.set(key, full_response.strip())
