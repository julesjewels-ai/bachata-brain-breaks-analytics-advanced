"""
Unit tests for the Service Layer.
"""
import pandas as pd
from src.core.services import AnalyticsService, GeminiThinkingAgent
from src.core.models import VideoAnalysisInput


def test_analytics_service_ingest():
    service = AnalyticsService()
    df = service.ingest_data()
    assert not df.empty
    assert "video_id" in df.columns
    assert len(df) == 20


def test_analytics_service_outliers():
    service = AnalyticsService()
    df = pd.DataFrame({
        'video_id': ['1', '2', '3'],
        'title': ['A', 'B', 'Viral'],
        'views': [100, 200, 10000],
        'retention_avg_pct': [50, 50, 90],
        'type': ['Shorts', 'Shorts', 'Shorts']
    })
    anomalies = service.detect_outliers(df)
    assert 'Shorts' in anomalies
    assert len(anomalies['Shorts']) > 0


def test_gemini_agent():
    agent = GeminiThinkingAgent()
    video = VideoAnalysisInput(
        video_id="vid_1",
        title="Test",
        views=100,
        retention_avg_pct=50.0,
        type="Shorts"
    )
    result = agent.analyze_semantics([video])
    assert "Gemini 3 Thinking Mode" in result
