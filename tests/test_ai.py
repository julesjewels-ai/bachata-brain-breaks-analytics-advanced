import pytest
from unittest.mock import MagicMock
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from google.genai import Client

class MockChunk:
    def __init__(self, text: str):
        self.text = text

async def mock_success_stream(*args, **kwargs):
    async def _gen():
        yield MockChunk("primary ")
        yield MockChunk("success")
    return _gen()

async def mock_primary_fail_stream(*args, **kwargs):
    if kwargs.get("model") == "gemini-3-pro-preview":
        raise Exception("Primary simulated failure")
    async def _gen():
        yield MockChunk("fallback ")
        yield MockChunk("success")
    return _gen()

async def mock_total_fail_stream(*args, **kwargs):
    raise Exception("Total simulated failure")

@pytest.fixture
def clean_dataset() -> list[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="123",
            title="Test Video",
            views=1000,
            retention_avg_pct=50.5,
            type="Long"
        )
    ]

@pytest.fixture
def agent(mocker) -> GeminiThinkingAgent:
    # We must patch AppConfig.get_config to prevent real config lookup
    mock_config = MagicMock()
    mock_config.get_api_key.return_value = "TEST_KEY"
    mocker.patch("src.core.ai.AppConfig.get_config", return_value=mock_config)

    # We must patch genai.Client so it doesn't initialize real connections
    mock_client_cls = mocker.patch("src.core.ai.genai.Client")

    agent = GeminiThinkingAgent()
    return agent

@pytest.mark.asyncio
@pytest.mark.parametrize("scenario, expected_chunks", [
    ("empty", ["No data to analyze."]),
    ("success", ["primary ", "success"]),
    ("primary_fail", [
        "\n[warning] Primary model failed (Primary simulated failure). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "fallback ",
        "success"
    ]),
    ("total_fail", [
        "\n[warning] Primary model failed (Total simulated failure). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "\n[error] Fallback model also failed: Total simulated failure. Please try again later.[/error]\n"
    ])
])
async def test_analyze_stream_branches(
    agent: GeminiThinkingAgent,
    clean_dataset: list[VideoAnalysisInput],
    scenario: str,
    expected_chunks: list[str],
    mocker
) -> None:
    # Arrange
    if scenario == "empty":
        clean_dataset = []

    # We patch client.aio.models.generate_content_stream using mocker.patch.object
    if scenario == "success":
        mocker.patch.object(
            agent.client.aio.models,
            "generate_content_stream",
            side_effect=mock_success_stream
        )
    elif scenario == "primary_fail":
        mocker.patch.object(
            agent.client.aio.models,
            "generate_content_stream",
            side_effect=mock_primary_fail_stream
        )
    elif scenario == "total_fail":
        mocker.patch.object(
            agent.client.aio.models,
            "generate_content_stream",
            side_effect=mock_total_fail_stream
        )

    # Act
    chunks = []
    async for chunk in agent.analyze_stream(clean_dataset):
        chunks.append(chunk)

    # Assert
    assert chunks == expected_chunks, f"Failed on scenario: {scenario}"
