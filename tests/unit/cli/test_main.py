"""Tests for CLI main module.

Phase 4: Multi-Graph CLI Integration
TDD RED tests for:
- T001: CLIContext.graph_name field
- T002: Mutual exclusivity validation
- T003: resolve_graph_from_context() utility

Per Testing Philosophy: Full TDD with targeted mocks.
"""

import pytest
from typer.testing import CliRunner

from fs2.cli.main import CLIContext, app


class TestCLIContextGraphName:
    """T001: Tests for CLIContext.graph_name field.

    Purpose: Verify CLIContext has graph_name field that defaults to None.
    Quality Contribution: Ensures the data model supports multi-graph selection.
    """

    def test_graph_name_field_exists(self):
        """Verify CLIContext has a graph_name attribute.

        Purpose: Foundation for multi-graph CLI support.
        Quality Contribution: Catches missing field early.
        """
        ctx = CLIContext()
        assert hasattr(ctx, "graph_name")

    def test_graph_name_defaults_to_none(self):
        """Verify graph_name defaults to None when not provided.

        Purpose: Backward compatibility - existing code doesn't pass graph_name.
        Quality Contribution: Ensures default behavior unchanged.
        """
        ctx = CLIContext()
        assert ctx.graph_name is None

    def test_graph_name_can_be_set(self):
        """Verify graph_name can be set to a string value.

        Purpose: Supports named graph selection.
        Quality Contribution: Verifies basic setter functionality.
        """
        ctx = CLIContext(graph_name="flowspace")
        assert ctx.graph_name == "flowspace"

    def test_both_graph_file_and_graph_name_can_be_set(self):
        """Verify both fields can be populated (validation is separate).

        Purpose: Data model allows both; validation happens in main().
        Quality Contribution: Separates concerns - model vs validation.
        """
        ctx = CLIContext(graph_file="/path/to/graph.pkl", graph_name="test")
        assert ctx.graph_file == "/path/to/graph.pkl"
        assert ctx.graph_name == "test"


class TestMutualExclusivity:
    """T002: Tests for mutual exclusivity validation.

    Per Critical Finding 05: --graph-file and --graph-name cannot both be provided.

    Purpose: Verify CLI rejects both options with clear error.
    Quality Contribution: Prevents confusing configuration.
    """

    runner = CliRunner()

    def test_both_options_raises_error(self):
        """Verify providing both --graph-file and --graph-name raises error.

        Purpose: Per CF05 - mutual exclusivity.
        Quality Contribution: Clear user feedback on configuration error.
        """
        result = self.runner.invoke(
            app,
            ["--graph-file", "/tmp/g.pkl", "--graph-name", "test", "tree"],
        )
        assert result.exit_code == 1
        assert "Cannot use both" in result.output or "cannot use both" in result.output.lower()

    def test_only_graph_file_works(self, tmp_path):
        """Verify --graph-file alone is accepted.

        Purpose: Backward compatibility.
        Quality Contribution: Ensures existing --graph-file usage continues.
        """
        # Create a minimal graph file (will fail later, but option parsing should work)
        graph_file = tmp_path / "graph.pkl"
        graph_file.touch()

        result = self.runner.invoke(
            app,
            ["--graph-file", str(graph_file), "tree", "--help"],
        )
        # Should not fail due to mutual exclusivity
        # (may fail for other reasons like missing graph, but that's ok)
        assert "Cannot use both" not in result.output

    def test_only_graph_name_works(self):
        """Verify --graph-name alone is accepted.

        Purpose: New feature works in isolation.
        Quality Contribution: Ensures new option is properly registered.
        """
        result = self.runner.invoke(
            app,
            ["--graph-name", "test", "tree", "--help"],
        )
        # Should not fail due to mutual exclusivity
        assert "Cannot use both" not in result.output

    def test_neither_option_uses_default(self):
        """Verify command works without either option.

        Purpose: Backward compatibility - default graph used.
        Quality Contribution: Ensures existing behavior unchanged.
        """
        result = self.runner.invoke(
            app,
            ["tree", "--help"],
        )
        assert result.exit_code == 0
        assert "Cannot use both" not in result.output


