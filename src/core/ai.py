"""
AI Services for Bachata Brain Breaks Analytics.
"""
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
    PRIMARY_MODEL = "gemini-3-pro-preview"
    FALLBACK_MODEL = "gemini-2.5-flash"

    def __init__(self):
        config = AppConfig.get_config()
        self.client = genai.Client(
            api_key=config.get_api_key(),
            http_options={'api_version': 'v1beta', 'timeout': 300_000}
        )

    def _build_prompt(self, videos: List[VideoAnalysisInput]) -> str:
        header = (
            "Analyze the following YouTube video data and identify "
            "semantic patterns for high retention:\n\n"
        )
        lines = [
            f"- ID: {v.video_id} | Title: {v.title} | Views: {v.views}"
            f" | Retention: {v.retention_avg_pct}% | Type: {v.type}"
            for v in videos
        ]
        footer = (
            "\nProvide a strategic recommendation on thumbnail styles, "
            "keywords, and overarching topics. Be concise."
        )
        return header + "\n".join(lines) + footer

    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Analyzes titles and thumbnails (metadata) to find conversion patterns.
        Now strictly typed for security.
        """
        if not videos:
            return "No data to analyze."

        prompt = self._build_prompt(videos)

        response = self.client.models.generate_content(
            model=self.PRIMARY_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(include_thoughts=True),
                temperature=1.0,
            ),
        )

        return response.text if response.text else (
            "No text response generated."
        )

    async def _stream_primary_model(
        self, prompt: str
    ) -> AsyncGenerator[str, None]:
        """
        Attempts to generate content stream using the primary model.
        """
        response_stream = await self.client.aio.models.generate_content_stream(
            model=self.PRIMARY_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(include_thoughts=True),
                temperature=1.0,
            ),
        )
        async for chunk in response_stream:
            if chunk.text:
                yield chunk.text

    async def _stream_fallback_model(
            self, prompt: str) -> AsyncGenerator[str, None]:
        """
        Attempts to generate content stream using the fallback model.
        """
        fallback_stream = await self.client.aio.models.generate_content_stream(
            model=self.FALLBACK_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,  # standard temperature for 2.5 flash
            ),
        )
        async for chunk in fallback_stream:
            if chunk.text:
                yield chunk.text

    async def analyze_stream(
        self, videos: List[VideoAnalysisInput]
    ) -> AsyncGenerator[str, None]:
        """
        Stream analysis of video metadata with a fallback mechanism.
        """
        if not videos:
            yield "No data to analyze."
            return

        prompt = self._build_prompt(videos)

        try:
            # Attempt primary model (Gemini 3 Pro Preview with Thinking)
            async for text in self._stream_primary_model(prompt):
                yield text
        except Exception as primary_err:
            # Yield a clear fallback message
            yield (
                f"\n[warning] Primary model failed ({primary_err}). "
                f"Falling back to {self.FALLBACK_MODEL}...[/warning]\n\n"
            )

            try:
                async for text in self._stream_fallback_model(prompt):
                    yield text
            except Exception as fallback_err:
                yield (
                    f"\n[error] Fallback model also failed: {fallback_err}. "
                    "Please try again later.[/error]\n"
                )
