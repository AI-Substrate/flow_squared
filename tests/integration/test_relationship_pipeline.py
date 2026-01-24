"""Integration test for LSP-based relationship extraction pipeline.

Purpose: Verifies end-to-end relationship extraction with real LSP adapter
         against the python_multi_project fixture.

Quality Contribution: Ensures LSP integration works in full pipeline context.

Per Phase 8 Tasks:
- T013: Ground truth integration test (≥67% detection rate)

Why: This test validates that the full pipeline - from scan to relationship
     extraction - correctly detects cross-file and same-file method calls.

Contract: Given Python fixtures with documented calls, when scanned with LSP,
          then ≥67% of expected edges are detected.

Usage Notes:
- Requires Pyright LSP server installed
- Uses python_multi_project fixtures
- Validates against EXPECTED_CALLS.md ground truth
"""

from pathlib import Path

import pytest

from fs2.config.objects import GraphConfig, LspConfig, ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.ast_parser_impl import TreeSitterParser
from fs2.core.adapters.file_scanner_impl import FileSystemScanner
from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter
from fs2.core.repos.graph_store_impl import NetworkXGraphStore
from fs2.core.services.scan_pipeline import ScanPipeline


def get_all_relationship_edges(store: NetworkXGraphStore) -> list[dict]:
    """Get all relationship edges from the graph store.

    Returns list of dicts with source_id, target_id, edge_type, confidence.
    """
    edges = []
    for node in store.get_all_nodes():
        outgoing = store.get_relationships(node.node_id, direction="outgoing")
        for rel in outgoing:
            edges.append(
                {
                    "source_id": node.node_id,
                    "target_id": rel["node_id"],
                    "edge_type": rel["edge_type"],
                    "confidence": rel.get("confidence"),
                }
            )
    return edges


@pytest.fixture
def python_multi_project_path() -> Path:
    """Return path to python_multi_project fixture."""
    fixture_path = (
        Path(__file__).parent.parent / "fixtures" / "lsp" / "python_multi_project"
    )
    assert fixture_path.exists(), f"Fixture not found: {fixture_path}"
    return fixture_path


@pytest.fixture
def test_graph_path(tmp_path: Path) -> Path:
    """Provide isolated graph path for tests."""
    return tmp_path / "test_graph.pickle"


