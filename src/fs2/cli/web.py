"""Web CLI command for fs2.

Launches the Streamlit-based web UI for configuring fs2.

Usage:
    fs2 web                    # Launch on localhost:8501, open browser
    fs2 web --port 9000        # Custom port
    fs2 web --host 0.0.0.0     # Bind to all interfaces
    fs2 web --no-browser       # Don't open browser automatically

The web UI provides:
- Configuration inspection and editing
- Graph browsing
- Doctor diagnostics (future phases)
"""

import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Annotated

import typer


def web(
    port: Annotated[
        int,
        typer.Option(
            "--port",
            "-p",
            help="Port to run the web server on",
        ),
    ] = 8501,
    host: Annotated[
        str,
        typer.Option(
            "--host",
            "-h",
            help="Host address to bind to",
        ),
    ] = "localhost",
    no_browser: Annotated[
        bool,
        typer.Option(
            "--no-browser",
            help="Don't open browser automatically",
        ),
    ] = False,
) -> None:
    """Launch the fs2 web UI.

    Starts a Streamlit server hosting the fs2 configuration and
    browsing interface. The server runs until interrupted (Ctrl+C).

    Examples:
        fs2 web                    # Default: localhost:8501
        fs2 web --port 9000        # Custom port
        fs2 web --no-browser       # Headless mode for servers
    """
    # Find app.py location (sibling to this module's parent)
    app_path = Path(__file__).parent.parent / "web" / "app.py"

    if not app_path.exists():
        typer.echo(f"Error: Web app not found at {app_path}", err=True)
        raise typer.Exit(1)

    # Build Streamlit command
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(port),
        "--server.address",
        host,
    ]

    # Always run headless to skip email prompt, handle browser ourselves
    cmd.extend(["--server.headless", "true"])

    # Disable telemetry
    cmd.extend(["--browser.gatherUsageStats", "false"])

    # Set up environment to skip onboarding prompt
    env = os.environ.copy()
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    # Open browser manually after a short delay (if not --no-browser)
    def open_browser() -> None:
        time.sleep(2)  # Wait for server to start
        webbrowser.open(f"http://{host}:{port}")

    # Launch Streamlit subprocess
    try:
        process = subprocess.Popen(cmd, env=env)

        if not no_browser:
            browser_thread = threading.Thread(target=open_browser, daemon=True)
            browser_thread.start()

        process.wait()
    except KeyboardInterrupt:
        typer.echo("\nShutting down web server...")
        process.terminate()
        process.wait()
    except FileNotFoundError:
        typer.echo(
            "Error: Streamlit not installed. Install with: pip install streamlit",
            err=True,
        )
        raise typer.Exit(1) from None
