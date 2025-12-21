"""FixtureIndex model for O(1) lookup of embeddings and smart_content by content_hash.

Provides a shared utility for FakeEmbeddingAdapter and FakeLLMAdapter to look up
pre-computed embeddings and AI-generated descriptions from a fixture graph.

Per DYK-1: FakeLLMAdapter needs extract_code_from_prompt() to extract code blocks.
Per DYK-2: Embeddings are stored as tuple[tuple[float, ...], ...] from CodeNode.

Usage:
    # Build index from nodes
    nodes = store.get_all_nodes()
    index = FixtureIndex.from_nodes(nodes)

    # Look up embedding by content hash
    embedding = index.get_embedding(content_hash)
    if embedding is not None:
        return list(embedding[0])  # Convert first chunk to list[float]

    # Look up smart_content for LLM responses
    smart = index.get_smart_content(content_hash)

    # Convenience: lookup by raw content
    embedding = index.lookup_embedding("def add(a, b): return a + b")
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fs2.core.utils.hash import compute_content_hash

if TYPE_CHECKING:
    from fs2.core.models.code_node import CodeNode


@dataclass
class FixtureIndex:
    """Index for O(1) lookup of embeddings and smart_content by content_hash.

    Built from CodeNode instances, this index enables FakeEmbeddingAdapter and
    FakeLLMAdapter to return real pre-computed data from fixture graphs.

    Attributes:
        _by_embedding_hash: Maps content_hash to embedding tuple.
        _by_smart_content_hash: Maps content_hash to smart_content string.
        node_count: Number of nodes indexed.
    """

    _by_embedding_hash: dict[str, tuple[tuple[float, ...], ...]] = field(
        default_factory=dict, repr=False
    )
    _by_smart_content_hash: dict[str, str] = field(default_factory=dict, repr=False)
    node_count: int = 0

    @classmethod
    def from_nodes(cls, nodes: Iterable[CodeNode]) -> FixtureIndex:
        """Build a FixtureIndex from CodeNode instances.

        Indexes all nodes by their content_hash, storing embeddings and
        smart_content for O(1) lookup.

        Args:
            nodes: Iterable of CodeNode instances to index.

        Returns:
            FixtureIndex with all nodes indexed.
        """
        by_embedding: dict[str, tuple[tuple[float, ...], ...]] = {}
        by_smart_content: dict[str, str] = {}
        count = 0

        for node in nodes:
            count += 1
            content_hash = node.content_hash

            # Index embedding if present
            if node.embedding is not None:
                by_embedding[content_hash] = node.embedding

            # Index smart_content if present
            if node.smart_content is not None:
                by_smart_content[content_hash] = node.smart_content

        return cls(
            _by_embedding_hash=by_embedding,
            _by_smart_content_hash=by_smart_content,
            node_count=count,
        )

    def get_embedding(
        self, content_hash: str
    ) -> tuple[tuple[float, ...], ...] | None:
        """Get embedding by content hash.

        Args:
            content_hash: SHA-256 hash of the content.

        Returns:
            Embedding tuple if found, None otherwise.
        """
        return self._by_embedding_hash.get(content_hash)

    def get_smart_content(self, content_hash: str) -> str | None:
        """Get smart_content by content hash.

        Args:
            content_hash: SHA-256 hash of the content.

        Returns:
            Smart content string if found, None otherwise.
        """
        return self._by_smart_content_hash.get(content_hash)

    def lookup_embedding(
        self, content: str
    ) -> tuple[tuple[float, ...], ...] | None:
        """Convenience method: lookup embedding by raw content.

        Computes content_hash internally and looks up the embedding.

        Args:
            content: Raw content string.

        Returns:
            Embedding tuple if found, None otherwise.
        """
        content_hash = compute_content_hash(content)
        return self.get_embedding(content_hash)

    def lookup_smart_content(self, content: str) -> str | None:
        """Convenience method: lookup smart_content by raw content.

        Computes content_hash internally and looks up the smart_content.

        Args:
            content: Raw content string.

        Returns:
            Smart content string if found, None otherwise.
        """
        content_hash = compute_content_hash(content)
        return self.get_smart_content(content_hash)

    @staticmethod
    def extract_code_from_prompt(prompt: str) -> str | None:
        """Extract code content from a markdown code block in a prompt.

        Per DYK-1: LLM prompts contain templates/instructions with code blocks.
        This helper extracts the code from the first markdown fence so we can
        compute its content_hash for smart_content lookup.

        Supported formats:
        - ```language\\ncode\\n```
        - ```\\ncode\\n```

        Args:
            prompt: The full prompt string potentially containing code blocks.

        Returns:
            The code content from the first code block, or None if no block found.
            Returns None for empty code blocks.
        """
        # Match markdown code fences: ```language? ... ```
        # Use DOTALL to match across newlines
        pattern = r"```(?:\w+)?\s*\n(.*?)```"
        match = re.search(pattern, prompt, re.DOTALL)

        if match:
            code = match.group(1)
            # Return None for empty/whitespace-only code blocks
            if not code.strip():
                return None
            return code

        return None
