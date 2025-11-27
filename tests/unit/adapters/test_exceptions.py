"""Tests for adapter exception hierarchy.

Tests verify:
- Exception inheritance chain
- Actionable error messages
- Exception translation pattern

Per Finding 07: Exception translation at adapter boundary
Per Plan 2.7-2.8: AdapterError hierarchy
"""

import pytest


@pytest.mark.unit
class TestAdapterErrorHierarchy:
    """Tests for adapter exception hierarchy."""

    def test_given_adapter_error_then_inherits_from_exception(self):
        """
        Purpose: Proves AdapterError is the base adapter exception
        Quality Contribution: Enables catch-all patterns
        """
        from fs2.core.adapters.exceptions import AdapterError

        assert issubclass(AdapterError, Exception)

    def test_given_authentication_error_then_inherits_from_adapter_error(self):
        """
        Purpose: Proves AuthenticationError is a specialized AdapterError
        Quality Contribution: Enables granular error handling
        """
        from fs2.core.adapters.exceptions import (AdapterError,
                                                  AuthenticationError)

        assert issubclass(AuthenticationError, AdapterError)
        assert issubclass(AuthenticationError, Exception)

    def test_given_connection_error_then_inherits_from_adapter_error(self):
        """
        Purpose: Proves ConnectionError is a specialized AdapterError
        Quality Contribution: Enables granular error handling
        """
        from fs2.core.adapters.exceptions import (AdapterConnectionError,
                                                  AdapterError)

        assert issubclass(AdapterConnectionError, AdapterError)
        assert issubclass(AdapterConnectionError, Exception)

    def test_given_adapter_error_when_raised_then_can_be_caught_as_exception(self):
        """
        Purpose: Proves AdapterError can be caught with generic handler
        Quality Contribution: Supports both specific and generic handling
        """
        from fs2.core.adapters.exceptions import AdapterError

        with pytest.raises(Exception):
            raise AdapterError("test error")

    def test_given_authentication_error_when_raised_then_can_be_caught_as_adapter_error(
        self,
    ):
        """
        Purpose: Proves AuthenticationError can be caught with AdapterError handler
        Quality Contribution: Supports hierarchical exception handling
        """
        from fs2.core.adapters.exceptions import (AdapterError,
                                                  AuthenticationError)

        with pytest.raises(AdapterError):
            raise AuthenticationError("auth failed")

    def test_given_adapter_error_with_message_then_message_accessible(self):
        """
        Purpose: Proves error message is accessible
        Quality Contribution: Enables error logging and debugging
        """
        from fs2.core.adapters.exceptions import AdapterError

        error = AdapterError("test message")

        assert str(error) == "test message"

    def test_given_authentication_error_with_message_then_message_accessible(self):
        """
        Purpose: Proves AuthenticationError message is accessible
        Quality Contribution: Enables actionable error messages
        """
        from fs2.core.adapters.exceptions import AuthenticationError

        error = AuthenticationError("Authentication failed: invalid token")

        assert "Authentication failed" in str(error)

    def test_given_connection_error_with_message_then_message_accessible(self):
        """
        Purpose: Proves ConnectionError message is accessible
        Quality Contribution: Enables actionable error messages
        """
        from fs2.core.adapters.exceptions import AdapterConnectionError

        error = AdapterConnectionError("Connection timeout to service")

        assert "Connection timeout" in str(error)
