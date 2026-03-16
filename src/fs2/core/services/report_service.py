"""ReportService — Generates HTML reports from the code graph.

Extracts nodes and edges from GraphStore, serializes them safely
(no embedding/hash leaks per DYK-01), renders via Jinja2 template,
and returns a self-contained HTML string.

Architecture:
    CLI → ReportService → GraphStore (read-only) + Jinja2 template
    Service receives ConfigurationService + GraphStore via constructor DI.
"""

from __future__ import annotations

import importlib.resources as importlib_resources
import json
import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jinja2

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService
    from fs2.core.models.code_node import CodeNode
    from fs2.core.repos.graph_store import GraphStore

logger = logging.getLogger(__name__)


# Fields to include in report JSON (DYK-01: whitelist, not blacklist)
_NODE_FIELDS = (
    "node_id",
    "name",
    "category",
    "file_path",
    "start_line",
    "end_line",
    "signature",
    "smart_content",
    "language",
    "parent_node_id",
)

# DYK-08: Python is the single source of truth for category→color map
_CATEGORY_COLORS: dict[str, str] = {
    "callable": "#22d3ee",   # cyan 400 — bright on dark
    "type": "#a78bfa",       # violet 400
    "file": "#60a5fa",       # blue 400
    "section": "#818cf8",    # indigo 400
    "folder": "#94a3b8",     # slate 400
    "block": "#34d399",      # emerald 400
    "statement": "#fb7185",  # rose 400
    "expression": "#fb923c", # orange 400
    "definition": "#a3e635", # lime 400
    "other": "#9ca3af",      # gray 400
}


@dataclass(frozen=True)
class ReportResult:
    """Output of report generation."""

    html: str
    metadata: dict[str, Any]


def _serialize_node(node: CodeNode, include_smart_content: bool = True) -> dict[str, Any]:
    """Serialize a CodeNode to a report-safe dict.

    Whitelists only visualization-relevant fields.
    Never includes content, embedding, or hash fields.
    """
    result: dict[str, Any] = {}
    for f in _NODE_FIELDS:
        if f == "smart_content" and not include_smart_content:
            continue
        result[f] = getattr(node, f, None)
    return result


def _serialize_edge(
    source: str, target: str, edge_data: dict[str, Any], idx: int = 0
) -> dict[str, Any]:
    """Serialize a graph edge to a report-safe dict.

    Adds Sigma.js rendering hints:
    - id: unique edge identifier for Graphology
    - color: amber for references, dark for containment
    - type: "arrow" for all edges (DYK-07: straight arrows in Phase 2)
    - hidden: True for containment edges (not shown by default)
    """
    edge_type = edge_data.get("edge_type", "containment")
    is_reference = edge_type == "references"
    return {
        "id": f"e-{idx}",
        "source": source,
        "target": target,
        "type": "arrow",
        "color": "#f59e0b" if is_reference else "#1e293b",
        "hidden": not is_reference,
    }


