import json
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from src.core.archiving import ArchivingAIService, FileArchiveRepository
from src.core.interfaces import AIService
from src.core.models import VideoAnalysisInput


class MockAIService(AIService):
    def analyze_semantics(self, videos: list[VideoAnalysisInput]) -> str:
        return "Mocked Semantics Response"

    async def analyze_stream(self, videos: list[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        yield "Chunk 1"
        yield "Chunk 2"

@pytest.fixture
def mock_video_inputs() -> list[VideoAnalysisInput]:
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
def archive_file(tmp_path: Path) -> Path:
    return tmp_path / "test_archive.jsonl"

def test_archiving_ai_service_semantics(
    archive_file: Path, mock_video_inputs: list[VideoAnalysisInput]
) -> None:
    repo = FileArchiveRepository(str(archive_file))
    service = ArchivingAIService(MockAIService(), repo)

    result = service.analyze_semantics(mock_video_inputs)

    assert result == "Mocked Semantics Response"
    assert archive_file.exists()

    with open(archive_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["strategy_output"] == "Mocked Semantics Response"
        assert record["inputs"][0]["video_id"] == "test1"

@pytest.mark.asyncio
async def test_archiving_ai_service_stream(
    archive_file: Path, mock_video_inputs: list[VideoAnalysisInput]
) -> None:
    repo = FileArchiveRepository(str(archive_file))
    service = ArchivingAIService(MockAIService(), repo)

    result = []
    async for chunk in service.analyze_stream(mock_video_inputs):
        result.append(chunk)

    assert "".join(result) == "Chunk 1Chunk 2"
    assert archive_file.exists()

    with open(archive_file, "r") as f:  # noqa: ASYNC230
        lines = f.readlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["strategy_output"] == "Chunk 1Chunk 2"
        assert record["inputs"][0]["video_id"] == "test1"
