#!/usr/bin/env python3
"""Diagnose terraform node_id generation.

Check what node_ids are being generated for terraform blocks
and whether they're unique.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from fs2.config.objects import ScanConfig, GraphConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters import TreeSitterParser


def main():
    print("=" * 80)
    print("TERRAFORM NODE_ID DIAGNOSTIC")
    print("=" * 80)

    tf_file = Path("tests/fixtures/samples/terraform/main.tf")

    scan_config = ScanConfig(scan_paths=[str(tf_file.parent)])
    graph_config = GraphConfig(graph_path=".fs2/graph.pickle")
    config = FakeConfigurationService(scan_config, graph_config)
    parser = TreeSitterParser(config)

    nodes = parser.parse(tf_file)

    print(f"\nParsed {len(nodes)} nodes")

    # Group by category
    by_category = {}
    for node in nodes:
        cat = node.category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(node)

    print(f"\nBy category:")
    for cat, cat_nodes in sorted(by_category.items()):
        print(f"  {cat}: {len(cat_nodes)}")

    # Check for duplicate node_ids
    node_ids = [n.node_id for n in nodes]
    id_counts = Counter(node_ids)
    duplicates = [(nid, count) for nid, count in id_counts.items() if count > 1]

    print(f"\nDuplicate node_ids: {len(duplicates)}")
    if duplicates:
        for nid, count in sorted(duplicates, key=lambda x: -x[1])[:10]:
            print(f"  {count}x: {nid}")

    # Show all block nodes
    print("\n" + "-" * 40)
    print("ALL BLOCK NODES")
    print("-" * 40)

    for node in nodes:
        if node.category == "block":
            print(f"\n  node_id: {node.node_id}")
            print(f"  name: {node.name}")
            print(f"  qualified_name: {node.qualified_name}")
            print(f"  signature: {node.signature[:60]}..." if len(node.signature) > 60 else f"  signature: {node.signature}")

    # Show all callable nodes (cidrsubnet, merge, etc.)
    print("\n" + "-" * 40)
    print("ALL CALLABLE NODES")
    print("-" * 40)

    for node in nodes:
        if node.category == "callable":
            print(f"\n  node_id: {node.node_id}")
            print(f"  name: {node.name}")
            print(f"  qualified_name: {node.qualified_name}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
