import pytest
from unittest.mock import MagicMock, patch
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from src.core.config import AppConfig

class MockChunk:
    def __init__(self, text):
        self.text = text

class AsyncGenMock:
    def __init__(self, chunks=None, exception=None):
        self.chunks = chunks or []
        self.exception = exception

    def __await__(self):
        async def _coro():
            return self
        return _coro().__await__()

    async def __aiter__(self):
        if self.exception:
            raise self.exception
        for chunk in self.chunks:
            yield MockChunk(chunk)

@pytest.fixture
def mock_config() -> MagicMock:
    with patch("src.core.ai.AppConfig") as mock_app_config:
        config_inst = MagicMock(spec=AppConfig)
        config_inst.get_api_key.return_value = "TEST_API_KEY"
        mock_app_config.get_config.return_value = config_inst
        yield config_inst

@pytest.fixture
def agent(mock_config: MagicMock) -> GeminiThinkingAgent:
    with patch("src.core.ai.genai.Client"):
        return GeminiThinkingAgent()

@pytest.fixture
def sample_videos() -> list[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="VID1",
            title="Test Video 1",
            views=1000,
            retention_avg_pct=50.0,
            type="Long"
        )
    ]

@pytest.mark.asyncio
@pytest.mark.parametrize("scenario,primary_exception,fallback_exception,expected_chunks", [
    ("empty_videos", None, None, ["No data to analyze."]),
    ("primary_success", None, None, ["chunk1", "chunk2"]),
    ("primary_fail_fallback_success", Exception("Primary Error"), None, [
        "\n[warning] Primary model failed (Primary Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "fb_chunk1", "fb_chunk2"
    ]),
    ("both_fail", Exception("Primary Error"), Exception("Fallback Error"), [
        "\n[warning] Primary model failed (Primary Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "\n[error] Fallback model also failed: Fallback Error. Please try again later.[/error]\n"
    ])
])
async def test_analyze_stream(
    agent: GeminiThinkingAgent,
    sample_videos: list[VideoAnalysisInput],
    scenario: str,
    primary_exception: Exception | None,
    fallback_exception: Exception | None,
    expected_chunks: list[str]
) -> None:

    if scenario == "empty_videos":
        videos = []
    else:
        videos = sample_videos

    if not primary_exception:
        primary_mock = AsyncGenMock(chunks=["chunk1", "chunk2"])
    else:
        primary_mock = AsyncGenMock(exception=primary_exception)

    if not fallback_exception:
        fallback_mock = AsyncGenMock(chunks=["fb_chunk1", "fb_chunk2"])
    else:
        fallback_mock = AsyncGenMock(exception=fallback_exception)

    def stream_side_effect(model, contents, config):
        if model == agent.PRIMARY_MODEL:
            return primary_mock
        elif model == agent.FALLBACK_MODEL:
            return fallback_mock
        return AsyncGenMock()

    agent.client.aio.models.generate_content_stream = MagicMock(side_effect=stream_side_effect)

    result_stream = agent.analyze_stream(videos)
    actual_chunks = []
    async for chunk in result_stream:
        actual_chunks.append(chunk)

    assert actual_chunks == expected_chunks, f"Failed on scenario: {scenario}"

@pytest.mark.parametrize("scenario,expected", [
    ("empty_videos", "No data to analyze."),
    ("success_with_text", "mock_response_text"),
    ("success_no_text", "No text response generated.")
])
def test_analyze_semantics(
    agent: GeminiThinkingAgent,
    sample_videos: list[VideoAnalysisInput],
    scenario: str,
    expected: str
) -> None:
    if scenario == "empty_videos":
        videos = []
    else:
        videos = sample_videos

    mock_response = MagicMock()
    if scenario == "success_with_text":
        mock_response.text = "mock_response_text"
    elif scenario == "success_no_text":
        mock_response.text = ""

    agent.client.models.generate_content = MagicMock(return_value=mock_response)

    result = agent.analyze_semantics(videos)
    assert result == expected, f"Failed on scenario: {scenario}"
