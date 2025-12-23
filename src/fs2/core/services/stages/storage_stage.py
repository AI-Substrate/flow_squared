"""StorageStage - Pipeline stage for graph persistence.

Wraps GraphStore repository to persist nodes and edges.
Uses node.parent_node_id to create parent-child edges.

Per Alignment Brief:
- Validates graph_store not None (raises ValueError)
- Uses node.parent_node_id for edges (set by ASTParser during traversal)
- Calls add_node for each node
- Calls add_edge for nodes with parent_node_id
- Calls save with context.graph_path
- Catches GraphStoreError, appends to context.errors
- Records metrics: storage_nodes, storage_edges
"""

from typing import TYPE_CHECKING

from fs2.core.adapters.exceptions import GraphStoreError

if TYPE_CHECKING:
    from fs2.core.services.pipeline_context import PipelineContext


class StorageStage:
    """Pipeline stage that persists nodes to GraphStore.

    This stage:
    - Validates graph_store is present in context
    - Adds all nodes to the graph store
    - Creates edges using node.parent_node_id
    - Saves the graph to context.graph_path
    - Catches GraphStoreError and appends to context.errors
    - Records storage_nodes and storage_edges in context.metrics
    """

    @property
    def name(self) -> str:
        """Human-readable stage name for logging and metrics."""
        return "storage"

    def process(self, context: "PipelineContext") -> "PipelineContext":
        """Store nodes and edges in the graph store.

        Args:
            context: Pipeline context with graph_store repository and nodes.

        Returns:
            Context (unchanged, but graph persisted).

        Raises:
            ValueError: If context.graph_store is None.
        """
        # Validate precondition
        if context.graph_store is None:
            raise ValueError(
                "StorageStage requires graph_store to be set in context. "
                "Ensure ScanPipeline injects the GraphStore repository."
            )

        edge_count = 0

        # Add all nodes
        for node in context.nodes:
            context.graph_store.add_node(node)

        # Create edges based on parent_node_id
        for node in context.nodes:
            if node.parent_node_id is not None:
                context.graph_store.add_edge(node.parent_node_id, node.node_id)
                edge_count += 1

        # Record metrics
        context.metrics["storage_nodes"] = len(context.nodes)
        context.metrics["storage_edges"] = edge_count

        embedding_metadata = context.metrics.get("embedding_metadata")
        if embedding_metadata:
            context.graph_store.set_metadata(embedding_metadata)

        # Save graph
        try:
            context.graph_store.save(context.graph_path)
        except GraphStoreError as e:
            context.errors.append(str(e))

        return context
