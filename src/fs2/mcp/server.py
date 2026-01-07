"""MCP server module for fs2.

Provides the FastMCP server instance for AI agent integration.
All logging is configured to use stderr BEFORE any fs2 imports
to ensure zero stdout pollution (MCP protocol requirement).

Architecture:
- MCPLoggingConfig configures stderr-only logging FIRST
- FastMCP instance created with name "fs2"
- translate_error() converts domain exceptions to agent-friendly responses
- Tools: tree (Phase 2), get_node (Phase 3), search (Phase 4)

Per Critical Discovery 01: STDIO protocol requires stderr-only logging.
Per Critical Discovery 05: Error translation at MCP boundary.
Per Critical Discovery 07: Logging config BEFORE imports.

Usage:
    # CLI entry point
    from fs2.mcp.server import mcp
    mcp.run()

    # Error translation
    from fs2.mcp.server import translate_error
    try:
        ...
    except Exception as e:
        return translate_error(e)

    # Direct tool access (for testing)
    from fs2.mcp.server import tree
    result = tree(pattern="Calculator")
"""

# CRITICAL: Configure logging BEFORE any fs2 imports
# This ensures all loggers created at module level use stderr
from fs2.core.adapters.logging_config import MCPLoggingConfig

MCPLoggingConfig().configure()

# Emit startup log to confirm logging is active (goes to stderr)
import logging

logging.getLogger(__name__).info("MCP logging configured: all output routed to stderr")

# NOW safe to import FastMCP and other fs2 modules
from typing import Any, Literal

logger = logging.getLogger(__name__)

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from fs2.config.exceptions import MissingConfigurationError
from fs2.core.adapters.exceptions import (
    DocsNotFoundError,
    GraphNotFoundError,
    GraphStoreError,
)
from fs2.core.models.code_node import CodeNode
from fs2.core.models.tree_node import TreeNode
from fs2.core.services.get_node_service import GetNodeService
from fs2.core.services.tree_service import TreeService
from fs2.mcp.dependencies import (
    get_config,
    get_docs_service,
    get_embedding_adapter,
    get_graph_store,
)

# Create FastMCP server instance
# Note: Tools will be added in Phase 2-4
mcp = FastMCP(
    name="fs2",
    instructions=(
        "fs2 (Flowspace2) is a code intelligence tool for exploring and "
        "querying code repositories. Use the available tools to search, "
        "navigate, and understand codebases."
    ),
)


def translate_error(exc: Exception) -> dict[str, Any]:
    """Translate domain exceptions to agent-friendly responses.

    Converts fs2 exceptions into structured dictionaries with:
    - type: Exception class name
    - message: Human-readable description
    - action: Suggested remediation (or None)

    Per Critical Discovery 05: Error translation at MCP boundary.

    Args:
        exc: Any exception from fs2 operations.

    Returns:
        Dict with type, message, and action keys.

    Example:
        >>> translate_error(GraphNotFoundError(Path(".fs2/graph.pickle")))
        {
            'type': 'GraphNotFoundError',
            'message': "Graph not found at .fs2/graph.pickle. Run 'fs2 scan' first.",
            'action': "Run 'fs2 scan' to create the graph."
        }
    """
    # Log original exception for debugging (goes to stderr per MCP config)
    logger.error("MCP error translation: %s", exc, exc_info=True)

    error_type = type(exc).__name__
    message = str(exc)
    action: str | None = None

    # Specific error handling with actionable guidance
    if isinstance(exc, DocsNotFoundError):
        # Per DYK-3: Rare error, only on broken package install
        action = "Documentation package not found. Use docs_list() to see available documents."

    elif isinstance(exc, GraphNotFoundError):
        action = "Run 'fs2 scan' to create the graph."

    elif isinstance(exc, GraphStoreError):
        action = (
            "The graph file may be corrupted. Try running 'fs2 scan' to regenerate it."
        )

    elif isinstance(exc, ValueError):
        # Often regex or pattern errors
        if "regex" in message.lower() or "pattern" in message.lower():
            action = "Check the search pattern for valid regex syntax."
        else:
            action = "Verify the input parameters are valid."

    return {
        "type": error_type,
        "message": message,
        "action": action,
    }


