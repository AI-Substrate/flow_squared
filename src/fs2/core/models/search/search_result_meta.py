"""SearchResultMeta domain model for search result metadata envelope.

A frozen dataclass representing search result metadata with:
- Required fields: total, showing, pagination, folders
- Optional filter fields: include, exclude, filtered

Also provides:
- extract_folder(): Extract folder from node_id
- compute_folder_distribution(): Compute folder counts with threshold-based drilling
- FOLDER_DRILL_THRESHOLD: Tunable constant for drilling (0.9 = 90%)

Per Subtask 003: Metadata envelope for search results.
Per DYK-003-02: Threshold-based drilling at 90%.
Per DYK-003-03: Handle all node_id formats (file:, callable:, class:, chunk:, content:).
Per DYK-003-05: include/exclude are always arrays, omitted when empty.
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

# Threshold for folder drilling (90% = 0.9)
# If any folder has >= this proportion of results, drill into second level
FOLDER_DRILL_THRESHOLD = 0.9


def extract_folder(node_id: str) -> str:
    """Extract the top-level folder from a node_id.

    Handles various node_id formats:
    - file:src/foo.py → "src/"
    - callable:tests/unit/test_foo.py:test_bar → "tests/"
    - class:src/models/user.py:User → "src/"
    - chunk:docs/api.md:10-20 → "docs/"
    - content:docs/guide.md → "docs/"

    Root-level files (no folder) return "(root)":
    - file:README.md → "(root)"
    - content:CHANGELOG.md → "(root)"

    Args:
        node_id: Node identifier string with prefix and optional suffix.

    Returns:
        Folder name with trailing slash, or "(root)" for root-level files.

    Example:
        >>> extract_folder("file:src/core/models/search/query.py")
        'src/'
        >>> extract_folder("file:README.md")
        '(root)'
    """
    # Strip prefix (everything up to and including first colon)
    if ":" in node_id:
        # Handle formats like "callable:path/to/file.py:symbol"
        # Split on first colon only to get the path portion
        parts = node_id.split(":", 1)
        path_part = parts[1] if len(parts) >= 2 else node_id
    else:
        path_part = node_id

    # For callable/class/chunk nodes, remove the :symbol or :line-range suffix
    # These have format path:suffix where path contains the file path
    # We need to find the last occurrence of a colon that follows a file extension
    # E.g., "tests/unit/test_foo.py:test_bar" → "tests/unit/test_foo.py"
    # E.g., "docs/api.md:10-20" → "docs/api.md"
    if ":" in path_part:
        # Check if this looks like a path:symbol pattern
        # The path should contain a "/" or file extension before the colon
        colon_idx = path_part.rfind(":")
        potential_path = path_part[:colon_idx]
        # If the part before the colon contains path separators, it's a path:symbol format
        if "/" in potential_path or "." in potential_path:
            path_part = potential_path

    # Extract the first segment (folder)
    if "/" not in path_part:
        # Root-level file (no folder)
        return "(root)"

    first_segment = path_part.split("/")[0]
    return f"{first_segment}/"


def _extract_second_level_folder(node_id: str) -> str:
    """Extract second-level folder from a node_id.

    Used when drilling into a dominant folder.

    Args:
        node_id: Node identifier string.

    Returns:
        Second-level folder path (e.g., "tests/unit/") or first-level if no second level.
    """
    # Strip prefix
    if ":" in node_id:
        parts = node_id.split(":", 1)
        path_part = parts[1] if len(parts) >= 2 else node_id
    else:
        path_part = node_id

    # Remove :symbol suffix
    if ":" in path_part:
        colon_idx = path_part.rfind(":")
        potential_path = path_part[:colon_idx]
        if "/" in potential_path or "." in potential_path:
            path_part = potential_path

    # Extract up to second level
    segments = path_part.split("/")
    if len(segments) >= 2:
        return f"{segments[0]}/{segments[1]}/"
    elif len(segments) == 1:
        return f"{segments[0]}/"
    return "(root)"


def compute_folder_distribution(node_ids: list[str]) -> dict[str, int]:
    """Compute folder distribution from node IDs with threshold-based drilling.

    If any folder has >= FOLDER_DRILL_THRESHOLD (90%) of results, drill into
    second-level folders for that folder while keeping minority folders at
    first level.

    Args:
        node_ids: List of node identifier strings.

    Returns:
        Dictionary mapping folder names to counts.
        Folders have trailing slashes (e.g., "src/", "tests/unit/").

    Example:
        >>> node_ids = [
        ...     "file:tests/unit/test_a.py",
        ...     "file:tests/unit/test_b.py",
        ...     "file:tests/integration/test_c.py",
        ...     "file:src/foo.py",
        ... ]
        >>> compute_folder_distribution(node_ids)
        {'tests/unit/': 2, 'tests/integration/': 1, 'src/': 1}
    """
    if not node_ids:
        return {}

    # First pass: count at first level
    first_level_counts: Counter[str] = Counter()
    for node_id in node_ids:
        folder = extract_folder(node_id)
        first_level_counts[folder] += 1

    total = len(node_ids)

    # Check if any folder meets drilling threshold
    dominant_folder = None
    for folder, count in first_level_counts.items():
        if count / total >= FOLDER_DRILL_THRESHOLD:
            dominant_folder = folder
            break

    if dominant_folder is None:
        # No drilling needed - return first-level counts
        return dict(first_level_counts)

    # Drill into the dominant folder
    result: Counter[str] = Counter()
    for node_id in node_ids:
        first_level = extract_folder(node_id)
        if first_level == dominant_folder:
            # Drill to second level
            second_level = _extract_second_level_folder(node_id)
            result[second_level] += 1
        else:
            # Keep minority folders at first level
            result[first_level] += 1

    return dict(result)


@dataclass(frozen=True)
class SearchResultMeta:
    """Immutable search result metadata for envelope output.

    Contains pagination info, total counts, and folder distribution.
    Optional filter fields are included only when filters are applied.

    Attributes (required):
        total: Total number of matches before pagination.
        showing: Dict with from, to, count for current page.
        pagination: Dict with limit, offset as passed in.
        folders: Dict mapping folder names to result counts.

    Attributes (optional - omitted from to_dict when empty):
        include: List of include patterns (omitted when None or empty).
        exclude: List of exclude patterns (omitted when None or empty).
        filtered: Count after filtering (omitted when no filters applied).

    Example:
        >>> meta = SearchResultMeta(
        ...     total=47,
        ...     showing={"from": 0, "to": 20, "count": 20},
        ...     pagination={"limit": 20, "offset": 0},
        ...     folders={"tests/": 36, "src/": 11},
        ... )
        >>> meta.to_dict()
        {'total': 47, 'showing': {...}, 'pagination': {...}, 'folders': {...}}
    """

    # Required fields
    total: int
    showing: dict[str, int]
    pagination: dict[str, int]
    folders: dict[str, int]

    # Optional filter fields (omitted from to_dict when empty)
    include: list[str] | None = field(default=None)
    exclude: list[str] | None = field(default=None)
    filtered: int | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, omitting empty filter fields.

        Per DYK-003-05: include/exclude are always arrays when present,
        but are omitted entirely when None or empty lists.

        Returns:
            Dictionary with required fields always present.
            Filter fields (include, exclude, filtered) only present when non-empty.

        Example:
            >>> meta = SearchResultMeta(
            ...     total=47,
            ...     showing={"from": 0, "to": 11, "count": 11},
            ...     pagination={"limit": 20, "offset": 0},
            ...     folders={"src/": 11},
            ...     include=["src/"],
            ...     filtered=11,
            ... )
            >>> d = meta.to_dict()
            >>> d["include"]
            ['src/']
            >>> d["filtered"]
            11
        """
        result: dict[str, Any] = {
            "total": self.total,
            "showing": self.showing,
            "pagination": self.pagination,
            "folders": self.folders,
        }

        # Only include filter fields when non-empty
        if self.include:  # Non-None and non-empty list
            result["include"] = self.include

        if self.exclude:  # Non-None and non-empty list
            result["exclude"] = self.exclude

        if self.filtered is not None:
            result["filtered"] = self.filtered

        return result
