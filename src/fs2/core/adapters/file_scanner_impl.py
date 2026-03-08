"""FileSystemScanner - Production implementation of FileScanner ABC.

Provides gitignore-aware directory traversal using pathspec library.
Discovers source files in configured scan paths while respecting
.gitignore patterns at each directory level.

Architecture:
- Inherits from FileScanner ABC
- Receives ConfigurationService (registry) via constructor
- Uses pathspec library for gitignore pattern matching
- Depth-first directory traversal with pattern merging

Per Critical Finding 01: Receives ConfigurationService, not extracted config.
Per Critical Finding 02: Adapter ABC with Dual Implementation Pattern.
Per Critical Finding 04: Depth-first walk, merge .gitignore at each level.
Per Critical Finding 06: Default follow_symlinks=False.
Per Critical Finding 10: Translate OS errors to FileScannerError.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pathspec

from fs2.config.objects import ScanConfig
from fs2.core.adapters.exceptions import FileScannerError
from fs2.core.adapters.file_scanner import FileScanner
from fs2.core.models.scan_result import ScanResult

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


logger = logging.getLogger(__name__)


class FileSystemScanner(FileScanner):
    """Production implementation of FileScanner using pathspec.

    Discovers source files in directories specified in ScanConfig.scan_paths,
    respecting gitignore patterns at each level of the directory tree.

    Features:
    - Recursive directory traversal
    - Root .gitignore pattern support (AC2)
    - Nested .gitignore pattern scoping (AC3)
    - Configurable symlink handling (Critical Finding 06)
    - Permission error handling (Critical Finding 10)

    Usage:
        ```python
        config = FS2ConfigurationService()
        scanner = FileSystemScanner(config)

        results = scanner.scan()  # Returns list[ScanResult]

        # Query specific paths against loaded patterns
        if scanner.should_ignore(Path("node_modules/pkg.js")):
            print("Would be excluded")
        ```

    Lifecycle:
        1. Construct with ConfigurationService
        2. Call scan() to traverse directories and load patterns
        3. Optionally call should_ignore() to query specific paths
    """

    def __init__(self, config: "ConfigurationService"):
        """Initialize with ConfigurationService registry.

        Args:
            config: ConfigurationService registry.
                    Scanner will call config.require(ScanConfig) internally.

        Raises:
            MissingConfigurationError: If ScanConfig not in registry.
        """
        # Extract config internally (per Critical Finding 01)
        self._scan_config = config.require(ScanConfig)
        # Gitignore specs loaded during scan, keyed by directory
        self._gitignore_specs: dict[Path, pathspec.PathSpec] = {}
        # Config-level ignore patterns (always applied, regardless of respect_gitignore)
        self._config_ignore_spec: pathspec.PathSpec | None = None
        if self._scan_config.ignore_patterns:
            self._config_ignore_spec = pathspec.PathSpec.from_lines(
                pathspec.patterns.GitWildMatchPattern,
                self._scan_config.ignore_patterns,
            )
        # Root paths for relative pattern matching
        self._scan_roots: list[Path] = []
        # Flag to track if scan() has been called
        self._scanned = False

    def scan(self) -> list[ScanResult]:
        """Discover source files in configured scan paths.

        Recursively traverses directories, respecting gitignore patterns
        at each level. Symlinks are handled per follow_symlinks config.

        Returns:
            List of ScanResult containing path and size_bytes for each file.

        Raises:
            FileScannerError: If a scan_path does not exist.
        """
        results: list[ScanResult] = []
        self._scan_roots = []
        self._gitignore_specs = {}

        for scan_path_str in self._scan_config.scan_paths:
            scan_path = Path(scan_path_str).resolve()
            self._scan_roots.append(scan_path)

            if not scan_path.exists():
                raise FileScannerError(
                    f"Scan path does not exist: {scan_path}. "
                    "Check scan_paths configuration in .fs2/config.yaml."
                )

            # Load ancestor gitignore files up to repo root (or filesystem root)
            # This ensures patterns from the repo-root .gitignore apply even
            # when scan_paths are subdirectories like "scripts" or "src".
            if self._scan_config.respect_gitignore:
                self._load_ancestor_gitignores(scan_path)

            # Walk the directory tree
            results.extend(self._walk_directory(scan_path, scan_path))

        self._scanned = True
        return results

    def should_ignore(self, path: Path) -> bool:
        """Check if a path matches ignore patterns (config or gitignore).

        Args:
            path: Path to check against ignore patterns.

        Returns:
            True if path should be ignored, False otherwise.

        Raises:
            FileScannerError: If scan() has not been called first.
        """
        if not self._scanned:
            raise FileScannerError(
                "scan() must be called before should_ignore(). "
                "Gitignore patterns are not loaded until scan() traverses directories."
            )

        # Config-level patterns always apply
        if self._is_config_ignored(path):
            return True

        if not self._scan_config.respect_gitignore:
            return False

        return self._is_ignored(path)

    def _walk_directory(self, directory: Path, root: Path) -> list[ScanResult]:
        """Recursively walk a directory, collecting non-ignored files.

        Args:
            directory: Current directory to process.
            root: Root scan path for relative path calculations.

        Returns:
            List of ScanResult for files in this subtree.
        """
        results: list[ScanResult] = []

        try:
            entries = list(directory.iterdir())
        except PermissionError as e:
            logger.warning(
                f"Permission denied reading directory: {directory}. "
                f"Skipping subtree. Error: {e}"
            )
            return results

        for entry in entries:
            try:
                # Handle symlinks - skip if not following
                if entry.is_symlink() and not self._scan_config.follow_symlinks:
                    logger.debug(f"Skipping symlink: {entry}")
                    continue

                if entry.is_dir():
                    # Skip .git directory
                    if entry.name == ".git":
                        continue

                    # Config-level ignore patterns always apply
                    if self._is_config_ignored(entry):
                        continue

                    # Check if directory is ignored by gitignore
                    if self._scan_config.respect_gitignore and self._is_ignored(entry):
                        continue

                    # Load nested gitignore if present
                    if self._scan_config.respect_gitignore:
                        self._load_gitignore(entry)

                    # Recurse into subdirectory
                    results.extend(self._walk_directory(entry, root))

                elif entry.is_file():
                    # Skip .gitignore files themselves
                    if entry.name == ".gitignore":
                        continue

                    # Config-level ignore patterns always apply
                    if self._is_config_ignored(entry):
                        continue

                    # Check if file is ignored by gitignore
                    if self._scan_config.respect_gitignore and self._is_ignored(entry):
                        continue

                    # Get file size
                    try:
                        size_bytes = entry.stat().st_size
                    except PermissionError as e:
                        logger.warning(
                            f"Permission denied getting file size: {entry}. "
                            f"Skipping file. Error: {e}"
                        )
                        continue

                    results.append(ScanResult(path=entry, size_bytes=size_bytes))

            except PermissionError as e:
                logger.warning(
                    f"Permission denied accessing: {entry}. Skipping. Error: {e}"
                )
                continue

        return results

    def _is_config_ignored(self, path: Path) -> bool:
        """Check if a path matches config-level ignore_patterns.

        These patterns are always applied regardless of respect_gitignore.

        Args:
            path: Path to check.

        Returns:
            True if path matches a config ignore pattern.
        """
        if not self._config_ignore_spec:
            return False

        abs_path = path.resolve()

        # Check against each scan root
        for root in self._scan_roots:
            try:
                rel_path = abs_path.relative_to(root)
            except ValueError:
                continue

            rel_path_str = str(rel_path).replace("\\", "/")

            if abs_path.is_dir():
                rel_path_str += "/"

            if self._config_ignore_spec.match_file(rel_path_str):
                return True

        return False

    def _load_ancestor_gitignores(self, scan_path: Path) -> None:
        """Load .gitignore patterns from scan_path and all ancestor directories.

        Walks upward from scan_path to the git repo root (directory containing
        .git) or filesystem root, loading .gitignore from each level. This
        ensures repo-root patterns like 'node_modules' apply even when
        scan_paths are subdirectories.

        Args:
            scan_path: The resolved scan path to start from.
        """
        # Collect ancestors from scan_path upward, stopping at .git or root
        ancestors: list[Path] = []
        current = scan_path
        while True:
            ancestors.append(current)
            if (current / ".git").exists():
                break
            parent = current.parent
            if parent == current:
                break
            current = parent

        # Load gitignores top-down (repo root first) so patterns layer correctly
        for directory in reversed(ancestors):
            self._load_gitignore(directory)

    def _load_gitignore(self, directory: Path) -> None:
        """Load .gitignore patterns from a directory.

        Args:
            directory: Directory to check for .gitignore.
        """
        gitignore_path = directory / ".gitignore"
        if gitignore_path.exists():
            try:
                patterns = gitignore_path.read_text().splitlines()
                # Filter empty lines and comments
                patterns = [
                    p.strip()
                    for p in patterns
                    if p.strip() and not p.strip().startswith("#")
                ]
                if patterns:
                    spec = pathspec.PathSpec.from_lines(
                        pathspec.patterns.GitWildMatchPattern, patterns
                    )
                    self._gitignore_specs[directory] = spec
            except Exception as e:
                logger.warning(
                    f"Error reading .gitignore at {gitignore_path}: {e}. "
                    "Continuing without these patterns."
                )

    def _is_ignored(self, path: Path) -> bool:
        """Check if a path matches any applicable gitignore patterns.

        Patterns are checked hierarchically - a file in a subdirectory
        is checked against all parent directory gitignore specs.

        Per Critical Finding 04: Negation in nested gitignore cannot
        un-exclude files excluded by parent gitignore.

        Args:
            path: Path to check.

        Returns:
            True if path matches an ignore pattern.
        """
        # Resolve to absolute path
        abs_path = path.resolve()

        # Check against each gitignore spec from root to deepest
        for gitignore_dir, spec in self._gitignore_specs.items():
            # Only apply patterns to paths under the gitignore directory
            try:
                rel_path = abs_path.relative_to(gitignore_dir)
            except ValueError:
                # Path is not under this gitignore directory
                continue

            # Convert to string with forward slashes for matching
            rel_path_str = str(rel_path).replace("\\", "/")

            # For directories, append trailing slash
            if abs_path.is_dir():
                rel_path_str += "/"

            if spec.match_file(rel_path_str):
                return True

        return False
