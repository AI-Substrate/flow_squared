"""Project discovery — detect language projects by marker files.

Extracted from cross_file_rels_stage.py for reuse by CLI commands
and future stage integration.

Walks a directory tree looking for project marker files (pyproject.toml,
tsconfig.json, go.mod, .csproj, etc.) and returns detected project roots.

Key design decisions:
- No child dedup: SCIP needs per-project indexes, so nested projects are kept.
- One entry per (path, language): multi-language roots produce separate entries.
- Extended markers: C# (.csproj, .sln) and Ruby (Gemfile) added.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Project marker files for language detection
PROJECT_MARKERS: dict[str, list[str]] = {
    "python": ["pyproject.toml", "setup.py", "setup.cfg", "Pipfile"],
    "typescript": ["tsconfig.json"],
    "javascript": ["package.json"],
    "go": ["go.mod"],
    "rust": ["Cargo.toml"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
    "dotnet": ["*.csproj", "*.sln"],
    "ruby": ["Gemfile"],
}

# Directories to skip during project discovery
_SKIP_DIRS = frozenset({
    ".venv", "venv", ".env", "env",
    "node_modules",
    ".git", ".hg", ".svn",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".tox", ".nox",
    "site-packages",
    "dist", "build", ".eggs",
    "obj", "bin",  # C# build output
})

# SCIP indexer binary names for each language (used by CLI for status display)
INDEXER_BINARIES: dict[str, str] = {
    "python": "scip-python",
    "typescript": "scip-typescript",
    "javascript": "scip-typescript",
    "go": "scip-go",
    "dotnet": "scip-dotnet",
}

# Install instructions for SCIP indexers
INDEXER_INSTALL: dict[str, str] = {
    "python": "npm install -g @sourcegraph/scip-python",
    "typescript": "npm install -g @sourcegraph/scip-typescript",
    "javascript": "npm install -g @sourcegraph/scip-typescript",
    "go": "go install github.com/sourcegraph/scip-go/cmd/scip-go@latest",
    "dotnet": "dotnet tool install --global scip-dotnet",
}


@dataclass(frozen=True)
class DiscoveredProject:
    """A detected language project root.

    Attributes:
        path: Absolute path to the project root directory.
        language: The detected language type (one entry per language).
        marker_file: The marker file that triggered detection.
    """

    path: str
    language: str
    marker_file: str


def detect_project_roots(scan_root: str) -> list[DiscoveredProject]:
    """Detect project roots by walking for marker files.

    Walks the scan_root directory tree looking for project marker files.
    Returns one entry per (path, language) pair — multi-language roots
    produce separate entries.

    No child dedup: nested projects are preserved because SCIP indexers
    need per-project indexes (unlike Serena which covered children).

    Skips vendored/dependency directories (.venv, node_modules, obj/, etc.)
    to avoid detecting projects inside installed packages or build output.

    Args:
        scan_root: Root directory to scan.

    Returns:
        List of DiscoveredProject sorted by path then language.
    """
    root_path = Path(scan_root).resolve()
    # Collect: (dir_path, language, marker_filename)
    found: list[tuple[str, str, str]] = []

    # Build lookup tables for plain markers and glob patterns
    plain_markers: dict[str, str] = {}  # filename → language
    glob_markers: list[tuple[str, str]] = []  # (pattern, language)
    for language, markers in PROJECT_MARKERS.items():
        for marker in markers:
            if "*" in marker:
                glob_markers.append((marker, language))
            else:
                plain_markers[marker] = language

    # Single walk with directory pruning
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Prune vendored/dependency directories in-place
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]

        for fname in filenames:
            if fname in plain_markers:
                found.append((dirpath, plain_markers[fname], fname))
            else:
                for pattern, language in glob_markers:
                    if Path(fname).match(pattern):
                        found.append((dirpath, language, fname))

    # Deduplicate: one entry per (path, language)
    seen: set[tuple[str, str]] = set()
    results: list[DiscoveredProject] = []
    for dirpath, language, marker in found:
        key = (dirpath, language)
        if key not in seen:
            seen.add(key)
            results.append(DiscoveredProject(
                path=dirpath,
                language=language,
                marker_file=marker,
            ))

    results.sort(key=lambda r: (r.path, r.language))
    return results
