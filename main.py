"""
Entry point for the Bachata Brain Breaks Analytics Advanced application.
Handles command-line arguments and initializes the core application logic.
"""
import argparse
import asyncio
import sys

from dotenv import load_dotenv

# Load environment variables BEFORE any imports that use them
load_dotenv()

from pydantic import ValidationError

from src.core.ai import GeminiThinkingAgent
from src.core.app import BachataAnalyticsApp
from src.core.caching import CachedAIService, FileCacheBackend
from src.core.config import AppConfig
from src.core.formatting import format_validation_error
from src.core.ingestion import SimulationDataIngestionService
from src.core.metrics import (
    FileMetricsRepository,
    MetricsDataIngestionService,
    MetricsReportGenerator,
)
from src.core.notifications import (
    CompositeNotificationService,
    ConsoleNotificationService,
    FileNotificationService,
)
from src.core.reporting import ExcelReportGenerator
from src.core.ui import RichConsoleUI
from src.core.visualization import MatplotlibVisualizer
from src.core.youtube import YouTubeAPIClient
from src.core.youtube_ingestion import YouTubeIngestionService


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Bachata Brain Breaks Analytics: Audience & Retention Dashboard"
        )
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show application version"
    )
    parser.add_argument(
        "--real-data",
        action="store_true",
        help="Use real data from YouTube API instead of simulation"
    )
    parser.add_argument(
        "--channel-id",
        type=str,
        help="YouTube Channel ID to fetch data for "
             "(defaults to YOUTUBE_CHANNEL_ID config if not provided)"
    )
    args = parser.parse_args()

    if args.version:
        print("Bachata Brain Breaks Analytics v1.0.0")
        sys.exit(0)

    return args


def _initialize_ai_service(
    config: AppConfig, ui: RichConsoleUI
) -> CachedAIService | GeminiThinkingAgent:
    base_ai_service = GeminiThinkingAgent()
    try:
        cache_backend = FileCacheBackend(cache_dir=config.cache_dir)
        ai_service = CachedAIService(
            ai_service=base_ai_service,
            cache_backend=cache_backend
        )
        ui.display_status(f"Caching enabled at: {config.cache_dir}")
        return ai_service
    except Exception as e:  # noqa: BLE001
        ui.display_error(
            f"Caching initialization failed: {e}. continuing without cache."
        )
        return base_ai_service


def _initialize_reporting(
    metrics_repo: FileMetricsRepository,
) -> MetricsReportGenerator:
    """Creates the report generation stack with visualization."""
    visualizer = MatplotlibVisualizer()
    base_report_generator = ExcelReportGenerator(visualizer=visualizer)
    return MetricsReportGenerator(
        inner=base_report_generator, repository=metrics_repo
    )


def _initialize_notifications(
    ui: RichConsoleUI,
) -> CompositeNotificationService:
    """Creates the notification service stack."""
    return CompositeNotificationService([
        ConsoleNotificationService(ui),
        FileNotificationService("notifications.jsonl"),
    ])


def _initialize_data_ingestion(
    args: argparse.Namespace,
    config: AppConfig,
    ui: RichConsoleUI,
    metrics_repo: FileMetricsRepository
) -> MetricsDataIngestionService:
    if args.real_data:
        target_channel_id = args.channel_id
        if not target_channel_id:
            try:
                target_channel_id = config.get_youtube_channel_id()
            except ValueError:
                ui.display_error(
                    "--channel-id is required when using --real-data "
                    "unless YOUTUBE_CHANNEL_ID is set in .env"
                )
                sys.exit(1)

        try:
            youtube_client = YouTubeAPIClient(config=config)
            base_data_ingestion_service_yt = YouTubeIngestionService(
                youtube_client=youtube_client,
                target_channel_id=target_channel_id
            )
            data_ingestion_service = MetricsDataIngestionService(
                inner=base_data_ingestion_service_yt, repository=metrics_repo
            )
            ui.display_status(
                f"Using REAL data integration for channel: "
                f"{target_channel_id}"
            )
            return data_ingestion_service
        except Exception as e:  # noqa: BLE001
            ui.display_error(f"Failed to initialize YouTube service: {e}")
            sys.exit(1)
    else:
        ui.display_status(
            "\n[NOTICE] The '--real-data' flag was not provided. "
            "Defaulting to simulation mode."
        )
        ui.display_status(
            "[NOTICE] To use live YouTube Data API, run: "
            "python main.py --real-data\n"
        )
        base_data_ingestion_service_sim = SimulationDataIngestionService()
        data_ingestion_service = MetricsDataIngestionService(
            inner=base_data_ingestion_service_sim, repository=metrics_repo
        )
        ui.display_status("Using SIMULATED data ingestion")
        return data_ingestion_service


def main() -> None:
    args = _parse_arguments()

    # Initialize UI
    ui = RichConsoleUI()

    # Load Configuration
    try:
        config = AppConfig.get_config()
    except ValidationError as e:
        ui.display_error(f"Configuration Error: {e}")
        sys.exit(1)

    # Initialize services
    ai_service = _initialize_ai_service(config, ui)
    metrics_repo = FileMetricsRepository("telemetry_metrics.jsonl")
    report_generator = _initialize_reporting(metrics_repo)
    data_ingestion_service = _initialize_data_ingestion(
        args, config, ui, metrics_repo
    )
    notification_service = _initialize_notifications(ui)

    ui.display_status("Initializing Analytics Dashboard...")
    try:
        app = BachataAnalyticsApp(
            ui=ui,
            ai_service=ai_service,
            report_generator=report_generator,
            data_ingestion_service=data_ingestion_service,
            notification_service=notification_service
        )
        asyncio.run(app.run())
    except ValidationError as e:
        ui.display_error(format_validation_error(e))
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        ui.display_error(f"Critical Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
