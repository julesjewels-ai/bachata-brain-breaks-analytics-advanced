from src.core.services.ai import AIService, GeminiStreamingService

def get_ai_service() -> AIService:
    """
    Dependency provider for AIService.
    In a real app, this might pull from a configured container.
    """
    return GeminiStreamingService()
