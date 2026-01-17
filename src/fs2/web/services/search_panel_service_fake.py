"""FakeSearchPanelService - Test double for SearchPanelService.

Per Phase 1/2 pattern: Fake services provide deterministic behavior for testing.
They record call history, allow result configuration, and support error simulation.

Example:
    >>> from fs2.web.services.search_panel_service_fake import FakeSearchPanelService
    >>> fake = FakeSearchPanelService()
    >>> fake.set_results([mock_result1, mock_result2])
    >>> result = fake.search(pattern="test", mode=SearchMode.TEXT)
    >>> assert len(result.results) == 2
    >>> assert fake.call_history[0]["pattern"] == "test"
"""

from __future__ import annotations

from typing import Any

from fs2.core.models.search.search_mode import SearchMode
from fs2.core.models.search.search_result import SearchResult
from fs2.web.services.search_panel_service import SearchPanelResult


class FakeSearchPanelService:
    """Fake implementation of SearchPanelService for testing.

    Per Phase 1/2 pattern: This implementation provides:
    - Deterministic results via set_results()
    - Call history recording for test assertions
    - Error simulation via simulate_error()

    Attributes:
        call_history: List of recorded search calls.
    """

    def __init__(self) -> None:
        """Initialize FakeSearchPanelService with empty state."""
        self._results: list[SearchResult] = []
        self._call_history: list[dict[str, Any]] = []
        self._simulated_error: Exception | None = None

    @property
    def call_history(self) -> list[dict[str, Any]]:
        """Access recorded calls for test assertions.

        Returns:
            List of dicts with pattern, mode, limit, offset for each call.
        """
        return self._call_history

    def set_results(self, results: list[SearchResult]) -> None:
        """Configure results to return from search().

        Args:
            results: List of SearchResult to return.
        """
        self._results = list(results)

    def simulate_error(self, error: Exception) -> None:
        """Configure an error to raise on next search().

        Args:
            error: Exception to raise.
        """
        self._simulated_error = error

    def clear(self) -> None:
        """Reset all state for test isolation.

        Clears results, call history, and simulated error.
        """
        self._results = []
        self._call_history = []
        self._simulated_error = None

    def search(
        self,
        pattern: str,
        mode: SearchMode = SearchMode.AUTO,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchPanelResult:
        """Fake search implementation.

        Records the call and returns configured results or raises simulated error.

        Args:
            pattern: Search pattern.
            mode: Search mode.
            limit: Maximum results.
            offset: Results to skip.

        Returns:
            SearchPanelResult with configured results.

        Raises:
            Configured error if simulate_error() was called.
        """
        self._call_history.append({
            "pattern": pattern,
            "mode": mode,
            "limit": limit,
            "offset": offset,
        })

        if self._simulated_error is not None:
            error = self._simulated_error
            self._simulated_error = None  # Clear after raising
            raise error

        # Apply limit and offset to results
        paginated = self._results[offset : offset + limit]

        return SearchPanelResult(
            results=paginated,
            total=len(self._results),  # Total before pagination
            mode_used=mode,
            query=pattern,
        )
