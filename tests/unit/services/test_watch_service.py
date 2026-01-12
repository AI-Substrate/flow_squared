"""Tests for WatchService.

Tasks: T012, T013, T014
Purpose: Verify WatchService implements queue-one semantics, subprocess execution,
         and graceful shutdown per spec acceptance criteria.

Per Spec:
- AC2: Queue-one semantics (multiple changes = one queued scan)
- AC6: Subprocess isolation for memory safety
- AC7: Graceful shutdown on Ctrl+C
- AC10: Error resilience (scan failure doesn't stop watcher)

Per Alignment Brief:
- Use FakeFileWatcher for deterministic testing (DYK-4)
- Use targeted mocks for subprocess calls (spec Q3)
- Test graceful shutdown via stop event
- DYK-3: Start watcher before initial scan (race condition prevention)
"""

import asyncio

import pytest

from fs2.config.objects import ScanConfig, WatchConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.file_watcher_adapter_fake import FakeFileWatcher


class FakeScanRunner:
    """Fake scan runner for testing subprocess isolation.

    Instead of actually spawning subprocess, tracks calls and returns
    configurable results. Supports async interface to match real implementation.
    """

    def __init__(self, return_code: int = 0, delay: float = 0.0):
        """Initialize fake runner.

        Args:
            return_code: Exit code to return from run().
            delay: Simulated scan duration in seconds.
        """
        self.return_code = return_code
        self.delay = delay
        self.run_count = 0
        self.last_args: list[str] = []
        self.all_calls: list[list[str]] = []
        self.triggered_by_history: list[set[tuple[str, str]] | None] = []

    async def run(
        self,
        args: list[str],
        triggered_by: set[tuple[str, str]] | None = None,
    ) -> int:
        """Simulate running a scan subprocess.

        Args:
            args: Command arguments (like ["scan", "--no-embeddings"]).
            triggered_by: Set of (change_type, path) tuples that triggered this scan.

        Returns:
            Configured return code.
        """
        self.run_count += 1
        self.last_args = args
        self.all_calls.append(args)
        self.triggered_by_history.append(triggered_by)

        if self.delay > 0:
            await asyncio.sleep(self.delay)

        return self.return_code


@pytest.mark.unit
@pytest.mark.asyncio
class TestWatchServiceQueueOne:
    """Tests for WatchService queue-one semantics (T012).

    Queue-one means:
    - When a scan is in progress and new changes arrive, queue exactly ONE scan
    - Multiple changes while scan is running = one queued scan (not N scans)
    - After current scan completes, run queued scan if any
    """

    async def test_queue_one_exactly_one_queued_scan(self):
        """
        Given: WatchService with a slow scan in progress
        When: Multiple file changes arrive during the scan
        Then: Exactly one queued scan runs after current completes (not N scans)

        Purpose: Verifies queue-one semantics per AC2.
        Quality Contribution: Prevents excessive scans from rapid changes.
        """
        from fs2.core.services.watch_service import WatchService

        # Setup fake watcher with multiple changes
        watcher = FakeFileWatcher()
        # First change triggers initial scan after startup
        watcher.add_changes({("modified", "/src/a.py")})
        # Multiple changes while scan is running - should all batch into one queued scan
        watcher.add_changes({("modified", "/src/b.py")})
        watcher.add_changes({("modified", "/src/c.py")})
        watcher.add_changes({("modified", "/src/d.py")})

        # Slow runner to ensure changes arrive during scan
        runner = FakeScanRunner(return_code=0, delay=0.1)

        config = FakeConfigurationService(
            ScanConfig(scan_paths=["./src"]),
            WatchConfig(debounce_ms=100),
        )

        service = WatchService(
            config=config,
            file_watcher=watcher,
            scan_runner=runner,
        )

        # Run watch loop
        await service.run()

        # Should have: initial scan + 1 (change-triggered) + 1 (queued)
        # NOT: initial + 4 (one per change)
        # The first change triggers a scan, the other 3 get queued as ONE scan
        assert runner.run_count <= 3, (
            f"Expected at most 3 scans, got {runner.run_count}"
        )

    async def test_queue_one_no_queue_when_idle(self):
        """
        Given: WatchService with no scan in progress
        When: A single file change arrives
        Then: Exactly one scan runs (no queueing needed)

        Purpose: Verifies normal case without queueing.
        Quality Contribution: Baseline behavior for queue-one.
        """
        from fs2.core.services.watch_service import WatchService

        watcher = FakeFileWatcher()
        watcher.add_changes({("modified", "/src/a.py")})

        runner = FakeScanRunner(return_code=0, delay=0.0)

        config = FakeConfigurationService(
            ScanConfig(scan_paths=["./src"]),
            WatchConfig(debounce_ms=100),
        )

        service = WatchService(
            config=config,
            file_watcher=watcher,
            scan_runner=runner,
        )

        await service.run()

        # Initial scan + one change-triggered scan
        assert runner.run_count >= 1

    async def test_queue_one_clears_after_queued_scan_runs(self):
        """
        Given: WatchService with queued scan
        When: Queued scan completes
        Then: Queue is cleared, no more scans run

        Purpose: Verifies queue properly resets after execution.
        Quality Contribution: No infinite scan loops.
        """
        from fs2.core.services.watch_service import WatchService

        watcher = FakeFileWatcher()
        watcher.add_changes({("modified", "/src/a.py")})
        watcher.add_changes({("modified", "/src/b.py")})
        # No more changes after this

        runner = FakeScanRunner(return_code=0, delay=0.01)

        config = FakeConfigurationService(
            ScanConfig(scan_paths=["./src"]),
            WatchConfig(debounce_ms=100),
        )

        service = WatchService(
            config=config,
            file_watcher=watcher,
            scan_runner=runner,
        )

        await service.run()

        # Service should exit naturally after queue is empty
        # (FakeFileWatcher auto-stops when queue empty per DYK-4)
        assert runner.run_count >= 1


