"""TokenCounterAdapter ABC interface.

Provides a small adapter contract for token counting.

Rationale:
- Services must not import tokenizer libraries directly (Clean Architecture).
- Token counting can be faked deterministically in tests (fakes over mocks).
- Implementations translate tokenizer/library errors to TokenCounterError.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


class TokenCounterAdapter(ABC):
    """Abstract base class for token counting.

    Implementations must:
    - Receive ConfigurationService in constructor (registry pattern)
    - Translate underlying library failures to TokenCounterError
    - Provide a deterministic count_tokens(text) -> int API
    """

    @abstractmethod
    def __init__(self, config: ConfigurationService) -> None:
        """Initialize with ConfigurationService registry."""
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Return token count for the given text.

        Raises:
            TokenCounterError: If token counting fails.
        """
        ...
