"""Pytest fixtures for MCP server tests.

Provides reusable fixtures using existing Fakes from fs2:
- FakeConfigurationService
- FakeGraphStore
- FakeEmbeddingAdapter

These fixtures enable deterministic testing without external dependencies.

Phase 2 Addition (T000): Added mcp_client fixture for protocol-level testing.
CRITICAL: TreeService._ensure_loaded() checks Path.exists() on real filesystem
before calling load(). We use tmp_path.touch() to satisfy this check.

Usage:
    def test_something(fake_config, fake_graph_store):
        # Test with controlled dependencies
        ...

    async def test_mcp_tool(mcp_client):
        # Test via actual MCP protocol
        result = await mcp_client.call_tool("tree", {"pattern": "."})
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from mcp import ClientSession


@pytest.fixture(autouse=True)
def reset_mcp_dependencies():
    """Reset MCP service singletons after each test.

    This autouse fixture ensures clean state between tests,
    preventing singleton leakage across test cases.

    Per code review COR-002: Tests should not depend on execution order.
    """
    yield
    from fs2.mcp import dependencies

    dependencies.reset_services()


from fs2.config.objects import GraphConfig, ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter
from fs2.core.models.code_node import CodeNode
from fs2.core.repos.graph_store_fake import FakeGraphStore
from fs2.core.utils.hash import compute_content_hash


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
    """Helper to create CodeNode with minimal required fields.

    Fills in defaults for optional fields to simplify test fixture creation.
    """
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


@pytest.fixture
def fake_config() -> FakeConfigurationService:
    """Create a FakeConfigurationService with standard test configs.

    Returns:
        FakeConfigurationService with ScanConfig and GraphConfig set.
    """
    return FakeConfigurationService(
        ScanConfig(),
        GraphConfig(graph_path=".fs2/graph.pickle"),
    )


@pytest.fixture
def fake_graph_store(fake_config: FakeConfigurationService) -> FakeGraphStore:
    """Create a FakeGraphStore with the test configuration.

    Args:
        fake_config: FakeConfigurationService from fixture.

    Returns:
        FakeGraphStore ready for test use.
    """
    store = FakeGraphStore(fake_config)
    # Add some test nodes for use in tests
    store.set_nodes([
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
            content="class Calculator:\n    pass",
            start_line=5,
            end_line=45,
            parent_node_id="file:src/calculator.py",
        ),
        make_code_node(
            node_id="callable:src/calculator.py:Calculator.add",
            category="callable",
            name="add",
            content="def add(self, a, b):\n    return a + b",
            start_line=10,
            end_line=15,
            signature="def add(self, a: int, b: int) -> int",
            parent_node_id="class:src/calculator.py:Calculator",
        ),
    ])
    return store


@pytest.fixture
def tree_test_graph_store(tmp_path: Path) -> tuple[FakeGraphStore, FakeConfigurationService]:
    """Create FakeGraphStore with temp file for TreeService compatibility.

    CRITICAL: TreeService._ensure_loaded() checks Path.exists() before calling
    load(). We must create an empty file to satisfy this check. This is the
    proven pattern used in 13+ existing TreeService tests.

    The file can be empty (0 bytes) because FakeGraphStore.load() is a no-op
    that doesn't actually read the file - it just records the call.

    Args:
        tmp_path: Pytest's temporary directory fixture.

    Returns:
        Tuple of (FakeGraphStore, FakeConfigurationService) for injection.
    """
    # Create empty graph file to satisfy TreeService._ensure_loaded() check
    graph_path = tmp_path / "graph.pickle"
    graph_path.touch()  # 0-byte file is sufficient

    # Config must point to the temp file location
    config = FakeConfigurationService(
        ScanConfig(),
        GraphConfig(graph_path=str(graph_path)),
    )

    store = FakeGraphStore(config)
    # Pre-load test nodes (FakeGraphStore stores in-memory, ignores file)
    store.set_nodes([
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
            content="class Calculator:\n    pass",
            start_line=5,
            end_line=45,
            parent_node_id="file:src/calculator.py",
        ),
        make_code_node(
            node_id="callable:src/calculator.py:Calculator.add",
            category="callable",
            name="add",
            content="def add(self, a, b):\n    return a + b",
            start_line=10,
            end_line=15,
            signature="def add(self, a: int, b: int) -> int",
            parent_node_id="class:src/calculator.py:Calculator",
        ),
    ])

    # Set up parent→child edges for tree traversal
    store.add_edge("file:src/calculator.py", "class:src/calculator.py:Calculator")
    store.add_edge("class:src/calculator.py:Calculator", "callable:src/calculator.py:Calculator.add")

    return store, config


@pytest.fixture
async def mcp_client(tree_test_graph_store: tuple[FakeGraphStore, FakeConfigurationService]):
    """Async MCP client connected to server with injected fakes.

    CRITICAL: This fixture enables testing via actual MCP protocol,
    not just direct Python function calls. Tests using this fixture
    validate JSON serialization, schema generation, and protocol framing.

    Args:
        tree_test_graph_store: Tuple of (store, config) with temp graph file.

    Yields:
        ClientSession connected to the MCP server.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    from fs2.mcp import dependencies
    from fs2.mcp.server import mcp

    store, config = tree_test_graph_store

    # Inject fakes before creating client
    dependencies.reset_services()
    dependencies.set_config(config)
    dependencies.set_graph_store(store)

    # Use in-memory client via FastMCP's test utilities
    # FastMCP provides a Client class for testing
    from fastmcp.client import Client

    async with Client(mcp) as client:
        yield client

    # Cleanup handled by reset_mcp_dependencies autouse fixture


def parse_tool_response(result) -> dict | list:
    """Parse MCP tool call response to Python object.

    FastMCP returns results with content array containing TextContent objects.
    This helper extracts and parses the JSON text.

    Args:
        result: Tool call result from client.call_tool().

    Returns:
        Parsed JSON as dict or list.
    """
    return json.loads(result.content[0].text)


@pytest.fixture
def fake_embedding_adapter() -> FakeEmbeddingAdapter:
    """Create a FakeEmbeddingAdapter for testing.

    Returns:
        FakeEmbeddingAdapter ready for test use.
    """
    return FakeEmbeddingAdapter(dimensions=1024)


@pytest.fixture
def sample_node() -> CodeNode:
    """Create a sample CodeNode for testing.

    Returns:
        CodeNode with typical test data.
    """
    return make_code_node(
        node_id="callable:src/test.py:test_function",
        category="callable",
        name="test_function",
        content="def test_function():\n    pass",
        start_line=1,
        end_line=10,
        signature="def test_function() -> None",
    )
