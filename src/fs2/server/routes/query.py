"""Query routes for fs2 server.

Endpoints:
- GET  /api/v1/graphs/{name}/tree     — tree view with folder hierarchy
- GET  /api/v1/graphs/{name}/search   — single-graph search
- GET  /api/v1/graphs/{name}/nodes/{node_id} — get-node detail
- GET  /api/v1/search                  — multi-graph search

Per Phase 4 DYK decisions:
- #1: Wire existing EmbeddingAdapter for text-mode semantic
- #2: Single SQL with IN(...) for multi-graph
- #3: Reuse TreeService folder hierarchy algorithm (Python, not CTE)
- #4: Get-node includes children_count
- #5: Auto-mode checks per-graph embedding availability
"""

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from fs2.core.models.code_node import CodeNode
from fs2.core.models.content_type import ContentType
from fs2.core.repos.graph_store_pg import PostgreSQLGraphStore
from fs2.core.services.search import PgvectorSemanticMatcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])

# Regex metacharacters that trigger REGEX mode in auto-detect
_REGEX_METACHARACTERS = set("*?[]^$|()")

# Category icons for text rendering (matches MCP/CLI conventions)
_CATEGORY_ICONS = {
    "file": "📄", "folder": "📁", "type": "📦", "callable": "ƒ",
    "section": "📝", "block": "🏗️",
}


def _render_tree_as_text(tree_nodes: list[dict], indent: str = "", is_last_list: list[bool] | None = None) -> str:
    """Render tree dicts as compact text with icons."""
    if is_last_list is None:
        is_last_list = []
    lines: list[str] = []
    for i, node in enumerate(tree_nodes):
        is_last = i == len(tree_nodes) - 1
        cat = node.get("category", "other")
        icon = _CATEGORY_ICONS.get(cat, "○")
        node_id = node.get("node_id", "?")
        start = node.get("start_line", "?")
        end = node.get("end_line", "?")
        children = node.get("children", [])
        hidden = node.get("hidden_children_count", 0)

        suffix = f" ({len(children) + hidden} children)" if hidden else ""
        if is_last_list:
            prefix = ""
            for _j, was_last in enumerate(is_last_list):
                prefix += "    " if was_last else "│   "
            prefix += "└── " if is_last else "├── "
        else:
            prefix = ""

        lines.append(f"{prefix}{icon} {node_id} [{start}-{end}]{suffix}")

        if children:
            lines.append(_render_tree_as_text(children, indent, [*is_last_list, is_last]))
    return "\n".join(lines)


# ── Helpers ──


async def _resolve_graph(db, name: str) -> dict:
    """Resolve graph by name. Returns graph row dict or raises 404."""
    async with db.connection() as conn:
        result = await conn.execute(
            """SELECT id, name, status, embedding_model, embedding_dimensions
            FROM graphs WHERE name = %s""",
            (name,),
        )
        row = await result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Graph '{name}' not found")

    if row[2] != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Graph '{name}' is not ready (status: {row[2]})",
        )

    return {
        "id": str(row[0]),
        "name": row[1],
        "status": row[2],
        "embedding_model": row[3],
        "embedding_dimensions": row[4],
    }


def _detect_search_mode(pattern: str) -> str:
    """Detect search mode from pattern (same heuristic as local SearchService)."""
    if any(c in pattern for c in _REGEX_METACHARACTERS):
        return "regex"
    return "semantic"


def _detect_tree_input_mode(pattern: str) -> str:
    """Detect tree input mode (same as TreeService._detect_input_mode)."""
    if ":" in pattern:
        return "node_id"
    if "/" in pattern:
        return "folder"
    return "pattern"


def _extract_file_path(node_id: str) -> str:
    """Extract file path from node_id (e.g. 'file:src/main.py' → 'src/main.py')."""
    if ":" in node_id:
        parts = node_id.split(":", 1)
        if len(parts) > 1:
            return parts[1]
    return node_id


def _create_folder_node_dict(folder_path: str) -> dict:
    """Create a synthetic folder node dict for tree rendering."""
    name = folder_path.rstrip("/").rsplit("/", 1)[-1] if "/" in folder_path else folder_path.rstrip("/")
    return {
        "node_id": folder_path,
        "name": name,
        "category": "folder",
        "start_line": 0,
        "end_line": 0,
    }


