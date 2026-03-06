import pytest
from unittest.mock import Mock, patch
from typing import Generator, Any
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput

@pytest.fixture
def mock_genai_client() -> Generator[Mock, None, None]:
    with patch("src.core.ai.AppConfig.get_config") as mock_config:
        mock_config.return_value.get_api_key.return_value = "fake-api-key"
        with patch("src.core.ai.genai.Client") as mock_client_cls:
            mock_instance = Mock()
            mock_client_cls.return_value = mock_instance
            yield mock_instance

@pytest.mark.parametrize("input_videos, expected", [
    ([], "No data to analyze."),
    ([VideoAnalysisInput(video_id="V", title="T", views=1, retention_avg_pct=1.0, type="Long")], "Analysis Result"),
    ([VideoAnalysisInput(video_id="V2", title="T2", views=1, retention_avg_pct=1.0, type="Shorts")], "No text response generated.")
])
def test_analyze_semantics_boundaries(
    mock_genai_client: Mock,
    input_videos: list[VideoAnalysisInput],
    expected: str
) -> None:
    agent = GeminiThinkingAgent()

    # Configure mock behavior based on expected outcome
    if expected == "Analysis Result":
        mock_response = Mock()
        mock_response.text = "Analysis Result"
        mock_genai_client.models.generate_content.return_value = mock_response
    elif expected == "No text response generated.":
        mock_response = Mock()
        mock_response.text = ""
        mock_genai_client.models.generate_content.return_value = mock_response

    result = agent.analyze_semantics(input_videos)

    assert result == expected, f"Failed on inputs: {input_videos}"

@pytest.mark.asyncio
@pytest.mark.parametrize("scenario, input_videos, primary_err, fallback_err, expected_chunks", [
    ("empty", [], None, None, ["No data to analyze."]),
    ("primary_success", [VideoAnalysisInput(video_id="V", title="T", views=1, retention_avg_pct=1.0, type="Long")], None, None, ["Primary", " ", "Chunk"]),
    ("fallback_success", [VideoAnalysisInput(video_id="V", title="T", views=1, retention_avg_pct=1.0, type="Long")], Exception("Primary Error"), None, [
        "\n[warning] Primary model failed (Primary Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "Fallback", " ", "Chunk"
    ]),
    ("both_fail", [VideoAnalysisInput(video_id="V", title="T", views=1, retention_avg_pct=1.0, type="Long")], Exception("Primary Error"), Exception("Fallback Error"), [
        "\n[warning] Primary model failed (Primary Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "\n[error] Fallback model also failed: Fallback Error. Please try again later.[/error]\n"
    ])
])
async def test_analyze_stream_boundaries(
    mock_genai_client: Mock,
    scenario: str,
    input_videos: list[VideoAnalysisInput],
    primary_err: Exception | None,
    fallback_err: Exception | None,
    expected_chunks: list[str]
) -> None:
    agent = GeminiThinkingAgent()

    # Setup mock stream behavior
    async def mock_primary_stream(*args: Any, **kwargs: Any):
        if primary_err:
            raise primary_err
        for chunk_text in ["Primary", " ", "Chunk"]:
            chunk = Mock()
            chunk.text = chunk_text
            yield chunk

    async def mock_fallback_stream(*args: Any, **kwargs: Any):
        if fallback_err:
            raise fallback_err
        for chunk_text in ["Fallback", " ", "Chunk"]:
            chunk = Mock()
            chunk.text = chunk_text
            yield chunk

    # Attach mock async generators
    async def mock_generate_content_stream(model, *args, **kwargs):
        if model == "gemini-3-pro-preview":
            return mock_primary_stream()
        else:
            return mock_fallback_stream()

    mock_genai_client.aio.models.generate_content_stream = mock_generate_content_stream

    result_chunks = []
    async for chunk in agent.analyze_stream(input_videos):
        result_chunks.append(chunk)

    assert result_chunks == expected_chunks, f"Failed on scenario: {scenario}"
