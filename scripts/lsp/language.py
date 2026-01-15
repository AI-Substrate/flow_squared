"""
Language enum prototype for LSP project root detection.

This module validates Serena's Language enum pattern for Phase 3 adoption.
It provides:
- Language enum with `markers` property (project root marker files)
- `file_patterns` property (fnmatch globs for source files)
- `from_filename()` classmethod (detect language from filename)

TypeScript uses algorithmic pattern generation for 12 JS/TS variants.

Production quality: This code will be cherry-picked to
`src/fs2/core/utils/language.py` in Phase 3.
"""

from __future__ import annotations

import fnmatch
from enum import Enum


class Language(str, Enum):
    """
    Supported languages for LSP integration.

    Each language defines:
    - markers: Project root marker files (priority order)
    - file_patterns: fnmatch globs for source file detection

    Pattern: Following Serena's `Language(str, Enum)` for string comparison support.
    """

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    GO = "go"
    CSHARP = "csharp"

    @property
    def markers(self) -> tuple[str, ...]:
        """
        Return marker files for project root detection (priority order).

        The detection algorithm finds the deepest directory containing any marker.
        Priority order matters only when multiple markers exist at the same level.

        Returns:
            Tuple of marker filenames in priority order.
        """
        match self:
            case Language.PYTHON:
                return ("pyproject.toml", "setup.py", "setup.cfg")
            case Language.TYPESCRIPT:
                return ("tsconfig.json", "package.json")
            case Language.GO:
                return ("go.mod",)
            case Language.CSHARP:
                return (".csproj", ".sln")

    @property
    def file_patterns(self) -> tuple[str, ...]:
        """
        Return fnmatch glob patterns for source file detection.

        TypeScript uses algorithmic generation for 12 JS/TS variants:
        - prefix: c (CommonJS), m (ESModule), "" (standard)
        - postfix: x (JSX), "" (standard)
        - base: ts, js

        Returns:
            Tuple of fnmatch-compatible glob patterns.
        """
        match self:
            case Language.PYTHON:
                return ("*.py", "*.pyi")
            case Language.TYPESCRIPT:
                # Algorithmic generation: prefix × postfix × base = 12 patterns
                # See: https://github.com/oraios/serena/issues/204
                patterns: list[str] = []
                for prefix in ("c", "m", ""):  # cjs/mjs/standard
                    for postfix in ("x", ""):  # jsx/tsx or plain
                        for base in ("ts", "js"):
                            patterns.append(f"*.{prefix}{base}{postfix}")
                return tuple(patterns)
            case Language.GO:
                return ("*.go",)
            case Language.CSHARP:
                return ("*.cs",)

    @classmethod
    def from_filename(cls, filename: str) -> Language | None:
        """
        Detect language from filename using fnmatch patterns.

        Args:
            filename: The filename (not path) to match.

        Returns:
            The matching Language, or None if no match.

        Note:
            Returns first match. Order matters if patterns overlap.
        """
        for lang in cls:
            for pattern in lang.file_patterns:
                if fnmatch.fnmatch(filename, pattern):
                    return lang
        return None

    def matches_filename(self, filename: str) -> bool:
        """
        Check if filename matches this language's file patterns.

        Args:
            filename: The filename (not path) to match.

        Returns:
            True if filename matches any of this language's patterns.
        """
        for pattern in self.file_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
        return False

    def __str__(self) -> str:
        return self.value


def get_typescript_patterns() -> list[str]:
    """
    Generate all TypeScript/JavaScript file patterns algorithmically.

    This is exposed for testing the pattern generation algorithm.
    Expected patterns (12 total):
    - Standard: *.ts, *.tsx, *.js, *.jsx
    - CommonJS: *.cts, *.ctsx, *.cjs, *.cjsx
    - ES Module: *.mts, *.mtsx, *.mjs, *.mjsx

    Returns:
        List of 12 fnmatch patterns.
    """
    patterns: list[str] = []
    for prefix in ("c", "m", ""):
        for postfix in ("x", ""):
            for base in ("ts", "js"):
                patterns.append(f"*.{prefix}{base}{postfix}")
    return patterns
