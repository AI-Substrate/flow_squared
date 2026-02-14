"""Integration tests for fs2 get-node CLI command.

Uses the real scanned ast_samples graph for end-to-end validation.
Per plan-005 T016: Validates real graph, real node lookup.
"""

import json

import pytest
from typer.testing import CliRunner

from fs2.cli.main import app

pytestmark = pytest.mark.slow  # Real CLI invocations with scanned graph

runner = CliRunner()


@pytest.mark.integration
class TestGetNodeIntegration:
    """T016: Integration tests using scanned_fixtures_graph."""

    def test_given_real_graph_when_get_node_then_returns_file_node(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Validates end-to-end retrieval from real scanned graph.
        Quality Contribution: Ensures real-world usage works.
        Acceptance Criteria: Retrieves a real file node with all fields.

        Task: T016
        """
        # scanned_fixtures_graph already chdir'd and set NO_COLOR
        # Get a known node from the fixtures (Python file)
        # Node ID includes full relative path from scan root
        result = runner.invoke(
            app, ["get-node", "file:tests/fixtures/ast_samples/python/simple_class.py"]
        )

        assert result.exit_code == 0, f"Expected exit 0: {result.stdout}"

        data = json.loads(result.stdout)
        assert "simple_class.py" in data["node_id"]
        assert data["category"] == "file"
        assert data["language"] == "python"

    def test_given_real_graph_when_get_node_then_returns_class_node(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Validates retrieval of class-level node.
        Quality Contribution: Ensures non-file nodes work.
        Acceptance Criteria: Retrieves class node with signature.

        Task: T016
        """
        # Get a known class from the fixtures (Calculator in simple_class.py)
        result = runner.invoke(
            app,
            [
                "get-node",
                "type:tests/fixtures/ast_samples/python/simple_class.py:Calculator",
            ],
        )

        assert result.exit_code == 0, f"Expected exit 0: {result.stdout}"

        data = json.loads(result.stdout)
        assert data["category"] == "type"
        assert "Calculator" in data["node_id"]

    def test_given_real_graph_when_get_node_then_returns_callable_node(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Validates retrieval of callable node.
        Quality Contribution: Ensures method-level nodes work.
        Acceptance Criteria: Retrieves callable node with signature.

        Task: T016
        """
        # Get a known callable from the fixtures (Calculator.add method)
        result = runner.invoke(
            app,
            [
                "get-node",
                "callable:tests/fixtures/ast_samples/python/simple_class.py:Calculator.add",
            ],
        )

        assert result.exit_code == 0, f"Expected exit 0: {result.stdout}"

        data = json.loads(result.stdout)
        assert data["category"] == "callable"

    def test_given_real_graph_when_file_output_then_writes_json(
        self, scanned_fixtures_graph, tmp_path
    ):
        """
        Purpose: Validates --file flag with real graph.
        Quality Contribution: Ensures file output works end-to-end.
        Acceptance Criteria: File contains valid JSON from real node.

        Task: T016
        """
        output_file = tmp_path / "node.json"

        result = runner.invoke(
            app,
            [
                "get-node",
                "file:tests/fixtures/ast_samples/python/simple_class.py",
                "--file",
                str(output_file),
            ],
        )

        assert result.exit_code == 0, f"Expected exit 0: {result.stdout}"
        assert output_file.exists()

        data = json.loads(output_file.read_text())
        assert "simple_class.py" in data["node_id"]
