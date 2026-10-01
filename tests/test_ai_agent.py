import pytest
from typing import AsyncGenerator, List, Any
from unittest.mock import MagicMock
from pytest_mock import MockerFixture
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from google.genai.types import GenerateContentConfig, GenerateContentResponse

# We need to mock the chunks returned by generate_content_stream
class MockChunk:
    def __init__(self, text: str) -> None:
        self.text = text

async def mock_stream(*chunks: str) -> AsyncGenerator[MockChunk, None]:
    for chunk in chunks:
        yield MockChunk(chunk)

@pytest.fixture
def sample_videos() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="vid_1",
            title="A title",
            views=1000,
            retention_avg_pct=50.5,
            type="Shorts"
        )
    ]

# Parameterize our test to cover the edge cases
@pytest.mark.asyncio
@pytest.mark.parametrize("scenario, expected_outputs", [
    ("empty_data", ["No data to analyze."]),
    ("primary_success", ["chunk 1 ", "chunk 2"]),
    ("primary_fail_fallback_success", [
        "\n[warning] Primary model failed (Primary Failure). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "fallback chunk 1 ", "fallback chunk 2"
    ]),
    ("both_fail", [
        "\n[warning] Primary model failed (Primary Failure). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "\n[error] Fallback model also failed: Fallback Failure. Please try again later.[/error]\n"
    ])
])
async def test_analyze_stream(
    mocker: MockerFixture,
    sample_videos: List[VideoAnalysisInput],
    scenario: str,
    expected_outputs: List[str]
) -> None:
    # Mock AppConfig to return dummy api key
    mock_config = mocker.patch("src.core.ai.AppConfig")
    mock_config.get_config.return_value.get_api_key.return_value = "dummy"

    agent = GeminiThinkingAgent()

    # Create an async mock for the generate_content_stream method
    mock_generate_content_stream = mocker.AsyncMock()

    if scenario == "empty_data":
        pass # Doesn't matter, won't be called
    elif scenario == "primary_success":
        # Should return a mocked async generator for primary model
        mock_generate_content_stream.return_value = mock_stream("chunk 1 ", "chunk 2")
    elif scenario == "primary_fail_fallback_success":
        # Fails on the first call, succeeds on the second (fallback)
        mock_generate_content_stream.side_effect = [
            Exception("Primary Failure"),
            mock_stream("fallback chunk 1 ", "fallback chunk 2")
        ]
    elif scenario == "both_fail":
        # Fails on both calls
        mock_generate_content_stream.side_effect = [
            Exception("Primary Failure"),
            Exception("Fallback Failure")
        ]

    # Patch the generate_content_stream method
    # According to memory directive:
    # mocker.patch.object(client.aio.models, 'generate_content_stream')
    mocker.patch.object(agent.client.aio.models, "generate_content_stream", mock_generate_content_stream)

    # Act
    videos = [] if scenario == "empty_data" else sample_videos
    generator = agent.analyze_stream(videos)

    actual_outputs = []
    async for output in generator:
        actual_outputs.append(output)

    # Assert
    assert actual_outputs == expected_outputs, f"Failed on scenario '{scenario}'. Expected {expected_outputs}, but got {actual_outputs}"
