import pytest
from unittest.mock import Mock, patch
from typing import Generator, List, Any
from src.core.models import VideoAnalysisInput
from src.core.ai import GeminiThinkingAgent

@pytest.fixture
def mock_config() -> Generator[Mock, None, None]:
    with patch('src.core.ai.AppConfig.get_config') as mock:
        mock.return_value.get_api_key.return_value = "dummy-key"
        yield mock

@pytest.fixture
def mock_genai_client() -> Generator[Mock, None, None]:
    with patch('src.core.ai.genai.Client') as mock_client:
        yield mock_client

@pytest.fixture
def mock_videos() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="123",
            title="Test Video",
            views=1000,
            retention_avg_pct=45.5,
            type="Long"
        )
    ]

@pytest.mark.asyncio
@pytest.mark.parametrize("use_empty_videos, primary_fails, fallback_fails, expected_substrings", [
    (True, False, False, ["No data to analyze."]),
    (False, False, False, ["Primary chunk 1", "Primary chunk 2"]),
    (False, True, False, ["[warning] Primary model failed", "Fallback chunk"]),
    (False, True, True, ["[warning] Primary model failed", "[error] Fallback model also failed"]),
])
async def test_analyze_stream_edge_cases(
    mock_config: Mock,
    mock_genai_client: Mock,
    mock_videos: List[VideoAnalysisInput],
    use_empty_videos: bool,
    primary_fails: bool,
    fallback_fails: bool,
    expected_substrings: List[str]
) -> None:
    # Arrange
    agent = GeminiThinkingAgent()
    input_videos = [] if use_empty_videos else mock_videos

    # We must mock the underlying internal methods rather than standard Mock
    # because they return AsyncGenerators. Memory explicitly guides:
    # "assign a custom mock function that returns an async generator directly"

    async def mock_stream_primary(*args: Any, **kwargs: Any) -> Any:
        if primary_fails:
            raise ValueError("Simulated Primary API Error")
        yield "Primary chunk 1"
        yield "Primary chunk 2"

    async def mock_stream_fallback(*args: Any, **kwargs: Any) -> Any:
        if fallback_fails:
            raise ConnectionError("Simulated Fallback API Error")
        yield "Fallback chunk"

    # Patch the private async generators on the instance
    agent._stream_primary_model = mock_stream_primary  # type: ignore
    agent._stream_fallback_model = mock_stream_fallback  # type: ignore

    # Act
    results = []
    async for chunk in agent.analyze_stream(input_videos):
        results.append(chunk)

    output_text = "".join(results)

    # Assert
    for substring in expected_substrings:
        assert substring in output_text, f"Expected '{substring}' in output, but got '{output_text}'"
