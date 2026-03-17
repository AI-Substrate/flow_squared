"""Tests for SCIPGoAdapter.

Tests Go-specific symbol-to-node-id mapping against both
synthetic data and the real fixture index.scip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fs2.core.adapters.scip_adapter_go import SCIPGoAdapter

FIXTURE_DIR = Path(__file__).parent.parent.parent.parent / "scripts" / "scip" / "fixtures" / "go"
FIXTURE_INDEX = FIXTURE_DIR / "index.scip"


@pytest.fixture
def adapter():
    return SCIPGoAdapter()


@pytest.fixture
def known_node_ids():
    """Simulate fs2 node_ids for the Go fixture."""
    return {
        # model/model.go
        "file:model/model.go",
        "type:model/model.go:Priority",
        "class:model/model.go:Task",
        "callable:model/model.go:NewTask",
        "callable:model/model.go:Task.MarkDone",
        "callable:model/model.go:Task.Display",
        "callable:model/model.go:Priority.String",
        # service/service.go
        "file:service/service.go",
        "class:service/service.go:TaskService",
        "callable:service/service.go:NewTaskService",
        "callable:service/service.go:TaskService.AddTask",
        "callable:service/service.go:TaskService.CompleteTask",
        "callable:service/service.go:TaskService.GetPending",
        "callable:service/service.go:TaskService.Summary",
        # main.go
        "file:main.go",
        "callable:main.go:HandleCreate",
        "callable:main.go:HandleList",
        "callable:main.go:main",
    }


class TestSCIPGoAdapter:
    def test_language_name(self, adapter):
        assert adapter.language_name() == "go"

    def test_symbol_to_node_id_struct(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-go gomod example.com/taskapp hash `example.com/taskapp/model`/Task#",
            "model/model.go",
            known_node_ids,
        )
        assert result == "class:model/model.go:Task"

    def test_symbol_to_node_id_method(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-go gomod example.com/taskapp hash `example.com/taskapp/service`/TaskService#AddTask().",
            "service/service.go",
            known_node_ids,
        )
        assert result == "callable:service/service.go:TaskService.AddTask"

    def test_symbol_to_node_id_function(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-go gomod example.com/taskapp hash `example.com/taskapp/model`/NewTask().",
            "model/model.go",
            known_node_ids,
        )
        assert result == "callable:model/model.go:NewTask"

    def test_symbol_to_node_id_top_level_function(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-go gomod example.com/taskapp hash `example.com/taskapp`/HandleCreate().",
            "main.go",
            known_node_ids,
        )
        assert result == "callable:main.go:HandleCreate"

    def test_symbol_to_node_id_type(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-go gomod example.com/taskapp hash `example.com/taskapp/model`/Priority#",
            "model/model.go",
            known_node_ids,
        )
        assert result == "type:model/model.go:Priority"

    def test_unknown_returns_none(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-go gomod example.com/taskapp hash `example.com/taskapp`/Unknown#",
            "unknown.go",
            known_node_ids,
        )
        assert result is None

    def test_stdlib_not_matched(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-go gomod github.com/golang/go/src go1.22 fmt/Printf().",
            "main.go",
            known_node_ids,
        )
        # fmt.Printf is not in our known_node_ids, so falls back to file
        assert result == "file:main.go"

    def test_local_returns_none(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id("local 5", "main.go", known_node_ids)
        assert result is None


class TestSCIPGoAdapterWithFixture:
    """Integration tests using the real Go fixture index.scip."""

    @pytest.fixture(autouse=True)
    def _check_fixture(self):
        if not FIXTURE_INDEX.exists():
            pytest.skip("Go index.scip fixture not generated")

    def test_extracts_cross_file_edges(self, adapter, known_node_ids):
        edges = adapter.extract_cross_file_edges(str(FIXTURE_INDEX), known_node_ids)
        assert len(edges) > 0

    def test_edge_format(self, adapter, known_node_ids):
        edges = adapter.extract_cross_file_edges(str(FIXTURE_INDEX), known_node_ids)
        for src, tgt, data in edges:
            assert isinstance(src, str)
            assert isinstance(tgt, str)
            assert data == {"edge_type": "references"}

    def test_main_references_service(self, adapter, known_node_ids):
        edges = adapter.extract_cross_file_edges(str(FIXTURE_INDEX), known_node_ids)
        src_tgt_pairs = {(s, t) for s, t, _ in edges}
        main_to_service = any(
            "main" in s and "service" in t for s, t in src_tgt_pairs
        )
        assert main_to_service, f"Expected main→service edge, got: {src_tgt_pairs}"

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
