"""EmbeddingStage - Pipeline stage for vector embedding generation.

Merges prior embeddings from context.prior_nodes before processing,
then delegates to EmbeddingService for batch embedding generation.

Per Phase 4:
- Mirrors SmartContentStage async bridge and metrics behavior
- Uses dataclasses.replace() for CodeNode immutability
- Handles --no-embeddings by skipping gracefully
"""

import asyncio
import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from fs2.core.adapters.exceptions import EmbeddingAuthenticationError, GraphStoreError

if TYPE_CHECKING:
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.pipeline_context import PipelineContext

logger = logging.getLogger(__name__)


class EmbeddingStage:
    """Pipeline stage that generates embeddings for nodes.

    This stage:
    1. Merges prior embeddings from context.prior_nodes (hash-based skip)
    2. Delegates to EmbeddingService.process_batch() for generation
    3. Updates context.nodes with results
    """

    @property
    def name(self) -> str:
        """Human-readable stage name for logging and metrics."""
        return "embedding"

    def process(self, context: "PipelineContext") -> "PipelineContext":
        """Generate embeddings for nodes in context.

        Args:
            context: Pipeline context with nodes, prior_nodes, and optional
                     embedding_service.

        Returns:
            Context with nodes updated with embeddings, and metrics set.

        Raises:
            EmbeddingAuthenticationError: If auth fails (fatal, re-raised).
            RuntimeError: If called from async context (helpful message).
        """
        # Step 1: Merge prior embeddings for unchanged nodes
        merged_nodes = self._merge_prior_embeddings(
            nodes=context.nodes,
            prior_nodes=context.prior_nodes,
        )
        context.nodes = merged_nodes

        preserved_count = sum(1 for node in context.nodes if node.embedding is not None)

        service = context.embedding_service
        if service is None:
            logger.debug("EmbeddingStage: No service, skipping embedding generation")
            context.metrics["embedding_enriched"] = 0
            context.metrics["embedding_preserved"] = preserved_count
            context.metrics["embedding_errors"] = 0
            return context

        current_metadata = service.get_metadata()
        context.metrics["embedding_metadata"] = current_metadata

        if context.graph_store is not None:
            try:
                prior_metadata = context.graph_store.get_metadata()
            except GraphStoreError:
                prior_metadata = None

            mismatch = self._detect_metadata_mismatch(prior_metadata, current_metadata)
            if mismatch:
                message = f"Embedding metadata mismatch: {mismatch}"
                has_dim_mismatch = "embedding_dimensions" in mismatch

                if has_dim_mismatch and not context.force_embeddings:
                    # DYK-2: Block scan on dimension mismatch unless --force
                    error_msg = (
                        f"{message}. "
                        "Dimension mismatch will produce mixed-dimension embeddings "
                        "that break search. Run `fs2 scan --embed --force` to "
                        "re-embed all nodes with the new dimensions."
                    )
                    context.errors.append(error_msg)
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

                if has_dim_mismatch and context.force_embeddings:
                    # DYK-2: Force mode — clear all existing embeddings
                    # so hash-based skip doesn't preserve old dimensions
                    logger.warning(
                        f"{message}. --force: clearing all existing embeddings "
                        "for re-generation with new dimensions."
                    )
                    import dataclasses

                    context.nodes = [
                        dataclasses.replace(
                            node,
                            embedding=None,
                            smart_content_embedding=None,
                            embedding_hash=None,
                            embedding_chunk_offsets=None,
                        )
                        for node in context.nodes
                    ]
                else:
                    context.errors.append(message)
                    logger.warning(message)

        needs_generation = [n for n in context.nodes if n.embedding is None]
        if not needs_generation:
            logger.info(
                "EmbeddingStage: All %d nodes already have embeddings (preserved)",
                len(context.nodes),
            )
            context.metrics["embedding_enriched"] = 0
            context.metrics["embedding_preserved"] = preserved_count
            context.metrics["embedding_errors"] = 0
            return context

        # Create courtesy save wrapper that merges partial results (Plan 036 T05)
        courtesy_callback = None
        if context.courtesy_save is not None:
            pre_batch_nodes = list(context.nodes)

            def _courtesy_save_wrapper(partial_results: dict) -> None:
                """Merge partial results into context.nodes and courtesy save."""
                context.nodes = [
                    partial_results.get(n.node_id, n) for n in pre_batch_nodes
                ]
                context.courtesy_save()

            courtesy_callback = _courtesy_save_wrapper

        try:
            batch_result = asyncio.run(
                service.process_batch(
                    needs_generation,
                    progress_callback=context.embedding_progress_callback,
                    courtesy_save=courtesy_callback,
                )
            )
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                raise RuntimeError(
                    "EmbeddingStage cannot run inside an existing async event loop. "
                    "This happens when fs2 is called from Jupyter notebooks, async tests, "
                    "or other async contexts. Use --no-embeddings flag or run fs2 "
                    "from a synchronous context (normal CLI)."
                ) from e
            raise
        except EmbeddingAuthenticationError:
            raise

        results_dict = batch_result.get("results", {})
        updated_nodes = []
        for node in context.nodes:
            if node.node_id in results_dict:
                updated_nodes.append(results_dict[node.node_id])
            else:
                updated_nodes.append(node)
        context.nodes = updated_nodes

        context.metrics["embedding_enriched"] = batch_result.get("processed", 0)
        context.metrics["embedding_preserved"] = preserved_count
        context.metrics["embedding_errors"] = len(batch_result.get("errors", []))

        logger.info(
            "EmbeddingStage: %d enriched, %d preserved, %d errors",
            context.metrics["embedding_enriched"],
            context.metrics["embedding_preserved"],
            context.metrics["embedding_errors"],
        )

        return context

    def _merge_prior_embeddings(
        self,
        nodes: list["CodeNode"],
        prior_nodes: dict[str, "CodeNode"] | None,
    ) -> list["CodeNode"]:
        """Merge prior embeddings to fresh nodes when content unchanged.

        Args:
            nodes: Fresh nodes from parsing (embedding=None).
            prior_nodes: Dict mapping node_id -> prior CodeNode.

        Returns:
            List of nodes with embeddings merged where applicable.
        """
        if prior_nodes is None:
            logger.debug("No prior nodes (first scan), skipping embedding merge")
            return nodes

        merged = []
        merged_count = 0

        for node in nodes:
            prior = prior_nodes.get(node.node_id)
            if prior is None:
                merged.append(node)
                continue

            if prior.embedding_hash != node.content_hash:
                merged.append(node)
                continue

            if prior.embedding is None and prior.smart_content_embedding is None:
                merged.append(node)
                continue

            merged_node = replace(
                node,
                embedding=prior.embedding,
                smart_content_embedding=prior.smart_content_embedding,
                embedding_hash=prior.embedding_hash,
            )
            merged.append(merged_node)
            merged_count += 1

        if merged_count > 0:
            logger.info(
                "Merged %d/%d nodes with prior embeddings (hash match)",
                merged_count,
                len(nodes),
            )

        return merged

    def _detect_metadata_mismatch(
        self,
        prior_metadata: dict[str, object] | None,
        current_metadata: dict[str, object],
    ) -> str | None:
        """Detect mismatch between prior graph metadata and current config."""
        if not prior_metadata:
            return None

        mismatches = []
        for key in ("embedding_model", "embedding_dimensions", "chunk_params"):
            if key in prior_metadata and prior_metadata.get(
                key
            ) != current_metadata.get(key):
                mismatches.append(
                    f"{key} (graph={prior_metadata.get(key)}, current={current_metadata.get(key)})"
                )

        if mismatches:
            return "; ".join(mismatches)
        return None
