"""
Entry point for the Bachata Brain Breaks Analytics Advanced application.
Handles command-line arguments and initializes the core application logic.
"""
import argparse
import sys
from src.core.app import BachataAnalyticsApp

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

    if args.version:
        print("Bachata Brain Breaks Analytics v1.0.0")
        sys.exit(0)

    print("Initializing Analytics Dashboard...")
    app = BachataAnalyticsApp(dry_run=args.dry_run)
    try:
        app.run()
    except Exception as e:
        print(f"Critical Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()