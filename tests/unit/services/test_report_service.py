"""Tests for ReportService.

Validates graph extraction, safe serialization (no embedding leak),
metadata computation, and HTML rendering.
Uses FakeGraphStore per doctrine (fakes over mocks).
"""

import pytest

from fs2.config.objects import ReportsConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.models.code_node import CodeNode
from fs2.core.repos.graph_store_fake import FakeGraphStore
from fs2.core.services.report_service import (
    ReportService,
    _serialize_edge,
    _serialize_node,
)


def _make_node(
    node_id: str = "callable:src/a.py:foo",
    name: str = "foo",
    category: str = "callable",
    file_path: str = "src/a.py",
    content: str = "def foo(): pass",
) -> CodeNode:
    return CodeNode.create_file(file_path, "python", name, 0, 10, 1, 5, content)


@pytest.mark.unit
class TestNodeSerialization:
    """Proves safe node serialization (DYK-01)."""

    def test_excludes_content_field(self):
        """Proves content (source code) is excluded."""
        node = _make_node(content="def foo():\n    return 42\n")
        result = _serialize_node(node)
        assert "content" not in result

    def test_excludes_embedding_field(self):
        """Proves embedding vectors are excluded."""
        node = _make_node()
        result = _serialize_node(node)
        assert "embedding" not in result
        assert "smart_content_embedding" not in result
        assert "embedding_hash" not in result
        assert "content_hash" not in result

    def test_includes_whitelisted_fields(self):
        """Proves visualization fields are present."""
        node = _make_node()
        result = _serialize_node(node)
        assert "node_id" in result
        assert "name" in result
        assert "category" in result
        assert "file_path" in result
        assert "start_line" in result
        assert "end_line" in result
        assert "language" in result


@pytest.mark.unit
class TestNodePositionAndColor:
    """Proves node serialization includes layout positions and colors."""

    def _make_service(self, nodes=None, edges=None):
        from fs2.config.objects import ScanConfig

        config = FakeConfigurationService(ReportsConfig(), ScanConfig())
        store = FakeGraphStore(config)
        if nodes:
            for n in nodes:
                store.add_node(n)
        if edges:
            for src, tgt, data in edges:
                store.add_edge(src, tgt, **data)
        return ReportService(config=config, graph_store=store)

    def test_nodes_have_position_fields(self):
        """Every node gets x, y, size, color, label."""
        node = CodeNode.create_file("src/a.py", "python", "a.py", 0, 100, 1, 10, "# a")
        service = self._make_service(nodes=[node])
        result = service.generate_codebase_graph()
        import json
        data = json.loads(result.html.split("GRAPH_DATA = ")[1].split(";\n")[0])
        nd = data["nodes"][0]
        assert "x" in nd
        assert "y" in nd
        assert "size" in nd
        assert "color" in nd
        assert "label" in nd

    def test_callable_nodes_are_cyan(self):
        """Callable nodes get cyan color #67e8f9."""
        from fs2.core.services.report_service import _CATEGORY_COLORS
        assert _CATEGORY_COLORS["callable"] == "#67e8f9"

    def test_type_nodes_are_violet(self):
        """Type nodes get violet color #c4b5fd."""
        from fs2.core.services.report_service import _CATEGORY_COLORS
        assert _CATEGORY_COLORS["type"] == "#c4b5fd"

    def test_file_nodes_are_slate(self):
        """File nodes get slate color #94a3b8."""
        from fs2.core.services.report_service import _CATEGORY_COLORS
        assert _CATEGORY_COLORS["file"] == "#94a3b8"

    def test_excludes_smart_content_when_flag_false(self):
        """Proves --no-smart-content works."""
        node = _make_node()
        result = _serialize_node(node, include_smart_content=False)
        assert "smart_content" not in result

    def test_includes_smart_content_by_default(self):
        """Proves smart_content included when not excluded."""
        node = _make_node()
        result = _serialize_node(node, include_smart_content=True)
        assert "smart_content" in result


@pytest.mark.unit
class TestEdgeSerialization:
    """Proves edge serialization adds Sigma.js rendering hints."""

    def test_reference_edge_has_amber_color(self):
        result = _serialize_edge("a", "b", {"edge_type": "references"}, idx=0)
        assert result["color"] == "#f59e0b"
        assert result["hidden"] is False
        assert result["type"] == "arrow"
        assert result["id"] == "e-0"

    def test_containment_edge_is_hidden(self):
        result = _serialize_edge("a", "b", {}, idx=5)
        assert result["color"] == "#1e293b"
        assert result["hidden"] is True
        assert result["type"] == "arrow"
        assert result["id"] == "e-5"

    def test_edge_preserves_source_target(self):
        result = _serialize_edge("src_node", "tgt_node", {"edge_type": "references"}, idx=0)
        assert result["source"] == "src_node"
        assert result["target"] == "tgt_node"


