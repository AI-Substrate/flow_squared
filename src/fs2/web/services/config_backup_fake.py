"""FakeConfigBackupService - Test double for backup operations.

Per Phase 1 Foundation:
- T010: Implement with call_history and simulate_error
- Pattern: Follow fs2 fake pattern

Usage for Phase 3+ tests:
    ```python
    fake = FakeConfigBackupService()

    # Use in config editor service tests
    service = ConfigEditorService(backup_service=fake)
    service.save_config({"llm": {"timeout": 60}})

    # Assert backup was called before save
    assert len(fake.call_history) == 1
    assert fake.call_history[0][0] == "backup"
    ```
"""

from pathlib import Path

from fs2.web.services.config_backup import BackupResult


class FakeConfigBackupService:
    """Test double for ConfigBackupService.

    Provides:
    - call_history: List of (method, source_path, backup_dir) tuples
    - set_result(): Configure what backup() returns
    - simulate_error: Set to Exception to make backup() raise

    Does NOT create actual backup files - returns configurable results.
    """

    def __init__(self) -> None:
        """Initialize with empty state."""
        self._call_history: list[tuple[str, Path, Path | None]] = []
        self._result: BackupResult | None = None
        self.simulate_error: Exception | None = None

    @property
    def call_history(self) -> list[tuple[str, Path, Path | None]]:
        """Get list of method calls made.

        Returns:
            List of (method_name, source_path, backup_dir) tuples.
        """
        return self._call_history

    def clear(self) -> None:
        """Clear call history.

        Useful for test isolation between assertions.
        """
        self._call_history.clear()

    def set_result(self, result: BackupResult) -> None:
        """Configure the result returned by backup().

        Args:
            result: BackupResult to return on backup() calls.
        """
        self._result = result

    def backup(
        self,
        source_path: Path,
        backup_dir: Path | None = None,
    ) -> BackupResult:
        """Fake backup that returns configured result.

        Records call in history, then returns configured result
        or raises if simulate_error is set.

        Args:
            source_path: Path to file being "backed up".
            backup_dir: Optional backup directory.

        Returns:
            Configured BackupResult (default: success with generated path).

        Raises:
            Exception: If simulate_error is set to an exception.
        """
        self._call_history.append(("backup", source_path, backup_dir))

        if self.simulate_error is not None:
            raise self.simulate_error

        if self._result is not None:
            return self._result

        # Default success result
        return BackupResult(
            success=True,
            backup_path=source_path.with_suffix(".backup"),
            checksum="fake-checksum-" + source_path.name,
        )
