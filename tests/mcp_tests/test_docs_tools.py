"""Tests for MCP documentation tools (docs_list, docs_get).

Phase 3: MCP Tool Integration
Testing Approach: Full TDD

These tests verify the MCP tools for documentation access:
- docs_list: Browse available documentation with filtering
- docs_get: Retrieve full document content by ID

Per DYK-1: Both tools use sync function pattern (not async).
Per DYK-4: Uses dedicated docs_mcp_client fixture (no GraphStore needed).
Per DYK-5: Response format uses explicit dict construction.
"""

from __future__ import annotations

import pytest

from fs2.mcp import dependencies

# =============================================================================
# T001: TestDocsListTool - Direct function call tests
# =============================================================================


class TestDocsListTool:
    """Tests for docs_list MCP tool (direct function calls).

    Per DYK-1: These are sync function tests (not async).
    Per DYK-5: Response format is {"docs": [...], "count": N}.
    """

    @pytest.fixture(autouse=True)
    def setup_docs_service(self):
        """Inject DocsService with test fixtures before each test."""
        from fs2.core.services.docs_service import DocsService

        # Reset and inject test service
        dependencies.reset_services()
        test_service = DocsService(docs_package="tests.fixtures.docs")
        dependencies.set_docs_service(test_service)

        yield

        # Cleanup
        dependencies.reset_docs_service()

    def test_docs_list_returns_all_documents(self):
        """
        Purpose: Proves docs_list returns all registered docs when no filters
        Quality Contribution: Validates basic catalog functionality (AC1)
        Acceptance Criteria: Response has 'docs' array with count matching registry
        """
        from fs2.mcp.server import docs_list

        result = docs_list()

        assert "docs" in result
        assert "count" in result
        assert isinstance(result["docs"], list)
        assert result["count"] == len(result["docs"])
        assert result["count"] == 2  # sample-doc and another-doc

    def test_docs_list_with_category_filter(self):
        """
        Purpose: Proves category filtering works (exact match)
        Quality Contribution: Enables agent discovery by category (AC2)
        Acceptance Criteria: Only docs with matching category returned
        """
        from fs2.mcp.server import docs_list

        result = docs_list(category="how-to")

        assert result["count"] == 1
        assert all(doc["category"] == "how-to" for doc in result["docs"])
        assert result["docs"][0]["id"] == "sample-doc"

    def test_docs_list_with_tags_filter_or_logic(self):
        """
        Purpose: Proves tag filtering uses OR logic
        Quality Contribution: Matches spec AC3 (OR logic for tags)
        Acceptance Criteria: Docs with ANY matching tag returned
        """
        from fs2.mcp.server import docs_list

        # sample-doc has tags: sample, testing
        # another-doc has tags: config, reference
        result = docs_list(tags=["sample", "config"])

        # Both docs should match (one has 'sample', other has 'config')
        assert result["count"] == 2

    def test_docs_list_with_combined_filters(self):
        """
        Purpose: Proves category + tags filters work together
        Quality Contribution: Validates complex filtering scenarios
        Acceptance Criteria: Both filters applied (AND between category/tags)
        """
        from fs2.mcp.server import docs_list

        result = docs_list(category="how-to", tags=["testing"])

        # Only sample-doc has category=how-to AND tag=testing
        assert result["count"] == 1
        assert result["docs"][0]["id"] == "sample-doc"

    def test_docs_list_empty_results(self):
        """
        Purpose: Proves empty results return properly formatted response
        Quality Contribution: Validates graceful handling of no matches
        Acceptance Criteria: Returns {"docs": [], "count": 0}
        """
        from fs2.mcp.server import docs_list

        result = docs_list(category="nonexistent-category")

        assert result["docs"] == []
        assert result["count"] == 0

    def test_docs_list_response_format_structure(self):
        """
        Purpose: Proves response structure matches spec (AC6)
        Quality Contribution: Validates JSON serialization works
        Acceptance Criteria: All expected fields present in response
        """
        import json

        from fs2.mcp.server import docs_list

        result = docs_list()

        # Must be JSON-serializable
        json_str = json.dumps(result)
        assert json_str  # Non-empty

        # Check structure
        assert "docs" in result
        assert "count" in result

        # Each doc must have expected metadata fields
        for doc in result["docs"]:
            assert "id" in doc
            assert "title" in doc
            assert "summary" in doc
            assert "category" in doc
            assert "tags" in doc
            assert "path" in doc


# =============================================================================
# T002: TestDocsGetTool - Direct function call tests
# =============================================================================