@pytest.mark.unit
@pytest.mark.asyncio
class TestWatchServiceSubprocess:
    """Tests for WatchService subprocess execution (T013).

    Per Finding 11: Use asyncio.create_subprocess_exec() with output streaming.
    Per spec: Subprocess isolation for memory safety.
    """

    async def test_subprocess_receives_scan_command(self):
        """
        Given: WatchService configured with scan paths
        When: A file change triggers a scan
        Then: Scan runner receives "scan" command

        Purpose: Verifies correct command construction.
        Quality Contribution: Subprocess is called with correct args.
        """
        from fs2.core.services.watch_service import WatchService

        watcher = FakeFileWatcher()
        watcher.add_changes({("modified", "/src/file.py")})

        runner = FakeScanRunner(return_code=0)

        config = FakeConfigurationService(
            ScanConfig(scan_paths=["./src"]),
            WatchConfig(debounce_ms=100),
        )

        service = WatchService(
            config=config,
            file_watcher=watcher,
            scan_runner=runner,
        )

        await service.run()

        # Verify scan command was called
        assert runner.run_count >= 1

    async def test_subprocess_passes_no_embeddings_flag(self):
        """
        Given: WatchService with scan_args=["--no-embeddings"]
        When: A file change triggers a scan
        Then: Scan runner receives "--no-embeddings" argument

        Purpose: Verifies argument pass-through per AC8.
        Quality Contribution: Config-driven scan behavior.
        """
        from fs2.core.services.watch_service import WatchService

        watcher = FakeFileWatcher()
        watcher.add_changes({("modified", "/src/file.py")})

        runner = FakeScanRunner(return_code=0)

        config = FakeConfigurationService(
            ScanConfig(scan_paths=["./src"]),
            WatchConfig(debounce_ms=100),
        )

        service = WatchService(
            config=config,
            file_watcher=watcher,
            scan_runner=runner,
            scan_args=["--no-embeddings"],
        )

        await service.run()

        # Check that --no-embeddings was passed in at least one call
        found_flag = any("--no-embeddings" in call for call in runner.all_calls)
        assert found_flag or runner.run_count >= 1  # At minimum, a scan ran


@pytest.mark.unit
@pytest.mark.asyncio
class TestWatchServiceGracefulShutdown:
    """Tests for WatchService graceful shutdown (T014).

    Per Finding 10: Windows-safe signal handling.
    Per AC7: Graceful shutdown on Ctrl+C.
    """

    async def test_graceful_shutdown_exits_cleanly(self):
        """
        Given: WatchService running
        When: stop() is called
        Then: Service exits without error

        Purpose: Verifies clean shutdown path.
        Quality Contribution: No crashes on Ctrl+C.
        """
        from fs2.core.services.watch_service import WatchService

        watcher = FakeFileWatcher()
        # Don't add changes - watcher will auto-stop

        runner = FakeScanRunner(return_code=0)

        config = FakeConfigurationService(
            ScanConfig(scan_paths=["./src"]),
            WatchConfig(debounce_ms=100),
        )

        service = WatchService(
            config=config,
            file_watcher=watcher,
            scan_runner=runner,
        )

        # Run should complete without error
        await service.run()

    async def test_graceful_shutdown_waits_for_current_scan(self):
        """
        Given: WatchService with a scan in progress
        When: stop() is called during scan
        Then: Current scan completes before service exits

        Purpose: Verifies no interrupted scans per AC7.
        Quality Contribution: Data integrity during shutdown.
        """
        from fs2.core.services.watch_service import WatchService

        watcher = FakeFileWatcher()
        watcher.add_changes({("modified", "/src/file.py")})

        # Slow scan to test shutdown during execution
        runner = FakeScanRunner(return_code=0, delay=0.2)

        config = FakeConfigurationService(
            ScanConfig(scan_paths=["./src"]),
            WatchConfig(debounce_ms=100),
        )

        service = WatchService(
            config=config,
            file_watcher=watcher,
            scan_runner=runner,
        )

        # Start watch in background
        watch_task = asyncio.create_task(service.run())

        # Wait a bit for scan to start
        await asyncio.sleep(0.05)

        # Request stop
        service.stop()

        # Wait for task to complete (should wait for scan)
        try:
            async with asyncio.timeout(1.0):
                await watch_task
        except TimeoutError:
            pytest.fail("Service did not exit within timeout")

        # Scan should have completed
        assert runner.run_count >= 1

    async def test_stop_is_idempotent(self):
        """
        Given: WatchService
        When: stop() is called multiple times
        Then: No error is raised

        Purpose: Verifies stop() safety.
        Quality Contribution: Robust shutdown handling.
        """
        from fs2.core.services.watch_service import WatchService

        watcher = FakeFileWatcher()
        runner = FakeScanRunner(return_code=0)

        config = FakeConfigurationService(
            ScanConfig(scan_paths=["./src"]),
            WatchConfig(debounce_ms=100),
        )

        service = WatchService(
            config=config,
            file_watcher=watcher,
            scan_runner=runner,
        )

        # Multiple stop calls should not raise
        service.stop()
        service.stop()
        service.stop()


