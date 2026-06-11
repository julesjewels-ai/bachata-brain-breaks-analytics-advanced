import pytest
from unittest.mock import patch, MagicMock
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput

class AsyncGenMock:
    def __init__(self, chunks, exc=None):
        self.chunks = chunks
        self.exc = exc

    def __await__(self):
        async def _awaitable():
            return self
        return _awaitable().__await__()

    async def __aiter__(self):
        if self.exc:
            raise self.exc
        for chunk in self.chunks:
            mock_chunk = MagicMock()
            mock_chunk.text = chunk
            yield mock_chunk

@pytest.fixture
def mock_videos() -> list[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="vid_1",
            title="Test",
            views=10,
            retention_avg_pct=10.0,
            type="Shorts"
        )
    ]

@pytest.mark.asyncio
@pytest.mark.parametrize("scenario, primary_res, fallback_res, expected_chunks", [
    ("empty_videos", None, None, ["No data to analyze."]),
    ("primary_success", AsyncGenMock(["Chunk 1", "Chunk 2"]), None, ["Chunk 1", "Chunk 2"]),
    ("primary_fail_fallback_success", AsyncGenMock([], Exception("Primary API Error")), AsyncGenMock(["Fallback Chunk 1"]), [
        "\n[warning] Primary model failed (Primary API Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "Fallback Chunk 1"
    ]),
    ("both_fail", AsyncGenMock([], Exception("Primary API Error")), AsyncGenMock([], Exception("Fallback API Error")), [
        "\n[warning] Primary model failed (Primary API Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "\n[error] Fallback model also failed: Fallback API Error. Please try again later.[/error]\n"
    ])
])
@patch('src.core.ai.genai.Client')
async def test_analyze_stream_edge_cases(
    mock_client_class: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    mock_videos: list[VideoAnalysisInput],
    scenario: str,
    primary_res: AsyncGenMock | None,
    fallback_res: AsyncGenMock | None,
    expected_chunks: list[str]
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy_key")

    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    # We mock the generate_content_stream async generator behavior
    # The SDK uses self.client.aio.models.generate_content_stream
    mock_aio_models = MagicMock()
    mock_client.aio.models = mock_aio_models

    def side_effect(model, contents, config):
        if model == GeminiThinkingAgent.PRIMARY_MODEL:
            return primary_res
        elif model == GeminiThinkingAgent.FALLBACK_MODEL:
            return fallback_res
        raise ValueError(f"Unknown model: {model}")

    mock_aio_models.generate_content_stream.side_effect = side_effect

    agent = GeminiThinkingAgent()

    videos = [] if scenario == "empty_videos" else mock_videos

    results = []
    async for chunk in agent.analyze_stream(videos):
        results.append(chunk)

    assert results == expected_chunks
