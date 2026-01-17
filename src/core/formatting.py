"""
Formatting utilities for user-facing output.
Handles string manipulation, error message processing, and display formatting.
"""
from pydantic import ValidationError
import pandas as pd

def format_validation_error(e: ValidationError) -> str:
    """
    Formats Pydantic ValidationErrors into a user-friendly bulleted list.

    Args:
        e: The ValidationError exception caught from Pydantic.

    Returns:
        A formatted string with a header and bullet points for each error.
    """
    messages = []
    for error in e.errors():
        # Get the field name, defaulting to 'root' if empty
        loc = error.get("loc", ())
        field = ".".join(str(x) for x in loc) if loc else "root"

        msg = error.get("msg", "Unknown error")

        # Clean up common Pydantic prefixes for cleaner UX
        if msg.startswith("Value error, "):
            msg = msg.replace("Value error, ", "")

        messages.append(f"• {field}: {msg}")

    return "Validation Error:\n" + "\n".join(messages)

def format_dataframe_for_display(df: pd.DataFrame) -> str:
    """
    Formats a DataFrame for CLI display with human-readable numbers.

    Args:
        df: The pandas DataFrame to format.

    Returns:
        A formatted string representation of the DataFrame.
    """
    if df.empty:
        return "No data available."

    display_df = df.copy()

    # Format Views (Comma separated)
    if 'views' in display_df.columns:
        display_df['views'] = display_df['views'].apply(lambda x: f"{x:,.0f}")

    # Format Retention (Percentage)
    if 'retention_avg_pct' in display_df.columns:
        display_df['retention_avg_pct'] = display_df['retention_avg_pct'].apply(lambda x: f"{x:.1f}%")

    # Rename columns for display
    display_df = display_df.rename(columns={
        'title': 'Video Title',
        'views': 'Views',
        'retention_avg_pct': 'Retention',
        'video_id': 'ID',
        'type': 'Type'
    })

    return display_df.to_string(index=False)
