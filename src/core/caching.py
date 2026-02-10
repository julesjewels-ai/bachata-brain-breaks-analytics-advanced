"""
Caching module for Bachata Brain Breaks Analytics.
Provides caching services and backends to optimize performance.
"""
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict, List, Optional

from src.core.interfaces import AIService, CacheBackend
from src.core.models import CacheEntry, VideoAnalysisInput

class CacheError(Exception):
    """Base exception for caching errors."""
    pass

class SerializationError(CacheError):
    """Raised when serialization fails."""
    pass

class InMemoryCacheBackend(CacheBackend):
    """
    In-memory implementation of CacheBackend using a dictionary.
    Thread-safe for single-process applications (GIL).
    """
    def __init__(self) -> None:
        self._store: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            return None

        entry = self._store[key]
        if entry.expires_at and datetime.now() > entry.expires_at:
            del self._store[key]
            return None

        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        expires_at = datetime.now() + timedelta(seconds=ttl) if ttl else None
        # Validates data against schema before storing
        entry = CacheEntry(key=key, value=value, expires_at=expires_at)
        self._store[key] = entry

    def delete(self, key: str) -> None:
        if key in self._store:
            del self._store[key]

class CachedAIService(AIService):
    """
    Decorator/Proxy for AIService that adds caching capabilities.
    """
    def __init__(self, service: AIService, cache: CacheBackend, ttl: int = 3600):
        self._service = service
        self._cache = cache
        self._ttl = ttl

    def _generate_key(self, prefix: str, videos: List[VideoAnalysisInput]) -> str:
        """Generates a consistent cache key based on video inputs."""
        # Create a canonical representation of the input
        # Convert Pydantic models to dicts and sort keys for consistency
        data_list = [v.model_dump() for v in videos]
        # Sort list by video_id to ensure order independence if needed,
        # but inputs are usually ordered. Let's assume input order matters.

        data_str = json.dumps(
            data_list,
            sort_keys=True,
            default=str
        )
        hash_digest = hashlib.sha256(data_str.encode('utf-8')).hexdigest()
        return f"{prefix}:{hash_digest}"

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        key = self._generate_key("semantics", videos)
        cached = self._cache.get(key)

        if cached is not None:
            return str(cached)

        result = self._service.analyze_semantics(videos)
        self._cache.set(key, result, ttl=self._ttl)
        return result

    async def analyze_stream(self, videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        key = self._generate_key("stream", videos)
        cached = self._cache.get(key)

        if cached is not None:
            # Replay cached stream without altering content
            full_text = str(cached)
            # Simulate streaming by yielding chunks
            chunk_size = 50
            for i in range(0, len(full_text), chunk_size):
                yield full_text[i:i + chunk_size]
            return

        # Cache Miss: Capture stream
        full_response = []
        async for chunk in self._service.analyze_stream(videos):
            full_response.append(chunk)
            yield chunk

        # Cache the full result
        self._cache.set(key, "".join(full_response), ttl=self._ttl)
