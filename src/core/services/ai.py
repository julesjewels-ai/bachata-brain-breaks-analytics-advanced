"""
AI Services for semantic analysis.
"""
from typing import List, Protocol, Generator
from src.core.domain import VideoAnalysisInput


class AIService(Protocol):
    """Interface for AI analysis services."""

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        """Synchronously analyze video semantics."""
        ...

    def analyze_stream(
        self, videos: List[VideoAnalysisInput]
    ) -> Generator[str, None, None]:
        """Stream analysis results."""
        ...


class GeminiStreamingService:
    """
    Simulates Gemini 3 'Thinking Mode' to analyze semantic patterns.
    """
    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Analyzes titles and thumbnails (metadata) to find conversion patterns.
        """
        if not videos:
            return "No data to analyze."

        # Simulated 'Thinking Mode' logic
        return (
            "[Gemini 3 Thinking Mode] Analysis Complete:\n"
            "1. Pattern Identification: High-retention videos often use "
            "'sensual' or 'footwork' keywords.\n"
            "2. Strategy: Use high-contrast thumbnails with dynamic poses.\n"
            "3. Recommendation: Rename lower performers to include "
            "'Step-by-Step' hook."
        )

    def analyze_stream(
        self, videos: List[VideoAnalysisInput]
    ) -> Generator[str, None, None]:
        """
        Simulates streaming response chunks.
        """
        if not videos:
            yield "No data to analyze."
            return

        chunks = [
            "[Gemini 3 Thinking Mode] Starting Analysis...\n",
            "Processing 10 videos...\n",
            "Identifying patterns in titles and retention...\n",
            "1. Pattern Identification: High-retention videos often use "
            "'sensual' or 'footwork' keywords.\n",
            "2. Strategy: Use high-contrast thumbnails with dynamic poses.\n",
            "3. Recommendation: Rename lower performers to include "
            "'Step-by-Step' hook.\n",
            "Analysis Complete."
        ]

        for chunk in chunks:
            yield chunk
