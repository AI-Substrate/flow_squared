"""Tests for FakeLspAdapter test double.

TDD Phase: RED - These tests should fail until T006 is implemented.

Tests cover:
- AC06: FakeLspAdapter inherits from ABC with call_history tracking
- Per DYK-1: Method-specific response setters (set_definition_response, set_references_response)
- Per Discovery 08: set_error for error simulation
- is_ready lifecycle (False until initialized, True after, False after shutdown)

Per Testing Philosophy: Full TDD approach.
"""

from pathlib import Path

import pytest

from fs2.core.models.code_edge import CodeEdge
from fs2.core.models.edge_type import EdgeType


@pytest.mark.unit
class TestFakeLspAdapter:
    """Tests for FakeLspAdapter test double behavior."""

    def test_given_fake_adapter_when_initialized_then_receives_config_service(self):
        """Per Discovery 06: Receives ConfigurationService, calls require() internally.

        Purpose: Proves FakeLspAdapter follows ConfigurationService injection pattern
        Quality Contribution: Ensures no concept leakage
        """
        from fs2.config.objects import LspConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.lsp_adapter_fake import FakeLspAdapter

        config = FakeConfigurationService(LspConfig(timeout_seconds=10.0))
        adapter = FakeLspAdapter(config)

        # Should not raise MissingConfigurationError
        assert adapter is not None

    def test_given_fake_adapter_when_missing_config_then_raises(self):
        """MissingConfigurationError raised when LspConfig not in registry.

        Purpose: Proves config.require() is used
        Quality Contribution: Catches misconfigured test setups
        """
        from fs2.config.service import (
            FakeConfigurationService,
            MissingConfigurationError,
        )
        from fs2.core.adapters.lsp_adapter_fake import FakeLspAdapter

        config = FakeConfigurationService()  # No LspConfig registered

        with pytest.raises(MissingConfigurationError):
            FakeLspAdapter(config)

    def test_given_fake_adapter_when_set_references_response_then_returns_for_get_references(
        self,
    ):
        """AC06: FakeLspAdapter supports method-specific response setters (DYK-1).

        Purpose: Proves method-specific setters work correctly
        Quality Contribution: Enables independent response configuration
        """
        from fs2.config.objects import LspConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.lsp_adapter_fake import FakeLspAdapter

        config = FakeConfigurationService(LspConfig())
        adapter = FakeLspAdapter(config)

        refs = [
            CodeEdge(
                source_node_id="file:app.py",
                target_node_id="file:lib.py",
                edge_type=EdgeType.REFERENCES,
                confidence=1.0,
                resolution_rule="lsp:references",
            )
        ]
        adapter.set_references_response(refs)

        # Must initialize before get_references
        adapter.initialize("python", Path("/project"))
        result = adapter.get_references("app.py", line=10, column=5)

        assert result == refs

    def test_given_fake_adapter_when_set_definition_response_then_returns_for_get_definition(
        self,
    ):
        """AC06: Method-specific setters allow independent response configuration (DYK-1).

        Purpose: Proves definition and references responses are independent
        Quality Contribution: Enables testing scenarios using both methods
        """
        from fs2.config.objects import LspConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.lsp_adapter_fake import FakeLspAdapter

        config = FakeConfigurationService(LspConfig())
        adapter = FakeLspAdapter(config)

        definition = [
            CodeEdge(
                source_node_id="file:app.py",
                target_node_id="file:base.py",
                edge_type=EdgeType.CALLS,
                confidence=1.0,
                resolution_rule="lsp:definition",
            )
        ]
        refs = [
            CodeEdge(
                source_node_id="file:other.py",
                target_node_id="file:app.py",
                edge_type=EdgeType.REFERENCES,
                confidence=1.0,
                resolution_rule="lsp:references",
            )
        ]
        adapter.set_definition_response(definition)
        adapter.set_references_response(refs)

        adapter.initialize("python", Path("/project"))

        # Each method returns its own configured response
        assert adapter.get_definition("app.py", line=10, column=5) == definition
        assert adapter.get_references("app.py", line=10, column=5) == refs

    def test_given_fake_adapter_when_called_then_records_call_history(self):
        """AC06: FakeLspAdapter tracks all method calls.

        Purpose: Proves call_history tracking works
        Quality Contribution: Enables verification of call sequences
        """
        from fs2.config.objects import LspConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.lsp_adapter_fake import FakeLspAdapter

        config = FakeConfigurationService(LspConfig())
        adapter = FakeLspAdapter(config)
        adapter.set_references_response([])

        adapter.initialize("python", Path("/project"))
        adapter.get_references("app.py", line=10, column=5)
        adapter.shutdown()

        assert len(adapter.call_history) == 3
        assert adapter.call_history[0]["method"] == "initialize"
        assert adapter.call_history[1]["method"] == "get_references"
        assert adapter.call_history[2]["method"] == "shutdown"

    def test_given_fake_adapter_when_set_error_then_raises_on_call(self):
        """Per Discovery 08: Fake supports error simulation.

        Purpose: Proves error simulation works
        Quality Contribution: Enables testing error handling paths
        """
        from fs2.config.objects import LspConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.exceptions import LspTimeoutError
        from fs2.core.adapters.lsp_adapter_fake import FakeLspAdapter

        config = FakeConfigurationService(LspConfig())
        adapter = FakeLspAdapter(config)

        adapter.set_error(LspTimeoutError("Simulated timeout"))
        adapter.initialize("python", Path("/project"))

        with pytest.raises(LspTimeoutError, match="Simulated timeout"):
            adapter.get_references("app.py", line=10, column=5)

    def test_given_fake_adapter_when_is_ready_then_returns_configured_state(self):
        """is_ready() should be controllable for testing initialization failures.

        Purpose: Proves is_ready lifecycle works correctly
        Quality Contribution: Enables testing graceful degradation
        """
        from fs2.config.objects import LspConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.lsp_adapter_fake import FakeLspAdapter

        config = FakeConfigurationService(LspConfig())
        adapter = FakeLspAdapter(config)

        # Default: not ready until initialized
        assert adapter.is_ready() is False

        # After initialize: ready
        adapter.initialize("python", Path("/project"))
        assert adapter.is_ready() is True

        # After shutdown: not ready
        adapter.shutdown()
        assert adapter.is_ready() is False

    def test_given_fake_adapter_when_inheriting_then_is_lsp_adapter(self):
        """FakeLspAdapter inherits from LspAdapter ABC.

        Purpose: Proves implementation follows ABC pattern
        Quality Contribution: Ensures type compatibility
        """
        from fs2.config.objects import LspConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.lsp_adapter import LspAdapter
        from fs2.core.adapters.lsp_adapter_fake import FakeLspAdapter

        config = FakeConfigurationService(LspConfig())
        adapter = FakeLspAdapter(config)

        assert isinstance(adapter, LspAdapter)
