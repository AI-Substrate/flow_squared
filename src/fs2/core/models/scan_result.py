"""ScanResult domain model.

A frozen dataclass representing a file discovered during scanning.
Used by FileScanner adapters to return both path and size information,
enabling Phase 3 to make truncation decisions without re-statting files.

Per Critical Finding 09: Domain models use @dataclass(frozen=True).
Per Critical Finding 12: File sizes needed for large file truncation.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScanResult:
    """Result of scanning a single file.

    Immutable dataclass containing file path and size information.
    Returned by FileScanner.scan() to enable downstream processing
    decisions without additional file system calls.

    Attributes:
        path: Path to the scanned file.
        size_bytes: File size in bytes (for truncation decisions).

    Example:
        >>> result = ScanResult(path=Path("src/main.py"), size_bytes=1024)
        >>> result.path
        PosixPath('src/main.py')
        >>> result.size_bytes
        1024
    """

    path: Path
    size_bytes: int
