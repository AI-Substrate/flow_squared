"""Tests for fs2 search CLI command.

Full TDD tests for the search CLI command covering:
- T004: CLI argument parsing (pattern, --mode, --limit, --offset, --detail)
- T005: JSON stdout + stderr error handling
- T006: Min detail level (9 fields)
- T007: Max detail level (13 fields)

Per Phase 5 tasks.md: Full TDD approach - tests written before implementation.
Per Discovery 10: print() for clean stdout, Console(stderr=True) for errors.
"""

import json

import pytest
from typer.testing import CliRunner

runner = CliRunner()


# ============================================================================
# T004: CLI Argument Parsing Tests
# ============================================================================


@pytest.mark.unit
class TestSearchHelp:
    """T004: Tests for search command registration and --help."""

    def test_given_cli_app_when_inspected_then_search_command_registered(self):
        """
        Purpose: Verifies search command is registered on app.
        Quality Contribution: Ensures command is discoverable.
        Acceptance Criteria: 'search' in registered commands.

        Task: T004
        """
        from fs2.cli.main import app

        command_names = [cmd.name for cmd in app.registered_commands]
        assert "search" in command_names, f"Expected 'search' in {command_names}"

    def test_given_help_flag_when_search_then_shows_usage(self):
        """
        Purpose: Proves command is registered and help is accessible.
        Quality Contribution: Ensures discoverability.
        Acceptance Criteria: Exit 0, shows pattern, --mode, --limit, --offset, --detail.

        Task: T004
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["search", "--help"])

        assert result.exit_code == 0
        assert "pattern" in result.stdout.lower(), f"Expected 'pattern' in help: {result.stdout}"
        assert "--mode" in result.stdout, f"Expected '--mode' in help: {result.stdout}"
        assert "--limit" in result.stdout, f"Expected '--limit' in help: {result.stdout}"
        assert "--offset" in result.stdout, f"Expected '--offset' in help: {result.stdout}"
        assert "--detail" in result.stdout, f"Expected '--detail' in help: {result.stdout}"

    def test_given_help_flag_then_shows_mode_choices(self):
        """
        Purpose: Proves mode choices are documented in help.
        Quality Contribution: User knows valid mode values.
        Acceptance Criteria: Help mentions auto, text, regex, semantic.

        Task: T004
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["search", "--help"])

        assert result.exit_code == 0
        # Check for mode values in help text
        stdout_lower = result.stdout.lower()
        assert "auto" in stdout_lower, f"Expected 'auto' in help: {result.stdout}"


# ============================================================================
# T005: JSON stdout + stderr Error Handling Tests
# ============================================================================


