import pytest
import typing
from unittest.mock import Mock
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput


class AsyncGenMock:
    """Custom mock for async streaming in google-genai SDK."""
    def __init__(
        self,
        chunks: typing.List[typing.Any],
        exception: typing.Optional[Exception] = None
    ):
        self.chunks = chunks
        self.exception = exception

    def __await__(self):
        async def _awaitable():
            return self
        return _awaitable().__await__()

    async def __aiter__(self):
        if self.exception:
            raise self.exception
        for chunk in self.chunks:
            yield chunk


@pytest.fixture
def clean_dataset() -> typing.List[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="test_vid_1",
            title="Test Video",
            views=1000,
            retention_avg_pct=55.5,
            type="Shorts"
        )
    ]


@pytest.fixture
def mock_genai_client(mocker) -> Mock:
    client_mock = mocker.patch("src.core.ai.genai.Client")
    client_instance = Mock()
    client_mock.return_value = client_instance
    return client_instance


@pytest.mark.parametrize(
    "scenario, use_clean_dataset, primary_chunks, primary_error, fallback_chunks, fallback_error, expected_chunks",
    [
        (
            "no_videos",
            False,
            [], None,
            [], None,
            ["No data to analyze."]
        ),
        (
            "primary_success",
            True,
            [Mock(text="chunk1"), Mock(text="chunk2")], None,
            [], None,
            ["chunk1", "chunk2"]
        ),
        (
            "primary_fails_fallback_success",
            True,
            [], Exception("primary timeout"),
            [Mock(text="fallback1")], None,
            [
                "\n[warning] Primary model failed (primary timeout). "
                "Falling back to gemini-2.5-flash...[/warning]\n\n",
                "fallback1"
            ]
        ),
        (
            "both_fail",
            True,
            [], Exception("primary timeout"),
            [], Exception("fallback timeout"),
            [
                "\n[warning] Primary model failed (primary timeout). "
                "Falling back to gemini-2.5-flash...[/warning]\n\n",
                "\n[error] Fallback model also failed: fallback timeout. "
                "Please try again later.[/error]\n"
            ]
        )
    ]
)
@pytest.mark.asyncio
async def test_analyze_stream_edge_cases(
    clean_dataset: typing.List[VideoAnalysisInput],
    mock_genai_client: Mock,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    use_clean_dataset: bool,
    primary_chunks: list,
    primary_error: typing.Optional[Exception],
    fallback_chunks: list,
    fallback_error: typing.Optional[Exception],
    expected_chunks: list
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("APP_ENV", "testing")

    videos = clean_dataset if use_clean_dataset else []

    mock_aio = Mock()
    mock_genai_client.aio = mock_aio

    def side_effect(model, contents, config):
        if model == "gemini-3-pro-preview":
            return AsyncGenMock(chunks=primary_chunks, exception=primary_error)
        elif model == "gemini-2.5-flash":
            return AsyncGenMock(chunks=fallback_chunks, exception=fallback_error)
        return AsyncGenMock(chunks=[])

    mock_aio.models.generate_content_stream.side_effect = side_effect

    agent = GeminiThinkingAgent()

    actual_chunks = []
    async for chunk in agent.analyze_stream(videos):
        actual_chunks.append(chunk)

    assert actual_chunks == expected_chunks, f"Failed on scenario: {scenario}"
