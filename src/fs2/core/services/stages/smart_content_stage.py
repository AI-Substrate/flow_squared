"""SmartContentStage - Pipeline stage for AI-powered smart content generation.

Merges prior smart_content from context.prior_nodes before processing,
then delegates to SmartContentService for batch generation.

Per Subtask 001 (Graph Loading for Smart Content Preservation):
- Merges prior smart_content/smart_content_hash when content_hash matches
- Uses dataclasses.replace() for CodeNode immutability (CD03)
- Handles prior_nodes=None gracefully (first scan case)

Per Phase 6 Tasks:
- T003: Implements SmartContentStage with asyncio.run() bridge
- Uses SmartContentService.process_batch() for generation
- Catches LLMAuthenticationError for fatal exit (re-raised)
- Handles asyncio.run() for sync pipeline calling async service
- Catches nested loop RuntimeError with helpful message

Per Session 2 Critical Insights:
- Insight #1: Simple overlay pattern for results reconstruction
- Insight #2: Stage-level metrics (enriched, preserved, errors)
- Insight #3: Service accessed via context.smart_content_service
- Insight #4: TemplateError caught in worker (handled by service)
"""

import asyncio
import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from fs2.core.adapters.exceptions import LLMAuthenticationError
from fs2.core.models.content_type import ContentType

if TYPE_CHECKING:
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.pipeline_context import PipelineContext


logger = logging.getLogger(__name__)

_SELF_DOCUMENTING_LANGUAGES = frozenset({"markdown", "rst"})


def _is_self_documenting(node: "CodeNode") -> bool:
    """Content section nodes in human-readable languages don't need LLM summarization.

    Markdown and RST sections are already human-written prose — summarizing them
    with an LLM wastes tokens and produces inferior results compared to the
    original text.
    """
    return (
        node.content_type == ContentType.CONTENT
        and node.category == "section"
        and node.language in _SELF_DOCUMENTING_LANGUAGES
    )


