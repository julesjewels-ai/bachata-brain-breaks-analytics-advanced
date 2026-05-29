import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Generator, Any

from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from src.core.config import AppConfig


class AsyncGenMock:
    """Custom mock for async generators required by google-genai streaming."""
    def __init__(self, chunks: Any):
        self.chunks = chunks

    def __await__(self) -> Any:
        async def _awaitable() -> 'AsyncGenMock':
            return self
        return _awaitable().__await__()

    async def __aiter__(self) -> Any:
        if isinstance(self.chunks, Exception):
            raise self.chunks
        for chunk in self.chunks:
            obj = MagicMock()
            obj.text = chunk
            yield obj


@pytest.fixture
def mock_config() -> Generator[Mock, None, None]:
    with patch("src.core.ai.AppConfig.get_config") as mock_get_config:
        config = MagicMock(spec=AppConfig)
        config.get_api_key.return_value = "TEST_API_KEY"
        mock_get_config.return_value = config
        yield mock_get_config


@pytest.fixture
def agent(mock_config: Mock) -> Generator[GeminiThinkingAgent, None, None]:
    with patch("src.core.ai.genai.Client"):
        yield GeminiThinkingAgent()


@pytest.fixture
def valid_videos() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="VID1",
            title="Valid Title",
            views=1000,
            retention_avg_pct=50.0,
            type="Long"
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "is_empty, primary_response, fallback_response, expected_yields",
    [
        # Case 1: Empty videos list
        (True, [], [], ["No data to analyze."]),

        # Case 2: Primary model success
        (False, ["chunk1", "chunk2"], [], ["chunk1", "chunk2"]),

        # Case 3: Primary fails, fallback succeeds
        (False, Exception("API Error"), ["fallback1"], [
            "\n[warning] Primary model failed (API Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
            "fallback1"
        ]),

        # Case 4: Primary fails, fallback fails
        (False, Exception("API Error"), Exception("Fallback Error"), [
            "\n[warning] Primary model failed (API Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
            "\n[error] Fallback model also failed: Fallback Error. Please try again later.[/error]\n"
        ])
    ]
)
async def test_analyze_stream(
    agent: GeminiThinkingAgent,
    valid_videos: List[VideoAnalysisInput],
    is_empty: bool,
    primary_response: Any,
    fallback_response: Any,
    expected_yields: List[str]
) -> None:
    # Arrange
    videos = [] if is_empty else valid_videos

    async_gen_primary = AsyncGenMock(primary_response)
    async_gen_fallback = AsyncGenMock(fallback_response)

    def mock_stream(model: str, *args: Any, **kwargs: Any) -> Any:
        if model == agent.PRIMARY_MODEL:
            return async_gen_primary
        return async_gen_fallback

    agent.client.aio.models.generate_content_stream = MagicMock(side_effect=mock_stream)

    # Act
    results = []
    async for chunk in agent.analyze_stream(videos):
        results.append(chunk)

    # Assert
    assert results == expected_yields, f"Failed on inputs - Empty: {is_empty}, Primary: {primary_response}, Fallback: {fallback_response}"