def _code_node_to_tree_dict(node: CodeNode) -> dict:
    """Convert CodeNode to tree-compatible dict."""
    return {
        "node_id": node.node_id,
        "name": node.name,
        "category": node.category,
        "start_line": node.start_line,
        "end_line": node.end_line,
    }


def _compute_folder_hierarchy(
    file_nodes: list[CodeNode], max_depth: int,
    children_cache: dict[str, int] | None = None,
) -> list[dict]:
    """Compute virtual folder hierarchy from file nodes.

    Same algorithm as TreeService._compute_folder_hierarchy — splits
    node_id paths at '/' to build synthetic folder structure.
    """
    if not file_nodes:
        return []

    root: dict = {"files": [], "folders": {}}

    for node in file_nodes:
        file_path = _extract_file_path(node.node_id)
        parts = file_path.split("/")
        if len(parts) <= 1:
            root["files"].append(node)
        else:
            current = root
            for folder in parts[:-1]:
                if folder not in current["folders"]:
                    current["folders"][folder] = {"files": [], "folders": {}}
                current = current["folders"][folder]
            current["files"].append(node)

    return _build_folder_tree(root, max_depth, 0, "", None, children_cache)


def _count_folder_items(folder_dict: dict) -> int:
    """Count total items in a folder recursively."""
    count = len(folder_dict["files"])
    for sub in folder_dict["folders"].values():
        count += _count_folder_items(sub)
    return count


def _build_folder_tree(
    folder_dict: dict, max_depth: int, current_depth: int, path_prefix: str,
    store: PostgreSQLGraphStore | None = None,
    children_cache: dict | None = None,
) -> list[dict]:
    """Build tree node dicts from folder structure.

    If store and children_cache are provided, expands file symbol children
    and tracks real hidden_children_count for depth-limited nodes.
    """
    result = []

    # Folders first, sorted
    for folder_name in sorted(folder_dict["folders"].keys()):
        contents = folder_dict["folders"][folder_name]
        folder_path = f"{path_prefix}{folder_name}/"
        total = _count_folder_items(contents)

        node = _create_folder_node_dict(folder_path)

        if max_depth > 0 and current_depth + 1 >= max_depth:
            node["children"] = []
            node["hidden_children_count"] = total
        else:
            children = _build_folder_tree(
                contents, max_depth, current_depth + 1, folder_path,
                store, children_cache,
            )
            node["children"] = children
            node["hidden_children_count"] = 0

        result.append(node)

    # Files second, sorted
    for file_node in sorted(folder_dict["files"], key=lambda n: n.name or ""):
        node = _code_node_to_tree_dict(file_node)
        # Get real children count from cache
        child_count = 0
        if children_cache and file_node.node_id in children_cache:
            child_count = children_cache[file_node.node_id]

        if max_depth > 0 and current_depth + 1 >= max_depth:
            node["children"] = []
            node["hidden_children_count"] = child_count
        else:
            node["children"] = []
            node["hidden_children_count"] = child_count
        result.append(node)

    return result


async def _build_pattern_tree_async(
    matched: list[CodeNode], store: PostgreSQLGraphStore, max_depth: int
) -> list[dict]:
    """Build tree from pattern-matched nodes with async child expansion.

    Keeps only shallowest matches as roots (like TreeService._build_root_bucket),
    then recursively expands children via get_children_async.
    """
    if not matched:
        return []

    # Build root bucket: remove children when ancestor also matched
    matched_ids = {n.node_id for n in matched}
    roots = []

    for node in matched:
        has_ancestor = False
        parent_id = node.parent_node_id
        while parent_id:
            if parent_id in matched_ids:
                has_ancestor = True
                break
            parent_node = next(
                (n for n in matched if n.node_id == parent_id), None
            )
            parent_id = parent_node.parent_node_id if parent_node else None

        if not has_ancestor:
            roots.append(node)

    # Expand each root with children
    result = []
    for n in sorted(roots, key=lambda n: n.node_id):
        tree_node = await _build_tree_node_async(n, store, max_depth, 0)
        result.append(tree_node)
    return result


