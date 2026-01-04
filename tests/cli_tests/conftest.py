"""Pytest fixtures for CLI tests.

Provides fixtures needed for CLI integration testing.
Re-uses patterns from mcp_tests conftest but as standalone fixtures.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


@pytest.fixture(autouse=True)
def reset_mcp_dependencies():
    """Reset MCP service singletons after each test.

    This autouse fixture ensures clean state between tests,
    preventing singleton leakage across test cases.
    """
    yield
    from fs2.mcp import dependencies

    dependencies.reset_services()


@pytest.fixture
def fake_config():
    """Create a FakeConfigurationService with standard test configs."""
    from fs2.config.objects import GraphConfig, ScanConfig
    from fs2.config.service import FakeConfigurationService

    return FakeConfigurationService(
        ScanConfig(),
        GraphConfig(graph_path=".fs2/graph.pickle"),
    )


@pytest.fixture
def tree_test_graph_store(tmp_path: Path, fake_config):
    """Create FakeGraphStore with temp file for TreeService compatibility."""
    from fs2.config.objects import GraphConfig, ScanConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.models.code_node import CodeNode
    from fs2.core.repos.graph_store_fake import FakeGraphStore
    from fs2.core.utils.hash import compute_content_hash

    # Create empty graph file to satisfy TreeService._ensure_loaded() check
    graph_path = tmp_path / "graph.pickle"
    graph_path.touch()

    # Config must point to the temp file location
    config = FakeConfigurationService(
        ScanConfig(),
        GraphConfig(graph_path=str(graph_path)),
    )

    def make_code_node(
        node_id: str,
        category: str,
        name: str | None,
        content: str,
        start_line: int = 1,
        end_line: int = 10,
        signature: str | None = None,
        language: str = "python",
        parent_node_id: str | None = None,
    ) -> CodeNode:
        return CodeNode(
            node_id=node_id,
            category=category,
            ts_kind="test_node",
            name=name,
            qualified_name=name or "anonymous",
            start_line=start_line,
            end_line=end_line,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=len(content),
            content=content,
            content_hash=compute_content_hash(content),
            signature=signature,
            language=language,
            is_named=True,
            field_name=None,
            parent_node_id=parent_node_id,
        )

    store = FakeGraphStore(config)
    # Pre-load test nodes
    store.set_nodes(
        [
            make_code_node(
                node_id="file:src/calculator.py",
                category="file",
                name="calculator.py",
                content="# Calculator module",
                start_line=1,
                end_line=50,
            ),
            make_code_node(
                node_id="class:src/calculator.py:Calculator",
                category="class",
                name="Calculator",
                content="class Calculator:\\n    pass",
                start_line=5,
                end_line=45,
                parent_node_id="file:src/calculator.py",
            ),
            make_code_node(
                node_id="callable:src/calculator.py:Calculator.add",
                category="callable",
                name="add",
                content="def add(self, a, b):\\n    return a + b",
                start_line=10,
                end_line=15,
                signature="def add(self, a: int, b: int) -> int",
                parent_node_id="class:src/calculator.py:Calculator",
            ),
        ]
    )

    # Set up parent→child edges for tree traversal
    store.add_edge("file:src/calculator.py", "class:src/calculator.py:Calculator")
    store.add_edge(
        "class:src/calculator.py:Calculator",
        "callable:src/calculator.py:Calculator.add",
    )

    return store, config


@pytest.fixture
async def mcp_client(tree_test_graph_store):
    """Async MCP client connected to server with injected fakes."""
    from fastmcp.client import Client

    from fs2.mcp import dependencies
    from fs2.mcp.server import mcp

    store, config = tree_test_graph_store

    # Inject fakes before creating client
    dependencies.reset_services()
    dependencies.set_config(config)
    dependencies.set_graph_store(store)

    # Use in-memory client via FastMCP's test utilities
    async with Client(mcp) as client:
        yield client

    # Cleanup handled by reset_mcp_dependencies autouse fixture
