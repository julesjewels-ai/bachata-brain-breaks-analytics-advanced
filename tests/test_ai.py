import pytest
from unittest.mock import MagicMock, Mock, patch, call
from typing import Any, List, cast
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from src.core.config import AppConfig
from collections import deque
import asyncio

class AsyncGenMock:
    def __init__(self, chunks: List[str] | Exception):
        self.chunks = chunks

    def __await__(self):
        async def _await_mock():
            if isinstance(self.chunks, Exception):
                raise self.chunks
            return self
        return _await_mock().__await__()

    async def __aiter__(self):
        if isinstance(self.chunks, Exception):
            raise self.chunks
        for chunk in self.chunks:
            mock_chunk = MagicMock()
            mock_chunk.text = chunk
            yield mock_chunk

@pytest.fixture
def mock_config() -> MagicMock:
    config = MagicMock(spec=AppConfig)
    config.get_api_key.return_value = "TEST_API_KEY"
    return config

@pytest.fixture
def test_videos() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="vid_1",
            title="Test Video",
            views=1000,
            retention_avg_pct=50.0,
            type="Shorts"
        )
    ]

@pytest.fixture
def agent(mock_config: MagicMock, monkeypatch: pytest.MonkeyPatch) -> GeminiThinkingAgent:
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy_key")
    with patch("src.core.ai.AppConfig.get_config", return_value=mock_config), \
         patch("src.core.ai.genai.Client"):
        return GeminiThinkingAgent()

@pytest.mark.asyncio
@pytest.mark.parametrize("scenario, primary_res, fallback_res, expected_chunks", [
    ("empty_data", [], [], ["No data to analyze."]),
    ("primary_success", ["Chunk 1", "Chunk 2"], [], ["Chunk 1", "Chunk 2"]),
    ("primary_fails_fallback_success", Exception("Primary Err"), ["Fallback 1"], [
        "\n[warning] Primary model failed (Primary Err). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "Fallback 1"
    ]),
    ("both_fail", Exception("Primary Err"), Exception("Fallback Err"), [
        "\n[warning] Primary model failed (Primary Err). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "\n[error] Fallback model also failed: Fallback Err. Please try again later.[/error]\n"
    ]),
])
async def test_analyze_stream(
    agent: GeminiThinkingAgent,
    test_videos: List[VideoAnalysisInput],
    scenario: str,
    primary_res: Any,
    fallback_res: Any,
    expected_chunks: List[str]
) -> None:
    if scenario == "empty_data":
        videos = []
    else:
        videos = test_videos

    mock_client = agent.client

    if scenario != "empty_data":
        mock_models = MagicMock()
        mock_client.aio = MagicMock()
        mock_client.aio.models = mock_models

        def mock_generate_content_stream(model: str, contents: str, config: Any) -> AsyncGenMock:
            if model == agent.PRIMARY_MODEL:
                return AsyncGenMock(primary_res)
            elif model == agent.FALLBACK_MODEL:
                return AsyncGenMock(fallback_res)
            raise ValueError(f"Unexpected model: {model}")

        mock_models.generate_content_stream.side_effect = mock_generate_content_stream

    result_chunks = []
    async for chunk in agent.analyze_stream(videos):
        result_chunks.append(chunk)

    assert result_chunks == expected_chunks, f"Failed on scenario: {scenario}"
