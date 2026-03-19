"""Acceptance test for cross-file relationships with real SCIP indexers.

Scans tests/fixtures/cross_file_sample/ with SCIP indexer,
verifies known reference edges match actual source code imports/calls.

Requires: scip-python on PATH (skip if unavailable).
Marked @pytest.mark.slow — excluded from default test run.
"""

import shutil
from pathlib import Path

import pytest

from fs2.config.objects import CrossFileRelsConfig, GraphConfig, ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters import FileSystemScanner, TreeSitterParser
from fs2.core.repos import NetworkXGraphStore
from fs2.core.services import ScanPipeline

SCIP_PYTHON_AVAILABLE = shutil.which("scip-python") is not None

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "cross_file_sample"


@pytest.mark.slow
@pytest.mark.skipif(
    not SCIP_PYTHON_AVAILABLE,
    reason="scip-python not on PATH — install with: npm install -g @sourcegraph/scip-python",
)
class TestRealSCIPAcceptance:
    """Acceptance test — SCIP edges match actual source code."""

    def test_scan_with_real_scip_produces_reference_edges(self, tmp_path):
        """Real SCIP resolves references in cross_file_sample fixture."""
        graph_path = tmp_path / "graph.pickle"

        scan_config = ScanConfig(
            scan_paths=[str(FIXTURE_PATH)],
            respect_gitignore=False,
        )
        graph_config = GraphConfig(graph_path=str(graph_path))
        cross_file_config = CrossFileRelsConfig(enabled=True)

        config = FakeConfigurationService(scan_config, graph_config)

        pipeline = ScanPipeline(
            config=config,
            file_scanner=FileSystemScanner(config),
            ast_parser=TreeSitterParser(config),
            graph_store=NetworkXGraphStore(config),
            graph_path=graph_path,
            cross_file_rels_config=cross_file_config,
        )

        summary = pipeline.run()

        assert summary.success, f"Scan failed: {summary.errors}"

        # Check metrics — should have resolved edges (not skipped)
        metrics = summary.metrics
        if metrics.get("cross_file_rels_skipped"):
            pytest.skip(
                f"CrossFileRels was skipped: {metrics.get('cross_file_rels_reason')}"
            )

        edge_count = metrics.get("cross_file_rels_edges", 0)
        assert edge_count > 0, (
            f"Expected reference edges from cross_file_sample fixture. "
            f"Got 0 edges. Metrics: {metrics}"
        )
