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

        Process:
        1. Skip non-callable nodes (only methods/functions can be referenced)
        2. Extract file path from node_id
        3. Call LSP get_references to find "who calls me"
        4. Upgrade edges to symbol-level using find_node_at_line()

        NOTE: We only use get_references (who calls me), not get_definition (what do I call).
        The naive line-scanning approach for get_definition was removed because:
        - It generated hundreds of thousands of useless LSP queries
        - 99%+ returned None (querying random column positions)
        - Proper "what do I call" detection requires tree-sitter call expression analysis

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
        try:
            # Get references to this symbol (who calls me?)
            # Query at definition line to find callers
            reference_edges = self._lsp_adapter.get_references(
                file_path=file_path,
                line=node.start_line,
                column=0,
            )
            raw_edges.extend(reference_edges)

        except Exception as e:
            logger.debug("LSP query failed for %s: %s", node.node_id, e)
            return []

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
        # Extract source file from source_node_id
        source_parts = edge.source_node_id.split(":", 2)
        if len(source_parts) < 2:
            return None
        source_file = source_parts[1]

        # Extract target file from target_node_id
        target_parts = edge.target_node_id.split(":", 2)
        if len(target_parts) < 2:
            return None
        target_file = target_parts[1]

        # Resolve source to symbol-level
        source_node_id = edge.source_node_id  # Default to original
        if edge.source_line is not None:
            source_symbol = find_node_at_line(all_nodes, edge.source_line, source_file)
            if source_symbol is not None:
                source_node_id = source_symbol.node_id

        # Resolve target to symbol-level
        target_node_id = edge.target_node_id  # Default to original
        if edge.target_line is not None:
            target_symbol = find_node_at_line(all_nodes, edge.target_line, target_file)
            if target_symbol is not None:
                target_node_id = target_symbol.node_id
            else:
                # Target line has no symbol - filter out this edge
                logger.debug(
                    "No symbol at target line %d in %s, filtering edge",
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
