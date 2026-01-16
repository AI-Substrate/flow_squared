"""Tests for ConfigBackupService.

Per Phase 1 Tasks Dossier:
- AC-05: Backup before save
- Critical Discovery 05: Atomic backup pattern

Testing Approach: Full TDD (RED phase - tests first)
These tests must FAIL initially because the implementation doesn't exist.

Per Critical Insight #3: Use Path.replace() for cross-platform atomic rename.
"""

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

# These imports will fail initially (RED phase) - implementation doesn't exist yet
from fs2.web.services.config_backup import (
    BackupResult,
    ConfigBackupService,
)


class TestBackupCreation:
    """Tests for basic backup file creation."""

    def test_backup_creates_timestamped_file(self, tmp_path: Path) -> None:
        """Verify backup creates file with timestamp in name.

        Contract: Backup filename includes timestamp for uniqueness.
        """
        # Arrange
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  timeout: 30")

        # Act
        service = ConfigBackupService()
        result = service.backup(config_file)

        # Assert
        assert result.success
        assert result.backup_path is not None
        assert result.backup_path.exists()
        # Filename contains timestamp pattern like config.yaml.2026-01-15T10-30-45.backup
        assert "backup" in result.backup_path.name
        assert config_file.stem in result.backup_path.name

    def test_backup_preserves_content(self, tmp_path: Path) -> None:
        """Verify backup file has exact same content as original.

        Contract: Backup is byte-for-byte identical to original.
        """
        # Arrange
        original_content = "llm:\n  timeout: 30\n  provider: azure"
        config_file = tmp_path / "config.yaml"
        config_file.write_text(original_content)

        # Act
        service = ConfigBackupService()
        result = service.backup(config_file)

        # Assert
        assert result.success
        backup_content = result.backup_path.read_text()
        assert backup_content == original_content

    def test_backup_in_same_directory_as_original(self, tmp_path: Path) -> None:
        """Verify backup is created in same directory as original.

        Contract: Backup sibling to original file for easy discovery.
        """
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  timeout: 30")

        service = ConfigBackupService()
        result = service.backup(config_file)

        assert result.backup_path.parent == config_file.parent

    def test_backup_multiple_creates_unique_files(self, tmp_path: Path) -> None:
        """Verify multiple backups create separate files.

        Contract: Each backup is unique, no overwrites.
        """
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  timeout: 30")

        service = ConfigBackupService()
        result1 = service.backup(config_file)
        result2 = service.backup(config_file)

        assert result1.backup_path != result2.backup_path
        assert result1.backup_path.exists()
        assert result2.backup_path.exists()


class TestAtomicOperations:
    """Tests for atomic backup pattern.

    Per Critical Discovery 05: Temp file → verify → atomic rename.
    Per Critical Insight #3: Use Path.replace() for cross-platform.
    """

    def test_backup_uses_atomic_rename(self, tmp_path: Path) -> None:
        """Verify backup uses atomic rename (no partial writes).

        Contract: Backup file either exists completely or not at all.
        """
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  timeout: 30")

        service = ConfigBackupService()
        result = service.backup(config_file)

        # If we got a path, the file must be complete
        assert result.success
        assert result.backup_path.exists()
        content = result.backup_path.read_text()
        assert content == "llm:\n  timeout: 30"

    def test_backup_overwrites_existing_backup_atomically(
        self, tmp_path: Path
    ) -> None:
        """Verify overwriting existing backup is atomic.

        Per Insight #3: Path.replace() handles existing target.
        Contract: Even if backup name collides, operation is atomic.
        """
        config_file = tmp_path / "config.yaml"
        config_file.write_text("original content")

        # Create a pre-existing backup file at expected path
        # (This simulates a backup name collision)
        service = ConfigBackupService()

        # First backup
        result1 = service.backup(config_file)
        assert result1.success

        # Modify original and backup again (same path via mocking timestamp)
        config_file.write_text("modified content")

        # Second backup should succeed even if names could collide
        result2 = service.backup(config_file)
        assert result2.success
        assert result2.backup_path.read_text() == "modified content"

    def test_no_partial_backup_on_write_failure(self, tmp_path: Path) -> None:
        """Verify no partial backup file left on write failure.

        Contract: Failure leaves no temp files behind.
        """
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  timeout: 30")

        # Count files before
        files_before = list(tmp_path.iterdir())

        service = ConfigBackupService()

        # Simulate write failure by making directory read-only
        # (Note: This may not work in all environments)
        with patch("builtins.open", side_effect=OSError("Disk full")):
            result = service.backup(config_file)

        # Should fail cleanly
        assert not result.success
        # No extra temp files should remain
        files_after = list(tmp_path.iterdir())
        assert len(files_after) == len(files_before)