class TestDocsGetTool:
    """Tests for docs_get MCP tool (direct function calls).

    Per DYK-1: These are sync function tests (not async).
    Per DYK-2: Returns None for not-found (not error).
    Per DYK-5: Response format is {id, title, content, metadata}.
    """

    @pytest.fixture(autouse=True)
    def setup_docs_service(self):
        """Inject DocsService with test fixtures before each test."""
        from fs2.core.services.docs_service import DocsService

        # Reset and inject test service
        dependencies.reset_services()
        test_service = DocsService(docs_package="tests.fixtures.docs")
        dependencies.set_docs_service(test_service)

        yield

        # Cleanup
        dependencies.reset_docs_service()

    def test_docs_get_returns_content(self):
        """
        Purpose: Proves docs_get returns full document content (AC4)
        Quality Contribution: Validates content retrieval works
        Acceptance Criteria: Response has id, title, content, metadata
        """
        from fs2.mcp.server import docs_get

        result = docs_get(id="sample-doc")

        assert result is not None
        assert result["id"] == "sample-doc"
        assert "title" in result
        assert "content" in result
        assert "metadata" in result
        assert len(result["content"]) > 0  # Not empty

    def test_docs_get_nonexistent_returns_none(self):
        """
        Purpose: Proves docs_get returns None for non-existent ID (AC5)
        Quality Contribution: Validates graceful handling of missing docs
        Acceptance Criteria: Returns None (not error)
        """
        from fs2.mcp.server import docs_get

        result = docs_get(id="nonexistent-doc")

        assert result is None

    def test_docs_get_content_matches_file(self):
        """
        Purpose: Proves content matches actual file content
        Quality Contribution: Validates content integrity
        Acceptance Criteria: Content starts with expected markdown header
        """
        from fs2.mcp.server import docs_get

        result = docs_get(id="sample-doc")

        assert result is not None
        assert result["content"].startswith("# Sample Documentation")

    def test_docs_get_metadata_populated(self):
        """
        Purpose: Proves metadata fields are correctly populated
        Quality Contribution: Validates metadata extraction
        Acceptance Criteria: All metadata fields present and correct
        """
        from fs2.mcp.server import docs_get

        result = docs_get(id="sample-doc")

        assert result is not None
        metadata = result["metadata"]
        assert metadata["id"] == "sample-doc"
        assert metadata["title"] == "Sample Documentation"
        assert metadata["category"] == "how-to"
        assert "sample" in metadata["tags"]
        assert "testing" in metadata["tags"]

    def test_docs_get_response_is_json_serializable(self):
        """
        Purpose: Proves response can be JSON serialized
        Quality Contribution: Validates MCP protocol compatibility
        Acceptance Criteria: json.dumps succeeds
        """
        import json

        from fs2.mcp.server import docs_get

        result = docs_get(id="sample-doc")

        assert result is not None
        json_str = json.dumps(result)
        assert json_str  # Non-empty


# =============================================================================
# T003: TestDocsToolAnnotations - Verify MCP tool annotations
# =============================================================================


class TestDocsToolAnnotations:
    """Tests for MCP tool annotations (via protocol).

    Per Critical Finding 03: Tools must have correct annotations:
    - readOnlyHint=True (no side effects)
    - destructiveHint=False
    - idempotentHint=True (same inputs = same outputs)
    - openWorldHint=False (no external network calls)

    These tests require mcp_client fixture to query tools via MCP protocol.
    """

    @pytest.mark.asyncio
    async def test_docs_list_has_correct_annotations(self, mcp_client):
        """
        Purpose: Proves docs_list has correct MCP annotations (CF-03)
        Quality Contribution: Agents can make informed tool selection
        Acceptance Criteria: Tool has readOnly, idempotent, not destructive, not openWorld
        """
        tools = await mcp_client.list_tools()

        docs_list_tool = next((t for t in tools if t.name == "docs_list"), None)
        assert docs_list_tool is not None, "docs_list tool should exist"

        # Check annotations per Critical Finding 03
        assert docs_list_tool.annotations is not None, "annotations should be present"
        assert docs_list_tool.annotations.readOnlyHint is True
        assert docs_list_tool.annotations.destructiveHint is False
        assert docs_list_tool.annotations.idempotentHint is True
        assert docs_list_tool.annotations.openWorldHint is False

    @pytest.mark.asyncio
    async def test_docs_get_has_correct_annotations(self, mcp_client):
        """
        Purpose: Proves docs_get has correct MCP annotations (CF-03)
        Quality Contribution: Agents can make informed tool selection
        Acceptance Criteria: Tool has readOnly, idempotent, not destructive, not openWorld
        """
        tools = await mcp_client.list_tools()

        docs_get_tool = next((t for t in tools if t.name == "docs_get"), None)
        assert docs_get_tool is not None, "docs_get tool should exist"

        # Check annotations per Critical Finding 03
        assert docs_get_tool.annotations is not None, "annotations should be present"
        assert docs_get_tool.annotations.readOnlyHint is True
        assert docs_get_tool.annotations.destructiveHint is False
        assert docs_get_tool.annotations.idempotentHint is True
        assert docs_get_tool.annotations.openWorldHint is False


