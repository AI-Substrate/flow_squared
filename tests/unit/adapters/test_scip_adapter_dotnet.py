"""Tests for SCIPDotNetAdapter.

Tests C#-specific symbol-to-node-id mapping and document filtering
against both synthetic data and the real fixture index.scip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fs2.core.adapters import scip_pb2
from fs2.core.adapters.scip_adapter_dotnet import SCIPDotNetAdapter

FIXTURE_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "scripts"
    / "scip"
    / "fixtures"
    / "dotnet"
)
FIXTURE_INDEX = FIXTURE_DIR / "index.scip"


@pytest.fixture
def adapter():
    return SCIPDotNetAdapter()


@pytest.fixture
def known_node_ids():
    """Simulate fs2 node_ids for the C# fixture."""
    return {
        # Model.cs
        "file:Model.cs",
        "type:Model.cs:Priority",
        "class:Model.cs:TaskItem",
        "callable:Model.cs:TaskItem.MarkDone",
        "callable:Model.cs:TaskItem.Display",
        # Service.cs
        "file:Service.cs",
        "class:Service.cs:TaskService",
        "callable:Service.cs:TaskService.AddTask",
        "callable:Service.cs:TaskService.CompleteTask",
        "callable:Service.cs:TaskService.GetPending",
        "callable:Service.cs:TaskService.Summary",
        # Program.cs
        "file:Program.cs",
    }


class TestSCIPDotNetAdapter:
    def test_language_name(self, adapter):
        assert adapter.language_name() == "dotnet"

    def test_symbol_to_node_id_class(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-dotnet nuget . . TaskApp/TaskService#",
            "Service.cs",
            known_node_ids,
        )
        assert result == "class:Service.cs:TaskService"

    def test_symbol_to_node_id_method(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-dotnet nuget . . TaskApp/TaskService#AddTask().",
            "Service.cs",
            known_node_ids,
        )
        assert result == "callable:Service.cs:TaskService.AddTask"

    def test_symbol_to_node_id_enum(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-dotnet nuget . . TaskApp/Priority#",
            "Model.cs",
            known_node_ids,
        )
        assert result == "type:Model.cs:Priority"

    def test_namespace_skipped_in_matching(self, adapter, known_node_ids):
        """Namespace segments (TaskApp/) are correctly ignored."""
        result = adapter.symbol_to_node_id(
            "scip-dotnet nuget . . TaskApp/TaskItem#Display().",
            "Model.cs",
            known_node_ids,
        )
        assert result == "callable:Model.cs:TaskItem.Display"

    def test_unknown_returns_none(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-dotnet nuget . . SomeApp/Unknown#",
            "unknown.cs",
            known_node_ids,
        )
        assert result is None

    def test_falls_back_to_file(self, adapter, known_node_ids):
        result = adapter.symbol_to_node_id(
            "scip-dotnet nuget . . TaskApp/SomethingWeird#",
            "Model.cs",
            known_node_ids,
        )
        assert result == "file:Model.cs"


class TestSCIPDotNetAdapterDocumentFilter:
    def test_skips_obj_directory(self, adapter):
        doc = scip_pb2.Document()
        doc.relative_path = "obj/Debug/net8.0/TaskApp.GlobalUsings.g.cs"
        assert adapter.should_skip_document(doc) is True

    def test_skips_assembly_info(self, adapter):
        doc = scip_pb2.Document()
        doc.relative_path = "obj/Debug/net8.0/TaskApp.AssemblyInfo.cs"
        assert adapter.should_skip_document(doc) is True

    def test_keeps_source_files(self, adapter):
        doc = scip_pb2.Document()
        doc.relative_path = "Model.cs"
        assert adapter.should_skip_document(doc) is False

    def test_keeps_nested_source_files(self, adapter):
        doc = scip_pb2.Document()
        doc.relative_path = "src/Services/TaskService.cs"
        assert adapter.should_skip_document(doc) is False


class TestSCIPDotNetAdapterWithFixture:
    """Integration tests using the real C# fixture index.scip."""

    @pytest.fixture(autouse=True)
    def _check_fixture(self):
        if not FIXTURE_INDEX.exists():
            pytest.skip("C# index.scip fixture not generated")

    def test_extracts_cross_file_edges(self, adapter, known_node_ids):
        edges = adapter.extract_cross_file_edges(str(FIXTURE_INDEX), known_node_ids)
        assert len(edges) > 0

    def test_edge_format(self, adapter, known_node_ids):
        edges = adapter.extract_cross_file_edges(str(FIXTURE_INDEX), known_node_ids)
        for src, tgt, data in edges:
            assert isinstance(src, str)
            assert isinstance(tgt, str)
            assert data == {"edge_type": "references"}

    def test_program_references_service(self, adapter, known_node_ids):
        edges = adapter.extract_cross_file_edges(str(FIXTURE_INDEX), known_node_ids)
        src_tgt_pairs = {(s, t) for s, t, _ in edges}
        program_to_service = any(
            "Program" in s and "Service" in t for s, t in src_tgt_pairs
        )
        assert program_to_service, (
            f"Expected Program→Service edge, got: {src_tgt_pairs}"
        )

    def test_service_references_model(self, adapter, known_node_ids):
        edges = adapter.extract_cross_file_edges(str(FIXTURE_INDEX), known_node_ids)
        src_tgt_pairs = {(s, t) for s, t, _ in edges}
        service_to_model = any(
            "Service" in s and "Model" in t for s, t in src_tgt_pairs
        )
        assert service_to_model, f"Expected Service→Model edge, got: {src_tgt_pairs}"

    def test_no_self_references(self, adapter, known_node_ids):
        edges = adapter.extract_cross_file_edges(str(FIXTURE_INDEX), known_node_ids)
        for src, tgt, _ in edges:
            assert src != tgt, f"Self-reference found: {src}"

    def test_edges_are_deduplicated(self, adapter, known_node_ids):
        edges = adapter.extract_cross_file_edges(str(FIXTURE_INDEX), known_node_ids)
        pairs = [(s, t) for s, t, _ in edges]
        assert len(pairs) == len(set(pairs)), "Duplicate edges found"

    def test_generated_docs_filtered(self, adapter, known_node_ids):
        """Verify obj/ documents don't produce spurious edges."""
        edges = adapter.extract_cross_file_edges(str(FIXTURE_INDEX), known_node_ids)
        for src, tgt, _ in edges:
            assert "obj/" not in src, f"Edge from generated file: {src}"
            assert "obj/" not in tgt, f"Edge to generated file: {tgt}"