# =============================================================================
# Helper Functions
# =============================================================================

# Icon mapping for text output (duplicated from CLI per Finding #06)
CATEGORY_ICONS = {
    "file": "📄",
    "folder": "📁",
    "type": "📦",
    "callable": "ƒ",
    "section": "📝",
    "block": "🏗️",
    "definition": "🔹",
    "statement": "▸",
    "expression": "●",
    "other": "○",
}


def _render_tree_as_text(
    tree_dicts: list[dict[str, Any]],
    indent: str = "",
    is_last_list: list[bool] | None = None,
) -> str:
    """Render tree nodes as compact plain text with full node_ids.

    Per T012/T013: Shows full node_id (not just name) so agents can copy-paste
    node_ids directly for use with get_node() without switching to JSON format.

    Produces output like:
        📄 file:src/tree.py [1-364] (4 children)
        ├── ƒ callable:src/tree.py:_tree_node_to_dict [51-99]
        ├── ƒ callable:src/tree.py:tree [102-240]
        └── ƒ callable:src/tree.py:_display_tree [243-309]

    Note: Folder nodes (category="folder") use their node_id as-is since
    the node_id IS the path with trailing slash (e.g., "src/fs2/").

    Args:
        tree_dicts: List of tree node dicts from _tree_node_to_dict().
        indent: Current indentation prefix.
        is_last_list: Stack tracking last-child status for drawing lines.

    Returns:
        Plain text tree representation.
    """
    if is_last_list is None:
        is_last_list = []

    lines = []
    for i, node in enumerate(tree_dicts):
        is_last = i == len(tree_dicts) - 1

        # Build prefix based on tree position
        if not is_last_list:
            prefix = ""
        else:
            prefix = ""
            for j, was_last in enumerate(is_last_list):
                if j == len(is_last_list) - 1:
                    prefix += "└── " if is_last else "├── "
                else:
                    prefix += "    " if was_last else "│   "

        # Format node line - use full node_id for copy-paste workflow (T012/T013)
        icon = CATEGORY_ICONS.get(node.get("category", "other"), "○")
        node_id = node.get("node_id", "unknown")
        start = node.get("start_line", 0)
        end = node.get("end_line", 0)
        hidden = node.get("hidden_children_count", 0)

        line = f"{prefix}{icon} {node_id} [{start}-{end}]"
        if hidden > 0:
            line += f" ({hidden} children)"

        lines.append(line)

        # Recurse into children
        children = node.get("children", [])
        if children:
            child_text = _render_tree_as_text(
                children,
                indent,
                is_last_list + [is_last],
            )
            lines.append(child_text)

    return "\n".join(lines)


def _tree_node_to_dict(
    tree_node: TreeNode,
    detail: Literal["min", "max"] = "min",
) -> dict[str, Any]:
    """Convert TreeNode to JSON-serializable dict.

    Per T005a: Recursive conversion with correct fields per detail level.

    Fields always included:
    - node_id, name, category, start_line, end_line, children

    Fields included when > 0:
    - hidden_children_count

    Fields included only in max detail:
    - signature, smart_content

    Args:
        tree_node: TreeNode from TreeService.build_tree().
        detail: "min" for compact output, "max" for full metadata.

    Returns:
        Dict suitable for JSON serialization.
    """
    node = tree_node.node

    # Base fields (always present - CRITICAL: node_id always included for agent workflow)
    result: dict[str, Any] = {
        "node_id": node.node_id,
        "name": node.name,
        "category": node.category,
        "start_line": node.start_line,
        "end_line": node.end_line,
        "children": [_tree_node_to_dict(child, detail) for child in tree_node.children],
    }

    # Add hidden_children_count only when > 0
    if tree_node.hidden_children_count > 0:
        result["hidden_children_count"] = tree_node.hidden_children_count

    # Max detail includes additional fields
    if detail == "max":
        if node.signature:
            result["signature"] = node.signature
        if node.smart_content:
            result["smart_content"] = node.smart_content

    return result


