"""Pattern normalization utilities for glob/regex filter support."""

from __future__ import annotations

import fnmatch
import re


def normalize_filter_pattern(pattern: str) -> str:
    """Convert glob patterns to regex for node_id matching.

    Uses GLOB-DETECTION-FIRST algorithm (DYK Insight #1):
    1. Extension patterns (.py, .cs) - always convert (unambiguous glob intent)
    2. Starts with * (*.py) - always convert (invalid regex anyway)
    3. Ends with * but not .* (test_*) - convert (likely glob intent)
    4. Contains ? after word char - convert (likely glob intent)
    5. All else - try as regex (Calculator.*, src/, ^class:)

    Node ID format assumption:
        file:path/to/file.ext
        category:path/to/file.ext:Symbol

    The anchor (?:$|:) matches at end of string OR before colon.

    Args:
        pattern: User-provided filter pattern (glob or regex)

    Returns:
        Regex pattern suitable for re.search()

    Raises:
        ValueError: If pattern is empty/whitespace or invalid
    """
    # Validate non-empty
    if not pattern or not pattern.strip():
        raise ValueError(
            "Filter pattern cannot be empty or whitespace-only. "
            "Provide a pattern like '*.py' or 'src/'"
        )

    # CRITICAL: Detect OBVIOUS glob patterns FIRST (DYK Insight #1)
    # These are unambiguous glob intent, even if technically valid regex

    # 1. Extension pattern (.py, .cs) - always convert
    if re.match(r"^\.\w+$", pattern):
        return re.escape(pattern) + r"(?:$|:)"

    # 2. Starts with * (*.py) - always convert (invalid regex anyway)
    if pattern.startswith("*"):
        return _convert_glob_to_regex(pattern)

    # 3. Ends with * but NOT .* (test_*) - likely glob intent
    if pattern.endswith("*") and not pattern.endswith(".*"):
        return _convert_glob_to_regex(pattern)

    # 4. Contains ? after word char (file?.py) - likely glob
    if re.search(r"\w\?", pattern):
        return _convert_glob_to_regex(pattern)

    # 5. All else - try as regex (Calculator.*, src/, ^class:)
    try:
        re.compile(pattern)
        return pattern
    except re.error as e:
        raise ValueError(f"Invalid pattern '{pattern}': {e}") from e


def _convert_glob_to_regex(pattern: str) -> str:
    """Convert glob pattern to regex with node_id anchor.

    Uses fnmatch.translate() and adds (?:$|:) anchor to handle
    both file nodes (ext at end) and symbol nodes (ext before :).

    Args:
        pattern: Glob pattern to convert

    Returns:
        Regex pattern with (?:$|:) anchor
    """
    translated = fnmatch.translate(pattern)

    # fnmatch.translate returns (?s:CORE)\Z (Python <3.14) or (?s:CORE)\z (Python 3.14+)
    # Use regex for safer extraction in case format changes
    match = re.match(r"^\(\?s:(.*)\)\\[Zz]$", translated)
    if match:
        core = match.group(1)
    else:
        # Format changed - fall back to string manipulation
        core = translated
        if core.endswith(r"\Z") or core.endswith(r"\z"):
            core = core[:-2]
        if core.startswith("(?s:") and core.endswith(")"):
            core = core[4:-1]

    # Add anchor for node_id format: matches at end OR before colon
    return core + r"(?:$|:)"
