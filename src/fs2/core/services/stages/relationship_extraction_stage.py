"""RelationshipExtractionStage - Pipeline stage for cross-file relationship extraction.

Orchestrates relationship extractors to detect cross-file references and method calls.
Populates context.relationships with list[CodeEdge] for downstream StorageStage.

Per Alignment Brief:
- Stage position: After ParsingStage, before SmartContentStage
- Orchestrates: NodeIdDetector, RawFilenameDetector, LspAdapter (optional)
- Graceful degradation: Logs WARNING when lsp_adapter=None (DYK-4)
- Deduplication: Reuses TextReferenceExtractor._deduplicate_edges() (DYK-5)
- Records metrics: relationship_extraction_count

Per Critical Insights:
- DYK-4: Log WARNING when LSP skipped for user visibility
- DYK-5: Reuse existing _deduplicate_edges() from TextReferenceExtractor
- T016: Symbol-level resolution via find_node_at_line() post-processing
"""

import logging
from typing import TYPE_CHECKING, Any

from tree_sitter_language_pack import get_parser

from fs2.core.models.code_edge import CodeEdge
from fs2.core.services.relationship_extraction.symbol_resolver import find_node_at_line
from fs2.core.services.relationship_extraction.text_reference_extractor import (
    TextReferenceExtractor,
)

if TYPE_CHECKING:
    from fs2.core.adapters.lsp_adapter import LspAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)


# ==============================================================================
# Call Expression Extraction (Phase 8 Subtask 001)
# ==============================================================================

# Call node types by language
# Per research dossier: each language has specific node type for function/method calls
CALL_NODE_TYPES: dict[str, str] = {
    "python": "call",
    "typescript": "call_expression",
    "javascript": "call_expression",
    "tsx": "call_expression",
    "go": "call_expression",
    "csharp": "invocation_expression",  # tree-sitter-language-pack uses 'csharp'
}

# Method/attribute access node types by language
# These are the nodes that represent obj.method access patterns
METHOD_ACCESS_TYPES: dict[str, str] = {
    "python": "attribute",
    "typescript": "member_expression",
    "javascript": "member_expression",
    "tsx": "member_expression",
    "go": "selector_expression",
    "csharp": "member_access_expression",  # tree-sitter-language-pack uses 'csharp'
}

# Stdlib/external package path patterns by language
# Used to filter out calls to standard library and external packages
STDLIB_PATTERNS: dict[str, list[str]] = {
    "python": ["typeshed", "site-packages", ".pyenv", "/python3.", "builtins.pyi"],
    "typescript": ["node_modules", "@types/", "typescript/lib/"],
    "javascript": ["node_modules", "@types/"],
    "tsx": ["node_modules", "@types/", "typescript/lib/"],
    "go": ["/go/src/", "pkg/mod/", "GOROOT"],
    "csharp": [".nuget", "dotnet/shared", "Program Files"],
}


