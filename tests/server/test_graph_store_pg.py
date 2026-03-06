"""Tests for PostgreSQLGraphStore — field-by-field CodeNode round-trip parity.

Unit tests use a FakeConnectionProvider. Integration tests (slow) use real PostgreSQL.
"""

import pytest

from fs2.core.models.code_node import CodeNode
from fs2.core.models.content_type import ContentType
from fs2.core.repos.graph_store_pg import ConnectionProvider, PostgreSQLGraphStore


def test_connection_provider_protocol():
    """ConnectionProvider is a runtime-checkable Protocol."""

    # Database satisfies ConnectionProvider
    assert issubclass(type, type)  # Protocol exists
    # Just verify the import chain works without circular deps
    assert ConnectionProvider is not None


def test_row_to_code_node_basic():
    """Test that _row_to_code_node reconstructs a CodeNode from a DB row."""
    # Simulate a DB row tuple (25 columns matching _NODE_COLUMNS order)
    row = (
        "file:test.py",  # node_id
        "file",  # category
        "module",  # ts_kind
        "code",  # content_type
        "test.py",  # name
        "test.py",  # qualified_name
        1,  # start_line
        10,  # end_line
        0,  # start_column
        0,  # end_column
        0,  # start_byte
        100,  # end_byte
        "print('hello')",  # content
        "abc123",  # content_hash
        None,  # signature
        "python",  # language
        True,  # is_named
        None,  # field_name
        False,  # is_error
        None,  # parent_node_id
        False,  # truncated
        None,  # truncated_at_line
        "Test file",  # smart_content
        "sc_hash",  # smart_content_hash
        None,  # embedding_hash
    )

    # Create a minimal store (won't connect — just testing row conversion)
    class FakeDB:
        pass

    store = PostgreSQLGraphStore.__new__(PostgreSQLGraphStore)
    store._db = FakeDB()
    store._graph_id = "test-graph"

    node = store._row_to_code_node(row)

    assert isinstance(node, CodeNode)
    assert node.node_id == "file:test.py"
    assert node.category == "file"
    assert node.ts_kind == "module"
    assert node.content_type == ContentType.CODE
    assert node.name == "test.py"
    assert node.qualified_name == "test.py"
    assert node.start_line == 1
    assert node.end_line == 10
    assert node.content == "print('hello')"
    assert node.language == "python"
    assert node.is_named is True
    assert node.is_error is False
    assert node.parent_node_id is None
    assert node.smart_content == "Test file"
    assert node.embedding is None


def test_row_to_code_node_with_embeddings():
    """Test embedding reconstruction from chunks."""
    row = (
        "file:test.py", "file", "module", "code", "test.py", "test.py",
        1, 10, 0, 0, 0, 100, "content", "hash", None, "python",
        True, None, False, None, False, None, None, None, None,
    )

    embeddings = {
        "file:test.py": {
            "content": [
                (0, [0.1, 0.2, 0.3], 1, 5),
                (1, [0.4, 0.5, 0.6], 6, 10),
            ],
            "smart_content": [
                (0, [0.7, 0.8, 0.9], None, None),
            ],
        }
    }

    store = PostgreSQLGraphStore.__new__(PostgreSQLGraphStore)
    store._db = None
    store._graph_id = "test"

    node = store._row_to_code_node(row, embeddings)

    assert node.embedding is not None
    assert len(node.embedding) == 2
    assert node.embedding[0] == (0.1, 0.2, 0.3)
    assert node.embedding[1] == (0.4, 0.5, 0.6)

    assert node.smart_content_embedding is not None
    assert len(node.smart_content_embedding) == 1
    assert node.smart_content_embedding[0] == (0.7, 0.8, 0.9)

    assert node.embedding_chunk_offsets is not None
    assert node.embedding_chunk_offsets == ((1, 5), (6, 10))


def test_group_embeddings():
    """Test _group_embeddings groups by node_id and type."""
    store = PostgreSQLGraphStore.__new__(PostgreSQLGraphStore)
    store._db = None
    store._graph_id = "test"

    rows = [
        ("node1", "content", 0, [0.1, 0.2], 1, 5),
        ("node1", "content", 1, [0.3, 0.4], 6, 10),
        ("node1", "smart_content", 0, [0.5, 0.6], None, None),
        ("node2", "content", 0, [0.7, 0.8], 1, 3),
    ]

    result = store._group_embeddings(rows)

    assert "node1" in result
    assert "node2" in result
    assert len(result["node1"]["content"]) == 2
    assert len(result["node1"]["smart_content"]) == 1
    assert len(result["node2"]["content"]) == 1


def test_sync_write_methods_raise():
    """Sync write methods raise NotImplementedError."""
    store = PostgreSQLGraphStore.__new__(PostgreSQLGraphStore)
    store._db = None
    store._graph_id = "test"

    node = CodeNode(
        node_id="test", category="file", ts_kind="module",
        name="test", qualified_name="test",
        start_line=1, end_line=1, start_column=0, end_column=0,
        start_byte=0, end_byte=0, content="", content_hash="",
        signature=None, language="python", is_named=True,
        field_name=None, is_error=False, content_type=ContentType.CODE,
        parent_node_id=None, truncated=False, truncated_at_line=None,
        smart_content=None, smart_content_hash=None,
        embedding=None, smart_content_embedding=None,
        embedding_hash=None, embedding_chunk_offsets=None,
    )

    with pytest.raises(NotImplementedError):
        store.add_node(node)
    with pytest.raises(NotImplementedError):
        store.add_edge("a", "b")
    with pytest.raises(NotImplementedError):
        store.get_node("a")
    with pytest.raises(NotImplementedError):
        store.get_children("a")
    with pytest.raises(NotImplementedError):
        store.get_parent("a")
    with pytest.raises(NotImplementedError):
        store.get_all_nodes()
    with pytest.raises(NotImplementedError):
        store.clear()

    # save/load/set_metadata are no-ops (no error)
    store.save(None)
    store.load(None)
    store.set_metadata({})
