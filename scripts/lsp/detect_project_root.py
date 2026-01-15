"""
Project root detection script for LSP integration.

This module implements the "deepest wins" algorithm for finding project roots
based on language-specific marker files.

Key features:
- find_project_root(): Explicit language, returns deepest marker match
- detect_project_root_auto(): Auto-detects language from filename
- Boundary constraint: Search stops at workspace_root if provided
- Always returns a Path (never None) - falls back to file's directory

Production quality: This code will be cherry-picked to
`src/fs2/core/utils/project_root.py` in Phase 3.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from scripts.lsp.language import Language


def find_project_root(
    file_path: Path | str,
    language: Language,
    workspace_root: Path | str | None = None,
) -> Path:
    """
    Find the project root for a file using the "deepest wins" algorithm.

    Walks up from the file's directory, checking for language-specific marker
    files. Returns the deepest directory containing any marker (closest to file).

    Args:
        file_path: Path to the source file being analyzed.
        language: The language to use for marker file detection.
        workspace_root: Optional boundary. Search stops at this directory.
            Acts as a virtual filesystem root for sandboxed environments.

    Returns:
        The deepest project root directory (Path), or the file's parent
        directory if no marker is found.

    Example:
        >>> # Given: workspace/packages/auth/handler.py
        >>> # With markers: workspace/pyproject.toml, packages/auth/pyproject.toml
        >>> find_project_root("workspace/packages/auth/handler.py", Language.PYTHON)
        PosixPath('workspace/packages/auth')  # Deepest wins
    """
    file_path = Path(file_path).resolve()
    boundary = Path(workspace_root).resolve() if workspace_root is not None else None
    markers = language.markers

    # Start from file's parent directory
    # Note: is_file() returns False for non-existent files, so also check suffix
    is_file = file_path.is_file() or (file_path.suffix and not file_path.is_dir())
    start_dir = file_path.parent if is_file else file_path
    candidate: Path | None = None

    def ancestors(start: Path) -> Iterator[Path]:
        """Yield start directory and ancestors up to boundary."""
        current = start
        yield current
        for parent in current.parents:
            yield parent
            if boundary is not None and parent == boundary:
                return

    # Walk up, keeping the FIRST (deepest) marker match
    # "Deepest wins" means the directory closest to the file takes precedence
    for directory in ancestors(start_dir):
        for marker in markers:
            marker_path = directory / marker
            # Handle both file markers (pyproject.toml) and glob patterns (.csproj)
            if marker.startswith(".") and marker.endswith(("proj", "sln")):
                # For .csproj/.sln, check if any file matches the pattern
                if list(directory.glob(f"*{marker}")):
                    if candidate is None:
                        candidate = directory
                    break
            elif marker_path.exists():
                if candidate is None:
                    candidate = directory
                break

    # Return deepest match, or fall back to file's directory
    if candidate is not None:
        return candidate

    return start_dir


def detect_project_root_auto(
    file_path: Path | str,
    workspace_root: Path | str | None = None,
) -> tuple[Path, Language | None]:
    """
    Auto-detect language and find project root for a file.

    First detects the language from the filename, then uses find_project_root()
    to locate the project root.

    Args:
        file_path: Path to the source file being analyzed.
        workspace_root: Optional boundary. Search stops at this directory.

    Returns:
        Tuple of (project_root, detected_language).
        If language cannot be detected, returns (file's parent, None).

    Example:
        >>> detect_project_root_auto("workspace/packages/auth/handler.py")
        (PosixPath('workspace/packages/auth'), Language.PYTHON)
    """
    file_path = Path(file_path).resolve()
    filename = file_path.name

    language = Language.from_filename(filename)
    if language is None:
        # Cannot detect language - return file's directory
        return (file_path.parent if file_path.is_file() else file_path, None)

    root = find_project_root(file_path, language, workspace_root)
    return (root, language)


def find_all_project_roots(
    directory: Path | str,
    language: Language,
    workspace_root: Path | str | None = None,
) -> list[Path]:
    """
    Find all project roots within a directory tree.

    Useful for workspace-level analysis where multiple projects may exist.

    Args:
        directory: Root directory to search within.
        language: The language to use for marker file detection.
        workspace_root: Optional boundary for search.

    Returns:
        List of unique project root directories, sorted by depth (deepest first).
    """
    directory = Path(directory).resolve()
    boundary = Path(workspace_root).resolve() if workspace_root is not None else None
    markers = language.markers
    roots: set[Path] = set()

    def should_continue(path: Path) -> bool:
        """Check if we should continue searching beyond this path."""
        if boundary is not None and path == boundary:
            return False
        return True

    def walk_tree(start: Path) -> Iterator[Path]:
        """Walk directory tree yielding all directories."""
        if start.is_dir():
            yield start
            for child in start.iterdir():
                if child.is_dir() and should_continue(child):
                    yield from walk_tree(child)

    for dir_path in walk_tree(directory):
        for marker in markers:
            marker_path = dir_path / marker
            if marker.startswith(".") and marker.endswith(("proj", "sln")):
                if list(dir_path.glob(f"*{marker}")):
                    roots.add(dir_path)
                    break
            elif marker_path.exists():
                roots.add(dir_path)
                break

    # Sort by depth (deepest first)
    return sorted(roots, key=lambda p: len(p.parts), reverse=True)
