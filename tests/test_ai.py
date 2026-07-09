import pytest
from unittest.mock import Mock, patch
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from google.genai import types

class MockChunk:
    def __init__(self, text):
        self.text = text

class AsyncGenMock:
    def __init__(self, chunks, raise_err=None):
        self.chunks = chunks
        self.raise_err = raise_err

    def __await__(self):
        async def _awaitable():
            if self.raise_err:
                raise self.raise_err
            return self
        return _awaitable().__await__()

    async def __aiter__(self):
        if self.raise_err:
            raise self.raise_err
        for chunk in self.chunks:
            yield chunk

@pytest.fixture
def mock_config():
    with patch("src.core.ai.AppConfig") as mock_config_cls:
        mock_instance = mock_config_cls.get_config.return_value
        mock_instance.get_api_key.return_value = "fake_key"
        yield mock_instance

@pytest.fixture
def mock_client(mock_config):
    with patch("src.core.ai.genai.Client") as mock_client_cls:
        client_instance = mock_client_cls.return_value
        yield client_instance

@pytest.fixture
def agent(mock_client) -> GeminiThinkingAgent:
    return GeminiThinkingAgent()

@pytest.fixture
def video() -> VideoAnalysisInput:
    return VideoAnalysisInput(
        video_id="v1",
        title="Test Title",
        views=100,
        retention_avg_pct=50.0,
        type="Shorts"
    )

@pytest.mark.parametrize("videos, mock_text, expected", [
    ([], None, "No data to analyze."),
    (["video"], "Success", "Success"),
    (["video"], "", "No text response generated."),
    (["video"], None, "No text response generated.")
])
def test_analyze_semantics_edge_cases(
    agent: GeminiThinkingAgent,
    video: VideoAnalysisInput,
    videos: list,
    mock_text: str | None,
    expected: str
) -> None:
    # Arrange
    v_list = [video] if videos else []

    mock_response = Mock()
    mock_response.text = mock_text
    agent.client.models.generate_content.return_value = mock_response

    # Act
    result = agent.analyze_semantics(v_list)

    # Assert
    assert result == expected, f"Failed for {videos} with mock {mock_text}"


@pytest.mark.asyncio
@pytest.mark.parametrize("videos, primary_chunks, primary_err, fallback_chunks, fallback_err, expected_outputs", [
    (
        [],
        [], None,
        [], None,
        ["No data to analyze."]
    ),
    (
        ["video"],
        [MockChunk("Hello"), MockChunk("World")], None,
        [], None,
        ["Hello", "World"]
    ),
    (
        ["video"],
        [], Exception("API limit"),
        [MockChunk("Fallback"), MockChunk("Hello")], None,
        [
            "\n[warning] Primary model failed (API limit). Falling back to gemini-2.5-flash...[/warning]\n\n",
            "Fallback", "Hello"
        ]
    ),
    (
        ["video"],
        [], Exception("Primary dead"),
        [], Exception("Fallback dead"),
        [
            "\n[warning] Primary model failed (Primary dead). Falling back to gemini-2.5-flash...[/warning]\n\n",
            "\n[error] Fallback model also failed: Fallback dead. Please try again later.[/error]\n"
        ]
    )
])
async def test_analyze_stream_edge_cases(
    agent: GeminiThinkingAgent,
    video: VideoAnalysisInput,
    videos: list,
    primary_chunks: list,
    primary_err: Exception | None,
    fallback_chunks: list,
    fallback_err: Exception | None,
    expected_outputs: list
) -> None:
    # Arrange
    v_list = [video] if videos else []

    def mock_generate_stream(model, contents, config):
        if model == agent.PRIMARY_MODEL:
            return AsyncGenMock(primary_chunks, primary_err)
        elif model == agent.FALLBACK_MODEL:
            return AsyncGenMock(fallback_chunks, fallback_err)
        return AsyncGenMock([])

    agent.client.aio.models.generate_content_stream.side_effect = mock_generate_stream

    # Act
    results = []
    async for output in agent.analyze_stream(v_list):
        results.append(output)

    # Assert
    assert results == expected_outputs, f"Failed for primary_err={primary_err}, fallback_err={fallback_err}"

def test_build_prompt(agent: GeminiThinkingAgent, video: VideoAnalysisInput) -> None:
    prompt = agent._build_prompt([video])
    assert video.video_id in prompt
    assert video.title in prompt
    assert str(video.views) in prompt
    assert str(video.retention_avg_pct) in prompt
    assert video.type in prompt
