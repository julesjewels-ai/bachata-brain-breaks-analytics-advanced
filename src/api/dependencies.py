from functools import lru_cache
from src.core.interfaces import AIService
from src.core.ai import GeminiThinkingAgent

@lru_cache()
def get_ai_service() -> AIService:
    """
    Dependency provider for AIService.
    Uses lru_cache to ensure a singleton instance.
    """
    return GeminiThinkingAgent()