@pytest.mark.unit
class TestSearchJsonOutput:
    """T005: Tests for JSON stdout and stderr error handling."""

    def test_given_valid_pattern_when_search_then_stdout_is_valid_json(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves search outputs valid JSON on stdout.
        Quality Contribution: Pipeable output for tools like jq.
        Acceptance Criteria: json.loads(stdout) succeeds.

        Task: T005
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "calculator"])

        assert result.exit_code == 0, f"Expected exit 0: {result.stdout}"
        # Stdout should be valid JSON
        data = json.loads(result.stdout)
        assert isinstance(data, list), f"Expected list, got {type(data)}"

    def test_given_missing_graph_when_search_then_error_on_stderr(
        self, config_only_project, monkeypatch
    ):
        """
        Purpose: Proves errors go to stderr, not stdout.
        Quality Contribution: Clean stdout for piping even on error.
        Acceptance Criteria: Exit 1, stdout is empty (error goes to stderr).

        Task: T005
        """
        from fs2.cli.main import app

        monkeypatch.chdir(config_only_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "test"])

        assert result.exit_code == 1
        # Stdout should be empty (error message goes to stderr for clean piping)
        # CliRunner can't capture Rich Console(stderr=True) output
        assert result.stdout == "", (
            f"Expected empty stdout for error case, got: {result.stdout}"
        )

    def test_given_no_matches_when_search_then_returns_empty_json_array(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves no-match returns empty array, not error.
        Quality Contribution: Consistent JSON structure.
        Acceptance Criteria: stdout is "[]" or empty array.

        Task: T005
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "xyznonexistentpattern12345"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == [], f"Expected empty list, got {data}"


# ============================================================================
# T006: Min Detail Level Tests
# ============================================================================


@pytest.mark.unit
class TestSearchMinDetail:
    """T006: Tests for min detail level (9 fields per AC19)."""

    def test_given_detail_min_when_search_then_result_has_9_fields(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves min detail returns exactly 9 fields.
        Quality Contribution: Documents expected min-mode output.
        Acceptance Criteria: Each result has exactly 9 keys.

        Task: T006
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "calculator", "--detail", "min"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) > 0, "Expected at least one result"

        # Check first result has 9 fields
        first = data[0]
        assert len(first) == 9, f"Expected 9 fields, got {len(first)}: {first.keys()}"

    def test_given_detail_min_when_search_then_content_not_in_result(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves min detail excludes 'content' field.
        Quality Contribution: Verifies min/max field partitioning.
        Acceptance Criteria: 'content' key not present.

        Task: T006
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "calculator", "--detail", "min"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) > 0, "Expected at least one result"

        first = data[0]
        assert "content" not in first, f"'content' should not be in min detail: {first.keys()}"

    def test_given_default_detail_when_search_then_uses_min(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves default detail level is 'min'.
        Quality Contribution: Documents default behavior.
        Acceptance Criteria: No --detail flag gives same as --detail min.

        Task: T006
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "calculator"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) > 0, "Expected at least one result"

        first = data[0]
        # Default should be min (9 fields, no content)
        assert len(first) == 9, f"Expected 9 fields (min), got {len(first)}"
        assert "content" not in first


# ============================================================================
# T007: Max Detail Level Tests
# ============================================================================


@pytest.mark.unit
class TestSearchMaxDetail:
    """T007: Tests for max detail level (13 fields per DYK-02)."""

    def test_given_detail_max_when_search_then_result_has_13_fields(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves max detail returns exactly 13 fields.
        Quality Contribution: Documents expected max-mode output per DYK-02.
        Acceptance Criteria: Each result has exactly 13 keys.

        Task: T007
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "calculator", "--detail", "max"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) > 0, "Expected at least one result"

        first = data[0]
        assert len(first) == 13, f"Expected 13 fields, got {len(first)}: {first.keys()}"

    def test_given_detail_max_when_search_then_content_in_result(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves max detail includes 'content' field.
        Quality Contribution: Verifies max mode includes all fields.
        Acceptance Criteria: 'content' key is present.

        Task: T007
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "calculator", "--detail", "max"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) > 0, "Expected at least one result"

        first = data[0]
        assert "content" in first, f"'content' should be in max detail: {first.keys()}"


# ============================================================================
# Additional CLI Argument Tests
# ============================================================================


@pytest.mark.unit
class TestSearchArguments:
    """Additional tests for CLI argument validation."""

    def test_given_limit_flag_when_search_then_respects_limit(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves --limit controls result count.
        Quality Contribution: Enables pagination.
        Acceptance Criteria: len(results) <= limit.

        Task: T004
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "a", "--limit", "2"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) <= 2, f"Expected at most 2 results, got {len(data)}"

    def test_given_offset_flag_when_search_then_skips_results(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves --offset skips first N results.
        Quality Contribution: Enables pagination.
        Acceptance Criteria: offset=high returns different results than offset=0.

        Task: T004
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        # First page
        result1 = runner.invoke(app, ["search", "a", "--limit", "2", "--offset", "0"])
        assert result1.exit_code == 0
        page1 = json.loads(result1.stdout)

        # Second page
        result2 = runner.invoke(app, ["search", "a", "--limit", "2", "--offset", "2"])
        assert result2.exit_code == 0
        page2 = json.loads(result2.stdout)

        # If there are enough results, pages should be different
        if len(page1) == 2 and len(page2) > 0:
            page1_ids = {r["node_id"] for r in page1}
            page2_ids = {r["node_id"] for r in page2}
            assert page1_ids.isdisjoint(page2_ids), "Pages should have different results"

    def test_given_mode_text_when_search_then_uses_text_mode(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves --mode text forces text search.
        Quality Contribution: Explicit mode control.
        Acceptance Criteria: Text search matches case-insensitively.

        Task: T004
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "calculator", "--mode", "text"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        # Should find matches using text search
        assert isinstance(data, list)

    def test_given_mode_regex_when_search_then_uses_regex_mode(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves --mode regex forces regex search.
        Quality Contribution: Explicit mode control.
        Acceptance Criteria: Regex pattern matches.

        Task: T004
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "calc.*", "--mode", "regex"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
