"""FakeFileWatcher - Test double implementing FileWatcherAdapter ABC.

Provides a configurable fake for testing components that depend on FileWatcherAdapter.
Uses "Finite Queue + Auto-Stop" pattern for deterministic, timeout-free tests.

Architecture:
- Inherits from FileWatcherAdapter ABC
- Emits pre-programmed changes via add_changes()
- Auto-stops when queue is empty (no timeouts needed)
- Tracks watch() calls for test verification

Per Critical Finding 06: Use FakeFileWatcher (not mocks), state-driven assertions.
Per DYK-4: Finite Queue + Auto-Stop pattern for deterministic tests.
"""

from collections.abc import AsyncIterator

from fs2.core.adapters.file_watcher_adapter import FileChange, FileWatcherAdapter


class FakeFileWatcher(FileWatcherAdapter):
    """Fake implementation of FileWatcherAdapter for testing.

    Uses "Finite Queue + Auto-Stop" pattern:
    1. add_changes() queues pre-programmed change sets
    2. watch() yields each change set in order
    3. After queue empty, automatically raises StopAsyncIteration
    4. Service sees watcher stop and exits gracefully

    This enables deterministic tests without timeouts or flakiness.

    Usage in tests:
        ```python
        watcher = FakeFileWatcher()
        watcher.add_changes({("modified", "/path/to/a.py")})
        watcher.add_changes({("modified", "/path/to/b.py")})

        changes_received = []
        async for changes in watcher.watch():
            changes_received.append(changes)

        assert len(changes_received) == 2
        ```
    """

    def __init__(self) -> None:
        """Initialize empty change queue and counters."""
        self._change_queue: list[set[FileChange]] = []
        self._stopped: bool = False
        self._watch_call_count: int = 0

    def add_changes(self, changes: set[FileChange]) -> None:
        """Queue a batch of changes to be yielded by watch().

        Args:
            changes: Set of (change_type, path) tuples to yield.
                     change_type: "added", "modified", or "deleted"
                     path: Absolute path string to the changed file

        Example:
            >>> watcher.add_changes({("modified", "/path/to/file.py")})
            >>> watcher.add_changes({
            ...     ("added", "/new.py"),
            ...     ("deleted", "/old.py"),
            ... })
        """
        self._change_queue.append(changes)

    @property
    def watch_call_count(self) -> int:
        """Number of times watch() has yielded.

        Useful for verifying watch() was actually called in tests.
        """
        return self._watch_call_count

    async def watch(self) -> AsyncIterator[set[FileChange]]:
        """Yield pre-programmed changes, then auto-stop.

        Yields each queued change set in order until:
        - Queue is empty (auto-stop, raises StopAsyncIteration)
        - stop() is called (breaks immediately)

        Yields:
            Set of (change_type, path) tuples from the queue.

        Example:
            >>> watcher = FakeFileWatcher()
            >>> watcher.add_changes({("modified", "/file.py")})
            >>> async for changes in watcher.watch():
            ...     print(changes)
            {('modified', '/file.py')}
            # Loop exits naturally after queue empty
        """
        while self._change_queue and not self._stopped:
            changes = self._change_queue.pop(0)
            self._watch_call_count += 1
            yield changes

        # Auto-stop when queue empty - just return (StopAsyncIteration implicit)

    def stop(self) -> None:
        """Request graceful shutdown of watch loop.

        This is idempotent - safe to call multiple times.
        The watch() generator will exit at next opportunity.
        """
        self._stopped = True
