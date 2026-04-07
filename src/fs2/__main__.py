"""Entry point for python -m fs2."""

import os
import sys

# Ensure UTF-8 mode on Windows (prevents cp1252 encoding crashes and Rich garbling).
# PYTHONUTF8 must be set before Python starts to affect default encodings,
# but setting it here covers subprocesses. For the current process, we
# reconfigure stdout/stderr directly.
os.environ.setdefault("PYTHONUTF8", "1")
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

from fs2.cli.main import app

if __name__ == "__main__":
    app()
