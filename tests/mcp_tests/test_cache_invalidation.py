"""E2E cache invalidation tests for multi-graph MCP integration.

Per T015: Validates that GraphService staleness detection works end-to-end
when accessed via MCP tools. Tests the flow:
1. Query graph via MCP
2. Modify graph file (simulates fs2 scan)
3. Query again via MCP
4. Verify new content is visible (cache was invalidated)

Per DYK-03: Full delegation to GraphService ensures staleness detection works.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


def create_graph_pickle(
    path: Path,
    nodes: list[tuple[str, str, str, str]],
) -> None:
    """Create a real graph pickle file using NetworkXGraphStore.

    Args:
        path: Path to write pickle file.
        nodes: List of (node_id, name, category, content) tuples.
    """
    from fs2.config.objects import GraphConfig, ScanConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.models.code_node import CodeNode
    from fs2.core.repos.graph_store_impl import NetworkXGraphStore
    from fs2.core.utils.hash import compute_content_hash

    # Create a minimal config for NetworkXGraphStore
    config = FakeConfigurationService(
        ScanConfig(),
        GraphConfig(graph_path=str(path)),
    )

    store = NetworkXGraphStore(config)

    for node_id, name, category, content in nodes:
        node = CodeNode(
            node_id=node_id,
            name=name,
            category=category,
            ts_kind="test_node",
            qualified_name=name,
            start_line=1,
            end_line=10,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=len(content),
            content=content,
            content_hash=compute_content_hash(content),
            signature=None,
            language="python",
            is_named=True,
            field_name=None,
            parent_node_id=None,
            embedding=None,
            smart_content=None,
            smart_content_embedding=None,
        )
        store.add_node(node)

    store.save(path)


class TestCacheInvalidationE2E:
    """T015: E2E validation of cache invalidation via MCP.

    These tests use real GraphService (not FakeGraphService) to validate
    that staleness detection works when accessing graphs via MCP tools.
    """

    @pytest.mark.asyncio
    async def test_tree_sees_updated_content_after_graph_modification(
        self, tmp_path: Path
    ):
        """
        Purpose: Proves cache invalidation works for tree tool.
        Quality Contribution: Users see fresh content after re-scanning.
        Acceptance Criteria: Second query returns updated content.

        Task: T015
        """
        from fastmcp.client import Client

        from fs2.config.objects import GraphConfig, OtherGraphsConfig, ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.mcp import dependencies
        from fs2.mcp.server import mcp

        # Create initial graph with "OriginalClass"
        graph_path = tmp_path / "graph.pickle"
        create_graph_pickle(
            graph_path,
            [
                ("file:src/original.py", "original.py", "file", "# Original"),
                (
                    "class:src/original.py:OriginalClass",
                    "OriginalClass",
                    "class",
                    "class OriginalClass: pass",
                ),
            ],
        )

        # Create config pointing to real graph file
        config = FakeConfigurationService(
            ScanConfig(),
            GraphConfig(graph_path=str(graph_path)),
            OtherGraphsConfig(graphs=[]),
        )

        # Reset and inject config (but NOT GraphService - use real one)
        dependencies.reset_services()
        dependencies.set_config(config)
        # Don't inject FakeGraphService - let it use real GraphService

        async with Client(mcp) as client:
            # First query - should see OriginalClass
            result1 = await client.call_tool("tree", {"pattern": ".", "format": "json"})
            data1 = json.loads(result1.content[0].text)
            node_ids1 = [n["node_id"] for n in data1.get("tree", [])]

            assert any("OriginalClass" in nid for nid in node_ids1), (
                f"First query should find OriginalClass. Got: {node_ids1}"
            )

            # Wait to ensure mtime changes
            time.sleep(0.1)

            # Modify graph file - add NewClass, remove OriginalClass
            create_graph_pickle(
                graph_path,
                [
                    ("file:src/new.py", "new.py", "file", "# New"),
                    ("class:src/new.py:NewClass", "NewClass", "class", "class NewClass: pass"),
                ],
            )

            # Second query - should see NewClass (cache invalidated)
            result2 = await client.call_tool("tree", {"pattern": ".", "format": "json"})
            data2 = json.loads(result2.content[0].text)
            node_ids2 = [n["node_id"] for n in data2.get("tree", [])]

            assert any("NewClass" in nid for nid in node_ids2), (
                f"Second query should find NewClass after invalidation. Got: {node_ids2}"
            )
            assert not any("OriginalClass" in nid for nid in node_ids2), (
                f"Second query should NOT find OriginalClass. Got: {node_ids2}"
            )

    @pytest.mark.asyncio
    async def test_get_node_sees_updated_content_after_graph_modification(
        self, tmp_path: Path
    ):
        """
        Purpose: Proves cache invalidation works for get_node tool.
        Quality Contribution: Users see fresh node content after re-scanning.
        Acceptance Criteria: Second query returns updated node content.

        Task: T015
        """
        from fastmcp.client import Client

        from fs2.config.objects import GraphConfig, OtherGraphsConfig, ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.mcp import dependencies
        from fs2.mcp.server import mcp

        # Create initial graph with specific content
        graph_path = tmp_path / "graph.pickle"
        create_graph_pickle(
            graph_path,
            [
                (
                    "callable:src/func.py:my_function",
                    "my_function",
                    "callable",
                    "def my_function(): return 'version_1'",
                ),
            ],
        )

        config = FakeConfigurationService(
            ScanConfig(),
            GraphConfig(graph_path=str(graph_path)),
            OtherGraphsConfig(graphs=[]),
        )

        dependencies.reset_services()
        dependencies.set_config(config)

        async with Client(mcp) as client:
            # First query
            result1 = await client.call_tool(
                "get_node", {"node_id": "callable:src/func.py:my_function"}
            )
            data1 = json.loads(result1.content[0].text)

            assert data1 is not None
            assert "version_1" in data1["content"]

            # Wait to ensure mtime changes
            time.sleep(0.1)

            # Update graph with new content
            create_graph_pickle(
                graph_path,
                [
                    (
                        "callable:src/func.py:my_function",
                        "my_function",
                        "callable",
                        "def my_function(): return 'version_2'",
                    ),
                ],
            )

            # Second query - should see version_2
            result2 = await client.call_tool(
                "get_node", {"node_id": "callable:src/func.py:my_function"}
            )
            data2 = json.loads(result2.content[0].text)

            assert data2 is not None
            assert "version_2" in data2["content"], (
                f"Should see version_2 after cache invalidation. Got: {data2['content']}"
            )

    @pytest.mark.asyncio
    async def test_external_graph_cache_invalidation(self, tmp_path: Path):
        """
        Purpose: Proves cache invalidation works for external graphs.
        Quality Contribution: External library updates are visible.
        Acceptance Criteria: Named graph sees updated content.

        Task: T015
        """
        from fastmcp.client import Client

        from fs2.config.objects import GraphConfig, OtherGraph, OtherGraphsConfig, ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.mcp import dependencies
        from fs2.mcp.server import mcp

        # Create default and external graph files
        default_path = tmp_path / "default.pickle"
        external_path = tmp_path / "external.pickle"

        create_graph_pickle(
            default_path,
            [("file:src/main.py", "main.py", "file", "# Main")],
        )
        create_graph_pickle(
            external_path,
            [
                (
                    "class:lib/helper.py:HelperV1",
                    "HelperV1",
                    "class",
                    "class HelperV1: pass",
                ),
            ],
        )

        # Config with external graph
        config = FakeConfigurationService(
            ScanConfig(),
            GraphConfig(graph_path=str(default_path)),
            OtherGraphsConfig(
                graphs=[
                    OtherGraph(
                        name="external-lib",
                        path=str(external_path),
                        description="External library",
                    ),
                ]
            ),
        )

        dependencies.reset_services()
        dependencies.set_config(config)

        async with Client(mcp) as client:
            # First query - should see HelperV1
            result1 = await client.call_tool(
                "tree", {"pattern": ".", "graph_name": "external-lib", "format": "json"}
            )
            data1 = json.loads(result1.content[0].text)
            node_ids1 = [n["node_id"] for n in data1.get("tree", [])]

            assert any("HelperV1" in nid for nid in node_ids1), (
                f"First query should find HelperV1. Got: {node_ids1}"
            )

            # Wait to ensure mtime changes
            time.sleep(0.1)

            # Update external graph
            create_graph_pickle(
                external_path,
                [
                    (
                        "class:lib/helper.py:HelperV2",
                        "HelperV2",
                        "class",
                        "class HelperV2: pass",
                    ),
                ],
            )

            # Second query - should see HelperV2
            result2 = await client.call_tool(
                "tree", {"pattern": ".", "graph_name": "external-lib", "format": "json"}
            )
            data2 = json.loads(result2.content[0].text)
            node_ids2 = [n["node_id"] for n in data2.get("tree", [])]

            assert any("HelperV2" in nid for nid in node_ids2), (
                f"Second query should find HelperV2 after invalidation. Got: {node_ids2}"
            )
            assert not any("HelperV1" in nid for nid in node_ids2), (
                f"Second query should NOT find HelperV1. Got: {node_ids2}"
            )


class TestCachingActuallyWorks:
    """Verify that caching is actually being used (not just that invalidation works).

    These tests prove the cache is hit on subsequent requests when the file
    hasn't changed, by spying on GraphService._load_graph to count load calls.
    """

    @pytest.mark.asyncio
    async def test_multiple_queries_use_cache_not_disk(self, tmp_path: Path):
        """
        Purpose: Proves caching actually works (graph loaded once, not on every query).
        Quality Contribution: Performance - avoids unnecessary disk I/O.
        Acceptance Criteria: _load_graph called exactly once across multiple MCP queries.
        """
        from fastmcp.client import Client

        from fs2.config.objects import GraphConfig, OtherGraphsConfig, ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.mcp import dependencies
        from fs2.mcp.server import mcp

        # Create graph with test data
        graph_path = tmp_path / "graph.pickle"
        create_graph_pickle(
            graph_path,
            [
                ("file:src/app.py", "app.py", "file", "# App"),
                ("class:src/app.py:MyClass", "MyClass", "class", "class MyClass: pass"),
            ],
        )

        config = FakeConfigurationService(
            ScanConfig(),
            GraphConfig(graph_path=str(graph_path)),
            OtherGraphsConfig(graphs=[]),
        )

        dependencies.reset_services()
        dependencies.set_config(config)

        # Get the GraphService instance and wrap _load_graph to count calls
        service = dependencies.get_graph_service()
        original_load = service._load_graph
        load_call_count = 0

        def counting_load(name, path):
            nonlocal load_call_count
            load_call_count += 1
            return original_load(name, path)

        service._load_graph = counting_load

        async with Client(mcp) as client:
            # First query - should trigger load
            result1 = await client.call_tool(
                "tree", {"pattern": ".", "format": "json"}
            )
            data1 = json.loads(result1.content[0].text)
            assert data1["count"] > 0, "First query should return data"

            # Second query - should use cache (no additional load)
            result2 = await client.call_tool(
                "tree", {"pattern": ".", "format": "json"}
            )
            data2 = json.loads(result2.content[0].text)
            assert data2["count"] > 0, "Second query should return data"

            # Third query with different tool - should still use cache
            result3 = await client.call_tool(
                "get_node", {"node_id": "class:src/app.py:MyClass"}
            )
            data3 = json.loads(result3.content[0].text)
            assert data3 is not None, "Third query should return node"

            # Fourth query with search - should still use cache
            result4 = await client.call_tool(
                "search", {"pattern": "MyClass", "mode": "text"}
            )
            data4 = json.loads(result4.content[0].text)
            assert len(data4.get("results", [])) > 0, "Fourth query should find results"

        # Verify _load_graph was called exactly once (caching works!)
        assert load_call_count == 1, (
            f"Expected _load_graph to be called exactly 1 time (caching), "
            f"but it was called {load_call_count} times"
        )

    @pytest.mark.asyncio
    async def test_different_graphs_each_loaded_once(self, tmp_path: Path):
        """
        Purpose: Proves each graph is cached independently.
        Quality Contribution: Multi-graph caching works correctly.
        Acceptance Criteria: Each graph loaded exactly once regardless of query count.
        """
        from fastmcp.client import Client

        from fs2.config.objects import GraphConfig, OtherGraph, OtherGraphsConfig, ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.mcp import dependencies
        from fs2.mcp.server import mcp

        # Create two distinct graphs
        default_path = tmp_path / "default.pickle"
        lib_path = tmp_path / "lib.pickle"

        create_graph_pickle(
            default_path,
            [("file:src/main.py", "main.py", "file", "# Main app")],
        )
        create_graph_pickle(
            lib_path,
            [("file:lib/util.py", "util.py", "file", "# Utility lib")],
        )

        config = FakeConfigurationService(
            ScanConfig(),
            GraphConfig(graph_path=str(default_path)),
            OtherGraphsConfig(
                graphs=[
                    OtherGraph(
                        name="my-lib",
                        path=str(lib_path),
                        description="My library",
                    ),
                ]
            ),
        )

        dependencies.reset_services()
        dependencies.set_config(config)

        # Get the GraphService instance and wrap _load_graph to count calls
        service = dependencies.get_graph_service()
        original_load = service._load_graph
        load_call_count = 0

        def counting_load(name, path):
            nonlocal load_call_count
            load_call_count += 1
            return original_load(name, path)

        service._load_graph = counting_load

        async with Client(mcp) as client:
            # Query default graph twice
            await client.call_tool("tree", {"pattern": ".", "format": "json"})
            await client.call_tool("tree", {"pattern": ".", "format": "json"})

            # Query named graph twice
            await client.call_tool(
                "tree", {"pattern": ".", "graph_name": "my-lib", "format": "json"}
            )
            await client.call_tool(
                "tree", {"pattern": ".", "graph_name": "my-lib", "format": "json"}
            )

            # Back to default graph
            await client.call_tool("tree", {"pattern": ".", "format": "json"})

        # Each graph should be loaded exactly once (2 total)
        assert load_call_count == 2, (
            f"Expected _load_graph to be called exactly 2 times "
            f"(once per graph), but it was called {load_call_count} times"
        )
