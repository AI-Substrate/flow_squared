"""Search service exceptions.

Provides the SearchError exception for search-related errors.
Per AC03: Clear error messages for invalid patterns and search failures.
"""


class SearchError(Exception):
    """Exception raised for search-related errors.

    This exception is raised when:
    - An invalid regex pattern is provided (AC03)
    - Other search operation failures occur

    The error message should be actionable and help users fix the issue.

    Example:
        >>> raise SearchError("Invalid regex pattern: unterminated character class")
    """

    pass
