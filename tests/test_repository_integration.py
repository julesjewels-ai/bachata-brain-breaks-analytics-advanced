"""
Integration tests for repository and BachataAnalyticsApp.
"""
import os
import tempfile
import json
from typing import AsyncGenerator
from unittest.mock import Mock, MagicMock
import pytest
import pandas as pd
from src.core.app import BachataAnalyticsApp
from src.core.repository import JsonlRepository
from src.core.models import VideoAnalysisInput
from src.core.interfaces import (
    UserInterface, AIService, ReportGenerator, DataIngestionService,
    NotificationService
)


@pytest.mark.asyncio
async def test_app_archives_analysis_input() -> None:
    # Setup mocks
    mock_ui = Mock(spec=UserInterface)
    mock_ui.loading.return_value = MagicMock()
    mock_ui.loading.return_value.__enter__.return_value = None

    mock_ai = Mock(spec=AIService)
    mock_report = Mock(spec=ReportGenerator)
    mock_ingest = Mock(spec=DataIngestionService)
    mock_notification = Mock(spec=NotificationService)

    # Valid data matching the schema
    mock_ingest.ingest_data.return_value = pd.DataFrame({
        'video_id': ['vid_1', 'vid_2'],
        'title': ['Test Shorts', 'Test Long'],
        'views': [1000, 2000],
        'retention_avg_pct': [50.0, 75.0],
        'type': ['Shorts', 'Long']
    })

    async def mock_stream(videos: list[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        yield "Strategy"

    mock_ai.analyze_stream.side_effect = mock_stream

    mock_ui.display_stream = MagicMock()
    async def mock_display_stream(gen: AsyncGenerator[str, None]) -> None:
        async for _ in gen:
            pass
    mock_ui.display_stream.side_effect = mock_display_stream

    # Use a temporary file for the repository
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl") as tmp:
        repo_path = tmp.name

    try:
        jsonl_repo = JsonlRepository[VideoAnalysisInput](
            filepath=repo_path,
            model_cls=VideoAnalysisInput
        )

        app = BachataAnalyticsApp(
            ui=mock_ui,
            ai_service=mock_ai,
            report_generator=mock_report,
            data_ingestion_service=mock_ingest,
            notification_service=mock_notification,
            repository=jsonl_repo
        )

        await app.run()

        # Verify items were saved
        # The app uses head(5) and tail(5) and concats them,
        # so for 2 elements it duplicates them, creating 4 elements.
        saved_items = jsonl_repo.get_all()
        assert len(saved_items) == 4

        # Verify specific content
        assert saved_items[0].video_id == 'vid_2'  # vid_2 has higher retention 75.0 vs 50.0
        assert saved_items[0].title == 'Test Long'
        assert saved_items[1].video_id == 'vid_1'
        assert saved_items[1].title == 'Test Shorts'

        # Also manually verify JSONL parsing correctly matches memory requirement
        # for proper date/etc model_dump(mode='json') behavior
        with open(repo_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            assert len(lines) == 4
            data1 = json.loads(lines[0])
            assert data1['video_id'] == 'vid_2'
            data2 = json.loads(lines[1])
            assert data2['video_id'] == 'vid_1'

    finally:
        if os.path.exists(repo_path):
            os.remove(repo_path)
