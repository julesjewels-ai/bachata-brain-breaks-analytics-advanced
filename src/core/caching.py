"""
Caching module for AI services.
Implements the Decorator pattern to add caching behavior to AIService implementations.
"""
import time
import json
import hashlib
import asyncio
from typing import Optional, Any, List, AsyncGenerator, Dict
from src.core.interfaces import CacheBackend, AIService
from src.core.models import CacheEntry, VideoAnalysisInput

class InMemoryCacheBackend(CacheBackend):
    """
    In-memory implementation of CacheBackend using a dictionary.
    Suitable for development and single-instance deployments.
    """
    def __init__(self) -> None:
        self._store: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        """Retrieves a value from the cache if it exists and hasn't expired."""
        entry = self._store.get(key)
        if not entry:
            return None

        if entry.expires_at and time.time() > entry.expires_at:
            del self._store[key]
            return None

        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Sets a value in the cache with an optional TTL (in seconds)."""
        expires_at = time.time() + ttl if ttl else None
        entry = CacheEntry(key=key, value=value, expires_at=expires_at)
        self._store[key] = entry

    def delete(self, key: str) -> None:
        """Deletes a value from the cache."""
        if key in self._store:
            del self._store[key]


class CachedAIService(AIService):
    """
    Decorator for AIService that caches results.
    Adheres to the Open/Closed Principle by extending behavior without modifying the base service.
    """
    def __init__(self, service: AIService, cache: CacheBackend, ttl: int = 3600):
        self.service = service
        self.cache = cache
        self.ttl = ttl

    def _generate_key(self, method: str, videos: List[VideoAnalysisInput]) -> str:
        """Generates a unique cache key based on the method and input data."""
        # Serialize input strictly to ensure deterministic keys
        # We use Pydantic's model_dump_json for consistent serialization
        data_str = json.dumps([v.model_dump() for v in videos], sort_keys=True)
        hash_digest = hashlib.sha256(data_str.encode('utf-8')).hexdigest()
        return f"ai_service:{method}:{hash_digest}"

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Analyzes video metadata with caching.
        """
        key = self._generate_key("semantics", videos)
        cached_result = self.cache.get(key)

        if cached_result:
            return str(cached_result)

        result = self.service.analyze_semantics(videos)
        self.cache.set(key, result, ttl=self.ttl)
        return result

    async def analyze_stream(self, videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        """
        Stream analysis with caching.
        """
        key = self._generate_key("stream", videos)
        cached_result = self.cache.get(key)

        if cached_result:
            # Replay from cache
            # Simulate streaming behavior by yielding chunks
            full_text = str(cached_result)
            chunk_size = 10 # Arbitrary chunk size for replay
            for i in range(0, len(full_text), chunk_size):
                yield full_text[i:i+chunk_size]
                # Simulate a tiny delay for realism, though not strictly required
                await asyncio.sleep(0.01)
            return

        # Cache miss: Consume stream from service, yield, and aggregate
        full_response = []
        async for chunk in self.service.analyze_stream(videos):
            full_response.append(chunk)
            yield chunk

        # Store aggregated result
        self.cache.set(key, "".join(full_response), ttl=self.ttl)
