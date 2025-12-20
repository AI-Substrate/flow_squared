"""Tests for embedding exception hierarchy.

Phase 1: Core Infrastructure - Embedding exception tests.
Purpose: Verify EmbeddingAdapterError hierarchy follows LLM pattern.

Per Plan 1.3: Exception hierarchy follows existing pattern.
Per DYK-4: EmbeddingRateLimitError includes retry_after and attempts_made metadata.
"""

import pytest


@pytest.mark.unit
class TestEmbeddingExceptionInheritance:
    """T007: Tests for embedding exception inheritance hierarchy."""

    def test_given_base_error_when_checking_inheritance_then_inherits_adapter_error(
        self,
    ):
        """
        Purpose: Proves EmbeddingAdapterError inherits from AdapterError.
        Quality Contribution: Enables catch-all patterns at service layer.
        Acceptance Criteria: EmbeddingAdapterError is subclass of AdapterError.

        Task: T007
        """
        from fs2.core.adapters.exceptions import AdapterError, EmbeddingAdapterError

        # Arrange / Act / Assert
        assert issubclass(EmbeddingAdapterError, AdapterError)
        assert issubclass(EmbeddingAdapterError, Exception)

    def test_given_rate_limit_error_when_checking_inheritance_then_inherits_embedding_error(
        self,
    ):
        """
        Purpose: Proves EmbeddingRateLimitError inherits from EmbeddingAdapterError.
        Quality Contribution: Enables specific rate limit handling.
        Acceptance Criteria: EmbeddingRateLimitError is subclass of EmbeddingAdapterError.

        Task: T007
        """
        from fs2.core.adapters.exceptions import (
            EmbeddingAdapterError,
            EmbeddingRateLimitError,
        )

        # Arrange / Act / Assert
        assert issubclass(EmbeddingRateLimitError, EmbeddingAdapterError)

    def test_given_auth_error_when_checking_inheritance_then_inherits_embedding_error(
        self,
    ):
        """
        Purpose: Proves EmbeddingAuthenticationError inherits from EmbeddingAdapterError.
        Quality Contribution: Enables specific auth error handling.
        Acceptance Criteria: EmbeddingAuthenticationError is subclass of EmbeddingAdapterError.

        Task: T007
        """
        from fs2.core.adapters.exceptions import (
            EmbeddingAdapterError,
            EmbeddingAuthenticationError,
        )

        # Arrange / Act / Assert
        assert issubclass(EmbeddingAuthenticationError, EmbeddingAdapterError)


@pytest.mark.unit
class TestEmbeddingRateLimitErrorMetadata:
    """T007: Tests for EmbeddingRateLimitError retry metadata per DYK-4."""

    def test_given_rate_limit_error_with_retry_after_when_constructed_then_stores_value(
        self,
    ):
        """
        Purpose: Per DYK-4: Proves retry_after attribute is stored.
        Quality Contribution: Enables respecting API Retry-After header.
        Acceptance Criteria: retry_after is accessible on exception.

        Task: T007
        """
        from fs2.core.adapters.exceptions import EmbeddingRateLimitError

        # Arrange / Act
        error = EmbeddingRateLimitError(
            "Rate limit exceeded", retry_after=30.5, attempts_made=2
        )

        # Assert
        assert error.retry_after == 30.5

    def test_given_rate_limit_error_with_attempts_when_constructed_then_stores_value(
        self,
    ):
        """
        Purpose: Per DYK-4: Proves attempts_made attribute is stored.
        Quality Contribution: Enables logging/metrics for retry tracking.
        Acceptance Criteria: attempts_made is accessible on exception.

        Task: T007
        """
        from fs2.core.adapters.exceptions import EmbeddingRateLimitError

        # Arrange / Act
        error = EmbeddingRateLimitError(
            "Rate limit exceeded", retry_after=30.5, attempts_made=3
        )

        # Assert
        assert error.attempts_made == 3

    def test_given_rate_limit_error_with_none_retry_after_when_constructed_then_accepts_none(
        self,
    ):
        """
        Purpose: Per DYK-4: Proves retry_after can be None (no Retry-After header).
        Quality Contribution: Handles APIs that don't provide Retry-After.
        Acceptance Criteria: retry_after=None is valid.

        Task: T007
        """
        from fs2.core.adapters.exceptions import EmbeddingRateLimitError

        # Arrange / Act
        error = EmbeddingRateLimitError(
            "Rate limit exceeded", retry_after=None, attempts_made=1
        )

        # Assert
        assert error.retry_after is None
        assert error.attempts_made == 1

    def test_given_rate_limit_error_when_converted_to_string_then_includes_message(
        self,
    ):
        """
        Purpose: Proves error message is accessible via str().
        Quality Contribution: Enables clear error logging.
        Acceptance Criteria: str(error) includes the message.

        Task: T007
        """
        from fs2.core.adapters.exceptions import EmbeddingRateLimitError

        # Arrange / Act
        error = EmbeddingRateLimitError(
            "Rate limit exceeded", retry_after=30.0, attempts_made=2
        )

        # Assert
        assert "Rate limit exceeded" in str(error)


@pytest.mark.unit
class TestEmbeddingAuthenticationError:
    """T007: Tests for EmbeddingAuthenticationError."""

    def test_given_auth_error_when_constructed_then_stores_message(self):
        """
        Purpose: Proves EmbeddingAuthenticationError stores message.
        Quality Contribution: Enables clear auth failure messages.
        Acceptance Criteria: Message is accessible via str().

        Task: T007
        """
        from fs2.core.adapters.exceptions import EmbeddingAuthenticationError

        # Arrange / Act
        error = EmbeddingAuthenticationError("Invalid API key")

        # Assert
        assert "Invalid API key" in str(error)

    def test_given_auth_error_when_raised_then_can_be_caught(self):
        """
        Purpose: Proves exception can be raised and caught.
        Quality Contribution: Ensures proper exception flow.
        Acceptance Criteria: Exception can be caught by type.

        Task: T007
        """
        from fs2.core.adapters.exceptions import EmbeddingAuthenticationError

        # Arrange / Act / Assert
        with pytest.raises(EmbeddingAuthenticationError):
            raise EmbeddingAuthenticationError("Auth failed")


@pytest.mark.unit
class TestEmbeddingAdapterError:
    """T007: Tests for EmbeddingAdapterError base class."""

    def test_given_base_error_when_constructed_then_stores_message(self):
        """
        Purpose: Proves EmbeddingAdapterError can be used directly.
        Quality Contribution: Enables generic embedding error handling.
        Acceptance Criteria: Message is accessible via str().

        Task: T007
        """
        from fs2.core.adapters.exceptions import EmbeddingAdapterError

        # Arrange / Act
        error = EmbeddingAdapterError("Generic embedding failure")

        # Assert
        assert "Generic embedding failure" in str(error)

    def test_given_base_error_when_raised_then_can_be_caught_as_adapter_error(self):
        """
        Purpose: Proves catch-all pattern works.
        Quality Contribution: Enables service-layer catch-all for adapter errors.
        Acceptance Criteria: EmbeddingAdapterError can be caught as AdapterError.

        Task: T007
        """
        from fs2.core.adapters.exceptions import AdapterError, EmbeddingAdapterError

        # Arrange / Act / Assert
        with pytest.raises(AdapterError):
            raise EmbeddingAdapterError("Some error")
