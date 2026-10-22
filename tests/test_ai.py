from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput


@pytest.fixture
def videos_dataset() -> list[VideoAnalysisInput]:
    return [
        VideoAnalysisInput(
            video_id="abc",
            title="Test Video",
            views=1000,
            retention_avg_pct=55.5,
            type="Long"
        )
    ]

# Mocks an async generator chunk with a text attribute
class MockChunk:
    def __init__(self, text: str | None):
        self.text = text

@pytest.mark.asyncio
@pytest.mark.parametrize("scenario, expected_texts", [
    ("empty_list", ["No data to analyze."]),
    ("primary_success", ["Chunk 1 ", "Chunk 2"]),
    ("primary_fail_fallback_success", [
        "\n[warning] Primary model failed (Primary Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "Fallback Chunk 1"
    ]),
    ("primary_fail_fallback_fail", [
        "\n[warning] Primary model failed (Primary Error). Falling back to gemini-2.5-flash...[/warning]\n\n",
        "\n[error] Fallback model also failed: Fallback Error. Please try again later.[/error]\n"
    ]),
])
async def test_analyze_stream(
    mocker: MockerFixture,
    videos_dataset: list[VideoAnalysisInput],
    scenario: str,
    expected_texts: list[str]
) -> None:
    # Setup AppConfig mock for GeminiThinkingAgent initialization
    mock_config = mocker.patch("src.core.ai.AppConfig")
    mock_config_instance = mock_config.get_config.return_value
    mock_config_instance.get_api_key.return_value = "fake_key"

    agent = GeminiThinkingAgent()

    if scenario == "empty_list":
        videos_dataset = []

    # Prepare async generators for the mock
    async def primary_gen() -> AsyncGenerator[MockChunk, None]:
        if scenario.startswith("primary_fail"):
            raise ValueError("Primary Error")
            yield MockChunk(None) # unreachable but helps with types
        yield MockChunk("Chunk 1 ")
        yield MockChunk(None) # Testing empty text chunk handling
        yield MockChunk("Chunk 2")

    async def fallback_gen() -> AsyncGenerator[MockChunk, None]:
        if scenario == "primary_fail_fallback_fail":
            raise ValueError("Fallback Error")
            yield MockChunk(None)
        yield MockChunk("Fallback Chunk 1")

    async def mock_generate_content_stream(model: str, contents: str, config: object) -> AsyncGenerator[MockChunk, None]:
        if model == agent.PRIMARY_MODEL:
            async for chunk in primary_gen():
                yield chunk
        else:
            async for chunk in fallback_gen():
                yield chunk

    # Mock the generate_content_stream method using patch.object directly on the property
    mocker.patch.object(
        agent.client.aio.models,
        "generate_content_stream",
        side_effect=mock_generate_content_stream
    )

    # Act
    results = []
    async for chunk in agent.analyze_stream(videos_dataset):
        results.append(chunk)

    # Assert
    assert results == expected_texts, f"Failed on scenario: {scenario}"

@pytest.mark.parametrize("scenario, expected_text, mock_text", [
    ("empty_list", "No data to analyze.", "ignored"),
    ("success", "Analysis complete.", "Analysis complete."),
    ("empty_response", "No text response generated.", "")
])
def test_analyze_semantics(
    mocker: MockerFixture,
    videos_dataset: list[VideoAnalysisInput],
    scenario: str,
    expected_text: str,
    mock_text: str
) -> None:
    mock_config = mocker.patch("src.core.ai.AppConfig")
    mock_config_instance = mock_config.get_config.return_value
    mock_config_instance.get_api_key.return_value = "fake_key"

    agent = GeminiThinkingAgent()

    if scenario == "empty_list":
        videos_dataset = []

    mock_response = MagicMock()
    mock_response.text = mock_text
    mocker.patch.object(agent.client.models, "generate_content", return_value=mock_response)

    result = agent.analyze_semantics(videos_dataset)
    assert result == expected_text, f"Failed on scenario: {scenario}"
