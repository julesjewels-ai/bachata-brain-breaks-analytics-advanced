"""
Core logic for Bachata Brain Breaks Analytics.
Contains data ingestion, outlier detection, and the Gemini 3 agent simulation.
"""
import logging
from typing import Optional
from pydantic import ValidationError
from src.core.reporting import ExcelReportGenerator
from src.core.config import AppConfig
from src.core.formatting import format_validation_error, prepare_display_dataframe
from src.core.interfaces import UserInterface
from src.core.services import AnalyticsService, GeminiThinkingAgent

# Configure logging
logger = logging.getLogger(__name__)


class BachataAnalyticsApp:
    """
    Main application controller.
    """

    def __init__(self, ui: UserInterface, analytics_service: Optional[AnalyticsService] = None, agent: Optional[GeminiThinkingAgent] = None):
        # Securely load configuration
        self.config = AppConfig.get_config()
        self.analytics_service = analytics_service or AnalyticsService()
        self.agent = agent or GeminiThinkingAgent()
        self.ui = ui

    # Delegate methods for backward compatibility/testing if needed,
    # but ideally we should update tests to not call these directly on the App.
    # I'll rely on updating tests.

    def run(self) -> None:
        """
        Executes the analytics pipeline.
        """
        # 1. Ingest
        self.ui.display_header("Bachata Analytics Dashboard")
        self.ui.display_status("Ingesting channel data...")
        df = self.analytics_service.ingest_data()
        self.ui.display_success(f"Data loaded: {len(df)} records.")

        # 2. Outlier Detection
        anomalies = self.analytics_service.detect_outliers(df)
        for v_type, data in anomalies.items():
            self.ui.display_section(f"Viral Anomalies ({v_type})")
            display_df = prepare_display_dataframe(
                data[['title', 'views', 'retention_avg_pct']])
            self.ui.display_table(display_df)

        # 3. Gemini Analysis (Top/Bottom 5)
        self.ui.display_section("Gemini 3 Agent Analysis")

        try:
            analysis_input = self.analytics_service.prepare_agent_input(df)
        except ValidationError as e:
            logger.error(f"Data validation failed for Gemini Analysis: {e}")
            # Decide whether to abort or skip. Aborting is safer for security.
            self.ui.display_error(format_validation_error(e))
            self.ui.display_error("Aborting analysis for security.")
            return

        strategy = self.agent.analyze_semantics(analysis_input)
        self.ui.display_info(strategy)

        # 4. Generate Excel Report
        self.ui.display_status("Generating Excel Report...")
        try:
            report_gen = ExcelReportGenerator()
            report_gen.generate_excel(
                anomalies, strategy, "bachata_analytics.xlsx")
            self.ui.display_success("Report saved to 'bachata_analytics.xlsx'.")
        except ValueError as e:
            logger.error(f"Failed to generate report: {e}")
            self.ui.display_error(f"Error generating report: {e}")

        self.ui.display_success("Dashboard update complete.")
