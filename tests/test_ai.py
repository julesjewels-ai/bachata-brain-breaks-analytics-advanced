import pytest
from unittest.mock import Mock, patch
from typing import Generator
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from src.core.config import AppConfig

class MockChunk:
    def __init__(self, text):
        self.text = text

class AsyncGenMock:
    def __init__(self, chunks=None, error=None):
        self.chunks = chunks or []
        self.error = error

    def __await__(self):
        async def _awaitable():
            return self
        return _awaitable().__await__()

    async def __aiter__(self):
        if self.error:
            raise self.error
        for chunk in self.chunks:
            yield chunk

@pytest.fixture
def clean_videos() -> list[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="123",
            title="Test Video",
            views=1000,
            retention_avg_pct=50.0,
            type="Long"
        )
    ]

@pytest.fixture
def mock_genai_client() -> Generator[Mock, None, None]:
    with patch("src.core.ai.genai.Client", autospec=True) as mock_client_cls:
        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        mock_client.aio = Mock()
        mock_client.aio.models = Mock()
        yield mock_client

@pytest.fixture
def mock_app_config() -> Generator[Mock, None, None]:
    with patch("src.core.ai.AppConfig.get_config", autospec=True) as mock_get_config:
        mock_config = Mock(spec=AppConfig)
        mock_config.get_api_key.return_value = "fake_key"
        mock_get_config.return_value = mock_config
        yield mock_get_config

@pytest.mark.asyncio
@pytest.mark.parametrize("scenario, expected_outputs", [
    ("empty_videos", ["No data to analyze."]),
    ("success", ["Primary ", "Success"]),
    ("fallback_success", [
        "\n[warning] Primary model failed (Primary Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "Fallback ", "Success"
    ]),
    ("fallback_failure", [
        "\n[warning] Primary model failed (Primary Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "\n[error] Fallback model also failed: Fallback Error. Please try again later.[/error]\n"
    ]),
])
async def test_analyze_stream_boundaries(
    mock_app_config: Mock,
    mock_genai_client: Mock,
    clean_videos: list[VideoAnalysisInput],
    scenario: str,
    expected_outputs: list[str]
) -> None:
    # Arrange
    agent = GeminiThinkingAgent()

    videos = [] if scenario == "empty_videos" else clean_videos

    if scenario == "success":
        mock_genai_client.aio.models.generate_content_stream.return_value = AsyncGenMock(
            chunks=[MockChunk("Primary "), MockChunk("Success")]
        )
    elif scenario == "fallback_success":
        def side_effect(*args, **kwargs):
            if kwargs.get("model") == GeminiThinkingAgent.PRIMARY_MODEL:
                return AsyncGenMock(error=Exception("Primary Error"))
            return AsyncGenMock(chunks=[MockChunk("Fallback "), MockChunk("Success")])
        mock_genai_client.aio.models.generate_content_stream.side_effect = side_effect
    elif scenario == "fallback_failure":
        def side_effect(*args, **kwargs):
            if kwargs.get("model") == GeminiThinkingAgent.PRIMARY_MODEL:
                return AsyncGenMock(error=Exception("Primary Error"))
            return AsyncGenMock(error=Exception("Fallback Error"))
        mock_genai_client.aio.models.generate_content_stream.side_effect = side_effect

    # Act
    results = []
    async for chunk in agent.analyze_stream(videos):
        results.append(chunk)

    # Assert
    assert results == expected_outputs, f"Failed on scenario: {scenario}"