class ReportService:
    """Generates HTML reports from the code graph.

    Follows TreeService DI pattern: receives ConfigurationService
    and GraphStore in constructor. Service extracts graph data,
    serializes safely, and renders HTML via Jinja2 template.
    """

    def __init__(
        self,
        config: ConfigurationService,
        graph_store: GraphStore,
    ):
        self._config = config
        self._graph_store = graph_store

    def generate_codebase_graph(
        self,
        include_smart_content: bool = True,
        graph_path: Path | None = None,
    ) -> ReportResult:
        """Generate a codebase graph HTML report.

        Args:
            include_smart_content: Include smart_content in node data.
            graph_path: Path to graph file (for metadata display).

        Returns:
            ReportResult with HTML string and metadata dict.
        """
        # Extract all nodes and edges
        nodes = self._graph_store.get_all_nodes()
        all_edges = self._graph_store.get_all_edges()

        # Get max_nodes from config
        max_nodes = self._get_max_nodes()

        # Cluster if over threshold
        clustered = False
        if len(nodes) > max_nodes:
            nodes, all_edges = self._cluster_nodes(nodes, all_edges, max_nodes)
            clustered = True
            logger.warning(
                "Node count %d exceeds max_nodes %d — clustered to %d nodes",
                len(self._graph_store.get_all_nodes()),
                max_nodes,
                len(nodes),
            )

        # Separate containment and reference edges
        containment_edges = []
        reference_edges = []
        for source, target, data in all_edges:
            if data.get("edge_type") == "references":
                reference_edges.append((source, target, data))
            else:
                containment_edges.append((source, target, data))

        # Serialize nodes (DYK-01: whitelist fields only)
        node_dicts = [
            _serialize_node(n, include_smart_content=include_smart_content)
            for n in nodes
        ]

        # Compute force-directed layout using NetworkX spring_layout
        import networkx as nx

        G = nx.Graph()
        node_ids = {n.node_id for n in nodes}
        for n in nodes:
            G.add_node(n.node_id)
        # Add containment edges (parent-child) for structure
        for source, target, _data in containment_edges:
            if source in node_ids and target in node_ids:
                G.add_edge(source, target)
        # Add reference edges for connectivity
        for source, target, _data in reference_edges:
            if source in node_ids and target in node_ids:
                G.add_edge(source, target)

        positions = nx.spring_layout(
            G,
            k=2.0 / math.sqrt(max(len(nodes), 1)),  # optimal spacing
            iterations=80,
            seed=42,
            scale=2000,  # spread across large canvas
        )

        # Compute graph metrics (FX001-2: degree, depth, entry point detection)
        in_degree: dict[str, int] = {}
        out_degree: dict[str, int] = {}
        for source, target, data in all_edges:
            if data.get("edge_type") == "references":
                out_degree[source] = out_degree.get(source, 0) + 1
                in_degree[target] = in_degree.get(target, 0) + 1

        node_map = {n.node_id: n for n in nodes}

        def _compute_depth(node_id: str) -> int:
            depth = 0
            current = node_map.get(node_id)
            while current and current.parent_node_id:
                depth += 1
                current = node_map.get(current.parent_node_id)
                if depth > 20:
                    break  # safety
            return depth

        # Apply positions, sizes, colors, and metrics to node dicts
        for nd in node_dicts:
            nid = nd["node_id"]
            if nid in positions:
                pos = positions[nid]
                nd["x"] = round(float(pos[0]), 2)
                nd["y"] = round(float(pos[1]), 2)
            else:
                nd["x"] = 0.0
                nd["y"] = 0.0
            # Category color — Python is single source of truth
            nd["color"] = _CATEGORY_COLORS.get(nd.get("category", ""), "#6b7280")
            nd["label"] = nd.get("name", "")

            # Graph metrics
            nd_in = in_degree.get(nid, 0)
            nd_out = out_degree.get(nid, 0)
            nd["in_degree"] = nd_in
            nd["out_degree"] = nd_out
            nd["degree"] = nd_in + nd_out
            nd["depth"] = _compute_depth(nid)
            nd["is_entry_point"] = (
                nd_in == 0 and nd_out > 0 and nd.get("category") == "callable"
            )

            # Size based on connections — more connections = bigger node
            degree = nd["degree"]
            nd["size"] = round(
                max(3.0, min(18.0, 3.0 + math.log2(degree + 1) * 3.0)), 2
            )

        # Serialize edges (both types with rendering hints)
        edge_dicts = [
            _serialize_edge(s, t, d, idx=i)
            for i, (s, t, d) in enumerate(all_edges)
        ]

        # Build rich metadata (DYK-04)
        metadata = self._build_metadata(
            nodes=nodes,
            containment_count=len(containment_edges),
            reference_count=len(reference_edges),
            graph_path=graph_path,
            clustered=clustered,
        )

        # Build graph JSON
        graph_data = {
            "metadata": metadata,
            "nodes": node_dicts,
            "edges": edge_dicts,
        }

        # Render HTML
        graph_json = json.dumps(graph_data, default=str)
        metadata_json = json.dumps(metadata, default=str)
        html = self._render_template(graph_json, metadata_json)

        return ReportResult(html=html, metadata=metadata)

    def _get_max_nodes(self) -> int:
        """Get max_nodes threshold from config."""
        try:
            from fs2.config.objects import ReportsConfig

            reports_config = self._config.require(ReportsConfig)
            return reports_config.max_nodes
        except Exception:
            return 10000

    def _cluster_nodes(
        self,
        nodes: list[CodeNode],
        edges: list[tuple[str, str, dict[str, Any]]],
        max_nodes: int,
    ) -> tuple[list[CodeNode], list[tuple[str, str, dict[str, Any]]]]:
        """Cluster leaf callable nodes by file when count > max_nodes.

        Strategy: group callables sharing a parent file into a single
        summary node. Preserves files, types, and other non-callable nodes.
        Edges referencing clustered nodes are retargeted to summary nodes.
        """
        from fs2.core.models.code_node import CodeNode as CN

        # Separate: keep non-callable nodes, cluster callables by parent file
        keep_nodes: list[CodeNode] = []
        callables_by_file: dict[str, list[CodeNode]] = {}

        for node in nodes:
            if node.category == "callable" and node.parent_node_id:
                parent = node.parent_node_id
                callables_by_file.setdefault(parent, []).append(node)
            else:
                keep_nodes.append(node)

        # Build clustered node IDs map for edge retargeting
        clustered_ids: dict[str, str] = {}  # old_node_id → summary_node_id
        summary_nodes: list[CodeNode] = []

        for parent_id, callable_group in sorted(callables_by_file.items()):
            if len(keep_nodes) + len(summary_nodes) + len(callable_group) <= max_nodes:
                # Still under threshold — keep individual nodes
                keep_nodes.extend(callable_group)
            else:
                # Cluster this group into a summary node
                count = len(callable_group)
                first = callable_group[0]
                summary = CN.create_callable(
                    file_path=first.file_path or "",
                    language=first.language or "unknown",
                    ts_kind="cluster",
                    name=f"[{count} callables]",
                    qualified_name=f"_cluster_{count}",
                    start_line=min(n.start_line or 0 for n in callable_group),
                    end_line=max(n.end_line or 0 for n in callable_group),
                    start_column=0,
                    end_column=0,
                    start_byte=0,
                    end_byte=0,
                    content="",
                    signature=f"[{count} callables clustered]",
                    parent_node_id=parent_id,
                )
                summary_nodes.append(summary)
                for n in callable_group:
                    clustered_ids[n.node_id] = summary.node_id

        result_nodes = keep_nodes + summary_nodes

        # Retarget edges
        valid_ids = {n.node_id for n in result_nodes}
        result_edges: list[tuple[str, str, dict[str, Any]]] = []
        seen_edges: set[tuple[str, str]] = set()

        for source, target, data in edges:
            new_src = clustered_ids.get(source, source)
            new_tgt = clustered_ids.get(target, target)
            # Only keep edges where both endpoints exist
            if new_src in valid_ids and new_tgt in valid_ids:
                key = (new_src, new_tgt)
                if key not in seen_edges:
                    seen_edges.add(key)
                    result_edges.append((new_src, new_tgt, data))

        return result_nodes, result_edges

    def _build_metadata(
        self,
        nodes: list[CodeNode],
        containment_count: int,
        reference_count: int,
        graph_path: Path | None = None,
        clustered: bool = False,
    ) -> dict[str, Any]:
        """Build rich report metadata beyond GraphStore.get_metadata()."""
        project_name = graph_path.parent.parent.name if graph_path else Path.cwd().name

        # fs2 version
        try:
            from importlib.metadata import version

            fs2_version = version("fs2")
        except Exception:
            fs2_version = "unknown"

        # Category breakdown
        categories: dict[str, int] = {}
        for node in nodes:
            categories[node.category] = categories.get(node.category, 0) + 1

        return {
            "project_name": project_name,
            "generated_at": datetime.now(UTC).isoformat(),
            "fs2_version": fs2_version,
            "node_count": len(nodes),
            "containment_edge_count": containment_count,
            "reference_edge_count": reference_count,
            "categories": categories,
            "clustered": clustered,
        }

    def _render_template(
        self, graph_json: str, metadata_json: str
    ) -> str:
        """Render the HTML template with graph data and all assets.

        DYK-03: Simple inline Jinja2, not full TemplateService.
        DYK-09: Uses **template_vars pattern for extensibility.
        """
        # Load all static assets for embedding
        template_vars = {
            "graph_json": graph_json,
            "metadata_json": metadata_json,
            "d3_js": self._load_static_asset("d3.v7.min.js"),
            "graph_viewer_js": self._load_static_asset("graph-viewer.js"),
            "graph_viewer_css": self._load_static_asset("graph-viewer.css"),
            "inter_font_b64": self._load_font_base64("inter-latin.woff2"),
            "jetbrains_mono_font_b64": self._load_font_base64("jetbrains-mono-latin.woff2"),
        }

        template_pkg = importlib_resources.files("fs2.core.templates.reports")
        template_text = (
            template_pkg.joinpath("codebase_graph.html.j2").read_text(encoding="utf-8")
        )

        template = jinja2.Template(template_text, undefined=jinja2.StrictUndefined)
        return template.render(**template_vars)

    @staticmethod
    def _load_static_asset(name: str) -> str:
        """Load a static asset from fs2.core.static.reports as a string."""
        pkg = importlib_resources.files("fs2.core.static.reports")
        return pkg.joinpath(name).read_text(encoding="utf-8")

    @staticmethod
    def _load_font_base64(name: str) -> str:
        """Load a font file as base64 for CSS @font-face embedding."""
        import base64

        pkg = importlib_resources.files("fs2.core.static.reports")
        font_bytes = pkg.joinpath(name).read_bytes()
        return base64.b64encode(font_bytes).decode("ascii")
