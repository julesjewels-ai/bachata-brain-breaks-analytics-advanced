import pytest
import asyncio
from typing import AsyncGenerator, Iterator, Any
from unittest.mock import MagicMock
from pytest_mock import MockerFixture
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from google.genai import Client

class MockChunk:
    def __init__(self, text: str | None):
        self.text = text

async def mock_response_stream(chunks: list[str | None]) -> AsyncGenerator[MockChunk, None]:
    for text in chunks:
        yield MockChunk(text)

async def mock_response_stream_fail(exc: Exception) -> AsyncGenerator[MockChunk, None]:
    raise exc
    yield MockChunk("unreachable")

def get_test_videos() -> list[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="1",
            title="A Test Video",
            views=100,
            retention_avg_pct=50.0,
            type="Long"
        )
    ]

@pytest.mark.asyncio
@pytest.mark.parametrize("input_videos, primary_exc, fallback_exc, expected_results, stream_chunks", [
    ([], None, None, ["No data to analyze."], []),
    (get_test_videos(), None, None, ["chunk1", "chunk2"], ["chunk1", None, "chunk2"]), # Testing branch 89->88, 103->102 (if chunk.text evaluates to False)
    (get_test_videos(), Exception("Primary Error"), None, [
        "\n[warning] Primary model failed (Primary Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "fallback1", "fallback2"
    ], ["fallback1", None, "fallback2"]),
    (get_test_videos(), Exception("Primary Error"), Exception("Fallback Error"), [
        "\n[warning] Primary model failed (Primary Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "\n[error] Fallback model also failed: Fallback Error. Please try again later.[/error]\n"
    ], [])
])
async def test_analyze_stream(
    mocker: MockerFixture,
    input_videos: list[VideoAnalysisInput],
    primary_exc: Exception | None,
    fallback_exc: Exception | None,
    expected_results: list[str],
    stream_chunks: list[str | None]
) -> None:
    mock_config = MagicMock()
    mock_config.get_api_key.return_value = "fake_key"
    mocker.patch("src.core.ai.AppConfig.get_config", return_value=mock_config)

    agent = GeminiThinkingAgent()
    mock_stream = mocker.patch.object(agent.client.aio.models, 'generate_content_stream')

    if primary_exc and fallback_exc:
        mock_stream.side_effect = [
            mock_response_stream_fail(primary_exc),
            mock_response_stream_fail(fallback_exc)
        ]
    elif primary_exc:
        mock_stream.side_effect = [
            mock_response_stream_fail(primary_exc),
            mock_response_stream(stream_chunks)
        ]
    else:
        mock_stream.side_effect = [
            mock_response_stream(stream_chunks)
        ]

    results = []
    async for chunk in agent.analyze_stream(input_videos):
        results.append(chunk)

    assert results == expected_results

@pytest.mark.parametrize("input_videos, mock_response_text, expected_text", [
    ([], None, "No data to analyze."),
    (
        [VideoAnalysisInput(video_id="2", title="B", views=20, retention_avg_pct=60.0, type="Shorts")],
        "Analysis Result",
        "Analysis Result"
    ),
    (
        [VideoAnalysisInput(video_id="3", title="C", views=30, retention_avg_pct=70.0, type="Long")],
        "",
        "No text response generated."
    ),
    (
        [VideoAnalysisInput(video_id="4", title="D", views=40, retention_avg_pct=80.0, type="Shorts")],
        None,
        "No text response generated."
    )
])
def test_analyze_semantics(
    input_videos: list[VideoAnalysisInput],
    mock_response_text: str | None,
    expected_text: str,
    mocker: MockerFixture
) -> None:
    mock_config = MagicMock()
    mock_config.get_api_key.return_value = "fake_key"
    mocker.patch("src.core.ai.AppConfig.get_config", return_value=mock_config)

    agent = GeminiThinkingAgent()

    mock_generate = mocker.patch.object(agent.client.models, 'generate_content')

    mock_response = MagicMock()
    mock_response.text = mock_response_text
    mock_generate.return_value = mock_response

    result = agent.analyze_semantics(input_videos)
    assert result == expected_text
