"""FileScanner ABC interface.

Abstract base class defining the file scanning contract.
Implementations discover source files in directories while
respecting gitignore patterns.

Architecture:
- This file: ABC definition only
- Implementations: file_scanner_fake.py, file_scanner_impl.py

Per Critical Finding 02: Adapter ABC with Dual Implementation Pattern.
Per Critical Finding 01: Implementations receive ConfigurationService.

Lifecycle Contract:
- scan() must be called before should_ignore()
- should_ignore() raises FileScannerError if scan() not called
- This allows patterns to be loaded during scan traversal
"""

from abc import ABC, abstractmethod
from pathlib import Path

from fs2.core.models.scan_result import ScanResult


class FileScanner(ABC):
    """Abstract base class for file scanning adapters.

    This interface defines the contract for discovering source files
    in a codebase while respecting gitignore patterns.

    Implementations must:
    - Receive ConfigurationService in constructor (not ScanConfig directly)
    - Return list[ScanResult] with path and size information
    - Load gitignore patterns during scan() traversal
    - Translate OS errors to FileScannerError

    Lifecycle:
        1. Construct scanner with ConfigurationService
        2. Call scan() to discover files (loads gitignore patterns)
        3. Optionally call should_ignore() to check specific paths

    Warning:
        should_ignore() requires scan() to be called first.
        Calling should_ignore() before scan() raises FileScannerError.

    See Also:
        - file_scanner_fake.py: Test double implementation
        - file_scanner_impl.py: Production FileSystemScanner implementation
    """

    @abstractmethod
    def scan(self) -> list[ScanResult]:
        """Discover source files in configured scan paths.

        Recursively traverses directories specified in ScanConfig.scan_paths,
        respecting gitignore patterns at each level.

        Missing or invalid scan paths are skipped with a warning rather than
        aborting. Check missing_paths after scan() for skipped paths.

        Returns:
            List of ScanResult containing path and size_bytes for each file.
            Does not include directories, only files.

        Raises:
            FileScannerError: If scan is inaccessible due to permissions.
        """
        ...

    @property
    @abstractmethod
    def missing_paths(self) -> list[str]:
        """Scan paths that were skipped because they don't exist or aren't directories.

        Populated during scan(). Returns empty list before scan() is called
        or when all scan paths are valid.

        Returns:
            List of human-readable error strings for each skipped path.
        """
        ...

    @abstractmethod
    def should_ignore(self, path: Path) -> bool:
        """Check if a path matches gitignore patterns.

        Useful for querying whether a specific path would be excluded
        by the loaded gitignore patterns.

        Args:
            path: Path to check against gitignore patterns.

        Returns:
            True if path should be ignored, False otherwise.

        Raises:
            FileScannerError: If scan() has not been called first.
                Patterns are loaded during scan traversal.

        Warning:
            Must call scan() before calling this method.
        """
        ...
