"""FileWatcherAdapter ABC interface.

Abstract base class defining the file watching contract.
Implementations monitor directories for file changes and yield
change events asynchronously.

Architecture:
- This file: ABC definition only
- Implementations: file_watcher_adapter_fake.py, file_watcher_adapter_watchfiles.py

Per Critical Finding 02: Adapter ABC with Dual Implementation Pattern.
Per spec: watch() async generator, stop() method.

Change Event Format:
    Each change is a tuple of (change_type, path) where:
    - change_type: "added", "modified", or "deleted"
    - path: Absolute path string to the changed file

Example:
    >>> async for changes in watcher.watch():
    ...     for change_type, path in changes:
    ...         print(f"{change_type}: {path}")
    modified: /path/to/file.py
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

# Type alias for file change events
# Each change is (change_type, absolute_path)
# change_type is one of: "added", "modified", "deleted"
FileChange = tuple[str, str]


class FileWatcherAdapter(ABC):
    """Abstract base class for file watching adapters.

    This interface defines the contract for monitoring directories
    for file changes and yielding events asynchronously.

    Implementations must:
    - Provide watch() as an async generator yielding change sets
    - Provide stop() to gracefully terminate the watch loop
    - Filter changes according to gitignore patterns
    - Debounce rapid changes per configuration

    Lifecycle:
        1. Construct watcher with config and paths
        2. Call watch() to start monitoring (async generator)
        3. Process yielded change sets
        4. Call stop() when shutting down

    Thread Safety:
        stop() may be called from a different thread/task than watch().
        Implementations must handle this safely.

    See Also:
        - file_watcher_adapter_fake.py: Test double implementation
        - file_watcher_adapter_watchfiles.py: Production implementation
    """

    @abstractmethod
    def watch(self) -> AsyncIterator[set[FileChange]]:
        """Monitor directories for file changes.

        Yields sets of file changes as they are detected. Each yield
        represents a batch of changes collected during the debounce window.

        Yields:
            Set of (change_type, path) tuples where:
            - change_type: One of "added", "modified", "deleted"
            - path: Absolute path string to the changed file

        Behavior:
            - Respects gitignore patterns and additional_ignores
            - Batches rapid changes according to debounce_ms setting
            - Continues until stop() is called or an error occurs

        Example:
            >>> async for changes in watcher.watch():
            ...     for change_type, path in changes:
            ...         if path.endswith('.py'):
            ...             trigger_scan()

        Note:
            This is an async generator. Use `async for` to iterate.
            The generator exits cleanly when stop() is called.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Request graceful shutdown of the watch loop.

        Signals the watch() generator to stop yielding and exit cleanly.
        May be called from a different thread/task than watch().

        This method should:
        - Be idempotent (safe to call multiple times)
        - Not block (return immediately)
        - Cause watch() to exit at next opportunity

        The watch() generator should complete any in-progress yield
        and then raise StopAsyncIteration.
        """
        ...
