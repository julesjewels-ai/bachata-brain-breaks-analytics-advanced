import pytest
from typing import List, Any, Generator
from unittest.mock import Mock, patch

from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput


@pytest.fixture
def clean_videos() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="abc-123",
            title="Test Video",
            views=1000,
            retention_avg_pct=55.5,
            type="Long"
        )
    ]


@pytest.fixture
def mock_genai_client() -> Generator[Mock, None, None]:
    with patch("src.core.ai.genai.Client") as mock_client_cls:
        with patch("src.core.ai.AppConfig.get_config") as mock_config:
            mock_config.return_value.get_api_key.return_value = "fake-key"

            mock_instance = mock_client_cls.return_value
            mock_instance.models.generate_content.return_value.text = "Mocked text"

            yield mock_instance


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario, primary_chunks, primary_error, fallback_chunks, fallback_error, input_empty, expected_outputs",
    [
        (
            "empty_input",
            [], None, [], None, True,
            ["No data to analyze."]
        ),
        (
            "primary_success",
            ["Chunk 1", "", "Chunk 2"], None, [], None, False,
            ["Chunk 1", "Chunk 2"]
        ),
        (
            "primary_failure_fallback_success",
            [], Exception("Network Error"), ["Fallback Chunk 1"], None, False,
            [
                "\n[warning] Primary model failed (Network Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
                "Fallback Chunk 1"
            ]
        ),
        (
            "primary_failure_fallback_failure",
            [], Exception("Network Error 1"), [], Exception("Network Error 2"), False,
            [
                "\n[warning] Primary model failed (Network Error 1). Falling back to gemini-2.5-flash...[/warning]\n\n",
                "\n[error] Fallback model also failed: Network Error 2. Please try again later.[/error]\n"
            ]
        ),
    ]
)
async def test_analyze_stream_boundaries(
    mock_genai_client: Mock,
    clean_videos: List[VideoAnalysisInput],
    scenario: str,
    primary_chunks: List[str],
    primary_error: Exception | None,
    fallback_chunks: List[str],
    fallback_error: Exception | None,
    input_empty: bool,
    expected_outputs: List[str]
) -> None:
    # Arrange
    agent = GeminiThinkingAgent()

    videos = [] if input_empty else clean_videos

    async def mock_generate_content_stream(*args: Any, **kwargs: Any) -> Any:
        model = kwargs.get("model")

        async def mock_generator():
            if model == agent.PRIMARY_MODEL:
                if primary_error:
                    raise primary_error
                for chunk in primary_chunks:
                    mock_chunk = Mock()
                    mock_chunk.text = chunk
                    yield mock_chunk
            elif model == agent.FALLBACK_MODEL:
                if fallback_error:
                    raise fallback_error
                for chunk in fallback_chunks:
                    mock_chunk = Mock()
                    mock_chunk.text = chunk
                    yield mock_chunk
            else:
                raise ValueError(f"Unknown model: {model}")

        return mock_generator()

    # Assign the mock function directly to properly simulate async generator
    agent.client.aio.models.generate_content_stream = mock_generate_content_stream

    # Act
    actual_outputs = []
    async for output in agent.analyze_stream(videos):
        actual_outputs.append(output)

    # Assert
    assert actual_outputs == expected_outputs, f"Failed on scenario: {scenario}"
