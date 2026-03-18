import os
import json
import pytest
import tempfile
import pandas as pd
from unittest.mock import Mock, MagicMock

from src.core.app import BachataAnalyticsApp
from src.core.models import VideoAnalysisInput
from src.core.repository import JsonlRepository
from src.core.interfaces import (
    UserInterface, AIService, ReportGenerator, DataIngestionService,
    NotificationService
)

@pytest.mark.asyncio
async def test_repository_archives_data_before_analysis():
    """
    Integration test proving that BachataAnalyticsApp correctly uses the
    Repository pattern to archive VideoAnalysisInput records before calling
    the AIService.
    """
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
        tmp_filepath = tmp.name

    try:
        # 1. Setup Concrete Repository
        repository = JsonlRepository[VideoAnalysisInput](tmp_filepath)

        # 2. Setup Mocks for other dependencies
        mock_ui = Mock(spec=UserInterface)
        mock_ui.loading.return_value = MagicMock()
        mock_ui.loading.return_value.__enter__.return_value = None
        mock_ui.display_stream = MagicMock()

        async def mock_display_stream(gen):
            async for _ in gen:
                pass
        mock_ui.display_stream.side_effect = mock_display_stream

        mock_ai = Mock(spec=AIService)
        async def mock_stream(videos):
            yield "Strategy chunk 1"
        mock_ai.analyze_stream.side_effect = mock_stream

        mock_report = Mock(spec=ReportGenerator)
        mock_notification = Mock(spec=NotificationService)
        mock_ingest = Mock(spec=DataIngestionService)

        # Prepare dummy ingested data with exactly 10 videos (5 top, 5 bottom)
        # to ensure they are all selected and archived.
        data = []
        for i in range(10):
            data.append({
                'video_id': f'vid_{i}',
                'title': f'Test Video {i}',
                'views': 1000 + i,
                'retention_avg_pct': 50.0 + i,
                'type': 'Shorts'
            })
        df = pd.DataFrame(data)
        mock_ingest.ingest_data.return_value = df

        # 3. Setup and Run App
        app = BachataAnalyticsApp(
            ui=mock_ui,
            ai_service=mock_ai,
            report_generator=mock_report,
            data_ingestion_service=mock_ingest,
            notification_service=mock_notification,
            repository=repository
        )

        await app.run()

        # 4. Verify the file was written to
        assert os.path.exists(tmp_filepath)

        with open(tmp_filepath, 'r') as f:
            lines = f.readlines()

        # The app selects top 5 and bottom 5, so there should be 10 records
        assert len(lines) == 10

        # Verify JSON content is valid and matches our model
        for line in lines:
            record_dict = json.loads(line)
            # This should not raise a validation error
            validated_record = VideoAnalysisInput(**record_dict)
            assert validated_record.video_id.startswith('vid_')
            assert validated_record.type == 'Shorts'

    finally:
        # Cleanup temp file
        if os.path.exists(tmp_filepath):
            os.remove(tmp_filepath)
