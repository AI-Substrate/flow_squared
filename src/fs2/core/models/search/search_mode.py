"""SearchMode enum for type-safe search mode selection.

Provides the four search modes supported by the search capability:
- TEXT: Case-insensitive substring matching
- REGEX: Regular expression pattern matching
- SEMANTIC: Embedding similarity-based search
- AUTO: Automatic mode detection based on pattern heuristics

Per Phase 1 tasks.md: Type safety for search mode selection.
"""

from enum import Enum


class SearchMode(str, Enum):
    """Search mode enumeration.

    Inherits from str to enable string comparison and JSON serialization.

    Attributes:
        TEXT: Case-insensitive substring matching. Pattern is escaped
              and transformed to regex internally.
        REGEX: Regular expression pattern matching with timeout protection.
        SEMANTIC: Embedding similarity-based conceptual search.
        AUTO: Automatic mode detection based on pattern characteristics.
              Uses regex if pattern contains regex metacharacters,
              otherwise defaults to semantic.
    """

    TEXT = "text"
    REGEX = "regex"
    SEMANTIC = "semantic"
    AUTO = "auto"
