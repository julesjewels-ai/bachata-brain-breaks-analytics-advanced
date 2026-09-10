import pytest
from unittest.mock import patch, MagicMock, AsyncMock, Mock
from typing import List, Any
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from src.core.config import AppConfig
from google import genai
from google.genai import types


class MockChunk:
    def __init__(self, text: str):
        self.text = text


class AsyncGenMock:
    def __init__(self, chunks: List[MockChunk] | None = None, error: Exception | None = None):
        self.chunks = chunks or []
        self.error = error

    def __await__(self):
        async def _resolve():
            return self
        return _resolve().__await__()

    async def __aiter__(self):
        if self.error:
            raise self.error
        for chunk in self.chunks:
            yield chunk


@pytest.fixture
def mock_config() -> MagicMock:
    config = MagicMock(spec=AppConfig)
    config.get_api_key.return_value = "TEST_API_KEY"
    return config


@pytest.fixture
def agent(mock_config: MagicMock) -> GeminiThinkingAgent:
    with patch('src.core.config.AppConfig.get_config', return_value=mock_config):
        return GeminiThinkingAgent()


@pytest.fixture
def sample_videos() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="123",
            title="Test Video",
            views=1000,
            retention_avg_pct=50.0,
            type="Long"
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario, primary_response, fallback_response, expected_chunks", [
    (
        "empty_videos",
        None,
        None,
        ["No data to analyze."]
    ),
    (
        "primary_success",
        AsyncGenMock(chunks=[MockChunk("Hello"), MockChunk(" World")]),
        None,
        ["Hello", " World"]
    ),
    (
        "primary_fails_fallback_success",
        AsyncGenMock(error=Exception("API Error")),
        AsyncGenMock(chunks=[MockChunk("Fallback"), MockChunk(" Strategy")]),
        [
            "\n[warning] Primary model failed (API Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
            "Fallback",
            " Strategy"
        ]
    ),
    (
        "both_fail",
        AsyncGenMock(error=Exception("Primary Error")),
        AsyncGenMock(error=Exception("Fallback Error")),
        [
            "\n[warning] Primary model failed (Primary Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
            "\n[error] Fallback model also failed: Fallback Error. Please try again later.[/error]\n"
        ]
    )
])
async def test_analyze_stream(
    agent: GeminiThinkingAgent,
    sample_videos: List[VideoAnalysisInput],
    scenario: str,
    primary_response: AsyncGenMock | None,
    fallback_response: AsyncGenMock | None,
    expected_chunks: List[str]
) -> None:
    # Setup videos based on scenario
    videos = [] if scenario == "empty_videos" else sample_videos

    # Mock the client's generate_content_stream method
    mock_generate = Mock()
    agent.client.aio.models.generate_content_stream = mock_generate # type: ignore[method-assign]

    # We need to configure the mock to return different things based on the model argument
    def side_effect(*args: Any, **kwargs: Any) -> Any:
        model = kwargs.get('model')
        if model == agent.PRIMARY_MODEL:
            return primary_response
        elif model == agent.FALLBACK_MODEL:
            return fallback_response
        return None

    mock_generate.side_effect = side_effect

    # Execute
    stream = agent.analyze_stream(videos)
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)

    # Assert
    assert chunks == expected_chunks, f"Failed on scenario: {scenario}"

    if scenario == "primary_success":
        mock_generate.assert_called_once()
        assert mock_generate.call_args.kwargs['model'] == agent.PRIMARY_MODEL
    elif scenario in ("primary_fails_fallback_success", "both_fail"):
        assert mock_generate.call_count == 2
        calls = mock_generate.call_args_list
        assert calls[0].kwargs['model'] == agent.PRIMARY_MODEL
        assert calls[1].kwargs['model'] == agent.FALLBACK_MODEL
