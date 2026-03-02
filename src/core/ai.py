"""
AI Services for Bachata Brain Breaks Analytics.
"""
import asyncio
from typing import List, AsyncGenerator
from src.core.interfaces import AIService
from src.core.models import VideoAnalysisInput
from src.core.config import AppConfig
from google import genai
from google.genai import types

class GeminiThinkingAgent(AIService):
    """
    Connects to Gemini 3 'Thinking Mode' to analyze semantic patterns.
    """
    def __init__(self):
        config = AppConfig.get_config()
        self.client = genai.Client(
            api_key=config.get_api_key(),
            http_options={'api_version': 'v1beta', 'timeout': 300_000}
        )
        self.model_name = "gemini-3-pro-preview"

    def _build_prompt(self, videos: List[VideoAnalysisInput]) -> str:
        prompt = "Analyze the following YouTube video data and identify semantic patterns for high retention:\n\n"
        for v in videos:
            prompt += f"- ID: {v.video_id} | Title: {v.title} | Views: {v.views} | Retention: {v.retention_avg_pct}% | Type: {v.type}\n"
        prompt += "\nProvide a strategic recommendation on thumbnail styles, keywords, and overarching topics. Be concise."
        return prompt

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Analyzes titles and thumbnails (metadata) to find conversion patterns.
        Now strictly typed for security.
        """
        if not videos:
            return "No data to analyze."

        prompt = self._build_prompt(videos)

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(include_thoughts=True),
                temperature=1.0,
            ),
        )

        return response.text if response.text else "No text response generated."

    async def analyze_stream(self, videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        """
        Stream analysis of video metadata.
        """
        if not videos:
            yield "No data to analyze."
            return

        prompt = self._build_prompt(videos)

        response_stream = await self.client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(include_thoughts=True),
                temperature=1.0,
            ),
        )

        async for chunk in response_stream:
            if chunk.text:
                yield chunk.text
