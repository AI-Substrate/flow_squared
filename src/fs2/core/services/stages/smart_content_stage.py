"""SmartContentStage - Pipeline stage for AI-powered smart content generation.

Merges prior smart_content from context.prior_nodes before processing,
then delegates to SmartContentService for batch generation.

Per Subtask 001 (Graph Loading for Smart Content Preservation):
- Merges prior smart_content/smart_content_hash when content_hash matches
- Uses dataclasses.replace() for CodeNode immutability (CD03)
- Handles prior_nodes=None gracefully (first scan case)

Per Phase 6 Tasks:
- T003: Implements SmartContentStage with merge logic
- Uses SmartContentService.process_batch() for generation
- Catches LLMAuthenticationError for fatal exit
- Handles asyncio.run() for sync pipeline calling async service
"""

import logging
from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.pipeline_context import PipelineContext


logger = logging.getLogger(__name__)


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

        Args:
            context: Pipeline context with nodes and optional prior_nodes.

        Returns:
            Context with nodes updated with smart_content.

        Note:
            Full implementation pending Phase 6 T003.
            Currently only performs merge logic from Subtask 001.
        """
        # Step 1: Merge prior smart_content for unchanged nodes (Subtask 001)
        merged_nodes = self._merge_prior_smart_content(
            nodes=context.nodes,
            prior_nodes=context.prior_nodes,
        )
        context.nodes = merged_nodes

        # Step 2: Generate smart_content for remaining nodes (Phase 6 T003)
        # TODO: Call SmartContentService.process_batch() here
        # For now, just log what we'd do
        needs_generation = [n for n in context.nodes if n.smart_content is None]
        logger.info(
            "SmartContentStage: %d nodes merged from prior, %d need generation",
            len(context.nodes) - len(needs_generation),
            len(needs_generation),
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
                # Prior exists but has no smart_content
                merged.append(node)
                continue

            # Hash matches and prior has smart_content - copy it!
            merged_node = replace(
                node,
                smart_content=prior.smart_content,
                smart_content_hash=prior.smart_content_hash,
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
