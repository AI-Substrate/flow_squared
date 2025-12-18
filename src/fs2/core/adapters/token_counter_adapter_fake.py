"""FakeTokenCounterAdapter - deterministic test double for TokenCounterAdapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fs2.core.adapters.token_counter_adapter import TokenCounterAdapter

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


class FakeTokenCounterAdapter(TokenCounterAdapter):
    """Fake token counter adapter for tests.

    Features:
    - Deterministic default return value (0)
    - Configurable default count
    - Per-text overrides for precise test scenarios
    - Call history recording (fakes over mocks)
    """

    def __init__(self, config: ConfigurationService) -> None:
        self._config = config
        self._default_count: int = 0
        self._counts_by_text: dict[str, int] = {}
        self._call_history: list[dict[str, Any]] = []

    @property
    def call_history(self) -> list[dict[str, Any]]:
        """Access recorded calls for assertions."""
        return self._call_history

    def set_default_count(self, count: int) -> None:
        """Set the default count returned by count_tokens when no override exists."""
        self._default_count = count

    def set_count_for_text(self, text: str, count: int) -> None:
        """Set an explicit token count for a specific text."""
        self._counts_by_text[text] = count

    def count_tokens(self, text: str) -> int:
        self._call_history.append({"method": "count_tokens", "args": {"text": text}})
        return self._counts_by_text.get(text, self._default_count)