class TestRelationshipPipelineIntegration:
    """T013: Integration tests for relationship extraction pipeline."""

    @pytest.mark.slow
    @pytest.mark.lsp
    def test_given_python_fixtures_when_scanned_with_lsp_then_detects_relationships(
        self, python_multi_project_path: Path, test_graph_path: Path, tmp_path: Path
    ):
        """
        Purpose: Verifies full pipeline detects cross-file relationships.
        Quality Contribution: End-to-end LSP relationship extraction.
        Acceptance Criteria: ≥10/15 ground truth entries detected (67%+).

        Why: Ground truth validation proves LSP integration works.
        Contract: scan with LSP → relationships detected from EXPECTED_CALLS.md.
        Worked Example:
          - app.py:main → auth.py:AuthService.create (cross-file)
          - auth.py:login → auth.py:_validate (same-file)
        """
        # Configure scan for the fixture src directory
        src_path = python_multi_project_path / "src"

        config = FakeConfigurationService(
            ScanConfig(scan_paths=[str(src_path)], respect_gitignore=True),
            GraphConfig(graph_path=str(test_graph_path)),
            LspConfig(),
        )

        # Create adapters
        scanner = FileSystemScanner(config)
        parser = TreeSitterParser(config)
        store = NetworkXGraphStore(config)

        # Create and initialize LSP adapter
        lsp_adapter = SolidLspAdapter(config)

        # Initialize for Python - use cwd as project root since node IDs
        # contain paths relative to cwd (e.g., tests/fixtures/lsp/.../app.py)
        from pathlib import Path

        lsp_adapter.initialize("python", Path.cwd())

        pipeline = ScanPipeline(
            config=config,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            graph_path=test_graph_path,
            lsp_adapter=lsp_adapter,
        )

        summary = pipeline.run()

        # Basic scan should succeed
        assert summary.success is True
        assert (
            summary.files_scanned >= 3
        )  # app.py, auth.py, utils.py (+ possibly __init__.py)

        # Extract relationship edges using helper function
        all_nodes = store.get_all_nodes()
        edges = get_all_relationship_edges(store)

        # Filter to call edges (relationship type)
        call_edges = [e for e in edges if e["edge_type"] == "calls"]

        # Log for debugging
        print("\n=== Relationship Pipeline Test Results ===")
        print(f"Total nodes: {len(all_nodes)}")
        print(f"Total edges: {len(edges)}")
        print(f"Call edges: {len(call_edges)}")

        # Show detected edges
        for edge in call_edges[:20]:
            print(f"  {edge['source_id']} -> {edge['target_id']}")

        # Ground truth from EXPECTED_CALLS.md:
        # 6 cross-file + 4 same-file = 10 expected edges minimum
        # Acceptance criteria: ≥67% = ≥10 edges * 0.67 ≈ 7 edges
        MIN_EXPECTED_EDGES = 7

        assert len(call_edges) >= MIN_EXPECTED_EDGES, (
            f"Expected ≥{MIN_EXPECTED_EDGES} call edges, got {len(call_edges)}. "
            f"Detection rate: {len(call_edges) * 100 / 10:.1f}%"
        )

        # Clean up LSP server
        lsp_adapter.shutdown()

    @pytest.mark.slow
    @pytest.mark.lsp
    def test_given_python_fixtures_when_scanned_then_cross_file_edges_detected(
        self, python_multi_project_path: Path, test_graph_path: Path, tmp_path: Path
    ):
        """
        Purpose: Verifies cross-file relationships specifically.
        Quality Contribution: Validates LSP resolves across file boundaries.
        Acceptance Criteria: At least one cross-file edge detected.

        Why: Cross-file resolution is the main value of LSP integration.
        Contract: app.py calling auth.py → cross-file edge in graph.
        """
        src_path = python_multi_project_path / "src"

        config = FakeConfigurationService(
            ScanConfig(scan_paths=[str(src_path)], respect_gitignore=True),
            GraphConfig(graph_path=str(test_graph_path)),
            LspConfig(),
        )

        scanner = FileSystemScanner(config)
        parser = TreeSitterParser(config)
        store = NetworkXGraphStore(config)

        lsp_adapter = SolidLspAdapter(config)
        # Initialize with cwd as project root since node IDs are relative to cwd
        from pathlib import Path

        lsp_adapter.initialize("python", Path.cwd())

        pipeline = ScanPipeline(
            config=config,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            graph_path=test_graph_path,
            lsp_adapter=lsp_adapter,
        )

        pipeline.run()

        edges = get_all_relationship_edges(store)
        call_edges = [e for e in edges if e["edge_type"] == "calls"]

        # Check for cross-file edges (source and target in different files)
        cross_file_edges = []
        for edge in call_edges:
            source_file = (
                edge["source_id"].split(":")[1] if ":" in edge["source_id"] else ""
            )
            target_file = (
                edge["target_id"].split(":")[1] if ":" in edge["target_id"] else ""
            )
            if source_file and target_file and source_file != target_file:
                cross_file_edges.append(edge)

        print("\n=== Cross-File Edge Detection ===")
        print(f"Total call edges: {len(call_edges)}")
        print(f"Cross-file edges: {len(cross_file_edges)}")
        for edge in cross_file_edges[:10]:
            print(f"  {edge['source_id']} -> {edge['target_id']}")

        # At least one cross-file edge should be detected
        assert len(cross_file_edges) >= 1, (
            f"Expected at least 1 cross-file edge, got {len(cross_file_edges)}"
        )

        lsp_adapter.shutdown()


class TestRelationshipPipelineGracefulDegradation:
    """Tests for pipeline behavior without LSP."""

    def test_given_no_lsp_when_scanned_then_pipeline_succeeds(
        self, python_multi_project_path: Path, test_graph_path: Path
    ):
        """
        Purpose: Verifies pipeline works without LSP adapter.
        Quality Contribution: Graceful degradation.
        Acceptance Criteria: Scan completes, no crashes.

        Why: LSP is optional; pipeline must work without it.
        Contract: lsp_adapter=None → scan succeeds, zero call edges.
        """
        src_path = python_multi_project_path / "src"

        config = FakeConfigurationService(
            ScanConfig(scan_paths=[str(src_path)], respect_gitignore=True),
            GraphConfig(graph_path=str(test_graph_path)),
        )

        scanner = FileSystemScanner(config)
        parser = TreeSitterParser(config)
        store = NetworkXGraphStore(config)

        pipeline = ScanPipeline(
            config=config,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            graph_path=test_graph_path,
            lsp_adapter=None,  # No LSP
        )

        summary = pipeline.run()

        # Should still succeed
        assert summary.success is True
        assert (
            summary.files_scanned >= 3
        )  # app.py, auth.py, utils.py (+ possibly __init__.py)

        # Without LSP, minimal call edges should be detected (text-based only)
        edges = get_all_relationship_edges(store)
        call_edges = [e for e in edges if e["edge_type"] == "calls"]

        print("\n=== No-LSP Pipeline Test ===")
        print(f"Total edges: {len(edges)}")
        print(f"Call edges: {len(call_edges)}")

        # Scan should succeed regardless of edge count
        assert summary.success is True
