import logging
import random
from typing import List, Dict, Optional
import pandas as pd
from pydantic import ValidationError

from src.core.models import VideoAnalysisInput
from src.core.reporting import ExcelReportGenerator
from src.core.config import AppConfig

logger = logging.getLogger(__name__)

class GeminiThinkingAgent:
    """
    Simulates Gemini 3 'Thinking Mode' to analyze semantic patterns.
    """
    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Analyzes titles and thumbnails (metadata) to find conversion patterns.
        Now strictly typed for security.
        """
        if not videos:
            return "No data to analyze."

        # Simulated 'Thinking Mode' logic
        return (
            "[Gemini 3 Thinking Mode] Analysis Complete:\n"
            "1. Pattern Identification: High-retention videos often use 'sensual' or 'footwork' keywords.\n"
            "2. Strategy: Use high-contrast thumbnails with dynamic poses.\n"
            "3. Recommendation: Rename lower performers to include 'Step-by-Step' hook."
        )

class AnalyticsService:
    """
    Service layer for Analytics operations.
    Decoupled from UI and HTTP concerns.
    """
    def __init__(self):
        self.config = AppConfig.get_config()
        self.agent = GeminiThinkingAgent()

    def ingest_data(self) -> pd.DataFrame:
        """
        Simulates ingesting channel data (Shorts and Long-form).
        In a real app, this would connect to YouTube Analytics API.
        """
        # Generate mock data
        titles = [
            'Basic Step Tutorial', 'Sensual Bachata Demo', 'Viral Short Dance',
            'Advanced Footwork', 'Partner Connection Secrets', 'Musicality 101',
            'Funny Bloopers', 'Festival Vlog', 'Dip Technique', 'Spin Drill'
        ] * 2

        raw_data = []
        for i in range(1, 21):
            raw_data.append({
                'video_id': f'vid_{i}',
                'title': titles[i-1],
                'views': random.randint(500, 500000),
                'retention_avg_pct': random.uniform(20.0, 95.0),
                'type': 'Long' if i % 3 != 0 else 'Shorts'
            })

        # Validate data using VideoAnalysisInput (Ensures type safety & security)
        validated_data = [VideoAnalysisInput(**record).model_dump() for record in raw_data]

        return pd.DataFrame(validated_data)

    def detect_outliers(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        Implements statistical outlier detection for viral anomalies.
        """
        results: Dict[str, pd.DataFrame] = {}
        # Ensure we have data
        if df.empty:
            return results

        for v_type, group in df.groupby('type'):
            # Simple statistical outlier detection using Quantiles (Viral > 90th percentile)
            threshold = group['views'].quantile(0.90)
            results[str(v_type)] = group[group['views'] > threshold]

        return results

    def _prepare_agent_input(self, df: pd.DataFrame) -> List[VideoAnalysisInput]:
        """
        Selects top/bottom performing videos and validates them for the agent.
        """
        if df.empty:
            return []

        sorted_df = df.sort_values(by='retention_avg_pct', ascending=False)
        records = pd.concat([sorted_df.head(5), sorted_df.tail(5)]).to_dict('records')

        return [VideoAnalysisInput(**{str(k): v for k, v in record.items()}) for record in records]

    def analyze_semantics(self, df: pd.DataFrame) -> str:
        """
        Prepares data and runs Gemini Agent analysis.
        """
        try:
            analysis_input = self._prepare_agent_input(df)
            return self.agent.analyze_semantics(analysis_input)
        except ValidationError as e:
            logger.error(f"Data validation failed for Gemini Analysis: {e}")
            raise

    def generate_report(self, anomalies: Dict[str, pd.DataFrame], strategy: str, filepath: str = "bachata_analytics.xlsx") -> str:
        """
        Generates the Excel report.
        """
        report_gen = ExcelReportGenerator()
        report_gen.generate_excel(anomalies, strategy, filepath)
        return filepath
