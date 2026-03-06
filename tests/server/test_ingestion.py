"""Tests for the ingestion pipeline — standalone, no FastAPI.

Tests the IngestionPipeline class in isolation.
"""

import pickle
from pathlib import Path

import networkx as nx
import pytest

from fs2.core.models.code_node import CodeNode
from fs2.core.models.content_type import ContentType
from fs2.core.repos.pickle_security import RestrictedUnpickler
from fs2.server.ingestion import (
    IngestionError,
    extract_edges,
    extract_graph_metadata,
    extract_nodes,
    load_pickle,
)


def make_test_graph(node_count: int = 3) -> tuple[dict, nx.DiGraph]:
    """Create a minimal test graph pickle tuple."""
    graph = nx.DiGraph()
    for i in range(node_count):
        node = CodeNode(
            node_id=f"file:test_{i}.py",
            category="file",
            ts_kind="module",
            name=f"test_{i}.py",
            qualified_name=f"test_{i}.py",
            start_line=1,
            end_line=10 + i,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=100 + i,
            content=f"# test file {i}\nprint('hello')",
            content_hash=f"hash_{i}",
            signature=None,
            language="python",
            is_named=True,
            field_name=None,
            is_error=False,
            content_type=ContentType.CODE,
            parent_node_id=None if i == 0 else "file:test_0.py",
            truncated=False,
            truncated_at_line=None,
            smart_content=f"Test file {i} that prints hello",
            smart_content_hash=f"sc_hash_{i}",
            embedding=None,
            smart_content_embedding=None,
            embedding_hash=None,
            embedding_chunk_offsets=None,
        )
        graph.add_node(node.node_id, data=node)

    # Add edges: node 0 → node 1, node 0 → node 2
    for i in range(1, node_count):
        graph.add_edge("file:test_0.py", f"file:test_{i}.py")

    metadata = {
        "format_version": "1.0",
        "node_count": node_count,
        "edge_count": node_count - 1,
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 1024,
    }
    return metadata, graph


def write_pickle(metadata: dict, graph: nx.DiGraph, path: Path) -> None:
    """Write a test pickle file."""
    with open(path, "wb") as f:
        pickle.dump((metadata, graph), f)


class TestLoadPickle:
    def test_load_valid_pickle(self, tmp_path):
        metadata, graph = make_test_graph()
        path = tmp_path / "test.pickle"
        write_pickle(metadata, graph, path)

        loaded_meta, loaded_graph = load_pickle(path)
        assert loaded_meta["format_version"] == "1.0"
        assert loaded_graph.number_of_nodes() == 3

    def test_load_missing_file(self, tmp_path):
        with pytest.raises(IngestionError, match="not found"):
            load_pickle(tmp_path / "missing.pickle")

    def test_load_malicious_pickle(self, tmp_path):
        """RestrictedUnpickler blocks dangerous classes."""
        import os

        path = tmp_path / "evil.pickle"
        with open(path, "wb") as f:
            # Craft pickle that tries to use os.system
            pickle.dump(os.system, f)

        with pytest.raises(IngestionError, match="corrupted or malicious"):
            load_pickle(path)

    def test_load_invalid_format(self, tmp_path):
        path = tmp_path / "bad.pickle"
        with open(path, "wb") as f:
            pickle.dump("not a tuple", f)

        with pytest.raises(IngestionError, match="expected.*tuple"):
            load_pickle(path)


class TestExtractNodes:
    def test_extract_nodes_from_graph(self):
        _, graph = make_test_graph(3)
        nodes = extract_nodes(graph)
        assert len(nodes) == 3
        assert all(isinstance(n, CodeNode) for n in nodes)

    def test_extract_edges_from_graph(self):
        _, graph = make_test_graph(3)
        edges = extract_edges(graph)
        assert len(edges) == 2
        assert ("file:test_0.py", "file:test_1.py") in edges


class TestExtractMetadata:
    def test_extract_graph_metadata(self):
        meta = {
            "format_version": "1.0",
            "embedding_model": "text-embedding-3-small",
            "embedding_dimensions": 1024,
            "node_count": 100,
            "edge_count": 50,
            "chunk_params": {"max_tokens": 512},
        }
        result = extract_graph_metadata(meta)
        assert result["format_version"] == "1.0"
        assert result["embedding_model"] == "text-embedding-3-small"
        assert result["embedding_dimensions"] == 1024
        assert result["embedding_metadata"]["chunk_params"] == {"max_tokens": 512}

    def test_extract_metadata_missing_fields(self):
        result = extract_graph_metadata({})
        assert result["format_version"] is None
        assert result["embedding_model"] is None
        assert result["embedding_metadata"] is None


class TestRestrictedUnpickler:
    def test_allows_code_node(self, tmp_path):
        """RestrictedUnpickler allows CodeNode objects."""
        metadata, graph = make_test_graph(1)
        path = tmp_path / "test.pickle"
        write_pickle(metadata, graph, path)

        with open(path, "rb") as f:
            data = RestrictedUnpickler(f).load()
        assert isinstance(data, tuple)
        assert isinstance(data[1], nx.DiGraph)

    def test_blocks_os_module(self, tmp_path):
        """RestrictedUnpickler blocks os module."""
        import os

        path = tmp_path / "evil.pickle"
        with open(path, "wb") as f:
            pickle.dump(os.getcwd, f)

        with pytest.raises(Exception, match="Forbidden class"), open(path, "rb") as f:
            RestrictedUnpickler(f).load()
