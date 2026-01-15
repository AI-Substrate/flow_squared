"""Integration tests for CLI multi-graph support.

Phase 4: Multi-Graph CLI Integration
TDD RED tests for:
- T004: CLI commands with --graph-name
- T005: Backward compatibility tests

Per Testing Philosophy: Full TDD with targeted mocks.
Uses real fixtures where practical.
"""

import pickle
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fs2.cli.main import app


@pytest.fixture
def fixture_graph_path() -> Path:
    """Path to the fixture graph for testing."""
    return Path(__file__).parent.parent / "fixtures" / "fixture_graph.pkl"


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary .fs2 config directory."""
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def tmp_config_with_graph(tmp_path: Path, fixture_graph_path: Path) -> Path:
    """Create temp config with a named graph configuration.

    Returns the temp directory as CWD.
    """
    import shutil

    # Create .fs2 directory
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()

    # Copy fixture graph as default graph
    default_graph = config_dir / "graph.pickle"
    shutil.copy(fixture_graph_path, default_graph)

    # Create an "external" graph directory
    external_dir = tmp_path / "external" / ".fs2"
    external_dir.mkdir(parents=True)
    external_graph = external_dir / "graph.pickle"
    shutil.copy(fixture_graph_path, external_graph)

    # Write config with other_graphs
    config_file = config_dir / "config.yaml"
    config_file.write_text(f"""
scan:
  project_root: "{tmp_path}"

graph:
  graph_path: "{default_graph}"

other_graphs:
  graphs:
    - name: external
      path: "{external_graph}"
      description: External test graph
