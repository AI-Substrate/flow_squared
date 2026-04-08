"""EmbeddingService for generating vector embeddings of code nodes.

Provides:
- Content-type aware chunking (code=400, docs=800, smart_content=8000 tokens)
- API-level batch processing (FlowSpace pattern)
- Hash-based skip logic for incremental updates
- Rate limit coordination across batches
- Progress reporting callback

Per CD01: Accepts EmbeddingConfig directly (not ConfigurationService).
Per CD03: Returns new CodeNode instances (frozen immutability).
Per CD10: Stateless service - batch processing uses local variables.
Per DYK-1: ChunkItem tracks (node_id, chunk_index, text) for reassembly.
Per DYK-2: Unified batching for both raw and smart_content embeddings.
Per DYK-5: Inline conditional for ContentType → ChunkConfig mapping.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from fs2.config.objects import EmbeddingConfig
from fs2.core.models.content_type import ContentType
from fs2.core.utils.hash import compute_content_hash

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.embedding_adapter import EmbeddingAdapter
    from fs2.core.adapters.token_counter_adapter import TokenCounterAdapter
    from fs2.core.models.code_node import CodeNode


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChunkItem:
    """Immutable data structure for tracking chunks through batching pipeline.

    Per DYK-1: Tracks (node_id, chunk_index, text) for reassembly after
    embed_batch() returns embeddings.

    Per DYK-2: is_smart_content flag distinguishes raw content chunks from
    AI-generated description chunks for dual embedding storage.

    Per Phase 0 (Chunk Offset Tracking): Optional start_line/end_line track
    which source lines each chunk spans, enabling semantic search to report
    accurate line ranges (not just full node range).

    Attributes:
        node_id: Original CodeNode.node_id for reassembly.
        chunk_index: Position in chunk sequence (0, 1, 2, ...).
        text: Chunk content to embed.
        is_smart_content: True for smart_content chunks (default: False).
        start_line: First line of content in this chunk (1-indexed, optional).
        end_line: Last line of content in this chunk (1-indexed, optional).
    """

    node_id: str
    chunk_index: int
    text: str
    is_smart_content: bool = False
    start_line: int | None = None
    end_line: int | None = None


class EmbeddingService:
    """Service for generating vector embeddings of code nodes.

    Uses content-type aware chunking and API-level batch processing
    (FlowSpace pattern) for efficient embedding generation.

    Example:
        >>> config = EmbeddingConfig(mode="azure")
        >>> service = EmbeddingService(
        ...     config=config,
        ...     embedding_adapter=AzureEmbeddingAdapter(...),
        ...     token_counter=TiktokenTokenCounterAdapter(...),
        ... )
        >>> result = await service.process_batch(nodes)
        >>> print(result["processed"])
    """

    def __init__(
        self,
        config: EmbeddingConfig,
        embedding_adapter: EmbeddingAdapter | None,
        token_counter: TokenCounterAdapter | None,
    ) -> None:
        """Initialize the embedding service.

        Args:
            config: EmbeddingConfig with chunk parameters and batch settings.
            embedding_adapter: Adapter for generating embeddings (can be None for chunking-only tests).
            token_counter: Adapter for counting tokens (can be None for structure tests).
        """
        self._config = config
        self._adapter = embedding_adapter
        self._token_counter = token_counter

    def get_metadata(self) -> dict[str, Any]:
        """Return embedding metadata for graph persistence."""
        model_name = self._config.mode
        if self._config.mode == "azure" and self._config.azure is not None:
            model_name = self._config.azure.deployment_name

        return {
            "embedding_model": model_name,
            "embedding_dimensions": self._config.dimensions,
            "chunk_params": {
                "code": {
                    "max_tokens": self._config.code.max_tokens,
                    "overlap_tokens": self._config.code.overlap_tokens,
                },
                "documentation": {
                    "max_tokens": self._config.documentation.max_tokens,
                    "overlap_tokens": self._config.documentation.overlap_tokens,
                },
                "smart_content": {
                    "max_tokens": self._config.smart_content.max_tokens,
                    "overlap_tokens": self._config.smart_content.overlap_tokens,
                },
            },
        }

    @classmethod
    def create(cls, config: ConfigurationService) -> EmbeddingService:
        """Factory to build EmbeddingService with configured adapters."""
        from fs2.config.objects import EmbeddingConfig
        from fs2.core.adapters.embedding_adapter_azure import AzureEmbeddingAdapter
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter
        from fs2.core.adapters.token_counter_adapter_tiktoken import (
            TiktokenTokenCounterAdapter,
        )

        embedding_config = config.require(EmbeddingConfig)

        if embedding_config.mode == "azure":
            if embedding_config.azure is None:
                raise ValueError("EmbeddingConfig.azure must be set for azure mode")
            embedding_adapter = AzureEmbeddingAdapter(config)
        elif embedding_config.mode == "openai_compatible":
            if embedding_config.openai is None:
                raise ValueError(
                    "EmbeddingConfig.openai must be set for openai_compatible mode"
                )
            from fs2.core.adapters.embedding_adapter_openai import (
                OpenAICompatibleEmbeddingAdapter,
            )

            embedding_adapter = OpenAICompatibleEmbeddingAdapter(
                config,
                api_key=embedding_config.openai.api_key,
                base_url=embedding_config.openai.base_url,
                model=embedding_config.openai.model,
            )
        elif embedding_config.mode == "local":
            import importlib.util

            # Per 047: Prefer ONNX Runtime when available for local mode
            if importlib.util.find_spec("onnxruntime") is not None:
                from fs2.config.objects import OnnxEmbeddingConfig
                from fs2.core.adapters.embedding_adapter_onnx import (
                    OnnxEmbeddingAdapter,
                )

                if embedding_config.onnx is None:
                    model = "BAAI/bge-small-en-v1.5"
                    max_seq_length = 512
                    if embedding_config.local is not None:
                        model = embedding_config.local.model
                        max_seq_length = embedding_config.local.max_seq_length
                    embedding_config.onnx = OnnxEmbeddingConfig(
                        model=model, max_seq_length=max_seq_length
                    )
                embedding_adapter = OnnxEmbeddingAdapter(config)
            else:
                from fs2.config.objects import LocalEmbeddingConfig
                from fs2.core.adapters.embedding_adapter_local import (
                    SentenceTransformerEmbeddingAdapter,
                )

                if embedding_config.local is None:
                    embedding_config.local = LocalEmbeddingConfig()
                embedding_adapter = SentenceTransformerEmbeddingAdapter(config)
        elif embedding_config.mode == "onnx":
            from fs2.config.objects import OnnxEmbeddingConfig
            from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter

            if embedding_config.onnx is None:
                embedding_config.onnx = OnnxEmbeddingConfig()
            embedding_adapter = OnnxEmbeddingAdapter(config)
        elif embedding_config.mode == "fake":
            embedding_adapter = FakeEmbeddingAdapter(
                dimensions=embedding_config.dimensions
            )
        else:
            raise ValueError(f"Unsupported embedding mode: {embedding_config.mode}")

        token_counter = TiktokenTokenCounterAdapter(config)

        return cls(
            config=embedding_config,
            embedding_adapter=embedding_adapter,
            token_counter=token_counter,
        )

    def _chunk_content(
        self,
        node: CodeNode,
        is_smart_content: bool = False,
    ) -> list[ChunkItem]:
        """Chunk node content based on content type and config.

        Per DYK-5: Inline conditional for config selection:
        - is_smart_content=True → config.smart_content (8000 tokens, 0 overlap)
        - ContentType.CODE → config.code (400 tokens, 50 overlap)
        - ContentType.CONTENT → config.documentation (800 tokens, 120 overlap)

        Args:
            node: CodeNode to chunk.
            is_smart_content: If True, chunk smart_content field with large limit.
                              If False, chunk raw content with type-specific limits.

        Returns:
            List of ChunkItem with sequential chunk_index for reassembly.
            Empty list if content is empty.
        """
        # Select content to chunk
        if is_smart_content:
            content = node.smart_content or ""
        else:
            # Prepend leading_context for richer embeddings (Plan 037)
            parts = []
            if node.leading_context:
                parts.append(node.leading_context)
            parts.append(node.content)
            content = "\n".join(parts)

        # Handle empty content
        if not content or not content.strip():
            return []

        # Per DYK-5: Inline conditional for config selection
        if is_smart_content:
            chunk_config = self._config.smart_content
        elif node.content_type == ContentType.CODE:
            chunk_config = self._config.code
        else:  # ContentType.CONTENT
            chunk_config = self._config.documentation

        max_tokens = chunk_config.max_tokens
        overlap_tokens = chunk_config.overlap_tokens

        # Use token counter if available, otherwise estimate
        # Both methods return list[tuple[str, int, int]] per Phase 0
        if self._token_counter is not None:
            chunks = self._chunk_by_tokens(
                content=content,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens,
            )
        else:
            # Fallback: estimate ~4 chars per token
            chunks = self._chunk_by_chars(
                content=content,
                max_chars=max_tokens * 4,
                overlap_chars=overlap_tokens * 4,
            )

        # Convert to ChunkItems with metadata (including line offsets per Phase 0)
        # Per Phase 0: Convert content-relative (1-indexed) to file-absolute line numbers
        # This allows search to report accurate source file line ranges.
        # For smart_content, offsets remain None per DYK-05 (asymmetry by design).
        line_offset = (node.start_line - 1) if node.start_line else 0
        return [
            ChunkItem(
                node_id=node.node_id,
                chunk_index=i,
                text=chunk_text,
                is_smart_content=is_smart_content,
                start_line=start_line + line_offset if not is_smart_content else None,
                end_line=end_line + line_offset if not is_smart_content else None,
            )
            for i, (chunk_text, start_line, end_line) in enumerate(chunks)
        ]

    def _chunk_by_tokens(
        self,
        content: str,
        max_tokens: int,
        overlap_tokens: int,
    ) -> list[tuple[str, int, int]]:
        """Chunk content by token count with overlap, tracking line offsets.

        Uses TokenCounterAdapter for accurate token counting.
        Chunks at sentence/line boundaries when possible for readability.

        Per Phase 0: Returns tuples with line offset metadata for semantic search.
        Per DYK-03: Overlap lines appear in multiple chunks with their actual ranges.
        Per DYK-04: Long line character splits all report same line number.

        Args:
            content: Text content to chunk.
            max_tokens: Maximum tokens per chunk.
            overlap_tokens: Tokens to overlap between consecutive chunks.

        Returns:
            List of (text, start_line, end_line) tuples. Lines are 1-indexed.
        """
        assert self._token_counter is not None

        # Check if content fits in single chunk
        total_tokens = self._token_counter.count_tokens(content)
        line_count = content.count("\n") + 1
        if total_tokens <= max_tokens:
            return [(content, 1, line_count)]

        chunks: list[tuple[str, int, int]] = []
        lines = content.split("\n")

        # Track both line content and line numbers
        # Each entry is (line_text_with_newline, line_number)
        current_chunk_lines: list[tuple[str, int]] = []
        current_tokens = 0

        for line_idx, line in enumerate(lines):
            line_num = line_idx + 1  # 1-indexed
            line_with_newline = line + "\n"
            line_tokens = self._token_counter.count_tokens(line_with_newline)

            # If single line exceeds max, we need to split it
            if line_tokens > max_tokens:
                # Flush current chunk
                if current_chunk_lines:
                    chunk_text = "".join(t for t, _ in current_chunk_lines).rstrip("\n")
                    start_line = current_chunk_lines[0][1]
                    end_line = current_chunk_lines[-1][1]
                    chunks.append((chunk_text, start_line, end_line))
                    current_chunk_lines = []
                    current_tokens = 0

                # Split long line by characters (approximate)
                # Per DYK-04: All character-split chunks have same line number
                char_chunks = self._split_long_line(line, max_tokens)
                for char_chunk in char_chunks:
                    chunks.append((char_chunk, line_num, line_num))
                continue

            # Check if adding this line would exceed limit
            if current_tokens + line_tokens > max_tokens:
                # Save current chunk
                if current_chunk_lines:
                    chunk_text = "".join(t for t, _ in current_chunk_lines).rstrip("\n")
                    start_line = current_chunk_lines[0][1]
                    end_line = current_chunk_lines[-1][1]
                    chunks.append((chunk_text, start_line, end_line))

                # Start new chunk with overlap
                # Per DYK-03: Overlap lines keep their original line numbers
                if overlap_tokens > 0 and current_chunk_lines:
                    overlap_lines = self._get_overlap_lines_with_numbers(
                        current_chunk_lines, overlap_tokens
                    )
                    current_chunk_lines = overlap_lines
                    current_tokens = self._token_counter.count_tokens(
                        "".join(t for t, _ in current_chunk_lines)
                    )
                else:
                    current_chunk_lines = []
                    current_tokens = 0

            current_chunk_lines.append((line_with_newline, line_num))
            current_tokens += line_tokens

        # Add final chunk
        if current_chunk_lines:
            chunk_text = "".join(t for t, _ in current_chunk_lines).rstrip("\n")
            start_line = current_chunk_lines[0][1]
            end_line = current_chunk_lines[-1][1]
            chunks.append((chunk_text, start_line, end_line))

        return chunks

    def _split_long_line(self, line: str, max_tokens: int) -> list[str]:
        """Split a single long line that exceeds max_tokens.

        Uses character-based splitting with approximate token estimation.
        """
        assert self._token_counter is not None

        # Estimate chars per token for this line
        line_tokens = self._token_counter.count_tokens(line)
        chars_per_token = len(line) / max(line_tokens, 1)

        chunk_size = int(max_tokens * chars_per_token * 0.9)  # 10% safety margin
        chunk_size = max(chunk_size, 100)  # Minimum chunk size

        chunks = []
        start = 0
        while start < len(line):
            end = min(start + chunk_size, len(line))
            chunks.append(line[start:end])
            start = end

        return chunks

    def _get_overlap_lines(self, lines: list[str], overlap_tokens: int) -> list[str]:
        """Get trailing lines that sum to approximately overlap_tokens."""
        assert self._token_counter is not None

        overlap_lines: list[str] = []
        tokens = 0

        for line in reversed(lines):
            line_tokens = self._token_counter.count_tokens(line)
            if tokens + line_tokens > overlap_tokens:
                break
            overlap_lines.insert(0, line)
            tokens += line_tokens

        return overlap_lines

    def _get_overlap_lines_with_numbers(
        self, lines: list[tuple[str, int]], overlap_tokens: int
    ) -> list[tuple[str, int]]:
        """Get trailing lines with line numbers that sum to approximately overlap_tokens.

        Per DYK-03: Overlap lines keep their original line numbers so the same
        line can appear in multiple chunks with accurate line reporting.

        Args:
            lines: List of (line_text, line_number) tuples.
            overlap_tokens: Target token count for overlap.

        Returns:
            List of (line_text, line_number) tuples for overlap.
        """
        assert self._token_counter is not None

        overlap_lines: list[tuple[str, int]] = []
        tokens = 0

        for line_text, line_num in reversed(lines):
            line_tokens = self._token_counter.count_tokens(line_text)
            if tokens + line_tokens > overlap_tokens:
                break
            overlap_lines.insert(0, (line_text, line_num))
            tokens += line_tokens

        return overlap_lines

    def _chunk_by_chars(
        self,
        content: str,
        max_chars: int,
        overlap_chars: int,
    ) -> list[tuple[str, int, int]]:
        """Fallback chunking by character count when token counter unavailable.

        Per Phase 0: Returns tuples with approximate line offsets.
        Note: Character-based chunking provides less accurate line boundaries
        than token-based chunking since it doesn't split on line boundaries.

        Args:
            content: Text content to chunk.
            max_chars: Maximum characters per chunk.
            overlap_chars: Characters to overlap between consecutive chunks.

        Returns:
            List of (text, start_line, end_line) tuples. Lines are 1-indexed.
        """
        line_count = content.count("\n") + 1
        if len(content) <= max_chars:
            return [(content, 1, line_count)]

        chunks: list[tuple[str, int, int]] = []
        start = 0
        step = max_chars - overlap_chars
        content_len = len(content)

        while start < content_len:
            end = min(start + max_chars, content_len)
            chunk_text = content[start:end]

            # Approximate line numbers based on newlines in chunk
            # Count newlines before start to get start_line
            start_line = content[:start].count("\n") + 1
            # Count newlines in chunk to get end_line
            end_line = start_line + chunk_text.count("\n")

            chunks.append((chunk_text, start_line, end_line))
            start += step

        return chunks

    def _should_skip(self, node: CodeNode) -> bool:
        """Determine if node should skip embedding generation.

        Per Finding 08: Hash-based skip logic for incremental updates.
        Per DYK-2: Must check both embedding fields if smart_content exists.
        Per Review S1: Must compare content_hash with embedding_hash to detect stale embeddings.

        Skip logic:
        1. If content is non-empty and embedding is None → must process raw content
        2. If embedding_hash is None (legacy) → must process (no way to verify freshness)
        3. If content_hash != embedding_hash → must process (content changed, stale embedding)
        4. If smart_content exists but smart_content_embedding is None → must process
        5. If all conditions satisfied → skip (node fully embedded and fresh)

        Note: Empty content nodes (e.g., empty __init__.py files) skip raw embedding
        check since there's nothing to embed. They only need smart_content_embedding.

        Args:
            node: CodeNode to check.

        Returns:
            True if node should be skipped (already fully embedded and fresh).
            False if node needs embedding generation.
        """
        # Check if content is empty (nothing to embed for raw content)
        has_content = node.content and node.content.strip()

        # Check raw content embedding (only if content exists)
        if has_content and (node.embedding is None or len(node.embedding) == 0):
            return False

        # Check embedding_hash exists (legacy nodes without hash should be re-embedded)
        if node.embedding_hash is None:
            return False

        # Check content has not changed (stale embedding detection)
        # Per Plan 037: embedding_hash includes leading_context when present
        if node.leading_context:
            raw_text = "\n".join([node.leading_context, node.content])
            expected_hash = compute_content_hash(raw_text)
        else:
            expected_hash = node.content_hash
        if expected_hash != node.embedding_hash:
            return False

        # Check smart_content embedding (if smart_content exists)
        # Per fix 2026-01-14: Placeholder smart_content (e.g., "[Empty content...")
        # is intentionally not embedded in process_batch(). Don't require embedding
        # for placeholders, otherwise they get re-processed forever.
        is_placeholder = (
            node.smart_content is not None
            and node.smart_content.startswith("[Empty content")
        )

        if is_placeholder:
            # Placeholder content is intentionally not embedded - skip is OK
            return True

        # Has real smart_content - must also have smart_content_embedding
        # All required embeddings present and fresh
        return not (
            node.smart_content is not None
            and (
                node.smart_content_embedding is None
                or len(node.smart_content_embedding) == 0
            )
        )

    def _collect_batches(self, chunks: list[ChunkItem]) -> list[list[ChunkItem]]:
        """Split ChunkItems into fixed-size batches for API calls.

        Per FlowSpace pattern: API supports batch input, so we split items
        into config.batch_size chunks and call embed_batch() once per batch.

        Per DYK-1: ChunkItems preserve metadata through batching for reassembly.

        Args:
            chunks: List of ChunkItems to batch.

        Returns:
            List of batches, where each batch is a list of ChunkItems.
            Last batch may be smaller than batch_size.
            Empty input returns empty list.
        """
        if not chunks:
            return []

        batch_size = self._config.batch_size
        batches: list[list[ChunkItem]] = []

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            batches.append(batch)

        return batches

    # Type alias for progress callback
    # Called with (processed, total, skipped)
    ProgressCallback = Callable[[int, int, int], None]

    async def process_batch(
        self,
        nodes: list[CodeNode],
        progress_callback: ProgressCallback | None = None,
        courtesy_save: Callable | None = None,
    ) -> dict[str, Any]:
        """Process multiple nodes to generate embeddings.

        Per CD10: All batch state uses local variables (stateless).
        Per CD03: Returns new CodeNode instances via dataclasses.replace().
        Per DYK-1: Uses ChunkItem for tracking chunks through batching.
        Per DYK-2: Generates both embedding and smart_content_embedding.
        Per DYK-4: Converts list[list[float]] → tuple[tuple[float, ...], ...].

        Args:
            nodes: List of CodeNodes to process.
            progress_callback: Optional callback called during processing.
                Receives (processed, total, skipped).
            courtesy_save: Optional callback for periodic graph saves (Plan 036).
                Called every 50 processed nodes with dict of partial results
                (node_id -> updated CodeNode). Enables crash recovery.

        Returns:
            Dict containing:
            - processed: Count of nodes processed
            - skipped: Count of nodes skipped (already embedded)
            - errors: List of (node_id, error_message) tuples
            - total: Total input nodes
            - results: Dict mapping node_id -> updated CodeNode
        """
        # Per CD10: All state is local
        stats: dict[str, Any] = {
            "processed": 0,
            "skipped": 0,
            "errors": [],
            "total": len(nodes),
            "results": {},
        }

        if not nodes:
            return stats

        # Collect all chunks from non-skipped nodes
        # Per DYK-2: Collect both raw content and smart_content chunks
        # Per Phase 0: Track chunk offsets for raw content (not smart_content per DYK-05)
        all_chunks: list[ChunkItem] = []
        nodes_to_process: dict[str, CodeNode] = {}
        chunk_offsets: dict[str, tuple[tuple[int, int], ...]] = {}

        for node in nodes:
            if self._should_skip(node):
                stats["skipped"] += 1
                continue

            nodes_to_process[node.node_id] = node
            logger.debug("Embedding: %s", node.node_id)

            # Chunk raw content
            raw_chunks = self._chunk_content(node, is_smart_content=False)
            all_chunks.extend(raw_chunks)

            # Per Phase 0: Extract chunk offsets from raw content chunks
            # Per DYK-05: Only raw content has offsets (smart_content uses node's full range)
            if raw_chunks:
                offsets = tuple(
                    (chunk.start_line or 1, chunk.end_line or node.end_line)
                    for chunk in raw_chunks
                )
                chunk_offsets[node.node_id] = offsets

            # Chunk smart_content if present (skip placeholder content)
            # Per fix 2025-12-26: Don't embed placeholder smart_content like
            # "[Empty content - no summary generated...]" - they pollute search results
            if node.smart_content and not node.smart_content.startswith(
                "[Empty content"
            ):
                smart_chunks = self._chunk_content(node, is_smart_content=True)
                all_chunks.extend(smart_chunks)

        if not all_chunks:
            # All nodes were skipped
            return stats

        # Collect into batches
        batches = self._collect_batches(all_chunks)

        # Process batches concurrently with semaphore limiting
        # Per Review S2: Use max_concurrent_batches config setting
        chunk_embeddings: dict[tuple[str, int, bool], list[float]] = {}
        errors_list: list[tuple[str, str]] = []
        semaphore = asyncio.Semaphore(self._config.max_concurrent_batches)
        chunks_processed = 0
        total_chunks = len(all_chunks)

        async def process_single_batch(
            batch: list[ChunkItem],
        ) -> list[tuple[tuple[str, int, bool], list[float]]]:
            """Process a single batch with semaphore limiting."""
            if self._adapter is None:
                logger.warning("No embedding adapter configured - skipping batch")
                return []

            async with semaphore:
                texts = [chunk.text for chunk in batch]
                try:
                    embeddings = await self._adapter.embed_batch(texts)
                    # Return list of (key, embedding) pairs
                    return [
                        (
                            (chunk.node_id, chunk.chunk_index, chunk.is_smart_content),
                            embedding,
                        )
                        for chunk, embedding in zip(batch, embeddings, strict=True)
                    ]
                except Exception as e:
                    # Record errors for each chunk in batch
                    for chunk in batch:
                        errors_list.append((chunk.node_id, str(e)))
                    logger.error("Error processing batch: %s", e)
                    return []

        # Run batches with as_completed for incremental progress
        # This reports progress as each batch finishes, not after all complete
        batch_futures = [process_single_batch(batch) for batch in batches]
        batches_completed = 0

        for coro in asyncio.as_completed(batch_futures):
            result_list = await coro
            # Merge results into chunk_embeddings dict
            for key, embedding in result_list:
                chunk_embeddings[key] = embedding

            # Update progress after each batch
            chunks_processed += len(result_list)
            batches_completed += 1
            if progress_callback and total_chunks > 0:
                # Approximate node progress from chunk progress
                approx_nodes = int(
                    len(nodes_to_process) * chunks_processed / total_chunks
                )
                progress_callback(
                    approx_nodes,
                    len(nodes_to_process) + stats["skipped"],
                    stats["skipped"],
                )

            # Courtesy save every 100 batches during processing (Plan 036 T05)
            if courtesy_save is not None and batches_completed % 100 == 0:
                # Build partial results from completed chunks so far
                partial = self._reassemble_partial(
                    chunk_embeddings, nodes_to_process, chunk_offsets
                )
                if partial:
                    courtesy_save(partial)

        # Record any errors that occurred
        stats["errors"].extend(errors_list)

        # Reassemble embeddings into nodes
        # Per DYK-1: Group embeddings by node_id and is_smart_content
        # Per Review Q1: Iterate actual keys instead of hardcoded range(1000)
        for node_id, node in nodes_to_process.items():
            raw_embeddings: list[list[float]] = []
            smart_embeddings: list[list[float]] = []

            # Collect raw content embeddings (sorted by chunk_index)
            # Filter keys matching (node_id, *, False) pattern
            raw_chunks = [
                (key[1], chunk_embeddings[key])  # key[1] is chunk_index
                for key in chunk_embeddings
                if key[0] == node_id and key[2] is False
            ]
            raw_chunks.sort(key=lambda x: x[0])
            raw_embeddings = [emb for _, emb in raw_chunks]

            # Collect smart_content embeddings (sorted by chunk_index)
            if node.smart_content:
                smart_chunks = [
                    (key[1], chunk_embeddings[key])
                    for key in chunk_embeddings
                    if key[0] == node_id and key[2] is True
                ]
                smart_chunks.sort(key=lambda x: x[0])
                smart_embeddings = [emb for _, emb in smart_chunks]

            # Per DYK-4: Convert list[list[float]] → tuple[tuple[float, ...], ...]
            embedding_tuple: tuple[tuple[float, ...], ...] | None = None
            if raw_embeddings:
                embedding_tuple = tuple(tuple(e) for e in raw_embeddings)

            smart_embedding_tuple: tuple[tuple[float, ...], ...] | None = None
            if smart_embeddings:
                smart_embedding_tuple = tuple(tuple(e) for e in smart_embeddings)

            # Per CD03: Create new node via replace()
            # Per Review S1: Set embedding_hash to content_hash for staleness detection
            # Per Phase 0: Include chunk offsets for raw content
            updated_node = replace(
                node,
                embedding=embedding_tuple,
                smart_content_embedding=smart_embedding_tuple,
                embedding_hash=(
                    compute_content_hash(
                        "\n".join([node.leading_context, node.content])
                    )
                    if node.leading_context
                    else node.content_hash
                ),
                embedding_chunk_offsets=chunk_offsets.get(node_id),
            )

            stats["results"][node_id] = updated_node
            stats["processed"] += 1

        # Final progress callback with accurate counts
        if progress_callback and stats["processed"] > 0:
            progress_callback(
                stats["processed"],
                stats["total"],
                stats["skipped"],
            )

        return stats

    def _reassemble_partial(
        self,
        chunk_embeddings: dict[tuple[str, int, bool], list[float]],
        nodes_to_process: dict[str, CodeNode],
        chunk_offsets: dict[str, tuple[tuple[int, int], ...]],
    ) -> dict[str, CodeNode]:
        """Reassemble completed embeddings into CodeNodes for courtesy save.

        Only includes nodes where at least one raw content chunk is complete.
        Called during batch processing to enable crash recovery.
        """
        results: dict[str, CodeNode] = {}

        for node_id, node in nodes_to_process.items():
            raw_keys = [
                k for k in chunk_embeddings if k[0] == node_id and k[2] is False
            ]
            if not raw_keys:
                continue

            raw_sorted = sorted(raw_keys, key=lambda k: k[1])
            raw_embeddings = [chunk_embeddings[k] for k in raw_sorted]
            embedding_tuple = tuple(tuple(e) for e in raw_embeddings)

            smart_embedding_tuple = None
            if node.smart_content:
                smart_keys = [
                    k for k in chunk_embeddings if k[0] == node_id and k[2] is True
                ]
                if smart_keys:
                    smart_sorted = sorted(smart_keys, key=lambda k: k[1])
                    smart_embedding_tuple = tuple(
                        tuple(chunk_embeddings[k]) for k in smart_sorted
                    )

            updated = replace(
                node,
                embedding=embedding_tuple,
                smart_content_embedding=smart_embedding_tuple,
                embedding_hash=(
                    compute_content_hash(
                        "\n".join([node.leading_context, node.content])
                    )
                    if node.leading_context
                    else node.content_hash
                ),
                embedding_chunk_offsets=chunk_offsets.get(node_id),
            )
            results[node_id] = updated

        return results
