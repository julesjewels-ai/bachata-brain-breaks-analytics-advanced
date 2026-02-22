"""
Entry point for the Bachata Brain Breaks Analytics Advanced application.
Handles command-line arguments and initializes the core application logic.
"""
import argparse
import sys
import asyncio
from pydantic import ValidationError
from src.core.app import BachataAnalyticsApp
from src.core.ui import RichConsoleUI
from src.core.formatting import format_validation_error
from src.core.ai import GeminiThinkingAgent
from src.core.ingestion import SimulationDataIngestionService
from src.core.reporting import ExcelReportGenerator
from src.core.visualization import MatplotlibVisualizer


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

    # Initialize AI Service
    ai_service = GeminiThinkingAgent()

    # Initialize Visualizer
    visualizer = MatplotlibVisualizer()

    # Initialize Report Generator
    report_generator = ExcelReportGenerator(visualizer=visualizer)

    # Initialize Data Ingestion Service
    data_ingestion_service = SimulationDataIngestionService(ui=ui)

    ui.display_status("Initializing Analytics Dashboard...")
    try:
        app = BachataAnalyticsApp(
            ui=ui,
            ai_service=ai_service,
            report_generator=report_generator,
            data_ingestion_service=data_ingestion_service
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
