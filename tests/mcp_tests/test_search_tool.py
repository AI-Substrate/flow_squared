"""Tests for MCP search tool.

Phase 4 TDD tests for the search() MCP tool. Tests are organized by:
- T001: TestSearchToolTextMode - Text substring matching
- T002: TestSearchToolRegexMode - Regex pattern matching
- T003: TestSearchToolSemanticMode - Embedding similarity search
- T004: TestSearchToolFilters - Include/exclude path filters
- T005: TestSearchToolPagination - Limit/offset pagination
- T006: TestSearchToolCore - Envelope format and detail levels
- T009: TestSearchToolMCPProtocol - Async handling and protocol compliance

Per DYK#3: MCP tests focus on tool-level concerns (registration, parameters,
envelope format, protocol) - not search logic (already tested in test_search_service.py).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


# =============================================================================
# T001: TestSearchToolTextMode - Text substring matching
# =============================================================================


class TestSearchToolTextMode:
    """TDD tests for search text mode (T001)."""

    async def test_search_text_returns_envelope(
        self, search_test_graph_store
    ) -> None:
        """Search returns envelope with meta and results keys."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern="auth", mode="text")

        assert "meta" in result
        assert "results" in result

    async def test_search_text_matches_substring_in_content(
        self, search_test_graph_store
    ) -> None:
        """Text mode finds nodes with pattern in content."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern="authenticate", mode="text")

        assert len(result["results"]) >= 1
        node_ids = [r["node_id"] for r in result["results"]]
        assert any("auth" in nid for nid in node_ids)

    async def test_search_text_matches_in_node_id(
        self, search_test_graph_store
    ) -> None:
        """Text mode finds nodes with pattern in node_id."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern="login", mode="text")

        # Pattern should match node_id containing "login"
        assert len(result["results"]) >= 1

    async def test_search_text_matches_in_smart_content(
        self, search_test_graph_store
    ) -> None:
        """Text mode finds nodes with pattern in smart_content."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern="credentials", mode="text")

        # smart_content contains "credentials"
        assert len(result["results"]) >= 1

    async def test_search_text_case_insensitive(
        self, search_test_graph_store
    ) -> None:
        """Text mode is case insensitive."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result_upper = await search(pattern="AUTH", mode="text")
        result_lower = await search(pattern="auth", mode="text")

        # Both should find the same results
        assert len(result_upper["results"]) == len(result_lower["results"])

    async def test_search_text_no_matches_returns_empty(
        self, search_test_graph_store
    ) -> None:
        """Text mode returns empty results for no matches."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern="xyznonexistent123", mode="text")

        assert result["results"] == []
        assert result["meta"]["total"] == 0


# =============================================================================
# T002: TestSearchToolRegexMode - Regex pattern matching
# =============================================================================


class TestSearchToolRegexMode:
    """TDD tests for search regex mode (T002)."""

    async def test_search_regex_pattern_matching(
        self, search_test_graph_store
    ) -> None:
        """Regex mode matches patterns with regex syntax."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern="auth.*user", mode="regex")

        # Should match "authenticate" content
        assert "results" in result

    async def test_search_regex_invalid_pattern_raises_error(
        self, search_test_graph_store
    ) -> None:
        """Regex mode raises error for invalid patterns."""
        from fastmcp.exceptions import ToolError

        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        with pytest.raises(ToolError) as exc_info:
            await search(pattern="[invalid", mode="regex")

        assert "regex" in str(exc_info.value).lower() or "pattern" in str(exc_info.value).lower()

    async def test_search_regex_groups_work(
        self, search_test_graph_store
    ) -> None:
        """Regex mode supports capture groups."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern="(auth|calc)", mode="regex")

        # Should match nodes with "auth" or "calc"
        assert "results" in result

    async def test_search_regex_special_chars(
        self, search_test_graph_store
    ) -> None:
        """Regex mode handles special characters."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        # Pattern with escaped dot
        result = await search(pattern=r"\.py", mode="regex")

        # Should match file paths containing ".py"
        assert "results" in result


# =============================================================================
# T003: TestSearchToolSemanticMode - Embedding similarity search
# =============================================================================