def extract_call_positions(content: str, language: str) -> list[tuple[int, int]]:
    """Extract all call expression positions from source code.

    Uses tree-sitter to parse the AST and find call nodes.
    For method calls (obj.method()), returns the method name position,
    not the receiver position. This is critical because:
    - LSP at receiver position → resolves to variable assignment
    - LSP at method position → resolves to method definition

    Args:
        content: Source code content
        language: Tree-sitter language name (python, typescript, go, c_sharp, etc.)

    Returns:
        List of (line, column) tuples - both 0-indexed
        For method calls, position points to method name, not receiver

    Example:
        >>> extract_call_positions("auth.login()", "python")
        [(0, 5)]  # Position at "login", not "auth"

        >>> extract_call_positions("foo(bar())", "python")
        [(0, 0), (0, 4)]  # Both calls
    """
    if not content or language not in CALL_NODE_TYPES:
        return []

    call_type = CALL_NODE_TYPES[language]
    method_type = METHOD_ACCESS_TYPES.get(language)

    try:
        parser = get_parser(language)  # type: ignore[arg-type]
    except Exception:
        # Language not supported by tree-sitter-language-pack
        logger.debug("No parser available for language: %s", language)
        return []

    content_bytes = content.encode("utf-8")
    tree = parser.parse(content_bytes)

    positions: list[tuple[int, int]] = []

    def get_query_position(call_node: "Node") -> tuple[int, int]:  # type: ignore[name-defined]  # noqa: F821
        """Get position to query LSP for a call node.

        For method calls (obj.method()), returns method name position.
        For simple calls (func()), returns function name position.

        The callee is typically the first child of the call node.
        """
        # Find the callee child
        callee = None
        for child in call_node.children:
            # Skip argument lists and parentheses
            if child.type in ("argument_list", "arguments", "(", ")"):
                continue
            callee = child
            break

        if callee is None:
            return (call_node.start_point[0], call_node.start_point[1])

        # Check if callee is a method access (obj.method)
        if method_type and callee.type == method_type:
            # Method call: find the method name (rightmost identifier)
            method_name = _find_method_identifier(callee, language)
            if method_name:
                return (method_name.start_point[0], method_name.start_point[1])

        # Simple call or unknown pattern: use callee start
        return (callee.start_point[0], callee.start_point[1])

    def visit(node: "Node") -> None:  # type: ignore[name-defined]  # noqa: F821
        """Recursively visit nodes to find calls."""
        if node.type == call_type and node.is_named:
            pos = get_query_position(node)
            positions.append(pos)

        # Recurse into children
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return positions


def _find_method_identifier(access_node: "Node", language: str) -> "Node | None":  # type: ignore[name-defined]  # noqa: F821
    """Find the method/field identifier in a method access node.

    For different languages, the method name is stored differently:
    - Python attribute: .name field or second identifier child
    - TypeScript member_expression: property child
    - Go selector_expression: field child
    - C# member_access_expression: name child

    Args:
        access_node: The method access node (attribute, member_expression, etc.)
        language: Language name

    Returns:
        The identifier node for the method name, or None if not found
    """
    # Try common patterns across languages

    # Pattern 1: Python attribute - has "attribute" field
    if language == "python":
        # Python attribute node: attribute.name is the method identifier
        # But tree-sitter Python doesn't expose field names the same way
        # The structure is: attribute > [object, ".", name]
        # So we find the last identifier
        for child in reversed(access_node.children):
            if child.type == "identifier":
                return child

    # Pattern 2: TypeScript/JS member_expression
    elif language in ("typescript", "javascript", "tsx"):
        # member_expression > [object, ".", property_identifier]
        for child in reversed(access_node.children):
            if child.type in ("property_identifier", "identifier"):
                return child

    # Pattern 3: Go selector_expression
    elif language == "go":
        # selector_expression > [operand, ".", field_identifier]
        for child in reversed(access_node.children):
            if child.type == "field_identifier":
                return child

    # Pattern 4: C# member_access_expression
    elif language == "csharp":
        # member_access_expression > [expression, ".", name (identifier)]
        for child in reversed(access_node.children):
            if child.type == "identifier":
                return child

    # Fallback: return last identifier child
    for child in reversed(access_node.children):
        if "identifier" in child.type:
            return child

    return None


def is_stdlib_target(target_path: str, language: str) -> bool:
    """Check if an LSP definition target is a stdlib or external package.

    Args:
        target_path: Path from LSP response (may be absolute)
        language: Language name for pattern lookup

    Returns:
        True if target is stdlib/external (should be filtered), False otherwise
    """
    patterns = STDLIB_PATTERNS.get(language, [])
    return any(pattern in target_path for pattern in patterns)


