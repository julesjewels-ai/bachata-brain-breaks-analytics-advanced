import pytest
from unittest.mock import Mock, patch
from typing import AsyncGenerator

from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput


class MockChunk:
    def __init__(self, text: str):
        self.text = text


class AsyncGenMock:
    def __init__(self, chunks: list[MockChunk]):
        self.chunks = chunks

    def __await__(self):
        async def _self():
            return self
        return _self().__await__()

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk


@pytest.fixture
def clean_dataset() -> list[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="test1",
            title="Test Video",
            views=1000,
            retention_avg_pct=50.0,
            type="Long"
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario, primary_fail, fallback_fail, empty_videos, expected_substrings",
    [
        ("empty_videos", False, False, True, ["No data to analyze."]),
        ("primary_success", False, False, False, ["chunk1", "chunk2"]),
        ("primary_fail_fallback_success", True, False, False, ["Primary model failed", "fallback_chunk1"]),
        ("both_fail", True, True, False, ["Primary model failed", "Fallback model also failed"]),
    ],
)
async def test_analyze_stream_branches(
    clean_dataset: list[VideoAnalysisInput],
    scenario: str,
    primary_fail: bool,
    fallback_fail: bool,
    empty_videos: bool,
    expected_substrings: list[str]
) -> None:
    # Arrange
    with patch("src.core.ai.AppConfig.get_config") as mock_get_config:
        mock_config = Mock()
        mock_config.get_api_key.return_value = "fake_api_key"
        mock_get_config.return_value = mock_config

        with patch("src.core.ai.genai.Client") as mock_client_cls:
            mock_client = Mock()
            mock_client_cls.return_value = mock_client

            agent = GeminiThinkingAgent()

            def mock_generate_content_stream(model, contents, config):
                if model == agent.PRIMARY_MODEL:
                    if primary_fail:
                        raise RuntimeError("Primary Error")
                    return AsyncGenMock([MockChunk("chunk1"), MockChunk("chunk2")])
                elif model == agent.FALLBACK_MODEL:
                    if fallback_fail:
                        raise RuntimeError("Fallback Error")
                    return AsyncGenMock([MockChunk("fallback_chunk1")])

            mock_client.aio.models.generate_content_stream = Mock(
                side_effect=mock_generate_content_stream
            )

            videos = [] if empty_videos else clean_dataset

            # Act
            result_chunks = []
            async for chunk in agent.analyze_stream(videos):
                result_chunks.append(chunk)

            result_text = "".join(result_chunks)

            # Assert
            for expected in expected_substrings:
                assert expected in result_text, f"Failed on {scenario}: missing '{expected}' in result '{result_text}'"
