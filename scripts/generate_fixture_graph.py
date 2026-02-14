#!/usr/bin/env python3
"""Generate fixture graph with real embeddings and smart_content.

This script scans tests/fixtures/samples/, generates real embeddings and
smart_content using Azure adapters, and saves the result to
tests/fixtures/fixture_graph.pkl.

Usage:
    python scripts/generate_fixture_graph.py

    # Or via justfile:
    just generate-fixtures

Requirements:
    - Azure OpenAI credentials (FS2_AZURE__OPENAI__ENDPOINT, etc.)
    - Run from project root

The generated fixture graph is committed to the repository and used by
FakeEmbeddingAdapter and FakeLLMAdapter for tests via FixtureIndex.

Per Phase 0 (Chunk Offset Tracking): Uses ScanPipeline with EmbeddingService
to ensure proper chunking and offset tracking. Previously bypassed EmbeddingService
by calling embed_text() directly (DYK-01).
"""

import asyncio
import logging
import sys
from dataclasses import replace
from pathlib import Path

# Ensure fs2 is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fs2.config.objects import GraphConfig, ScanConfig
from fs2.config.service import FakeConfigurationService, FS2ConfigurationService
from fs2.core.adapters import FileSystemScanner, TreeSitterParser
from fs2.core.adapters.llm_adapter_azure import AzureOpenAIAdapter
from fs2.core.models.code_node import CodeNode
from fs2.core.repos import NetworkXGraphStore
from fs2.core.services import ScanPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# Paths
PROJECT_ROOT = Path(__file__).parent.parent
SAMPLES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "samples"
OUTPUT_PATH = PROJECT_ROOT / "tests" / "fixtures" / "fixture_graph.pkl"


async def generate_smart_content(
    adapter: AzureOpenAIAdapter, node: CodeNode
) -> CodeNode | None:
    """Generate smart_content for a node.

    Args:
        adapter: Azure LLM adapter.
        node: CodeNode to describe.

    Returns:
        Updated CodeNode with smart_content, or None on failure.
    """
    # Only generate for meaningful nodes
    if node.category not in ("file", "callable", "type", "section", "block"):
        return node

    # Truncate content for LLM input
    content = node.content[:2000]

    prompt = f"""Provide a concise, one-paragraph technical description of this {node.category}:

```{node.language}
{content}
```

Focus on:
- What it does (purpose)
- Key functionality
- Notable patterns or techniques used

Be technical but brief (2-3 sentences)."""

    try:
        response = await adapter.generate(prompt, max_tokens=150)
        smart_content = response.content.strip()

        return replace(
            node,
            smart_content=smart_content,
            smart_content_hash=node.content_hash,
        )

    except Exception as e:
        logger.warning(f"Failed to generate smart_content for {node.node_id}: {e}")
        return None


