import pytest
from typing import AsyncGenerator, List, Any, cast
from unittest.mock import Mock, patch

from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from google.genai.types import GenerateContentResponse

class AsyncGenMock:
    """Custom mock to simulate an async generator for google-genai streaming."""
    def __init__(self, chunks: List[str] | Exception):
        self.chunks = chunks
        self.index = 0

    def __await__(self) -> Any:
        # Return a coroutine that resolves to self
        async def _awaitable() -> 'AsyncGenMock':
            return self
        return _awaitable().__await__()

    async def __aiter__(self) -> AsyncGenerator[Any, None]:
        if isinstance(self.chunks, Exception):
            raise self.chunks
        for chunk in self.chunks:
            # Mock chunk with a .text attribute
            mock_chunk = Mock()
            mock_chunk.text = chunk
            yield mock_chunk

@pytest.fixture
def mock_genai_client() -> Any:
    with patch('src.core.ai.genai.Client') as mock_client_cls:
        mock_client = mock_client_cls.return_value
        # Mocking the client.aio.models.generate_content_stream
        mock_client.aio.models.generate_content_stream = Mock()
        yield mock_client

@pytest.fixture
def sample_videos() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="test1",
            title="Test Video 1",
            views=1000,
            retention_avg_pct=50.0,
            type="Long"
        )
    ]

@pytest.mark.asyncio
@pytest.mark.parametrize("scenario, primary_result, fallback_result, expected_chunks", [
    ("empty_videos", None, None, ["No data to analyze."]),
    ("primary_success", ["Primary ", "Chunk"], None, ["Primary ", "Chunk"]),
    ("primary_fail_fallback_success", Exception("Primary Error"), ["Fallback ", "Chunk"], ["\n[warning] Primary model failed (Primary Error). Falling back to gemini-2.5-flash...[/warning]\n\n", "Fallback ", "Chunk"]),
    ("both_fail", Exception("Primary Error"), Exception("Fallback Error"), ["\n[warning] Primary model failed (Primary Error). Falling back to gemini-2.5-flash...[/warning]\n\n", "\n[error] Fallback model also failed: Fallback Error. Please try again later.[/error]\n"])
])
async def test_analyze_stream_branches(
    mock_genai_client: Any,
    sample_videos: List[VideoAnalysisInput],
    scenario: str,
    primary_result: Any,
    fallback_result: Any,
    expected_chunks: List[str]
) -> None:
    # Arrange
    with patch('src.core.ai.AppConfig') as mock_config:
        mock_config.get_config.return_value.get_api_key.return_value = "fake_key"
        agent = GeminiThinkingAgent()

    if scenario == "empty_videos":
        videos = []
    else:
        videos = sample_videos

        def side_effect(*args: Any, **kwargs: Any) -> Any:
            model = kwargs.get('model')
            if model == agent.PRIMARY_MODEL:
                return AsyncGenMock(primary_result)
            elif model == agent.FALLBACK_MODEL:
                return AsyncGenMock(fallback_result)
            return AsyncGenMock([])

        # type: ignore[method-assign]
        agent.client.aio.models.generate_content_stream.side_effect = side_effect

    # Act
    actual_chunks = []
    async for chunk in agent.analyze_stream(videos):
        actual_chunks.append(chunk)

    # Assert
    assert actual_chunks == expected_chunks, f"Failed on scenario: {scenario}"
