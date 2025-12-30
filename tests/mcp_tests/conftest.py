"""Pytest fixtures for MCP server tests.

Provides reusable fixtures using existing Fakes from fs2:
- FakeConfigurationService
- FakeGraphStore
- FakeEmbeddingAdapter

These fixtures enable deterministic testing without external dependencies.

Usage:
    def test_something(fake_config, fake_graph_store):
        # Test with controlled dependencies
        ...
"""

import pytest


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
        ),
        make_code_node(
            node_id="callable:src/calculator.py:Calculator.add",
            category="callable",
            name="add",
            content="def add(self, a, b):\n    return a + b",
            start_line=10,
            end_line=15,
            signature="def add(self, a: int, b: int) -> int",
        ),
    ])
    return store


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
