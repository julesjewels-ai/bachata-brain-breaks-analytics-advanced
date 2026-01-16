"""
Formatting utilities for user-facing output.
Handles string manipulation, error message processing, and display formatting.
"""
from pydantic import ValidationError

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
