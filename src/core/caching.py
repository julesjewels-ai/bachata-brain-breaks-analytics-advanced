"""
Caching services for Bachata Brain Breaks Analytics.
Provides caching mechanisms for AI operations.
"""
import hashlib
import json
import asyncio
from pathlib import Path
from typing import List, Optional, AsyncGenerator
from src.core.interfaces import AIService, CacheBackend
from src.core.models import VideoAnalysisInput


class FileCacheBackend(CacheBackend):
    """
    File-based implementation of CacheBackend.
    Stores cached values in a local directory using hashed keys as filenames.
    """
    def __init__(self, cache_dir: str = ".cache/ai_responses"):
        self.cache_dir = Path(cache_dir)
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            msg = f"Failed to initialize cache directory '{cache_dir}': {e}"
            raise RuntimeError(msg)

    def get(self, key: str) -> Optional[str]:
        """
        Retrieves a value from the cache if it exists.
        """
        filepath = self.cache_dir / f"{self._hash_key(key)}.txt"
        if filepath.exists():
            try:
                return filepath.read_text(encoding="utf-8")
            except Exception:
                return None
        return None

    def set(self, key: str, value: str) -> None:
        """
        Sets a value in the cache. Best effort; ignores write errors.
        """
        filepath = self.cache_dir / f"{self._hash_key(key)}.txt"
        try:
            filepath.write_text(value, encoding="utf-8")
        except Exception:
            pass

    def _hash_key(self, key: str) -> str:
        """
        Generates a SHA-256 hash of the key for safe usage as a filename.
        """
        return hashlib.sha256(key.encode("utf-8")).hexdigest()


class CachedAIService(AIService):
    """
    Decorator for AIService that adds caching capabilities.
    Wraps an underlying AIService and uses a CacheBackend to store results.
    """
    def __init__(self, service: AIService, cache: CacheBackend):
        self.service = service
        self.cache = cache

    def _generate_key(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Generates a unique deterministic cache key based on the input data.
        """
        # Convert Pydantic models to dicts
        data = [v.model_dump() for v in videos]
        # Serialize to JSON with sorted keys for determinism
        return json.dumps(data, sort_keys=True, default=str)

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Analyzes semantics with caching.
        """
        key = self._generate_key(videos)
        cached = self.cache.get(key)
        if cached:
            return cached

        result = self.service.analyze_semantics(videos)
        self.cache.set(key, result)
        return result

    async def analyze_stream(
        self, videos: List[VideoAnalysisInput]
    ) -> AsyncGenerator[str, None]:
        """
        Stream analysis with caching.
        On cache hit: replays the full response as a simulated stream.
        On cache miss: consumes the real stream, yields it, and caches.
        """
        key = self._generate_key(videos)
        cached = self.cache.get(key)

        if cached:
            # Simulate stream from cache
            # Chunk by 4 characters to mimic token generation speed
            chunk_size = 4
            for i in range(0, len(cached), chunk_size):
                yield cached[i:i + chunk_size]
                # Small delay to mimic generation latency
                await asyncio.sleep(0.01)
            return

        # Cache miss
        full_response_parts: List[str] = []
        async for chunk in self.service.analyze_stream(videos):
            full_response_parts.append(chunk)
            yield chunk

        self.cache.set(key, "".join(full_response_parts))
