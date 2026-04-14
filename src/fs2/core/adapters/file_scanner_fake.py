"""FakeFileScanner - Test double implementing FileScanner ABC.

Provides a configurable fake for testing components that depend on FileScanner.
Follows the established adapter fake pattern with configurable results
and call history recording.

Architecture:
- Inherits from FileScanner ABC
- Receives ConfigurationService (registry) via constructor
- Returns configured results without file system access
- Records call history for test verification

Per Critical Finding 01: Receives ConfigurationService, not extracted config.
Per Critical Finding 02: Adapter ABC with Dual Implementation Pattern.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fs2.config.objects import ScanConfig
from fs2.core.adapters.file_scanner import FileScanner
from fs2.core.models.scan_result import ScanResult

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


class FakeFileScanner(FileScanner):
    """Fake implementation of FileScanner for testing.

    This implementation provides deterministic behavior for testing:
    - Returns pre-configured ScanResult list from scan()
    - Returns pre-configured boolean from should_ignore()
    - Records all method calls for verification

    Usage in tests:
        ```python
        config = FakeConfigurationService(ScanConfig())
        scanner = FakeFileScanner(config)

        # Configure results
        scanner.set_results([
            ScanResult(path=Path("src/main.py"), size_bytes=1024),
        ])

        # Use in test
        results = scanner.scan()
        assert len(results) == 1

        # Verify calls
        assert scanner.call_history[0]["method"] == "scan"
        ```
    """

    def __init__(self, config: "ConfigurationService"):
        """Initialize with ConfigurationService registry.

        Args:
            config: ConfigurationService registry.
                    Adapter will call config.require(ScanConfig) internally.

        Raises:
            MissingConfigurationError: If ScanConfig not in registry.
        """
        # Extract config internally (per Critical Finding 01)
        self._scan_config = config.require(ScanConfig)
        self._results_to_return: list[ScanResult] = []
        self._ignored_paths: set[Path] = set()
        self._call_history: list[dict[str, Any]] = []
        self._missing_paths_to_return: list[str] = []

    @property
    def missing_paths(self) -> list[str]:
        """Scan paths that were skipped. Configurable via set_missing_paths()."""
        return list(self._missing_paths_to_return)

    def set_missing_paths(self, paths: list[str]) -> None:
        """Configure missing paths to return from the missing_paths property.

        Args:
            paths: List of error strings for missing/invalid scan paths.
        """
        self._missing_paths_to_return = paths

    @property
    def call_history(self) -> list[dict[str, Any]]:
        """Access recorded calls for test assertions.

        Returns:
            List of dicts with 'method', 'args', 'kwargs' for each call.
        """
        return self._call_history

    def set_results(self, results: list[ScanResult]) -> None:
        """Configure results to return from scan().

        Args:
            results: List of ScanResult to return.
        """
        self._results_to_return = results

    def set_ignored_paths(self, paths: set[Path]) -> None:
        """Configure paths that should_ignore() returns True for.

        Args:
            paths: Set of paths to treat as ignored.
        """
        self._ignored_paths = paths

    def scan(self) -> list[ScanResult]:
        """Return configured results without file system access.

        Returns:
            List of pre-configured ScanResult objects.
        """
        self._call_history.append(
            {
                "method": "scan",
                "args": (),
                "kwargs": {},
            }
        )
        return self._results_to_return

    def should_ignore(self, path: Path) -> bool:
        """Check if path is in configured ignored paths.

        Args:
            path: Path to check.

        Returns:
            True if path in ignored_paths, False otherwise.
        """
        self._call_history.append(
            {
                "method": "should_ignore",
                "args": (path,),
                "kwargs": {},
            }
        )
        return path in self._ignored_paths
