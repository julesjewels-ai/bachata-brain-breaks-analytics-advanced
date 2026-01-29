"""
Core logic for Bachata Brain Breaks Analytics.
Contains data ingestion, outlier detection, and the Gemini 3 agent simulation.
"""
import logging
from typing import Dict
import pandas as pd
from pydantic import ValidationError

from src.core.services import AnalyticsService
from src.core.models import VideoAnalysisInput
from src.core.formatting import format_validation_error, prepare_display_dataframe
from src.core.interfaces import UserInterface

# Configure logging
logger = logging.getLogger(__name__)

from typing import Optional

class BachataAnalyticsApp:
    """
    Main application controller.
    """
    def __init__(self, ui: UserInterface, service: Optional[AnalyticsService] = None):
        self.ui = ui
        self.service = service or AnalyticsService()

    def run(self) -> None:
        """
        Executes the analytics pipeline.
        """
        # 1. Ingest
        self.ui.display_header("Bachata Analytics Dashboard")
        self.ui.display_status("Ingesting channel data...")

        df = self.service.ingest_data()
        self.ui.display_success(f"Data loaded: {len(df)} records.")

        # 2. Outlier Detection
        anomalies = self.service.detect_outliers(df)
        for v_type, data in anomalies.items():
            self.ui.display_section(f"Viral Anomalies ({v_type})")
            display_df = prepare_display_dataframe(data[['title', 'views', 'retention_avg_pct']])
            self.ui.display_table(display_df)

        # 3. Gemini Analysis
        self.ui.display_section("Gemini 3 Agent Analysis")
        
        try:
            strategy = self.service.analyze_semantics(df)
            self.ui.display_info(strategy)
        except ValidationError as e:
            self.ui.display_error(format_validation_error(e))
            self.ui.display_error("Aborting analysis for security.")
            return

        # 4. Generate Excel Report
        self.ui.display_status("Generating Excel Report...")
        try:
            filepath = self.service.generate_report(anomalies, strategy, "bachata_analytics.xlsx")
            self.ui.display_success(f"Report saved to '{filepath}'.")
        except ValueError as e:
            logger.error(f"Failed to generate report: {e}")
            self.ui.display_error(f"Error generating report: {e}")

        self.ui.display_success("Dashboard update complete.")
