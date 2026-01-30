"""
AI Service layer for Bachata Brain Breaks Analytics.
Defines contracts and implementations for AI analysis, supporting streaming.
"""
from typing import Protocol, List, AsyncGenerator
import asyncio
from src.core.domain import VideoAnalysisInput

class AIService(Protocol):
    """
    Protocol for AI Analysis Service.
    Allows for different implementations (Mock, Real API, etc).
    """
    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Standard synchronous analysis.
        """
        ...

    async def analyze_stream(self, videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        """
        Streaming analysis that yields chunks of text.
        """
        ...

class GeminiStreamingService:
    """
    Implementation of AIService using Gemini (Simulated for now).
    """

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Synchronous wrapper for legacy compatibility.
        """
        # For sync calls, we just return the full text.
        # In a real app, this might call the sync version of the API.
        if not videos:
            return "No data to analyze."

        return (
            "[Gemini 3 Thinking Mode] Analysis Complete:\n"
            "1. Pattern Identification: High-retention videos often use 'sensual' or 'footwork' keywords.\n"
            "2. Strategy: Use high-contrast thumbnails with dynamic poses.\n"
            "3. Recommendation: Rename lower performers to include 'Step-by-Step' hook."
        )

    async def analyze_stream(self, videos: List[VideoAnalysisInput]):
        """
        Simulates streaming response from an AI model.
        Yields chunks of text to demonstrate WebSocket capabilities.
        """
        if not videos:
            yield "No data to analyze."
            return

        # The simulated response
        response_text = (
            "[Gemini 3 Thinking Mode] Analysis Started...\n"
            "Analyzing " + str(len(videos)) + " videos...\n"
            "1. Pattern Identification: High-retention videos often use 'sensual' or 'footwork' keywords.\n"
            "2. Strategy: Use high-contrast thumbnails with dynamic poses.\n"
            "3. Recommendation: Rename lower performers to include 'Step-by-Step' hook.\n"
            "Analysis Complete."
        )

        # Simulate token generation
        chunk_size = 5
        for i in range(0, len(response_text), chunk_size):
            chunk = response_text[i:i+chunk_size]
            yield chunk
            # Simulate network/processing delay
            await asyncio.sleep(0.05)
