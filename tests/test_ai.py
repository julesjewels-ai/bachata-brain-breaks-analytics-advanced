import pytest
from unittest.mock import MagicMock
from typing import AsyncGenerator, List, Any
import google.genai
from google.genai import types

from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from src.core.config import AppConfig

# Mock AppConfig so we don't need real API keys
@pytest.fixture(autouse=True)
def mock_app_config(mocker):
    mock_config = MagicMock()
    mock_config.get_api_key.return_value = "test-api-key"
    mocker.patch.object(AppConfig, 'get_config', return_value=mock_config)

# Custom Mock for Async Generators as standard AsyncMock is insufficient
class AsyncGenMock:
    def __init__(self, chunks: List[str] = None, error: Exception = None):
        self.chunks = chunks or []
        self.error = error

    def __await__(self):
        async def resolve():
            return self
        return resolve().__await__()

    async def __aiter__(self):
        if self.error:
            raise self.error
        for chunk in self.chunks:
            # We need to simulate the structure expected: chunk.text
            mock_chunk = MagicMock()
            mock_chunk.text = chunk
            yield mock_chunk

@pytest.fixture
def agent() -> GeminiThinkingAgent:
    return GeminiThinkingAgent()

@pytest.fixture
def sample_videos() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="vid1",
            title="Test Video",
            views=1000,
            retention_avg_pct=50.0,
            type="Long"
        )
    ]

@pytest.mark.asyncio
@pytest.mark.parametrize("scenario, primary_mock, fallback_mock, expected_outputs", [
    (
        "empty_videos",
        None,
        None,
        ["No data to analyze."]
    ),
    (
        "primary_success",
        AsyncGenMock(chunks=["chunk1", "chunk2"]),
        None,
        ["chunk1", "chunk2"]
    ),
    (
        "primary_fail_fallback_success",
        AsyncGenMock(error=Exception("API Error")),
        AsyncGenMock(chunks=["fallback1"]),
        [
            "\n[warning] Primary model failed (API Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
            "fallback1"
        ]
    ),
    (
        "both_fail",
        AsyncGenMock(error=Exception("API Error")),
        AsyncGenMock(error=Exception("Fallback API Error")),
        [
            "\n[warning] Primary model failed (API Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
            "\n[error] Fallback model also failed: Fallback API Error. Please try again later.[/error]\n"
        ]
    )
])
async def test_analyze_stream(
    mocker,
    agent: GeminiThinkingAgent,
    sample_videos: List[VideoAnalysisInput],
    scenario: str,
    primary_mock: Any,
    fallback_mock: Any,
    expected_outputs: List[str]
) -> None:
    # Arrange
    videos_to_test = [] if scenario == "empty_videos" else sample_videos

    if scenario != "empty_videos":
        mocker.patch.object(agent.client.aio.models, 'generate_content_stream')

        # We need to mock generate_content_stream to return primary_mock on first call and fallback_mock on second call
        def side_effect(*args, **kwargs):
            if kwargs.get('model') == agent.PRIMARY_MODEL:
                return primary_mock
            elif kwargs.get('model') == agent.FALLBACK_MODEL:
                return fallback_mock
            return AsyncGenMock(chunks=[])

        agent.client.aio.models.generate_content_stream.side_effect = side_effect

    # Act
    outputs = []
    async for chunk in agent.analyze_stream(videos_to_test):
        outputs.append(chunk)

    # Assert
    assert outputs == expected_outputs, f"Failed on scenario: {scenario}"
