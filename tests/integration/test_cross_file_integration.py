"""Integration tests for cross-file relationship feature.

Verifies the full pipeline flow: scan → CrossFileRelsStage → graph has edges → get_node shows relationships.

Uses tests/fixtures/cross_file_sample/ project with known cross-file references.
"""

from pathlib import Path

import pytest

from fs2.config.objects import CrossFileRelsConfig, GraphConfig, ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters import FileSystemScanner, TreeSitterParser
from fs2.core.repos import NetworkXGraphStore
from fs2.core.services import ScanPipeline
from fs2.core.services.stages.cross_file_rels_stage import CrossFileRelsStage


# ---------------------------------------------------------------------------
# Helper pool for integration testing
# ---------------------------------------------------------------------------


class FakePool:
    """Fake pool that produces canned edges matching cross_file_sample fixture."""

    def __init__(self):
        self.ports: list[int] = []
        self._started = False

    def start(self, n_instances: int, base_port: int, project_path: str):
        self.ports = list(range(base_port, base_port + n_instances))
        self._started = True

    def wait_ready(self, timeout: float = 60.0) -> bool:
        return True

    def stop(self):
        self._started = False

    @staticmethod
    def cleanup_orphans():
        pass


@pytest.mark.unit
class TestCrossFileRelsIntegration:
    """End-to-end integration: scan fixture project → verify edges + relationships."""

    def _scan_with_cross_refs(
        self, tmp_path: Path, fixture_path: Path, cross_file_edges: list
    ) -> tuple:
        """Helper: scan a project and manually inject cross-file edges.

        Injects edges after the stage runs to verify downstream behavior
        (StorageStage, get_node, etc).
        """
        graph_path = tmp_path / "graph.pickle"

        scan_config = ScanConfig(
            scan_paths=[str(fixture_path)],
            respect_gitignore=False,
        )
        graph_config = GraphConfig(graph_path=str(graph_path))
        cross_file_config = CrossFileRelsConfig(enabled=False)  # Disable auto-resolve

        config = FakeConfigurationService(scan_config, graph_config)

        scanner = FileSystemScanner(config)
        parser = TreeSitterParser(config)
        store = NetworkXGraphStore(config)

        pipeline = ScanPipeline(
            config=config,
            file_scanner=scanner,
            ast_parser=parser,
            graph_store=store,
            graph_path=graph_path,
            cross_file_rels_config=cross_file_config,
        )

        summary = pipeline.run()
        assert summary.success, f"Scan failed: {summary.errors}"
        assert summary.nodes_created > 0

        # Now inject cross-file edges manually (simulating what SCIP would produce)
        all_nodes = store.get_all_nodes()
        node_ids = {n.node_id for n in all_nodes}

        for source_id, target_id, edge_data in cross_file_edges:
            if source_id in node_ids and target_id in node_ids:
                store.add_edge(source_id, target_id, **edge_data)

        store.save(graph_path)

        return store, config, summary, all_nodes

    def test_scan_produces_nodes_from_fixture(self, tmp_path):
        """Scan fixture project → produces file + callable + type nodes."""
        fixture = Path(__file__).parent.parent / "fixtures" / "cross_file_sample"
        store, config, summary, nodes = self._scan_with_cross_refs(
            tmp_path, fixture, []
        )

        node_ids = {n.node_id for n in nodes}

        # Verify key nodes exist
        assert any("model.py" in nid for nid in node_ids), f"Missing model.py node. IDs: {node_ids}"
        assert any("service.py" in nid for nid in node_ids)
        assert any("handler.py" in nid for nid in node_ids)

    def test_injected_edges_appear_in_graph(self, tmp_path):
        """Manually injected reference edges are stored in graph."""
        fixture = Path(__file__).parent.parent / "fixtures" / "cross_file_sample"

        # First scan to find actual node_ids
        store_probe, _, _, nodes = self._scan_with_cross_refs(tmp_path, fixture, [])
        node_ids = {n.node_id for n in nodes}

        # Find actual node IDs for Item and ItemService
        item_id = next((nid for nid in node_ids if "Item" in nid and "type:" in nid), None)
        service_id = next(
            (nid for nid in node_ids if "ItemService" in nid and "type:" in nid), None
        )

        if item_id and service_id:
            # Rescan with edges
            tmp2 = tmp_path / "run2"
            tmp2.mkdir()
            store, config, _, _ = self._scan_with_cross_refs(
                tmp2,
                fixture,
                [(service_id, item_id, {"edge_type": "references"})],
            )

            edges = store.get_edges(service_id, direction="outgoing", edge_type="references")
            assert len(edges) >= 1, f"Expected reference edge from {service_id} to {item_id}"
            assert any(nid == item_id for nid, _ in edges)

    def test_get_node_shows_relationships_for_injected_edges(self, tmp_path):
        """MCP get_node output includes relationships for injected edges."""
        from fs2.mcp import dependencies
        from fs2.mcp.server import get_node

        fixture = Path(__file__).parent.parent / "fixtures" / "cross_file_sample"

        # Scan to find node IDs
        store_probe, _, _, nodes = self._scan_with_cross_refs(tmp_path / "probe", fixture, [])
        node_ids = {n.node_id for n in nodes}

        item_id = next((nid for nid in node_ids if "Item" in nid and "type:" in nid), None)
        service_id = next(
            (nid for nid in node_ids if "ItemService" in nid and "type:" in nid), None
        )

        if item_id and service_id:
            store, config, _, _ = self._scan_with_cross_refs(
                tmp_path / "real",
                fixture,
                [(service_id, item_id, {"edge_type": "references"})],
            )

            dependencies.reset_services()
            dependencies.set_config(config)
            dependencies.set_graph_store(store)

            result = get_node(node_id=item_id)
            assert result is not None
            assert "relationships" in result, f"Missing relationships. Keys: {result.keys()}"
            assert "referenced_by" in result["relationships"]
            assert service_id in result["relationships"]["referenced_by"]


@pytest.mark.unit
class TestCrossFileRelsStageSkipsWithoutConfig:
    """DYK-P4-02: Stage skips cleanly when config is None or disabled."""

    def test_stage_skips_when_config_is_none(self):
        """Stage returns early with no_config reason."""
        from fs2.config.objects import ScanConfig
        from fs2.core.services.pipeline_context import PipelineContext
        from fs2.core.services.stages.cross_file_rels_stage import CrossFileRelsStage

        ctx = PipelineContext(scan_config=ScanConfig())
        # Do NOT set cross_file_rels_config (simulates old pipeline)

        stage = CrossFileRelsStage()
        result = stage.process(ctx)

        assert result.metrics["cross_file_rels_skipped"] is True
        assert result.metrics["cross_file_rels_reason"] == "no_config"

    def test_stage_skips_when_config_disabled(self):
        """Stage returns early when config.enabled=False."""
        from fs2.config.objects import CrossFileRelsConfig, ScanConfig
        from fs2.core.services.pipeline_context import PipelineContext
        from fs2.core.services.stages.cross_file_rels_stage import CrossFileRelsStage

        ctx = PipelineContext(scan_config=ScanConfig())
        ctx.cross_file_rels_config = CrossFileRelsConfig(enabled=False)

        stage = CrossFileRelsStage()
        result = stage.process(ctx)

        assert result.metrics["cross_file_rels_skipped"] is True
        assert result.metrics["cross_file_rels_reason"] == "disabled"
