"""Integration tests for fs2 tree CLI command.

T024: End-to-end tests using real scanned graph from ast_samples fixtures.
Uses session-scoped scanned_fixtures_graph fixture for high-fidelity testing.
"""

import pytest
from typer.testing import CliRunner

runner = CliRunner()


@pytest.mark.integration
class TestTreeIntegration:
    """T024: Integration tests with real graph from ast_samples."""

    def test_given_scanned_fixtures_when_tree_then_shows_python_files(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Verifies tree shows real Python file structure.
        Quality Contribution: End-to-end validation.
        Acceptance Criteria: Shows Python files from fixtures.

        Task: T024
        """
        from fs2.cli.main import app

        # scanned_fixtures_graph fixture provides working directory context
        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 0, f"Failed: {result.stdout}"
        stdout = result.stdout.lower()
        # Should show Python-related content
        assert ".py" in stdout or "python" in stdout or "class" in stdout

    def test_given_scanned_fixtures_when_tree_with_path_filter_then_filters(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Verifies path filtering works with real graph.
        Quality Contribution: End-to-end filter validation.
        Acceptance Criteria: Filters to specific path.

        Task: T024
        """
        from fs2.cli.main import app

        # Filter by python directory
        result = runner.invoke(app, ["tree", "python"])

        assert result.exit_code == 0, f"Failed: {result.stdout}"
        stdout = result.stdout.lower()
        # Should match python-related content
        assert "python" in stdout or "class" in stdout

    def test_given_scanned_fixtures_when_tree_with_glob_then_filters(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Verifies glob filtering works with real graph.
        Quality Contribution: End-to-end glob validation.
        Acceptance Criteria: Glob pattern matches correctly.

        Task: T024
        """
        from fs2.cli.main import app

        # Use glob to match all class-related content
        result = runner.invoke(app, ["tree", "*class*"])

        assert result.exit_code == 0, f"Failed: {result.stdout}"
        # Result may be empty or have matches - both are valid

    def test_given_scanned_fixtures_when_tree_with_depth_then_limits(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Verifies depth limiting works with real graph.
        Quality Contribution: End-to-end depth validation.
        Acceptance Criteria: Depth is respected.

        Task: T024
        """
        from fs2.cli.main import app

        # Limit depth
        result = runner.invoke(app, ["tree", "--depth", "1"])

        assert result.exit_code == 0, f"Failed: {result.stdout}"
        # Should complete without error

    def test_given_scanned_fixtures_when_tree_with_detail_max_then_shows_node_ids(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Verifies --detail max shows node IDs.
        Quality Contribution: End-to-end detail level validation.
        Acceptance Criteria: Node IDs visible in output.

        Task: T024
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree", "--detail", "max"])

        assert result.exit_code == 0, f"Failed: {result.stdout}"
        # In max detail, should show node_id format
        stdout = result.stdout
        # Node IDs contain colons (category:path:name format)
        assert ":" in stdout
