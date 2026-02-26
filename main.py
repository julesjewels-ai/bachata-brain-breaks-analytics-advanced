"""
Entry point for the Bachata Brain Breaks Analytics Advanced application.
Handles command-line arguments and initializes the core application logic.
"""
import argparse
import sys
import asyncio
from pathlib import Path
from rich.console import Console
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
    FileNotificationService, ConsoleNotificationService, CompositeNotificationService
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

    # Shared Console
    console = Console()

    # Initialize UI
    ui = RichConsoleUI(console=console)

    # Load Configuration
    try:
        config = AppConfig.get_config()
    except ValidationError as e:
        ui.display_error(f"Configuration Error: {e}")
        sys.exit(1)

    # Initialize Notification Service
    notification_service = CompositeNotificationService([
        ConsoleNotificationService(console=console),
        FileNotificationService(log_path=Path(config.notification_log_path))
    ])

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
        ui.display_error(f"Caching initialization failed: {e}. continuing without cache.")
        ai_service = base_ai_service

    # Initialize Visualizer
    visualizer = MatplotlibVisualizer()

    # Initialize Report Generator
    report_generator = ExcelReportGenerator(visualizer=visualizer)

    # Initialize Data Ingestion Service
    data_ingestion_service = SimulationDataIngestionService()

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
    except Exception as e:
        ui.display_error(f"Critical Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