class RelationshipExtractionStage:
    """Pipeline stage that extracts cross-file relationships.

    This stage:
    - Validates context has nodes to process
    - Runs TextReferenceExtractor for node_id and filename patterns
    - Runs LspAdapter for cross-file method calls (if available)
    - Deduplicates edges (highest confidence wins)
    - Validates targets exist in graph (deferred to storage)
    - Populates context.relationships
    - Records relationship_extraction_count in context.metrics

    Per DYK-4: Logs WARNING when LSP is not available for visibility.
    Per DYK-5: Reuses TextReferenceExtractor._deduplicate_edges().
    """

    def __init__(
        self,
        lsp_adapter: "LspAdapter | None" = None,
    ) -> None:
        """Initialize stage with optional LSP adapter.

        Args:
            lsp_adapter: Optional LspAdapter for cross-file method calls.
                         If None, only text-based extraction is performed.
        """
        self._lsp_adapter = lsp_adapter
        self._text_extractor = TextReferenceExtractor()

    @property
    def name(self) -> str:
        """Human-readable stage name for logging and metrics."""
        return "relationship_extraction"

    def process(self, context: "PipelineContext") -> "PipelineContext":
        """Extract relationships from nodes in context.

        Args:
            context: Pipeline context with nodes from ParsingStage.

        Returns:
            Context with relationships populated and metrics set.

        Notes:
            - If lsp_adapter is None, logs WARNING and uses text extractors only
            - Deduplication uses existing TextReferenceExtractor algorithm
            - All extractor errors are collected, not raised
        """
        # Initialize relationships
        all_edges: list[CodeEdge] = []

        # Check for LSP availability (DYK-4: Log warning if unavailable)
        if self._lsp_adapter is None:
            logger.warning(
                "LSP adapter not available, skipping cross-file method call extraction. "
                "Only text-based references (node_id patterns, filenames) will be detected."
            )

        # Skip processing if no nodes
        if not context.nodes:
            logger.debug("RelationshipExtractionStage: No nodes to process")
            context.relationships = []
            context.metrics["relationship_extraction_count"] = 0
            return context

        # Process each node
        for node in context.nodes:
            # Skip nodes without content
            if node.content is None:
                continue

            # Extract text-based references (always runs)
            try:
                text_edges = self._text_extractor.extract(
                    source_file=node.node_id,
                    content=node.content,
                )
                all_edges.extend(text_edges)
            except Exception as e:
                logger.warning(
                    "Text extraction failed for %s: %s",
                    node.node_id,
                    str(e),
                )
                context.errors.append(f"Text extraction failed for {node.node_id}: {e}")

            # Extract LSP-based references (if adapter available)
            if self._lsp_adapter is not None:
                try:
                    lsp_edges = self._extract_lsp_relationships(node, context.nodes)
                    all_edges.extend(lsp_edges)
                except Exception as e:
                    # Graceful degradation: Log and continue
                    logger.warning(
                        "LSP extraction failed for %s: %s",
                        node.node_id,
                        str(e),
                    )
                    # Don't add to errors - LSP failures are expected when servers unavailable

        # Deduplicate edges using existing algorithm (DYK-5)
        deduplicated = self._text_extractor._deduplicate_edges(all_edges)

        # Build set of known node_ids for validation
        known_node_ids = self._build_node_id_set(context.nodes)

        # Validate targets and filter invalid edges
        validated = self._validate_targets(deduplicated, known_node_ids)

        # Filter self-references (A -> A is meaningless)
        filtered = self._filter_self_references(validated)

        # Set context fields
        context.relationships = filtered
        context.metrics["relationship_extraction_count"] = len(filtered)

        logger.info(
            "RelationshipExtractionStage: Extracted %d edges (%d before dedup, %d after validation)",
            len(filtered),
            len(all_edges),
            len(deduplicated),
        )

        return context

    def _build_node_id_set(self, nodes: "list[Any]") -> set[str]:
        """Build a set of known node IDs from context nodes.

        Args:
            nodes: List of CodeNode instances.

        Returns:
            Set of node_id strings for O(1) lookup.
        """
        node_ids: set[str] = set()
        for node in nodes:
            node_ids.add(node.node_id)
            # Also add file-level node_id if this is a child node
            # This allows symbol-level targets to resolve to file-level nodes
            if hasattr(node, "file_path") and node.file_path:
                node_ids.add(f"file:{node.file_path}")
        return node_ids

    def _validate_targets(
        self, edges: list[CodeEdge], known_node_ids: set[str]
    ) -> list[CodeEdge]:
        """Filter edges pointing to non-existent targets.

        Args:
            edges: List of edges to validate.
            known_node_ids: Set of valid target node_ids.

        Returns:
            List of edges where target exists in known_node_ids.
        """
        valid_edges: list[CodeEdge] = []
        for edge in edges:
            target = edge.target_node_id
            # Check exact match first
            if target in known_node_ids:
                valid_edges.append(edge)
                continue
            # For symbol-level targets (method:X, class:X), check if file exists
            if ":" in target:
                # Extract file path from target like "method:src/auth.py:ClassName.method"
                parts = target.split(":", 2)
                if len(parts) >= 2:
                    file_path = parts[1]
                    # Check if file:path exists
                    file_node_id = f"file:{file_path}"
                    if file_node_id in known_node_ids:
                        valid_edges.append(edge)
                        continue
            # Edge filtered - target doesn't exist
            logger.debug("Filtering edge to non-existent target: %s", target)
        return valid_edges

    def _filter_self_references(self, edges: list[CodeEdge]) -> list[CodeEdge]:
        """Filter out self-referencing edges (A -> A).

        Args:
            edges: List of edges to filter.

        Returns:
            List of edges where source != target.
        """
        return [e for e in edges if e.source_node_id != e.target_node_id]

    def _extract_lsp_relationships(
        self, node: "CodeNode", all_nodes: list["CodeNode"]
    ) -> list[CodeEdge]:
        """Extract relationships using LSP adapter with symbol-level resolution.

        Per T016: Uses find_node_at_line() to upgrade file-level edges to symbol-level.
        Per Subtask 001: Now uses tree-sitter call extraction for get_definition.

        Process:
        1. Skip non-callable nodes (only methods/functions can be referenced)
        2. Extract file path from node_id
        3. Call LSP get_references to find "who calls me"
        4. Extract call positions from node.content using tree-sitter
        5. Call LSP get_definition at each call position to find "what do I call"
        6. Filter stdlib/external package targets
        7. Upgrade edges to symbol-level using find_node_at_line()

        Args:
            node: CodeNode to extract relationships from.
            all_nodes: All nodes in context for symbol resolution.

        Returns:
            List of CodeEdge instances with symbol-level node IDs.
        """
        if self._lsp_adapter is None:
            return []

        # Only process callable nodes (methods/functions) that can be called
        if node.category not in ("callable", "method", "function"):
            return []

        # Extract file path from node_id (format: "category:path:name")
        parts = node.node_id.split(":", 2)
        if len(parts) < 2:
            return []
        file_path = parts[1]

        raw_edges: list[CodeEdge] = []

        # =====================================================================
        # Part 1: get_references (who calls me?)
        # =====================================================================
        try:
            # Query at definition line to find callers
            # Note: LSP expects 0-indexed lines, CodeNode.start_line is 1-indexed
            reference_edges = self._lsp_adapter.get_references(
                file_path=file_path,
                line=node.start_line - 1,  # Convert 1-indexed to 0-indexed
                column=0,
            )
            raw_edges.extend(reference_edges)
        except Exception as e:
            logger.debug("LSP get_references failed for %s: %s", node.node_id, e)

        # =====================================================================
        # Part 2: get_definition at call sites (what do I call?)
        # Per Subtask 001: Extract call positions from tree-sitter AST
        # =====================================================================
        try:
            # Extract call positions from node content using tree-sitter
            # Returns list of (rel_line, col) tuples, 0-indexed relative to content
            call_positions = extract_call_positions(node.content, node.language)

            for rel_line, col in call_positions:
                # Convert relative position to file-level position
                # node.start_line is 1-indexed, rel_line is 0-indexed
                # LSP expects 0-indexed: file_line = (node.start_line - 1) + rel_line
                file_line = (node.start_line - 1) + rel_line

                try:
                    # Query LSP for definition at call site
                    definition_edges = self._lsp_adapter.get_definition(
                        file_path=file_path,
                        line=file_line,
                        column=col,
                    )

                    # Filter stdlib/external package targets
                    for edge in definition_edges:
                        target_path = edge.target_node_id
                        if is_stdlib_target(target_path, node.language):
                            logger.debug("Filtering stdlib target: %s", target_path)
                            continue

                        # Update source to be this node (the caller)
                        # The edge from get_definition has source as the file where
                        # we queried, but we want source to be the node doing the calling
                        updated_edge = CodeEdge(
                            source_node_id=node.node_id,
                            target_node_id=edge.target_node_id,
                            edge_type=edge.edge_type,
                            confidence=edge.confidence,
                            source_line=node.start_line + rel_line,  # 1-indexed
                            target_line=edge.target_line,
                            resolution_rule="lsp:definition",
                        )
                        raw_edges.append(updated_edge)
                        logger.debug(
                            "Added get_definition edge: %s -> %s (target_line=%s)",
                            updated_edge.source_node_id,
                            updated_edge.target_node_id,
                            updated_edge.target_line,
                        )

                except Exception as e:
                    logger.debug(
                        "LSP get_definition failed at %s:%d:%d: %s",
                        file_path,
                        file_line,
                        col,
                        e,
                    )

        except Exception as e:
            logger.debug("Call extraction failed for %s: %s", node.node_id, e)

        # Upgrade edges to symbol-level using find_node_at_line
        upgraded_edges: list[CodeEdge] = []
        for edge in raw_edges:
            upgraded = self._upgrade_edge_to_symbol_level(edge, all_nodes)
            if upgraded is not None:
                upgraded_edges.append(upgraded)

        return upgraded_edges

    def _upgrade_edge_to_symbol_level(
        self, edge: CodeEdge, all_nodes: list["CodeNode"]
    ) -> CodeEdge | None:
        """Upgrade a file-level edge to symbol-level using find_node_at_line.

        Per T016: Post-process LSP edges to resolve file:path to method:path:name.

        Args:
            edge: Edge with file-level node_ids and source_line/target_line.
            all_nodes: All nodes for symbol resolution.

        Returns:
            Upgraded edge with symbol-level node_ids, or None if resolution fails.
        """
        # Extract target file from target_node_id
        target_parts = edge.target_node_id.split(":", 2)
        if len(target_parts) < 2:
            return None
        target_file = target_parts[1]

        # Resolve source to symbol-level (only if file-level)
        source_node_id = edge.source_node_id  # Default to original
        source_parts = edge.source_node_id.split(":", 2)
        if len(source_parts) >= 2 and source_parts[0] == "file":
            # Only re-resolve file-level sources (from get_references)
            source_file = source_parts[1]
            if edge.source_line is not None:
                # edge.source_line from LSP is 0-indexed; find_node_at_line expects 1-indexed
                source_line_1idx = edge.source_line + 1
                source_symbol = find_node_at_line(
                    all_nodes, source_line_1idx, source_file
                )
                if source_symbol is not None:
                    source_node_id = source_symbol.node_id
        # else: source is already symbol-level (from get_definition), keep it

        # Resolve target to symbol-level
        target_node_id = edge.target_node_id  # Default to original
        if edge.target_line is not None:
            # edge.target_line from LSP is 0-indexed; find_node_at_line expects 1-indexed
            target_line_1idx = edge.target_line + 1
            target_symbol = find_node_at_line(all_nodes, target_line_1idx, target_file)
            if target_symbol is not None:
                target_node_id = target_symbol.node_id
            else:
                # Target line has no symbol - filter out this edge
                logger.debug(
                    "No symbol at target line %d (0-idx=%d) in %s, filtering edge",
                    target_line_1idx,
                    edge.target_line,
                    target_file,
                )
                return None

        # Create upgraded edge
        return CodeEdge(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge.edge_type,
            confidence=edge.confidence,
            source_line=edge.source_line,
            target_line=edge.target_line,
            resolution_rule=edge.resolution_rule,
        )