class SmartContentStage:
    """Pipeline stage that generates AI-powered smart content for nodes.

    This stage:
    1. Merges prior smart_content from context.prior_nodes (hash-based skip)
    2. Delegates to SmartContentService.process_batch() for generation
    3. Updates context.nodes with results

    The merge step enables hash-based skip logic (AC5/AC6):
    - If node's content_hash matches prior node's content_hash
    - AND prior node has smart_content
    - THEN copy smart_content to fresh node (skip regeneration)

    Usage:
        ```python
        stage = SmartContentStage()
        context = stage.process(context)
        ```

    Note: Full process() implementation pending Phase 6 T003.
    This subtask (001) implements _merge_prior_smart_content() only.
    """

    @property
    def name(self) -> str:
        """Human-readable stage name for logging and metrics."""
        return "smart_content"

    def process(self, context: "PipelineContext") -> "PipelineContext":
        """Generate smart content for nodes in context.

        Per Phase 6 T003: Full implementation with asyncio.run() bridge.

        Args:
            context: Pipeline context with nodes, prior_nodes, and
                     optional smart_content_service.

        Returns:
            Context with nodes updated with smart_content, and metrics set.

        Raises:
            LLMAuthenticationError: If auth fails (fatal, re-raised).
            RuntimeError: If called from async context (helpful message).

        Notes:
            - If smart_content_service is None, skips gracefully (--no-smart-content)
            - Uses asyncio.run() to bridge sync pipeline to async service
            - Metrics: smart_content_enriched, smart_content_preserved, smart_content_errors
        """
        # Step 1: Merge prior smart_content for unchanged nodes (Subtask 001)
        merged_nodes = self._merge_prior_smart_content(
            nodes=context.nodes,
            prior_nodes=context.prior_nodes,
        )
        context.nodes = merged_nodes

        # Count how many were preserved from prior
        preserved_count = sum(
            1 for node in context.nodes if node.smart_content is not None
        )

        # Step 2: Check for service (per Session 2 Insight #3)
        service = context.smart_content_service
        if service is None:
            # No service = --no-smart-content flag or no LLM config
            logger.debug(
                "SmartContentStage: No service, skipping smart content generation"
            )
            context.metrics["smart_content_enriched"] = 0
            context.metrics["smart_content_preserved"] = preserved_count
            context.metrics["smart_content_errors"] = 0
            return context

        # Step 3: Filter nodes that need generation (don't already have smart_content)
        needs_generation = [n for n in context.nodes if n.smart_content is None]

        # Step 3a: Skip self-documenting content (no LLM summary needed)
        pre_filter = len(needs_generation)
        needs_generation = [
            n for n in needs_generation if not _is_self_documenting(n)
        ]
        skipped_self_doc = pre_filter - len(needs_generation)
        if skipped_self_doc > 0:
            logger.info(
                "SmartContentStage: skipped %d self-documenting nodes "
                "(markdown/rst sections — already human-readable)",
                skipped_self_doc,
            )

        # Step 3b: Apply category filter if configured
        smart_content_config = service._config if hasattr(service, "_config") else None
        if (
            smart_content_config
            and getattr(smart_content_config, "enabled_categories", None) is not None
        ):
            enabled = set(smart_content_config.enabled_categories)
            filtered_out = len(needs_generation)
            needs_generation = [n for n in needs_generation if n.category in enabled]
            filtered_out -= len(needs_generation)
            if filtered_out > 0:
                logger.info(
                    "SmartContentStage: filtered %d nodes by category "
                    "(enabled: %s), %d remain",
                    filtered_out,
                    sorted(enabled),
                    len(needs_generation),
                )

        if not needs_generation:
            logger.info(
                "SmartContentStage: All %d nodes already have smart content (preserved)",
                len(context.nodes),
            )
            context.metrics["smart_content_enriched"] = 0
            context.metrics["smart_content_preserved"] = preserved_count
            context.metrics["smart_content_errors"] = 0
            return context

        # Step 4: Call async process_batch via asyncio.run() (sync→async bridge)
        # Create courtesy save wrapper that merges partial results (Plan 036 T04)
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
                    progress_callback=context.smart_content_progress_callback,
                    courtesy_save=courtesy_callback,
                )
            )
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                # Per Insight #3: Helpful error for async context
                raise RuntimeError(
                    "SmartContentStage cannot run inside an existing async event loop. "
                    "This happens when fs2 is called from Jupyter notebooks, async tests, "
                    "or other async contexts. Use --no-smart-content flag or run fs2 "
                    "from a synchronous context (normal CLI)."
                ) from e
            raise
        except LLMAuthenticationError:
            # Auth errors are fatal (per Session 1 Insight #5)
            raise

        # Step 5: Overlay results onto context.nodes (per Session 2 Insight #1)
        # Simple overlay pattern: iterate list, replace if in results dict
        results_dict = batch_result.get("results", {})
        updated_nodes = []
        for node in context.nodes:
            if node.node_id in results_dict:
                updated_nodes.append(results_dict[node.node_id])
            else:
                updated_nodes.append(node)
        context.nodes = updated_nodes

        # Step 6: Record metrics (per Session 2 Insight #2)
        # "enriched" = LLM-generated, "preserved" = copied from prior, "errors" = failed
        context.metrics["smart_content_enriched"] = batch_result.get("processed", 0)
        context.metrics["smart_content_preserved"] = preserved_count
        context.metrics["smart_content_errors"] = len(batch_result.get("errors", []))

        logger.info(
            "SmartContentStage: %d enriched, %d preserved, %d errors",
            context.metrics["smart_content_enriched"],
            context.metrics["smart_content_preserved"],
            context.metrics["smart_content_errors"],
        )

        return context

    def _merge_prior_smart_content(
        self,
        nodes: list["CodeNode"],
        prior_nodes: dict[str, "CodeNode"] | None,
    ) -> list["CodeNode"]:
        """Merge prior smart_content to fresh nodes when content unchanged.

        Per Subtask 001: Graph Loading for Smart Content Preservation.
        This enables hash-based skip logic (AC5/AC6) by preserving
        smart_content across scans for unchanged nodes.

        Args:
            nodes: Fresh nodes from parsing (smart_content=None).
            prior_nodes: Dict mapping node_id -> prior CodeNode with
                         smart_content (or None on first scan).

        Returns:
            List of nodes with smart_content merged where applicable.
            Uses dataclasses.replace() for immutability (CD03).

        Merge Logic:
            For each fresh node:
            1. If prior_nodes is None -> return unchanged
            2. If node_id not in prior_nodes -> return unchanged
            3. If content_hash != prior.content_hash -> return unchanged
            4. If prior.smart_content is None -> return unchanged
            5. Otherwise -> copy smart_content and smart_content_hash
        """
        if prior_nodes is None:
            logger.debug("No prior nodes (first scan), skipping merge")
            return nodes

        merged = []
        merged_count = 0

        for node in nodes:
            prior = prior_nodes.get(node.node_id)

            if prior is None:
                # New file - no prior state
                merged.append(node)
                continue

            if node.content_hash != prior.content_hash:
                # Content changed - must regenerate
                merged.append(node)
                continue

            if prior.smart_content is None:
                # Prior exists but has no smart_content — still carry
                # forward embedding fields so courtesy saves don't lose them
                if prior.embedding is not None:
                    merged_node = replace(
                        node,
                        embedding=prior.embedding,
                        smart_content_embedding=prior.smart_content_embedding,
                        embedding_hash=prior.embedding_hash,
                        embedding_chunk_offsets=prior.embedding_chunk_offsets,
                        leading_context=prior.leading_context,
                    )
                    merged.append(merged_node)
                else:
                    merged.append(node)
                continue

            # Hash matches and prior has smart_content - copy it!
            # Also preserve embedding fields and leading_context so
            # courtesy saves don't erase them before embedding stage runs
            merged_node = replace(
                node,
                smart_content=prior.smart_content,
                smart_content_hash=prior.smart_content_hash,
                embedding=prior.embedding,
                smart_content_embedding=prior.smart_content_embedding,
                embedding_hash=prior.embedding_hash,
                embedding_chunk_offsets=prior.embedding_chunk_offsets,
                leading_context=prior.leading_context,
            )
            merged.append(merged_node)
            merged_count += 1

        if merged_count > 0:
            logger.info(
                "Merged %d/%d nodes with prior smart_content (hash match)",
                merged_count,
                len(nodes),
            )

        return merged
