"""ConfigBackupService - Atomic configuration backup.

Per Phase 1 Foundation:
- AC-05: Backup before save
- Critical Discovery 05: Temp file → verify → atomic rename pattern

Per Critical Insight #3: Use Path.replace() for cross-platform atomic rename.
Windows rename() fails if target exists; replace() handles this atomically.
"""

import contextlib
import hashlib
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class BackupResult:
    """Result of a backup operation.

    Attributes:
        success: True if backup completed successfully
        backup_path: Path to the backup file (None on failure)
        checksum: SHA-256 hex digest of backup content (None on failure)
        error: Error message if backup failed (None on success)
    """

    success: bool
    backup_path: Path | None = None
    checksum: str | None = None
    error: str | None = None


class ConfigBackupService:
    """Service for creating atomic configuration backups.

    Creates timestamped backups using the pattern:
    1. Write content to temporary file
    2. Compute and verify checksum
    3. Atomic rename temp → backup

    Uses Path.replace() instead of Path.rename() for cross-platform
    compatibility (Windows rename() fails if target exists).

    Usage:
        ```python
        service = ConfigBackupService()
        result = service.backup(Path(".fs2/config.yaml"))

        if result.success:
            print(f"Backup created at: {result.backup_path}")
            print(f"Checksum: {result.checksum}")
        else:
            print(f"Backup failed: {result.error}")
        ```
    """

    def backup(
        self,
        source_path: Path,
        backup_dir: Path | None = None,
    ) -> BackupResult:
        """Create an atomic backup of a configuration file.

        Args:
            source_path: Path to the file to backup
            backup_dir: Directory for backup file (default: same as source)
                       Will be created if it doesn't exist.

        Returns:
            BackupResult with success/failure status and details.

        The backup is created atomically:
        1. Content written to temp file
        2. Checksum verified
        3. Temp file atomically renamed to final backup path

        Backup filename format: {original_stem}.{timestamp}.backup
        Example: config.2026-01-15T10-30-45.backup
        """
        # Validate source exists
        if not source_path.exists():
            return BackupResult(
                success=False,
                error=f"Source file not found: {source_path}",
            )

        # Determine backup directory
        if backup_dir is None:
            backup_dir = source_path.parent
        else:
            # Create backup directory if needed
            try:
                backup_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                return BackupResult(
                    success=False,
                    error=f"Permission denied creating backup directory: {backup_dir}",
                )
            except OSError as e:
                return BackupResult(
                    success=False,
                    error=f"Cannot create backup directory: {e}",
                )

        # Read source content
        try:
            content = source_path.read_text()
        except PermissionError:
            return BackupResult(
                success=False,
                error=f"Permission denied reading source file: {source_path}",
            )
        except OSError as e:
            return BackupResult(
                success=False,
                error=f"Error reading source file: {e}",
            )

        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S-%f")
        backup_name = f"{source_path.stem}.{timestamp}.backup"
        backup_path = backup_dir / backup_name

        # Compute checksum
        checksum = hashlib.sha256(content.encode()).hexdigest()

        # Write to temp file first (atomic pattern)
        temp_path = None
        try:
            # Create temp file in same directory for atomic rename
            fd, temp_path_str = tempfile.mkstemp(
                suffix=".tmp",
                prefix=f"{source_path.stem}_backup_",
                dir=backup_dir,
            )
            temp_path = Path(temp_path_str)

            # Write content
            with open(fd, "w") as f:
                f.write(content)

            # Verify write by reading back
            written_content = temp_path.read_text()
            if written_content != content:
                raise OSError("Backup verification failed: content mismatch")

            # Atomic rename (replace() is cross-platform safe per Insight #3)
            temp_path.replace(backup_path)
            temp_path = None  # Don't delete, it was renamed

            return BackupResult(
                success=True,
                backup_path=backup_path,
                checksum=checksum,
            )

        except PermissionError as e:
            error_msg = str(e)
            if "space" in error_msg.lower() or "disk" in error_msg.lower():
                return BackupResult(
                    success=False,
                    error="No space left on disk. Free up disk space and try again.",
                )
            return BackupResult(
                success=False,
                error=f"Permission denied writing backup: {e}",
            )

        except OSError as e:
            error_msg = str(e).lower()
            if "space" in error_msg or "disk" in error_msg:
                return BackupResult(
                    success=False,
                    error="No space left on disk. Free up disk space and try again.",
                )
            return BackupResult(
                success=False,
                error=f"Error creating backup: {e}",
            )

        finally:
            # Clean up temp file if it exists (operation failed)
            if temp_path is not None and temp_path.exists():
                with contextlib.suppress(OSError):
                    temp_path.unlink()
