import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import AsyncGenerator, Generator, List, Any
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from src.core.config import AppConfig

@pytest.fixture
def mock_app_config() -> Generator[Mock, None, None]:
    with patch("src.core.ai.AppConfig.get_config") as mock_get_config:
        mock_config = Mock(spec=AppConfig)
        mock_config.get_api_key.return_value = "fake_api_key"
        mock_get_config.return_value = mock_config
        yield mock_get_config

@pytest.fixture
def agent(mock_app_config: Mock) -> Generator[GeminiThinkingAgent, None, None]:
    with patch("src.core.ai.genai.Client") as mock_client_cls:
        # Prevent actual Client initialization
        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        yield GeminiThinkingAgent()

@pytest.fixture
def sample_videos() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="vid1",
            title="Test Video 1",
            views=1000,
            retention_avg_pct=50.5,
            type="Long",
            publish_date="2023-01-01"
        )
    ]


def async_gen_mock(items: List[Any], should_raise: type[Exception] | None = None) -> Mock:
    """Creates a mock that behaves like an async generator directly (not coroutine)."""
    async def mock_generator(*args, **kwargs) -> AsyncGenerator[Any, None]:
        if should_raise:
            raise should_raise("Mocked Exception")
        for item in items:
            yield item

    mock = Mock()
    mock.side_effect = mock_generator
    return mock


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "input_videos, primary_raises, fallback_raises, expected_chunks",
    [
        # Edge Case 1: Empty input list
        (
            [],
            None,
            None,
            ["No data to analyze."]
        ),
        # Edge Case 2: Primary model succeeds
        (
            [True],  # Represents valid videos
            None,
            None,
            ["chunk1", "chunk2"]
        ),
        # Edge Case 3: Primary fails, fallback succeeds
        (
            [True],
            RuntimeError,
            None,
            [
                "\n[warning] Primary model failed (Mocked Exception). Falling back to gemini-2.5-flash...[/warning]\n\n",
                "fallback_chunk1"
            ]
        ),
        # Edge Case 4: Primary fails, fallback also fails
        (
            [True],
            RuntimeError,
            ValueError,
            [
                "\n[warning] Primary model failed (Mocked Exception). Falling back to gemini-2.5-flash...[/warning]\n\n",
                "\n[error] Fallback model also failed: Mocked Exception. Please try again later.[/error]\n"
            ]
        )
    ]
)
async def test_analyze_stream_edge_cases(
    agent: GeminiThinkingAgent,
    sample_videos: List[VideoAnalysisInput],
    input_videos: List[Any],
    primary_raises: type[Exception] | None,
    fallback_raises: type[Exception] | None,
    expected_chunks: List[str]
) -> None:
    # Arrange
    videos = sample_videos if input_videos else []

    # Custom mock for primary model
    agent._stream_primary_model = async_gen_mock(
        items=["chunk1", "chunk2"] if not primary_raises else [],
        should_raise=primary_raises
    )  # type: ignore

    # Custom mock for fallback model
    agent._stream_fallback_model = async_gen_mock(
        items=["fallback_chunk1"] if not fallback_raises else [],
        should_raise=fallback_raises
    )  # type: ignore

    # Act
    collected_chunks = []
    async for chunk in agent.analyze_stream(videos):
        collected_chunks.append(chunk)

    # Assert
    assert collected_chunks == expected_chunks, f"Failed for input scenario with primary_raises={primary_raises}"
