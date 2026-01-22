"""
Entry point for the Bachata Brain Breaks Analytics Advanced application.
Handles command-line arguments and initializes the core application logic.
"""
import argparse
import sys
from pydantic import ValidationError
from src.core.app import BachataAnalyticsApp
from src.core.formatting import format_validation_error

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

    print("Initializing Analytics Dashboard...")
    try:
        app = BachataAnalyticsApp()
        app.run()
    except ValidationError as e:
        print(format_validation_error(e), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Critical Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()