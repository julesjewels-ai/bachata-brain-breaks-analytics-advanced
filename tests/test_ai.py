import pytest
from unittest.mock import Mock, patch
from typing import List, Generator, Callable, Any
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from google.genai import types

class AsyncGenMock:
    def __init__(self, items: List[Any] | None = None, exception: Exception | None = None) -> None:
        self.items = items or []
        self.exception = exception
        self.index = 0

    def __await__(self) -> Generator[Any, None, Any]:
        async def _awaitable() -> "AsyncGenMock":
            return self
        return _awaitable().__await__()

    def __aiter__(self) -> "AsyncGenMock":
        return self

    async def __anext__(self) -> Any:
        if self.exception and self.index == 0:
            raise self.exception
        if self.index < len(self.items):
            item = self.items[self.index]
            self.index += 1
            return item
        raise StopAsyncIteration

class MockChunk:
    def __init__(self, text: str) -> None:
        self.text = text

@pytest.fixture
def mock_genai_client() -> Generator[Mock, None, None]:
    with patch("src.core.ai.genai.Client") as mock_client_cls:
        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        mock_client.models = Mock()
        mock_client.aio = Mock()
        mock_client.aio.models = Mock()
        yield mock_client

@pytest.fixture
def sample_videos() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="id1",
            title="Bachata Basic",
            views=1000,
            retention_avg_pct=50.0,
            type="Shorts"
        ),
        VideoAnalysisInput(
            video_id="id2",
            title="Bachata Turn",
            views=2000,
            retention_avg_pct=60.0,
            type="Long"
        )
    ]

@pytest.fixture
def agent(mock_genai_client: Mock) -> Generator[GeminiThinkingAgent, None, None]:
    with patch("src.core.ai.AppConfig.get_config") as mock_get_config:
        mock_config = Mock()
        mock_config.get_api_key.return_value = "fake-key"
        mock_get_config.return_value = mock_config
        yield GeminiThinkingAgent()


def primary_success_side_effect(model: str, contents: str, config: types.GenerateContentConfig) -> AsyncGenMock:
    return AsyncGenMock(items=[MockChunk("chunk1"), MockChunk("chunk2")])

def primary_fails_fallback_success_side_effect(model: str, contents: str, config: types.GenerateContentConfig) -> AsyncGenMock:
    if model == GeminiThinkingAgent.PRIMARY_MODEL:
        return AsyncGenMock(exception=Exception("Primary Down"))
    return AsyncGenMock(items=[MockChunk("fallback_chunk1")])

def primary_fails_fallback_fails_side_effect(model: str, contents: str, config: types.GenerateContentConfig) -> AsyncGenMock:
    if model == GeminiThinkingAgent.PRIMARY_MODEL:
        return AsyncGenMock(exception=Exception("Primary Down"))
    return AsyncGenMock(exception=Exception("Fallback Down"))


@pytest.mark.asyncio
@pytest.mark.parametrize("use_videos, side_effect, expected_chunks, expected_call_count", [
    (False, None, ["No data to analyze."], 0),
    (True, primary_success_side_effect, ["chunk1", "chunk2"], 1),
    (True, primary_fails_fallback_success_side_effect, ["\n[warning] Primary model failed (Primary Down). Falling back to gemini-2.5-flash...[/warning]\n\n", "fallback_chunk1"], 2),
    (True, primary_fails_fallback_fails_side_effect, ["\n[warning] Primary model failed (Primary Down). Falling back to gemini-2.5-flash...[/warning]\n\n", "\n[error] Fallback model also failed: Fallback Down. Please try again later.[/error]\n"], 2)
])
async def test_analyze_stream_boundaries(
    agent: GeminiThinkingAgent,
    mock_genai_client: Mock,
    sample_videos: List[VideoAnalysisInput],
    use_videos: bool,
    side_effect: Callable[..., AsyncGenMock] | None,
    expected_chunks: List[str],
    expected_call_count: int
) -> None:
    videos = sample_videos if use_videos else []

    if side_effect:
        mock_genai_client.aio.models.generate_content_stream.side_effect = side_effect

    chunks: List[str] = []
    async for chunk in agent.analyze_stream(videos):
        chunks.append(chunk)

    assert chunks == expected_chunks, f"Expected chunks {expected_chunks}, got {chunks}"
    assert mock_genai_client.aio.models.generate_content_stream.call_count == expected_call_count, f"Expected {expected_call_count} calls to generate_content_stream"

@pytest.mark.parametrize("use_videos, mock_response_text, expected_result", [
    (False, None, "No data to analyze."),
    (True, "semantic response", "semantic response"),
    (True, "", "No text response generated."),
])
def test_analyze_semantics_boundaries(
    agent: GeminiThinkingAgent,
    mock_genai_client: Mock,
    sample_videos: List[VideoAnalysisInput],
    use_videos: bool,
    mock_response_text: str | None,
    expected_result: str
) -> None:
    videos = sample_videos if use_videos else []

    if mock_response_text is not None:
        mock_response = Mock()
        mock_response.text = mock_response_text
        mock_genai_client.models.generate_content.return_value = mock_response

    result = agent.analyze_semantics(videos)
    assert result == expected_result, f"Expected result {expected_result}, got {result}"
