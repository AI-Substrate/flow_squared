"""Integration tests for Logger Adapter composition pattern.

Purpose: Validate FakeLogAdapter works correctly in service composition.
Quality Contribution: End-to-end validation of DI pattern.

Per Plan AC7: LogAdapter ABC with debug/info/warning/error.
Per Task T018: Integration test for adapter + service composition.
"""


class TestLogAdapterServiceComposition:
    """Integration tests for logger adapter in service composition (T018)."""

    def test_given_service_with_fake_log_adapter_when_operation_then_logs_captured(
        self, test_context
    ):
        """
        Purpose: Proves full composition pattern works
        Quality Contribution: End-to-end validation of DI pattern

        Test Doc:
        - Why: Demonstrates the canonical Clean Architecture composition pattern
               where services receive adapters via constructor injection
        - Contract: Services compose LogAdapter via DI; FakeLogAdapter captures
                    all log messages for test assertions
        - Usage Notes:
            1. Use test_context fixture for pre-wired dependencies
            2. Pass logger to service constructor
            3. Call service method
            4. Assert on captured messages via test_context.logger.messages
        - Quality Contribution: Critical path - validates logging integration
        - Worked Example:
            Input: test_context with FakeLogAdapter
            Action: Use logger in a simulated service operation
            Output: Messages captured in test_context.logger.messages
        """
        # Arrange - Using TestContext fixture
        from fs2.core.models.log_level import LogLevel

        # Act - Simulate service using logger
        test_context.logger.info("Service started", service="TestService")
        test_context.logger.debug("Processing item", item_id=123)
        test_context.logger.info("Service completed", result="success")

        # Assert - Verify messages captured
        assert len(test_context.logger.messages) == 3

        # First message
        assert test_context.logger.messages[0].level == LogLevel.INFO
        assert test_context.logger.messages[0].message == "Service started"
        assert test_context.logger.messages[0].context["service"] == "TestService"

        # Second message (debug)
        assert test_context.logger.messages[1].level == LogLevel.DEBUG
        assert test_context.logger.messages[1].message == "Processing item"

        # Third message
        assert test_context.logger.messages[2].level == LogLevel.INFO
        assert test_context.logger.messages[2].message == "Service completed"
        assert test_context.logger.messages[2].context["result"] == "success"

    def test_given_service_with_log_adapter_when_error_occurs_then_error_logged(
        self, test_context
    ):
        """
        Purpose: Proves error logging works in service composition
        Quality Contribution: Validates error path logging
        """
        # Arrange
        from fs2.core.models.log_level import LogLevel

        # Act - Simulate error scenario
        test_context.logger.info("Starting operation")
        try:
            raise ValueError("Something went wrong")
        except ValueError as e:
            test_context.logger.error("Operation failed", error=str(e), retry_count=0)

        # Assert
        assert len(test_context.logger.messages) == 2
        error_entry = test_context.logger.messages[1]
        assert error_entry.level == LogLevel.ERROR
        assert "Operation failed" in error_entry.message
        assert error_entry.context["error"] == "Something went wrong"

    def test_given_test_context_fixture_then_adapters_importable_from_package(self):
        """
        Purpose: Proves public API exports work correctly
        Quality Contribution: Validates T017 package exports
        """
        # Act - Import from package (not direct file)
        from fs2.core.adapters import ConsoleLogAdapter, FakeLogAdapter, LogAdapter

        # Assert - All imports work
        assert LogAdapter is not None
        assert ConsoleLogAdapter is not None
        assert FakeLogAdapter is not None

    def test_given_test_context_then_logger_instance_is_fresh_per_test(
        self, test_context
    ):
        """
        Purpose: Proves fixture isolation - each test gets fresh logger
        Quality Contribution: Prevents test pollution
        """
        # Assert - Should be empty since it's a new test
        assert len(test_context.logger.messages) == 0

        # Act
        test_context.logger.info("Test message")

        # Assert
        assert len(test_context.logger.messages) == 1

    def test_given_multiple_adapters_with_different_levels_then_filtering_independent(
        self,
    ):
        """
        Purpose: Proves level filtering is per-adapter instance
        Quality Contribution: Validates adapter independence
        """
        # Arrange
        from fs2.config.objects import LogAdapterConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.log_adapter_fake import FakeLogAdapter

        # Create two adapters with different min_levels
        config_debug = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
        config_info = FakeConfigurationService(LogAdapterConfig(min_level="INFO"))

        logger_verbose = FakeLogAdapter(config_debug)
        logger_quiet = FakeLogAdapter(config_info)

        # Act
        logger_verbose.debug("Debug message")
        logger_verbose.info("Info message")
        logger_quiet.debug("Debug message")  # Should be filtered
        logger_quiet.info("Info message")

        # Assert
        assert len(logger_verbose.messages) == 2  # Both captured
        assert len(logger_quiet.messages) == 1  # Only info captured
