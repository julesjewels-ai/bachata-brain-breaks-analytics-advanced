"""
Entry point for the Bachata Brain Breaks Analytics Advanced application.
Handles command-line arguments and initializes the core application logic.
"""
import argparse
import sys
import asyncio
from pydantic import ValidationError
from src.core.app import BachataAnalyticsApp
from src.core.config import AppConfig
from src.core.ui import RichConsoleUI
from src.core.formatting import format_validation_error
from src.core.ai import GeminiThinkingAgent
from src.core.caching import CachedAIService, FileCacheBackend
from src.core.reporting import ExcelReportGenerator
from src.core.visualization import MatplotlibVisualizer
from src.core.ingestion import SimulationDataIngestionService
from src.core.notifications import (
    ConsoleNotificationService, FileNotificationService,
    CompositeNotificationService
)
from src.core.metrics import (
    FileMetricsRepository, StandardMetricsService,
    MetricsDataIngestionService, MetricsReportGenerator
)

def main() -> None:
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
    args = parser.parse_args()

    if args.version:
        print("Bachata Brain Breaks Analytics v1.0.0")
        sys.exit(0)

    # Initialize UI
    ui = RichConsoleUI()

    # Load Configuration
    try:
        config = AppConfig.get_config()
    except ValidationError as e:
        ui.display_error(f"Configuration Error: {e}")
        sys.exit(1)

    # Initialize AI Service
    base_ai_service = GeminiThinkingAgent()

    # Initialize Caching Layer
    try:
        cache_backend = FileCacheBackend(cache_dir=config.cache_dir)
        ai_service = CachedAIService(
            ai_service=base_ai_service,
            cache_backend=cache_backend
        )
        ui.display_status(f"Caching enabled at: {config.cache_dir}")
    except Exception as e:
        ui.display_error(
            f"Caching initialization failed: {e}. continuing without cache."
        )
        ai_service = base_ai_service  # type: ignore

    # Initialize Metrics Service
    metrics_repo = FileMetricsRepository("metrics.jsonl")
    metrics_service = StandardMetricsService(metrics_repo)

    # Initialize Visualizer
    visualizer = MatplotlibVisualizer()

    # Initialize Report Generator (Decorated)
    base_report_generator = ExcelReportGenerator(visualizer=visualizer)
    report_generator = MetricsReportGenerator(
        inner_generator=base_report_generator,
        metrics_service=metrics_service
    )

    # Initialize Data Ingestion Service (Decorated)
    base_data_ingestion_service = SimulationDataIngestionService()
    data_ingestion_service = MetricsDataIngestionService(
        inner_service=base_data_ingestion_service,
        metrics_service=metrics_service
    )

    # Initialize Notification Service
    console_notifier = ConsoleNotificationService(ui)
    file_notifier = FileNotificationService("notifications.jsonl")
    notification_service = CompositeNotificationService(
        [console_notifier, file_notifier]
    )

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

        # Export final metrics
        metrics_service.export("metrics_export.json")
        ui.display_success("Metrics exported to 'metrics_export.json'")
    except ValidationError as e:
        ui.display_error(format_validation_error(e))
        sys.exit(1)
    except Exception as e:
        ui.display_error(f"Critical Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
