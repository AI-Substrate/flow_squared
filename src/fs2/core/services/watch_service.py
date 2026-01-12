"""WatchService - File watching with queue-one semantics.

Orchestrates file watching and automatic scanning:
- Monitors directories for file changes via FileWatcherAdapter
- Runs scans using injected scan runner (subprocess isolation)
- Implements queue-one semantics (multiple changes = one queued scan)
- Supports graceful shutdown on Ctrl+C

Architecture:
- Receives ConfigurationService (registry), calls config.require(WatchConfig)
- Receives FileWatcherAdapter ABC (FakeFileWatcher for testing, WatchfilesAdapter for production)
- Receives scan runner for subprocess isolation (FakeScanRunner for testing)

Per Finding 03: Service DI pattern - receives registry, extracts config internally.
Per DYK-3: Start watcher BEFORE initial scan to prevent race conditions.
Per DYK-4: FakeFileWatcher uses Finite Queue + Auto-Stop for deterministic tests.
Per DYK-5: KISS - log errors and continue (per AC10).
"""

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Protocol

from fs2.config.objects import ScanConfig, WatchConfig

logger = logging.getLogger(__name__)
from fs2.core.adapters.file_watcher_adapter import FileWatcherAdapter

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


class ScanRunner(Protocol):
    """Protocol for scan execution.

    Abstracts the scan subprocess to enable testing without real processes.
    """

    async def run(
        self,
        args: list[str],
        triggered_by: set[tuple[str, str]] | None = None,
    ) -> int:
        """Run a scan with the given arguments.

        Args:
            args: Command arguments (e.g., ["scan", "--no-embeddings"]).
            triggered_by: Set of (change_type, path) tuples that triggered this scan.
                          None for initial scan or queued scans.

        Returns:
            Exit code (0 = success, non-zero = failure).
        """
        ...


class WatchService:
    """Service for watching files and triggering scans.

    Implements queue-one semantics:
    - When a scan is running and new changes arrive, queue ONE scan
    - Multiple changes while scan is running = one queued scan, not N scans
    - After current scan completes, run queued scan if any

    Lifecycle:
    1. run() is called
    2. Watcher is started (collects changes)
    3. Initial scan runs (no timeout per DYK-2)
    4. Enter watch loop: wait for changes, run scan, repeat
    5. stop() triggers graceful shutdown

    Thread Safety:
        stop() may be called from signal handler.
        Uses asyncio.Event for cross-task communication.

    Usage:
        ```python
        config = FS2ConfigurationService()
        watcher = WatchfilesAdapter(watch_paths=[Path("./src")])
        runner = SubprocessScanRunner()

        service = WatchService(
            config=config,
            file_watcher=watcher,
            scan_runner=runner,
        )

        await service.run()  # Runs until Ctrl+C
        ```

    Testing:
        ```python
        watcher = FakeFileWatcher()
        watcher.add_changes({("modified", "/src/a.py")})

        runner = FakeScanRunner()

        service = WatchService(config=..., file_watcher=watcher, scan_runner=runner)
        await service.run()

        assert runner.run_count >= 1
        ```
    """

    def __init__(
        self,
        config: "ConfigurationService",
        file_watcher: FileWatcherAdapter,
        scan_runner: ScanRunner,
        scan_args: list[str] | None = None,
    ) -> None:
        """Initialize WatchService.

        Args:
            config: ConfigurationService registry (NOT WatchConfig directly).
                    Service calls config.require(WatchConfig) internally.
            file_watcher: Adapter for file change detection (ABC type).
            scan_runner: Runner for executing scans (Protocol type).
            scan_args: Optional arguments to pass to each scan (e.g., ["--no-embeddings"]).

        Raises:
            MissingConfigurationError: If WatchConfig not in registry.
        """
        self._watch_config = config.require(WatchConfig)
        self._scan_config = config.require(ScanConfig)
        self._file_watcher = file_watcher
        self._scan_runner = scan_runner
        self._scan_args = scan_args or []

        # State
        self._stop_event = asyncio.Event()
        self._scan_in_progress = False
        self._scan_queued = False

        logger.debug(
            "WatchService initialized with %d watch paths",
            len(self._watch_config.watch_paths or []),
        )

    async def run(self) -> None:
        """Run the watch loop.

        Executes:
        1. Start file watcher (per DYK-3: before initial scan)
        2. Run initial scan (no timeout)
        3. Enter watch loop until stop() is called
        4. Clean up and exit

        The loop continues even if individual scans fail (per AC10).
        """
        # Start watching immediately (DYK-3: race condition prevention)
        watch_task = asyncio.create_task(self._watch_loop())

        try:
            # Run initial scan (no timeout per DYK-2)
            await self._run_scan()

            # Wait for watch loop to complete (runs until stop or watcher exhausted)
            await watch_task

            # Run any final queued scan
            if self._scan_queued and not self._stop_event.is_set():
                self._scan_queued = False
                await self._run_scan()

        except asyncio.CancelledError:
            # Graceful cancellation
            pass
        except Exception:
            # Cancel watch_task if initial scan raises (FIX-004: prevent task leak)
            watch_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watch_task
            raise
        finally:
            # Ensure watcher is stopped
            self._file_watcher.stop()

    async def _watch_loop(self) -> None:
        """Process file change events from watcher.

        Implements queue-one semantics:
        - If scan in progress, set queue flag (don't increment counter)
        - If no scan in progress, start scan immediately
        """
        try:
            async for changes in self._file_watcher.watch():
                if self._stop_event.is_set():
                    break

                if self._scan_in_progress:
                    # Queue-one: just set flag, don't accumulate
                    logger.debug("Scan in progress, queueing next scan (queue-one)")
                    self._scan_queued = True
                else:
                    # Start scan immediately with triggering files
                    logger.debug("No scan in progress, triggering immediate scan")
                    await self._run_scan(triggered_by=changes)

                    # Check if scan was queued during execution
                    # Note: queued scans don't have specific trigger info
                    while self._scan_queued and not self._stop_event.is_set():
                        self._scan_queued = False
                        await self._run_scan()

        except asyncio.CancelledError:
            pass

    async def _run_scan(
        self,
        triggered_by: set[tuple[str, str]] | None = None,
    ) -> int:
        """Execute a scan via the scan runner.

        Args:
            triggered_by: Set of (change_type, path) tuples that triggered this scan.
                          None for initial scan or queued scans.

        Returns:
            Exit code from scan runner.

        Per AC10/DYK-5: Logs errors but continues (KISS).
        """
        self._scan_in_progress = True
        logger.debug("Starting scan, triggered_by=%s", triggered_by)
        try:
            # Build command args
            args = ["scan"] + self._scan_args
            result = await self._scan_runner.run(args, triggered_by=triggered_by)
            logger.info("Scan completed with exit code %d", result)
            return result
        except Exception:
            # Per DYK-5: Log and continue
            logger.exception("Scan failed")
            return 1
        finally:
            self._scan_in_progress = False

    def stop(self) -> None:
        """Request graceful shutdown.

        Safe to call from signal handlers or other tasks.
        Idempotent - can be called multiple times.
        """
        logger.info("Stop requested, initiating graceful shutdown")
        self._stop_event.set()
        self._file_watcher.stop()
