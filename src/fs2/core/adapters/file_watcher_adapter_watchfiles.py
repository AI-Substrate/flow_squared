"""WatchfilesAdapter - Production implementation of FileWatcherAdapter.

Provides file watching using the watchfiles library with gitignore filtering.
Uses pathspec for .gitignore pattern matching.

Architecture:
- Inherits from FileWatcherAdapter ABC
- Wraps watchfiles.awatch() for cross-platform file watching
- Uses GitignoreFilter for pattern matching
- Supports debouncing via watchfiles configuration

Per Finding 09: Gitignore Reuse via pathspec library.
Per Critical Finding 02: Adapter ABC with Dual Implementation Pattern.
"""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pathspec
import watchfiles
from watchfiles import Change, DefaultFilter

from fs2.core.adapters.file_watcher_adapter import FileChange, FileWatcherAdapter


class GitignoreFilter(DefaultFilter):
    """Filter that respects .gitignore patterns and additional ignores.

    Extends watchfiles.DefaultFilter to add:
    - Loading of .gitignore patterns from root directory
    - Support for additional_ignores from WatchConfig
    - Pathspec-based pattern matching
    - Built-in patterns for common editor temp files

    Usage:
        ```python
        filter_ = GitignoreFilter(
            root_path=Path("."),
            additional_ignores=["*.tmp", ".cache/"]
        )
        # Returns False for ignored files (watchfiles convention)
        filter_(Change.modified, "/path/to/file.pyc")  # False if *.pyc in .gitignore
        ```

    Note:
        watchfiles convention: __call__ returns True to INCLUDE, False to EXCLUDE.
    """

    # Built-in patterns for common editor temp files
    _BUILTIN_IGNORES = [
        "*.tmp.*",  # Editor temp files like .tmp.1234.5678
        "*~",  # Emacs/vim backup files
        "*.swp",  # Vim swap files
        "*.swo",  # Vim swap files
        ".#*",  # Emacs lock files
        "#*#",  # Emacs auto-save files
    ]

    def __init__(
        self,
        root_path: Path,
        additional_ignores: list[str] | None = None,
    ) -> None:
        """Initialize filter with gitignore patterns.

        Args:
            root_path: Root directory to load .gitignore from.
            additional_ignores: Extra patterns to ignore (from WatchConfig).
        """
        super().__init__()
        self._root_path = root_path
        self._patterns: list[str] = list(self._BUILTIN_IGNORES)  # Start with built-ins

        # Load .gitignore if it exists
        gitignore_path = root_path / ".gitignore"
        if gitignore_path.exists():
            gitignore_content = gitignore_path.read_text()
            for line in gitignore_content.splitlines():
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    self._patterns.append(line)

        # Add additional ignores
        if additional_ignores:
            self._patterns.extend(additional_ignores)

        # Create pathspec matcher
        if self._patterns:
            self._spec = pathspec.PathSpec.from_lines("gitwildmatch", self._patterns)
        else:
            self._spec = None

    def __call__(self, change: Change, path: str) -> bool:
        """Check if a path should be included (not ignored).

        Args:
            change: Type of change (added, modified, deleted).
            path: Absolute path to the file.

        Returns:
            True to include (not ignored), False to exclude (ignored).
            This follows watchfiles convention.
        """
        # First, apply parent filter
        if not super().__call__(change, path):
            return False

        # No patterns = include everything
        if self._spec is None:
            return True

        # Get path relative to root for pattern matching
        try:
            rel_path = Path(path).relative_to(self._root_path)
            # Check if any pattern matches
            if self._spec.match_file(str(rel_path)):
                return False  # Ignored
            # Also check with trailing slash for directories
            if Path(path).is_dir() and self._spec.match_file(str(rel_path) + "/"):
                return False
        except ValueError:
            # Path not relative to root - don't filter
            pass

        return True  # Not ignored


# Map watchfiles Change enum to our string change types
_CHANGE_TYPE_MAP = {
    Change.added: "added",
    Change.modified: "modified",
    Change.deleted: "deleted",
}


class WatchfilesAdapter(FileWatcherAdapter):
    """Production implementation of FileWatcherAdapter using watchfiles.

    Wraps watchfiles.awatch() to provide:
    - Cross-platform file watching (Linux, macOS, Windows)
    - Debouncing of rapid changes via debounce_ms
    - Gitignore pattern filtering via GitignoreFilter
    - Graceful stop via asyncio.Event

    Usage:
        ```python
        adapter = WatchfilesAdapter(
            watch_paths=[Path("./src"), Path("./tests")],
            debounce_ms=1600,
            additional_ignores=["*.tmp", ".cache/"],
        )

        async for changes in adapter.watch():
            for change_type, path in changes:
                print(f"{change_type}: {path}")

        # To stop:
        adapter.stop()
        ```

    Note:
        The watch() generator respects stop() being called from another task.
        It will complete any in-progress yield and then exit cleanly.
    """

    def __init__(
        self,
        watch_paths: list[Path],
        debounce_ms: int = 1600,
        additional_ignores: list[str] | None = None,
    ) -> None:
        """Initialize the watchfiles adapter.

        Args:
            watch_paths: List of directories to watch for changes.
            debounce_ms: Debounce time in milliseconds (default: 1600).
                         Rapid changes within this window are batched.
            additional_ignores: Extra patterns to ignore beyond .gitignore.
        """
        self._watch_paths = watch_paths
        self._debounce_ms = debounce_ms
        self._additional_ignores = additional_ignores or []
        self._stop_event = asyncio.Event()

    async def watch(self) -> AsyncIterator[set[FileChange]]:
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
        """
        if not self._watch_paths:
            return

        # Use the first watch path for gitignore (typically project root)
        root_path = self._watch_paths[0]

        # Create filter with gitignore support
        watch_filter = GitignoreFilter(
            root_path=root_path,
            additional_ignores=self._additional_ignores,
        )

        # Convert paths to strings for watchfiles
        paths = [str(p) for p in self._watch_paths]

        # Use watchfiles.awatch with our filter and debounce settings
        # We need to handle the stop event in the loop
        try:
            async for raw_changes in watchfiles.awatch(
                *paths,
                watch_filter=watch_filter,
                debounce=self._debounce_ms,
                stop_event=self._stop_event,
            ):
                # Convert watchfiles Change tuples to our format
                # watchfiles yields: set[tuple[Change, str]]
                changes: set[FileChange] = set()
                for change, path in raw_changes:
                    change_type = _CHANGE_TYPE_MAP.get(change, "modified")
                    changes.add((change_type, path))

                if changes:
                    yield changes

                # Check if stop was requested during processing
                if self._stop_event.is_set():
                    break

        except asyncio.CancelledError:
            # Graceful exit on task cancellation
            pass

    def stop(self) -> None:
        """Request graceful shutdown of the watch loop.

        Signals the watch() generator to stop yielding and exit cleanly.
        May be called from a different thread/task than watch().

        This method is idempotent - safe to call multiple times.
        """
        self._stop_event.set()
