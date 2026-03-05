import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import List, AsyncGenerator, Generator
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from google.genai import types

@pytest.fixture
def sample_videos() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="v1",
            title="How to Dance Bachata",
            views=1000,
            retention_avg_pct=55.5,
            type="Long"
        )
    ]

@pytest.fixture
def mock_genai_client() -> Generator[Mock, None, None]:
    """Mock the genai.Client dependency."""
    with patch("src.core.ai.genai.Client", autospec=True) as mock_client_cls:
        # Create a mock instance
        mock_client = mock_client_cls.return_value
        # Mock the async streaming methods under client.aio.models
        mock_client.aio = Mock()
        mock_client.aio.models = Mock()
        mock_client.aio.models.generate_content_stream = AsyncMock()

        # Mock AppConfig to avoid missing API key error
        with patch("src.core.ai.AppConfig.get_config") as mock_config:
            mock_config.return_value.get_api_key.return_value = "fake_key"
            yield mock_client

async def _async_gen(items: List[Mock]) -> AsyncGenerator[Mock, None]:
    for item in items:
        yield item

@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", [
    "empty_input",
    "primary_success",
    "primary_fail_fallback_success",
    "both_fail"
])
async def test_analyze_stream_edge_cases(
    mock_genai_client: Mock,
    sample_videos: List[VideoAnalysisInput],
    scenario: str
) -> None:
    # Arrange
    agent = GeminiThinkingAgent()

    mock_primary_chunk = Mock(spec=types.GenerateContentResponse)
    mock_primary_chunk.text = "Primary Response"

    mock_fallback_chunk = Mock(spec=types.GenerateContentResponse)
    mock_fallback_chunk.text = "Fallback Response"

    # Configure the mock streams based on the scenario
    if scenario == "empty_input":
        input_videos = []
    else:
        input_videos = sample_videos

    if scenario == "primary_success":
        mock_genai_client.aio.models.generate_content_stream.return_value = _async_gen([mock_primary_chunk])
    elif scenario == "primary_fail_fallback_success":
        # First call (primary) raises Exception, second call (fallback) succeeds
        mock_genai_client.aio.models.generate_content_stream.side_effect = [
            Exception("Primary Model Overloaded"),
            _async_gen([mock_fallback_chunk])
        ]
    elif scenario == "both_fail":
        # Both calls raise Exceptions
        mock_genai_client.aio.models.generate_content_stream.side_effect = [
            Exception("Primary Model Overloaded"),
            Exception("Fallback Model Overloaded")
        ]

    # Act
    stream = agent.analyze_stream(input_videos)
    results = [chunk async for chunk in stream]

    # Assert
    if scenario == "empty_input":
        assert results == ["No data to analyze."], f"Failed on empty input. Expected ['No data to analyze.'], got {results}"
        mock_genai_client.aio.models.generate_content_stream.assert_not_called()
    elif scenario == "primary_success":
        assert results == ["Primary Response"], f"Failed on primary success. Expected ['Primary Response'], got {results}"
        # Verify it was called exactly once with the primary model
        mock_genai_client.aio.models.generate_content_stream.assert_called_once()
        args, kwargs = mock_genai_client.aio.models.generate_content_stream.call_args
        assert kwargs["model"] == agent.PRIMARY_MODEL, f"Expected model {agent.PRIMARY_MODEL}, got {kwargs['model']}"
    elif scenario == "primary_fail_fallback_success":
        assert len(results) == 2, f"Expected 2 results for fallback success, got {len(results)}"
        assert "[warning] Primary model failed (Primary Model Overloaded)." in results[0], f"Expected primary failure warning, got {results[0]}"
        assert results[1] == "Fallback Response", f"Expected 'Fallback Response' from fallback, got {results[1]}"
        # Verify it was called twice (once primary, once fallback)
        assert mock_genai_client.aio.models.generate_content_stream.call_count == 2, f"Expected 2 API calls, got {mock_genai_client.aio.models.generate_content_stream.call_count}"
    elif scenario == "both_fail":
        assert len(results) == 2, f"Expected 2 results for total failure, got {len(results)}"
        assert "[warning] Primary model failed (Primary Model Overloaded)." in results[0], f"Expected primary failure warning, got {results[0]}"
        assert "[error] Fallback model also failed: Fallback Model Overloaded." in results[1], f"Expected fallback error message, got {results[1]}"
        assert mock_genai_client.aio.models.generate_content_stream.call_count == 2, f"Expected 2 API calls, got {mock_genai_client.aio.models.generate_content_stream.call_count}"
