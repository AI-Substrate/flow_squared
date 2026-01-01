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

    def test_search_text_returns_envelope(
        self, search_test_graph_store
    ) -> None:
        """Search returns envelope with meta and results keys."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern="auth", mode="text")
        )

        assert "meta" in result
        assert "results" in result

    def test_search_text_matches_substring_in_content(
        self, search_test_graph_store
    ) -> None:
        """Text mode finds nodes with pattern in content."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern="authenticate", mode="text")
        )

        assert len(result["results"]) >= 1
        node_ids = [r["node_id"] for r in result["results"]]
        assert any("auth" in nid for nid in node_ids)

    def test_search_text_matches_in_node_id(
        self, search_test_graph_store
    ) -> None:
        """Text mode finds nodes with pattern in node_id."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern="login", mode="text")
        )

        # Pattern should match node_id containing "login"
        assert len(result["results"]) >= 1

    def test_search_text_matches_in_smart_content(
        self, search_test_graph_store
    ) -> None:
        """Text mode finds nodes with pattern in smart_content."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern="credentials", mode="text")
        )

        # smart_content contains "credentials"
        assert len(result["results"]) >= 1

    def test_search_text_case_insensitive(
        self, search_test_graph_store
    ) -> None:
        """Text mode is case insensitive."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio

        result_upper = asyncio.get_event_loop().run_until_complete(
            search(pattern="AUTH", mode="text")
        )
        result_lower = asyncio.get_event_loop().run_until_complete(
            search(pattern="auth", mode="text")
        )

        # Both should find the same results
        assert len(result_upper["results"]) == len(result_lower["results"])

    def test_search_text_no_matches_returns_empty(
        self, search_test_graph_store
    ) -> None:
        """Text mode returns empty results for no matches."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern="xyznonexistent123", mode="text")
        )

        assert result["results"] == []
        assert result["meta"]["total"] == 0


# =============================================================================
# T002: TestSearchToolRegexMode - Regex pattern matching
# =============================================================================


