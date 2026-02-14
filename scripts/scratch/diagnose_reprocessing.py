#!/usr/bin/env python3
"""Diagnose why certain nodes are always being re-processed.

This script:
1. Loads the saved graph
2. Identifies nodes from fixture files
3. Checks their hash states (content_hash vs smart_content_hash)
4. Re-parses the files to compare with fresh nodes
5. Identifies the root cause of re-processing
"""

import pickle
import sys
from collections import defaultdict
from pathlib import Path

# Ensure fs2 is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from fs2.config.objects import GraphConfig, ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters import TreeSitterParser


def load_graph(graph_path: Path) -> tuple[dict, object]:
    """Load graph from pickle file."""
    with open(graph_path, "rb") as f:
        metadata, graph = pickle.load(f)
    return metadata, graph


def extract_nodes(graph) -> dict:
    """Extract all nodes from graph as dict."""
    nodes = {}
    for node_id in graph.nodes:
        node_data = graph.nodes[node_id].get("data")
        if node_data is not None:
            nodes[node_id] = node_data
    return nodes


def parse_file(file_path: Path) -> list:
    """Parse a file to get fresh nodes."""
    scan_config = ScanConfig(scan_paths=[str(file_path.parent)])
    graph_config = GraphConfig(graph_path=".fs2/graph.pickle")
    config = FakeConfigurationService(scan_config, graph_config)
    parser = TreeSitterParser(config)
    return parser.parse(file_path)


def main():
    print("=" * 80)
    print("REPROCESSING DIAGNOSTIC")
    print("=" * 80)

    graph_path = Path(".fs2/graph.pickle")
    if not graph_path.exists():
        print(f"ERROR: Graph not found at {graph_path}")
        return

    # Load graph
    metadata, graph = load_graph(graph_path)
    nodes = extract_nodes(graph)
    print(f"\nLoaded {len(nodes)} nodes from graph")

    # Find fixture nodes
    fixture_nodes = {
        node_id: node for node_id, node in nodes.items()
        if "fixtures" in node_id
    }
    print(f"Found {len(fixture_nodes)} fixture nodes")

    # Analyze hash states
    print("\n" + "-" * 40)
    print("HASH STATE ANALYSIS")
    print("-" * 40)

    # Categorize nodes by their state
    states = defaultdict(list)

    for node_id, node in fixture_nodes.items():
        content_hash = getattr(node, "content_hash", None)
        smart_content = getattr(node, "smart_content", None)
        smart_content_hash = getattr(node, "smart_content_hash", None)

        if smart_content is None:
            states["no_smart_content"].append(node_id)
        elif smart_content == "":
            states["empty_smart_content"].append(node_id)
        elif smart_content_hash is None:
            states["no_smart_content_hash"].append(node_id)
        elif smart_content_hash != content_hash:
            states["hash_mismatch"].append(node_id)
        else:
            states["ok"].append(node_id)

    print("\nFixture node states:")
    for state, node_ids in sorted(states.items()):
        print(f"  {state}: {len(node_ids)}")

    # Show details for problematic nodes
    problem_states = ["no_smart_content", "empty_smart_content", "no_smart_content_hash", "hash_mismatch"]

    for state in problem_states:
        if states[state]:
            print(f"\n--- {state.upper()} ({len(states[state])}) ---")
            for node_id in states[state][:5]:
                node = nodes[node_id]
                print(f"\n  {node_id}")
                print(f"    category: {node.category}")
                print(f"    content_hash: {node.content_hash[:16] if node.content_hash else None}...")
                print(f"    smart_content_hash: {node.smart_content_hash[:16] if node.smart_content_hash else None}...")
                sc = node.smart_content
                if sc:
                    print(f"    smart_content: {repr(sc[:50])}...")
                else:
                    print(f"    smart_content: {sc}")
            if len(states[state]) > 5:
                print(f"    ... and {len(states[state]) - 5} more")

    # Deep dive: Compare saved vs fresh parsed nodes
    print("\n" + "-" * 40)
    print("FRESH PARSE COMPARISON")
    print("-" * 40)

    # Pick a specific problematic file to analyze
    tf_file = Path("tests/fixtures/samples/terraform/main.tf")
    if tf_file.exists():
        print(f"\nAnalyzing: {tf_file}")

        # Parse fresh
        fresh_nodes = parse_file(tf_file)
        print(f"Fresh parse: {len(fresh_nodes)} nodes")

        # Get saved nodes for this file
        saved_tf_nodes = {
            node_id: node for node_id, node in nodes.items()
            if "terraform/main.tf" in node_id
        }
        print(f"Saved nodes: {len(saved_tf_nodes)} nodes")

        # Compare node_ids
        fresh_ids = {n.node_id for n in fresh_nodes}
        saved_ids = set(saved_tf_nodes.keys())

        only_fresh = fresh_ids - saved_ids
        only_saved = saved_ids - fresh_ids
        both = fresh_ids & saved_ids

        print(f"\n  Only in fresh parse: {len(only_fresh)}")
        print(f"  Only in saved graph: {len(only_saved)}")
        print(f"  In both: {len(both)}")

        if only_fresh:
            print("\n  NEW node_ids (not in saved graph):")
            for nid in list(only_fresh)[:5]:
                print(f"    {nid}")

        if only_saved:
            print("\n  ORPHANED node_ids (not in fresh parse):")
            for nid in list(only_saved)[:5]:
                print(f"    {nid}")

        # For nodes in both, compare content_hash
        print("\n  Comparing content_hash for nodes in both:")
        fresh_by_id = {n.node_id: n for n in fresh_nodes}
        hash_matches = 0
        hash_mismatches = []

        for node_id in both:
            fresh = fresh_by_id[node_id]
            saved = saved_tf_nodes[node_id]

            if fresh.content_hash == saved.content_hash:
                hash_matches += 1
            else:
                hash_mismatches.append({
                    "node_id": node_id,
                    "fresh_hash": fresh.content_hash[:16],
                    "saved_hash": saved.content_hash[:16],
                })

        print(f"    Hash matches: {hash_matches}")
        print(f"    Hash mismatches: {len(hash_mismatches)}")

        if hash_mismatches:
            print("\n  HASH MISMATCHES (content changed between parses):")
            for m in hash_mismatches[:5]:
                print(f"    {m['node_id']}")
                print(f"      fresh: {m['fresh_hash']}...")
                print(f"      saved: {m['saved_hash']}...")

    # Check the embedding diagnostic
    print("\n" + "-" * 40)
    print("EMBEDDING STATE ANALYSIS")
    print("-" * 40)

    embedding_states = defaultdict(list)

    for node_id, node in fixture_nodes.items():
        embedding = getattr(node, "embedding", None)
        embedding_hash = getattr(node, "embedding_hash", None)
        content_hash = getattr(node, "content_hash", None)

        if embedding is None:
            embedding_states["no_embedding"].append(node_id)
        elif embedding_hash is None:
            embedding_states["no_embedding_hash"].append(node_id)
        elif embedding_hash != content_hash:
            embedding_states["embedding_hash_mismatch"].append(node_id)
        else:
            embedding_states["ok"].append(node_id)

    print("\nFixture embedding states:")
    for state, node_ids in sorted(embedding_states.items()):
        print(f"  {state}: {len(node_ids)}")

    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
