import pytest
from unittest.mock import Mock, patch, call, AsyncMock
from typing import Generator, List
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from google import genai
from google.genai import types


@pytest.fixture
def mock_config() -> Generator[Mock, None, None]:
    with patch("src.core.ai.AppConfig") as mock:
        mock.get_config.return_value.get_api_key.return_value = "fake_api_key"
        yield mock


@pytest.fixture
def mock_genai_client() -> Generator[Mock, None, None]:
    with patch("src.core.ai.genai.Client") as mock:
        client_instance = Mock()
        client_instance.aio = Mock()
        client_instance.aio.models = Mock()
        mock.return_value = client_instance
        yield client_instance


@pytest.fixture
def sample_videos() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="test1",
            title="Test Video 1",
            views=1000,
            retention_avg_pct=55.5,
            type="Long"
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario, primary_succeeds, fallback_succeeds, expected_outputs, expect_error", [
    ("empty_videos", True, True, ["No data to analyze."], False),
    ("primary_success", True, True, ["Primary output"], False),
    ("primary_fail_fallback_success", False, True, ["\n[warning] Primary model failed (Primary failure). Falling back to gemini-2.5-flash...[/warning]\n\n", "Fallback output"], False),
    ("both_fail", False, False, ["\n[warning] Primary model failed (Primary failure). Falling back to gemini-2.5-flash...[/warning]\n\n", "\n[error] Fallback model also failed: Fallback failure. Please try again later.[/error]\n"], False)
])
async def test_analyze_stream_edge_cases(
    mock_config: Mock,
    mock_genai_client: Mock,
    sample_videos: List[VideoAnalysisInput],
    scenario: str,
    primary_succeeds: bool,
    fallback_succeeds: bool,
    expected_outputs: List[str],
    expect_error: bool
) -> None:
    # Arrange
    agent = GeminiThinkingAgent()

    # We create a factory to generate async generators that yield chunks or raise errors
    def make_async_gen(succeeds: bool, output: str, error_msg: str):
        async def _gen():
            if not succeeds:
                raise Exception(error_msg)
            # Yield a mock chunk object with a .text attribute
            chunk = Mock()
            chunk.text = output
            yield chunk
        return _gen()

    async def stream_side_effect(model, contents, config):
        if model == "gemini-3-pro-preview":
            return make_async_gen(primary_succeeds, "Primary output", "Primary failure")
        elif model == "gemini-2.5-flash":
            return make_async_gen(fallback_succeeds, "Fallback output", "Fallback failure")
        else:
            raise ValueError(f"Unknown model: {model}")

    mock_genai_client.aio.models.generate_content_stream = AsyncMock(side_effect=stream_side_effect)

    input_videos = [] if scenario == "empty_videos" else sample_videos

    # Act
    actual_outputs = []
    try:
        async for chunk in agent.analyze_stream(input_videos):
            actual_outputs.append(chunk)

        # Assert
        assert not expect_error, f"Expected an error in scenario {scenario} but none occurred."
        assert actual_outputs == expected_outputs, f"Scenario {scenario} failed: Expected {expected_outputs}, got {actual_outputs}"

    except Exception as e:
        assert expect_error, f"Scenario {scenario} failed: Unexpected error {e}"
