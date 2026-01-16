"""
Stub for serena.util.file_system.

Provides match_path function used for path matching against ignore patterns.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathspec import PathSpec


def match_path(
    relative_path: str,
    path_spec: "PathSpec",
    root_path: str = "",
) -> bool:
    """
    Match a relative path against a given pathspec.

    This stub implementation provides path matching functionality compatible
    with pathspec.match_file() but handles edge cases like leading slashes.

    Args:
        relative_path: Relative path to match against the pathspec
        path_spec: The pathspec to match against
        root_path: The root path from which the relative path is derived

    Returns:
        True if the path matches the pathspec (should NOT be ignored)
    """
    normalized_path = str(relative_path).replace(os.path.sep, "/")

    # Handle patterns that start with /
    # pathspec expects paths relative to root, so we need to add leading slash
    if root_path:
        # Create variant with leading slash for patterns like /src/...
        path_with_slash = "/" + normalized_path.lstrip("/")

        # Check both variants
        matches = path_spec.match_file(normalized_path)
        matches_with_slash = path_spec.match_file(path_with_slash)

        # Return True if path should be included (NOT ignored)
        return not (matches or matches_with_slash)

    # Simple case: just check if path matches
    return not path_spec.match_file(normalized_path)
