import pytest
from unittest.mock import patch, MagicMock
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from src.core.config import AppConfig

# Mock for google.genai async streaming
class AsyncGenMock:
    def __init__(self, chunks, fail_on_start=False, fail_during=False):
        self.chunks = chunks
        self.fail_on_start = fail_on_start
        self.fail_during = fail_during

    def __await__(self):
        async def _awaitable():
            if self.fail_on_start:
                raise Exception("API Connection Error")
            return self
        return _awaitable().__await__()

    async def __aiter__(self):
        if self.fail_on_start:
            raise Exception("API Connection Error")
        for i, chunk_text in enumerate(self.chunks):
            if self.fail_during and i == len(self.chunks) - 1:
                raise Exception("Stream interrupted")
            chunk = MagicMock()
            chunk.text = chunk_text
            yield chunk

@pytest.fixture
def mock_config():
    with patch("src.core.ai.AppConfig") as MockAppConfig:
        config_instance = MagicMock(spec=AppConfig)
        config_instance.get_api_key.return_value = "TEST_API_KEY"
        MockAppConfig.get_config.return_value = config_instance
        yield config_instance

@pytest.fixture
def mock_genai_client():
    with patch("src.core.ai.genai.Client") as MockClient:
        client_instance = MagicMock()
        MockClient.return_value = client_instance
        yield client_instance

@pytest.fixture
def agent(mock_config, mock_genai_client):
    return GeminiThinkingAgent()

@pytest.fixture
def sample_videos():
    return [
        VideoAnalysisInput(
            video_id="VID1",
            title="Bachata Styling Level 1",
            views=1000,
            likes=100,
            comments=10,
            retention_avg_pct=60.0,
            duration_sec=300,
            type="Long"
        ),
        VideoAnalysisInput(
            video_id="VID2",
            title="Crazy Bachata Moves",
            views=5000,
            likes=500,
            comments=50,
            retention_avg_pct=85.0,
            duration_sec=45,
            type="Shorts"
        )
    ]

@pytest.mark.asyncio
async def test_analyze_stream_empty_data(agent):
    chunks = []
    async for chunk in agent.analyze_stream([]):
        chunks.append(chunk)

    assert chunks == ["No data to analyze."]

@pytest.mark.asyncio
@pytest.mark.parametrize("primary_chunks", [
    (["This is ", "a primary ", "response."]),
])
async def test_analyze_stream_success(agent, sample_videos, mock_genai_client, primary_chunks):
    mock_genai_client.aio.models.generate_content_stream.return_value = AsyncGenMock(primary_chunks)

    chunks = []
    async for chunk in agent.analyze_stream(sample_videos):
        chunks.append(chunk)

    assert chunks == primary_chunks
    mock_genai_client.aio.models.generate_content_stream.assert_called_once()
    call_kwargs = mock_genai_client.aio.models.generate_content_stream.call_args[1]
    assert call_kwargs["model"] == agent.PRIMARY_MODEL

@pytest.mark.asyncio
async def test_analyze_stream_primary_fail_fallback_success(agent, sample_videos, mock_genai_client):
    primary_mock = AsyncGenMock([], fail_on_start=True)
    fallback_chunks = ["Fallback ", "response ", "success."]
    fallback_mock = AsyncGenMock(fallback_chunks)

    # Configure the mock to return primary_mock on first call, fallback_mock on second call
    mock_genai_client.aio.models.generate_content_stream.side_effect = [primary_mock, fallback_mock]

    chunks = []
    async for chunk in agent.analyze_stream(sample_videos):
        chunks.append(chunk)

    # Verify fallback warning is in the output
    assert any("Primary model failed" in chunk for chunk in chunks)
    assert any("Fallback " in chunk for chunk in chunks)

    assert mock_genai_client.aio.models.generate_content_stream.call_count == 2
    call_kwargs_primary = mock_genai_client.aio.models.generate_content_stream.call_args_list[0][1]
    call_kwargs_fallback = mock_genai_client.aio.models.generate_content_stream.call_args_list[1][1]

    assert call_kwargs_primary["model"] == agent.PRIMARY_MODEL
    assert call_kwargs_fallback["model"] == agent.FALLBACK_MODEL

@pytest.mark.asyncio
async def test_analyze_stream_both_fail(agent, sample_videos, mock_genai_client):
    primary_mock = AsyncGenMock([], fail_on_start=True)
    fallback_mock = AsyncGenMock([], fail_on_start=True)

    mock_genai_client.aio.models.generate_content_stream.side_effect = [primary_mock, fallback_mock]

    chunks = []
    async for chunk in agent.analyze_stream(sample_videos):
        chunks.append(chunk)

    assert any("Primary model failed" in chunk for chunk in chunks)
    assert any("Fallback model also failed" in chunk for chunk in chunks)

    assert mock_genai_client.aio.models.generate_content_stream.call_count == 2

def test_analyze_semantics_empty_data(agent):
    response = agent.analyze_semantics([])
    assert response == "No data to analyze."

def test_analyze_semantics_success(agent, sample_videos, mock_genai_client):
    mock_response = MagicMock()
    mock_response.text = "Strategic recommendations: use bold text."
    mock_genai_client.models.generate_content.return_value = mock_response

    response = agent.analyze_semantics(sample_videos)

    assert response == mock_response.text
    mock_genai_client.models.generate_content.assert_called_once()

def test_analyze_semantics_no_text(agent, sample_videos, mock_genai_client):
    mock_response = MagicMock()
    mock_response.text = None
    mock_genai_client.models.generate_content.return_value = mock_response

    response = agent.analyze_semantics(sample_videos)

    assert response == "No text response generated."