class TestSearchToolSemanticMode:
    """TDD tests for search semantic mode (T003)."""

    async def test_search_semantic_requires_embeddings(
        self, search_semantic_graph_store
    ) -> None:
        """Semantic mode requires nodes to have embeddings."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config, adapter = search_semantic_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)
        dependencies.set_embedding_adapter(adapter)

        result = await search(pattern="authentication", mode="semantic")

        # Should find nodes based on embedding similarity
        assert "results" in result
        assert len(result["results"]) >= 1

    async def test_search_semantic_returns_scored_results(
        self, search_semantic_graph_store
    ) -> None:
        """Semantic mode returns results with scores."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config, adapter = search_semantic_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)
        dependencies.set_embedding_adapter(adapter)

        result = await search(pattern="authentication", mode="semantic")

        # All results should have scores (use tolerance for float precision)
        for r in result["results"]:
            assert "score" in r
            assert -0.001 <= r["score"] <= 1.001  # Allow float precision tolerance

    async def test_search_semantic_no_embeddings_raises_error(
        self, search_test_graph_store
    ) -> None:
        """Semantic mode raises error when no embeddings exist (explicit mode)."""
        from fastmcp.exceptions import ToolError

        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)
        # No embedding adapter set!

        with pytest.raises(ToolError) as exc_info:
            await search(pattern="auth", mode="semantic")

        # Error should mention embeddings or semantic
        assert "embedding" in str(exc_info.value).lower() or "semantic" in str(exc_info.value).lower()

    async def test_search_semantic_auto_fallback_to_text(
        self, search_test_graph_store
    ) -> None:
        """AUTO mode falls back to TEXT when no embeddings available."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)
        # No embedding adapter - should fall back to TEXT

        result = await search(pattern="auth", mode="auto")

        # Should succeed with TEXT fallback
        assert "results" in result


# =============================================================================
# T004: TestSearchToolFilters - Include/exclude path filters
# =============================================================================


class TestSearchToolFilters:
    """TDD tests for search include/exclude filters (T004)."""

    async def test_search_include_filter_keeps_matching(
        self, search_test_graph_store
    ) -> None:
        """Include filter keeps only matching node_ids."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern=".", mode="text", include=["auth"])

        # All results should contain "auth" in node_id
        for r in result["results"]:
            assert "auth" in r["node_id"]

    async def test_search_exclude_filter_removes_matching(
        self, search_test_graph_store
    ) -> None:
        """Exclude filter removes matching node_ids."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern=".", mode="text", exclude=["test"])

        # No results should contain "test" in node_id
        for r in result["results"]:
            assert "test" not in r["node_id"]

    async def test_search_include_exclude_combined(
        self, search_test_graph_store
    ) -> None:
        """Include and exclude filters work together."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern=".", mode="text", include=["src"], exclude=["test"])

        # Results should contain "src" but not "test"
        for r in result["results"]:
            assert "src" in r["node_id"]
            assert "test" not in r["node_id"]

    async def test_search_include_or_logic(
        self, search_test_graph_store
    ) -> None:
        """Include filter uses OR logic across patterns."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern=".", mode="text", include=["auth", "calc"])

        # Results should contain "auth" OR "calc"
        for r in result["results"]:
            assert "auth" in r["node_id"] or "calc" in r["node_id"]

    async def test_search_invalid_filter_regex_raises_error(
        self, search_test_graph_store
    ) -> None:
        """Invalid regex in filter raises error."""
        from fastmcp.exceptions import ToolError

        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        with pytest.raises(ToolError) as exc_info:
            await search(pattern="auth", mode="text", include=["[invalid"])

        assert "regex" in str(exc_info.value).lower() or "pattern" in str(exc_info.value).lower()


# =============================================================================
# T007: TestSearchToolGlobPatterns - Glob pattern support (plan 015)
# =============================================================================


class TestSearchToolGlobPatterns:
    """Tests for glob pattern support in MCP search (T007 - plan 015).

    Verifies that glob patterns like *.py and .py work through the MCP layer.
    The pattern conversion is tested thoroughly at unit level (44 tests in
    test_pattern_utils.py), so these tests focus on MCP integration.
    """

    async def test_search_glob_star_py_filters_correctly(
        self, search_test_graph_store
    ) -> None:
        """Glob *.py pattern converted to regex and filters correctly."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern=".", mode="text", include=["*.py"])

        # All results should have .py in node_id
        assert result["meta"]["total"] > 0
        for r in result["results"]:
            assert ".py" in r["node_id"], f"Expected .py in {r['node_id']}"

    async def test_search_extension_pattern_filters_correctly(
        self, search_test_graph_store
    ) -> None:
        """Extension pattern .py (without *) works correctly."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern=".", mode="text", include=[".py"])

        # All results should have .py in node_id
        assert result["meta"]["total"] > 0
        for r in result["results"]:
            assert ".py" in r["node_id"], f"Expected .py in {r['node_id']}"

    async def test_search_glob_exclude_works(
        self, search_test_graph_store
    ) -> None:
        """Glob pattern in exclude filter works."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        # Exclude all .py files - should get 0 results since fixture only has .py
        result = await search(pattern=".", mode="text", exclude=["*.py"])

        # No results should have .py (all excluded)
        for r in result["results"]:
            assert ".py" not in r["node_id"], f"Unexpected .py in {r['node_id']}"

    async def test_search_regex_still_works(
        self, search_test_graph_store
    ) -> None:
        """Regex patterns still work (backward compatibility)."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        # Use regex pattern that should pass through unchanged
        result = await search(pattern=".", mode="text", include=[".*auth.*"])

        # All results should have auth in node_id
        for r in result["results"]:
            assert "auth" in r["node_id"], f"Expected auth in {r['node_id']}"


# =============================================================================
# T005: TestSearchToolPagination - Limit/offset pagination
# =============================================================================


class TestSearchToolPagination:
    """TDD tests for search limit/offset pagination (T005)."""

    async def test_search_limit_restricts_results(
        self, search_test_graph_store
    ) -> None:
        """Limit parameter restricts number of results."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern=".", mode="text", limit=2)

        assert len(result["results"]) <= 2

    async def test_search_offset_skips_results(
        self, search_test_graph_store
    ) -> None:
        """Offset parameter skips results."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        # Get all results
        result_all = await search(pattern=".", mode="text", limit=10)

        # Get results with offset
        result_offset = await search(pattern=".", mode="text", limit=10, offset=1)

        # If there are results, offset should skip one
        if len(result_all["results"]) > 1:
            assert result_offset["results"][0]["node_id"] == result_all["results"][1]["node_id"]

    async def test_search_limit_offset_combined(
        self, search_test_graph_store
    ) -> None:
        """Limit and offset work together for pagination."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern=".", mode="text", limit=2, offset=1)

        # Should have at most 2 results
        assert len(result["results"]) <= 2

        # Meta should reflect pagination
        assert result["meta"]["pagination"]["limit"] == 2
        assert result["meta"]["pagination"]["offset"] == 1

    async def test_search_default_limit_is_5(
        self, search_test_graph_store
    ) -> None:
        """Default limit is 5."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern=".", mode="text")

        # Meta should show default limit
        assert result["meta"]["pagination"]["limit"] == 5


# =============================================================================
# T006: TestSearchToolCore - Envelope format and detail levels
# =============================================================================


class TestSearchToolCore:
    """TDD tests for search tool core functionality (T006)."""

    async def test_search_min_detail_has_9_fields(
        self, search_test_graph_store
    ) -> None:
        """Min detail results have 9 fields."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern="auth", mode="text", detail="min")

        if result["results"]:
            # Min detail has exactly 9 fields per SearchResult.to_dict()
            assert len(result["results"][0]) == 9

    async def test_search_max_detail_has_13_fields(
        self, search_test_graph_store
    ) -> None:
        """Max detail results have 13 fields."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern="auth", mode="text", detail="max")

        if result["results"]:
            # Max detail has exactly 13 fields per SearchResult.to_dict()
            assert len(result["results"][0]) == 13

    async def test_search_envelope_has_meta_and_results(
        self, search_test_graph_store
    ) -> None:
        """Response envelope has meta and results keys."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern="auth", mode="text")

        assert "meta" in result
        assert "results" in result

        # Meta should have required fields
        meta = result["meta"]
        assert "total" in meta
        assert "showing" in meta
        assert "pagination" in meta
        assert "folders" in meta

    async def test_search_empty_pattern_raises_error(
        self, search_test_graph_store
    ) -> None:
        """Empty pattern raises error."""
        from fastmcp.exceptions import ToolError

        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        with pytest.raises(ToolError) as exc_info:
            await search(pattern="", mode="text")

        assert "empty" in str(exc_info.value).lower() or "pattern" in str(exc_info.value).lower()

    async def test_search_returns_scores_in_range(
        self, search_test_graph_store
    ) -> None:
        """All results have scores in 0.0-1.0 range."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        result = await search(pattern="auth", mode="text")

        for r in result["results"]:
            assert 0.0 <= r["score"] <= 1.0


# =============================================================================
# T009: TestSearchToolMCPProtocol - Async handling and protocol compliance
# =============================================================================


class TestSearchToolMCPProtocol:
    """TDD tests for search tool MCP protocol compliance (T009)."""

    @pytest.mark.asyncio
    async def test_search_callable_via_mcp_client(self, search_mcp_client) -> None:
        """Search tool is callable via MCP client."""

        result = await search_mcp_client.call_tool("search", {"pattern": "auth", "mode": "text"})

        # Should return parseable JSON
        data = json.loads(result.content[0].text)
        assert "meta" in data
        assert "results" in data

    @pytest.mark.asyncio
    async def test_search_async_execution_works(self, search_mcp_client) -> None:
        """Async execution works correctly."""

        result = await search_mcp_client.call_tool("search", {"pattern": "def", "mode": "regex"})

        data = json.loads(result.content[0].text)
        assert "results" in data

    @pytest.mark.asyncio
    async def test_search_listed_in_available_tools(self, search_mcp_client) -> None:
        """Search is listed in available tools."""
        tools = await search_mcp_client.list_tools()

        tool_names = [t.name for t in tools]
        assert "search" in tool_names

    @pytest.mark.asyncio
    async def test_search_has_annotations(self, search_mcp_client) -> None:
        """Search tool has MCP annotations."""
        tools = await search_mcp_client.list_tools()

        search_tool = next(t for t in tools if t.name == "search")
        assert search_tool.annotations is not None
        # Per DYK#8: openWorldHint should be True for SEMANTIC API calls
        assert search_tool.annotations.openWorldHint is True
        # Per AC8: readOnlyHint=False because save_to_file writes to filesystem
        assert search_tool.annotations.readOnlyHint is False

    @pytest.mark.asyncio
    async def test_search_no_stdout_pollution(self, search_mcp_client, capsys) -> None:
        """Search tool produces no stdout output."""
        await search_mcp_client.call_tool("search", {"pattern": "test", "mode": "text"})

        captured = capsys.readouterr()
        # MCP protocol requires zero stdout pollution
        assert captured.out == ""

    @pytest.mark.asyncio
    async def test_search_error_handling_via_mcp(self, search_mcp_client) -> None:
        """Search tool handles errors and raises ToolError via MCP.

        Tests that ToolError is properly raised when an error occurs,
        verifying the error boundary between MCP and tool implementation.
        """
        from fastmcp.exceptions import ToolError

        # Invalid regex pattern should raise ToolError
        with pytest.raises(ToolError) as exc_info:
            await search_mcp_client.call_tool("search", {"pattern": "test", "mode": "regex", "include": ["[invalid"]})

        # Error message should mention regex or pattern
        error_msg = str(exc_info.value).lower()
        assert "regex" in error_msg or "pattern" in error_msg


# =============================================================================
# T004 (Phase 1: save-to-file): TestSearchSaveToFile - save_to_file parameter
# =============================================================================


class TestSearchSaveToFile:
    """T004: Tests for MCP search save_to_file parameter (AC3, AC4, AC9, AC10).

    Full TDD tests per save-to-file-plan.md.
    These tests are expected to FAIL until T005 implements the feature.
    """

    @pytest.mark.asyncio
    async def test_given_save_to_file_when_search_then_creates_file(
        self, search_test_graph_store, tmp_path
    ):
        """
        Purpose: Proves save_to_file creates the specified file.
        Quality Contribution: Enables agents to persist search results.
        Acceptance Criteria: File exists after call (AC3).

        Task: T004
        """
        import os

        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        output_file = tmp_path / "results.json"
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            await search(pattern="auth", mode="text", save_to_file="results.json")
        finally:
            os.chdir(original_cwd)

        assert output_file.exists(), "File should be created"

    @pytest.mark.asyncio
    async def test_given_save_to_file_when_search_then_writes_valid_json_envelope(
        self, search_test_graph_store, tmp_path
    ):
        """
        Purpose: Proves saved file contains valid JSON envelope.
        Quality Contribution: Ensures parseable output for jq/agents.
        Acceptance Criteria: JSON has meta and results keys (AC3).

        Task: T004
        """
        import os

        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        output_file = tmp_path / "results.json"
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            await search(pattern="auth", mode="text", save_to_file="results.json")
        finally:
            os.chdir(original_cwd)

        data = json.loads(output_file.read_text())
        assert "meta" in data, "JSON must have 'meta' key"
        assert "results" in data, "JSON must have 'results' key"

    @pytest.mark.asyncio
    async def test_given_save_to_file_when_search_then_response_includes_saved_to(
        self, search_test_graph_store, tmp_path
    ):
        """
        Purpose: Proves response includes saved_to field with absolute path.
        Quality Contribution: Agents know where file was saved.
        Acceptance Criteria: Response has saved_to with absolute path (AC3).

        Task: T004
        """
        import os

        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = await search(pattern="auth", mode="text", save_to_file="results.json")
        finally:
            os.chdir(original_cwd)

        assert "saved_to" in result, "Response must include saved_to"
        assert str(tmp_path / "results.json") == result["saved_to"]

    @pytest.mark.asyncio
    async def test_given_path_escape_when_save_to_file_then_raises_tool_error(
        self, search_test_graph_store, tmp_path
    ):
        """
        Purpose: Proves path validation rejects directory traversal.
        Quality Contribution: Security - prevents writes outside cwd.
        Acceptance Criteria: ToolError raised for ../escape.json (AC4).

        Task: T004
        """
        import os

        from fastmcp.exceptions import ToolError

        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(ToolError) as exc_info:
                await search(pattern="auth", mode="text", save_to_file="../escape.json")
        finally:
            os.chdir(original_cwd)

        assert "escape" in str(exc_info.value).lower() or "path" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_given_absolute_path_outside_cwd_when_save_to_file_then_raises_tool_error(
        self, search_test_graph_store, tmp_path
    ):
        """
        Purpose: Proves absolute paths outside cwd are rejected.
        Quality Contribution: Security - prevents writes to arbitrary locations.
        Acceptance Criteria: ToolError for /tmp/outside.json (AC4).

        Task: T004
        """
        import os

        from fastmcp.exceptions import ToolError

        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(ToolError):
                await search(pattern="auth", mode="text", save_to_file="/tmp/outside.json")
        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_given_empty_results_when_save_to_file_then_still_saves_envelope(
        self, search_test_graph_store, tmp_path
    ):
        """
        Purpose: Proves empty results still create valid file.
        Quality Contribution: Consistent behavior for agent workflows.
        Acceptance Criteria: Empty envelope saved (AC9).

        Task: T004
        """
        import os

        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        output_file = tmp_path / "results.json"
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            await search(
                pattern="NONEXISTENT_PATTERN_XYZ123", mode="text", save_to_file="results.json"
            )
        finally:
            os.chdir(original_cwd)

        assert output_file.exists(), "File should exist even with empty results"
        data = json.loads(output_file.read_text())
        assert data["results"] == [], "Empty results should be empty array"

    @pytest.mark.asyncio
    async def test_given_nested_path_when_save_to_file_then_creates_subdirectory(
        self, search_test_graph_store, tmp_path
    ):
        """
        Purpose: Proves subdirectories are auto-created.
        Quality Contribution: Convenience for nested output paths.
        Acceptance Criteria: Subdirectory created (AC10).

        Task: T004
        """
        import os

        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store
        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        output_file = tmp_path / "subdir" / "nested" / "results.json"
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            await search(
                pattern="auth", mode="text", save_to_file="subdir/nested/results.json"
            )
        finally:
            os.chdir(original_cwd)

        assert output_file.exists(), "Nested file should be created"