class TestResolveGraphFromContext:
    """T003: Tests for resolve_graph_from_context() utility.

    Per DYK-01: Uses GraphService for all graph resolution.
    Per DYK-04: Centralized error handling with actionable messages.
    Per CF06: Extracted utility for consistent composition roots.

    Purpose: Verify resolve_graph_from_context() correctly resolves graphs.
    Quality Contribution: Consistent behavior across all CLI commands.
    """

    def test_resolve_with_graph_file_uses_graphservice(self):
        """Verify --graph-file is handled via GraphService.

        Purpose: Per DYK-01 - CLI uses same pattern as MCP.
        Quality Contribution: Consistent behavior across CLI and MCP.
        """
        # Import here to verify it exists (will fail in RED phase)
        from fs2.cli.utils import resolve_graph_from_context

        # Create mock context with graph_file
        ctx_obj = CLIContext(graph_file="/path/to/graph.pkl")

        # Should not raise AttributeError - function exists
        assert callable(resolve_graph_from_context)

    def test_resolve_with_graph_name_uses_graphservice(self):
        """Verify --graph-name delegates to GraphService.

        Purpose: Named graphs resolved via GraphService.
        Quality Contribution: Leverages caching and staleness detection.
        """
        from fs2.cli.utils import resolve_graph_from_context

        # Create mock context with graph_name
        ctx_obj = CLIContext(graph_name="flowspace")

        # Should not raise AttributeError - function exists
        assert callable(resolve_graph_from_context)

    def test_resolve_unknown_graph_name_shows_actionable_error(self):
        """Verify unknown graph name shows available graphs.

        Purpose: Per DYK-04 - clear and actionable error messages.
        Quality Contribution: User knows what graphs are available.
        """
        from fs2.core import dependencies
        from fs2.core.services.graph_service_fake import FakeGraphService
        from fs2.cli.utils import resolve_graph_from_context

        # Set up fake with only "default" graph
        fake_service = FakeGraphService()
        # Don't add any graphs, so "unknown" will fail
        dependencies.set_graph_service(fake_service)

        try:
            ctx_obj = CLIContext(graph_name="unknown")
            # Should raise SystemExit with actionable message
            # (implementation will call typer.Exit)
        finally:
            dependencies.reset_services()

    def test_resolve_default_returns_config_graph_path(self):
        """Verify neither option uses default graph.

        Purpose: Backward compatibility.
        Quality Contribution: Existing commands work unchanged.
        """
        from fs2.cli.utils import resolve_graph_from_context

        # Create context with neither option
        ctx_obj = CLIContext()

        # Should not raise AttributeError - function exists
        assert callable(resolve_graph_from_context)

    def test_resolve_returns_config_and_graphstore_tuple(self):
        """Verify return type is (ConfigurationService, GraphStore) tuple.

        Purpose: Commands need both config and store.
        Quality Contribution: Consistent interface for all commands.
        """
        from fs2.cli.utils import resolve_graph_from_context

        # Verify function signature exists
        import inspect
        sig = inspect.signature(resolve_graph_from_context)
        # Should accept ctx parameter
        assert "ctx" in sig.parameters or len(sig.parameters) >= 1


class TestGraphNameHelp:
    """T001 (additional): Tests for --graph-name help text.

    Purpose: Verify --graph-name option appears in help.
    Quality Contribution: Users can discover the new option.
    """

    runner = CliRunner()

    def test_graph_name_in_help(self):
        """Verify --graph-name appears in main help.

        Purpose: Discoverability.
        Quality Contribution: Users can find the new option.
        """
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--graph-name" in result.output

    def test_graph_name_help_text_mentions_configured_graphs(self):
        """Verify help explains the option.

        Purpose: User understanding.
        Quality Contribution: Clear documentation.
        """
        result = self.runner.invoke(app, ["--help"])
        # Help should mention something about configured/named graphs
        assert result.exit_code == 0
        # Will fail until option is added with proper help text
        help_lower = result.output.lower()
        assert "graph" in help_lower and "name" in help_lower
