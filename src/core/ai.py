"""
AI Service implementation using Google Gemini.
Implements the AIService protocol.
"""
import os
import logging
import asyncio
from typing import List, Dict, Any, AsyncGenerator, Optional
import google.generativeai as genai
from src.core.interfaces import AIService

logger = logging.getLogger(__name__)

class GeminiService(AIService):
    """
    Implementation of AIService using Google's Gemini models.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model = None

        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel("gemini-pro")
            except Exception as e:
                logger.error(f"Failed to configure Gemini: {e}")
        else:
            logger.warning("GOOGLE_API_KEY not found. GeminiService will use mock responses.")

    def _prepare_prompt(self, videos: List[Dict[str, Any]]) -> str:
        """Constructs a prompt from the video data."""
        prompt = (
            "You are a YouTube Analytics expert. Analyze the following video performance data "
            "and suggest a specific content strategy to improve views and retention.\n\n"
            "Data:\n"
        )
        for v in videos:
            title = v.get('title', 'Unknown')
            views = v.get('views', 0)
            retention = v.get('retention_avg_pct', 0)
            v_type = v.get('type', 'Video')
            prompt += f"- [{v_type}] '{title}': {views} views, {retention}% retention\n"

        prompt += "\nProvide a concise strategy focusing on titles and content gaps."
        return prompt

    def analyze_semantics(self, videos: List[Dict[str, Any]]) -> str:
        """
        Synchronous analysis using Gemini.
        """
        if not self.model:
            return (
                "[Mock] Gemini Analysis: Focus on high retention content. "
                "Consider renaming 'Part 1' videos to include specific outcomes."
            )

        try:
            prompt = self._prepare_prompt(videos)
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return f"Error generating analysis: {e}"

    async def analyze_stream(self, videos: List[Dict[str, Any]]) -> AsyncGenerator[str, None]:
        """
        Streaming analysis using Gemini async API.
        """
        if not self.model:
            # Mock streaming response
            mock_response = (
                "**[Mock] Streaming Analysis**\n\n"
                "1. **Observation**: High retention on 'Sensual' videos.\n"
                "2. **Strategy**: Double down on partner work tutorials.\n"
                "3. **Action**: Create a series on 'Connection Secrets'."
            )
            tokens = mock_response.split(' ')
            for token in tokens:
                yield token + " "
                await asyncio.sleep(0.05) # Simulate network delay
            return

        try:
            prompt = self._prepare_prompt(videos)
            # stream=True returns a generator, but generate_content_async returns an awaitable that resolves to a response
            # For streaming, we use generate_content_async(stream=True) which returns an async generator?
            # Actually, per docs: await model.generate_content_async(..., stream=True) returns an AsyncIterable
            response = await self.model.generate_content_async(prompt, stream=True)
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Gemini Streaming API error: {e}")
            yield f"Error generating stream: {e}"
