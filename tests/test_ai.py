"""Tests for the AI Services."""
import pytest
from unittest.mock import Mock, patch
from typing import List, Any, cast

from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from src.core.config import AppConfig


class AsyncGenMock:
    """Mock for an async generator to test streaming."""
    def __init__(self, items: List[Mock]):
        self.items = items
        self.idx = 0

    def __await__(self) -> Any:
        async def _await_impl() -> "AsyncGenMock":
            return self
        return _await_impl().__await__()

    async def __anext__(self) -> Mock:
        if self.idx < len(self.items):
            item = self.items[self.idx]
            self.idx += 1
            return item
        raise StopAsyncIteration

    def __aiter__(self) -> "AsyncGenMock":
        return self


@pytest.fixture
def mock_app_config() -> Any:
    """Mock the AppConfig to prevent reading real environment variables."""
    with patch("src.core.ai.AppConfig.get_config") as mock_get_config:
        config_instance = Mock(spec=AppConfig)
        config_instance.get_api_key.return_value = "fake_api_key"
        mock_get_config.return_value = config_instance
        yield mock_get_config


@pytest.fixture
def agent(mock_app_config: Any) -> GeminiThinkingAgent:
    """Returns a GeminiThinkingAgent with mocked dependencies."""
    with patch("src.core.ai.genai.Client"):
        return GeminiThinkingAgent()


@pytest.fixture
def videos() -> List[VideoAnalysisInput]:
    """Provide some dummy videos."""
    return [
        VideoAnalysisInput(
            video_id="v1",
            title="Video 1",
            views=1000,
            retention_avg_pct=50.0,
            type="Shorts"
        )
    ]


@pytest.mark.asyncio
async def test_analyze_stream_empty_videos(agent: GeminiThinkingAgent) -> None:
    """Test analyze_stream when the video list is empty."""
    chunks = [chunk async for chunk in agent.analyze_stream([])]
    assert chunks == ["No data to analyze."]


@pytest.mark.asyncio
async def test_analyze_stream_success(
    agent: GeminiThinkingAgent, videos: List[VideoAnalysisInput]
) -> None:
    """Test analyze_stream when the primary model succeeds."""
    mock_chunk1 = Mock()
    mock_chunk1.text = "Chunk 1 "
    mock_chunk2 = Mock()
    mock_chunk2.text = "Chunk 2"

    agent.client.aio.models.generate_content_stream = cast(Any, Mock(
        return_value=AsyncGenMock([mock_chunk1, mock_chunk2])
    )) # type: ignore[method-assign]

    chunks = [chunk async for chunk in agent.analyze_stream(videos)]
    assert chunks == ["Chunk 1 ", "Chunk 2"]


@pytest.mark.asyncio
async def test_analyze_stream_primary_fail_fallback_success(
    agent: GeminiThinkingAgent, videos: List[VideoAnalysisInput]
) -> None:
    """Test analyze_stream when the primary model fails but fallback succeeds."""
    # Raise an exception for the primary model
    agent.client.aio.models.generate_content_stream = cast(Any, Mock(
        side_effect=[
            Exception("Primary Model API Error"),
            AsyncGenMock([Mock(text="Fallback Chunk 1")])
        ]
    )) # type: ignore[method-assign]

    chunks = [chunk async for chunk in agent.analyze_stream(videos)]

    assert len(chunks) == 2
    assert "Primary model failed (Primary Model API Error)" in chunks[0]
    assert "Falling back to" in chunks[0]
    assert chunks[1] == "Fallback Chunk 1"


@pytest.mark.asyncio
async def test_analyze_stream_primary_fail_fallback_fail(
    agent: GeminiThinkingAgent, videos: List[VideoAnalysisInput]
) -> None:
    """Test analyze_stream when both primary and fallback models fail."""
    agent.client.aio.models.generate_content_stream = cast(Any, Mock(
        side_effect=[
            Exception("Primary Model API Error"),
            Exception("Fallback Model API Error")
        ]
    )) # type: ignore[method-assign]

    chunks = [chunk async for chunk in agent.analyze_stream(videos)]

    assert len(chunks) == 2
    assert "Primary model failed (Primary Model API Error)" in chunks[0]
    assert "Fallback model also failed: Fallback Model API Error" in chunks[1]
