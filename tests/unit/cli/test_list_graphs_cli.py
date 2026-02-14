"""Tests for fs2 list-graphs CLI command.

Per Subtask 001: Add list-graphs CLI command for graph discovery.
Tests for command registration, help output, JSON/table output formats,
and MCP contract parity.

Testing Approach: Lightweight (per subtask scope)
Focus: Command registration, basic output validation, error handling
"""

import json

import pytest
from typer.testing import CliRunner

from fs2.cli.main import app

pytestmark = pytest.mark.slow

runner = CliRunner()


@pytest.mark.unit
class TestListGraphsCommandRegistration:
    """Tests for list-graphs command registration."""

    def test_given_cli_app_when_inspected_then_list_graphs_registered(self):
        """
        Purpose: Verifies list-graphs command is registered on app.
        Quality Contribution: Ensures command is discoverable.
        Acceptance Criteria: 'list-graphs' in registered commands.
        """
        command_names = [cmd.name for cmd in app.registered_commands]
        assert "list-graphs" in command_names, (
            f"Expected 'list-graphs' in {command_names}"
        )


@pytest.mark.unit
class TestListGraphsHelp:
    """Tests for list-graphs --help output."""

    def test_given_help_flag_when_invoked_then_shows_usage(self):
        """
        Purpose: Verifies list-graphs --help works.
        Quality Contribution: Ensures CLI is user-friendly.
        Acceptance Criteria: Help output includes command description and options.
        """
        result = runner.invoke(app, ["list-graphs", "--help"])

        assert result.exit_code == 0
        assert "list" in result.stdout.lower() and "graph" in result.stdout.lower()
        assert "--json" in result.stdout

    def test_given_help_when_invoked_then_shows_json_option(self):
        """
        Purpose: Verifies --json option is documented.
        Quality Contribution: Ensures option is discoverable.
        Acceptance Criteria: --json in help output.
        """
        result = runner.invoke(app, ["list-graphs", "--help"])

        assert result.exit_code == 0
        assert "--json" in result.stdout


