"""fs2 watch command implementation.

Monitors directories for file changes and automatically triggers scans.
Uses WatchService for the core watch loop with queue-one semantics.

Per spec:
- AC1: Basic watch triggers scan on file change
- AC2: Queue-one semantics (multiple changes = one queued scan)
- AC7: Graceful shutdown on Ctrl+C
- AC8: Scan argument pass-through (--no-embeddings, --verbose)
- AC11: Startup information displayed
- AC12: Initial scan on startup

Per Clean Architecture:
- CLI layer creates adapters and passes to service
- Uses ConsoleAdapter ABC for all console output
"""

import asyncio
import logging
import shutil
import signal
import sys
from pathlib import Path
from typing import Annotated

import typer

from fs2.config.exceptions import MissingConfigurationError
from fs2.config.objects import ScanConfig, WatchConfig
from fs2.config.service import FS2ConfigurationService
from fs2.core.adapters import RichConsoleAdapter
from fs2.core.adapters.console_adapter import ConsoleAdapter
from fs2.core.adapters.file_watcher_adapter_watchfiles import WatchfilesAdapter
from fs2.core.services.watch_service import WatchService

logger = logging.getLogger("fs2.cli.watch")


class SubprocessScanRunner:
    """Production scan runner using subprocess isolation.

    Runs `fs2 scan` as a subprocess to:
    - Isolate memory (subprocess can be killed if it hangs)
    - Allow hot-reload of code changes
    - Prevent watcher memory growth from repeated scans
    - Support configurable timeout per DYK-2

    Per DYK-2: No timeout on initial scan; subsequent scans have configurable timeout.
    """

    def __init__(
        self,
        console: ConsoleAdapter,
        scan_args: list[str] | None = None,
        timeout_seconds: int | None = None,
    ):
        """Initialize runner.

        Args:
            console: Console adapter for output.
            scan_args: Additional arguments to pass to scan command.
            timeout_seconds: Timeout in seconds (None = no timeout, e.g., for initial scan).
        """
        self._console = console
        self._scan_args = scan_args or []
        self._timeout_seconds = timeout_seconds

    async def run(
        self,
        args: list[str],
        triggered_by: set[tuple[str, str]] | None = None,
    ) -> int:
        """Run a scan subprocess with optional timeout.

        Args:
            args: Command arguments (e.g., ["scan", "--no-embeddings"]).
            triggered_by: Set of (change_type, path) tuples that triggered this scan.

        Returns:
            Exit code from subprocess (0 = success, 1 = error, 124 = timeout).
        """
        # Build command
        # Try uv run first (uses local project), fall back to sys.executable
        if shutil.which("uv"):
            cmd = ["uv", "run", "fs2", "scan"] + self._scan_args
        else:
            cmd = [sys.executable, "-m", "fs2", "scan"] + self._scan_args

        # Display what triggered the scan
        if triggered_by:
            self._console.print_line()
            self._console.print_info(f"File changes detected ({len(triggered_by)}):")
            for change_type, path in sorted(triggered_by):
                self._console.print_info(f"  {change_type}: {path}")
            self._console.print_line()

        self._console.print_info("Running scan...")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=Path.cwd(),  # Ensure subprocess runs from caller's directory
            )

            async def stream_output():
                """Stream subprocess output to console."""
                if proc.stdout:
                    async for line in proc.stdout:
                        line_text = line.decode().rstrip("\n")
                        if line_text:
                            # Print raw output - subprocess already has Rich formatting
                            self._console.print(line_text)

            # Run with timeout if configured
            if self._timeout_seconds:
                try:
                    async with asyncio.timeout(self._timeout_seconds):
                        await stream_output()
                        await proc.wait()
                except TimeoutError:
                    # Kill the subprocess
                    proc.kill()
                    await proc.wait()
                    self._console.print_error(
                        f"Scan timed out after {self._timeout_seconds}s"
                    )
                    return 124  # Standard timeout exit code (like timeout command)
            else:
                await stream_output()
                await proc.wait()

            return proc.returncode or 0

        except Exception as e:
            self._console.print_error(f"Scan failed: {e}")
            return 1


def watch(
    ctx: typer.Context,
    no_embeddings: Annotated[
        bool,
        typer.Option(
            "--no-embeddings",
            help="Pass --no-embeddings to scan commands",
        ),
    ] = False,
    no_smart_content: Annotated[
        bool,
        typer.Option(
            "--no-smart-content",
            help="Pass --no-smart-content to scan commands",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed output"),
    ] = False,
) -> None:
    """Watch for file changes and automatically run scans.

    Monitors configured directories for changes and triggers `fs2 scan`
    automatically. Uses queue-one semantics to avoid excessive scans
    during rapid changes.

    Press Ctrl+C to stop watching.
    """
    console: ConsoleAdapter = RichConsoleAdapter()

    try:
        # Load configuration
        config = FS2ConfigurationService()

        # Get configs
        scan_config = config.require(ScanConfig)
        watch_config = config.get(WatchConfig) or WatchConfig()
        config.set(watch_config)  # Ensure WatchService.require() works

        # Build watch paths
        watch_paths = watch_config.watch_paths or scan_config.scan_paths
        resolved_paths = [Path(p).resolve() for p in watch_paths]

        # Display startup info (AC11)
        logger.info("Watch mode starting with %d paths", len(resolved_paths))
        logger.debug(
            "Debounce: %dms, Timeout: %ss",
            watch_config.debounce_ms,
            watch_config.scan_timeout_seconds,
        )
        console.print_success("Watch mode started")
        console.print_info(f"Watching: {', '.join(str(p) for p in resolved_paths)}")
        console.print_info(f"Debounce: {watch_config.debounce_ms}ms")
        console.print_info("Press Ctrl+C to stop")
        console.print_line()

        # Build scan args
        scan_args: list[str] = []
        if no_embeddings:
            scan_args.append("--no-embeddings")
        if no_smart_content:
            scan_args.append("--no-smart-content")
        if verbose:
            scan_args.append("--verbose")

        # Create components
        file_watcher = WatchfilesAdapter(
            watch_paths=resolved_paths,
            debounce_ms=watch_config.debounce_ms,
            additional_ignores=watch_config.additional_ignores,
        )

        # Create runner with timeout from config
        # Per DYK-2: scan_timeout_seconds applies to change-triggered scans
        scan_runner = SubprocessScanRunner(
            console=console,
            scan_args=scan_args,
            timeout_seconds=watch_config.scan_timeout_seconds,
        )

        service = WatchService(
            config=config,
            file_watcher=file_watcher,
            scan_runner=scan_runner,
            scan_args=scan_args,
        )

        # Setup signal handler for graceful shutdown
        def handle_signal(signum, frame):
            logger.info("Received signal %d, initiating shutdown", signum)
            console.print_info("\nShutting down...")
            service.stop()

        signal.signal(signal.SIGINT, handle_signal)
        # SIGTERM may not exist on Windows
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, handle_signal)

        # Run the watch loop
        asyncio.run(service.run())

        logger.info("Watch mode stopped gracefully")
        console.print_success("Stopped.")

    except MissingConfigurationError:
        logger.warning("No configuration found, suggesting 'fs2 init'")
        console.print_error(
            "No configuration found. Run 'fs2 init' first to create .fs2/config.yaml"
        )
        raise typer.Exit(code=1) from None

    except KeyboardInterrupt:
        logger.info("Watch mode stopped via KeyboardInterrupt")
        console.print_success("Stopped.")

    except Exception as e:
        logger.exception("Watch failed: %s", e)
        console.print_error(f"Watch failed: {e}")
        raise typer.Exit(code=1) from None