def process_nodes_smart_content(
    nodes: list[CodeNode],
    llm_adapter: AzureOpenAIAdapter,
) -> list[CodeNode]:
    """Process nodes to add smart_content only.

    Per DYK-01: Embeddings are now handled by EmbeddingService via ScanPipeline,
    which properly chunks content and tracks line offsets (Phase 0).

    Args:
        nodes: List of CodeNodes from scan.
        llm_adapter: Azure LLM adapter.

    Returns:
        List of CodeNodes with smart_content added.
    """
    async def _process_async():
        enriched = []
        for i, node in enumerate(nodes):
            logger.info(f"Generating smart_content {i + 1}/{len(nodes)}: {node.node_id}")
            # Generate smart_content only (embeddings handled by EmbeddingService)
            result = await generate_smart_content(llm_adapter, node) or node
            enriched.append(result)
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.1)
        return enriched

    return asyncio.run(_process_async())


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success).
    """
    logger.info("=" * 60)
    logger.info("Fixture Graph Generator")
    logger.info("=" * 60)

    # Verify samples directory exists
    if not SAMPLES_DIR.exists():
        logger.error(f"Samples directory not found: {SAMPLES_DIR}")
        return 1

    logger.info(f"Samples directory: {SAMPLES_DIR}")
    logger.info(f"Output path: {OUTPUT_PATH}")

    # Delete existing fixture to force fresh embedding generation
    # This prevents merging of prior embeddings that may lack chunk offsets
    if OUTPUT_PATH.exists():
        logger.info("Removing existing fixture to force fresh embeddings...")
        OUTPUT_PATH.unlink()

    # Create configuration
    scan_config = ScanConfig(
        scan_paths=[str(SAMPLES_DIR)],
        respect_gitignore=False,
        max_file_size_kb=500,
    )
    graph_config = GraphConfig(graph_path=str(OUTPUT_PATH))
    config = FakeConfigurationService(scan_config, graph_config)

    # Create adapters for scanning
    file_scanner = FileSystemScanner(config)
    ast_parser = TreeSitterParser(config)
    graph_store = NetworkXGraphStore(config)

    # Try to create Azure adapters and EmbeddingService for enrichment
    # Use FS2ConfigurationService to load from .fs2/config.yaml
    embedding_service = None
    llm_adapter = None
    try:
        # Load real config from YAML and environment
        real_config = FS2ConfigurationService()

        # Per DYK-01: Use EmbeddingService for proper chunking and offset tracking
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        embedding_service = EmbeddingService.create(real_config)
        llm_adapter = AzureOpenAIAdapter(real_config)

        logger.info("Azure adapters and EmbeddingService configured")

    except Exception as e:
        logger.warning(f"Could not create Azure adapters: {e}")
        logger.warning("Saving graph without embeddings/smart_content")
        logger.warning(
            "Set FS2_AZURE__OPENAI__ENDPOINT and FS2_AZURE__OPENAI__KEY to enable enrichment"
        )

    # Run scan pipeline with EmbeddingService (Discovery → Parsing → Embedding → Storage)
    # Per Phase 0: ScanPipeline with EmbeddingService ensures proper chunking and offset tracking
    logger.info("Scanning fixture samples...")
    pipeline = ScanPipeline(
        config=config,
        file_scanner=file_scanner,
        ast_parser=ast_parser,
        graph_store=graph_store,
        embedding_service=embedding_service,  # Per DYK-01: Use EmbeddingService
    )
    summary = pipeline.run()

    logger.info(f"Scanned {summary.files_scanned} files")
    logger.info(f"Created {summary.nodes_created} nodes")

    if not summary.success:
        logger.warning(f"Scan had errors: {summary.errors}")

    # Get all nodes from the graph
    nodes = graph_store.get_all_nodes()
    logger.info(f"Retrieved {len(nodes)} nodes from graph")

    # Count nodes with embeddings (generated by EmbeddingService via ScanPipeline)
    with_embedding = sum(1 for n in nodes if n.embedding is not None)
    with_offsets = sum(1 for n in nodes if n.embedding_chunk_offsets is not None)
    logger.info(f"Nodes with embeddings: {with_embedding}")
    logger.info(f"Nodes with chunk offsets: {with_offsets}")

    # Generate smart_content if LLM adapter is available
    if llm_adapter:
        logger.info("Generating smart_content...")
        enriched_nodes = process_nodes_smart_content(nodes, llm_adapter)

        # Clear and rebuild graph with enriched nodes
        graph_store.clear()
        for node in enriched_nodes:
            graph_store.add_node(node)

            # Re-add edges if parent exists
            if node.parent_node_id:
                import contextlib
                with contextlib.suppress(Exception):
                    graph_store.add_edge(node.parent_node_id, node.node_id)  # Parent may not exist

        with_smart = sum(1 for n in enriched_nodes if n.smart_content is not None)
        logger.info(f"Nodes with smart_content: {with_smart}")

    # Save graph
    logger.info(f"Saving graph to {OUTPUT_PATH}...")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    graph_store.save(OUTPUT_PATH)

    # Final stats
    final_nodes = graph_store.get_all_nodes()
    logger.info("=" * 60)
    logger.info("Generation complete!")
    logger.info(f"  Nodes: {len(final_nodes)}")
    logger.info(f"  Output: {OUTPUT_PATH}")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    exit_code = main()  # Synchronous - ScanPipeline manages its own async context
    sys.exit(exit_code)