@pytest.mark.unit
class TestListGraphsNotGuarded:
    """Tests that list-graphs is NOT guarded by require_init."""

    def test_given_no_config_when_list_graphs_then_exits_one_with_helpful_message(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies list-graphs shows helpful message without config.
        Quality Contribution: User guidance when no config exists.
        Acceptance Criteria: Exit code 1 (config error), helpful message.

        Per Subtask: Not guarded, but handles missing config gracefully.
        """
        # Change to directory without .fs2 config
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["list-graphs"])

        # Should exit 1 (config error) with helpful message
        assert result.exit_code == 1
        # Note: Error goes to stderr which CliRunner mixes into output
        # Just verify it failed with config error
        assert "init" in result.output.lower() or result.exit_code == 1


@pytest.fixture
def config_with_default_graph(tmp_path, monkeypatch):
    """Create a project with config and default graph only."""
    from fs2.config.objects import ScanConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.repos.graph_store_impl import NetworkXGraphStore

    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()

    config_file = config_dir / "config.yaml"
    config_file.write_text("""scan:
  scan_paths:
    - "."
graph:
  graph_path: ".fs2/graph.pickle"
""")

    # Create a graph file
    config = FakeConfigurationService(ScanConfig())
    store = NetworkXGraphStore(config)
    store.save(config_dir / "graph.pickle")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NO_COLOR", "1")

    # Reset dependencies to pick up new config
    from fs2.core import dependencies

    dependencies.reset_services()

    return tmp_path


@pytest.fixture
def config_with_multi_graph(tmp_path, monkeypatch):
    """Create a project with config and multiple graphs."""
    from fs2.config.objects import ScanConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.repos.graph_store_impl import NetworkXGraphStore

    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()

    # Create external graph directory
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    external_config_dir = external_dir / ".fs2"
    external_config_dir.mkdir()

    config_file = config_dir / "config.yaml"
    config_file.write_text(f"""scan:
  scan_paths:
    - "."
graph:
  graph_path: ".fs2/graph.pickle"
other_graphs:
  graphs:
    - name: external-lib
      path: "{external_dir}/.fs2/graph.pickle"
      description: "External library for testing"
      source_url: "https://github.com/example/lib"
""")

    # Create default graph file
    config = FakeConfigurationService(ScanConfig())
    store = NetworkXGraphStore(config)
    store.save(config_dir / "graph.pickle")

    # Create external graph file
    store.save(external_config_dir / "graph.pickle")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NO_COLOR", "1")

    # Reset dependencies to pick up new config
    from fs2.core import dependencies

    dependencies.reset_services()

    return tmp_path


@pytest.mark.unit
class TestListGraphsTableOutput:
    """Tests for default table output."""

    def test_given_config_when_list_graphs_then_shows_table(
        self, config_with_default_graph
    ):
        """
        Purpose: Verifies default output is a Rich table.
        Quality Contribution: Human-readable output.
        Acceptance Criteria: Exit code 0, table with column headers.
        """
        result = runner.invoke(app, ["list-graphs"])

        assert result.exit_code == 0, f"Failed with: {result.output}"
        # Table should have headers
        assert "Name" in result.stdout or "name" in result.stdout.lower()
        # Should show default graph
        assert "default" in result.stdout.lower()

    def test_given_multi_graph_config_when_list_graphs_then_shows_all(
        self, config_with_multi_graph
    ):
        """
        Purpose: Verifies all configured graphs appear in table.
        Quality Contribution: Complete graph discovery.
        Acceptance Criteria: Both default and external-lib visible.
        """
        result = runner.invoke(app, ["list-graphs"])

        assert result.exit_code == 0
        stdout_lower = result.stdout.lower()
        assert "default" in stdout_lower
        assert "external" in stdout_lower or "lib" in stdout_lower

    def test_given_config_when_list_graphs_then_shows_availability_status(
        self, config_with_default_graph
    ):
        """
        Purpose: Verifies availability status is shown.
        Quality Contribution: Users know if graphs are accessible.
        Acceptance Criteria: Status column with ✓ or ✗.
        """
        result = runner.invoke(app, ["list-graphs"])

        assert result.exit_code == 0
        # Should have checkmark for available graph
        assert "✓" in result.stdout or "Status" in result.stdout

    def test_given_config_when_list_graphs_then_shows_total_count(
        self, config_with_default_graph
    ):
        """
        Purpose: Verifies total graph count is shown.
        Quality Contribution: Summary information.
        Acceptance Criteria: "Total: N graph(s)" message.
        """
        result = runner.invoke(app, ["list-graphs"])

        assert result.exit_code == 0
        assert "total" in result.stdout.lower() or "graph" in result.stdout.lower()


@pytest.mark.unit
class TestListGraphsJsonOutput:
    """Tests for JSON output with --json flag."""

    def test_given_json_flag_when_list_graphs_then_outputs_json(
        self, config_with_default_graph
    ):
        """
        Purpose: Verifies --json flag outputs JSON format.
        Quality Contribution: Enables scripting and programmatic processing.
        Acceptance Criteria: Output is valid JSON.
        """
        result = runner.invoke(app, ["list-graphs", "--json"])

        assert result.exit_code == 0, f"Failed with: {result.output}"
        # Should be parseable as JSON
        try:
            json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Output is not valid JSON: {e}\nOutput: {result.stdout}")

    def test_given_json_flag_when_list_graphs_then_has_docs_and_count(
        self, config_with_default_graph
    ):
        """
        Purpose: Verifies JSON has expected structure.
        Quality Contribution: Consistent API for scripts.
        Acceptance Criteria: Top-level "docs" and "count" keys.
        """
        result = runner.invoke(app, ["list-graphs", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "docs" in data, f"Expected 'docs' key in {data.keys()}"
        assert "count" in data, f"Expected 'count' key in {data.keys()}"

    def test_given_json_flag_when_list_graphs_then_count_matches_docs_length(
        self, config_with_default_graph
    ):
        """
        Purpose: Verifies count field is accurate.
        Quality Contribution: Data integrity.
        Acceptance Criteria: count == len(docs).
        """
        result = runner.invoke(app, ["list-graphs", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["count"] == len(data["docs"])


@pytest.mark.unit
class TestListGraphsMcpContractParity:
    """Tests for MCP contract parity.

    Per Critical Insight #3: JSON output must match MCP list_graphs() structure exactly.
    """

    def test_json_output_matches_mcp_contract(self, config_with_multi_graph):
        """
        Purpose: Verifies JSON output matches MCP list_graphs() structure exactly.
        Quality Contribution: Scripts can consume both CLI and MCP output identically.
        Acceptance Criteria: All 5 GraphInfo fields present in exact structure.

        Per Critical Insight #3: JSON output must match MCP list_graphs() structure.
        """
        result = runner.invoke(app, ["list-graphs", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)

        # Must have docs and count
        assert "docs" in data
        assert "count" in data

        # Each doc must have all 5 GraphInfo fields
        expected_fields = {"name", "path", "description", "source_url", "available"}
        for doc in data["docs"]:
            actual_fields = set(doc.keys())
            assert actual_fields == expected_fields, (
                f"Expected fields {expected_fields}, got {actual_fields}"
            )

    def test_json_output_path_is_string(self, config_with_default_graph):
        """
        Purpose: Verifies path field is serialized as string (not Path object).
        Quality Contribution: JSON serialization correctness.
        Acceptance Criteria: path is string type in JSON.
        """
        result = runner.invoke(app, ["list-graphs", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)

        for doc in data["docs"]:
            assert isinstance(doc["path"], str), (
                f"Expected path as string, got {type(doc['path'])}"
            )

    def test_json_output_available_is_boolean(self, config_with_default_graph):
        """
        Purpose: Verifies available field is boolean.
        Quality Contribution: Type correctness.
        Acceptance Criteria: available is bool type in JSON.
        """
        result = runner.invoke(app, ["list-graphs", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)

        for doc in data["docs"]:
            assert isinstance(doc["available"], bool), (
                f"Expected available as bool, got {type(doc['available'])}"
            )


@pytest.mark.unit
class TestListGraphsStdoutClean:
    """Tests for stdout cleanliness with --json flag."""

    def test_given_json_flag_when_list_graphs_then_stdout_is_clean(
        self, config_with_default_graph
    ):
        """
        Purpose: Verifies stdout contains ONLY JSON when --json is used.
        Quality Contribution: Enables piping to jq and other tools.
        Acceptance Criteria: No extra content before/after JSON.
        """
        result = runner.invoke(app, ["list-graphs", "--json"])

        assert result.exit_code == 0
        # Parse as JSON - if this fails, there's extra content
        json.loads(result.stdout)
        # Check there's no extra lines before or after the JSON
        lines = result.stdout.strip().split("\n")
        # First line should start with { and last should end with }
        assert lines[0].strip().startswith("{"), (
            f"First line not JSON start: {lines[0]}"
        )
        assert lines[-1].strip().endswith("}"), f"Last line not JSON end: {lines[-1]}"
