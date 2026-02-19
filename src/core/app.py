"""
Core logic for Bachata Brain Breaks Analytics.
Contains data ingestion, outlier detection, and the Gemini 3 agent simulation.
"""
import random
import logging
from typing import List, Dict, Optional
import pandas as pd
from pydantic import ValidationError
from src.core.config import AppConfig
from src.core.formatting import format_validation_error, prepare_display_dataframe
from src.core.interfaces import UserInterface, AIService, ReportGenerator
from src.core.models import VideoAnalysisInput

# Configure logging
logger = logging.getLogger(__name__)

class BachataAnalyticsApp:
    """
    Main application controller.
    """
    def __init__(self, ui: UserInterface, ai_service: AIService, report_generator: ReportGenerator):
        # Securely load configuration
        self.config = AppConfig.get_config()
        self.ai_service = ai_service
        self.ui = ui
        self.report_generator = report_generator

    def ingest_data(self) -> pd.DataFrame:
        """
        Simulates ingesting channel data (Shorts and Long-form).
        In a real app, this would connect to YouTube Analytics API.
        """
        with self.ui.loading("Ingesting channel data..."):
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
        results = {}
        for v_type, group in df.groupby('type'):
            # Simple statistical outlier detection using Quantiles (Viral > 90th percentile)
            threshold = group['views'].quantile(0.90)
            results[str(v_type)] = group[group['views'] > threshold]

        return results

    def _display_anomalies(self, anomalies: Dict[str, pd.DataFrame]) -> None:
        """
        Displays the viral anomalies for each video type.
        """
        for v_type, data in anomalies.items():
            self.ui.display_section(f"Viral Anomalies ({v_type})")
            display_df = prepare_display_dataframe(data[['title', 'views', 'retention_avg_pct']])
            self.ui.display_table(display_df)

    def _prepare_agent_input(self, df: pd.DataFrame) -> List[VideoAnalysisInput]:
        """
        Selects top/bottom performing videos and validates them for the agent.
        """
        sorted_df = df.sort_values(by='retention_avg_pct', ascending=False)
        records = pd.concat([sorted_df.head(5), sorted_df.tail(5)]).to_dict('records')

        return [VideoAnalysisInput(**{str(k): v for k, v in record.items()}) for record in records]

    async def _perform_analysis(self, df: pd.DataFrame) -> Optional[str]:
        """
        Performs the Gemini Agent analysis on the data.
        """
        self.ui.display_section("Gemini 3 Agent Analysis")
        
        try:
            analysis_input = self._prepare_agent_input(df)
        except ValidationError as e:
            logger.error(f"Data validation failed for Gemini Analysis: {e}")
            self.ui.display_error(format_validation_error(e))
            self.ui.display_error("Aborting analysis for security.")
            return None

        strategy_chunks: List[str] = []
        with self.ui.loading("Initializing Gemini 3 Stream..."):
            stream = self.ai_service.analyze_stream(analysis_input)

        async def _capture_wrapper(gen):
            async for chunk in gen:
                strategy_chunks.append(chunk)
                yield chunk

        await self.ui.display_stream(_capture_wrapper(stream))
        return "".join(strategy_chunks)

    def _generate_report(self, anomalies: Dict[str, pd.DataFrame], strategy: str) -> None:
        """
        Generates the Excel report.
        """
        try:
            with self.ui.loading("Generating Excel Report..."):
                self.report_generator.generate_report(anomalies, strategy, "bachata_analytics.xlsx")
            self.ui.display_success("Report saved to 'bachata_analytics.xlsx'.")
        except ValueError as e:
            logger.error(f"Failed to generate report: {e}")
            self.ui.display_error(f"Error generating report: {e}")

    async def run(self) -> None:
        """
        Executes the analytics pipeline.
        """
        # 1. Ingest
        self.ui.display_header("Bachata Analytics Dashboard")
        df = self.ingest_data()
        self.ui.display_success(f"Data loaded: {len(df)} records.")

        # 2. Outlier Detection
        anomalies = self.detect_outliers(df)
        self._display_anomalies(anomalies)

        # 3. Gemini Analysis (Top/Bottom 5)
        strategy = await self._perform_analysis(df)
        if strategy is None:
            return

        # 4. Generate Excel Report
        self._generate_report(anomalies, strategy)

        self.ui.display_success("Dashboard update complete.")
