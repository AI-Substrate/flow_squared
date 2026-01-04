"""Tests for adapter ABC interfaces.

Tests verify:
- ABC enforcement (TypeError on direct instantiation)
- Required abstract methods defined
- Method signatures correct

Architecture: Each ABC is in its own file:
- log_adapter.py → LogAdapter
- console_adapter.py → ConsoleAdapter
- sample_adapter.py → SampleAdapter

Per Plan 2.1-2.4, 2.11: LogAdapter, ConsoleAdapter, SampleAdapter ABCs
Per AC4: ABC + @abstractmethod for explicit contracts
"""

import inspect

import pytest


@pytest.mark.unit
class TestLogAdapterABC:
    """Tests for LogAdapter abstract base class."""

    def test_given_log_adapter_abc_when_instantiating_directly_then_raises_type_error(
        self,
    ):
        """
        Purpose: Proves ABC enforcement prevents direct instantiation
        Quality Contribution: Ensures all adapters implement required methods
        Acceptance Criteria:
        - LogAdapter() raises TypeError
        - Message mentions abstract methods
        """
        from fs2.core.adapters.log_adapter import LogAdapter

        with pytest.raises(TypeError) as exc_info:
            LogAdapter()

        assert "abstract" in str(exc_info.value).lower()

    def test_given_log_adapter_abc_then_has_debug_method(self):
        """
        Purpose: Proves LogAdapter defines debug method
        Quality Contribution: Documents required interface
        """
        from fs2.core.adapters.log_adapter import LogAdapter

        abstract_methods = [
            name
            for name, method in inspect.getmembers(LogAdapter)
            if getattr(method, "__isabstractmethod__", False)
        ]

        assert "debug" in abstract_methods

    def test_given_log_adapter_abc_then_has_info_method(self):
        """
        Purpose: Proves LogAdapter defines info method
        Quality Contribution: Documents required interface
        """
        from fs2.core.adapters.log_adapter import LogAdapter

        abstract_methods = [
            name
            for name, method in inspect.getmembers(LogAdapter)
            if getattr(method, "__isabstractmethod__", False)
        ]

        assert "info" in abstract_methods

    def test_given_log_adapter_abc_then_has_warning_method(self):
        """
        Purpose: Proves LogAdapter defines warning method
        Quality Contribution: Documents required interface
        """
        from fs2.core.adapters.log_adapter import LogAdapter

        abstract_methods = [
            name
            for name, method in inspect.getmembers(LogAdapter)
            if getattr(method, "__isabstractmethod__", False)
        ]

        assert "warning" in abstract_methods

    def test_given_log_adapter_abc_then_has_error_method(self):
        """
        Purpose: Proves LogAdapter defines error method
        Quality Contribution: Documents required interface
        """
        from fs2.core.adapters.log_adapter import LogAdapter

        abstract_methods = [
            name
            for name, method in inspect.getmembers(LogAdapter)
            if getattr(method, "__isabstractmethod__", False)
        ]

        assert "error" in abstract_methods

    def test_given_log_adapter_abc_then_all_four_methods_are_abstract(self):
        """
        Purpose: Proves LogAdapter requires exactly 4 abstract methods
        Quality Contribution: Ensures complete interface definition
        """
        from fs2.core.adapters.log_adapter import LogAdapter

        abstract_methods = [
            name
            for name, method in inspect.getmembers(LogAdapter)
            if getattr(method, "__isabstractmethod__", False)
        ]

        assert set(abstract_methods) == {"debug", "info", "warning", "error"}


