"""
Integration test for generic repository logic.
"""
import os
import tempfile
import pytest
import pandas as pd
from unittest.mock import Mock, MagicMock
from src.core.app import BachataAnalyticsApp
from src.core.interfaces import (
    UserInterface, AIService, ReportGenerator, DataIngestionService,
    NotificationService
)
from src.core.repository import JsonlRepository
from src.core.models import ViralAnomalyEvent


@pytest.mark.asyncio
async def test_app_persists_anomalies_to_repository():
    """
    Test that the BachataAnalyticsApp successfully persists detected
    viral anomalies into the injected Repository.
    """
    # Create a temporary file for the repository
    fd, temp_path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)

    try:
        # Initialize the actual repository implementation
        anomaly_repository = JsonlRepository[ViralAnomalyEvent](
            filepath=temp_path, model_class=ViralAnomalyEvent
        )

        # Setup mocks
        mock_ui = Mock(spec=UserInterface)
        mock_ui.loading.return_value = MagicMock()
        mock_ui.loading.return_value.__enter__.return_value = None

        mock_ai = Mock(spec=AIService)
        mock_report = Mock(spec=ReportGenerator)
        mock_ingest = Mock(spec=DataIngestionService)
        mock_notification = Mock(spec=NotificationService)

        # We need an anomaly to be detected. The threshold is 90th percentile.
        # Let's provide 11 videos: 10 with 100 views, 1 with 1000 views.
        # The 1000 views one should be the anomaly.
        mock_data = [
            {
                'video_id': f'vid_{i}',
                'title': f'Test {i}',
                'views': 100,
                'retention_avg_pct': 50.0,
                'type': 'Shorts'
            }
            for i in range(10)
        ]
        # Add the outlier
        mock_data.append({
            'video_id': 'vid_outlier',
            'title': 'Viral Video',
            'views': 5000,
            'retention_avg_pct': 90.0,
            'type': 'Shorts'
        })

        mock_ingest.ingest_data.return_value = pd.DataFrame(mock_data)

        # Mock AI Stream
        async def mock_stream(videos):
            yield "Strategy"
        mock_ai.analyze_stream.side_effect = mock_stream

        # Mock display stream
        mock_ui.display_stream = MagicMock()
        async def mock_display_stream(gen):
            async for _ in gen:
                pass
        mock_ui.display_stream.side_effect = mock_display_stream

        # Initialize the App
        app = BachataAnalyticsApp(
            ui=mock_ui,
            ai_service=mock_ai,
            report_generator=mock_report,
            data_ingestion_service=mock_ingest,
            notification_service=mock_notification,
            anomaly_repository=anomaly_repository
        )

        # Run the app
        await app.run()

        # Verify that the repository has the outlier saved
        saved_anomalies = anomaly_repository.get_all()

        # Only the 'vid_outlier' should be saved
        assert len(saved_anomalies) == 1
        assert saved_anomalies[0].video_id == 'vid_outlier'
        assert saved_anomalies[0].title == 'Viral Video'
        assert saved_anomalies[0].views == 5000
        assert saved_anomalies[0].type == 'Shorts'

    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
