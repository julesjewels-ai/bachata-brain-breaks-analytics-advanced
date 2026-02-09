"""
Caching module providing backend implementations and service logic.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, AsyncGenerator
import json
import hashlib

from src.core.interfaces import CacheBackend, AIService
from src.core.models import CacheEntry, VideoAnalysisInput

class CacheError(Exception):
    """Base exception for caching errors."""
    pass

class SerializationError(CacheError):
    """Raised when data serialization for cache key generation fails."""
    pass

class InMemoryCacheBackend(CacheBackend):
    """
    In-memory implementation of CacheBackend using a dictionary.
    Thread-safe enough for asyncio contexts (single-threaded loop).
    """
    def __init__(self) -> None:
        self._store: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if not entry:
            return None

        # Check expiration
        if entry.expires_at and entry.expires_at < datetime.now():
            self.delete(key)
            return None

        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        expires_at = None
        if ttl:
            expires_at = datetime.now() + timedelta(seconds=ttl)

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=datetime.now(),
            expires_at=expires_at
        )
        self._store[key] = entry

    def delete(self, key: str) -> None:
        if key in self._store:
            del self._store[key]

    def clear(self) -> None:
        self._store.clear()


class CacheService:
    """
    Service layer for caching operations.
    """
    def __init__(self, backend: CacheBackend):
        self._backend = backend

    def get(self, key: str) -> Optional[Any]:
        return self._backend.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._backend.set(key, value, ttl)

    def generate_key(self, prefix: str, data: Any) -> str:
        """Generates a consistent cache key."""
        try:
            # Handle Pydantic models
            if hasattr(data, "model_dump_json"):
                 serialized = data.model_dump_json()
            elif isinstance(data, list):
                 # Handle list of Pydantic models
                 serialized = json.dumps([
                     d.model_dump() if hasattr(d, "model_dump") else d
                     for d in data
                 ], sort_keys=True, default=str)
            else:
                 serialized = str(data)

            hash_digest = hashlib.sha256(serialized.encode()).hexdigest()
            return f"{prefix}:{hash_digest}"
        except Exception as e:
            raise SerializationError(f"Failed to generate cache key: {e}") from e


class CachedAIService:
    """
    Decorator/Proxy for AIService that adds caching.
    """
    def __init__(self, service: AIService, cache_service: CacheService, ttl: int = 3600):
        self._service = service
        self._cache = cache_service
        self._ttl = ttl

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        # Use a consistent key prefix for semantics
        key = self._cache.generate_key("ai_semantics", videos)
        cached = self._cache.get(key)
        if cached:
            return str(cached)

        result = self._service.analyze_semantics(videos)
        self._cache.set(key, result, ttl=self._ttl)
        return result

    async def analyze_stream(self, videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        # Use the same key so we can hit the cache populated by analyze_semantics
        key = self._cache.generate_key("ai_semantics", videos)
        cached = self._cache.get(key)

        if cached and isinstance(cached, str):
            # Simulate streaming from cache
            yield "[Cached] "
            words = cached.split(' ')
            for word in words:
                yield word + " "
                # Simulate faster streaming for cached content
                await asyncio.sleep(0.005)
            return

        # Cache miss
        full_response_accum: List[str] = []
        async for chunk in self._service.analyze_stream(videos):
            full_response_accum.append(chunk)
            yield chunk

        # Store accumulated response
        full_text = "".join(full_response_accum)
        self._cache.set(key, full_text, ttl=self._ttl)
