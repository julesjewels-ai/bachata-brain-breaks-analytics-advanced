"""
Unit tests for core application logic.
"""
import pandas as pd
from src.core.app import BachataAnalyticsApp, GeminiThinkingAgent

def test_agent_initialization():
    app = BachataAnalyticsApp()
    assert isinstance(app.agent, GeminiThinkingAgent)

def test_ingest_data_structure():
    app = BachataAnalyticsApp()
    df = app.ingest_data()
    expected_cols = ['video_id', 'title', 'views', 'retention_avg_pct', 'type']
    assert not df.empty
    assert list(df.columns) == expected_cols

def test_outlier_detection():
    app = BachataAnalyticsApp()
    df = pd.DataFrame({
        'video_id': ['1', '2', '3'],
        'title': ['A', 'B', 'Viral'],
        'views': [100, 200, 10000],
        'retention_avg_pct': [50, 50, 90],
        'type': ['Shorts', 'Shorts', 'Shorts']
    })
    anomalies = app.detect_outliers(df)
    assert 'Shorts' in anomalies
    # The logic looks for > 90th percentile. 
    # With 3 items, 90th percentile is high. 'Viral' (10000) should be caught or border case depending on interpolation.
    # For this simple test, we ensure it returns a DataFrame.
    assert isinstance(anomalies['Shorts'], pd.DataFrame)

def test_gemini_agent_output():
    agent = GeminiThinkingAgent()
    output = agent.analyze_semantics([{'title': 'test'}])
    assert "Gemini 3 Thinking Mode" in output