@pytest.mark.unit
class TestReportService:
    """Proves ReportService generates valid HTML with correct data."""

    def _make_service(self, nodes=None, edges=None):
        """Create service with fake dependencies."""
        from fs2.config.objects import ScanConfig

        config = FakeConfigurationService(ReportsConfig(), ScanConfig())
        store = FakeGraphStore(config)
        if nodes:
            for n in nodes:
                store.add_node(n)
        if edges:
            for src, tgt, data in edges:
                store.add_edge(src, tgt, **data)
        return ReportService(config=config, graph_store=store)

    def test_generates_valid_html(self):
        """Proves output is valid HTML."""
        node = CodeNode.create_file("src/a.py", "python", "a.py", 0, 100, 1, 10, "# file")
        service = self._make_service(nodes=[node])
        result = service.generate_codebase_graph()
        assert result.html.startswith("<!DOCTYPE html>")
        assert "</html>" in result.html

    def test_metadata_contains_project_info(self):
        """Proves metadata has project name, version, counts."""
        node = CodeNode.create_file("src/a.py", "python", "a.py", 0, 100, 1, 10, "# file")
        service = self._make_service(nodes=[node])
        result = service.generate_codebase_graph()
        meta = result.metadata
        assert "project_name" in meta
        assert "fs2_version" in meta
        assert "generated_at" in meta
        assert meta["node_count"] == 1
        assert meta["reference_edge_count"] == 0

    def test_reference_edges_in_output(self):
        """Proves reference edges appear in graph data."""
        n1 = CodeNode.create_file("src/a.py", "python", "a.py", 0, 100, 1, 10, "# a")
        n2 = CodeNode.create_file("src/b.py", "python", "b.py", 0, 100, 1, 10, "# b")
        service = self._make_service(
            nodes=[n1, n2],
            edges=[(n1.node_id, n2.node_id, {"edge_type": "references"})],
        )
        result = service.generate_codebase_graph()
        # Reference edges have amber color
        assert '"#f59e0b"' in result.html
        meta = result.metadata
        assert meta["reference_edge_count"] == 1

    def test_empty_graph(self):
        """Proves empty graph produces valid report."""
        service = self._make_service()
        result = service.generate_codebase_graph()
        assert result.html.startswith("<!DOCTYPE html>")
        assert result.metadata["node_count"] == 0

    def test_no_content_in_html(self):
        """Proves source code content is NOT in the HTML (DYK-01)."""
        node = CodeNode.create_file(
            "src/a.py", "python", "a.py", 0, 100, 1, 10,
            "def secret_function():\n    password = 'hunter2'\n"
        )
        service = self._make_service(nodes=[node])
        result = service.generate_codebase_graph()
        assert "hunter2" not in result.html
        assert "secret_function" not in result.html  # content excluded


@pytest.mark.unit
class TestNodeClustering:
    """Proves node clustering above max_nodes threshold."""

    def _make_service_with_max(self, nodes, edges=None, max_nodes=100):
        """Create service with a specific max_nodes threshold for testing."""
        from fs2.config.objects import ScanConfig

        config = FakeConfigurationService(
            ReportsConfig(max_nodes=max_nodes),
            ScanConfig(),
        )
        store = FakeGraphStore(config)
        for n in nodes:
            store.add_node(n)
        if edges:
            for src, tgt, data in edges:
                store.add_edge(src, tgt, **data)
        return ReportService(config=config, graph_store=store)

    def test_no_clustering_below_threshold(self):
        """Under max_nodes: no clustering occurs."""
        nodes = [
            CodeNode.create_file("src/a.py", "python", "a.py", 0, 100, 1, 10, "# a"),
            CodeNode.create_file("src/b.py", "python", "b.py", 0, 100, 1, 10, "# b"),
        ]
        service = self._make_service_with_max(nodes, max_nodes=100)
        result = service.generate_codebase_graph()
        assert result.metadata["node_count"] == 2
        assert result.metadata["clustered"] is False

    def test_clustering_above_threshold(self):
        """Above max_nodes: callable nodes are clustered."""
        file_node = CodeNode.create_file(
            "src/a.py", "python", "a.py", 0, 10000, 1, 1000, "# file"
        )
        callable_nodes = [
            CodeNode.create_callable(
                "src/a.py", "python", "function",
                f"func_{i}", f"func_{i}",
                i * 10 + 1, i * 10 + 10, 0, 0, 0, 100,
                f"def func_{i}(): pass", f"def func_{i}()",
                parent_node_id="file:src/a.py",
            )
            for i in range(150)
        ]
        all_nodes = [file_node] + callable_nodes  # 151 total
        service = self._make_service_with_max(all_nodes, max_nodes=100)
        result = service.generate_codebase_graph()
        # Should have fewer nodes than original (151 → clustered)
        assert result.metadata["node_count"] < len(all_nodes)
        assert result.metadata["clustered"] is True

    def test_clustering_preserves_file_nodes(self):
        """File nodes are never clustered."""
        file_nodes = [
            CodeNode.create_file(f"src/{chr(97+i)}.py", "python", f"{chr(97+i)}.py", 0, 100, 1, 10, f"# {chr(97+i)}")
            for i in range(120)
        ]
        service = self._make_service_with_max(file_nodes, max_nodes=100)
        result = service.generate_codebase_graph()
        # File nodes don't have parent_node_id → never clustered
        assert result.metadata["node_count"] == 120
