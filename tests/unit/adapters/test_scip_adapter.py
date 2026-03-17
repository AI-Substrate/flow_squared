"""Tests for SCIPAdapterBase.

Tests the universal protobuf parsing, edge extraction, deduplication,
and filtering logic that all SCIP language adapters share.
"""

from __future__ import annotations

import pytest

from fs2.core.adapters import scip_pb2
from fs2.core.adapters.exceptions import (
    SCIPAdapterError,
    SCIPIndexError,
    SCIPMappingError,
)
from fs2.core.adapters.scip_adapter import SCIPAdapterBase
from fs2.core.adapters.scip_adapter_fake import SCIPFakeAdapter

# ── Exception hierarchy ───────────────────────────────────────────


class TestSCIPExceptions:
    def test_scip_adapter_error_inherits_adapter_error(self):
        from fs2.core.adapters.exceptions import AdapterError
        assert issubclass(SCIPAdapterError, AdapterError)

    def test_scip_index_error_inherits_scip_adapter_error(self):
        assert issubclass(SCIPIndexError, SCIPAdapterError)

    def test_scip_mapping_error_inherits_scip_adapter_error(self):
        assert issubclass(SCIPMappingError, SCIPAdapterError)


# ── ABC compliance ────────────────────────────────────────────────


class TestSCIPAdapterBaseABC:
    def test_cannot_instantiate_base(self):
        with pytest.raises(TypeError, match="abstract method"):
            SCIPAdapterBase()

    def test_fake_adapter_instantiates(self):
        adapter = SCIPFakeAdapter()
        assert adapter.language_name() == "fake"


# ── Protobuf loading ─────────────────────────────────────────────


class TestProtobufLoading:
    def test_load_missing_file_raises_scip_index_error(self, tmp_path):
        adapter = SCIPFakeAdapter()
        with pytest.raises(SCIPIndexError, match="not found"):
            adapter._load_index(tmp_path / "nonexistent.scip")

    def test_load_corrupted_file_raises_scip_index_error(self, tmp_path):
        bad_file = tmp_path / "bad.scip"
        bad_file.write_bytes(b"not a valid protobuf")
        adapter = SCIPFakeAdapter()
        with pytest.raises(SCIPIndexError, match="Failed to parse"):
            adapter._load_index(bad_file)

    def test_load_valid_empty_index(self, tmp_path):
        empty_index = scip_pb2.Index()
        index_file = tmp_path / "empty.scip"
        index_file.write_bytes(empty_index.SerializeToString())
        adapter = SCIPFakeAdapter()
        result = adapter._load_index(index_file)
        assert len(result.documents) == 0

    def test_load_index_with_documents(self, tmp_path):
        index = _build_simple_index()
        index_file = tmp_path / "test.scip"
        index_file.write_bytes(index.SerializeToString())
        adapter = SCIPFakeAdapter()
        result = adapter._load_index(index_file)
        assert len(result.documents) == 2


# ── Edge extraction ──────────────────────────────────────────────


class TestEdgeExtraction:
    def test_extracts_cross_file_edges(self):
        index = _build_simple_index()
        adapter = SCIPFakeAdapter()
        raw = adapter._extract_raw_edges(index)
        # b.py references a symbol defined in a.py
        assert len(raw) > 0
        ref_files = {e[0] for e in raw}
        def_files = {e[1] for e in raw}
        assert "b.py" in ref_files
        assert "a.py" in def_files

    def test_skips_local_symbols(self):
        index = scip_pb2.Index()
        doc = index.documents.add()
        doc.relative_path = "a.py"
        occ = doc.occurrences.add()
        occ.symbol = "local 0"
        occ.symbol_roles = 1  # Definition

        doc2 = index.documents.add()
        doc2.relative_path = "b.py"
        occ2 = doc2.occurrences.add()
        occ2.symbol = "local 0"
        occ2.symbol_roles = 0  # Reference

        adapter = SCIPFakeAdapter()
        raw = adapter._extract_raw_edges(index)
        assert len(raw) == 0

    def test_skips_same_file_references(self):
        index = scip_pb2.Index()
        doc = index.documents.add()
        doc.relative_path = "a.py"
        # Define and reference in same file
        occ_def = doc.occurrences.add()
        occ_def.symbol = "scip-python python pkg 0.1 `mod`/MyClass#"
        occ_def.symbol_roles = 1
        occ_ref = doc.occurrences.add()
        occ_ref.symbol = "scip-python python pkg 0.1 `mod`/MyClass#"
        occ_ref.symbol_roles = 0

        adapter = SCIPFakeAdapter()
        raw = adapter._extract_raw_edges(index)
        assert len(raw) == 0  # Same file, not cross-file

    def test_skips_empty_symbols(self):
        index = scip_pb2.Index()
        doc = index.documents.add()
        doc.relative_path = "a.py"
        occ = doc.occurrences.add()
        occ.symbol = ""
        occ.symbol_roles = 1

        adapter = SCIPFakeAdapter()
        raw = adapter._extract_raw_edges(index)
        assert len(raw) == 0