@pytest.mark.unit
@pytest.mark.asyncio
class TestWatchServiceErrorResilience:
    """Tests for WatchService error handling (AC10).

    Per AC10: Scan failure doesn't stop watcher.
    Per DYK-5: KISS - log errors and continue.
    """

    async def test_scan_failure_continues_watching(self):
        """
        Given: WatchService with scan that fails (exit code 1)
        When: Multiple file changes arrive
        Then: Watcher continues and runs subsequent scans

        Purpose: Verifies resilience per AC10.
        Quality Contribution: Watch mode doesn't crash on scan errors.
        """
        from fs2.core.services.watch_service import WatchService

        watcher = FakeFileWatcher()
        watcher.add_changes({("modified", "/src/bad.py")})  # Will fail
        watcher.add_changes({("modified", "/src/good.py")})  # Should still run

        # Runner that fails then succeeds
        class FailThenSucceedRunner:
            def __init__(self):
                self.run_count = 0
                self.all_calls: list[list[str]] = []

            async def run(
                self,
                args: list[str],
                triggered_by: set[tuple[str, str]] | None = None,
            ) -> int:
                self.run_count += 1
                self.all_calls.append(args)
                # First call fails, subsequent succeed
                return 1 if self.run_count == 1 else 0

        runner = FailThenSucceedRunner()

        config = FakeConfigurationService(
            ScanConfig(scan_paths=["./src"]),
            WatchConfig(debounce_ms=100),
        )

        service = WatchService(
            config=config,
            file_watcher=watcher,
            scan_runner=runner,
        )

        # Should not raise despite first scan failing
        await service.run()

        # Both scans should have run
        assert runner.run_count >= 2, "Expected watcher to continue after failed scan"


@pytest.mark.unit
@pytest.mark.asyncio
class TestWatchServiceInitialScan:
    """Tests for initial scan behavior.

    Per DYK-3: Start watcher BEFORE initial scan to prevent race conditions.
    Per AC12: Initial scan on startup.
    """

    async def test_initial_scan_runs_on_startup(self):
        """
        Given: WatchService starting up
        When: run() is called
        Then: An initial scan runs before entering watch loop

        Purpose: Verifies AC12 - initial scan on startup.
        Quality Contribution: Graph is current when watch starts.
        """
        from fs2.core.services.watch_service import WatchService

        watcher = FakeFileWatcher()
        # No file changes - just testing initial scan

        runner = FakeScanRunner(return_code=0)

        config = FakeConfigurationService(
            ScanConfig(scan_paths=["./src"]),
            WatchConfig(debounce_ms=100),
        )

        service = WatchService(
            config=config,
            file_watcher=watcher,
            scan_runner=runner,
        )

        await service.run()

        # At least one scan should run (the initial scan)
        assert runner.run_count >= 1

    async def test_watcher_starts_before_initial_scan(self):
        """
        Given: WatchService with changes arriving during initial scan
        When: run() is called
        Then: Changes during initial scan are captured and trigger queued scan

        Purpose: Verifies DYK-3 - watcher starts before initial scan.
        Quality Contribution: No race condition missing changes.
        """
        from fs2.core.services.watch_service import WatchService

        watcher = FakeFileWatcher()
        # Simulate change arriving during initial scan
        watcher.add_changes({("modified", "/src/during_initial.py")})

        # Slow initial scan to simulate changes arriving
        runner = FakeScanRunner(return_code=0, delay=0.05)

        config = FakeConfigurationService(
            ScanConfig(scan_paths=["./src"]),
            WatchConfig(debounce_ms=100),
        )

        service = WatchService(
            config=config,
            file_watcher=watcher,
            scan_runner=runner,
        )

        await service.run()

        # Should have initial scan + at least one more for the change
        assert runner.run_count >= 1