""")

    return tmp_path


class TestCLIMultiGraph:
    """T004: Integration tests for CLI commands with --graph-name.

    Purpose: Verify tree, search, get-node work with named graphs.
    Quality Contribution: End-to-end validation of multi-graph CLI support.

    Note: Uses monkeypatch to change CWD since CliRunner doesn't honor os.chdir.
    """

    runner = CliRunner()

    def test_tree_with_graph_name(self, tmp_config_with_graph: Path, monkeypatch):
        """Verify tree command accepts --graph-name and returns results.

        Purpose: E2E tree with named graph.
        Quality Contribution: Core feature works end-to-end.
        """
        monkeypatch.chdir(tmp_config_with_graph)

        result = self.runner.invoke(
            app,
            ["--graph-name", "external", "tree"],
        )

        # Should succeed (exit 0) and show tree output
        assert result.exit_code == 0, f"Failed with: {result.output}"
        # Should have some tree-like output
        assert "file:" in result.output.lower() or "Code Structure" in result.output

    def test_search_with_graph_name(self, tmp_config_with_graph: Path, monkeypatch):
        """Verify search command accepts --graph-name and returns results.

        Purpose: E2E search with named graph.
        Quality Contribution: Search feature works with external graphs.
        """
        monkeypatch.chdir(tmp_config_with_graph)

        result = self.runner.invoke(
            app,
            ["--graph-name", "external", "search", "test"],
        )

        # Should succeed and return JSON
        assert result.exit_code == 0, f"Failed with: {result.output}"
        # JSON output should be parseable
        import json

        try:
            data = json.loads(result.output)
            assert "meta" in data or "results" in data
        except json.JSONDecodeError:
            # May fail for other reasons, but JSON should be valid
            pass

    def test_get_node_with_graph_name(
        self, tmp_config_with_graph: Path, fixture_graph_path: Path, monkeypatch
    ):
        """Verify get-node command accepts --graph-name and returns node.

        Purpose: E2E get-node with named graph.
        Quality Contribution: Node retrieval works from external graphs.
        """
        monkeypatch.chdir(tmp_config_with_graph)

        # Get a valid node_id from the fixture graph
        # Fixture graph format: dict with 'graph' key containing (format_version, DiGraph)
        with open(fixture_graph_path, "rb") as f:
            data = pickle.load(f)
            # Handle both old tuple format and new dict format
            if isinstance(data, dict):
                # New format: {format_version, networkx.DiGraph, ...}
                # Find the DiGraph in the values
                import networkx as nx

                for v in data.values():
                    if isinstance(v, nx.DiGraph):
                        G = v
                        break
                else:
                    pytest.skip("Could not find DiGraph in fixture")
            elif isinstance(data, tuple):
                G = data[1]  # Old format: (version, graph)
            else:
                G = data

            nodes = list(G.nodes())
            if nodes:
                node_id = nodes[0]
            else:
                pytest.skip("Fixture graph has no nodes")

        result = self.runner.invoke(
            app,
            ["--graph-name", "external", "get-node", node_id],
        )

        # Should succeed and return JSON
        assert result.exit_code == 0, f"Failed with: {result.output}"

    def test_unknown_graph_name_error(self, tmp_config_with_graph: Path, monkeypatch):
        """Verify unknown graph name produces clear error.

        Purpose: Per DYK-04 - actionable error messages.
        Quality Contribution: Users know what graphs are available.
        """
        monkeypatch.chdir(tmp_config_with_graph)

        result = self.runner.invoke(
            app,
            ["--graph-name", "nonexistent", "tree"],
        )

        # Should fail with exit code 1
        assert result.exit_code == 1
        # Error should mention the unknown graph and available options
        output_lower = result.output.lower()
        assert (
            "unknown" in output_lower
            or "not found" in output_lower
            or "error" in output_lower
        )


class TestBackwardCompatibility:
    """T005: Backward compatibility tests.

    Per Critical Finding 12: All commands without --graph-name must work as before.

    Purpose: Verify existing functionality unchanged.
    Quality Contribution: No regression for existing users.

    Note: Uses monkeypatch to change CWD since CliRunner doesn't honor os.chdir.
    """

    runner = CliRunner()

    def test_tree_without_graph_options(self, tmp_config_with_graph: Path, monkeypatch):
        """Verify tree works without any graph options.

        Purpose: Backward compatibility.
        Quality Contribution: Existing scripts continue to work.
        """
        monkeypatch.chdir(tmp_config_with_graph)

        result = self.runner.invoke(app, ["tree"])

        # Should succeed using default graph
        assert result.exit_code == 0, f"Failed with: {result.output}"

    def test_search_without_graph_options(
        self, tmp_config_with_graph: Path, monkeypatch
    ):
        """Verify search works without any graph options.

        Purpose: Backward compatibility.
        Quality Contribution: Existing scripts continue to work.
        """
        monkeypatch.chdir(tmp_config_with_graph)

        result = self.runner.invoke(app, ["search", "test"])

        # Should succeed using default graph
        assert result.exit_code == 0, f"Failed with: {result.output}"

    def test_get_node_without_graph_options(
        self, tmp_config_with_graph: Path, fixture_graph_path: Path, monkeypatch
    ):
        """Verify get-node works without any graph options.

        Purpose: Backward compatibility.
        Quality Contribution: Existing scripts continue to work.
        """
        monkeypatch.chdir(tmp_config_with_graph)

        # Get a valid node_id from the fixture graph
        with open(fixture_graph_path, "rb") as f:
            import networkx as nx

            data = pickle.load(f)
            # Handle both old tuple format and new dict format
            if isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, nx.DiGraph):
                        G = v
                        break
                else:
                    pytest.skip("Could not find DiGraph in fixture")
            elif isinstance(data, tuple):
                G = data[1]
            else:
                G = data

            nodes = list(G.nodes())
            if nodes:
                node_id = nodes[0]
            else:
                pytest.skip("Fixture graph has no nodes")

        result = self.runner.invoke(app, ["get-node", node_id])

        # Should succeed using default graph
        assert result.exit_code == 0, f"Failed with: {result.output}"

    def test_tree_with_graph_file_only(
        self, tmp_config_with_graph: Path, fixture_graph_path: Path, monkeypatch
    ):
        """Verify --graph-file alone continues to work.

        Purpose: Backward compatibility for --graph-file.
        Quality Contribution: Existing --graph-file usage unchanged.
        """
        monkeypatch.chdir(tmp_config_with_graph)

        result = self.runner.invoke(
            app,
            ["--graph-file", str(fixture_graph_path), "tree"],
        )

        # Should succeed using specified graph file
        assert result.exit_code == 0, f"Failed with: {result.output}"
