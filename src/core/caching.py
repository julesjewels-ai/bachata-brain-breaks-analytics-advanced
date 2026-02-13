"""
Caching module for Bachata Brain Breaks Analytics.
Provides InMemoryCacheBackend and CachedAIService wrapper.
"""
import asyncio
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, AsyncGenerator
from src.core.interfaces import CacheBackend, AIService
from src.core.models import CacheEntry, VideoAnalysisInput

class CacheError(Exception):
    """Base exception for cache operations."""
    pass

class SerializationError(CacheError):
    """Raised when serialization fails."""
    pass

class InMemoryCacheBackend(CacheBackend):
    """
    Simple in-memory cache backend using a dictionary.
    """
    def __init__(self) -> None:
        self._store: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if not entry:
            return None
        if time.time() > entry.expires_at:
            del self._store[key]
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        expires_at = time.time() + ttl
        self._store[key] = CacheEntry(key=key, value=value, expires_at=expires_at)

    def delete(self, key: str) -> None:
        if key in self._store:
            del self._store[key]

    def clear(self) -> None:
        self._store.clear()

class CachedAIService:
    """
    Decorator/Proxy for AIService that adds caching.
    """
    def __init__(self, service: AIService, cache: CacheBackend):
        self._service = service
        self._cache = cache

    def _generate_key(self, videos: List[VideoAnalysisInput], prefix: str) -> str:
        """Generates a stable cache key based on input data."""
        try:
            # Sort by video_id to ensure order independence?
            # Or preserve order?
            # If the analysis depends on the order (e.g. top 5), we must preserve order.
            # So we iterate over the list as is.
            data = [v.model_dump() for v in videos]
            # Use sort_keys=True for deterministic JSON representation of the dictionaries
            serialized = json.dumps(data, sort_keys=True)
            hashed = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
            return f"{prefix}:{hashed}"
        except Exception as e:
            raise SerializationError(f"Failed to generate cache key: {e}")

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Cached version of analyze_semantics.
        """
        key = self._generate_key(videos, "semantics")
        cached = self._cache.get(key)
        if cached is not None and isinstance(cached, str):
            return cached

        result = self._service.analyze_semantics(videos)
        self._cache.set(key, result)
        return result

    async def analyze_stream(self, videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        """
        Cached version of analyze_stream.
        Replays cached data in chunks to simulate streaming.
        """
        key = self._generate_key(videos, "stream")
        cached = self._cache.get(key)

        if cached is not None and isinstance(cached, str):
            # Replay from cache
            chunk_size = 50
            for i in range(0, len(cached), chunk_size):
                chunk = cached[i:i+chunk_size]
                yield chunk
                # Simulate async stream delay
                await asyncio.sleep(0.01)
            return

        # Cache miss: consume stream and accumulate
        full_response_parts: List[str] = []
        async for chunk in self._service.analyze_stream(videos):
            full_response_parts.append(chunk)
            yield chunk

        full_response = "".join(full_response_parts)
        self._cache.set(key, full_response)
