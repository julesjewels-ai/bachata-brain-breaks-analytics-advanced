"""
Entry point for the Bachata Brain Breaks Analytics Advanced application.
Handles command-line arguments and initializes the core application logic.
"""
import argparse
import sys
from src.core.app import BachataAnalyticsApp
from src.core.ui import RichConsoleUI

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bachata Brain Breaks Analytics: Audience & Retention Dashboard"
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

    ui.display_status("Initializing Analytics Dashboard...")
    app = BachataAnalyticsApp(ui=ui)
    try:
        app.run()
    except Exception as e:
        ui.display_error(f"Critical Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()