"""
Integration tests for the auditing feature.
"""
import os
import json
import pytest
from unittest.mock import Mock, MagicMock

from src.core.models import VideoAnalysisInput
from src.core.auditing import JSONLinesAuditRepository, AuditedAIService
from src.core.interfaces import AIService

@pytest.fixture
def mock_ai_service():
    mock = Mock(spec=AIService)
    mock.analyze_semantics.return_value = "Mocked AI Response"

    async def mock_stream(videos):
        yield "Mocked "
        yield "AI "
        yield "Stream"

    mock.analyze_stream = mock_stream
    return mock

@pytest.fixture
def sample_video_inputs():
    return [
        VideoAnalysisInput(
            video_id="vid-1",
            title="First Video",
            views=1000,
            retention_avg_pct=50.5,
            type="Shorts"
        ),
        VideoAnalysisInput(
            video_id="vid-2",
            title="Second Video",
            views=2000,
            retention_avg_pct=60.0,
            type="Long"
        )
    ]

def test_audited_ai_service_semantics(mock_ai_service, sample_video_inputs, tmp_path):
    # Setup
    audit_file = tmp_path / "test_audit.jsonl"
    repository = JSONLinesAuditRepository(str(audit_file))
    audited_service = AuditedAIService(ai_service=mock_ai_service, repository=repository)

    # Execute
    result = audited_service.analyze_semantics(sample_video_inputs)

    # Verify delegation
    assert result == "Mocked AI Response"
    mock_ai_service.analyze_semantics.assert_called_once_with(sample_video_inputs)

    # Verify persistence
    assert audit_file.exists()

    with open(audit_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 2

        # Verify first item
        data1 = json.loads(lines[0])
        assert data1["video_id"] == "vid-1"
        assert data1["title"] == "First Video"

        # Verify second item
        data2 = json.loads(lines[1])
        assert data2["video_id"] == "vid-2"
        assert data2["title"] == "Second Video"

@pytest.mark.asyncio
async def test_audited_ai_service_stream(mock_ai_service, sample_video_inputs, tmp_path):
    # Setup
    audit_file = tmp_path / "test_audit.jsonl"
    repository = JSONLinesAuditRepository(str(audit_file))
    audited_service = AuditedAIService(ai_service=mock_ai_service, repository=repository)

    # Execute
    chunks = []
    async for chunk in audited_service.analyze_stream(sample_video_inputs):
        chunks.append(chunk)

    # Verify delegation
    assert "".join(chunks) == "Mocked AI Stream"

    # Verify persistence
    assert audit_file.exists()

    with open(audit_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 2

        data1 = json.loads(lines[0])
        assert data1["video_id"] == "vid-1"
