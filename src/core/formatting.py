"""
Formatting utilities for user-facing output.
Focuses on converting technical errors into readable messages.
"""
from pydantic import ValidationError

def format_validation_error(e: ValidationError) -> str:
    """
    Formats Pydantic validation errors into a user-friendly bulleted list.

    Args:
        e: The Pydantic ValidationError instance.

    Returns:
        A formatted string suitable for CLI output.
    """
    messages = ["Validation Issues Detected:"]
    for err in e.errors():
        # Convert location tuple to dot notation or arrows
        loc = " -> ".join(str(part) for part in err['loc'])
        msg = err['msg']

        # Clean up technical prefixes from custom validators
        if msg.startswith('Value error, '):
            msg = msg.replace('Value error, ', '')

        messages.append(f" • {loc}: {msg}")

    return "\n".join(messages)
