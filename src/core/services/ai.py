"""
AI Service implementation using Gemini (Simulated).
"""
import asyncio
from typing import List, AsyncGenerator
from src.core.domain import VideoAnalysisInput
# Implicitly implements AIService protocol

class GeminiStreamingService:
    """
    Service for AI analysis using Gemini (simulated).
    Implements AIService protocol.
    """
    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Analyzes titles and thumbnails (metadata) to find conversion patterns.
        Synchronous version for CLI compatibility.
        """
        if not videos:
            return "No data to analyze."

        # Simulated 'Thinking Mode' logic
        return (
            "[Gemini 3 Thinking Mode] Analysis Complete:\n"
            "1. Pattern Identification: High-retention videos often use 'sensual' or 'footwork' keywords.\n"
            "2. Strategy: Use high-contrast thumbnails with dynamic poses.\n"
            "3. Recommendation: Rename lower performers to include 'Step-by-Step' hook."
        )

    async def analyze_stream(self, videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        """
        Streams the analysis response token by token (simulated).
        """
        if not videos:
            yield "No data to analyze."
            return

        full_response = self.analyze_semantics(videos)

        # Simulate streaming by yielding chunks
        chunk_size = 5
        for i in range(0, len(full_response), chunk_size):
            yield full_response[i:i+chunk_size]
            await asyncio.sleep(0.01) # Simulate network latency (fast enough for tests)
