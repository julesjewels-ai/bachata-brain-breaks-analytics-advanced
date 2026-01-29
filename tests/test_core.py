"""
Unit tests for core application logic.
"""
import pandas as pd
from src.core.app import BachataAnalyticsApp
from src.core.services import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput


class DummyUI:
    def display_header(self, text: str): pass
    def display_section(self, text: str): pass
    def display_status(self, text: str): pass
    def display_table(self, data, title=None): pass
    def display_error(self, error): pass
    def display_success(self, text: str): pass
    def display_info(self, text: str): pass
    def display_message(self, text: str): pass


def test_agent_initialization():
    app = BachataAnalyticsApp(ui=DummyUI())
    assert isinstance(app.agent, GeminiThinkingAgent)


def test_ingest_data_structure():
    app = BachataAnalyticsApp(ui=DummyUI())
    # Logic moved to service, testing via app's service attribute
    df = app.analytics_service.ingest_data()
    expected_cols = ['video_id', 'title', 'views', 'retention_avg_pct', 'type']
    assert not df.empty
    assert list(df.columns) == expected_cols


def test_outlier_detection():
    app = BachataAnalyticsApp(ui=DummyUI())
    df = pd.DataFrame({
        'video_id': ['1', '2', '3'],
        'title': ['A', 'B', 'Viral'],
        'views': [100, 200, 10000],
        'retention_avg_pct': [50, 50, 90],
        'type': ['Shorts', 'Shorts', 'Shorts']
    })
    anomalies = app.analytics_service.detect_outliers(df)
    assert 'Shorts' in anomalies
    assert isinstance(anomalies['Shorts'], pd.DataFrame)


def test_outlier_detection_dynamic_types():
    """Test that outlier detection handles arbitrary types dynamically."""
    app = BachataAnalyticsApp(ui=DummyUI())
    df = pd.DataFrame({
        'video_id': ['1', '2', '3', '4'],
        'title': ['A', 'B', 'C', 'D'],
        'views': [100, 1000, 100, 1000],
        'retention_avg_pct': [50, 90, 50, 90],
        'type': ['NewType1', 'NewType1', 'NewType2', 'NewType2']
    })
    anomalies = app.analytics_service.detect_outliers(df)
    assert 'NewType1' in anomalies
    assert 'NewType2' in anomalies
    assert len(anomalies['NewType1']) == 1  # 1000 should be filtered
    assert len(anomalies['NewType2']) == 1


def test_prepare_agent_input():
    app = BachataAnalyticsApp(ui=DummyUI())
    df = pd.DataFrame({
        'video_id': [f'vid_{i}' for i in range(10)],
        'title': [f'Title {i}' for i in range(10)],
        'views': [100 * i for i in range(10)],
        'retention_avg_pct': [10.0 * i for i in range(10)],
        'type': ['Shorts'] * 10
    })

    result = app.analytics_service.prepare_agent_input(df)
    assert len(result) == 10
    assert isinstance(result[0], VideoAnalysisInput)
    assert result[0].retention_avg_pct == 90.0


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
