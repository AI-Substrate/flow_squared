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
        from fs2.core.adapters.exceptions import AdapterError, AuthenticationError

        assert issubclass(AuthenticationError, AdapterError)
        assert issubclass(AuthenticationError, Exception)

    def test_given_connection_error_then_inherits_from_adapter_error(self):
        """
        Purpose: Proves ConnectionError is a specialized AdapterError
        Quality Contribution: Enables granular error handling
        """
        from fs2.core.adapters.exceptions import AdapterConnectionError, AdapterError

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
        from fs2.core.adapters.exceptions import AdapterError, AuthenticationError

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


@pytest.mark.unit
class TestFileScannerError:
    """Tests for FileScannerError exception (T028)."""

    def test_given_file_scanner_error_then_inherits_from_adapter_error(self):
        """
        Purpose: Proves FileScannerError is a specialized AdapterError.
        Quality Contribution: Enables granular error handling for file scanning.

        Task: T028
        """
        from fs2.core.adapters.exceptions import AdapterError, FileScannerError

        assert issubclass(FileScannerError, AdapterError)
        assert issubclass(FileScannerError, Exception)

    def test_given_file_scanner_error_when_raised_then_can_be_caught_as_adapter_error(
        self,
    ):
        """
        Purpose: Proves FileScannerError can be caught with AdapterError handler.
        Quality Contribution: Supports hierarchical exception handling.

        Task: T028
        """
        from fs2.core.adapters.exceptions import AdapterError, FileScannerError

        with pytest.raises(AdapterError):
            raise FileScannerError("Permission denied: /etc/shadow")

    def test_given_file_scanner_error_with_message_then_message_accessible(self):
        """
        Purpose: Proves FileScannerError message is accessible.
        Quality Contribution: Enables actionable error messages.

        Task: T028
        """
        from fs2.core.adapters.exceptions import FileScannerError

        error = FileScannerError("Permission denied: /etc/shadow")

        assert "Permission denied" in str(error)


@pytest.mark.unit
class TestASTParserError:
    """Tests for ASTParserError exception (T029)."""

    def test_given_ast_parser_error_then_inherits_from_adapter_error(self):
        """
        Purpose: Proves ASTParserError is a specialized AdapterError.
        Quality Contribution: Enables granular error handling for AST parsing.

        Task: T029
        """
        from fs2.core.adapters.exceptions import AdapterError, ASTParserError

        assert issubclass(ASTParserError, AdapterError)
        assert issubclass(ASTParserError, Exception)

    def test_given_ast_parser_error_when_raised_then_can_be_caught_as_adapter_error(
        self,
    ):
        """
        Purpose: Proves ASTParserError can be caught with AdapterError handler.
        Quality Contribution: Supports hierarchical exception handling.

        Task: T029
        """
        from fs2.core.adapters.exceptions import AdapterError, ASTParserError

        with pytest.raises(AdapterError):
            raise ASTParserError("Unknown language: brainfuck")

    def test_given_ast_parser_error_with_message_then_message_accessible(self):
        """
        Purpose: Proves ASTParserError message is accessible.
        Quality Contribution: Enables actionable error messages.

        Task: T029
        """
        from fs2.core.adapters.exceptions import ASTParserError

        error = ASTParserError("Binary file detected: image.png")

        assert "Binary file" in str(error)


@pytest.mark.unit
class TestGraphStoreError:
    """Tests for GraphStoreError exception (T030)."""

    def test_given_graph_store_error_then_inherits_from_adapter_error(self):
        """
        Purpose: Proves GraphStoreError is a specialized AdapterError.
        Quality Contribution: Enables granular error handling for graph operations.

        Task: T030
        """
        from fs2.core.adapters.exceptions import AdapterError, GraphStoreError

        assert issubclass(GraphStoreError, AdapterError)
        assert issubclass(GraphStoreError, Exception)

    def test_given_graph_store_error_when_raised_then_can_be_caught_as_adapter_error(
        self,
    ):
        """
        Purpose: Proves GraphStoreError can be caught with AdapterError handler.
        Quality Contribution: Supports hierarchical exception handling.

        Task: T030
        """
        from fs2.core.adapters.exceptions import AdapterError, GraphStoreError

        with pytest.raises(AdapterError):
            raise GraphStoreError("Corrupted pickle file: graph.gpickle")

    def test_given_graph_store_error_with_message_then_message_accessible(self):
        """
        Purpose: Proves GraphStoreError message is accessible.
        Quality Contribution: Enables actionable error messages.

        Task: T030
        """
        from fs2.core.adapters.exceptions import GraphStoreError

        error = GraphStoreError("Failed to save graph: disk full")

        assert "Failed to save" in str(error)
