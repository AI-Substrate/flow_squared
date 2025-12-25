#!/usr/bin/env python3
"""Validate chunk offsets in fixture_graph.pkl.

T011: Verify that the regenerated fixture graph has proper chunk offsets.

Checks:
1. Nodes with embeddings have embedding_chunk_offsets set
2. Offsets are valid tuples of (start_line, end_line)
3. Line ranges make sense (start <= end, within node bounds)
4. Offset count matches embedding chunk count
"""

import pickle
import sys
from pathlib import Path

# Ensure fs2 is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "fixture_graph.pkl"


def validate_chunk_offsets() -> tuple[bool, list[str]]:
    """Validate chunk offsets in the fixture graph.

    Returns:
        Tuple of (success, list of issues found).
    """
    issues: list[str] = []
    stats = {
        "total_nodes": 0,
        "nodes_with_embedding": 0,
        "nodes_with_offsets": 0,
        "nodes_missing_offsets": 0,
        "offset_count_mismatches": 0,
        "invalid_line_ranges": 0,
        "offsets_exceed_node_bounds": 0,
    }

    # Load the graph
    if not FIXTURE_PATH.exists():
        issues.append(f"Fixture graph not found: {FIXTURE_PATH}")
        return False, issues

    with open(FIXTURE_PATH, "rb") as f:
        data = pickle.load(f)

    # Handle tuple format: (metadata, graph)
    if isinstance(data, tuple):
        metadata, graph = data
        print(f"Metadata: {metadata}")
    else:
        graph = data

    # Get all nodes
    nodes = list(graph.nodes(data=True))
    stats["total_nodes"] = len(nodes)

    for node_id, attrs in nodes:
        node = attrs.get("data")
        if node is None:
            continue

        # Check embedding presence
        has_embedding = node.embedding is not None
        has_offsets = (
            hasattr(node, "embedding_chunk_offsets")
            and node.embedding_chunk_offsets is not None
        )

        if has_embedding:
            stats["nodes_with_embedding"] += 1

            if has_offsets:
                stats["nodes_with_offsets"] += 1

                # Validate offset structure
                offsets = node.embedding_chunk_offsets

                if not isinstance(offsets, tuple):
                    issues.append(f"{node_id}: offsets is not a tuple: {type(offsets)}")
                    continue

                # Count chunks in embedding - embeddings can be tuple or list
                embedding = node.embedding
                if embedding and len(embedding) > 0:
                    # Check if it's nested (multi-chunk) or flat (single chunk)
                    first_elem = embedding[0]
                    if isinstance(first_elem, (list, tuple)) and len(first_elem) > 10:
                        # Multi-chunk: each element is an embedding vector
                        chunk_count = len(embedding)
                    else:
                        # Single chunk: embedding is a flat vector
                        chunk_count = 1
                else:
                    chunk_count = 0

                # Validate offset count matches chunk count
                if len(offsets) != chunk_count:
                    stats["offset_count_mismatches"] += 1
                    issues.append(
                        f"{node_id}: offset count ({len(offsets)}) != "
                        f"chunk count ({chunk_count})"
                    )

                # Validate each offset tuple
                for i, offset in enumerate(offsets):
                    if not isinstance(offset, tuple) or len(offset) != 2:
                        issues.append(
                            f"{node_id} chunk {i}: invalid offset format: {offset}"
                        )
                        continue

                    start_line, end_line = offset

                    # Check types
                    if not isinstance(start_line, int) or not isinstance(end_line, int):
                        issues.append(
                            f"{node_id} chunk {i}: non-int offset: "
                            f"({type(start_line)}, {type(end_line)})"
                        )
                        continue

                    # Check start <= end
                    if start_line > end_line:
                        stats["invalid_line_ranges"] += 1
                        issues.append(
                            f"{node_id} chunk {i}: start ({start_line}) > "
                            f"end ({end_line})"
                        )

                    # Check within node bounds (if node has line info)
                    if hasattr(node, "start_line") and node.start_line is not None:
                        if start_line < node.start_line:
                            stats["offsets_exceed_node_bounds"] += 1
                            issues.append(
                                f"{node_id} chunk {i}: start ({start_line}) < "
                                f"node start ({node.start_line})"
                            )

                    if hasattr(node, "end_line") and node.end_line is not None:
                        if end_line > node.end_line:
                            stats["offsets_exceed_node_bounds"] += 1
                            issues.append(
                                f"{node_id} chunk {i}: end ({end_line}) > "
                                f"node end ({node.end_line})"
                            )
            else:
                stats["nodes_missing_offsets"] += 1
                issues.append(f"{node_id}: has embedding but missing offsets")

    # Print summary
    print("=" * 60)
    print("Chunk Offset Validation Report")
    print("=" * 60)
    print(f"Fixture: {FIXTURE_PATH}")
    print()
    print("Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()

    if issues:
        print(f"Issues Found ({len(issues)}):")
        # Show first 20 issues
        for issue in issues[:20]:
            print(f"  - {issue}")
        if len(issues) > 20:
            print(f"  ... and {len(issues) - 20} more")
    else:
        print("No issues found!")

    print("=" * 60)

    success = len(issues) == 0
    return success, issues


def main() -> int:
    """Main entry point."""
    success, issues = validate_chunk_offsets()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
