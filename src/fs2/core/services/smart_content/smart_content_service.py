"""SmartContentService for AI-powered code node summaries.

Provides:
- Single-node smart content generation via LLMService
- Batch processing with asyncio Queue + Worker Pool pattern (Phase 4)
- Hash-based skip logic (AC5) and regeneration (AC6)
- Token-based content truncation (AC13)
- Error handling with graceful degradation (CD07)

Per CD01: Accepts ConfigurationService, extracts config internally.
Per CD03: Returns new CodeNode instances (frozen immutability).
Per CD10: Stateless service - batch processing uses local variables.
Per CD12: Catches domain exceptions only, never SDK exceptions.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from fs2.config.objects import SmartContentConfig
from fs2.core.adapters.exceptions import (
    LLMAuthenticationError,
    LLMContentFilterError,
    LLMRateLimitError,
    TokenCounterError,
)
from fs2.core.services.smart_content.exceptions import SmartContentProcessingError

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.token_counter_adapter import TokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.template_service import TemplateService


logger = logging.getLogger(__name__)


# Minimum content length to warrant LLM processing
# Nodes smaller than this get placeholder text instead of LLM calls
# 50 bytes filters out trivial declarations, empty blocks, etc.
_MIN_CONTENT_LENGTH = 50

# Progress callback interval (user request: every 10 items)
_PROGRESS_INTERVAL = 10


@dataclass(frozen=True)
class SmartContentProgress:
    """Progress information for smart content batch processing.

    Used for callback reporting without exposing implementation details.
    CLI can use this to display progress bars, status messages, etc.
    """

    processed: int
    """Number of nodes successfully processed."""

    total: int
    """Total number of nodes in the batch."""

    skipped: int
    """Number of nodes skipped (hash unchanged)."""

    errors: int
    """Number of nodes that failed processing."""

    @property
    def remaining(self) -> int:
        """Calculate remaining nodes to process."""
        return self.total - self.processed - self.skipped - self.errors


# Type alias for progress callback
# Called with progress info; error_message is set only for error events
ProgressCallback = Callable[[SmartContentProgress, str | None], None]


class SmartContentService:
    """Service for generating AI-powered summaries of code nodes.

    Uses LLMService for generation, TemplateService for prompts, and
    TokenCounterAdapter for truncation decisions.

    Example:
        >>> config = FS2ConfigurationService()
        >>> service = SmartContentService(
        ...     config=config,
        ...     llm_service=LLMService.create(config),
        ...     template_service=TemplateService(config),
        ...     token_counter=TiktokenTokenCounterAdapter(config),
        ... )
        >>> updated_node = await service.generate_smart_content(node)
        >>> print(updated_node.smart_content)
    """

    def __init__(
        self,
        config: ConfigurationService,
        llm_service: LLMService,
        template_service: TemplateService,
        token_counter: TokenCounterAdapter,
    ) -> None:
        """Initialize the service with required dependencies.

        Per CD01: Extracts SmartContentConfig via config.require() internally.

        Args:
            config: ConfigurationService for accessing configuration.
            llm_service: LLMService for AI generation.
            template_service: TemplateService for prompt rendering.
            token_counter: TokenCounterAdapter for token counting.

        Raises:
            ConfigurationError: If SmartContentConfig is not registered.
        """
        self._config = config.require(SmartContentConfig)
        self._llm_service = llm_service
        self._template_service = template_service
        self._token_counter = token_counter

    async def generate_smart_content(self, node: CodeNode) -> CodeNode:
        """Generate smart content for a single code node.

        Implements hash-based skip logic (AC5), regeneration (AC6),
        truncation (AC13), and error handling (CD07).

        Args:
            node: The CodeNode to process.

        Returns:
            A new CodeNode with smart_content and smart_content_hash set.
            Returns the original node unchanged if hash matches (AC5).

        Raises:
            LLMAuthenticationError: Auth failures propagate up (CD07).
            SmartContentProcessingError: Rate limit or other recoverable errors.
        """
        # AC5: Skip if content unchanged
        if self._should_skip(node):
            return node

        # CD08: Skip empty/trivial content
        if self._is_empty_or_trivial(node):
            return self._create_placeholder_node(node)

        # Prepare content (with truncation if needed)
        content = self._prepare_content(node)

        # Build prompt via TemplateService (AC8)
        context = self._build_context(node, content)
        prompt = self._template_service.render_for_category(node.category, context)

        # Call LLM with error handling (CD07)
        smart_content = await self._generate_with_error_handling(node, prompt)

        # Create new node with updated smart_content and hash (CD03)
        return replace(
            node,
            smart_content=smart_content,
            smart_content_hash=node.content_hash,
        )

    def _should_skip(self, node: CodeNode) -> bool:
        """Check if node should skip regeneration (AC5).

        Returns True if:
        - smart_content_hash matches content_hash
        - AND smart_content is already set
        """
        return (
            node.smart_content_hash is not None
            and node.smart_content_hash == node.content_hash
            and node.smart_content is not None
        )

    def _is_empty_or_trivial(self, node: CodeNode) -> bool:
        """Check if content is too short to warrant LLM processing (CD08)."""
        return len(node.content.strip()) < _MIN_CONTENT_LENGTH

    def _create_placeholder_node(self, node: CodeNode) -> CodeNode:
        """Create node with placeholder smart_content for empty/trivial content."""
        return replace(
            node,
            smart_content=f"[Empty content - no summary generated for {node.category} '{node.name or 'anonymous'}']",
            smart_content_hash=node.content_hash,
        )

    def _prepare_content(self, node: CodeNode) -> str:
        """Prepare content for prompt, truncating if needed (AC13)."""
        content = node.content
        try:
            token_count = self._token_counter.count_tokens(content)
        except TokenCounterError as e:
            raise SmartContentProcessingError(
                f"Token counting failed for node {node.node_id}: {e}"
            ) from e
        max_tokens = self._config.max_input_tokens

        if token_count > max_tokens:
            logger.warning(
                "Content truncated for node %s: %d tokens -> %d tokens",
                node.node_id,
                token_count,
                max_tokens,
            )
            # Truncate content (simple approach: truncate characters proportionally)
            # A more sophisticated approach would use token boundaries
            ratio = max_tokens / token_count
            truncate_at = int(len(content) * ratio * 0.9)  # 10% safety margin
            content = content[:truncate_at] + "\n\n[TRUNCATED]"

        return content

    def _build_context(self, node: CodeNode, content: str) -> dict:
        """Build context dictionary for template rendering (AC8)."""
        return {
            "name": node.name or "anonymous",
            "qualified_name": node.qualified_name,
            "category": node.category,
            "ts_kind": node.ts_kind,
            "language": node.language,
            "content": content,
            "signature": node.signature or "",
        }

    async def _generate_with_error_handling(
        self, node: CodeNode, prompt: str
    ) -> str:
        """Call LLM with error handling per CD07."""
        try:
            # Get max_tokens for output from config
            max_output_tokens = self._template_service.resolve_max_tokens(node.category)

            response = await self._llm_service.generate(
                prompt,
                max_tokens=max_output_tokens,
            )

            # Check for content filter FIRST (Azure returns was_filtered=True with empty content)
            if response.was_filtered:
                return "[Content filtered] - summary could not be generated due to content policies"

            content = response.content

            # Check for empty/whitespace response
            if not content or not content.strip():
                raise SmartContentProcessingError(
                    f"LLM returned empty/blank response for node {node.node_id}"
                )

            return content.strip()

        except LLMAuthenticationError:
            # Auth errors must propagate (config issue, batch should fail)
            raise

        except LLMContentFilterError:
            # Content filter exception (raised by some adapters)
            return "[Content filtered] - summary could not be generated due to content policies"

        except LLMRateLimitError as e:
            # Rate limit: log warning and raise recoverable error
            logger.warning(
                "Rate limit hit for node %s: %s",
                node.node_id,
                str(e),
            )
            raise SmartContentProcessingError(
                f"Rate limit exceeded for node {node.node_id}: {e}"
            ) from e

    # =========================================================================
    # Phase 4: Batch Processing with Queue + Worker Pool
    # =========================================================================

    async def process_batch(
        self,
        nodes: list[CodeNode],
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Process multiple nodes in parallel using asyncio Queue + Worker Pool.

        Implements AC7 (batch processing with configurable workers) using the
        pattern from Critical Discovery 06.

        Args:
            nodes: List of CodeNodes to process.
            progress_callback: Optional callback for progress updates.
                Called every 10 items and on errors. Receives SmartContentProgress
                and optional error message (for error events).

        Returns:
            Dict containing:
            - processed: Count of successfully processed nodes
            - skipped: Count of nodes skipped (hash match)
            - errors: List of (node_id, error_message) tuples
            - results: Dict mapping node_id -> updated CodeNode
            - total: Total input nodes

        Note:
            Per CD10 (Stateless Service Design): Uses local variables for queue
            and stats_lock, not instance attributes. This prevents race conditions
            when multiple batches run concurrently on the same service instance.
        """
        # Initialize stats - local variable per CD10
        stats: dict[str, Any] = {
            "processed": 0,
            "skipped": 0,
            "errors": [],
            "results": {},
            "total": len(nodes),
        }

        if not nodes:
            return stats

        # Create queue and lock - local variables per CD10
        queue: asyncio.Queue[CodeNode | None] = asyncio.Queue()
        stats_lock = asyncio.Lock()

        # Pre-filter and enqueue using existing _should_skip (per /didyouknow Insight #2)
        work_count = 0
        for node in nodes:
            if not self._should_skip(node):
                await queue.put(node)
                work_count += 1
            else:
                stats["skipped"] += 1

        if work_count == 0:
            logger.info(
                "Batch complete: 0 processed, %d skipped (all nodes up-to-date)",
                stats["skipped"],
            )
            return stats

        # Cap workers to actual work items (T010: don't spawn idle workers)
        actual_workers = min(self._config.max_workers, work_count)
        logger.info(
            "Starting %d workers for %d items (max_workers=%d)",
            actual_workers,
            work_count,
            self._config.max_workers,
        )

        # Create synchronized workers (T012: asyncio.Event barrier)
        worker_ready_event = asyncio.Event()
        workers_ready = [0]  # Use list for nonlocal mutation

        async def create_synchronized_worker(worker_id: int) -> None:
            """Worker factory with synchronized startup barrier."""
            workers_ready[0] += 1
            if workers_ready[0] >= actual_workers:
                worker_ready_event.set()  # Last worker signals all
            else:
                await worker_ready_event.wait()  # Others wait

            await self._worker_loop(
                worker_id=worker_id,
                queue=queue,
                stats_lock=stats_lock,
                stats=stats,
                progress_callback=progress_callback,
            )

        workers = [
            asyncio.create_task(
                create_synchronized_worker(i),
                name=f"smart-content-worker-{i}",
            )
            for i in range(actual_workers)
        ]

        # SENTINEL SHUTDOWN PATTERN
        # -------------------------
        # Sentinels (None) MUST be enqueued:
        #   1. AFTER all work items (so workers process work first)
        #   2. BEFORE gather() (so workers can receive them)
        # One sentinel per worker ensures all workers exit cleanly.
        for _ in range(actual_workers):
            await queue.put(None)

        # Wait for all workers to complete
        await asyncio.gather(*workers)

        logger.info(
            "Batch complete: %d processed, %d skipped, %d errors",
            stats["processed"],
            stats["skipped"],
            len(stats["errors"]),
        )

        return stats

    async def _worker_loop(
        self,
        worker_id: int,
        queue: asyncio.Queue[CodeNode | None],
        stats_lock: asyncio.Lock,
        stats: dict[str, Any],
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Worker coroutine that processes items from queue.

        Args:
            worker_id: Identifier for this worker (for logging).
            queue: Work queue (passed as param per CD10, not self._queue).
            stats_lock: Lock for thread-safe stats updates.
            stats: Shared stats dict (processed, errors, results).
            progress_callback: Optional callback for progress reporting.
        """
        logger.debug("Worker %d started", worker_id)

        def _make_progress() -> SmartContentProgress:
            """Create progress object from current stats (must hold lock)."""
            return SmartContentProgress(
                processed=stats["processed"],
                total=stats["total"],
                skipped=stats["skipped"],
                errors=len(stats["errors"]),
            )

        while True:
            item = await queue.get()

            if item is None:  # Sentinel for shutdown
                logger.debug("Worker %d received stop signal", worker_id)
                break

            node = item
            logger.debug("Smart content: %s", node.node_id)
            try:
                updated_node = await self.generate_smart_content(node)
                # Log the generated result (truncated for readability)
                if updated_node.smart_content:
                    preview = updated_node.smart_content[:200].replace("\n", " ")
                    if len(updated_node.smart_content) > 200:
                        preview += "..."
                    logger.debug("[%s] %s", node.node_id, preview)

                async with stats_lock:
                    stats["processed"] += 1
                    stats["results"][node.node_id] = updated_node

                    # Progress callback every N items (user request: every 10)
                    if stats["processed"] % _PROGRESS_INTERVAL == 0:
                        remaining = stats["total"] - stats["processed"] - stats["skipped"] - len(stats["errors"])
                        logger.info(
                            "Progress: %d/%d processed, %d remaining",
                            stats["processed"],
                            stats["total"],
                            remaining,
                        )
                        if progress_callback:
                            progress_callback(_make_progress(), None)

            except LLMAuthenticationError:
                # Auth errors should fail the entire batch - re-raise
                raise

            except Exception as e:
                error_msg = f"{node.node_id}: {e}"
                logger.error(
                    "Worker %d error processing %s: %s",
                    worker_id,
                    node.node_id,
                    str(e),
                )
                async with stats_lock:
                    stats["errors"].append((node.node_id, str(e)))
                    # Call callback for errors (immediate feedback)
                    if progress_callback:
                        progress_callback(_make_progress(), error_msg)

        logger.debug("Worker %d finished", worker_id)
