"""Tests for SCIPPythonAdapter.

Tests Python-specific symbol-to-node-id mapping against the real
cross_file_sample fixture (handler.py → service.py → model.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fs2.core.adapters.scip_adapter_python import SCIPPythonAdapter

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "cross_file_sample"
FIXTURE_INDEX = FIXTURE_DIR / "index.scip"


@pytest.fixture
def adapter():
    return SCIPPythonAdapter()


@pytest.fixture
def known_node_ids():
    """Simulate fs2 node_ids for the cross_file_sample fixture."""
    return {
        # model.py
        "file:model.py",
        "class:model.py:Item",
        "callable:model.py:Item.__init__",
        "callable:model.py:Item.display",
        # service.py
        "file:service.py",
        "class:service.py:ItemService",
        "callable:service.py:ItemService.__init__",
        "callable:service.py:ItemService.create_item",
        "callable:service.py:ItemService.format_item",
        # handler.py
        "file:handler.py",
        "callable:handler.py:handle_request",
    }


class TestSCIPPythonAdapter:
    def test_language_name(self, adapter):
        assert adapter.language_name() == "python"

    def test_symbol_to_node_id_class(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-python python test 0.1 `test.model`/Item#",
            "model.py",
            known_node_ids,
        )
        assert result == "class:model.py:Item"

    def test_symbol_to_node_id_method(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-python python test 0.1 `test.service`/ItemService#create_item().",
            "service.py",
            known_node_ids,
        )
        assert result == "callable:service.py:ItemService.create_item"

    def test_symbol_to_node_id_function(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-python python test 0.1 `test.handler`/handle_request().",
            "handler.py",
            known_node_ids,
        )
        assert result == "callable:handler.py:handle_request"

    def test_symbol_to_node_id_unknown_returns_none(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-python python test 0.1 `test.unknown`/Unknown#",
            "unknown.py",
            known_node_ids,
        )
        assert result is None

    def test_symbol_to_node_id_local_returns_none(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "local 0",
            "model.py",
            known_node_ids,
        )
        assert result is None

    def test_symbol_to_node_id_falls_back_to_file(self, adapter, known_node_ids):
        """When symbol name doesn't match any callable/class, fall back to file."""
        result = adapter.symbol_to_node_id(
            "scip-python python test 0.1 `test.model`/SomethingWeird#",
            "model.py",
            known_node_ids,
        )
        assert result == "file:model.py"


class TestSCIPPythonAdapterWithFixture:
    """Integration tests using the real cross_file_sample index.scip."""

    @pytest.fixture(autouse=True)
    def _check_fixture(self):
        if not FIXTURE_INDEX.exists():
            pytest.skip("index.scip fixture not generated — run scip-python first")

    def test_extracts_cross_file_edges(self, adapter, known_node_ids):
        edges = adapter.extract_cross_file_edges(str(FIXTURE_INDEX), known_node_ids)
        assert len(edges) > 0

    def test_edge_format(self, adapter, known_node_ids):
        edges = adapter.extract_cross_file_edges(str(FIXTURE_INDEX), known_node_ids)
        for src, tgt, data in edges:
            assert isinstance(src, str)
            assert isinstance(tgt, str)
            assert data == {"edge_type": "references"}

    def test_handler_references_service(self, adapter, known_node_ids):
        edges = adapter.extract_cross_file_edges(str(FIXTURE_INDEX), known_node_ids)
        src_tgt_pairs = {(s, t) for s, t, _ in edges}

        # handler.py should reference something in service.py
        handler_to_service = any(
            "handler" in s and "service" in t for s, t in src_tgt_pairs
        )
        assert handler_to_service, (
            f"Expected handler→service edge, got: {src_tgt_pairs}"
        )

    def test_service_references_model(self, adapter, known_node_ids):
        edges = adapter.extract_cross_file_edges(str(FIXTURE_INDEX), known_node_ids)
        src_tgt_pairs = {(s, t) for s, t, _ in edges}

        # service.py should reference something in model.py
        service_to_model = any(
            "service" in s and "model" in t for s, t in src_tgt_pairs
        )
        assert service_to_model, f"Expected service→model edge, got: {src_tgt_pairs}"

    def test_no_self_references(self, adapter, known_node_ids):
        edges = adapter.extract_cross_file_edges(str(FIXTURE_INDEX), known_node_ids)
        for src, tgt, _ in edges:
            assert src != tgt, f"Self-reference found: {src}"

    def test_edges_are_deduplicated(self, adapter, known_node_ids):
        edges = adapter.extract_cross_file_edges(str(FIXTURE_INDEX), known_node_ids)
        pairs = [(s, t) for s, t, _ in edges]
        assert len(pairs) == len(set(pairs)), "Duplicate edges found"
