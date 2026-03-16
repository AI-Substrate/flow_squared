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

        # Compute hierarchical solar-system layout:
        # Suns (directories) → Planets (files) → Moons (callables/types)
        import networkx as nx

        node_map = {n.node_id: n for n in nodes}

        # --- Step 1: Derive directory hierarchy ---
        # Group file nodes by their parent directory
        dir_files: dict[str, list[str]] = {}  # dir_path → [file_node_id]
        file_children: dict[str, list[str]] = {}  # file_node_id → [child_node_ids]

        for n in nodes:
            if n.category == "file" and n.file_path:
                dir_path = str(Path(n.file_path).parent)
                dir_files.setdefault(dir_path, []).append(n.node_id)
            elif n.parent_node_id:
                file_children.setdefault(n.parent_node_id, []).append(n.node_id)

        # --- Step 2: Macro layout — position directories (suns) ---
        dir_graph = nx.Graph()
        dir_list = list(dir_files.keys())
        for d in dir_list:
            dir_graph.add_node(d)
        # Connect directories that have cross-dir reference edges
        for source, target, data in reference_edges:
            if data.get("edge_type") != "references":
                continue
            s_node = node_map.get(source)
            t_node = node_map.get(target)
            if not s_node or not t_node:
                continue
            s_file = s_node.file_path or ""
            t_file = t_node.file_path or ""
            s_dir = str(Path(s_file).parent) if s_file else ""
            t_dir = str(Path(t_file).parent) if t_file else ""
            if s_dir in dir_files and t_dir in dir_files and s_dir != t_dir:
                dir_graph.add_edge(s_dir, t_dir)

        # Estimate each system's radius for macro spacing
        dir_radius: dict[str, float] = {}
        for dir_path in dir_list:
            files = dir_files[dir_path]
            num_files = len(files)
            max_per_ring = max(6, int(math.sqrt(num_files) * 3))
            num_rings = max(1, math.ceil(num_files / max_per_ring))
            outer_ring = 120 + (num_rings - 1) * 100  # outermost ring
            max_moon = 0.0
            for fid in files:
                nc = len(file_children.get(fid, []))
                max_moon = max(max_moon, max(30, min(80, nc * 8)) if nc else 0)
            dir_radius[dir_path] = outer_ring + max_moon + 100

        # Scale macro layout generously
        avg_radius = sum(dir_radius.values()) / max(len(dir_radius), 1)
        num_dirs = max(len(dir_list), 1)
        macro_scale = max(10000, avg_radius * num_dirs * 0.8)

        dir_positions = nx.spring_layout(
            dir_graph,
            k=8.0 / math.sqrt(num_dirs),
            iterations=150,
            seed=42,
            scale=macro_scale,
        ) if dir_list else {}

        # --- Step 3: Position files (planets) in valence rings around dirs ---
        import random as _rng

        positions: dict[str, tuple[float, float]] = {}
        dir_centers: dict[str, tuple[float, float]] = {}
        dir_actual_radius: dict[str, float] = {}  # measured outer boundary

        for dir_path in dir_list:
            cx, cy = dir_positions.get(dir_path, (0.0, 0.0))
            dir_centers[dir_path] = (float(cx), float(cy))
            files = dir_files[dir_path]
            num_files = len(files)

            # Distribute across multiple valence rings (like electron shells)
            max_per_ring = max(6, int(math.sqrt(num_files) * 3))
            num_rings = max(1, math.ceil(num_files / max_per_ring))
            ring_base = 120  # innermost ring radius
            ring_gap = 100   # gap between rings

            rng = _rng.Random(hash(dir_path))  # deterministic per directory
            ring_assignments: list[tuple[int, float]] = []  # (ring_idx, angle)
            slots_per_ring = [0] * num_rings
            for i in range(num_files):
                ring_idx = i % num_rings
                slots_per_ring[ring_idx] += 1

            fi = 0
            for ring_idx in range(num_rings):
                ring_r = ring_base + ring_idx * ring_gap
                n_in_ring = slots_per_ring[ring_idx]
                for j in range(n_in_ring):
                    # Evenly space within ring + random jitter
                    base_angle = (2 * math.pi * j) / max(n_in_ring, 1)
                    jitter = rng.uniform(-0.3, 0.3)
                    angle = base_angle + jitter
                    r_jitter = rng.uniform(-20, 20)
                    r = ring_r + r_jitter
                    fid = files[fi]
                    fx = cx + math.cos(angle) * r
                    fy = cy + math.sin(angle) * r
                    positions[fid] = (round(fx, 2), round(fy, 2))
                    fi += 1

        # --- Step 4: Position callables/types (moons) around files ---
        for file_id, children in file_children.items():
            if file_id not in positions:
                continue
            fx, fy = positions[file_id]
            num_ch = len(children)
            moon_orbit = max(30, min(80, num_ch * 8))
            rng = _rng.Random(hash(file_id))
            for i, cid in enumerate(children):
                angle = (2 * math.pi * i) / max(num_ch, 1) + rng.uniform(-0.2, 0.2)
                r = moon_orbit + rng.uniform(-8, 8)
                mx = fx + math.cos(angle) * r
                my = fy + math.sin(angle) * r
                positions[cid] = (round(mx, 2), round(my, 2))

        # --- Step 5: Measure actual system radii and push apart overlapping ---
        for dir_path in dir_list:
            cx, cy = dir_centers[dir_path]
            max_r = 0.0
            for fid in dir_files[dir_path]:
                if fid not in positions:
                    continue
                fx, fy = positions[fid]
                dist = math.sqrt((fx - cx) ** 2 + (fy - cy) ** 2)
                # Include moon orbit of this file
                nc = len(file_children.get(fid, []))
                moon_r = max(30, min(80, nc * 8)) if nc else 0
                max_r = max(max_r, dist + moon_r)
            dir_actual_radius[dir_path] = max_r + 60  # padding

        # Push apart overlapping solar systems (iterative repulsion)
        dir_pos_list = [(d, list(dir_centers[d])) for d in dir_list]
        for _iteration in range(50):
            moved = False
            for i in range(len(dir_pos_list)):
                for j in range(i + 1, len(dir_pos_list)):
                    d1, p1 = dir_pos_list[i]
                    d2, p2 = dir_pos_list[j]
                    dx = p1[0] - p2[0]
                    dy = p1[1] - p2[1]
                    dist = math.sqrt(dx * dx + dy * dy) or 1.0
                    min_dist = dir_actual_radius[d1] + dir_actual_radius[d2]
                    if dist < min_dist:
                        # Push apart
                        overlap = (min_dist - dist) / 2 + 10
                        nx_d = dx / dist
                        ny_d = dy / dist
                        p1[0] += nx_d * overlap
                        p1[1] += ny_d * overlap
                        p2[0] -= nx_d * overlap
                        p2[1] -= ny_d * overlap
                        moved = True
            if not moved:
                break

        # Apply pushed positions back — shift all nodes in each system
        for d, new_center in dir_pos_list:
            old_cx, old_cy = dir_centers[d]
            shift_x = new_center[0] - old_cx
            shift_y = new_center[1] - old_cy
            if abs(shift_x) < 0.01 and abs(shift_y) < 0.01:
                continue
            dir_centers[d] = (new_center[0], new_center[1])
            for fid in dir_files[d]:
                if fid in positions:
                    ox, oy = positions[fid]
                    positions[fid] = (round(ox + shift_x, 2), round(oy + shift_y, 2))
                for cid in file_children.get(fid, []):
                    if cid in positions:
                        ox, oy = positions[cid]
                        positions[cid] = (round(ox + shift_x, 2), round(oy + shift_y, 2))

        # Compute graph metrics (FX001-2: degree, depth, entry point detection)
        in_degree: dict[str, int] = {}
        out_degree: dict[str, int] = {}
        for source, target, data in all_edges:
            if data.get("edge_type") == "references":
                out_degree[source] = out_degree.get(source, 0) + 1
                in_degree[target] = in_degree.get(target, 0) + 1

        def _compute_depth(node_id: str) -> int:
            depth = 0
            current = node_map.get(node_id)
            while current and current.parent_node_id:
                depth += 1
                current = node_map.get(current.parent_node_id)
                if depth > 20:
                    break  # safety
            return depth

        # Build lookup: node_id → dir_path
        node_dir: dict[str, str] = {}
        for dir_path, file_ids in dir_files.items():
            for fid in file_ids:
                node_dir[fid] = dir_path
                for cid in file_children.get(fid, []):
                    node_dir[cid] = dir_path

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
            # Solar system level
            cat = nd.get("category", "")
            nd["level"] = "planet" if cat == "file" else "moon"
            nd["dir_path"] = node_dir.get(nid, "")

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

            # Size based on level: planets bigger, moons smaller
            degree = nd["degree"]
            if nd.get("category") == "file":
                for child_nd in node_dicts:
                    if child_nd.get("parent_node_id") == nid:
                        degree += in_degree.get(child_nd["node_id"], 0)
                        degree += out_degree.get(child_nd["node_id"], 0)
            nd["agg_degree"] = degree
            level = nd["level"]
            if level == "planet":
                nd["size"] = round(
                    max(8.0, min(35.0, 8.0 + math.log2(degree + 1) * 5.0)), 2
                )
            else:  # moon
                nd["size"] = round(
                    max(3.0, min(12.0, 3.0 + math.log2(degree + 1) * 2.0)), 2
                )

        # Inject virtual "sun" nodes for each directory
        sun_color = "#fbbf24"  # amber/gold for suns
        for dir_path in dir_list:
            cx, cy = dir_centers.get(dir_path, (0.0, 0.0))
            dir_name = Path(dir_path).name or dir_path
            num_files = len(dir_files[dir_path])
            sun_size = round(max(20.0, min(60.0, 20.0 + num_files * 3.0)), 2)
            node_dicts.append({
                "node_id": f"dir:{dir_path}",
                "name": dir_name,
                "category": "directory",
                "file_path": dir_path,
                "start_line": None,
                "end_line": None,
                "signature": None,
                "smart_content": f"Directory with {num_files} files",
                "language": None,
                "parent_node_id": None,
                "x": round(float(cx), 2),
                "y": round(float(cy), 2),
                "color": sun_color,
                "label": dir_name,
                "level": "sun",
                "dir_path": dir_path,
                "in_degree": 0,
                "out_degree": 0,
                "degree": 0,
                "depth": 0,
                "is_entry_point": False,
                "agg_degree": num_files,
                "size": sun_size,
            })

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
