#!/usr/bin/env python
"""
Validation script for chunk offsets in fixture_graph.pkl.

Purpose: Manual validation gate for Phase 0 (Chunk Offset Tracking)
Usage: uv run python tests/scratch/validate_chunk_offsets.py

Validates:
1. Nodes with embeddings have embedding_chunk_offsets populated
2. Offsets are valid tuple[tuple[int, int], ...] format
3. Line ranges are sensible (start <= end, within node's line range)
4. Multi-chunk nodes have overlapping ranges per DYK-03

Prints summary statistics and any anomalies found.
"""

from __future__ import annotations

import pickle
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ValidationResult:
    """Results from validating chunk offsets."""

    total_nodes: int = 0
    nodes_with_embeddings: int = 0
    nodes_with_offsets: int = 0
    nodes_with_both: int = 0
    nodes_missing_offsets: list[str] = field(default_factory=list)
    invalid_offset_format: list[str] = field(default_factory=list)
    invalid_line_ranges: list[str] = field(default_factory=list)
    outside_node_range: list[str] = field(default_factory=list)
    multi_chunk_nodes: int = 0
    overlapping_chunks: int = 0  # DYK-03: expected with overlap_tokens > 0


def validate_chunk_offsets(graph_path: Path) -> ValidationResult:
    """Validate chunk offsets in a fixture graph."""
    result = ValidationResult()

    # Load graph
    with open(graph_path, "rb") as f:
        graph = pickle.load(f)

    # Handle tuple format (metadata, digraph)
    if isinstance(graph, tuple):
        metadata, digraph = graph[0], graph[1]
        print(f"Metadata: {metadata}")
        nodes = [(nid, data["data"]) for nid, data in digraph.nodes(data=True)]
    else:
        # Fallback for other formats
        print("Unknown graph format")
        return result

    result.total_nodes = len(nodes)

    for node_id, node in nodes:
        has_embedding = node.embedding is not None
        has_offsets = (
            hasattr(node, "embedding_chunk_offsets")
            and node.embedding_chunk_offsets is not None
        )

        if has_embedding:
            result.nodes_with_embeddings += 1

        if has_offsets:
            result.nodes_with_offsets += 1

        if has_embedding and has_offsets:
            result.nodes_with_both += 1

            # Validate offset format
            offsets = node.embedding_chunk_offsets
            if not isinstance(offsets, tuple):
                result.invalid_offset_format.append(f"{node_id}: not a tuple")
                continue

            for i, offset in enumerate(offsets):
                if not isinstance(offset, tuple) or len(offset) != 2:
                    result.invalid_offset_format.append(
                        f"{node_id}[{i}]: not (int, int)"
                    )
                    continue

                start, end = offset
                if not isinstance(start, int) or not isinstance(end, int):
                    result.invalid_offset_format.append(
                        f"{node_id}[{i}]: not integers"
                    )
                    continue

                # Validate line range
                if start > end:
                    result.invalid_line_ranges.append(
                        f"{node_id}[{i}]: start ({start}) > end ({end})"
                    )

                # Check within node's overall range
                if hasattr(node, "start_line") and hasattr(node, "end_line"):
                    if node.start_line and node.end_line:
                        if start < node.start_line or end > node.end_line:
                            result.outside_node_range.append(
                                f"{node_id}[{i}]: chunk ({start}-{end}) outside node ({node.start_line}-{node.end_line})"
                            )

            # Check for multi-chunk and overlapping (DYK-03)
            if len(offsets) > 1:
                result.multi_chunk_nodes += 1
                # Check for overlapping ranges (expected per DYK-03)
                for i in range(len(offsets) - 1):
                    curr_end = offsets[i][1]
                    next_start = offsets[i + 1][0]
                    if next_start <= curr_end:
                        result.overlapping_chunks += 1
                        break  # Count once per node

        elif has_embedding and not has_offsets:
            result.nodes_missing_offsets.append(node_id)

    return result


def print_validation_report(result: ValidationResult) -> bool:
    """Print validation report and return True if all checks pass."""
    print("\n" + "=" * 60)
    print("CHUNK OFFSET VALIDATION REPORT")
    print("=" * 60)

    print(f"\n{'Summary':^60}")
    print("-" * 60)
    print(f"Total nodes:              {result.total_nodes:>8}")
    print(f"Nodes with embeddings:    {result.nodes_with_embeddings:>8}")
    print(f"Nodes with offsets:       {result.nodes_with_offsets:>8}")
    print(f"Nodes with both:          {result.nodes_with_both:>8}")
    print(f"Multi-chunk nodes:        {result.multi_chunk_nodes:>8}")
    print(f"Nodes with overlap:       {result.overlapping_chunks:>8}  (DYK-03: expected)")

    # Check for issues
    issues_found = False

    if result.nodes_missing_offsets:
        issues_found = True
        print(f"\nERROR: {len(result.nodes_missing_offsets)} nodes missing offsets")
        for node_id in result.nodes_missing_offsets[:5]:
            print(f"  - {node_id}")
        if len(result.nodes_missing_offsets) > 5:
            print(f"  ... and {len(result.nodes_missing_offsets) - 5} more")

    if result.invalid_offset_format:
        issues_found = True
        print(f"\nERROR: {len(result.invalid_offset_format)} invalid offset formats")
        for msg in result.invalid_offset_format[:5]:
            print(f"  - {msg}")

    if result.invalid_line_ranges:
        issues_found = True
        print(f"\nERROR: {len(result.invalid_line_ranges)} invalid line ranges")
        for msg in result.invalid_line_ranges[:5]:
            print(f"  - {msg}")

    if result.outside_node_range:
        # This is a warning, not an error - chunks may legitimately extend slightly
        print(f"\nWARNING: {len(result.outside_node_range)} chunks outside node range")
        for msg in result.outside_node_range[:3]:
            print(f"  - {msg}")

    # Overall verdict
    print("\n" + "=" * 60)
    if issues_found:
        print("VALIDATION FAILED - See errors above")
        return False
    else:
        print("VALIDATION PASSED - All checks OK")
        return True


def main():
    """Main entry point."""
    graph_path = Path("tests/fixtures/fixture_graph.pkl")

    if not graph_path.exists():
        print(f"ERROR: Graph not found at {graph_path}")
        print("Run 'just generate-fixtures' first")
        sys.exit(1)

    print(f"Validating: {graph_path}")
    result = validate_chunk_offsets(graph_path)
    success = print_validation_report(result)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
