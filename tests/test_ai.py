import pytest
from unittest.mock import MagicMock, patch
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from google.genai import types

class AsyncGenMock:
    def __init__(self, chunks=None, error=None):
        self.chunks = chunks or []
        self.error = error

    def __await__(self):
        async def _awaitable():
            if self.error:
                raise self.error
            return self
        return _awaitable().__await__()

    async def __aiter__(self):
        if self.error:
            raise self.error
        for chunk in self.chunks:
            yield chunk

@pytest.fixture
def mock_videos():
    return [
        VideoAnalysisInput(
            video_id="test1",
            title="Test Video 1",
            views=1000,
            retention_avg_pct=45.5,
            type="Long"
        )
    ]

@pytest.fixture
def agent():
    with patch("src.core.ai.AppConfig.get_config") as mock_config:
        mock_config.return_value.get_api_key.return_value = "fake_key"
        with patch("src.core.ai.genai.Client"):
            agent = GeminiThinkingAgent()
            yield agent

def test_analyze_semantics_no_videos(agent):
    result = agent.analyze_semantics([])
    assert result == "No data to analyze."

def test_analyze_semantics_with_videos(agent, mock_videos):
    mock_response = MagicMock()
    mock_response.text = "Strategic recommendation"
    agent.client.models.generate_content.return_value = mock_response

    result = agent.analyze_semantics(mock_videos)
    assert result == "Strategic recommendation"
    agent.client.models.generate_content.assert_called_once()

def test_analyze_semantics_no_text_in_response(agent, mock_videos):
    mock_response = MagicMock()
    mock_response.text = ""
    agent.client.models.generate_content.return_value = mock_response

    result = agent.analyze_semantics(mock_videos)
    assert result == "No text response generated."

@pytest.mark.asyncio
async def test_analyze_stream_no_videos(agent):
    results = []
    async for chunk in agent.analyze_stream([]):
        results.append(chunk)
    assert results == ["No data to analyze."]

@pytest.mark.asyncio
async def test_analyze_stream_success(agent, mock_videos):
    mock_chunk1 = MagicMock()
    mock_chunk1.text = "Chunk 1 "
    mock_chunk2 = MagicMock()
    mock_chunk2.text = "Chunk 2"
    mock_chunk3 = MagicMock()
    mock_chunk3.text = "" # Should be ignored

    agent.client.aio.models.generate_content_stream.return_value = AsyncGenMock(
        chunks=[mock_chunk1, mock_chunk2, mock_chunk3]
    )

    results = []
    async for chunk in agent.analyze_stream(mock_videos):
        results.append(chunk)

    assert results == ["Chunk 1 ", "Chunk 2"]
    agent.client.aio.models.generate_content_stream.assert_called_once()

    # Assert called with primary model and config
    call_kwargs = agent.client.aio.models.generate_content_stream.call_args.kwargs
    assert call_kwargs["model"] == agent.PRIMARY_MODEL
    assert call_kwargs["config"].temperature == 1.0
    assert call_kwargs["config"].thinking_config.include_thoughts == True


@pytest.mark.asyncio
async def test_analyze_stream_primary_fails_fallback_succeeds(agent, mock_videos):
    mock_chunk = MagicMock()
    mock_chunk.text = "Fallback output"

    # Primary fails
    agent.client.aio.models.generate_content_stream.side_effect = [
        AsyncGenMock(error=Exception("Primary Error")),
        AsyncGenMock(chunks=[mock_chunk])
    ]

    results = []
    async for chunk in agent.analyze_stream(mock_videos):
        results.append(chunk)

    assert len(results) == 2
    assert "[warning] Primary model failed" in results[0]
    assert "Primary Error" in results[0]
    assert "Falling back to gemini-2.5-flash" in results[0]
    assert results[1] == "Fallback output"

    assert agent.client.aio.models.generate_content_stream.call_count == 2
    # Verify fallback call args
    call_kwargs = agent.client.aio.models.generate_content_stream.call_args.kwargs
    assert call_kwargs["model"] == agent.FALLBACK_MODEL
    assert call_kwargs["config"].temperature == 0.7


@pytest.mark.asyncio
async def test_analyze_stream_both_fail(agent, mock_videos):
    # Both fail
    agent.client.aio.models.generate_content_stream.side_effect = [
        AsyncGenMock(error=Exception("Primary Error")),
        AsyncGenMock(error=Exception("Fallback Error"))
    ]

    results = []
    async for chunk in agent.analyze_stream(mock_videos):
        results.append(chunk)

    assert len(results) == 2
    assert "[warning] Primary model failed" in results[0]
    assert "[error] Fallback model also failed: Fallback Error" in results[1]

    assert agent.client.aio.models.generate_content_stream.call_count == 2
