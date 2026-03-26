import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, AsyncGenerator, Any, Generator

from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput


@pytest.fixture
def clean_videos() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="test_vid",
            title="Test Title",
            views=1000,
            retention_avg_pct=55.0,
            type="Shorts"
        )
    ]


@pytest.fixture
def mock_genai_client() -> Generator[Mock, None, None]:
    with patch("src.core.ai.genai.Client") as mock_client_cls:
        with patch("src.core.config.AppConfig.get_config") as mock_config_cls:
            mock_config = Mock()
            mock_config.get_api_key.return_value = "dummy_key"
            mock_config_cls.return_value = mock_config

            mock_client = Mock()
            mock_client_cls.return_value = mock_client
            yield mock_client


class AsyncGenMock:
    def __init__(self, items=None, exception=None):
        self.items = items or []
        self.exception = exception

    def __await__(self):
        # We need to return an instance that can act as an async generator when iterated over
        async def dummy_coro():
            return self
        return dummy_coro().__await__()

    async def __aiter__(self):
        for item in self.items:
            mock_chunk = Mock()
            mock_chunk.text = item
            yield mock_chunk
        if self.exception:
            raise self.exception


def stream_success(chunks: List[str]) -> AsyncGenMock:
    return AsyncGenMock(items=chunks)


def stream_failure(exception: Exception) -> AsyncGenMock:
    return AsyncGenMock(exception=exception)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario, primary_side_effect, fallback_side_effect, expected_output",
    [
        (
            "empty_input",
            None,
            None,
            ["No data to analyze."]
        ),
        (
            "primary_success",
            lambda *args, **kwargs: stream_success(["Primary", " Success"]),
            None,
            ["Primary", " Success"]
        ),
        (
            "primary_failure_fallback_success",
            lambda *args, **kwargs: stream_failure(ValueError("Primary Down")),
            lambda *args, **kwargs: stream_success(["Fallback", " Success"]),
            [
                "\n[warning] Primary model failed (Primary Down). "
                "Falling back to gemini-2.5-flash...[/warning]\n\n",
                "Fallback",
                " Success"
            ]
        ),
        (
            "primary_failure_fallback_failure",
            lambda *args, **kwargs: stream_failure(ValueError("Primary Down")),
            lambda *args, **kwargs: stream_failure(ValueError("Fallback Down")),
            [
                "\n[warning] Primary model failed (Primary Down). "
                "Falling back to gemini-2.5-flash...[/warning]\n\n",
                "\n[error] Fallback model also failed: Fallback Down. "
                "Please try again later.[/error]\n"
            ]
        )
    ],
    ids=[
        "empty_input",
        "primary_success",
        "primary_failure_fallback_success",
        "primary_failure_fallback_failure"
    ]
)
async def test_analyze_stream_edge_cases(
    clean_videos: List[VideoAnalysisInput],
    mock_genai_client: Mock,
    scenario: str,
    primary_side_effect: Any,
    fallback_side_effect: Any,
    expected_output: List[str]
) -> None:
    # Arrange
    if scenario == "empty_input":
        videos = []
    else:
        videos = clean_videos

    agent = GeminiThinkingAgent()

    # In Python tests for async generators where we need different side_effects
    # for different calls (first primary, then fallback), we can track the
    # calls to generate_content_stream and return the appropriate side_effect.

    # We will override the generate_content_stream side effect to handle both calls
    call_count = 0
    def side_effect_handler(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            if primary_side_effect:
                return primary_side_effect()
        else:
            if fallback_side_effect:
                return fallback_side_effect()

        # Default async generator if none provided
        async def default_gen():
            yield
        return default_gen()

    if primary_side_effect or fallback_side_effect:
        mock_genai_client.aio.models.generate_content_stream.side_effect = side_effect_handler

    # Act
    result_chunks = []
    async for chunk in agent.analyze_stream(videos):
        result_chunks.append(chunk)

    # Assert
    assert result_chunks == expected_output, f"Failed on scenario: {scenario}"

    if scenario != "empty_input":
        # Validate that client was called
        assert mock_genai_client.aio.models.generate_content_stream.called, f"Client not called in {scenario}"
