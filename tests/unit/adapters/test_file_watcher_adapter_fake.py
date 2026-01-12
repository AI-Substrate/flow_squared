"""Tests for FakeFileWatcher implementation.

Task: T005
Purpose: Verify FakeFileWatcher behaves correctly for testing.
Per Finding 06: Use FakeFileWatcher (not mocks), state-driven assertions.
Per DYK-4: Finite Queue + Auto-Stop pattern for deterministic tests.
"""

import pytest

from fs2.core.adapters.file_watcher_adapter import FileWatcherAdapter


@pytest.mark.unit
class TestFakeFileWatcher:
    """Tests for FakeFileWatcher test double (T005).

    FakeFileWatcher uses "Finite Queue + Auto-Stop" pattern:
    - add_changes() queues pre-programmed change sets
    - watch() yields each change set in order
    - After queue empty, automatically raises StopAsyncIteration
    """

    @pytest.mark.asyncio
    async def test_fake_file_watcher_implements_abc(self):
        """
        Given: FakeFileWatcher is a concrete implementation
        When: Checking its inheritance
        Then: It should be a subclass of FileWatcherAdapter

        Purpose: Verifies FakeFileWatcher implements the ABC.
        Quality Contribution: Ensures fake follows the interface contract.
        """
        from fs2.core.adapters.file_watcher_adapter_fake import FakeFileWatcher

        assert issubclass(FakeFileWatcher, FileWatcherAdapter)

    @pytest.mark.asyncio
    async def test_fake_file_watcher_emits_programmed_changes(self):
        """
        Given: FakeFileWatcher with pre-programmed changes via add_changes()
        When: Iterating over watch()
        Then: It yields each programmed change set in order

        Purpose: Proves fake emits configured changes.
        Quality Contribution: Enables deterministic testing of watch consumers.
        """
        from fs2.core.adapters.file_watcher_adapter_fake import FakeFileWatcher

        watcher = FakeFileWatcher()
        watcher.add_changes({("modified", "/path/to/a.py")})
        watcher.add_changes({("modified", "/path/to/b.py")})

        changes_received = []
        async for changes in watcher.watch():
            changes_received.append(changes)

        assert len(changes_received) == 2
        assert changes_received[0] == {("modified", "/path/to/a.py")}
        assert changes_received[1] == {("modified", "/path/to/b.py")}

    @pytest.mark.asyncio
    async def test_fake_file_watcher_auto_stops_when_queue_empty(self):
        """
        Given: FakeFileWatcher with finite changes queued
        When: All changes have been yielded
        Then: watch() automatically stops (StopAsyncIteration)

        Purpose: Proves auto-stop behavior for deterministic tests.
        Quality Contribution: No timeouts needed, no flaky tests.
        Per DYK-4: Finite Queue + Auto-Stop pattern.
        """
        from fs2.core.adapters.file_watcher_adapter_fake import FakeFileWatcher

        watcher = FakeFileWatcher()
        watcher.add_changes({("modified", "/path/to/file.py")})

        count = 0
        async for _ in watcher.watch():
            count += 1

        # Loop exited naturally after 1 iteration
        assert count == 1

    @pytest.mark.asyncio
    async def test_fake_file_watcher_yields_multiple_changes_per_batch(self):
        """
        Given: FakeFileWatcher with a batch containing multiple changes
        When: watch() yields
        Then: All changes in the batch are yielded together

        Purpose: Proves batched changes work correctly.
        Quality Contribution: Simulates debounced batch behavior.
        """
        from fs2.core.adapters.file_watcher_adapter_fake import FakeFileWatcher

        watcher = FakeFileWatcher()
        watcher.add_changes({
            ("modified", "/path/to/a.py"),
            ("modified", "/path/to/b.py"),
            ("added", "/path/to/c.py"),
        })

        async for changes in watcher.watch():
            assert len(changes) == 3
            assert ("modified", "/path/to/a.py") in changes
            assert ("modified", "/path/to/b.py") in changes
            assert ("added", "/path/to/c.py") in changes

    @pytest.mark.asyncio
    async def test_fake_file_watcher_stop_exits_loop(self):
        """
        Given: FakeFileWatcher with infinite or many changes
        When: stop() is called
        Then: watch() exits gracefully

        Purpose: Verifies stop() terminates the watch loop.
        Quality Contribution: Ensures graceful shutdown path is testable.
        """
        from fs2.core.adapters.file_watcher_adapter_fake import FakeFileWatcher

        watcher = FakeFileWatcher()
        # Add many changes
        for i in range(100):
            watcher.add_changes({("modified", f"/path/to/file{i}.py")})

        count = 0
        async for _ in watcher.watch():
            count += 1
            if count >= 3:
                watcher.stop()
                break

        # Loop exited after stop() called
        assert count == 3

    @pytest.mark.asyncio
    async def test_fake_file_watcher_tracks_watch_calls(self):
        """
        Given: FakeFileWatcher
        When: watch() is called
        Then: The call is tracked for test verification

        Purpose: Enables verification that watch() was called.
        Quality Contribution: Supports assertion-based testing.
        """
        from fs2.core.adapters.file_watcher_adapter_fake import FakeFileWatcher

        watcher = FakeFileWatcher()
        watcher.add_changes({("modified", "/path/to/file.py")})

        async for _ in watcher.watch():
            pass

        assert watcher.watch_call_count >= 1

    @pytest.mark.asyncio
    async def test_fake_file_watcher_empty_queue_yields_nothing(self):
        """
        Given: FakeFileWatcher with no changes queued
        When: watch() is called
        Then: It immediately stops without yielding

        Purpose: Verifies empty queue behavior.
        Quality Contribution: Edge case handling for tests.
        """
        from fs2.core.adapters.file_watcher_adapter_fake import FakeFileWatcher

        watcher = FakeFileWatcher()

        count = 0
        async for _ in watcher.watch():
            count += 1

        assert count == 0

    @pytest.mark.asyncio
    async def test_fake_file_watcher_stop_is_idempotent(self):
        """
        Given: FakeFileWatcher
        When: stop() is called multiple times
        Then: No error is raised

        Purpose: Verifies stop() is safe to call multiple times.
        Quality Contribution: Robust shutdown behavior.
        """
        from fs2.core.adapters.file_watcher_adapter_fake import FakeFileWatcher

        watcher = FakeFileWatcher()

        # Should not raise
        watcher.stop()
        watcher.stop()
        watcher.stop()

    @pytest.mark.asyncio
    async def test_fake_file_watcher_different_change_types(self):
        """
        Given: FakeFileWatcher with different change types
        When: watch() yields
        Then: Change types are preserved correctly

        Purpose: Verifies all change types work.
        Quality Contribution: Covers added, modified, deleted.
        """
        from fs2.core.adapters.file_watcher_adapter_fake import FakeFileWatcher

        watcher = FakeFileWatcher()
        watcher.add_changes({("added", "/new.py")})
        watcher.add_changes({("modified", "/existing.py")})
        watcher.add_changes({("deleted", "/removed.py")})

        changes_list = []
        async for changes in watcher.watch():
            changes_list.append(changes)

        assert len(changes_list) == 3
        assert ("added", "/new.py") in changes_list[0]
        assert ("modified", "/existing.py") in changes_list[1]
        assert ("deleted", "/removed.py") in changes_list[2]
