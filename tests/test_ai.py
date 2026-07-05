import pytest
from unittest.mock import patch, MagicMock
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput

class AsyncGenMock:
    """Mock for async generator to simulate aio.models.generate_content_stream."""
    def __init__(self, chunks=None, error=None):
        self.chunks = chunks or []
        self.error = error

    def __await__(self):
        async def _await_func():
            return self
        return _await_func().__await__()

    async def __aiter__(self):
        if self.error:
            raise self.error
        for chunk in self.chunks:
            mock_chunk = MagicMock()
            mock_chunk.text = chunk
            yield mock_chunk

@pytest.fixture
def sample_videos():
    return [
        VideoAnalysisInput(
            video_id="test1",
            title="Test Video 1",
            views=1000,
            retention_avg_pct=60.0,
            type="Shorts"
        ),
        VideoAnalysisInput(
            video_id="test2",
            title="Test Video 2",
            views=2000,
            retention_avg_pct=70.0,
            type="Long"
        )
    ]

@pytest.fixture
def ai_agent():
    with patch('src.core.ai.AppConfig') as mock_config:
        mock_config.get_config.return_value.get_api_key.return_value = "dummy-key"
        with patch('src.core.ai.genai.Client'):
            agent = GeminiThinkingAgent()
            # Agent's self.client is now a mock
            yield agent

def test_analyze_semantics_empty(ai_agent):
    result = ai_agent.analyze_semantics([])
    assert result == "No data to analyze."

def test_analyze_semantics_success(ai_agent, sample_videos):
    mock_response = MagicMock()
    mock_response.text = "Analysis Result"
    ai_agent.client.models.generate_content.return_value = mock_response

    result = ai_agent.analyze_semantics(sample_videos)
    assert result == "Analysis Result"
    ai_agent.client.models.generate_content.assert_called_once()

    # Test fallback if text is empty
    mock_response.text = ""
    result2 = ai_agent.analyze_semantics(sample_videos)
    assert result2 == "No text response generated."

@pytest.mark.asyncio
async def test_stream_primary_model_success(ai_agent):
    ai_agent.client.aio.models.generate_content_stream = MagicMock(
        return_value=AsyncGenMock(chunks=["chunk1", "chunk2"])
    )

    result = []
    async for chunk in ai_agent._stream_primary_model("prompt"):
        result.append(chunk)

    assert result == ["chunk1", "chunk2"]

@pytest.mark.asyncio
async def test_stream_fallback_model_success(ai_agent):
    ai_agent.client.aio.models.generate_content_stream = MagicMock(
        return_value=AsyncGenMock(chunks=["fallback_chunk"])
    )

    result = []
    async for chunk in ai_agent._stream_fallback_model("prompt"):
        result.append(chunk)

    assert result == ["fallback_chunk"]

@pytest.mark.asyncio
async def test_analyze_stream_empty(ai_agent):
    result = []
    async for chunk in ai_agent.analyze_stream([]):
        result.append(chunk)
    assert result == ["No data to analyze."]

@pytest.mark.asyncio
async def test_analyze_stream_primary_success(ai_agent, sample_videos):
    # Use AsyncGenMock but when we iterate analyze_stream, it yields the raw text chunks
    # instead of the mock objects.
    ai_agent.client.aio.models.generate_content_stream = MagicMock(
        return_value=AsyncGenMock(chunks=["primary_1", "primary_2"])
    )

    result = []
    async for chunk in ai_agent.analyze_stream(sample_videos):
        result.append(chunk)

    assert result == ["primary_1", "primary_2"]

@pytest.mark.asyncio
async def test_analyze_stream_fallback_success(ai_agent, sample_videos):
    # Primary model throws error
    async def _mock_primary(prompt):
        raise Exception("Primary Error")
        yield "never"

    async def _mock_fallback(prompt):
        yield "fallback_1"

    ai_agent._stream_primary_model = _mock_primary
    ai_agent._stream_fallback_model = _mock_fallback

    result = []
    async for chunk in ai_agent.analyze_stream(sample_videos):
        result.append(chunk)

    assert len(result) == 2
    assert "Primary model failed" in result[0]
    assert "Primary Error" in result[0]
    assert result[1] == "fallback_1"

@pytest.mark.asyncio
async def test_analyze_stream_total_failure(ai_agent, sample_videos):
    # Primary model throws error
    async def _mock_primary(prompt):
        raise Exception("Primary Error")
        yield "never"

    async def _mock_fallback(prompt):
        raise Exception("Fallback Error")
        yield "never"

    ai_agent._stream_primary_model = _mock_primary
    ai_agent._stream_fallback_model = _mock_fallback

    result = []
    async for chunk in ai_agent.analyze_stream(sample_videos):
        result.append(chunk)

    assert len(result) == 2
    assert "Primary model failed" in result[0]
    assert "Fallback model also failed: Fallback Error" in result[1]