# ── Deduplication ─────────────────────────────────────────────────


class TestDeduplication:
    def test_removes_duplicate_edges(self):
        adapter = SCIPFakeAdapter()
        edges = [
            ("file:a.py", "callable:b.py:foo", {"edge_type": "references"}),
            ("file:a.py", "callable:b.py:foo", {"edge_type": "references"}),
            ("file:a.py", "callable:b.py:bar", {"edge_type": "references"}),
        ]
        result = adapter._deduplicate(edges)
        assert len(result) == 2

    def test_preserves_unique_edges(self):
        adapter = SCIPFakeAdapter()
        edges = [
            ("file:a.py", "callable:b.py:foo", {"edge_type": "references"}),
            ("file:b.py", "callable:a.py:bar", {"edge_type": "references"}),
        ]
        result = adapter._deduplicate(edges)
        assert len(result) == 2


# ── Symbol parsing ────────────────────────────────────────────────


class TestSymbolParsing:
    def test_parse_python_symbol(self):
        result = SCIPAdapterBase.parse_symbol(
            "scip-python python test-pkg 0.1.0 `test_pkg.module`/MyClass#method()."
        )
        assert result is not None
        assert result["scheme"] == "scip-python"
        assert result["manager"] == "python"
        assert result["package"] == "test-pkg"
        assert result["version"] == "0.1.0"
        assert "`test_pkg.module`/MyClass#method()." in result["descriptor"]

    def test_parse_local_symbol_returns_none(self):
        assert SCIPAdapterBase.parse_symbol("local 0") is None
        assert SCIPAdapterBase.parse_symbol("local 42") is None

    def test_parse_typescript_symbol(self):
        result = SCIPAdapterBase.parse_symbol(
            "scip-typescript npm . . `model.ts`/Task#title."
        )
        assert result is not None
        assert result["scheme"] == "scip-typescript"

    def test_extract_class_method_from_descriptor(self):
        parts = SCIPAdapterBase.extract_name_from_descriptor(
            "`pkg.module`/MyClass#my_method()."
        )
        assert parts == ["MyClass", "my_method"]

    def test_extract_class_only(self):
        parts = SCIPAdapterBase.extract_name_from_descriptor(
            "`pkg.module`/MyClass#"
        )
        assert parts == ["MyClass"]

    def test_extract_function(self):
        parts = SCIPAdapterBase.extract_name_from_descriptor(
            "`pkg.module`/my_function()."
        )
        assert parts == ["my_function"]

    def test_extract_empty_descriptor(self):
        parts = SCIPAdapterBase.extract_name_from_descriptor("")
        assert parts == []


# ── Fake adapter ──────────────────────────────────────────────────


class TestFakeAdapter:
    def test_set_edges_returns_configured(self):
        adapter = SCIPFakeAdapter()
        edges = [("a", "b", {"edge_type": "references"})]
        adapter.set_edges(edges)
        result = adapter.extract_cross_file_edges("unused", set())
        assert result == edges

    def test_call_history_tracked(self):
        adapter = SCIPFakeAdapter()
        adapter.extract_cross_file_edges("path.scip", {"a", "b"})
        assert len(adapter.call_history) == 1
        assert adapter.call_history[0]["method"] == "extract_cross_file_edges"
        assert adapter.call_history[0]["known_node_ids_count"] == 2

    def test_empty_by_default(self):
        adapter = SCIPFakeAdapter()
        result = adapter.extract_cross_file_edges("unused", set())
        assert result == []


# ── Edge format ───────────────────────────────────────────────────


class TestEdgeFormat:
    def test_edges_use_references_type(self):
        """Edges must use {"edge_type": "references"} matching Serena format."""
        index = _build_simple_index()
        adapter = SCIPFakeAdapter()
        known = {
            "callable:a.py:greet",
            "callable:b.py:main",
            "file:a.py",
            "file:b.py",
        }
        adapter.set_index(index)
        edges = adapter.extract_cross_file_edges("unused", known)
        for _src, _tgt, data in edges:
            assert data == {"edge_type": "references"}


# ── Helpers ───────────────────────────────────────────────────────


def _build_simple_index() -> scip_pb2.Index:
    """Build a minimal 2-document SCIP index with cross-file refs."""
    index = scip_pb2.Index()

    # a.py defines greet()
    doc_a = index.documents.add()
    doc_a.relative_path = "a.py"
    occ_def = doc_a.occurrences.add()
    occ_def.symbol = "scip-python python test 0.1 `test.a`/greet()."
    occ_def.symbol_roles = 1  # Definition

    # b.py references greet()
    doc_b = index.documents.add()
    doc_b.relative_path = "b.py"
    occ_ref = doc_b.occurrences.add()
    occ_ref.symbol = "scip-python python test 0.1 `test.a`/greet()."
    occ_ref.symbol_roles = 0  # Reference

    # b.py also defines main()
    occ_main = doc_b.occurrences.add()
    occ_main.symbol = "scip-python python test 0.1 `test.b`/main()."
    occ_main.symbol_roles = 1

    return index
