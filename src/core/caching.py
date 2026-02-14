"""
Caching module for AI Service responses.
Implements a caching layer to reduce API calls and improve performance.
"""
import hashlib
import json
import asyncio
import logging
from typing import Protocol, Any, Optional, Dict, List, AsyncGenerator
from datetime import datetime, timedelta
from pydantic import BaseModel
from src.core.interfaces import AIService
from src.core.models import VideoAnalysisInput

logger = logging.getLogger(__name__)

class CacheError(Exception):
    """Base exception for caching errors."""
    pass

class SerializationError(CacheError):
    """Error during key serialization."""
    pass

class CacheEntry(BaseModel):
    """Model for a cached value with metadata."""
    key: str
    value: Any
    expires_at: Optional[datetime] = None

class CacheBackend(Protocol):
    """
    Protocol for cache backends.
    """
    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from the cache."""
        ...

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set a value in the cache.

        Args:
            key: Unique key.
            value: Data to store.
            ttl: Time-to-live in seconds.
        """
        ...

    def delete(self, key: str) -> None:
        """Remove a value from the cache."""
        ...

    def clear(self) -> None:
        """Clear all values from the cache."""
        ...

class InMemoryCacheBackend:
    """
    Simple in-memory cache using a dictionary.
    Thread-safe enough for this use case (GIL).
    """
    def __init__(self) -> None:
        self._store: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            return None

        entry = self._store[key]
        if entry.expires_at and datetime.now() > entry.expires_at:
            self.delete(key)
            return None

        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        expires_at = datetime.now() + timedelta(seconds=ttl) if ttl else None
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
    def __init__(self, service: AIService, cache: CacheBackend, ttl: int = 3600):
        self.service = service
        self.cache = cache
        self.ttl = ttl

    def _generate_key(self, videos: List[VideoAnalysisInput]) -> str:
        """Generates a deterministic SHA256 hash for the input."""
        try:
            # Pydantic models to dicts
            data = [v.model_dump() for v in videos]
            # Serialize with sorted keys for determinism
            json_str = json.dumps(data, sort_keys=True, default=str)
            return hashlib.sha256(json_str.encode('utf-8')).hexdigest()
        except Exception as e:
            raise SerializationError(f"Failed to generate cache key: {e}")

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        key = f"semantics:{self._generate_key(videos)}"
        cached = self.cache.get(key)

        if cached:
            logger.info(f"Cache Hit for semantics: {key}")
            return str(cached)

        logger.info(f"Cache Miss for semantics: {key}")
        result = self.service.analyze_semantics(videos)
        self.cache.set(key, result, ttl=self.ttl)
        return result

    async def analyze_stream(self, videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        key = f"stream:{self._generate_key(videos)}"
        cached = self.cache.get(key)

        if cached:
            logger.info(f"Cache Hit for stream: {key}")
            # Replay cached string in chunks
            full_text = str(cached)
            chunk_size = 50
            for i in range(0, len(full_text), chunk_size):
                yield full_text[i:i+chunk_size]
                # Simulate streaming delay
                await asyncio.sleep(0.01)
            return

        logger.info(f"Cache Miss for stream: {key}")
        full_response_parts = []
        async for chunk in self.service.analyze_stream(videos):
            full_response_parts.append(chunk)
            yield chunk

        # Cache the full response
        full_response = "".join(full_response_parts)
        self.cache.set(key, full_response, ttl=self.ttl)
