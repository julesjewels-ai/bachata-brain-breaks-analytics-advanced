"""
Entry point for the Bachata Brain Breaks Analytics Advanced application.
Handles command-line arguments and initializes the core application logic.
"""
import argparse
import sys
from src.core.app import BachataAnalyticsApp
from src.interfaces.cli import RichConsole

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bachata Brain Breaks Analytics: Audience & Retention Dashboard"
    )
    parser.add_argument(
        "--version", 
        action="store_true", 
        help="Show application version"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run analysis without executing external API calls"
    )

    args = parser.parse_args()
    console = RichConsole()

    if args.version:
        console.print_welcome()
        sys.exit(0)

    console.print_info("Initializing Analytics Dashboard...")
    app = BachataAnalyticsApp(console=console, dry_run=args.dry_run)
    try:
        app.run()
    except Exception as e:
        console.print_error(f"Critical Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()