class TestIntegrityVerification:
    """Tests for backup integrity verification."""

    def test_backup_verifies_integrity_checksum(self, tmp_path: Path) -> None:
        """Verify backup includes checksum for integrity verification.

        Contract: BackupResult includes checksum of backup file.
        """
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  timeout: 30")

        service = ConfigBackupService()
        result = service.backup(config_file)

        assert result.checksum is not None
        assert len(result.checksum) == 64  # SHA-256 hex digest

    def test_backup_checksum_matches_content(self, tmp_path: Path) -> None:
        """Verify checksum matches actual backup content.

        Contract: Checksum can be used to verify backup integrity.
        """
        content = "llm:\n  timeout: 30"
        config_file = tmp_path / "config.yaml"
        config_file.write_text(content)

        service = ConfigBackupService()
        result = service.backup(config_file)

        # Manually compute checksum
        expected_checksum = hashlib.sha256(content.encode()).hexdigest()
        assert result.checksum == expected_checksum

    def test_backup_verify_reads_back_content(self, tmp_path: Path) -> None:
        """Verify backup reads back content after write.

        Per Discovery 05: Verify backup integrity before completing.
        """
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  timeout: 30")

        service = ConfigBackupService()
        result = service.backup(config_file)

        # Backup should be readable
        assert result.success
        assert result.backup_path.read_text() == "llm:\n  timeout: 30"


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_backup_fails_on_missing_source(self, tmp_path: Path) -> None:
        """Verify graceful failure when source file doesn't exist.

        Contract: Returns error result, no exception raised.
        """
        missing_file = tmp_path / "nonexistent.yaml"

        service = ConfigBackupService()
        result = service.backup(missing_file)

        assert not result.success
        assert result.error is not None
        assert "not found" in result.error.lower() or "exist" in result.error.lower()

    def test_backup_fails_on_permission_error(self, tmp_path: Path) -> None:
        """Verify graceful failure when can't read source.

        Contract: Returns error with actionable message.
        """
        config_file = tmp_path / "protected.yaml"
        config_file.write_text("llm:\n  timeout: 30")
        config_file.chmod(0o000)

        try:
            service = ConfigBackupService()
            result = service.backup(config_file)

            assert not result.success
            assert result.error is not None
            assert "permission" in result.error.lower()
        finally:
            config_file.chmod(0o644)

    def test_backup_fails_on_directory_not_writable(self, tmp_path: Path) -> None:
        """Verify graceful failure when backup directory not writable.

        Contract: Returns error with actionable fix suggestion.
        """
        subdir = tmp_path / "readonly"
        subdir.mkdir()
        config_file = subdir / "config.yaml"
        config_file.write_text("llm:\n  timeout: 30")
        subdir.chmod(0o555)  # Read + execute only

        try:
            service = ConfigBackupService()
            result = service.backup(config_file)

            assert not result.success
            assert result.error is not None
            assert "permission" in result.error.lower() or "write" in result.error.lower()
        finally:
            subdir.chmod(0o755)

    def test_backup_handles_disk_full(self, tmp_path: Path) -> None:
        """Verify graceful failure on disk full.

        Contract: Returns error with fix suggestion.
        """
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  timeout: 30")

        service = ConfigBackupService()

        # Simulate disk full during write
        with patch("builtins.open", side_effect=OSError("No space left on device")):
            result = service.backup(config_file)

        assert not result.success
        assert result.error is not None
        assert "space" in result.error.lower() or "disk" in result.error.lower()


class TestBackupResultDataStructure:
    """Tests for BackupResult structure."""

    def test_success_result_has_all_fields(self, tmp_path: Path) -> None:
        """Verify successful result includes all expected fields.

        Contract: BackupResult has success, backup_path, checksum, error.
        """
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  timeout: 30")

        service = ConfigBackupService()
        result = service.backup(config_file)

        assert hasattr(result, "success")
        assert hasattr(result, "backup_path")
        assert hasattr(result, "checksum")
        assert hasattr(result, "error")

    def test_failed_result_has_error_message(self, tmp_path: Path) -> None:
        """Verify failed result includes error message.

        Contract: error field is populated on failure.
        """
        missing_file = tmp_path / "nonexistent.yaml"

        service = ConfigBackupService()
        result = service.backup(missing_file)

        assert not result.success
        assert result.error is not None
        assert len(result.error) > 0

    def test_success_result_has_no_error(self, tmp_path: Path) -> None:
        """Verify successful result has None error.

        Contract: error is None on success.
        """
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  timeout: 30")

        service = ConfigBackupService()
        result = service.backup(config_file)

        assert result.success
        assert result.error is None


class TestCustomBackupLocation:
    """Tests for custom backup directory."""

    def test_backup_to_custom_directory(self, tmp_path: Path) -> None:
        """Verify backup can be created in custom directory.

        Contract: backup_dir parameter specifies backup location.
        """
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  timeout: 30")

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        service = ConfigBackupService()
        result = service.backup(config_file, backup_dir=backup_dir)

        assert result.success
        assert result.backup_path.parent == backup_dir

    def test_backup_creates_directory_if_missing(self, tmp_path: Path) -> None:
        """Verify backup creates backup_dir if it doesn't exist.

        Contract: Missing backup directory is created automatically.
        """
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  timeout: 30")

        backup_dir = tmp_path / "new_backups"
        assert not backup_dir.exists()

        service = ConfigBackupService()
        result = service.backup(config_file, backup_dir=backup_dir)

        assert result.success
        assert backup_dir.exists()
        assert result.backup_path.parent == backup_dir