@pytest.mark.unit
class TestConsoleAdapterABC:
    """Tests for ConsoleAdapter abstract base class."""

    def test_given_console_adapter_abc_when_instantiating_directly_then_raises_type_error(
        self,
    ):
        """
        Purpose: Proves ABC enforcement prevents direct instantiation
        Quality Contribution: Ensures all console adapters implement required methods
        Acceptance Criteria:
        - ConsoleAdapter() raises TypeError
        - Message mentions abstract methods
        """
        from fs2.core.adapters.console_adapter import ConsoleAdapter

        with pytest.raises(TypeError) as exc_info:
            ConsoleAdapter()

        assert "abstract" in str(exc_info.value).lower()

    def test_given_console_adapter_abc_then_has_print_method(self):
        """
        Purpose: Proves ConsoleAdapter defines print method
        Quality Contribution: Documents required interface for Rich wrapping
        """
        from fs2.core.adapters.console_adapter import ConsoleAdapter

        abstract_methods = [
            name
            for name, method in inspect.getmembers(ConsoleAdapter)
            if getattr(method, "__isabstractmethod__", False)
        ]

        assert "print" in abstract_methods

    def test_given_console_adapter_abc_then_has_input_method(self):
        """
        Purpose: Proves ConsoleAdapter defines input method
        Quality Contribution: Documents required interface
        """
        from fs2.core.adapters.console_adapter import ConsoleAdapter

        abstract_methods = [
            name
            for name, method in inspect.getmembers(ConsoleAdapter)
            if getattr(method, "__isabstractmethod__", False)
        ]

        assert "input" in abstract_methods

    def test_given_console_adapter_abc_then_exactly_eleven_methods_are_abstract(self):
        """
        Purpose: Proves ConsoleAdapter requires exactly 11 abstract methods
        Quality Contribution: Ensures complete rich console interface definition
        """
        from fs2.core.adapters.console_adapter import ConsoleAdapter

        abstract_methods = [
            name
            for name, method in inspect.getmembers(ConsoleAdapter)
            if getattr(method, "__isabstractmethod__", False)
        ]

        assert set(abstract_methods) == {
            "print",
            "print_line",
            "print_success",
            "print_error",
            "print_warning",
            "print_progress",
            "print_info",
            "stage_banner",
            "stage_banner_skipped",
            "panel",
            "input",
        }


@pytest.mark.unit
class TestSampleAdapterABC:
    """Tests for SampleAdapter abstract base class."""

    def test_given_sample_adapter_abc_when_instantiating_directly_then_raises_type_error(
        self,
    ):
        """
        Purpose: Proves ABC enforcement prevents direct instantiation
        Quality Contribution: Ensures all sample adapters implement required methods
        """
        from fs2.core.adapters.sample_adapter import SampleAdapter

        with pytest.raises(TypeError) as exc_info:
            SampleAdapter()

        assert "abstract" in str(exc_info.value).lower()

    def test_given_sample_adapter_abc_then_has_process_method(self):
        """
        Purpose: Proves SampleAdapter defines process method
        Quality Contribution: Documents required interface for Phase 4
        """
        from fs2.core.adapters.sample_adapter import SampleAdapter

        abstract_methods = [
            name
            for name, method in inspect.getmembers(SampleAdapter)
            if getattr(method, "__isabstractmethod__", False)
        ]

        assert "process" in abstract_methods

    def test_given_sample_adapter_abc_then_has_validate_method(self):
        """
        Purpose: Proves SampleAdapter defines validate method
        Quality Contribution: Documents validation capability
        """
        from fs2.core.adapters.sample_adapter import SampleAdapter

        abstract_methods = [
            name
            for name, method in inspect.getmembers(SampleAdapter)
            if getattr(method, "__isabstractmethod__", False)
        ]

        assert "validate" in abstract_methods

    def test_given_sample_adapter_abc_then_exactly_two_methods_are_abstract(self):
        """
        Purpose: Proves SampleAdapter requires exactly 2 abstract methods
        Quality Contribution: Ensures complete interface definition
        """
        from fs2.core.adapters.sample_adapter import SampleAdapter

        abstract_methods = [
            name
            for name, method in inspect.getmembers(SampleAdapter)
            if getattr(method, "__isabstractmethod__", False)
        ]

        assert set(abstract_methods) == {"process", "validate"}
