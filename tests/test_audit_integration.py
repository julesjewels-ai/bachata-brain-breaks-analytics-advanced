import json

import pandas as pd
import pytest

from src.core.audit import (
    AuditedDataIngestionService,
    FileAuditUnitOfWork,
    StandardAuditService,
)
from src.core.interfaces import DataIngestionService


class MockDataIngestionService(DataIngestionService):
    """Mock implementation for testing."""
    async def ingest_data(self) -> pd.DataFrame:
        return pd.DataFrame({"test": [1, 2, 3]})


@pytest.mark.asyncio
async def test_audit_integration(tmp_path):
    """
    Test that AuditedDataIngestionService records start and completion
    events correctly via the Unit of Work.
    """
    audit_file = tmp_path / "test_audit.jsonl"

    # Setup dependencies
    uow = FileAuditUnitOfWork(str(audit_file))
    audit_service = StandardAuditService(uow)
    mock_ingestion = MockDataIngestionService()

    # Initialize the audited service
    audited_service = AuditedDataIngestionService(
        inner=mock_ingestion, audit_service=audit_service
    )

    # Execute
    result_df = await audited_service.ingest_data()

    # Verify result
    assert len(result_df) == 3

    # Verify audit file was created and contains the correct events
    assert audit_file.exists()

    with open(audit_file, "r") as f:
        events = [json.loads(line) for line in f]

    assert len(events) == 2

    # First event: started
    assert events[0]["action"] == "ingest_data"
    assert events[0]["status"] == "started"

    # Second event: completed
    assert events[1]["action"] == "ingest_data"
    assert events[1]["status"] == "completed"
    assert events[1]["details"]["row_count"] == 3
