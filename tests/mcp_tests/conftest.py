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
    # DYK#2: Added embedding support for search tests
    embedding: tuple[tuple[float, ...], ...] | None = None,
    smart_content: str | None = None,
    smart_content_embedding: tuple[tuple[float, ...], ...] | None = None,
) -> CodeNode:
    """Helper to create CodeNode with minimal required fields.

    Fills in defaults for optional fields to simplify test fixture creation.

    Per DYK#2: Extended with embedding, smart_content, and smart_content_embedding
    parameters to support semantic search testing.

    Args:
        node_id: Unique node identifier.
        category: Node category (file, class, callable, etc.).
        name: Node name.
        content: Node content (source code).
        start_line: Start line in source file.
        end_line: End line in source file.
        signature: Optional function/method signature.
        language: Programming language.
        parent_node_id: Optional parent node ID.
        embedding: Embedding vectors as tuple of tuples (multi-chunk).
        smart_content: AI-generated summary.
        smart_content_embedding: Embedding for smart_content.

    Returns:
        CodeNode instance.
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
        embedding=embedding,
        smart_content=smart_content,
        smart_content_embedding=smart_content_embedding,
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


# =============================================================================
# Search Tool Fixtures (Phase 4)
# =============================================================================


@pytest.fixture
def search_test_graph_store(tmp_path: Path) -> tuple[FakeGraphStore, FakeConfigurationService]:
    """FakeGraphStore with nodes for search tests.

    Creates a graph with varied content for testing search modes:
    - Text mode: Nodes with searchable content
    - Regex mode: Nodes with pattern-matchable content
    - Filter tests: Nodes in different paths (auth, calc, test)

    Per DYK#3: Focus on MCP-level concerns, not search logic.

    Args:
        tmp_path: Pytest's temporary directory fixture.

    Returns:
        Tuple of (FakeGraphStore, FakeConfigurationService).
    """
    # Create graph file for TreeService compatibility
    graph_path = tmp_path / "graph.pickle"
    graph_path.touch()

    config = FakeConfigurationService(
        ScanConfig(),
        GraphConfig(graph_path=str(graph_path)),
    )

    nodes = [
        make_code_node(
            node_id="callable:src/auth/login.py:authenticate",
            category="callable",
            name="authenticate",
            content="def authenticate(user, password):\n    return verify(user, password)",
            start_line=1,
            end_line=5,
            signature="def authenticate(user: str, password: str) -> bool",
            smart_content="Authenticates user with credentials",
        ),
        make_code_node(
            node_id="callable:src/auth/session.py:create_session",
            category="callable",
            name="create_session",
            content="def create_session(user_id):\n    return Session(user_id)",
            start_line=1,
            end_line=5,
            signature="def create_session(user_id: int) -> Session",
            smart_content="Creates a new session for authenticated user",
        ),
        make_code_node(
            node_id="callable:src/calc/math.py:calculate",
            category="callable",
            name="calculate",
            content="def calculate(x, y):\n    return x + y",
            start_line=1,
            end_line=5,
            signature="def calculate(x: int, y: int) -> int",
            smart_content="Performs mathematical calculation",
        ),
        make_code_node(
            node_id="callable:tests/test_auth.py:test_login",
            category="callable",
            name="test_login",
            content="def test_login():\n    assert login() works",
            start_line=1,
            end_line=5,
            smart_content="Tests the login functionality",
        ),
    ]

    store = FakeGraphStore(config)
    store.set_nodes(nodes)

    return store, config


@pytest.fixture
def search_semantic_graph_store(
    tmp_path: Path,
    fake_embedding_adapter: FakeEmbeddingAdapter,
) -> tuple[FakeGraphStore, FakeConfigurationService, FakeEmbeddingAdapter]:
    """FakeGraphStore with nodes containing embeddings for semantic search tests.

    Creates nodes with pre-computed embeddings to test semantic search mode
    without requiring real embedding API calls.

    Per DYK#2: Embeddings are tuple[tuple[float, ...], ...] (multi-chunk).

    Args:
        tmp_path: Pytest's temporary directory fixture.
        fake_embedding_adapter: FakeEmbeddingAdapter fixture.

    Returns:
        Tuple of (FakeGraphStore, FakeConfigurationService, FakeEmbeddingAdapter).
    """
    # Create graph file for TreeService compatibility
    graph_path = tmp_path / "graph.pickle"
    graph_path.touch()

    config = FakeConfigurationService(
        ScanConfig(),
        GraphConfig(graph_path=str(graph_path)),
    )

    # Embeddings: tuple of tuples (multi-chunk format)
    # Similar to "authentication" query
    auth_embedding = ((0.9, 0.1, 0.05, 0.02),)
    # Different from "authentication" query
    calc_embedding = ((0.1, 0.1, 0.9, 0.8),)

    nodes = [
        make_code_node(
            node_id="callable:src/auth/login.py:authenticate",
            category="callable",
            name="authenticate",
            content="def authenticate(user, password):\n    return verify(user, password)",
            start_line=1,
            end_line=5,
            signature="def authenticate(user: str, password: str) -> bool",
            smart_content="Authenticates user with credentials",
            embedding=auth_embedding,
            smart_content_embedding=auth_embedding,
        ),
        make_code_node(
            node_id="callable:src/calc/math.py:calculate",
            category="callable",
            name="calculate",
            content="def calculate(x, y):\n    return x + y",
            start_line=1,
            end_line=5,
            signature="def calculate(x: int, y: int) -> int",
            smart_content="Performs mathematical calculation",
            embedding=calc_embedding,
            smart_content_embedding=calc_embedding,
        ),
    ]

    store = FakeGraphStore(config)
    store.set_nodes(nodes)

    # Configure fake adapter to return embedding similar to auth nodes
    fake_embedding_adapter.set_response([0.9, 0.1, 0.05, 0.02])

    return store, config, fake_embedding_adapter


@pytest.fixture
async def search_mcp_client(
    search_test_graph_store: tuple[FakeGraphStore, FakeConfigurationService],
    fake_embedding_adapter: FakeEmbeddingAdapter,
):
    """Async MCP client for search tool testing.

    Per DYK#1: Injects ALL dependencies including embedding_adapter.

    Args:
        search_test_graph_store: Graph store with search test nodes.
        fake_embedding_adapter: FakeEmbeddingAdapter for semantic search.

    Yields:
        Client connected to MCP server with all dependencies.
    """
    from fastmcp.client import Client

    from fs2.mcp import dependencies
    from fs2.mcp.server import mcp

    store, config = search_test_graph_store

    # Per DYK#1: Inject ALL dependencies
    dependencies.reset_services()
    dependencies.set_config(config)
    dependencies.set_graph_store(store)
    dependencies.set_embedding_adapter(fake_embedding_adapter)

    async with Client(mcp) as client:
        yield client


@pytest.fixture
async def mcp_client_no_graph():
    """MCP client with no graph store (for GraphNotFoundError tests).

    Used to test error handling when graph file doesn't exist.

    Yields:
        Client connected to MCP server with no graph.
    """
    from fastmcp.client import Client

    from fs2.mcp import dependencies
    from fs2.mcp.server import mcp

    # Reset to ensure clean state, don't set graph store
    dependencies.reset_services()
    # Config will auto-create, but graph file won't exist

    async with Client(mcp) as client:
        yield client
