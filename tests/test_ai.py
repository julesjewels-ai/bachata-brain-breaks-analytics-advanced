import pytest
from unittest.mock import Mock, patch, call
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from src.core.config import AppConfig
from typing import Any, List, cast
import builtins

class AsyncGenMock:
    def __init__(self, chunks: List[str], error: Exception | None = None):
        self.chunks = chunks
        self.error = error

    def __await__(self) -> Any:
        async def _awaitable() -> Any:
            return self
        return _awaitable().__await__()

    async def __aiter__(self) -> Any:
        if self.error:
            raise self.error
        for chunk in self.chunks:
            mock_chunk = Mock()
            mock_chunk.text = chunk
            yield mock_chunk

@pytest.fixture
def mock_config() -> Any:
    with patch("src.core.ai.AppConfig") as mock_app_config:
        mock_config_instance = Mock()
        mock_config_instance.get_api_key.return_value = "fake-key"
        mock_app_config.get_config.return_value = mock_config_instance
        yield mock_app_config

@pytest.fixture
def mock_genai() -> Any:
    with patch("src.core.ai.genai") as mock_genai_module:
        mock_client = Mock()
        mock_genai_module.Client.return_value = mock_client
        yield mock_client

@pytest.fixture
def agent(mock_config: Any, mock_genai: Any) -> GeminiThinkingAgent:
    return GeminiThinkingAgent()

@pytest.mark.parametrize("videos, mock_response_text, expected_result", [
    ([], None, "No data to analyze."),
    ([VideoAnalysisInput(video_id="1", title="Title", views=100, retention_avg_pct=50, type="Long")], "Analysis result", "Analysis result"),
    ([VideoAnalysisInput(video_id="1", title="Title", views=100, retention_avg_pct=50, type="Long")], None, "No text response generated.")
])
def test_analyze_semantics(
    agent: GeminiThinkingAgent,
    mock_genai: Any,
    videos: List[VideoAnalysisInput],
    mock_response_text: str | None,
    expected_result: str
) -> None:
    # Arrange
    mock_response = Mock()
    mock_response.text = mock_response_text
    mock_genai.models.generate_content.return_value = mock_response

    # Act
    result = agent.analyze_semantics(videos)

    # Assert
    assert result == expected_result
    if videos:
        mock_genai.models.generate_content.assert_called_once()
        args, kwargs = mock_genai.models.generate_content.call_args
        assert kwargs["model"] == agent.PRIMARY_MODEL

@pytest.mark.asyncio
@pytest.mark.parametrize("videos, primary_chunks, primary_error, fallback_chunks, fallback_error, expected_chunks", [
    ([], [], None, [], None, ["No data to analyze."]),
    ([VideoAnalysisInput(video_id="1", title="Title", views=100, retention_avg_pct=50, type="Long")], ["Chunk 1 ", "Chunk 2"], None, [], None, ["Chunk 1 ", "Chunk 2"]),
    ([VideoAnalysisInput(video_id="1", title="Title", views=100, retention_avg_pct=50, type="Long")], [], builtins.Exception("Primary failed"), ["Fallback 1 ", "Fallback 2"], None, [
        "\n[warning] Primary model failed (Primary failed). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "Fallback 1 ",
        "Fallback 2"
    ]),
    ([VideoAnalysisInput(video_id="1", title="Title", views=100, retention_avg_pct=50, type="Long")], [], builtins.Exception("Primary failed"), [], builtins.Exception("Fallback failed"), [
        "\n[warning] Primary model failed (Primary failed). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "\n[error] Fallback model also failed: Fallback failed. Please try again later.[/error]\n"
    ])
])
async def test_analyze_stream(
    agent: GeminiThinkingAgent,
    mock_genai: Any,
    videos: List[VideoAnalysisInput],
    primary_chunks: List[str],
    primary_error: Exception | None,
    fallback_chunks: List[str],
    fallback_error: Exception | None,
    expected_chunks: List[str]
) -> None:
    # Arrange

    # We need to distinguish between calls to primary and fallback.
    # generate_content_stream is called with `model=self.PRIMARY_MODEL` and `model=self.FALLBACK_MODEL`.

    def mock_generate_content_stream(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("model") == agent.PRIMARY_MODEL:
            return AsyncGenMock(primary_chunks, primary_error)
        elif kwargs.get("model") == agent.FALLBACK_MODEL:
            return AsyncGenMock(fallback_chunks, fallback_error)
        return AsyncGenMock([])

    mock_genai.aio.models.generate_content_stream = Mock(side_effect=mock_generate_content_stream)

    # Act
    stream = agent.analyze_stream(videos)
    actual_chunks = []
    async for chunk in stream:
        actual_chunks.append(chunk)

    # Assert
    assert actual_chunks == expected_chunks
