"""Utility functions for cross-file call detection."""

from datetime import datetime


def format_date(dt: datetime | None = None) -> str:
    """Format a datetime for display.

    LSP should find references to this function from app.py.

    Line 8: function definition
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d")  # Line 14


def validate_string(value: str) -> bool:
    """Validate a string is not empty.

    LSP should find references from auth.py.

    Line 18: function definition
    """
    return len(value.strip()) > 0  # Line 24
