"""
Caching mechanisms for the application.
"""
import hashlib
import asyncio
from pathlib import Path
from typing import Optional, List, AsyncGenerator
from src.core.interfaces import CacheBackend, AIService
from src.core.models import VideoAnalysisInput


class FileCacheBackend(CacheBackend):
    """
    File-based implementation of CacheBackend.
    """
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.txt"

    def get(self, key: str) -> Optional[str]:
        path = self._get_path(key)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def set(self, key: str, value: str) -> None:
        path = self._get_path(key)
        path.write_text(value, encoding="utf-8")


class CachedAIService(AIService):
    """
    Decorator for AIService that adds transparent caching.
    """
    def __init__(self, service: AIService, backend: CacheBackend):
        self.service = service
        self.backend = backend

    def _hash(self, videos: List[VideoAnalysisInput]) -> str:
        # Use Pydantic's model_dump_json for consistent serialization
        data = "".join(v.model_dump_json() for v in videos)
        return hashlib.sha256(data.encode()).hexdigest()

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        key = self._hash(videos)
        cached = self.backend.get(key)
        if cached:
            return cached

        result = self.service.analyze_semantics(videos)
        self.backend.set(key, result)
        return result

    async def analyze_stream(
        self, videos: List[VideoAnalysisInput]
    ) -> AsyncGenerator[str, None]:
        key = self._hash(videos)
        cached = self.backend.get(key)

        if cached:
            # Simulate streaming from cache
            # Split by space to mimic token streaming
            tokens = cached.split(' ')
            for token in tokens:
                yield token + " "
                # Simulate fast network/generation
                await asyncio.sleep(0.01)
            return

        # Cache miss
        full_response = []
        async for chunk in self.service.analyze_stream(videos):
            full_response.append(chunk)
            yield chunk

        self.backend.set(key, "".join(full_response))
