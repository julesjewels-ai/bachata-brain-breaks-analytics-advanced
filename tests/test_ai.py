import pytest
from typing import List, AsyncGenerator, Any, Optional
from unittest.mock import Mock, patch
from pytest import MonkeyPatch

from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput

class MockChunk:
    def __init__(self, text: str):
        self.text = text

class AsyncGenMock:
    def __init__(self, items: List[MockChunk], should_raise: bool = False, error: Optional[Exception] = None):
        self.items = items
        self.should_raise = should_raise
        self.error = error

    def __await__(self) -> Any:
        async def _awaitable() -> 'AsyncGenMock':
            return self
        return _awaitable().__await__()

    async def __aiter__(self) -> AsyncGenerator[MockChunk, None]:
        if self.should_raise and self.error:
            raise self.error
        for item in self.items:
            yield item

@pytest.fixture
def clean_videos() -> List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="1",
            title="Test Video",
            views=100,
            retention_avg_pct=50.0,
            type="Long"
        )
    ]

@pytest.mark.asyncio
@pytest.mark.parametrize("scenario, expected_chunks", [
    ("empty_data", ["No data to analyze."]),
    ("primary_success", ["Primary ", "Success"]),
    ("primary_fail_fallback_success", [
        "\n[warning] Primary model failed (Primary Failure). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "Fallback ",
        "Success"
    ]),
    ("both_fail", [
        "\n[warning] Primary model failed (Primary Failure). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "\n[error] Fallback model also failed: Fallback Failure. Please try again later.[/error]\n"
    ])
])
async def test_analyze_stream_branches(
    scenario: str,
    expected_chunks: List[str],
    clean_videos: List[VideoAnalysisInput],
    monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy_key")

    with patch("src.core.ai.genai.Client") as mock_client_cls:
        mock_client = Mock()
        mock_client_cls.return_value = mock_client

        agent = GeminiThinkingAgent()

        videos: List[VideoAnalysisInput] = []
        if scenario != "empty_data":
            videos = clean_videos

        if scenario == "primary_success":
            mock_client.aio.models.generate_content_stream.return_value = AsyncGenMock([MockChunk("Primary "), MockChunk("Success")])
        elif scenario == "primary_fail_fallback_success":
            def mock_stream(*args: Any, **kwargs: Any) -> AsyncGenMock:
                if kwargs.get('model') == agent.PRIMARY_MODEL:
                    return AsyncGenMock([], True, Exception("Primary Failure"))
                else:
                    return AsyncGenMock([MockChunk("Fallback "), MockChunk("Success")])
            mock_client.aio.models.generate_content_stream.side_effect = mock_stream
        elif scenario == "both_fail":
            def mock_stream(*args: Any, **kwargs: Any) -> AsyncGenMock:
                if kwargs.get('model') == agent.PRIMARY_MODEL:
                    return AsyncGenMock([], True, Exception("Primary Failure"))
                else:
                    return AsyncGenMock([], True, Exception("Fallback Failure"))
            mock_client.aio.models.generate_content_stream.side_effect = mock_stream

        result_chunks: List[str] = []
        async for chunk in agent.analyze_stream(videos):
            result_chunks.append(chunk)

        assert result_chunks == expected_chunks
