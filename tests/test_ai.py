import pytest
from unittest.mock import AsyncMock, patch
from typing import List, Any
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from src.core.config import AppConfig


@pytest.fixture
def agent() -> Any:
    """Provides a fresh GeminiThinkingAgent instance for each test."""
    with patch.object(AppConfig, 'get_config') as mock_config:
        mock_config.return_value.get_api_key.return_value = "TEST_API_KEY"
        # Mock genai.Client to avoid real instantiation connecting to API
        with patch("src.core.ai.genai.Client"):
            yield GeminiThinkingAgent()


@pytest.fixture
def mock_videos() -> List[VideoAnalysisInput]:
    """Provides standard mock video data."""
    return [
        VideoAnalysisInput(
            video_id="vid1",
            title="Bachata Basics",
            views=1000,
            retention_avg_pct=45.5,
            type="Long"
        ),
        VideoAnalysisInput(
            video_id="vid2",
            title="Viral Shorts",
            views=50000,
            retention_avg_pct=95.0,
            type="Shorts"
        )
    ]


async def async_gen(items: List[str]):
    """Helper to create an async generator from a list of strings."""
    for item in items:
        yield item


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario, expected_chunks", [
    (
        "empty",
        ["No data to analyze."]
    ),
    (
        "primary_success",
        ["Chunk 1", "Chunk 2"]
    ),
    (
        "primary_fail_fallback_success",
        [
            "\n[warning] Primary model failed (Primary Error). "
            "Falling back to gemini-2.5-flash...[/warning]\n\n",
            "Fallback Chunk"
        ]
    ),
    (
        "primary_fail_fallback_fail",
        [
            "\n[warning] Primary model failed (Primary Error). "
            "Falling back to gemini-2.5-flash...[/warning]\n\n",
            "\n[error] Fallback model also failed: Fallback Error. "
            "Please try again later.[/error]\n"
        ]
    )
])
async def test_analyze_stream_edge_cases(
    agent: GeminiThinkingAgent,
    mock_videos: List[VideoAnalysisInput],
    scenario: str,
    expected_chunks: List[str]
) -> None:
    """
    Tests edge cases and fallback logic for analyze_stream.
    Avoids making actual API calls by mocking internal generator methods.
    """
    videos_to_test = mock_videos if scenario != "empty" else []

    # Setup the mock behaviors
    with patch.object(agent, '_stream_primary_model') as mock_primary, \
         patch.object(agent, '_stream_fallback_model') as mock_fallback:

        if scenario == "primary_success":
            mock_primary.return_value = async_gen(["Chunk 1", "Chunk 2"])
        elif scenario == "primary_fail_fallback_success":
            mock_primary.side_effect = Exception("Primary Error")
            mock_fallback.return_value = async_gen(["Fallback Chunk"])
        elif scenario == "primary_fail_fallback_fail":
            mock_primary.side_effect = Exception("Primary Error")
            mock_fallback.side_effect = Exception("Fallback Error")

        # Act
        stream = agent.analyze_stream(videos_to_test)
        result_chunks = [chunk async for chunk in stream]

        # Assert
        assert result_chunks == expected_chunks, f"Failed on scenario: {scenario}"

        if scenario == "primary_success":
            mock_primary.assert_called_once()
            mock_fallback.assert_not_called()
        elif scenario in ("primary_fail_fallback_success", "primary_fail_fallback_fail"):
            mock_primary.assert_called_once()
            mock_fallback.assert_called_once()
        else:
            mock_primary.assert_not_called()
            mock_fallback.assert_not_called()
