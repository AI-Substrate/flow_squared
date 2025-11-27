"""SampleAdapter ABC interface.

Canonical example demonstrating the full adapter pattern for Phase 4's
documentation test.

Architecture:
- This file: ABC definition only
- Implementations: sample_adapter_fake.py, sample_adapter_prod.py, etc.

Pattern demonstrates:
- Multiple methods with different purposes
- Context passing for traceability
- Result type for explicit success/error handling
- Validation method that can raise AdapterError
"""

from abc import ABC, abstractmethod
from typing import Any

from fs2.core.models.process_result import ProcessResult


class SampleAdapter(ABC):
    """Sample adapter ABC demonstrating the full adapter pattern.

    This interface is intentionally complete to serve as the canonical
    example for Phase 4's documentation test. It shows:
    - Multiple methods with different purposes
    - Context passing for traceability
    - Result type for explicit success/error handling
    - Validation method that can raise AdapterError

    Implementations:
    - Phase 3+ will provide FakeSampleAdapter for testing
    - Production adapters follow this pattern
    """

    @abstractmethod
    def process(
        self, input_data: str, context: dict[str, Any] | None = None
    ) -> ProcessResult:
        """Process input data and return a result.

        Args:
            input_data: The data to process
            context: Optional context (trace_id, user_id, etc.)

        Returns:
            ProcessResult with success/failure and metadata
        """
        ...

    @abstractmethod
    def validate(self, input_data: str) -> bool:
        """Validate input before processing.

        Args:
            input_data: The data to validate

        Returns:
            True if valid

        Raises:
            AdapterError: If validation fails with details
        """
        ...