# =============================================================================
# MCP Tools (Phase 2: tree)
# =============================================================================


def tree(
    pattern: str = ".",
    max_depth: int = 0,
    detail: Literal["min", "max"] = "min",
    format: Literal["text", "json"] = "text",
    save_to_file: str | None = None,
) -> dict[str, Any]:
    """Explore codebase structure as a hierarchical tree.

    WHEN TO USE: Start here to understand what exists in a codebase.
    Returns files, classes, and functions with their containment relationships.

    PREREQUISITES: Requires 'fs2 scan' to have been run first.
    If you get a "Graph not found" error, the codebase hasn't been indexed.

    WORKFLOW:
    1. Use tree(pattern=".") to see all top-level files
    2. Use tree(pattern="ClassName") to find specific classes/functions
    3. Use returned node_id values with get_node() for detailed source code

    FOLDER NAVIGATION (NEW):
    Use patterns with "/" to filter by folder path:
    1. tree(pattern="src/") - shows all files under src/
    2. tree(pattern="src/fs2/cli/") - shows files in src/fs2/cli/
    3. Copy node_id from results, use with get_node() for source

    IMPORTANT: Trailing "/" is recommended for folder patterns.
    - "src/fs2/" = folder filter (files under this path)
    - "src/fs2" = also folder filter (contains "/")
    - "Calculator" = pattern match (no "/")

    Parameters:
        pattern: Filter pattern for matching code elements.
            - "." returns all nodes (default)
            - "path/" filters files by folder (e.g., "src/fs2/")
            - "ClassName" finds nodes containing that substring
            - "file:path/to/file.py" matches exact node_id
            - "*.py" or "Calculator*" for glob patterns
        max_depth: How many levels deep to expand.
            - 0 = unlimited depth (full tree)
            - 1 = root nodes only
            - 2 = roots + one level of children
        detail: Output verbosity level.
            - "min" = node_id, name, category, lines, children (default)
            - "max" = adds signature, smart_content for detailed inspection
        format: Output format - "text" (default) or "json".
            - "text": Compact tree view with icons, ideal for LLM context (default)
            - "json": Full structured data, useful for jq/scripting but VERBOSE
            NOTE: JSON format uses significantly more tokens. Use "text" for
            exploration, "json" only when you need exact node_ids for get_node().
        save_to_file: Optional file path to save tree as JSON.
            Path must be under current working directory.

    Returns:
        Dict with format-specific content:
        - format="text": {"format": "text", "content": "...", "count": N}
        - format="json": {"format": "json", "tree": [...], "count": N}
        When save_to_file is used, adds 'saved_to' field.

    Example:
        >>> tree(pattern="Calculator")  # Default text format
        {"format": "text", "content": "📦 Calculator [5-45]\\n├── ƒ add...", "count": 3}

        >>> tree(pattern="Calculator", format="json")  # JSON for scripting
        {"format": "json", "tree": [{"node_id": "class:...", ...}], "count": 3}

        >>> tree(pattern="src/fs2/cli/")  # Folder filter
        {"format": "text", "content": "📄 tree.py [1-364]\\n📄 main.py...", "count": 12}
    """
    try:
        config = get_config()
        store = get_graph_store()
        service = TreeService(config=config, graph_store=store)
        tree_nodes = service.build_tree(pattern=pattern, max_depth=max_depth)
        tree_list = [_tree_node_to_dict(tn, detail) for tn in tree_nodes]

        # Count total nodes
        def count_nodes(nodes: list[dict]) -> int:
            total = len(nodes)
            for n in nodes:
                total += count_nodes(n.get("children", []))
            return total

        node_count = count_nodes(tree_list)

        # Handle save_to_file if specified (always saves JSON)
        if save_to_file is not None:
            import json
            from pathlib import Path

            absolute_path = _validate_save_path(save_to_file)
            output_path = Path(absolute_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(absolute_path, "w", encoding="utf-8") as f:
                json.dump(tree_list, f, indent=2)

            # Return in requested format with saved_to info
            if format == "json":
                return {
                    "format": "json",
                    "tree": tree_list,
                    "count": node_count,
                    "saved_to": absolute_path,
                }
            else:
                text_output = _render_tree_as_text(tree_list)
                return {
                    "format": "text",
                    "content": text_output,
                    "count": node_count,
                    "saved_to": absolute_path,
                }

        # Return in requested format
        if format == "json":
            return {"format": "json", "tree": tree_list, "count": node_count}
        else:
            text_output = _render_tree_as_text(tree_list)
            return {"format": "text", "content": text_output, "count": node_count}

    except GraphNotFoundError:
        raise ToolError(
            "Graph not found. Run 'fs2 scan' to create the graph."
        ) from None
    except GraphStoreError as e:
        raise ToolError(f"Graph error: {e}. The graph file may be corrupted.") from None
    except Exception as e:
        logger.exception("Unexpected error in tree tool")
        raise ToolError(f"Unexpected error: {e}") from None


# Register tree function as MCP tool with annotations (per T007)
# Per Critical Discovery 02: Tool descriptions drive agent tool selection
# Per plan 2.7: Annotations indicate tool behavior to clients
_tree_tool = mcp.tool(
    annotations={
        "title": "Explore Code Tree",
        "readOnlyHint": False,  # Can write files via save_to_file parameter
        "destructiveHint": False,  # No destructive side effects
        "idempotentHint": True,  # Same inputs always return same outputs
        "openWorldHint": False,  # No external network/API calls
    }
)(tree)


# =============================================================================
# MCP Tools (Phase 3: get_node)
# =============================================================================


def _code_node_to_dict(
    node: CodeNode,
    detail: Literal["min", "max"] = "min",
) -> dict[str, Any]:
    """Convert CodeNode to JSON-serializable dict with explicit field selection.

    Per DYK Session: Explicit field filtering to prevent embedding leakage.
    NEVER include embedding vectors or internal hash fields.

    Fields in min detail (7 core fields):
    - node_id, name, category, content, signature, start_line, end_line

    Fields in max detail (adds 5 more):
    - smart_content, language, parent_node_id, qualified_name, ts_kind

    NEVER included (embedding data and internal metadata):
    - embedding, smart_content_embedding, embedding_hash, embedding_chunk_offsets
    - content_hash, smart_content_hash
    - start_byte, end_byte, start_column, end_column
    - is_named, field_name, is_error, truncated, truncated_at_line, content_type

    Args:
        node: CodeNode from GetNodeService.get_node().
        detail: "min" for compact output, "max" for full metadata.

    Returns:
        Dict suitable for JSON serialization.
    """
    # Core fields (always present)
    result: dict[str, Any] = {
        "node_id": node.node_id,
        "name": node.name,
        "category": node.category,
        "content": node.content,
        "signature": node.signature,
        "start_line": node.start_line,
        "end_line": node.end_line,
    }

    # Extended fields (max detail only)
    if detail == "max":
        result["smart_content"] = node.smart_content
        result["language"] = node.language
        result["parent_node_id"] = node.parent_node_id
        result["qualified_name"] = node.qualified_name
        result["ts_kind"] = node.ts_kind

    return result


def _validate_save_path(save_to_file: str) -> str:
    """Validate save_to_file path is under current working directory.

    Per DYK Session: Security constraint - path must be at or under PWD.
    Prevents directory traversal attacks.

    Args:
        save_to_file: Relative or absolute path to validate.

    Returns:
        Absolute path string if valid.

    Raises:
        ToolError: If path escapes PWD or is absolute outside PWD.
    """
    from pathlib import Path

    cwd = Path.cwd().resolve()
    target = (cwd / save_to_file).resolve()

    # Check if target is under or equal to cwd
    try:
        target.relative_to(cwd)
    except ValueError:
        raise ToolError(
            f"Path '{save_to_file}' escapes working directory. "
            "Only paths under the current directory are allowed."
        ) from None

    return str(target)


def get_node(
    node_id: str,
    save_to_file: str | None = None,
    detail: Literal["min", "max"] = "min",
) -> dict[str, Any] | None:
    """Retrieve complete code node by ID.

    Returns full source content and metadata for a specific code element.
    Use after tree() or search() to get the complete source code for a node.

    Args:
        node_id: Unique identifier from tree() or search() results.
            Format: 'category:path:name' (e.g., 'class:src/calc.py:Calculator')
        save_to_file: Optional file path to save node as JSON.
            Path must be under current working directory.
        detail: Output verbosity level.
            - "min" = 7 core fields (default)
            - "max" = adds smart_content, language, parent_node_id, etc.

    Returns:
        CodeNode dict if found, None if node_id doesn't exist.
        When save_to_file is used, includes 'saved_to' field with absolute path.

    Raises:
        ToolError: If graph not found or path escapes working directory.
    """
    try:
        config = get_config()
        store = get_graph_store()
        service = GetNodeService(config=config, graph_store=store)
        code_node = service.get_node(node_id)

        # Return None for not-found (per AC5 - not an error)
        if code_node is None:
            return None

        # Convert to dict with explicit field selection
        result = _code_node_to_dict(code_node, detail)

        # Handle save_to_file if specified
        if save_to_file is not None:
            import json

            # Validate path security
            absolute_path = _validate_save_path(save_to_file)

            # Write JSON to file
            with open(absolute_path, "w") as f:
                json.dump(result, f, indent=2)

            # Add saved_to field per DYK Session decision
            result["saved_to"] = absolute_path

        return result

    except GraphNotFoundError:
        raise ToolError(
            "Graph not found. Run 'fs2 scan' to create the graph."
        ) from None
    except GraphStoreError as e:
        raise ToolError(f"Graph error: {e}. The graph file may be corrupted.") from None
    except ToolError:
        # Re-raise ToolErrors (from path validation) as-is
        raise
    except Exception as e:
        logger.exception("Unexpected error in get_node tool")
        raise ToolError(f"Unexpected error: {e}") from None


# Register get_node function as MCP tool with annotations (per T006)
# Per DYK Session: readOnlyHint=False because save_to_file writes to filesystem
_get_node_tool = mcp.tool(
    annotations={
        "title": "Get Code Node",
        "readOnlyHint": False,  # Can write files via save_to_file
        "destructiveHint": False,  # Doesn't destroy existing data
        "idempotentHint": True,  # Same inputs return same outputs
        "openWorldHint": False,  # No external network/API calls
    }
)(get_node)


# =============================================================================
# MCP Tools (Phase 4: search)
# =============================================================================


def _build_search_envelope(
    results: list,
    total: int,
    limit: int,
    offset: int,
    include: list[str] | None,
    exclude: list[str] | None,
    filtered_count: int | None,
    detail: Literal["min", "max"],
) -> dict[str, Any]:
    """Build search response envelope with meta and results.

    Per DYK#5: Uses SearchResultMeta for envelope format (CLI implementation).

    Args:
        results: List of SearchResult objects.
        total: Total matches before pagination.
        limit: Requested limit.
        offset: Requested offset.
        include: Include filter patterns (or None).
        exclude: Exclude filter patterns (or None).
        filtered_count: Count after filtering (or None if no filters).
        detail: Detail level for result serialization.

    Returns:
        Envelope dict with meta and results keys.
    """
    from fs2.core.models.search.search_result_meta import (
        SearchResultMeta,
        compute_folder_distribution,
    )

    # Compute folder distribution from result node_ids
    node_ids = [r.node_id for r in results]
    folders = compute_folder_distribution(node_ids)

    # Build showing info
    showing = {
        "from": offset,
        "to": offset + len(results),
        "count": len(results),
    }

    # Build pagination info
    pagination = {
        "limit": limit,
        "offset": offset,
    }

    # Build meta
    meta = SearchResultMeta(
        total=total,
        showing=showing,
        pagination=pagination,
        folders=folders,
        include=list(include) if include else None,
        exclude=list(exclude) if exclude else None,
        filtered=filtered_count,
    )

    # Per DYK#4: Use SearchResult.to_dict(detail) directly
    return {
        "meta": meta.to_dict(),
        "results": [r.to_dict(detail) for r in results],
    }


async def search(
    pattern: str,
    mode: str = "auto",
    limit: int = 5,
    offset: int = 0,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    detail: Literal["min", "max"] = "min",
    save_to_file: str | None = None,
) -> dict[str, Any]:
    """Search codebase for matching code elements.

    WHEN TO USE: Find code by content, pattern, or meaning.
    - TEXT mode: Substring search in content, node_id, smart_content
    - REGEX mode: Regular expression pattern matching
    - SEMANTIC mode: Conceptual search using embeddings (requires indexed codebase)
    - AUTO mode: Automatically selects best mode based on pattern

    PREREQUISITES:
    - Requires 'fs2 scan' to have been run first
    - SEMANTIC mode requires 'fs2 scan --embed' for embeddings

    WORKFLOW:
    1. Use search(pattern="concept", mode="semantic") for conceptual queries
    2. Use search(pattern="ClassName", mode="text") for exact matches
    3. Use search(pattern="def.*test", mode="regex") for pattern matching
    4. Use returned node_id values with get_node() for full source code

    Parameters:
        pattern: Search pattern (cannot be empty).
            - For TEXT: Substring to find (case-insensitive)
            - For REGEX: Regular expression pattern
            - For SEMANTIC: Natural language query
            - For AUTO: Pattern is analyzed to select best mode
        mode: Search mode - "text", "regex", "semantic", or "auto" (default: "auto")
        limit: Maximum results to return (default: 5, must be >= 1)
        offset: Number of results to skip for pagination (default: 0)
        include: Filter to keep only node_ids matching ANY pattern (glob like *.py or regex)
        exclude: Filter to remove node_ids matching ANY pattern (glob like *.py or regex)
        detail: Output verbosity - "min" (9 fields) or "max" (13 fields)
        save_to_file: Optional file path to save results as JSON.
            Path must be under current working directory (security constraint).
            When specified, response includes 'saved_to' field with absolute path.

    Returns:
        Envelope with meta and results:
        {
            "meta": {
                "total": 47,
                "showing": {"from": 0, "to": 20, "count": 20},
                "pagination": {"limit": 20, "offset": 0},
                "folders": {"src/": 30, "tests/": 17}
            },
            "results": [
                {"node_id": "...", "score": 0.92, "snippet": "...", ...}
            ]
        }

    Example:
        >>> await search(pattern="authentication", mode="semantic", limit=5)
        {"meta": {...}, "results": [{...}, {...}, ...]}
    """
    from fs2.core.adapters.exceptions import (
        EmbeddingAdapterError,
        EmbeddingAuthenticationError,
        EmbeddingRateLimitError,
    )
    from fs2.core.models.search import QuerySpec, SearchMode
    from fs2.core.services.search import SearchService
    from fs2.core.services.search.exceptions import SearchError
    from fs2.core.utils import normalize_filter_pattern

    try:
        from pathlib import Path

        from fs2.config.objects import GraphConfig

        # Validate pattern
        if not pattern or not pattern.strip():
            raise ToolError("Pattern cannot be empty or whitespace-only")

        # Validate and convert mode
        mode_upper = mode.upper()
        try:
            search_mode = SearchMode[mode_upper]
        except KeyError:
            valid_modes = ", ".join(m.value for m in SearchMode)
            raise ToolError(
                f"Invalid mode '{mode}'. Must be one of: {valid_modes}"
            ) from None

        # Convert glob patterns to regex, then to tuples for QuerySpec
        # normalize_filter_pattern() auto-detects globs like *.py and .cs
        try:
            include_tuple = (
                tuple(normalize_filter_pattern(p) for p in include) if include else None
            )
            exclude_tuple = (
                tuple(normalize_filter_pattern(p) for p in exclude) if exclude else None
            )
        except ValueError as e:
            raise ToolError(str(e)) from None

        # Build QuerySpec (validates parameters including regex patterns)
        try:
            spec = QuerySpec(
                pattern=pattern,
                mode=search_mode,
                limit=limit,
                offset=offset,
                include=include_tuple,
                exclude=exclude_tuple,
            )
        except ValueError as e:
            # Regex validation errors, limit/offset errors
            raise ToolError(str(e)) from None

        # Get dependencies
        config = get_config()
        store = get_graph_store()

        # Ensure graph is loaded (SearchService doesn't have _ensure_loaded like TreeService)
        graph_config = config.require(GraphConfig)
        graph_path = Path(graph_config.graph_path)
        if not graph_path.exists():
            raise GraphNotFoundError(graph_path)
        store.load(graph_path)

        # Create embedding adapter from config (or use injected one for testing)
        from fs2.core.adapters.embedding_adapter import (
            create_embedding_adapter_from_config,
        )

        adapter = get_embedding_adapter()
        if adapter is None:
            adapter = create_embedding_adapter_from_config(config)

        # Create service with optional embedding adapter
        # Per plan-018: Pass config for parent_penalty setting
        service = SearchService(
            graph_store=store, embedding_adapter=adapter, config=config
        )

        # Execute search
        results = await service.search(spec)

        # Calculate totals for envelope
        # Note: We need the full count before pagination, but SearchService
        # already applies pagination. For accurate total, we'd need a separate
        # count query. For now, use len(results) + offset as estimate.
        # This is a known limitation - total is the count we have.
        total = len(results) + offset

        # Build envelope
        envelope = _build_search_envelope(
            results=results,
            total=total,
            limit=limit,
            offset=offset,
            include=include,
            exclude=exclude,
            filtered_count=None,  # Filter already applied in service
            detail=detail,
        )

        # Handle save_to_file if specified
        if save_to_file is not None:
            import json

            # Validate path security
            absolute_path = _validate_save_path(save_to_file)

            # Create parent directories if needed (AC10)
            from pathlib import Path

            output_path = Path(absolute_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Write JSON to file with UTF-8 encoding (per Insight #3)
            with open(absolute_path, "w", encoding="utf-8") as f:
                json.dump(envelope, f, indent=2)

            # Add saved_to field per AC3
            envelope["saved_to"] = absolute_path

        return envelope

    except SearchError as e:
        # DYK#10: Explicit SEMANTIC mode failures (no embeddings, etc.)
        # Message already actionable, pass through
        raise ToolError(str(e)) from None

    except EmbeddingAuthenticationError:
        # DYK#9: Embedding API auth failure
        raise ToolError(
            "Embedding API authentication failed. "
            "Check FS2_AZURE__OPENAI__API_KEY configuration."
        ) from None

    except EmbeddingRateLimitError as e:
        # DYK#9: Embedding API rate limit
        retry_msg = f" Retry after {e.retry_after}s." if e.retry_after else ""
        raise ToolError(
            f"Embedding API rate limited.{retry_msg} Try TEXT/REGEX mode."
        ) from None

    except EmbeddingAdapterError as e:
        # DYK#9: Generic embedding API failure
        raise ToolError(f"Embedding service error: {e}. Try TEXT/REGEX mode.") from None

    except MissingConfigurationError:
        raise ToolError(
            "No configuration found. Run 'fs2 init' to create .fs2/config.yaml"
        ) from None

    except GraphNotFoundError:
        raise ToolError(
            "Graph not found. Run 'fs2 scan' to create the graph."
        ) from None

    except GraphStoreError as e:
        raise ToolError(f"Graph error: {e}. The graph file may be corrupted.") from None

    except ToolError:
        # Re-raise ToolErrors as-is
        raise

    except Exception as e:
        logger.exception("Unexpected error in search tool")
        raise ToolError(f"Unexpected error: {e}") from None


# Register search function as MCP tool with annotations (per T008)
# Per DYK#8: openWorldHint=True because SEMANTIC mode calls embedding APIs
# Per AC8: readOnlyHint=False because save_to_file writes to filesystem
_search_tool = mcp.tool(
    annotations={
        "title": "Search Code",
        "readOnlyHint": False,  # Can write files via save_to_file
        "destructiveHint": False,  # No destructive side effects
        "idempotentHint": True,  # Same inputs return same outputs
        "openWorldHint": True,  # SEMANTIC mode calls external embedding APIs
    }
)(search)


# =============================================================================
# MCP Tools (Phase 3: Documentation - docs_list, docs_get)
# =============================================================================


def docs_list(
    category: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """List available documentation with optional filtering.

    WHEN TO USE: Discover what documentation is available before reading.
    Call this FIRST to browse the catalog, then use docs_get(id) to retrieve content.

    PREREQUISITES: None - documentation is bundled with fs2.

    WORKFLOW:
    1. Use docs_list() to see all available documents
    2. Use docs_list(category="how-to") to filter by category
    3. Use docs_list(tags=["config"]) to filter by tags (OR logic)
    4. Use docs_get(id) with a document ID to retrieve full content

    Args:
        category: Filter by category (exact match). Example: "how-to", "reference".
        tags: Filter by tags (OR logic - docs with ANY matching tag).
              Example: ["agents", "config"].

    Returns:
        Dict with:
        - docs: List of document metadata (id, title, summary, category, tags, path)
        - count: Number of documents returned

    Example:
        >>> docs_list()
        {"docs": [{"id": "agents", "title": "AI Agent Guidance", ...}], "count": 2}

        >>> docs_list(category="how-to")
        {"docs": [{"id": "agents", ...}], "count": 1}

        >>> docs_list(tags=["config", "setup"])
        {"docs": [...], "count": 1}
    """
    import dataclasses

    try:
        service = get_docs_service()
        documents = service.list_documents(category=category, tags=tags)

        # Convert DocMetadata to dicts per DYK-5
        docs_list_result = [dataclasses.asdict(doc) for doc in documents]

        return {
            "docs": docs_list_result,
            "count": len(docs_list_result),
        }

    except Exception as e:
        logger.exception("Unexpected error in docs_list tool")
        raise ToolError(f"Unexpected error: {e}") from None


def docs_get(id: str) -> dict[str, Any] | None:
    """Retrieve complete document content by ID.

    WHEN TO USE: Read full documentation after discovering IDs via docs_list().
    Use after docs_list() to get the complete content of a specific document.

    PREREQUISITES: Call docs_list() first to discover available document IDs.

    Args:
        id: Document identifier from docs_list(). Format: lowercase with hyphens.
            Example: "agents", "configuration-guide".

    Returns:
        Dict with id, title, content, metadata if found.
        None if document ID doesn't exist (not an error).

    Example:
        >>> docs_get(id="agents")
        {"id": "agents", "title": "AI Agent Guidance", "content": "# AI Agent...", "metadata": {...}}

        >>> docs_get(id="nonexistent")
        None  # Not found, use docs_list() to discover IDs
    """
    import dataclasses

    try:
        service = get_docs_service()
        doc = service.get_document(doc_id=id)

        # Return None for not-found per AC5 and DYK-2
        if doc is None:
            return None

        # Convert to response format per DYK-5
        # Flatten top-level fields: id, title, content, metadata
        metadata_dict = dataclasses.asdict(doc.metadata)

        return {
            "id": doc.metadata.id,
            "title": doc.metadata.title,
            "content": doc.content,
            "metadata": metadata_dict,
        }

    except Exception as e:
        logger.exception("Unexpected error in docs_get tool")
        raise ToolError(f"Unexpected error: {e}") from None


# Register docs_list function as MCP tool with annotations (per CF-03)
# Per Critical Finding 03: readOnlyHint=True, idempotentHint=True, openWorldHint=False
_docs_list_tool = mcp.tool(
    annotations={
        "title": "List Documentation",
        "readOnlyHint": True,  # No side effects, pure read
        "destructiveHint": False,  # No destructive operations
        "idempotentHint": True,  # Same inputs always return same outputs
        "openWorldHint": False,  # No external network calls, docs bundled in package
    }
)(docs_list)


# Register docs_get function as MCP tool with annotations (per CF-03)
# Per Critical Finding 03: readOnlyHint=True, idempotentHint=True, openWorldHint=False
_docs_get_tool = mcp.tool(
    annotations={
        "title": "Get Documentation",
        "readOnlyHint": True,  # No side effects, pure read
        "destructiveHint": False,  # No destructive operations
        "idempotentHint": True,  # Same inputs always return same outputs
        "openWorldHint": False,  # No external network calls, docs bundled in package
    }
)(docs_get)
