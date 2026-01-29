import pytest
import pandas as pd
from src.core.services import AnalyticsService, GeminiThinkingAgent
from src.core.models import VideoAnalysisInput

@pytest.fixture
def service():
    return AnalyticsService()

def test_ingest_data_structure(service):
    df = service.ingest_data()
    expected_cols = ['video_id', 'title', 'views', 'retention_avg_pct', 'type']
    assert not df.empty
    assert list(df.columns) == expected_cols

def test_outlier_detection(service):
    df = pd.DataFrame({
        'video_id': ['1', '2', '3'],
        'title': ['A', 'B', 'Viral'],
        'views': [100, 200, 10000],
        'retention_avg_pct': [50, 50, 90],
        'type': ['Shorts', 'Shorts', 'Shorts']
    })
    anomalies = service.detect_outliers(df)
    assert 'Shorts' in anomalies
    assert isinstance(anomalies['Shorts'], pd.DataFrame)
    # With 3 items, 90th percentile is high.
    # We expect 'Viral' to be picked up or at least filtered correctly.
    # 100, 200, 10000. Quantile 0.9 is ~8040. 10000 > 8040.
    assert len(anomalies['Shorts']) == 1
    assert anomalies['Shorts'].iloc[0]['views'] == 10000

def test_gemini_agent_output():
    agent = GeminiThinkingAgent()
    video = VideoAnalysisInput(
        video_id="vid_1",
        title="test",
        views=100,
        retention_avg_pct=50.0,
        type="Shorts"
    )
    output = agent.analyze_semantics([video])
    assert "Gemini 3 Thinking Mode" in output