# =============================================================================
# T007: TestDocsNotFoundErrorTranslation - Error translation defensive test
# =============================================================================


class TestDocsNotFoundErrorTranslation:
    """Tests for DocsNotFoundError translation in translate_error().

    Per DYK-3: This error only fires on broken package install.
    We still test the translation function directly to document the path.
    """

    def test_translate_error_handles_docs_not_found_error(self):
        """
        Purpose: Proves DocsNotFoundError is translated with actionable guidance
        Quality Contribution: Verifies CF-06 compliance for docs errors
        Acceptance Criteria: Returns dict with action guidance
        """
        from fs2.core.adapters.exceptions import DocsNotFoundError
        from fs2.mcp.server import translate_error

        # Create a DocsNotFoundError using default message (no custom message)
        # This tests the real error format agents will see
        error = DocsNotFoundError("registry.yaml")

        result = translate_error(error)

        assert result["type"] == "DocsNotFoundError"
        assert "registry.yaml" in result["message"]
        assert result["action"] is not None
        assert "docs_list()" in result["action"]


# =============================================================================
# T008: TestDocsToolsProtocol - MCP protocol integration tests
# =============================================================================


class TestDocsToolsProtocol:
    """Protocol-level integration tests using docs_mcp_client fixture.

    Per DYK-4: Uses dedicated docs_mcp_client fixture (no GraphStore needed).
    These tests validate JSON serialization, MCP protocol framing, and
    end-to-end tool invocation via the MCP client.
    """

    @pytest.mark.asyncio
    async def test_docs_list_via_protocol(self, docs_mcp_client):
        """
        Purpose: Proves docs_list works via MCP protocol
        Quality Contribution: Validates end-to-end serialization
        Acceptance Criteria: Response parses correctly from MCP
        """
        import json

        result = await docs_mcp_client.call_tool("docs_list", {})

        # Parse response from MCP
        response = json.loads(result.content[0].text)

        assert "docs" in response
        assert "count" in response
        assert response["count"] == 2  # sample-doc and another-doc

    @pytest.mark.asyncio
    async def test_docs_list_with_category_via_protocol(self, docs_mcp_client):
        """
        Purpose: Proves category filter works via MCP protocol
        Quality Contribution: Validates parameter passing through protocol
        Acceptance Criteria: Filtering works end-to-end
        """
        import json

        result = await docs_mcp_client.call_tool("docs_list", {"category": "how-to"})

        response = json.loads(result.content[0].text)

        assert response["count"] == 1
        assert response["docs"][0]["category"] == "how-to"

    @pytest.mark.asyncio
    async def test_docs_get_via_protocol(self, docs_mcp_client):
        """
        Purpose: Proves docs_get works via MCP protocol
        Quality Contribution: Validates full document retrieval end-to-end
        Acceptance Criteria: Full document content returned via MCP
        """
        import json

        result = await docs_mcp_client.call_tool("docs_get", {"id": "sample-doc"})

        response = json.loads(result.content[0].text)

        assert response["id"] == "sample-doc"
        assert "content" in response
        assert response["content"].startswith("# Sample Documentation")

    @pytest.mark.asyncio
    async def test_docs_get_not_found_via_protocol(self, docs_mcp_client):
        """
        Purpose: Proves docs_get returns null via MCP for not-found
        Quality Contribution: Validates None serialization over protocol
        Acceptance Criteria: Response is null in JSON
        """
        result = await docs_mcp_client.call_tool("docs_get", {"id": "nonexistent-doc"})

        # FastMCP returns None via structured_content, not content array
        # When tool returns None, content is empty and structured_content has the result
        assert result.content == []  # No text content
        assert result.structured_content == {"result": None}
        assert result.is_error is False  # Not an error, just not found

    @pytest.mark.asyncio
    async def test_docs_tools_listed_in_tools(self, docs_mcp_client):
        """
        Purpose: Proves both docs tools appear in tools list
        Quality Contribution: Validates tool discovery
        Acceptance Criteria: docs_list and docs_get in available tools
        """
        tools = await docs_mcp_client.list_tools()

        tool_names = [t.name for t in tools]
        assert "docs_list" in tool_names, "docs_list should be listed"
        assert "docs_get" in tool_names, "docs_get should be listed"