async def _build_tree_node_async(
    node: CodeNode, store: PostgreSQLGraphStore, max_depth: int, depth: int
) -> dict:
    """Recursively build a tree node dict with async child expansion."""
    children = await store.get_children_async(node.node_id)
    tree_dict = _code_node_to_tree_dict(node)

    if max_depth > 0 and depth + 1 >= max_depth:
        tree_dict["children"] = []
        tree_dict["hidden_children_count"] = len(children)
    else:
        child_dicts = []
        for child in sorted(children, key=lambda c: c.start_line):
            child_dict = await _build_tree_node_async(child, store, max_depth, depth + 1)
            child_dicts.append(child_dict)
        tree_dict["children"] = child_dicts
        tree_dict["hidden_children_count"] = 0

    return tree_dict


def _compute_folder_distribution(results: list[dict]) -> dict[str, int]:
    """Compute folder distribution from search results."""
    folders: dict[str, int] = {}
    for r in results:
        node_id = r["node_id"]
        path = _extract_file_path(node_id)
        parts = path.split("/")
        folder = parts[0] + "/" if len(parts) > 1 else "."
        folders[folder] = folders.get(folder, 0) + 1
    return dict(sorted(folders.items(), key=lambda x: -x[1]))


# ── Tree endpoint ──


@router.get("/graphs/{name}/tree")
async def tree(
    request: Request,
    name: str,
    pattern: str = Query(default=".", description="Filter pattern"),
    max_depth: int = Query(default=0, ge=0, description="Max depth (0=unlimited)"),
    format: str = Query(default="json", pattern="^(text|json)$", description="Output format"),
) -> dict:
    """Get tree view of a graph.

    Replicates local `fs2 tree` output:
    - pattern="." + max_depth>0 → virtual folder hierarchy
    - pattern with ":" → exact node_id match
    - pattern with "/" → folder prefix filter
    - other → substring/glob match
    """
    db = request.app.state.db
    graph = await _resolve_graph(db, name)
    store = PostgreSQLGraphStore(db, graph["id"])

    if pattern == "." and max_depth > 0:
        # Folder hierarchy mode: fetch file-level nodes
        all_nodes = await store.get_filtered_nodes_async(".")
        file_nodes = [n for n in all_nodes if n.node_id.startswith("file:")]

        # Build children count cache for file nodes
        children_cache: dict[str, int] = {}
        for fn in file_nodes:
            children_cache[fn.node_id] = await store.get_children_count_async(fn.node_id)

        tree_nodes = _compute_folder_hierarchy(file_nodes, max_depth, children_cache)
    elif pattern == ".":
        # Unlimited depth: all file nodes as folder tree without depth limit
        all_nodes = await store.get_filtered_nodes_async(".")
        file_nodes = [n for n in all_nodes if n.node_id.startswith("file:")]
        tree_nodes = _compute_folder_hierarchy(file_nodes, 0, None)
    else:
        # Pattern search mode with child expansion
        matched = await store.get_filtered_nodes_async(pattern)
        tree_nodes = await _build_pattern_tree_async(matched, store, max_depth)

    result = {
        "graph_name": graph["name"],
        "pattern": pattern,
        "max_depth": max_depth,
        "count": len(tree_nodes),
    }

    if format == "text":
        result["format"] = "text"
        result["content"] = _render_tree_as_text(tree_nodes)
    else:
        result["format"] = "json"
        result["tree"] = tree_nodes

    return result


# ── Get-node endpoint ──


@router.get("/graphs/{name}/nodes/{node_id:path}")
async def get_node(
    request: Request,
    name: str,
    node_id: str,
    detail: str = Query(default="min", pattern="^(min|max)$"),
) -> dict:
    """Get a single code node by ID.

    Per DYK #4: Includes children_count for parity with local.
    """
    db = request.app.state.db
    graph = await _resolve_graph(db, name)
    store = PostgreSQLGraphStore(db, graph["id"])

    node = await store.get_node_async(node_id)
    if not node:
        raise HTTPException(
            status_code=404,
            detail=f"Node '{node_id}' not found in graph '{name}'",
        )

    children_count = await store.get_children_count_async(node_id)

    result = _code_node_to_dict(node, detail)
    result["children_count"] = children_count
    result["graph_name"] = graph["name"]
    return result


