"""
Services module for external integrations.
"""
import logging
from typing import List, Any, Optional
import google.generativeai as genai
from src.core.interfaces import AIService
from src.core.config import AppConfig

logger = logging.getLogger(__name__)

class GeminiStreamingService:
    """
    Implementation of AIService using Google's Gemini API.
    """
    def __init__(self) -> None:
        self.model: Optional[genai.GenerativeModel] = None
        try:
            config = AppConfig.get_config()
            # Attempt to get API key. If missing, this raises ValueError.
            api_key = config.get_api_key()
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        except Exception as e:
            logger.warning(f"Gemini Service initialization failed: {e}")
            # We don't raise here to allow the app to run other features.

    def analyze_semantics(self, videos: List[Any]) -> str:
        """
        Analyzes video data using Gemini.
        """
        if not self.model:
            return "Gemini Service Unavailable: Check API configuration."

        if not videos:
            return "No data to analyze."

        # Serialize input
        lines = []
        for v in videos:
            # Handle both object and dict access for robustness
            if hasattr(v, 'title'):
                title = v.title
                views = v.views
                ret = v.retention_avg_pct
            elif isinstance(v, dict):
                title = v.get('title')
                views = v.get('views')
                ret = v.get('retention_avg_pct')
            else:
                continue # Skip unknown format

            lines.append(f"- {title} (Views: {views}, Retention: {ret}%)")

        data_summary = "\n".join(lines)

        prompt = (
            "Analyze the following video performance data for a Bachata dance channel. "
            "Identify semantic patterns in titles and performance metrics. "
            "Provide a strategy for titles and thumbnails to improve conversion.\n\n"
            f"Data:\n{data_summary}\n\n"
            "Output Format:\n"
            "1. Pattern Identification\n"
            "2. Strategy\n"
            "3. Recommendation"
        )

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return f"Error generating analysis: {e}"
