import pytest
from unittest.mock import Mock, patch
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from src.core.config import AppConfig
from typing import Any, List

class MockChunk:
    def __init__(self, text: str | None):
        self.text = text

class AsyncGenMock:
    def __init__(self, chunks: list[str], error: Exception | None = None):
        self.chunks = chunks
        self.error = error

    def __await__(self) -> Any:
        async def _return_self() -> "AsyncGenMock":
            if self.error:
                raise self.error
            return self
        return _return_self().__await__()

    async def __aiter__(self) -> Any:
        for chunk_text in self.chunks:
            yield MockChunk(chunk_text)

@pytest.fixture
def clean_dataset() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="vid1",
            title="Title 1",
            views=100,
            retention_avg_pct=50.0,
            type="Long"
        )
    ]

@pytest.fixture
def mock_config() -> Mock:
    config = Mock(spec=AppConfig)
    config.get_api_key.return_value = "TEST_API_KEY"
    return config

@pytest.mark.parametrize("scenario, input_data, response_text, expected", [
    ("empty_data", [], None, "No data to analyze."),
    ("valid_data", ["data"], "Strategy recommendation.", "Strategy recommendation."),
    ("no_text", ["data"], "", "No text response generated."),
    ("none_text", ["data"], None, "No text response generated.")
])
def test_analyze_semantics(
    mock_config: Mock,
    clean_dataset: List[VideoAnalysisInput],
    scenario: str,
    input_data: List[Any],
    response_text: str | None,
    expected: str
) -> None:
    videos = clean_dataset if input_data else []

    with patch("src.core.config.AppConfig.get_config", return_value=mock_config), \
         patch("src.core.ai.genai.Client") as mock_client_cls:

        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        mock_models = Mock()
        mock_client.models = mock_models

        mock_response = Mock()
        mock_response.text = response_text
        mock_models.generate_content.return_value = mock_response

        agent = GeminiThinkingAgent()
        result = agent.analyze_semantics(videos)

        assert result == expected, f"Failed on scenario: {scenario}"

@pytest.mark.parametrize("scenario, input_data, primary_chunks, primary_error, fallback_chunks, fallback_error, expected_outputs", [
    (
        "empty_data",
        [],
        [], None,
        [], None,
        ["No data to analyze."]
    ),
    (
        "primary_success",
        ["data"],
        ["chunk1", "chunk2"], None,
        [], None,
        ["chunk1", "chunk2"]
    ),
    (
        "primary_success_empty_chunk",
        ["data"],
        ["chunk1", "", "chunk2"], None,
        [], None,
        ["chunk1", "chunk2"]
    ),
    (
        "primary_fails_fallback_success",
        ["data"],
        [], Exception("Primary Error"),
        ["fallback1"], None,
        [
            "\n[warning] Primary model failed (Primary Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
            "fallback1"
        ]
    ),
    (
        "primary_fails_fallback_fails",
        ["data"],
        [], Exception("Primary Error"),
        [], Exception("Fallback Error"),
        [
            "\n[warning] Primary model failed (Primary Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
            "\n[error] Fallback model also failed: Fallback Error. Please try again later.[/error]\n"
        ]
    )
])
@pytest.mark.asyncio
async def test_analyze_stream(
    mock_config: Mock,
    clean_dataset: List[VideoAnalysisInput],
    scenario: str,
    input_data: List[Any],
    primary_chunks: list[str],
    primary_error: Exception | None,
    fallback_chunks: list[str],
    fallback_error: Exception | None,
    expected_outputs: list[str]
) -> None:
    # Arrange
    videos = clean_dataset if input_data else []

    with patch("src.core.config.AppConfig.get_config", return_value=mock_config), \
         patch("src.core.ai.genai.Client") as mock_client_cls:

        mock_client = Mock()
        mock_client_cls.return_value = mock_client

        mock_aio = Mock()
        mock_client.aio = mock_aio

        mock_models = Mock()
        mock_aio.models = mock_models

        def mock_generate_content_stream(*args: Any, **kwargs: Any) -> AsyncGenMock:
            model = kwargs.get("model")
            if model == "gemini-3-pro-preview":
                return AsyncGenMock(primary_chunks, primary_error)
            elif model == "gemini-2.5-flash":
                return AsyncGenMock(fallback_chunks, fallback_error)
            return AsyncGenMock([])

        mock_models.generate_content_stream = Mock(side_effect=mock_generate_content_stream)

        agent = GeminiThinkingAgent()

        # Act
        results = []
        async for chunk in agent.analyze_stream(videos):
            results.append(chunk)

        # Assert
        assert results == expected_outputs, f"Failed on scenario: {scenario}"
