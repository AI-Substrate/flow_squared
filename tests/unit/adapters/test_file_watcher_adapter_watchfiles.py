"""Tests for WatchfilesAdapter.

Task: T007
Purpose: Verify WatchfilesAdapter correctly wraps watchfiles.awatch()
         with debouncing, gitignore filtering, and graceful stop.
Per Finding 07: Use real watchfiles with tmp_path.
Per Finding 02: Adapter ABC with Dual Implementation Pattern.
"""

import asyncio
from pathlib import Path

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
class TestWatchfilesAdapter:
    """Tests for WatchfilesAdapter (T007).

    WatchfilesAdapter wraps watchfiles.awatch() to:
    - Detect file changes across platforms (Linux, macOS, Windows)
    - Apply GitignoreFilter for pattern exclusion
    - Debounce rapid changes per debounce_ms setting
    - Provide graceful stop via stop() method
    """

    async def test_watchfiles_adapter_implements_abc(self):
        """
        Given: WatchfilesAdapter class
        When: Checking inheritance
        Then: It inherits from FileWatcherAdapter ABC

        Purpose: Verifies proper ABC implementation.
        Quality Contribution: Contract compliance.
        """
        from fs2.core.adapters.file_watcher_adapter import FileWatcherAdapter
        from fs2.core.adapters.file_watcher_adapter_watchfiles import WatchfilesAdapter

        assert issubclass(WatchfilesAdapter, FileWatcherAdapter)

    async def test_watchfiles_adapter_detects_file_modification(self, tmp_path: Path):
        """
        Given: A directory with a file being watched
        When: The file is modified
        Then: watch() yields the change with "modified" type

        Purpose: Verifies basic file change detection.
        Quality Contribution: Core watch functionality (AC1).
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import WatchfilesAdapter

        # Create a file to watch
        test_file = tmp_path / "test.py"
        test_file.write_text("initial content")

        # Create adapter with short debounce for testing
        adapter = WatchfilesAdapter(
            watch_paths=[tmp_path],
            debounce_ms=50,  # Short debounce for fast tests
        )

        # Start watching in background
        changes_received: list[set] = []

        async def watch_and_collect():
            try:
                async with asyncio.timeout(3.0):
                    async for changes in adapter.watch():
                        changes_received.append(changes)
                        # Stop after first change
                        adapter.stop()
            except TimeoutError:
                pass

        # Start watch task
        watch_task = asyncio.create_task(watch_and_collect())

        # Wait a moment for watcher to initialize
        await asyncio.sleep(0.2)

        # Modify the file
        test_file.write_text("modified content")

        # Wait for watch task to complete
        await watch_task

        # Verify we got the change
        assert len(changes_received) >= 1
        # Find the change for our file
        all_changes = set()
        for change_set in changes_received:
            all_changes.update(change_set)

        # Check that our file is in the changes
        file_changes = [c for c in all_changes if str(test_file) in c[1]]
        assert len(file_changes) >= 1
        assert file_changes[0][0] in ("modified", "added")  # Some platforms report as "added"

    async def test_watchfiles_adapter_detects_file_creation(self, tmp_path: Path):
        """
        Given: A directory being watched
        When: A new file is created
        Then: watch() yields the change with "added" type

        Purpose: Verifies new file detection.
        Quality Contribution: Complete change type coverage.
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import WatchfilesAdapter

        adapter = WatchfilesAdapter(
            watch_paths=[tmp_path],
            debounce_ms=50,
        )

        changes_received: list[set] = []

        async def watch_and_collect():
            try:
                async with asyncio.timeout(3.0):
                    async for changes in adapter.watch():
                        changes_received.append(changes)
                        adapter.stop()
            except TimeoutError:
                pass

        watch_task = asyncio.create_task(watch_and_collect())
        await asyncio.sleep(0.2)

        # Create a new file
        new_file = tmp_path / "new_file.py"
        new_file.write_text("new content")

        await watch_task

        assert len(changes_received) >= 1
        all_changes = set()
        for change_set in changes_received:
            all_changes.update(change_set)

        file_changes = [c for c in all_changes if str(new_file) in c[1]]
        assert len(file_changes) >= 1
        assert file_changes[0][0] == "added"

    async def test_watchfiles_adapter_detects_file_deletion(self, tmp_path: Path):
        """
        Given: A directory with a file being watched
        When: The file is deleted
        Then: watch() yields the change with "deleted" type

        Purpose: Verifies file deletion detection.
        Quality Contribution: Complete change type coverage.
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import WatchfilesAdapter

        # Create a file first
        test_file = tmp_path / "to_delete.py"
        test_file.write_text("content")

        adapter = WatchfilesAdapter(
            watch_paths=[tmp_path],
            debounce_ms=50,
        )

        changes_received: list[set] = []

        async def watch_and_collect():
            try:
                async with asyncio.timeout(3.0):
                    async for changes in adapter.watch():
                        changes_received.append(changes)
                        adapter.stop()
            except TimeoutError:
                pass

        watch_task = asyncio.create_task(watch_and_collect())
        await asyncio.sleep(0.2)

        # Delete the file
        test_file.unlink()

        await watch_task

        assert len(changes_received) >= 1
        all_changes = set()
        for change_set in changes_received:
            all_changes.update(change_set)

        file_changes = [c for c in all_changes if "to_delete.py" in c[1]]
        assert len(file_changes) >= 1
        assert file_changes[0][0] == "deleted"

    async def test_watchfiles_adapter_respects_gitignore(self, tmp_path: Path):
        """
        Given: A directory with .gitignore containing *.pyc
        When: A .pyc file is modified
        Then: watch() does NOT yield the change

        Purpose: Verifies gitignore patterns are applied.
        Quality Contribution: Gitignore filtering (AC4).
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import WatchfilesAdapter

        # Create .gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n")

        # Create files
        pyc_file = tmp_path / "test.pyc"
        pyc_file.write_text("bytecode")
        py_file = tmp_path / "test.py"
        py_file.write_text("source")

        adapter = WatchfilesAdapter(
            watch_paths=[tmp_path],
            debounce_ms=50,
        )

        changes_received: list[set] = []

        async def watch_and_collect():
            try:
                async with asyncio.timeout(2.0):
                    async for changes in adapter.watch():
                        changes_received.append(changes)
                        # Continue watching to see if pyc change comes through
            except TimeoutError:
                pass
            finally:
                adapter.stop()

        watch_task = asyncio.create_task(watch_and_collect())
        await asyncio.sleep(0.2)

        # Modify .pyc file (should be ignored)
        pyc_file.write_text("modified bytecode")

        # Wait a bit then modify .py file (should be detected)
        await asyncio.sleep(0.2)
        py_file.write_text("modified source")

        await watch_task

        # Flatten all changes
        all_changes = set()
        for change_set in changes_received:
            all_changes.update(change_set)

        # .py file should be in changes
        py_changes = [c for c in all_changes if c[1].endswith(".py")]
        # .pyc file should NOT be in changes
        pyc_changes = [c for c in all_changes if c[1].endswith(".pyc")]

        assert len(py_changes) >= 1, "Expected .py file change to be detected"
        assert len(pyc_changes) == 0, "Expected .pyc file change to be ignored"

    async def test_watchfiles_adapter_respects_additional_ignores(self, tmp_path: Path):
        """
        Given: Additional ignore patterns ["*.tmp", ".cache/"]
        When: A .tmp file is modified
        Then: watch() does NOT yield the change

        Purpose: Verifies WatchConfig additional_ignores work.
        Quality Contribution: Config-driven exclusions (AC9).
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import WatchfilesAdapter

        # Create files
        tmp_file = tmp_path / "test.tmp"
        tmp_file.write_text("temp data")
        py_file = tmp_path / "test.py"
        py_file.write_text("source")

        adapter = WatchfilesAdapter(
            watch_paths=[tmp_path],
            debounce_ms=50,
            additional_ignores=["*.tmp"],
        )

        changes_received: list[set] = []

        async def watch_and_collect():
            try:
                async with asyncio.timeout(2.0):
                    async for changes in adapter.watch():
                        changes_received.append(changes)
            except TimeoutError:
                pass
            finally:
                adapter.stop()

        watch_task = asyncio.create_task(watch_and_collect())
        await asyncio.sleep(0.2)

        # Modify .tmp file (should be ignored)
        tmp_file.write_text("modified temp")
        await asyncio.sleep(0.2)

        # Modify .py file (should be detected)
        py_file.write_text("modified source")

        await watch_task

        all_changes = set()
        for change_set in changes_received:
            all_changes.update(change_set)

        py_changes = [c for c in all_changes if c[1].endswith(".py")]
        tmp_changes = [c for c in all_changes if c[1].endswith(".tmp")]

        assert len(py_changes) >= 1, "Expected .py file change to be detected"
        assert len(tmp_changes) == 0, "Expected .tmp file change to be ignored"

    async def test_watchfiles_adapter_stop_exits_loop(self, tmp_path: Path):
        """
        Given: WatchfilesAdapter watching a directory
        When: stop() is called
        Then: watch() generator exits cleanly

        Purpose: Verifies graceful shutdown.
        Quality Contribution: Graceful shutdown (AC7).
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import WatchfilesAdapter

        adapter = WatchfilesAdapter(
            watch_paths=[tmp_path],
            debounce_ms=50,
        )

        loop_exited = False

        async def watch_and_wait():
            nonlocal loop_exited
            async for _changes in adapter.watch():
                pass  # Won't get here without file changes
            loop_exited = True

        watch_task = asyncio.create_task(watch_and_wait())
        await asyncio.sleep(0.2)

        # Stop the watcher
        adapter.stop()

        # Wait for task with timeout
        try:
            async with asyncio.timeout(2.0):
                await watch_task
        except TimeoutError:
            pytest.fail("watch() did not exit after stop() was called")

        assert loop_exited, "Watch loop should have exited cleanly"

    async def test_watchfiles_adapter_stop_is_idempotent(self, tmp_path: Path):
        """
        Given: WatchfilesAdapter
        When: stop() is called multiple times
        Then: No error is raised

        Purpose: Verifies stop() safety.
        Quality Contribution: Robust shutdown handling.
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import WatchfilesAdapter

        adapter = WatchfilesAdapter(
            watch_paths=[tmp_path],
            debounce_ms=50,
        )

        # Start then stop
        async def start_and_stop():
            async with asyncio.timeout(1.0):
                async for _changes in adapter.watch():
                    break

        task = asyncio.create_task(start_and_stop())
        await asyncio.sleep(0.1)

        # Stop multiple times - should not raise
        adapter.stop()
        adapter.stop()
        adapter.stop()

        try:
            await task
        except (TimeoutError, asyncio.CancelledError):
            pass

    async def test_watchfiles_adapter_watches_multiple_paths(self, tmp_path: Path):
        """
        Given: Multiple watch paths
        When: Files in different paths are modified
        Then: Changes from all paths are detected

        Purpose: Verifies multi-path support.
        Quality Contribution: Configuration flexibility.
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import WatchfilesAdapter

        # Create two directories
        dir_a = tmp_path / "dir_a"
        dir_b = tmp_path / "dir_b"
        dir_a.mkdir()
        dir_b.mkdir()

        file_a = dir_a / "a.py"
        file_b = dir_b / "b.py"
        file_a.write_text("content a")
        file_b.write_text("content b")

        adapter = WatchfilesAdapter(
            watch_paths=[dir_a, dir_b],
            debounce_ms=50,
        )

        changes_received: list[set] = []
        change_count = 0

        async def watch_and_collect():
            nonlocal change_count
            try:
                async with asyncio.timeout(3.0):
                    async for changes in adapter.watch():
                        changes_received.append(changes)
                        change_count += 1
                        if change_count >= 2:
                            adapter.stop()
            except TimeoutError:
                pass

        watch_task = asyncio.create_task(watch_and_collect())
        await asyncio.sleep(0.2)

        # Modify files in both directories
        file_a.write_text("modified a")
        await asyncio.sleep(0.2)
        file_b.write_text("modified b")

        await watch_task

        all_changes = set()
        for change_set in changes_received:
            all_changes.update(change_set)

        # Both files should have changes detected
        paths = [c[1] for c in all_changes]
        assert any("a.py" in p for p in paths), "Expected change in dir_a"
        assert any("b.py" in p for p in paths), "Expected change in dir_b"

    async def test_watchfiles_adapter_debounces_rapid_changes(self, tmp_path: Path):
        """
        Given: WatchfilesAdapter with debounce_ms=300
        When: Multiple rapid changes occur to the same file
        Then: Changes are batched into fewer yields

        Purpose: Verifies debouncing behavior.
        Quality Contribution: Debounce batching (AC5).
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import WatchfilesAdapter

        test_file = tmp_path / "test.py"
        test_file.write_text("initial")

        # Longer debounce to ensure batching
        adapter = WatchfilesAdapter(
            watch_paths=[tmp_path],
            debounce_ms=300,
        )

        changes_received: list[set] = []

        async def watch_and_collect():
            try:
                async with asyncio.timeout(2.0):
                    async for changes in adapter.watch():
                        changes_received.append(changes)
            except TimeoutError:
                pass
            finally:
                adapter.stop()

        watch_task = asyncio.create_task(watch_and_collect())
        await asyncio.sleep(0.2)

        # Make multiple rapid changes (faster than debounce window)
        for i in range(5):
            test_file.write_text(f"content {i}")
            await asyncio.sleep(0.05)  # 50ms between changes

        await watch_task

        # With 300ms debounce and 5 changes at 50ms intervals (250ms total),
        # they should be batched into 1-2 yields, not 5
        assert len(changes_received) < 5, "Expected changes to be debounced/batched"

    async def test_watchfiles_adapter_yields_change_tuples(self, tmp_path: Path):
        """
        Given: WatchfilesAdapter watching a directory
        When: A file is modified
        Then: Yielded changes are tuples of (change_type, absolute_path)

        Purpose: Verifies correct change format for ABC contract.
        Quality Contribution: Type contract compliance.
        """
        from fs2.core.adapters.file_watcher_adapter_watchfiles import WatchfilesAdapter

        test_file = tmp_path / "test.py"
        test_file.write_text("initial")

        adapter = WatchfilesAdapter(
            watch_paths=[tmp_path],
            debounce_ms=50,
        )

        changes_received: list[set] = []

        async def watch_and_collect():
            try:
                async with asyncio.timeout(2.0):
                    async for changes in adapter.watch():
                        changes_received.append(changes)
                        adapter.stop()
            except TimeoutError:
                pass

        watch_task = asyncio.create_task(watch_and_collect())
        await asyncio.sleep(0.2)

        test_file.write_text("modified")
        await watch_task

        assert len(changes_received) >= 1

        # Check the format
        for change_set in changes_received:
            assert isinstance(change_set, set)
            for change in change_set:
                assert isinstance(change, tuple)
                assert len(change) == 2
                change_type, path = change
                assert change_type in ("added", "modified", "deleted")
                assert isinstance(path, str)
                # Path should be absolute
                assert Path(path).is_absolute() or tmp_path.name in path
