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
from fs2.core.services.report_service import ReportService, _serialize_node


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
        assert '"references"' in result.html
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
