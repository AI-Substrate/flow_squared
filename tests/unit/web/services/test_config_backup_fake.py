"""Tests for FakeConfigBackupService.

Per Phase 1 Tasks Dossier:
- T009: Tests verify fake tracks backup operations, supports simulate_error
- Pattern: Follow fs2 fake pattern (call tracking, error simulation)

Testing Approach: Full TDD (RED phase - tests first)
"""

from pathlib import Path

import pytest

# These imports will fail initially (RED phase)
from fs2.web.services.config_backup_fake import FakeConfigBackupService
from fs2.web.services.config_backup import BackupResult


class TestCallTracking:
    """Tests for call tracking functionality."""

    def test_tracks_backup_calls(self, tmp_path: Path) -> None:
        """Verify backup() calls are tracked.

        Contract: Each backup() call records path in call_history.
        """
        fake = FakeConfigBackupService()
        path1 = tmp_path / "config1.yaml"
        path2 = tmp_path / "config2.yaml"

        fake.backup(path1)
        fake.backup(path2)

        assert len(fake.call_history) == 2
        assert fake.call_history[0] == ("backup", path1, None)
        assert fake.call_history[1] == ("backup", path2, None)

    def test_tracks_backup_dir_param(self, tmp_path: Path) -> None:
        """Verify backup_dir is tracked in call history."""
        fake = FakeConfigBackupService()
        source = tmp_path / "config.yaml"
        backup_dir = tmp_path / "backups"

        fake.backup(source, backup_dir=backup_dir)

        assert fake.call_history[0] == ("backup", source, backup_dir)

    def test_call_history_starts_empty(self) -> None:
        """Verify call_history is empty on creation."""
        fake = FakeConfigBackupService()
        assert fake.call_history == []

    def test_clear_history(self, tmp_path: Path) -> None:
        """Verify call history can be cleared."""
        fake = FakeConfigBackupService()
        fake.backup(tmp_path / "test.yaml")
        assert len(fake.call_history) == 1

        fake.clear()
        assert fake.call_history == []


class TestConfigurableResponses:
    """Tests for configurable response values."""

    def test_returns_default_success_result(self, tmp_path: Path) -> None:
        """Verify default result is success with generated path."""
        fake = FakeConfigBackupService()
        result = fake.backup(tmp_path / "config.yaml")

        assert isinstance(result, BackupResult)
        assert result.success is True
        assert result.backup_path is not None
        assert result.checksum is not None
        assert result.error is None

    def test_set_result_returned_on_backup(self, tmp_path: Path) -> None:
        """Verify set_result() configures returned value.

        Contract: Custom result can be injected for testing.
        """
        custom_result = BackupResult(
            success=True,
            backup_path=Path("/custom/backup.yaml"),
            checksum="abc123",
        )

        fake = FakeConfigBackupService()
        fake.set_result(custom_result)

        result = fake.backup(tmp_path / "config.yaml")
        assert result.backup_path == Path("/custom/backup.yaml")
        assert result.checksum == "abc123"

    def test_set_failure_result(self, tmp_path: Path) -> None:
        """Verify failure result can be configured."""
        fake = FakeConfigBackupService()
        fake.set_result(BackupResult(
            success=False,
            error="Simulated disk full",
        ))

        result = fake.backup(tmp_path / "config.yaml")
        assert not result.success
        assert result.error == "Simulated disk full"


class TestErrorSimulation:
    """Tests for error simulation functionality."""

    def test_simulate_error_raises_on_backup(self, tmp_path: Path) -> None:
        """Verify simulate_error causes backup() to raise.

        Contract: Simulated errors propagate to callers.
        """
        fake = FakeConfigBackupService()
        fake.simulate_error = IOError("Simulated I/O failure")

        with pytest.raises(IOError, match="Simulated I/O failure"):
            fake.backup(tmp_path / "config.yaml")

    def test_simulate_error_clears_on_none(self, tmp_path: Path) -> None:
        """Verify setting simulate_error=None clears error."""
        fake = FakeConfigBackupService()
        fake.simulate_error = IOError("Error")
        fake.simulate_error = None

        # Should not raise
        result = fake.backup(tmp_path / "config.yaml")
        assert isinstance(result, BackupResult)

    def test_error_simulation_still_tracks_call(self, tmp_path: Path) -> None:
        """Verify calls are tracked even when error is simulated."""
        fake = FakeConfigBackupService()
        fake.simulate_error = RuntimeError("Test error")
        source = tmp_path / "config.yaml"

        with pytest.raises(RuntimeError):
            fake.backup(source)

        # Call should still be tracked
        assert len(fake.call_history) == 1
        assert fake.call_history[0] == ("backup", source, None)


class TestUsagePatterns:
    """Tests demonstrating usage patterns for Phase 3+ tests."""

    def test_verify_backup_called_before_save(self, tmp_path: Path) -> None:
        """Demonstrate fake usage to verify backup precedes save.

        Example of how Phase 3 config editor tests will use this fake
        to ensure backup is called before saving changes.
        """
        fake = FakeConfigBackupService()
        config_path = tmp_path / ".fs2" / "config.yaml"

        # Simulate what config editor service would do
        fake.backup(config_path)

        # Assert backup was called with correct path
        assert len(fake.call_history) == 1
        assert fake.call_history[0][1] == config_path

    def test_simulate_backup_failure_handling(self, tmp_path: Path) -> None:
        """Demonstrate testing error handling when backup fails."""
        fake = FakeConfigBackupService()
        fake.set_result(BackupResult(
            success=False,
            error="Disk full",
        ))

        result = fake.backup(tmp_path / "config.yaml")

        # Service should handle this gracefully
        assert not result.success
        assert "disk" in result.error.lower()
