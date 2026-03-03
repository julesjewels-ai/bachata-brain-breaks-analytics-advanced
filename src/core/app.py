"""
Core logic for Bachata Brain Breaks Analytics.
Contains data ingestion, outlier detection, and the Gemini 3 agent simulation.
"""

import logging
from typing import List, Dict, Optional
import pandas as pd
from pydantic import ValidationError
from src.core.config import AppConfig
from src.core.formatting import (
    format_validation_error,
    prepare_display_dataframe,
)
from src.core.interfaces import (
    UserInterface,
    AIService,
    ReportGenerator,
    DataIngestionService,
    NotificationService,
)
from src.core.models import VideoAnalysisInput, NotificationEvent

# Configure logging
logger = logging.getLogger(__name__)


class BachataAnalyticsApp:
    """
    Main application controller.
    """

    def __init__(
        self,
        ui: UserInterface,
        ai_service: AIService,
        report_generator: ReportGenerator,
        data_ingestion_service: DataIngestionService,
        notification_service: NotificationService,
    ):
        # Securely load configuration
        self.config = AppConfig.get_config()
        self.ai_service = ai_service
        self.ui = ui
        self.report_generator = report_generator
        self.data_ingestion_service = data_ingestion_service
        self.notification_service = notification_service

    async def ingest_data(self) -> pd.DataFrame:
        """
        Ingests channel data using the injected service.
        """
        with self.ui.loading("Ingesting channel data..."):
            return await self.data_ingestion_service.ingest_data()

    def detect_outliers(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        Implements statistical outlier detection for viral anomalies.
        """
        results = {}
        for v_type, group in df.groupby("type"):
            # Simple statistical outlier detection using Quantiles
            # (Viral > 90th percentile)
            threshold = group["views"].quantile(0.90)
            results[str(v_type)] = group[group["views"] > threshold]

        return results

    def _prepare_agent_input(
        self, df: pd.DataFrame
    ) -> List[VideoAnalysisInput]:
        """
        Selects top/bottom performing videos and validates them for the agent.
        """
        sorted_df = df.sort_values(by="retention_avg_pct", ascending=False)
        records = pd.concat([sorted_df.head(5), sorted_df.tail(5)]).to_dict(
            "records"
        )

        return [VideoAnalysisInput(**record) for record in records]

    def _display_anomalies(self, anomalies: Dict[str, pd.DataFrame]) -> None:
        """Renders outlier tables for each video type."""
        for v_type, data in anomalies.items():
            self.ui.display_section(f"Viral Anomalies ({v_type})")
            display_df = prepare_display_dataframe(
                data[["title", "views", "retention_avg_pct"]]
            )
            self.ui.display_table(display_df)

    async def _stream_with_capture(self, stream, first_chunk) -> str:
        """
        Wraps an async generator to capture all yielded chunks into a
        single concatenated string while forwarding them to the UI.
        """
        captured: List[str] = []

        async def _wrapper():
            if first_chunk is not None:
                captured.append(first_chunk)
                yield first_chunk
            try:
                async for chunk in stream:
                    captured.append(chunk)
                    yield chunk
            except Exception as e:
                yield f"\n[error] Stream interrupted: {e}[/error]\n"

        await self.ui.display_stream(_wrapper())
        return "".join(captured)

    async def _run_gemini_analysis(self, df: pd.DataFrame) -> Optional[str]:
        """
        Validates data, initializes the Gemini stream, and returns
        the full strategy text. Returns None on failure.
        """
        self.ui.display_section("Gemini 3 Agent Analysis")

        try:
            analysis_input = self._prepare_agent_input(df)
        except ValidationError as e:
            logger.error(f"Data validation failed for Gemini Analysis: {e}")
            error_msg = format_validation_error(e)
            self.notification_service.notify(
                NotificationEvent(
                    title="Validation Error",
                    message=f"Aborting analysis: {error_msg}",
                    level="error",
                )
            )
            return None

        stream = self.ai_service.analyze_stream(analysis_input)

        first_chunk = None
        try:
            with self.ui.loading("Initializing Gemini 3 Stream..."):
                first_chunk = await stream.__anext__()
        except StopAsyncIteration:
            pass
        except Exception as e:
            logger.error(f"Stream initialization failed: {e}")
            self.ui.display_error(f"Failed to generate analysis: {e}")
            return None

        return await self._stream_with_capture(stream, first_chunk)

    def _generate_report(
        self, anomalies: Dict[str, pd.DataFrame], strategy: str
    ) -> None:
        """Generates the Excel report and notifies the user."""
        try:
            with self.ui.loading("Generating Excel Report..."):
                self.report_generator.generate_report(
                    anomalies, strategy, "bachata_analytics.xlsx"
                )
            self.notification_service.notify(
                NotificationEvent(
                    title="Report Generation",
                    message="Report saved to 'bachata_analytics.xlsx'.",
                    level="success",
                )
            )
        except ValueError as e:
            logger.error(f"Failed to generate report: {e}")
            self.notification_service.notify(
                NotificationEvent(
                    title="Report Generation Error",
                    message=str(e),
                    level="error",
                )
            )

    async def run(self) -> None:
        """Executes the full analytics pipeline."""
        self.ui.display_header("Bachata Analytics Dashboard")

        df = await self.ingest_data()
        self.notification_service.notify(
            NotificationEvent(
                title="Ingestion",
                message=f"Data loaded: {len(df)} records.",
                level="success",
            )
        )

        anomalies = self.detect_outliers(df)
        self._display_anomalies(anomalies)

        strategy = await self._run_gemini_analysis(df)
        if strategy is None:
            return

        self._generate_report(anomalies, strategy)

        self.notification_service.notify(
            NotificationEvent(
                title="Complete",
                message="Dashboard update complete.",
                level="success",
            )
        )
