"""Tests for SCIPTypeScriptAdapter.

Tests TypeScript-specific symbol-to-node-id mapping against both
synthetic data and the real fixture index.scip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fs2.core.adapters.scip_adapter_typescript import SCIPTypeScriptAdapter

FIXTURE_DIR = Path(__file__).parent.parent.parent.parent / "scripts" / "scip" / "fixtures" / "typescript"
FIXTURE_INDEX = FIXTURE_DIR / "index.scip"


@pytest.fixture
def adapter():
    return SCIPTypeScriptAdapter()


@pytest.fixture
def known_node_ids():
    """Simulate fs2 node_ids for the TypeScript fixture."""
    return {
        # model.ts
        "file:model.ts",
        "type:model.ts:Priority",
        "type:model.ts:Task",
        "callable:model.ts:createTask",
        "callable:model.ts:displayTask",
        # service.ts
        "file:service.ts",
        "class:service.ts:TaskService",
        "callable:service.ts:TaskService.addTask",
        "callable:service.ts:TaskService.completeTask",
        "callable:service.ts:TaskService.getPending",
        "callable:service.ts:TaskService.summary",
        # handler.ts
        "file:handler.ts",
        "callable:handler.ts:handleCreate",
        "callable:handler.ts:handleList",
    }


class TestSCIPTypeScriptAdapter:
    def test_language_name(self, adapter):
        assert adapter.language_name() == "typescript"

    def test_symbol_to_node_id_class(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-typescript npm . . `service.ts`/TaskService#",
            "service.ts",
            known_node_ids,
        )
        assert result == "class:service.ts:TaskService"

    def test_symbol_to_node_id_method(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-typescript npm . . `service.ts`/TaskService#addTask().",
            "service.ts",
            known_node_ids,
        )
        assert result == "callable:service.ts:TaskService.addTask"

    def test_symbol_to_node_id_function(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-typescript npm . . `model.ts`/createTask().",
            "model.ts",
            known_node_ids,
        )
        assert result == "callable:model.ts:createTask"

    def test_symbol_to_node_id_enum(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-typescript npm . . `model.ts`/Priority#",
            "model.ts",
            known_node_ids,
        )
        assert result == "type:model.ts:Priority"

    def test_unknown_returns_none(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-typescript npm . . `unknown.ts`/X#",
            "unknown.ts",
            known_node_ids,
        )
        assert result is None

    def test_local_returns_none(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "local 2",
            "model.ts",
            known_node_ids,
        )
        assert result is None

    def test_falls_back_to_file(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-typescript npm . . `model.ts`/SomethingWeird#",
            "model.ts",
            known_node_ids,
        )
        assert result == "file:model.ts"


class TestSCIPTypeScriptAdapterWithFixture:
    """Integration tests using the real TypeScript fixture index.scip."""

    @pytest.fixture(autouse=True)
    def _check_fixture(self):
        if not FIXTURE_INDEX.exists():
            pytest.skip("TypeScript index.scip fixture not generated")

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
        handler_to_service = any(
            "handler" in s and "service" in t for s, t in src_tgt_pairs
        )
        assert handler_to_service, f"Expected handler→service edge, got: {src_tgt_pairs}"

    def test_service_references_model(self, adapter, known_node_ids):
        edges = adapter.extract_cross_file_edges(str(FIXTURE_INDEX), known_node_ids)
        src_tgt_pairs = {(s, t) for s, t, _ in edges}
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