def _code_node_to_dict(node: CodeNode, detail: str = "min") -> dict:
    """Convert CodeNode to response dict with detail level."""
    ct = getattr(node, "content_type", None)
    ct_val = ct.value if isinstance(ct, ContentType) else str(ct) if ct else "code"

    result = {
        "node_id": node.node_id,
        "category": node.category,
        "ts_kind": node.ts_kind,
        "content_type": ct_val,
        "name": node.name,
        "qualified_name": node.qualified_name,
        "start_line": node.start_line,
        "end_line": node.end_line,
        "language": node.language,
        "is_named": node.is_named,
        "parent_node_id": node.parent_node_id,
        "smart_content": node.smart_content,
        "signature": node.signature,
    }

    if detail == "max":
        result.update({
            "start_column": node.start_column,
            "end_column": node.end_column,
            "start_byte": node.start_byte,
            "end_byte": node.end_byte,
            "content": node.content,
            "content_hash": node.content_hash,
            "field_name": node.field_name,
            "is_error": getattr(node, "is_error", False),
            "truncated": getattr(node, "truncated", False),
            "truncated_at_line": getattr(node, "truncated_at_line", None),
            "smart_content_hash": getattr(node, "smart_content_hash", None),
            "embedding_hash": node.embedding_hash,
            "has_embedding": node.embedding is not None,
            "has_smart_content_embedding": (
                getattr(node, "smart_content_embedding", None) is not None
            ),
        })

    return result


# ── Single-graph search endpoint ──