class TestSearchToolRegexMode:
    """TDD tests for search regex mode (T002)."""

    def test_search_regex_pattern_matching(
        self, search_test_graph_store
    ) -> None:
        """Regex mode matches patterns with regex syntax."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern="auth.*user", mode="regex")
        )

        # Should match "authenticate" content
        assert "results" in result

    def test_search_regex_invalid_pattern_raises_error(
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

        import asyncio

        with pytest.raises(ToolError) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                search(pattern="[invalid", mode="regex")
            )

        assert "regex" in str(exc_info.value).lower() or "pattern" in str(exc_info.value).lower()

    def test_search_regex_groups_work(
        self, search_test_graph_store
    ) -> None:
        """Regex mode supports capture groups."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern="(auth|calc)", mode="regex")
        )

        # Should match nodes with "auth" or "calc"
        assert "results" in result

    def test_search_regex_special_chars(
        self, search_test_graph_store
    ) -> None:
        """Regex mode handles special characters."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        # Pattern with escaped dot
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern=r"\.py", mode="regex")
        )

        # Should match file paths containing ".py"
        assert "results" in result


# =============================================================================
# T003: TestSearchToolSemanticMode - Embedding similarity search
# =============================================================================


class TestSearchToolSemanticMode:
    """TDD tests for search semantic mode (T003)."""

    def test_search_semantic_requires_embeddings(
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

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern="authentication", mode="semantic")
        )

        # Should find nodes based on embedding similarity
        assert "results" in result
        assert len(result["results"]) >= 1

    def test_search_semantic_returns_scored_results(
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

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern="authentication", mode="semantic")
        )

        # All results should have scores (use tolerance for float precision)
        for r in result["results"]:
            assert "score" in r
            assert -0.001 <= r["score"] <= 1.001  # Allow float precision tolerance

    def test_search_semantic_no_embeddings_raises_error(
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

        import asyncio

        with pytest.raises(ToolError) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                search(pattern="auth", mode="semantic")
            )

        # Error should mention embeddings or semantic
        assert "embedding" in str(exc_info.value).lower() or "semantic" in str(exc_info.value).lower()

    def test_search_semantic_auto_fallback_to_text(
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

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern="auth", mode="auto")
        )

        # Should succeed with TEXT fallback
        assert "results" in result


# =============================================================================
# T004: TestSearchToolFilters - Include/exclude path filters
# =============================================================================


class TestSearchToolFilters:
    """TDD tests for search include/exclude filters (T004)."""

    def test_search_include_filter_keeps_matching(
        self, search_test_graph_store
    ) -> None:
        """Include filter keeps only matching node_ids."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern=".", mode="text", include=["auth"])
        )

        # All results should contain "auth" in node_id
        for r in result["results"]:
            assert "auth" in r["node_id"]

    def test_search_exclude_filter_removes_matching(
        self, search_test_graph_store
    ) -> None:
        """Exclude filter removes matching node_ids."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern=".", mode="text", exclude=["test"])
        )

        # No results should contain "test" in node_id
        for r in result["results"]:
            assert "test" not in r["node_id"]

    def test_search_include_exclude_combined(
        self, search_test_graph_store
    ) -> None:
        """Include and exclude filters work together."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern=".", mode="text", include=["src"], exclude=["test"])
        )

        # Results should contain "src" but not "test"
        for r in result["results"]:
            assert "src" in r["node_id"]
            assert "test" not in r["node_id"]

    def test_search_include_or_logic(
        self, search_test_graph_store
    ) -> None:
        """Include filter uses OR logic across patterns."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern=".", mode="text", include=["auth", "calc"])
        )

        # Results should contain "auth" OR "calc"
        for r in result["results"]:
            assert "auth" in r["node_id"] or "calc" in r["node_id"]

    def test_search_invalid_filter_regex_raises_error(
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

        import asyncio

        with pytest.raises(ToolError) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                search(pattern="auth", mode="text", include=["[invalid"])
            )

        assert "regex" in str(exc_info.value).lower() or "pattern" in str(exc_info.value).lower()


# =============================================================================
# T005: TestSearchToolPagination - Limit/offset pagination
# =============================================================================


class TestSearchToolPagination:
    """TDD tests for search limit/offset pagination (T005)."""

    def test_search_limit_restricts_results(
        self, search_test_graph_store
    ) -> None:
        """Limit parameter restricts number of results."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern=".", mode="text", limit=2)
        )

        assert len(result["results"]) <= 2

    def test_search_offset_skips_results(
        self, search_test_graph_store
    ) -> None:
        """Offset parameter skips results."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio

        # Get all results
        result_all = asyncio.get_event_loop().run_until_complete(
            search(pattern=".", mode="text", limit=10)
        )

        # Get results with offset
        result_offset = asyncio.get_event_loop().run_until_complete(
            search(pattern=".", mode="text", limit=10, offset=1)
        )

        # If there are results, offset should skip one
        if len(result_all["results"]) > 1:
            assert result_offset["results"][0]["node_id"] == result_all["results"][1]["node_id"]

    def test_search_limit_offset_combined(
        self, search_test_graph_store
    ) -> None:
        """Limit and offset work together for pagination."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            search(pattern=".", mode="text", limit=2, offset=1)
        )

        # Should have at most 2 results
        assert len(result["results"]) <= 2

        # Meta should reflect pagination
        assert result["meta"]["pagination"]["limit"] == 2
        assert result["meta"]["pagination"]["offset"] == 1

    def test_search_default_limit_is_20(
        self, search_test_graph_store
    ) -> None:
        """Default limit is 20."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern=".", mode="text")
        )

        # Meta should show default limit
        assert result["meta"]["pagination"]["limit"] == 20


# =============================================================================
# T006: TestSearchToolCore - Envelope format and detail levels
# =============================================================================


class TestSearchToolCore:
    """TDD tests for search tool core functionality (T006)."""

    def test_search_min_detail_has_9_fields(
        self, search_test_graph_store
    ) -> None:
        """Min detail results have 9 fields."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern="auth", mode="text", detail="min")
        )

        if result["results"]:
            # Min detail has exactly 9 fields per SearchResult.to_dict()
            assert len(result["results"][0]) == 9

    def test_search_max_detail_has_13_fields(
        self, search_test_graph_store
    ) -> None:
        """Max detail results have 13 fields."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern="auth", mode="text", detail="max")
        )

        if result["results"]:
            # Max detail has exactly 13 fields per SearchResult.to_dict()
            assert len(result["results"][0]) == 13

    def test_search_envelope_has_meta_and_results(
        self, search_test_graph_store
    ) -> None:
        """Response envelope has meta and results keys."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern="auth", mode="text")
        )

        assert "meta" in result
        assert "results" in result

        # Meta should have required fields
        meta = result["meta"]
        assert "total" in meta
        assert "showing" in meta
        assert "pagination" in meta
        assert "folders" in meta

    def test_search_empty_pattern_raises_error(
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

        import asyncio

        with pytest.raises(ToolError) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                search(pattern="", mode="text")
            )

        assert "empty" in str(exc_info.value).lower() or "pattern" in str(exc_info.value).lower()

    def test_search_returns_scores_in_range(
        self, search_test_graph_store
    ) -> None:
        """All results have scores in 0.0-1.0 range."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import search

        store, config = search_test_graph_store

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            search(pattern="auth", mode="text")
        )

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
        assert search_tool.annotations.readOnlyHint is True

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
