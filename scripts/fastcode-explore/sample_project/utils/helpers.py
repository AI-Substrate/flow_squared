"""Utility helpers."""


def validate(data):
    """Validate input data."""
    if not data:
        raise ValueError("Empty data")
    return True


def format_output(result):
    """Format a result for display."""
    return str(result)


class Logger:
    def __init__(self, name):
        self.name = name

    def info(self, msg):
        print(f"[{self.name}] {msg}")

    def error(self, msg):
        print(f"[{self.name}] ERROR: {msg}")