@router.get("/graphs/{name}/search")
async def search_graph(
    request: Request,
    name: str,
    pattern: str = Query(..., min_length=1),
    mode: str = Query(default="auto", pattern="^(text|regex|semantic|auto)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    detail: str = Query(default="min", pattern="^(min|max)$"),
    min_similarity: float = Query(default=0.25, ge=0.0, le=1.0),
    include: str | None = Query(default=None, description="Comma-separated include patterns"),
    exclude: str | None = Query(default=None, description="Comma-separated exclude patterns"),
    query_vector: str | None = Query(default=None, description="Pre-embedded vector as JSON array"),
    model: str | None = Query(default=None, description="Embedding model name for validation"),
) -> dict:
    """Search within a single graph."""
    db = request.app.state.db
    graph = await _resolve_graph(db, name)

    inc = tuple(include.split(",")) if include else None
    exc = tuple(exclude.split(",")) if exclude else None

    return await _execute_search(
        request, [graph], pattern, mode, limit, offset, detail,
        min_similarity, inc, exc, query_vector, model,
    )


# ── Multi-graph search endpoint ──


@router.get("/search")
async def search_multi(
    request: Request,
    pattern: str = Query(..., min_length=1),
    graph: str = Query(default="all", description="Graph name(s), comma-separated, or 'all'"),
    mode: str = Query(default="auto", pattern="^(text|regex|semantic|auto)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    detail: str = Query(default="min", pattern="^(min|max)$"),
    min_similarity: float = Query(default=0.25, ge=0.0, le=1.0),
    include: str | None = Query(default=None),
    exclude: str | None = Query(default=None),
    query_vector: str | None = Query(default=None),
    model: str | None = Query(default=None, description="Embedding model name for validation"),
) -> dict:
    """Search across one, multiple, or all graphs.

    Per DYK #2: Single SQL query with WHERE graph_id IN(...).
    """
    db = request.app.state.db

    if graph == "all":
        async with db.connection() as conn:
            result = await conn.execute(
                """SELECT id, name, status, embedding_model, embedding_dimensions
                FROM graphs WHERE status = 'ready' ORDER BY name"""
            )
            rows = await result.fetchall()
        graphs = [
            {"id": str(r[0]), "name": r[1], "status": r[2],
             "embedding_model": r[3], "embedding_dimensions": r[4]}
            for r in rows
        ]
        if not graphs:
            return {"meta": {"total": 0, "showing": {"from": 0, "to": 0, "count": 0},
                             "pagination": {"limit": limit, "offset": offset}, "folders": {}},
                    "results": []}
    else:
        names = [n.strip() for n in graph.split(",")]
        graphs = []
        for n in names:
            g = await _resolve_graph(db, n)
            graphs.append(g)

    inc = tuple(include.split(",")) if include else None
    exc = tuple(exclude.split(",")) if exclude else None

    return await _execute_search(
        request, graphs, pattern, mode, limit, offset, detail,
        min_similarity, inc, exc, query_vector, model,
    )


async def _execute_search(
    request: Request,
    graphs: list[dict],
    pattern: str,
    mode: str,
    limit: int,
    offset: int,
    detail: str,
    min_similarity: float,
    include: tuple[str, ...] | None,
    exclude: tuple[str, ...] | None,
    query_vector_str: str | None,
    requested_model: str | None = None,
) -> dict:
    """Execute search across given graphs.

    Routes to text/regex/semantic based on mode.
    Auto-mode detects from pattern + embedding availability.
    """
    db = request.app.state.db
    graph_ids = [g["id"] for g in graphs]

    # Parse BYO query vector if provided
    query_vector = None
    if query_vector_str:
        import json
        try:
            query_vector = json.loads(query_vector_str)
        except (json.JSONDecodeError, TypeError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid query_vector JSON: {e}") from e

    # Resolve auto mode
    resolved_mode = mode
    if mode == "auto":
        resolved_mode = _detect_search_mode(pattern)
        if resolved_mode == "semantic":
            # DYK #5: Check per-graph embedding availability
            has_any_embeddings = False
            for g in graphs:
                store = PostgreSQLGraphStore(db, g["id"])
                if await store.has_embeddings_async():
                    has_any_embeddings = True
                    break
            if not has_any_embeddings:
                resolved_mode = "text"

    # Embedding model validation (T006/FT-002)
    embedding_adapter = getattr(request.app.state, "embedding_adapter", None)

    if resolved_mode == "semantic" and query_vector is None and embedding_adapter is None:
        raise HTTPException(
            status_code=503,
            detail="Semantic search requires a configured embedding adapter. "
            "Either configure one on the server or pass query_vector directly.",
        )

    if resolved_mode == "semantic" and query_vector is None:
        # Validate embedding model compatibility
        adapter_model = (
            requested_model
            or getattr(embedding_adapter, "model_name", None)
            or getattr(getattr(embedding_adapter, "_config", None), "model", None)
        )
        if adapter_model:
            for g in graphs:
                stored_model = g.get("embedding_model")
                if stored_model and adapter_model != stored_model:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Graph '{g['name']}' uses embedding model '{stored_model}' "
                        f"but query uses '{adapter_model}'. Embeddings are incompatible.",
                    )

    if resolved_mode in ("text", "regex"):
        store = PostgreSQLGraphStore(db, graph_ids[0])
        if resolved_mode == "text":
            results, total = await store.search_text_async(
                pattern, limit, offset, include, exclude, graph_ids
            )
        else:
            results, total = await store.search_regex_async(
                pattern, limit, offset, include, exclude, graph_ids
            )
    else:
        # Semantic search
        matcher = PgvectorSemanticMatcher(db, embedding_adapter)
        results, total = await matcher.search(
            graph_ids=graph_ids,
            limit=limit,
            offset=offset,
            min_similarity=min_similarity,
            query=pattern if query_vector is None else None,
            query_vector=query_vector,
            include=include,
            exclude=exclude,
        )

    # Format response
    showing_from = offset
    showing_to = offset + len(results)
    folders = _compute_folder_distribution(results)

    # Apply detail level to results
    formatted_results = []
    for r in results:
        entry = {
            "node_id": r["node_id"],
            "start_line": r["start_line"],
            "end_line": r["end_line"],
            "match_start_line": r.get("match_start_line", r["start_line"]),
            "match_end_line": r.get("match_end_line", r["end_line"]),
            "smart_content": r.get("smart_content"),
            "snippet": r.get("snippet", ""),
            "score": r["score"],
            "match_field": r.get("match_field", "content"),
            "graph_name": r.get("graph_name"),
        }
        if detail == "max":
            entry["content"] = r.get("content")
            entry["matched_lines"] = r.get("matched_lines")
            entry["chunk_offset"] = r.get("chunk_offset")
            entry["embedding_chunk_index"] = r.get("embedding_chunk_index")
        formatted_results.append(entry)

    return {
        "meta": {
            "total": total,
            "showing": {"from": showing_from, "to": showing_to, "count": len(results)},
            "pagination": {"limit": limit, "offset": offset},
            "folders": folders,
        },
        "results": formatted_results,
    }
