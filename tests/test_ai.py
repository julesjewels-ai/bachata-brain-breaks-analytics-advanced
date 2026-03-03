import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import AsyncGenerator, List, Any

from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from google.genai import types

# Helper to create an async generator that yields given chunks
async def create_async_generator(items: List[Any]) -> AsyncGenerator[Any, None]:
    for item in items:
        yield item

@pytest.fixture
def clean_videos() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="test_id",
            title="Test Title",
            views=1000,
            retention_avg_pct=50.5,
            type="Long"
        )
    ]

@pytest.fixture
def mock_config() -> Mock:
    with patch("src.core.ai.AppConfig.get_config") as mock_get_config:
        config_instance = Mock()
        config_instance.get_api_key.return_value = "fake_api_key"
        mock_get_config.return_value = config_instance
        yield mock_get_config

@pytest.fixture
def mock_genai_client(mock_config: Mock) -> Mock:
    with patch("src.core.ai.genai.Client") as mock_client_cls:
        client_instance = Mock()
        client_instance.aio = Mock()
        client_instance.aio.models = Mock()

        # Make the mock stream return a default async generator
        client_instance.aio.models.generate_content_stream = AsyncMock()

        mock_client_cls.return_value = client_instance
        yield client_instance

@pytest.mark.asyncio
@pytest.mark.parametrize("scenario, expected_chunks", [
    (
        "empty_videos",
        ["No data to analyze."]
    ),
    (
        "primary_success",
        ["Chunk 1", "Chunk 2"]
    ),
    (
        "primary_fail_fallback_success",
        ["\n[warning] Primary model failed (Primary Error). Falling back to gemini-2.5-flash...[/warning]\n\n", "Fallback Chunk", "Fallback Chunk 2"]
    ),
    (
        "primary_fail_fallback_fail",
        ["\n[warning] Primary model failed (Primary Error). Falling back to gemini-2.5-flash...[/warning]\n\n", "\n[error] Fallback model also failed: Fallback Error. Please try again later.[/error]\n"]
    )
])
async def test_analyze_stream_boundaries(
    scenario: str,
    expected_chunks: List[str],
    clean_videos: List[VideoAnalysisInput],
    mock_genai_client: Mock
) -> None:

    agent = GeminiThinkingAgent()

    # Arrange
    if scenario == "empty_videos":
        videos = []
    elif scenario == "primary_success":
        videos = clean_videos

        # Mock primary model stream yielding text and None text
        mock_chunk_1 = Mock()
        mock_chunk_1.text = "Chunk 1"
        mock_chunk_none = Mock()
        mock_chunk_none.text = None
        mock_chunk_2 = Mock()
        mock_chunk_2.text = "Chunk 2"

        mock_genai_client.aio.models.generate_content_stream.return_value = create_async_generator(
            [mock_chunk_1, mock_chunk_none, mock_chunk_2]
        )

    elif scenario == "primary_fail_fallback_success":
        videos = clean_videos

        # Primary fails
        mock_genai_client.aio.models.generate_content_stream.side_effect = [
            Exception("Primary Error"),
            create_async_generator([
                Mock(text="Fallback Chunk"),
                Mock(text=None),
                Mock(text="Fallback Chunk 2")
            ])
        ]

    elif scenario == "primary_fail_fallback_fail":
        videos = clean_videos

        # Both fail
        mock_genai_client.aio.models.generate_content_stream.side_effect = [
            Exception("Primary Error"),
            Exception("Fallback Error")
        ]

    # Act
    stream = agent.analyze_stream(videos)

    # Assert
    actual_chunks = []
    async for chunk in stream:
        actual_chunks.append(chunk)

    assert actual_chunks == expected_chunks, f"Failed on analyze_stream for scenario: {scenario}"


@pytest.mark.parametrize("scenario, expected_result", [
    ("empty_videos", "No data to analyze."),
    ("primary_success_text", "Semantics Output"),
    ("primary_success_none", "No text response generated.")
])
def test_analyze_semantics_boundaries(
    scenario: str,
    expected_result: str,
    clean_videos: List[VideoAnalysisInput],
    mock_genai_client: Mock
) -> None:

    agent = GeminiThinkingAgent()

    # Arrange
    if scenario == "empty_videos":
        videos = []
    else:
        videos = clean_videos
        mock_response = Mock()
        if scenario == "primary_success_text":
            mock_response.text = "Semantics Output"
        else:
            mock_response.text = None
        mock_genai_client.models.generate_content.return_value = mock_response

    # Act
    result = agent.analyze_semantics(videos)

    # Assert
    assert result == expected_result, f"Failed on analyze_semantics for scenario: {scenario}"
