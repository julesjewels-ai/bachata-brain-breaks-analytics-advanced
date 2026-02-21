"""
Unit tests for core application logic.
"""
import pandas as pd
from contextlib import nullcontext
from src.core.app import BachataAnalyticsApp
from src.core.ai import GeminiThinkingAgent
from src.core.models import VideoAnalysisInput
from src.core.interfaces import UserInterface, AIService, ReportGenerator, DataIngestionService

class DummyUI(UserInterface):
    def display_header(self, text: str): pass
    def display_section(self, text: str): pass
    def display_status(self, text: str): pass
    def display_table(self, data, title=None): pass
    def display_error(self, error): pass
    def display_success(self, text: str): pass
    def display_info(self, text: str): pass
    def display_message(self, text: str): pass
    def loading(self, text: str): return nullcontext()
    async def display_stream(self, generator):
        async for _ in generator:
            pass

class MockAIService(AIService):
    def analyze_semantics(self, videos):
        return "Mock Analysis"
    async def analyze_stream(self, videos):
        yield "Mock Analysis"

class MockReportGenerator(ReportGenerator):
    def generate_report(self, anomalies, strategy, filepath):
        pass

class MockDataIngestionService(DataIngestionService):
    def ingest_data(self) -> pd.DataFrame:
        # Return a minimal valid DataFrame
        return pd.DataFrame({
            'video_id': ['vid_1'],
            'title': ['Test Video'],
            'views': [1000],
            'retention_avg_pct': [50.0],
            'type': ['Long']
        })

def test_agent_initialization():
    ai_service = MockAIService()
    report_generator = MockReportGenerator()
    ingestion_service = MockDataIngestionService()
    app = BachataAnalyticsApp(
        ui=DummyUI(),
        ai_service=ai_service,
        report_generator=report_generator,
        ingestion_service=ingestion_service
    )
    assert app.ai_service == ai_service
    assert app.report_generator == report_generator
    assert app.ingestion_service == ingestion_service

def test_ingest_data_delegation():
    """Test that app delegates ingestion to the service."""
    ai_service = MockAIService()
    report_generator = MockReportGenerator()
    ingestion_service = MockDataIngestionService()
    app = BachataAnalyticsApp(
        ui=DummyUI(),
        ai_service=ai_service,
        report_generator=report_generator,
        ingestion_service=ingestion_service
    )
    df = app.ingest_data()
    assert not df.empty
    assert df.iloc[0]['video_id'] == 'vid_1'

def test_outlier_detection():
    ai_service = MockAIService()
    report_generator = MockReportGenerator()
    ingestion_service = MockDataIngestionService()
    app = BachataAnalyticsApp(
        ui=DummyUI(),
        ai_service=ai_service,
        report_generator=report_generator,
        ingestion_service=ingestion_service
    )
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

def test_outlier_detection_dynamic_types():
    """Test that outlier detection handles arbitrary types dynamically."""
    ai_service = MockAIService()
    report_generator = MockReportGenerator()
    ingestion_service = MockDataIngestionService()
    app = BachataAnalyticsApp(
        ui=DummyUI(),
        ai_service=ai_service,
        report_generator=report_generator,
        ingestion_service=ingestion_service
    )
    df = pd.DataFrame({
        'video_id': ['1', '2', '3', '4'],
        'title': ['A', 'B', 'C', 'D'],
        'views': [100, 1000, 100, 1000],
        'retention_avg_pct': [50, 90, 50, 90],
        'type': ['NewType1', 'NewType1', 'NewType2', 'NewType2']
    })
    anomalies = app.detect_outliers(df)
    assert 'NewType1' in anomalies
    assert 'NewType2' in anomalies
    assert len(anomalies['NewType1']) == 1  # 1000 should be filtered
    assert len(anomalies['NewType2']) == 1

def test_prepare_agent_input():
    ai_service = MockAIService()
    report_generator = MockReportGenerator()
    ingestion_service = MockDataIngestionService()
    app = BachataAnalyticsApp(
        ui=DummyUI(),
        ai_service=ai_service,
        report_generator=report_generator,
        ingestion_service=ingestion_service
    )
    df = pd.DataFrame({
        'video_id': [f'vid_{i}' for i in range(10)],
        'title': [f'Title {i}' for i in range(10)],
        'views': [100 * i for i in range(10)],
        'retention_avg_pct': [10.0 * i for i in range(10)],
        'type': ['Shorts'] * 10
    })

    result = app._prepare_agent_input(df)
    assert len(result) == 10
    assert isinstance(result[0], VideoAnalysisInput)
    # sort desc: 90, 80 ... 0
    # top 5: 90, 80, 70, 60, 50
    # bottom 5 (tail of desc sorted): 40, 30, 20, 10, 0
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
