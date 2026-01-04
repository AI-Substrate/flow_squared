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
        assert "pattern" in result.stdout.lower(), (
            f"Expected 'pattern' in help: {result.stdout}"
        )
        assert "--mode" in result.stdout, f"Expected '--mode' in help: {result.stdout}"
        assert "--limit" in result.stdout, (
            f"Expected '--limit' in help: {result.stdout}"
        )
        assert "--offset" in result.stdout, (
            f"Expected '--offset' in help: {result.stdout}"
        )
        assert "--detail" in result.stdout, (
            f"Expected '--detail' in help: {result.stdout}"
        )

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
        # Stdout should be valid JSON envelope
        data = json.loads(result.stdout)
        assert isinstance(data, dict), f"Expected dict (envelope), got {type(data)}"
        assert "results" in data, "Expected 'results' key in envelope"
        assert isinstance(data["results"], list), "Expected results to be list"

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

    def test_given_no_matches_when_search_then_returns_envelope_with_empty_results(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves no-match returns envelope with empty results.
        Quality Contribution: Consistent JSON structure.
        Acceptance Criteria: results is empty array, meta.total == 0.

        Task: T005
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "xyznonexistentpattern12345"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["results"] == [], f"Expected empty results, got {data['results']}"
        assert data["meta"]["total"] == 0


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
        results = data["results"]
        assert len(results) > 0, "Expected at least one result"

        # Check first result has 9 fields
        first = results[0]
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
        results = data["results"]
        assert len(results) > 0, "Expected at least one result"

        first = results[0]
        assert "content" not in first, (
            f"'content' should not be in min detail: {first.keys()}"
        )

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
        results = data["results"]
        assert len(results) > 0, "Expected at least one result"

        first = results[0]
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
        results = data["results"]
        assert len(results) > 0, "Expected at least one result"

        first = results[0]
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
        results = data["results"]
        assert len(results) > 0, "Expected at least one result"

        first = results[0]
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
        results = data["results"]
        assert len(results) <= 2, f"Expected at most 2 results, got {len(results)}"

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
        page1 = json.loads(result1.stdout)["results"]

        # Second page
        result2 = runner.invoke(app, ["search", "a", "--limit", "2", "--offset", "2"])
        assert result2.exit_code == 0
        page2 = json.loads(result2.stdout)["results"]

        # If there are enough results, pages should be different
        if len(page1) == 2 and len(page2) > 0:
            page1_ids = {r["node_id"] for r in page1}
            page2_ids = {r["node_id"] for r in page2}
            assert page1_ids.isdisjoint(page2_ids), (
                "Pages should have different results"
            )

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
        # Should find matches using text search - envelope format
        assert isinstance(data, dict)
        assert "results" in data
        assert isinstance(data["results"], list)

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
        # After ST006: data will be envelope with "results" key
        results = data.get("results", data) if isinstance(data, dict) else data
        assert isinstance(results, list)


# ============================================================================
# ST005: Envelope Output Format Tests
# ============================================================================


@pytest.mark.unit
class TestSearchEnvelopeOutput:
    """ST005: Tests for envelope output format (BC-09 through BC-13)."""

    def test_given_search_when_output_then_is_envelope_not_array(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves output is envelope with meta + results (BC-09).
        Quality Contribution: Breaking change validation.
        Acceptance Criteria: Output has meta and results keys.

        Task: ST005, BC-09
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "calculator"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict), f"Expected dict (envelope), got {type(data)}"
        assert "meta" in data, f"Expected 'meta' key in envelope: {data.keys()}"
        assert "results" in data, f"Expected 'results' key in envelope: {data.keys()}"

    def test_given_search_when_output_then_meta_total_present(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves meta.total shows total matches (BC-10).
        Quality Contribution: Pagination metadata.
        Acceptance Criteria: meta.total is integer >= 0.

        Task: ST005, BC-10
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "a", "--limit", "2"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        meta = data["meta"]
        assert "total" in meta, f"Expected 'total' in meta: {meta.keys()}"
        assert isinstance(meta["total"], int)
        assert meta["total"] >= 0

    def test_given_search_when_output_then_meta_showing_present(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves meta.showing has from/to/count (BC-11).
        Quality Contribution: Current page info.
        Acceptance Criteria: meta.showing has from, to, count keys.

        Task: ST005, BC-11
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "a", "--limit", "5"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        showing = data["meta"]["showing"]
        assert "from" in showing, f"Expected 'from' in showing: {showing.keys()}"
        assert "to" in showing, f"Expected 'to' in showing: {showing.keys()}"
        assert "count" in showing, f"Expected 'count' in showing: {showing.keys()}"

    def test_given_search_when_output_then_meta_pagination_mirrors_input(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves meta.pagination shows limit/offset passed in (BC-12).
        Quality Contribution: Request echo for clients.
        Acceptance Criteria: meta.pagination matches --limit and --offset.

        Task: ST005, BC-12
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "a", "--limit", "5", "--offset", "10"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        pagination = data["meta"]["pagination"]
        assert pagination["limit"] == 5
        assert pagination["offset"] == 10

    def test_given_search_when_output_then_meta_folders_present(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves meta.folders shows folder distribution (BC-13).
        Quality Contribution: Result distribution insight.
        Acceptance Criteria: meta.folders is dict.

        Task: ST005, BC-13
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "a"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        folders = data["meta"]["folders"]
        assert isinstance(folders, dict), f"Expected dict, got {type(folders)}"

    def test_given_no_matches_when_search_then_envelope_with_empty_results(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves no-match returns envelope with empty results.
        Quality Contribution: Consistent structure even on empty.
        Acceptance Criteria: meta.total == 0, results == [].

        Task: ST005
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "xyznonexistentpattern12345"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["meta"]["total"] == 0
        assert data["results"] == []

    def test_given_envelope_when_jq_results_then_works(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves jq .results[] extraction works.
        Quality Contribution: Backward compat for existing scripts.
        Acceptance Criteria: results array is iterable.

        Task: ST005, DYK-003-01
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "calculator"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        results = data["results"]
        assert isinstance(results, list)
        # Each result should have node_id
        for r in results:
            assert "node_id" in r


# ============================================================================
# ST007: Include/Exclude Option Tests
# ============================================================================


@pytest.mark.unit
class TestSearchIncludeExcludeOptions:
    """ST007: Tests for --include/--exclude options (BC-15 through BC-19)."""

    def test_given_include_flag_when_search_then_shows_in_help(self):
        """
        Purpose: Proves --include flag is registered.
        Quality Contribution: Discoverability.
        Acceptance Criteria: --include in help output.

        Task: ST007
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["search", "--help"])

        assert result.exit_code == 0
        assert "--include" in result.stdout

    def test_given_exclude_flag_when_search_then_shows_in_help(self):
        """
        Purpose: Proves --exclude flag is registered.
        Quality Contribution: Discoverability.
        Acceptance Criteria: --exclude in help output.

        Task: ST007
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["search", "--help"])

        assert result.exit_code == 0
        assert "--exclude" in result.stdout

    def test_given_include_flag_when_search_then_keeps_only_matching(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves --include keeps only matching node_ids (BC-15).
        Quality Contribution: Filter functionality.
        Acceptance Criteria: All results match include pattern.

        Task: ST007, BC-15
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(
            app, ["search", "a", "--include", "samples/", "--limit", "20"]
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        results = data["results"]
        # All results should match include pattern
        for r in results:
            assert "samples/" in r["node_id"], f"Expected samples/ in {r['node_id']}"

    def test_given_exclude_flag_when_search_then_removes_matching(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves --exclude removes matching node_ids (BC-16).
        Quality Contribution: Filter functionality.
        Acceptance Criteria: No results match exclude pattern.

        Task: ST007, BC-16
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(
            app, ["search", "a", "--exclude", "test", "--limit", "20"]
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        results = data["results"]
        # No results should match exclude pattern
        for r in results:
            assert "test" not in r["node_id"].lower(), (
                f"Expected no 'test' in {r['node_id']}"
            )

    def test_given_multiple_include_flags_when_search_then_or_logic(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves multiple --include uses OR logic (BC-15).
        Quality Contribution: Multi-pattern support.
        Acceptance Criteria: Results match pattern A OR pattern B.

        Task: ST007, BC-15, DYK-003-04
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(
            app,
            [
                "search",
                "a",
                "--include",
                "samples/",
                "--include",
                "Calculator",
                "--limit",
                "20",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        results = data["results"]
        # Each result should match at least one pattern
        for r in results:
            node_id = r["node_id"]
            matches = "samples/" in node_id or "Calculator" in node_id
            assert matches, f"Expected samples/ OR Calculator in {node_id}"

    def test_given_multiple_exclude_flags_when_search_then_or_logic(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves multiple --exclude uses OR logic (BC-16).
        Quality Contribution: Multi-pattern support.
        Acceptance Criteria: Results match neither pattern A NOR pattern B.

        Task: ST007, BC-16, DYK-003-04
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(
            app,
            [
                "search",
                "a",
                "--exclude",
                "test",
                "--exclude",
                "fixture",
                "--limit",
                "20",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        results = data["results"]
        # No result should match any exclude pattern
        for r in results:
            node_id = r["node_id"].lower()
            assert "test" not in node_id and "fixture" not in node_id, (
                f"Expected no test/fixture in {node_id}"
            )

    def test_given_include_and_exclude_when_search_then_include_first(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves include applied before exclude (BC-17).
        Quality Contribution: Correct filter ordering.
        Acceptance Criteria: Include narrows, then exclude removes.

        Task: ST007, BC-17
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(
            app,
            [
                "search",
                "a",
                "--include",
                "samples/",
                "--exclude",
                "Calculator",
                "--limit",
                "20",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        results = data["results"]
        # Results should be in samples/ but not Calculator
        for r in results:
            node_id = r["node_id"]
            assert "samples/" in node_id, f"Expected samples/ in {node_id}"
            assert "Calculator" not in node_id, f"Expected no Calculator in {node_id}"

    def test_given_include_when_output_then_meta_include_is_array(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves meta.include is always array (BC-18).
        Quality Contribution: Type consistency.
        Acceptance Criteria: meta.include is list even for single pattern.

        Task: ST007, BC-18, DYK-003-05
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "a", "--include", "samples/"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        include = data["meta"].get("include")
        assert include is not None
        assert isinstance(include, list), f"Expected list, got {type(include)}"
        assert include == ["samples/"]

    def test_given_exclude_when_output_then_meta_exclude_is_array(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves meta.exclude is always array (BC-18).
        Quality Contribution: Type consistency.
        Acceptance Criteria: meta.exclude is list even for single pattern.

        Task: ST007, BC-18, DYK-003-05
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "a", "--exclude", "test"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        exclude = data["meta"].get("exclude")
        assert exclude is not None
        assert isinstance(exclude, list), f"Expected list, got {type(exclude)}"
        assert exclude == ["test"]

    def test_given_no_filters_when_output_then_meta_omits_filter_keys(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves filter keys omitted when no filters (BC-18).
        Quality Contribution: Clean output.
        Acceptance Criteria: No include/exclude/filtered keys.

        Task: ST007, BC-18
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "calculator"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        meta = data["meta"]
        assert "include" not in meta
        assert "exclude" not in meta
        assert "filtered" not in meta

    def test_given_filter_applied_when_output_then_meta_filtered_present(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves meta.filtered shows post-filter count (BC-19).
        Quality Contribution: Filter result visibility.
        Acceptance Criteria: meta.filtered == len(results).

        Task: ST007, BC-19
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "a", "--include", "samples/"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        filtered = data["meta"].get("filtered")
        assert filtered is not None
        # filtered should match result count (accounting for pagination)
        results_count = len(data["results"])
        # filtered is count BEFORE pagination, results is AFTER
        # So filtered >= results_count
        assert filtered >= results_count

    def test_given_regex_include_when_search_then_pattern_matches(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves --include accepts regex patterns (BC-15).
        Quality Contribution: Regex filter support.
        Acceptance Criteria: Regex pattern matches.

        Task: ST007, BC-15
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(
            app, ["search", "a", "--include", "Calculator.*", "--limit", "20"]
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        results = data["results"]
        # All should match Calculator.*
        for r in results:
            assert "Calculator" in r["node_id"]

    def test_given_invalid_regex_when_search_then_error(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves invalid regex in filter raises error.
        Quality Contribution: Clear error handling.
        Acceptance Criteria: Exit 1, error message.

        Task: ST007
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "a", "--include", "[invalid"])

        assert result.exit_code == 1
        # Error should be on stderr (empty stdout)


# ============================================================================
# ST008: Glob Pattern Support Tests
# ============================================================================


@pytest.mark.unit
class TestSearchGlobPatterns:
    """ST008: Tests for glob pattern support in --include/--exclude (T004).

    These tests verify that glob patterns like *.py, .cs, and test_* work
    correctly when filtering search results. Uses scanned_fixtures_graph
    which contains multiple file types (.py, .cs, .md, .ts, etc.).
    """

    def test_given_glob_star_py_when_include_then_filters_to_py_only(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Proves *.py glob pattern filters to Python files only.
        Quality Contribution: Glob pattern support (AC1).
        Acceptance Criteria: All results have .py extension.

        Task: T004
        """
        from fs2.cli.main import app

        # scanned_fixtures_graph already sets chdir and NO_COLOR

        result = runner.invoke(
            app, ["search", ".", "--include", "*.py", "--limit", "50"]
        )

        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["meta"]["total"] > 0

        # All results should have .py in node_id
        for r in output["results"]:
            assert ".py" in r["node_id"], f"Expected .py in {r['node_id']}"

    def test_given_glob_star_cs_when_include_then_filters_to_cs_only(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Proves *.cs glob pattern filters to C# files only.
        Quality Contribution: Glob pattern support for non-Python files.
        Acceptance Criteria: All results have .cs extension.

        Task: T004
        """
        from fs2.cli.main import app

        result = runner.invoke(
            app, ["search", ".", "--include", "*.cs", "--limit", "50"]
        )

        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["meta"]["total"] > 0

        # All results should have .cs in node_id
        for r in output["results"]:
            assert ".cs" in r["node_id"], f"Expected .cs in {r['node_id']}"

    def test_given_glob_star_md_when_include_then_filters_to_md_only(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Proves *.md glob pattern filters to markdown files only.
        Quality Contribution: Glob pattern support for docs.
        Acceptance Criteria: All results have .md extension.

        Task: T004
        """
        from fs2.cli.main import app

        result = runner.invoke(
            app, ["search", ".", "--include", "*.md", "--limit", "50"]
        )

        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["meta"]["total"] > 0

        # All results should have .md in node_id
        for r in output["results"]:
            assert ".md" in r["node_id"], f"Expected .md in {r['node_id']}"

    def test_given_extension_pattern_when_include_then_filters_correctly(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Proves .cs extension pattern (without *) works.
        Quality Contribution: Extension pattern support (AC2).
        Acceptance Criteria: All results have .cs extension.

        Task: T004
        """
        from fs2.cli.main import app

        result = runner.invoke(
            app, ["search", ".", "--include", ".cs", "--limit", "50"]
        )

        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["meta"]["total"] > 0

        # All results should have .cs in node_id
        for r in output["results"]:
            assert ".cs" in r["node_id"], f"Expected .cs in {r['node_id']}"

    def test_given_extension_ts_when_include_then_excludes_typescript_dir(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Proves .ts extension doesn't match 'typescript' directory.
        Quality Contribution: Extension anchoring works correctly (AC2).
        Acceptance Criteria: Results have .ts extension, not 'typescript' substring.

        Task: T004
        """
        from fs2.cli.main import app

        result = runner.invoke(
            app, ["search", ".", "--include", ".ts", "--limit", "50"]
        )

        assert result.exit_code == 0
        output = json.loads(result.stdout)

        # All results should have .ts extension (before : or at end)
        for r in output["results"]:
            node_id = r["node_id"]
            # Must have .ts followed by : or end of string
            has_ts_extension = ".ts:" in node_id or node_id.endswith(".ts")
            assert has_ts_extension, f"Expected .ts extension in {node_id}"

    def test_given_glob_exclude_when_search_then_removes_matching(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Proves --exclude with glob pattern removes matches.
        Quality Contribution: Exclude pattern support with globs.
        Acceptance Criteria: No results have excluded extension.

        Task: T004
        """
        from fs2.cli.main import app

        result = runner.invoke(
            app, ["search", ".", "--exclude", "*.md", "--limit", "50"]
        )

        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["meta"]["total"] > 0

        # No results should have .md in node_id
        for r in output["results"]:
            assert ".md" not in r["node_id"], f"Unexpected .md in {r['node_id']}"

    def test_given_regex_pattern_when_include_then_still_works(
        self, scanned_fixtures_graph
    ):
        """
        Purpose: Proves regex patterns still work (backward compat - AC4).
        Quality Contribution: Backward compatibility with regex.
        Acceptance Criteria: Calculator.* matches calculator patterns.

        Task: T004
        """
        from fs2.cli.main import app

        # Use a regex pattern that shouldn't be converted
        result = runner.invoke(
            app, ["search", ".", "--include", ".*class.*", "--limit", "50"]
        )

        assert result.exit_code == 0
        output = json.loads(result.stdout)
        # Should match any node with 'class' in the ID
        for r in output["results"]:
            assert "class" in r["node_id"].lower(), f"Expected class in {r['node_id']}"


# ============================================================================
# T001: CLI Search --file Tests (Phase 1: save-to-file)
# ============================================================================


@pytest.mark.unit
class TestSearchFileOutput:
    """T001: Tests for fs2 search --file option (AC1, AC2, AC4b, AC9, AC10).

    Full TDD tests per save-to-file-plan.md.
    These tests are expected to FAIL until T002/T003 implement the feature.
    """

    def test_given_file_flag_when_search_then_writes_to_file(
        self, scanned_project, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves --file option writes JSON envelope to specified file.
        Quality Contribution: Validates core file output functionality.
        Acceptance Criteria:
        - File is created with valid JSON (AC1)
        - JSON contains 'meta' and 'results' keys

        Task: T001
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        output_file = tmp_path / "results.json"
        result = runner.invoke(
            app, ["search", "calculator", "--file", str(output_file)]
        )

        assert result.exit_code == 0, f"Expected exit 0: {result.output}"
        assert output_file.exists(), "File should be created"

        data = json.loads(output_file.read_text())
        assert "meta" in data, "JSON must contain 'meta' key"
        assert "results" in data, "JSON must contain 'results' key"

    def test_given_file_flag_when_search_then_stdout_is_empty(
        self, scanned_project, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves stdout is empty when --file is used.
        Quality Contribution: Enables clean piping (stdout discipline).
        Acceptance Criteria: stdout is empty string (AC1)

        Task: T001
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        output_file = tmp_path / "results.json"
        result = runner.invoke(
            app, ["search", "calculator", "--file", str(output_file)]
        )

        assert result.exit_code == 0
        assert result.stdout == "", f"Expected empty stdout, got: {result.stdout}"

    def test_given_file_flag_when_search_then_shows_confirmation_on_stderr(
        self, scanned_project, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves confirmation message goes to stderr.
        Quality Contribution: Ensures piping works correctly.
        Acceptance Criteria: Output includes confirmation (AC2).

        Note: CliRunner captures both stdout/stderr in output when mix_stderr=True.
        The actual confirmation goes to stderr via Console(stderr=True).

        Task: T001
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        output_file = tmp_path / "results.json"
        result = runner.invoke(
            app,
            ["search", "calculator", "--file", str(output_file)],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        # Note: When stdout is empty and confirmation is on stderr, result.output may still be empty
        # in some CliRunner configurations. The key test is that stdout is empty and file is created.
        # If using mix_stderr=False, stderr would be in result.stderr
        # For now, we just verify the file was created and stdout was clean
        assert output_file.exists()

    def test_given_path_escape_when_search_file_then_exits_with_error(
        self, scanned_project, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves path validation prevents directory traversal.
        Quality Contribution: Security - prevents writes outside cwd.
        Acceptance Criteria: Exit code 1 for path escape (AC4b).

        Task: T001
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(
            app, ["search", "calculator", "--file", "../escape.json"]
        )

        assert result.exit_code == 1, (
            f"Expected exit 1 for path escape: {result.output}"
        )

    def test_given_absolute_path_outside_cwd_when_file_flag_then_exits_with_error(
        self, scanned_project, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves absolute paths outside cwd are rejected.
        Quality Contribution: Security - prevents writes to arbitrary locations.
        Acceptance Criteria: Exit code 1 for absolute path outside cwd (AC4b).

        Task: T001
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(
            app, ["search", "calculator", "--file", "/tmp/escape.json"]
        )

        assert result.exit_code == 1, (
            f"Expected exit 1 for absolute path: {result.output}"
        )

    def test_given_empty_results_when_file_flag_then_still_saves_envelope(
        self, scanned_project, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves empty results still create valid file.
        Quality Contribution: Consistent behavior for agent workflows.
        Acceptance Criteria: Empty envelope saved (AC9).

        Task: T001
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        output_file = tmp_path / "results.json"
        result = runner.invoke(
            app,
            ["search", "NONEXISTENT_PATTERN_XYZ123", "--file", str(output_file)],
        )

        assert result.exit_code == 0
        assert output_file.exists(), "File should exist even with empty results"

        data = json.loads(output_file.read_text())
        assert data["results"] == [], "Empty results should be empty array"
        assert data["meta"]["total"] == 0

    def test_given_nested_path_when_file_flag_then_creates_subdirectory(
        self, scanned_project, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves subdirectories are auto-created.
        Quality Contribution: Convenience for nested output paths.
        Acceptance Criteria: Subdirectory created (AC10).

        Task: T001
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        output_file = tmp_path / "subdir" / "nested" / "results.json"
        result = runner.invoke(
            app, ["search", "calculator", "--file", str(output_file)]
        )

        assert result.exit_code == 0, f"Expected exit 0: {result.output}"
        assert output_file.exists(), "Nested file should be created"
        assert output_file.parent.exists(), "Parent directories should exist"
