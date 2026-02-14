#!/usr/bin/env python3
"""Compare saved graph nodes with freshly parsed nodes.

This script investigates the content differences between
what's saved in the graph and what fresh parsing produces.
"""

import difflib
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from fs2.config.objects import GraphConfig, ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters import TreeSitterParser


def load_graph(graph_path: Path):
    with open(graph_path, "rb") as f:
        metadata, graph = pickle.load(f)
    return metadata, graph


def extract_nodes(graph) -> dict:
    nodes = {}
    for node_id in graph.nodes:
        node_data = graph.nodes[node_id].get("data")
        if node_data is not None:
            nodes[node_id] = node_data
    return nodes


def parse_file(file_path: Path) -> list:
    scan_config = ScanConfig(scan_paths=[str(file_path.parent)])
    graph_config = GraphConfig(graph_path=".fs2/graph.pickle")
    config = FakeConfigurationService(scan_config, graph_config)
    parser = TreeSitterParser(config)
    return parser.parse(file_path)


def main():
    print("=" * 80)
    print("SAVED vs FRESH COMPARISON")
    print("=" * 80)

    # Load saved graph
    graph_path = Path(".fs2/graph.pickle")
    metadata, graph = load_graph(graph_path)
    saved_nodes = extract_nodes(graph)

    # Parse fresh
    tf_file = Path("tests/fixtures/samples/terraform/main.tf")
    fresh_nodes = parse_file(tf_file)
    fresh_by_id = {n.node_id: n for n in fresh_nodes}

    # Get saved terraform nodes
    saved_tf = {
        node_id: node for node_id, node in saved_nodes.items()
        if "terraform/main.tf" in node_id
    }

    print(f"\nSaved terraform nodes: {len(saved_tf)}")
    print(f"Fresh terraform nodes: {len(fresh_by_id)}")

    # Find mismatches
    print("\n" + "-" * 40)
    print("HASH MISMATCHES")
    print("-" * 40)

    for node_id in sorted(saved_tf.keys()):
        saved = saved_tf[node_id]
        fresh = fresh_by_id.get(node_id)

        if fresh is None:
            print(f"\n{node_id}")
            print("  NOT in fresh parse (orphaned)")
            continue

        if saved.content_hash != fresh.content_hash:
            print(f"\n{node_id}")
            print(f"  category: {saved.category}")
            print(f"  saved_hash:  {saved.content_hash[:32]}...")
            print(f"  fresh_hash:  {fresh.content_hash[:32]}...")

            saved_content = saved.content
            fresh_content = fresh.content

            print(f"  saved_len: {len(saved_content)}")
            print(f"  fresh_len: {len(fresh_content)}")

            if saved_content == fresh_content:
                print("  CONTENT IDENTICAL - hash algorithm issue?")

                # Debug: check the actual hash computation
                import hashlib
                saved_recomputed = hashlib.sha256(saved_content.encode("utf-8")).hexdigest()
                fresh_recomputed = hashlib.sha256(fresh_content.encode("utf-8")).hexdigest()
                print(f"  saved content rehashed: {saved_recomputed[:32]}...")
                print(f"  fresh content rehashed: {fresh_recomputed[:32]}...")

            else:
                print("  CONTENT DIFFERS:")

                # Show first difference
                for i, (c1, c2) in enumerate(zip(saved_content, fresh_content, strict=False)):
                    if c1 != c2:
                        print(f"    First diff at char {i}:")
                        print(f"      saved: {repr(saved_content[max(0,i-20):i+20])}")
                        print(f"      fresh: {repr(fresh_content[max(0,i-20):i+20])}")
                        break
                else:
                    # One is prefix of other
                    if len(saved_content) != len(fresh_content):
                        print("    One is prefix of other")

                # Show unified diff (first few lines)
                diff = list(difflib.unified_diff(
                    saved_content.splitlines(keepends=True),
                    fresh_content.splitlines(keepends=True),
                    fromfile="saved",
                    tofile="fresh",
                    n=1
                ))
                if diff:
                    print("    Diff (first 15 lines):")
                    for line in diff[:15]:
                        print(f"      {repr(line)}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
