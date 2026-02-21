"""
Core logic for Bachata Brain Breaks Analytics.
Contains data ingestion, outlier detection, and the Gemini 3 agent simulation.
"""
import logging
from typing import List, Dict
import pandas as pd
from pydantic import ValidationError
from src.core.config import AppConfig
from src.core.formatting import format_validation_error, prepare_display_dataframe
from src.core.interfaces import UserInterface, AIService, ReportGenerator, DataIngestionService
from src.core.models import VideoAnalysisInput

# Configure logging
logger = logging.getLogger(__name__)

class BachataAnalyticsApp:
    """
    Main application controller.
    """
    def __init__(self, ui: UserInterface, ai_service: AIService, report_generator: ReportGenerator, data_ingestion_service: DataIngestionService):
        # Securely load configuration
        self.config = AppConfig.get_config()
        self.ai_service = ai_service
        self.ui = ui
        self.report_generator = report_generator
        self.data_ingestion_service = data_ingestion_service

    def ingest_data(self) -> pd.DataFrame:
        """
        Ingests channel data using the configured service.
        """
        with self.ui.loading("Ingesting channel data..."):
            return self.data_ingestion_service.ingest_data()

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

    def _prepare_agent_input(self, df: pd.DataFrame) -> List[VideoAnalysisInput]:
        """
        Selects top/bottom performing videos and validates them for the agent.
        """
        sorted_df = df.sort_values(by='retention_avg_pct', ascending=False)
        records = pd.concat([sorted_df.head(5), sorted_df.tail(5)]).to_dict('records')

        return [VideoAnalysisInput(**{str(k): v for k, v in record.items()}) for record in records]

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
        for v_type, data in anomalies.items():
            self.ui.display_section(f"Viral Anomalies ({v_type})")
            display_df = prepare_display_dataframe(data[['title', 'views', 'retention_avg_pct']])
            self.ui.display_table(display_df)

        # 3. Gemini Analysis (Top/Bottom 5)
        self.ui.display_section("Gemini 3 Agent Analysis")
        
        try:
            analysis_input = self._prepare_agent_input(df)
        except ValidationError as e:
            logger.error(f"Data validation failed for Gemini Analysis: {e}")
            # Decide whether to abort or skip. Aborting is safer for security.
            self.ui.display_error(format_validation_error(e))
            self.ui.display_error("Aborting analysis for security.")
            return

        # Stream Strategy
        strategy_chunks: List[str] = []
        with self.ui.loading("Initializing Gemini 3 Stream..."):
            stream = self.ai_service.analyze_stream(analysis_input)

        async def _capture_wrapper(gen):
            async for chunk in gen:
                strategy_chunks.append(chunk)
                yield chunk

        await self.ui.display_stream(_capture_wrapper(stream))
        strategy = "".join(strategy_chunks)

        # 4. Generate Excel Report
        try:
            with self.ui.loading("Generating Excel Report..."):
                self.report_generator.generate_report(anomalies, strategy, "bachata_analytics.xlsx")
            self.ui.display_success("Report saved to 'bachata_analytics.xlsx'.")
        except ValueError as e:
            logger.error(f"Failed to generate report: {e}")
            self.ui.display_error(f"Error generating report: {e}")

        self.ui.display_success("Dashboard update complete.")
