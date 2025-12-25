#!/usr/bin/env python3
"""Diagnose why content_hash changes between parses.

This script parses the same file twice and compares the content
of nodes to see what's different.
"""

import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from fs2.config.objects import ScanConfig, GraphConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters import TreeSitterParser


def parse_file(file_path: Path) -> list:
    """Parse a file to get nodes."""
    scan_config = ScanConfig(scan_paths=[str(file_path.parent)])
    graph_config = GraphConfig(graph_path=".fs2/graph.pickle")
    config = FakeConfigurationService(scan_config, graph_config)
    parser = TreeSitterParser(config)
    return parser.parse(file_path)


def main():
    print("=" * 80)
    print("HASH INSTABILITY DIAGNOSTIC")
    print("=" * 80)

    tf_file = Path("tests/fixtures/samples/terraform/main.tf")

    # Parse twice
    print(f"\nParsing: {tf_file}")
    nodes1 = parse_file(tf_file)
    nodes2 = parse_file(tf_file)

    print(f"Parse 1: {len(nodes1)} nodes")
    print(f"Parse 2: {len(nodes2)} nodes")

    # Compare
    by_id_1 = {n.node_id: n for n in nodes1}
    by_id_2 = {n.node_id: n for n in nodes2}

    ids_1 = set(by_id_1.keys())
    ids_2 = set(by_id_2.keys())

    if ids_1 != ids_2:
        print(f"\nWARNING: Node IDs differ between parses!")
        print(f"  Only in parse 1: {ids_1 - ids_2}")
        print(f"  Only in parse 2: {ids_2 - ids_1}")

    # Compare content for each node
    print("\n" + "-" * 40)
    print("CONTENT COMPARISON")
    print("-" * 40)

    stable = 0
    unstable = 0
    unstable_nodes = []

    for node_id in sorted(ids_1 & ids_2):
        n1 = by_id_1[node_id]
        n2 = by_id_2[node_id]

        if n1.content_hash == n2.content_hash:
            stable += 1
        else:
            unstable += 1
            unstable_nodes.append({
                "node_id": node_id,
                "n1": n1,
                "n2": n2,
            })

    print(f"Stable (same hash): {stable}")
    print(f"Unstable (different hash): {unstable}")

    # Show unstable nodes
    if unstable_nodes:
        print(f"\n--- UNSTABLE NODES ---")
        for item in unstable_nodes[:3]:
            n1 = item["n1"]
            n2 = item["n2"]

            print(f"\n{item['node_id']}")
            print(f"  category: {n1.category}")
            print(f"  hash1: {n1.content_hash[:16]}...")
            print(f"  hash2: {n2.content_hash[:16]}...")

            # Show content diff
            content1 = n1.content
            content2 = n2.content

            if content1 == content2:
                print(f"  CONTENT IDENTICAL but hash differs!")
                print(f"    len1: {len(content1)}")
                print(f"    len2: {len(content2)}")
                # Check byte-level
                if content1.encode() == content2.encode():
                    print(f"    Bytes also identical - hash function issue?")
                else:
                    print(f"    Bytes differ!")
            else:
                print(f"  CONTENT DIFFERS:")
                print(f"    len1: {len(content1)}")
                print(f"    len2: {len(content2)}")

                # Show diff
                diff = list(difflib.unified_diff(
                    content1.splitlines(keepends=True),
                    content2.splitlines(keepends=True),
                    fromfile="parse1",
                    tofile="parse2",
                    n=2
                ))
                if diff:
                    print("    Diff:")
                    for line in diff[:20]:
                        print(f"      {repr(line)}")
                    if len(diff) > 20:
                        print(f"      ... and {len(diff) - 20} more lines")

    # Check if order matters
    print("\n" + "-" * 40)
    print("NODE ORDER ANALYSIS")
    print("-" * 40)

    order1 = [n.node_id for n in nodes1]
    order2 = [n.node_id for n in nodes2]

    if order1 == order2:
        print("Node order is STABLE between parses")
    else:
        print("Node order DIFFERS between parses!")
        # Find first difference
        for i, (id1, id2) in enumerate(zip(order1, order2)):
            if id1 != id2:
                print(f"  First difference at index {i}:")
                print(f"    parse1: {id1}")
                print(f"    parse2: {id2}")
                break

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
