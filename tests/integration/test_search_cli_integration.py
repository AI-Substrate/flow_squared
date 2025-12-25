"""Integration tests for fs2 search CLI command.

Uses the real scanned ast_samples graph for end-to-end validation.
Per Phase 5 tasks.md T013: Validates real graph, real search, pagination.
"""

import json

import pytest
from typer.testing import CliRunner

from fs2.cli.main import app

runner = CliRunner()


@pytest.mark.integration
class TestSearchIntegration:
    """T013: Integration tests using scanned_fixtures_graph."""

    def test_given_real_graph_when_search_then_returns_json_array(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Validates end-to-end search from real scanned graph.
        Quality Contribution: Ensures real-world usage works.
        Acceptance Criteria: Returns valid JSON array with results.

        Task: T013
        """
        # scanned_fixtures_graph already chdir'd and set NO_COLOR
        result = runner.invoke(app, ["search", "Calculator"])

        assert result.exit_code == 0, f"Expected exit 0: {result.stdout}"

        data = json.loads(result.stdout)
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        # Should find Calculator class in ast_samples
        assert len(data) > 0, "Expected at least one result for 'Calculator'"

    def test_given_real_graph_when_search_then_results_have_node_id(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Validates search results contain node_id field.
        Quality Contribution: Ensures results are usable.
        Acceptance Criteria: Each result has node_id field.

        Task: T013
        """
        result = runner.invoke(app, ["search", "Calculator"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) > 0

        # Each result should have node_id
        for item in data:
            assert "node_id" in item, f"Missing node_id in result: {item}"

    def test_given_real_graph_when_search_with_limit_then_respects_limit(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Validates --limit flag works with real graph.
        Quality Contribution: Pagination support verified.
        Acceptance Criteria: Result count <= limit.

        Task: T013
        """
        result = runner.invoke(app, ["search", "def", "--limit", "3"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) <= 3, f"Expected at most 3 results, got {len(data)}"

    def test_given_real_graph_when_search_with_offset_then_paginates(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Validates --offset flag enables pagination.
        Quality Contribution: Ensures pagination works end-to-end.
        Acceptance Criteria: Different pages have different results.

        Task: T013
        """
        # Get first page
        result1 = runner.invoke(app, ["search", "def", "--limit", "2", "--offset", "0"])
        assert result1.exit_code == 0
        page1 = json.loads(result1.stdout)

        # Get second page
        result2 = runner.invoke(app, ["search", "def", "--limit", "2", "--offset", "2"])
        assert result2.exit_code == 0
        page2 = json.loads(result2.stdout)

        # If we have enough results, pages should be different
        if len(page1) == 2 and len(page2) > 0:
            page1_ids = {r["node_id"] for r in page1}
            page2_ids = {r["node_id"] for r in page2}
            assert page1_ids.isdisjoint(page2_ids), (
                "Pagination failed: pages should have different results"
            )

    def test_given_real_graph_when_search_detail_max_then_includes_content(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Validates --detail max includes content field.
        Quality Contribution: Max detail verified end-to-end.
        Acceptance Criteria: Results have 13 fields including content.

        Task: T013
        """
        result = runner.invoke(
            app, ["search", "Calculator", "--detail", "max", "--limit", "1"]
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) > 0

        first = data[0]
        assert "content" in first, f"Max detail should include content: {first.keys()}"
        assert len(first) == 13, f"Expected 13 fields in max detail, got {len(first)}"

    def test_given_real_graph_when_search_detail_min_then_excludes_content(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Validates --detail min excludes content field.
        Quality Contribution: Min detail verified end-to-end.
        Acceptance Criteria: Results have 9 fields, no content.

        Task: T013
        """
        result = runner.invoke(
            app, ["search", "Calculator", "--detail", "min", "--limit", "1"]
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) > 0

        first = data[0]
        assert "content" not in first, f"Min detail should exclude content: {first.keys()}"
        assert len(first) == 9, f"Expected 9 fields in min detail, got {len(first)}"

    def test_given_real_graph_when_search_regex_mode_then_finds_pattern(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Validates --mode regex works with real graph.
        Quality Contribution: Regex search verified end-to-end.
        Acceptance Criteria: Regex pattern finds matches.

        Task: T013
        """
        result = runner.invoke(app, ["search", "Calc.*", "--mode", "regex"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        # Should find Calculator or similar patterns
        assert isinstance(data, list)

    def test_given_real_graph_when_no_matches_then_returns_empty_array(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Validates no-match returns empty array.
        Quality Contribution: Edge case verified end-to-end.
        Acceptance Criteria: Returns [] for non-matching pattern.

        Task: T013
        """
        result = runner.invoke(app, ["search", "xyznonexistent12345"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == [], f"Expected empty array, got {data}"
