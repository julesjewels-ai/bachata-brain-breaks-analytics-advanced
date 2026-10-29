import pytest
from unittest.mock import patch, MagicMock
from typing import List, AsyncGenerator
from src.core.models import VideoAnalysisInput
from src.core.ai import GeminiThinkingAgent

class MockChunk:
    def __init__(self, text: str):
        self.text = text

@pytest.fixture
def mock_videos() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="vid_1",
            title="Test Video",
            views=100,
            retention_avg_pct=50.0,
            type="Long"
        )
    ]

# Define coroutines for side effects that return async generators
async def _success_primary(*args, **kwargs) -> AsyncGenerator[MockChunk, None]:
    async def _gen():
        yield MockChunk("primary1 ")
        yield MockChunk("primary2")
    return _gen()

async def _success_fallback(*args, **kwargs) -> AsyncGenerator[MockChunk, None]:
    async def _gen():
        yield MockChunk("fallback1 ")
        yield MockChunk("fallback2")
    return _gen()

async def _fail_primary(*args, **kwargs) -> AsyncGenerator[MockChunk, None]:
    raise Exception("primary error")

async def _fail_fallback(*args, **kwargs) -> AsyncGenerator[MockChunk, None]:
    raise Exception("fallback error")

@pytest.mark.asyncio
@pytest.mark.parametrize("scenario, expected_texts", [
    (
        "empty",
        ["No data to analyze."]
    ),
    (
        "primary_success",
        ["primary1 ", "primary2"]
    ),
    (
        "primary_fail_fallback_success",
        [
            "\n[warning] Primary model failed (primary error). Falling back to gemini-2.5-flash...[/warning]\n\n",
            "fallback1 ",
            "fallback2"
        ]
    ),
    (
        "primary_fail_fallback_fail",
        [
            "\n[warning] Primary model failed (primary error). Falling back to gemini-2.5-flash...[/warning]\n\n",
            "\n[error] Fallback model also failed: fallback error. Please try again later.[/error]\n"
        ]
    )
])
async def test_analyze_stream(
    mock_videos: List[VideoAnalysisInput],
    scenario: str,
    expected_texts: List[str]
) -> None:
    # Set up mock configuration via patch to avoid actual environment dependencies
    with patch('src.core.ai.AppConfig.get_config') as mock_config, \
         patch('src.core.ai.genai.Client') as mock_client_class:

        # Configure mock AppConfig
        mock_config_instance = MagicMock()
        mock_config_instance.get_api_key.return_value = "TEST_API_KEY"
        mock_config.return_value = mock_config_instance

        # Setup mock Client and stream method
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_generate_stream = MagicMock()

        # Set side_effect based on scenario
        if scenario == "primary_success":
            mock_generate_stream.side_effect = _success_primary
        elif scenario == "primary_fail_fallback_success":
            mock_generate_stream.side_effect = [_fail_primary(), _success_fallback()]
        elif scenario == "primary_fail_fallback_fail":
            mock_generate_stream.side_effect = [_fail_primary(), _fail_fallback()]

        mock_client.aio.models.generate_content_stream = mock_generate_stream

        # Initialize agent
        agent = GeminiThinkingAgent()

        # Test input
        videos = [] if scenario == "empty" else mock_videos

        # Act
        stream = agent.analyze_stream(videos)

        # Assert
        actual_texts = []
        async for chunk in stream:
            actual_texts.append(chunk)

        assert actual_texts == expected_texts, f"Failed for scenario: {scenario}"
