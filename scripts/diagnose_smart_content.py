#!/usr/bin/env python3
"""Diagnostic script to investigate smart content caching issues.

This script inspects the graph.pickle to understand:
1. How many nodes have smart_content populated
2. Whether smart_content_hash matches content_hash
3. What the hash distribution looks like
4. Whether there are any anomalies in the data

Run after `fs2 scan` to diagnose why smart content re-processes.
"""

import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load_graph(graph_path: Path) -> tuple[dict, object]:
    """Load graph from pickle file."""
    if not graph_path.exists():
        print(f"ERROR: Graph file not found: {graph_path}")
        sys.exit(1)

    with open(graph_path, "rb") as f:
        data = pickle.load(f)

    if not isinstance(data, tuple) or len(data) != 2:
        print("ERROR: Invalid graph format - expected (metadata, graph) tuple")
        sys.exit(1)

    return data[0], data[1]


def analyze_graph(graph_path: Path):
    """Analyze the graph and report on smart content state."""
    print("=" * 80)
    print("SMART CONTENT DIAGNOSTIC REPORT")
    print("=" * 80)
    print(f"\nGraph file: {graph_path}")
    print(f"File size: {graph_path.stat().st_size / 1024:.1f} KB")
    print()

    metadata, graph = load_graph(graph_path)

    # === SECTION 1: METADATA ===
    print("-" * 40)
    print("SECTION 1: GRAPH METADATA")
    print("-" * 40)
    for key, value in metadata.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")
    print()

    # === SECTION 2: NODE STATISTICS ===
    print("-" * 40)
    print("SECTION 2: NODE STATISTICS")
    print("-" * 40)

    total_nodes = graph.number_of_nodes()
    print(f"Total nodes: {total_nodes}")
    print(f"Total edges: {graph.number_of_edges()}")
    print()

    # Extract all nodes
    nodes = []
    for node_id in graph.nodes:
        node_data = graph.nodes[node_id].get("data")
        if node_data is not None:
            nodes.append(node_data)

    print(f"Nodes with data attribute: {len(nodes)}")
    if len(nodes) != total_nodes:
        print(f"  WARNING: {total_nodes - len(nodes)} nodes missing 'data' attribute!")
    print()

    # === SECTION 3: SMART CONTENT ANALYSIS ===
    print("-" * 40)
    print("SECTION 3: SMART CONTENT ANALYSIS")
    print("-" * 40)

    # Count smart content states
    has_smart_content = 0
    has_smart_content_hash = 0
    has_content_hash = 0
    hash_matches = 0
    hash_mismatches = 0
    smart_content_none_but_hash_exists = 0

    # Track by category
    by_category = defaultdict(lambda: {
        "total": 0,
        "has_smart_content": 0,
        "hash_match": 0,
        "hash_mismatch": 0,
    })

    # Sample nodes for inspection
    sample_with_smart_content = []
    sample_without_smart_content = []
    sample_hash_mismatch = []

    for node in nodes:
        cat = getattr(node, "category", "unknown")
        by_category[cat]["total"] += 1

        content_hash = getattr(node, "content_hash", None)
        smart_content = getattr(node, "smart_content", None)
        smart_content_hash = getattr(node, "smart_content_hash", None)

        if content_hash is not None:
            has_content_hash += 1

        if smart_content is not None:
            has_smart_content += 1
            by_category[cat]["has_smart_content"] += 1
            if len(sample_with_smart_content) < 3:
                sample_with_smart_content.append(node)
        else:
            if len(sample_without_smart_content) < 3:
                sample_without_smart_content.append(node)

        if smart_content_hash is not None:
            has_smart_content_hash += 1

            if smart_content is None:
                smart_content_none_but_hash_exists += 1

        # Check hash match
        if smart_content_hash is not None and content_hash is not None:
            if smart_content_hash == content_hash:
                hash_matches += 1
                by_category[cat]["hash_match"] += 1
            else:
                hash_mismatches += 1
                by_category[cat]["hash_mismatch"] += 1
                if len(sample_hash_mismatch) < 3:
                    sample_hash_mismatch.append(node)

    print(f"Nodes with content_hash: {has_content_hash}/{len(nodes)} ({100*has_content_hash/len(nodes):.1f}%)")
    print(f"Nodes with smart_content: {has_smart_content}/{len(nodes)} ({100*has_smart_content/len(nodes):.1f}%)")
    print(f"Nodes with smart_content_hash: {has_smart_content_hash}/{len(nodes)} ({100*has_smart_content_hash/len(nodes):.1f}%)")
    print()

    if smart_content_none_but_hash_exists > 0:
        print(f"WARNING: {smart_content_none_but_hash_exists} nodes have smart_content_hash but smart_content=None!")
        print("         This indicates incomplete smart content generation.")
    print()

    print("Hash comparison (smart_content_hash vs content_hash):")
    print(f"  Matches: {hash_matches}")
    print(f"  Mismatches: {hash_mismatches}")
    print("  (Only applicable when smart_content_hash is set)")
    print()

    # === SECTION 4: BY CATEGORY BREAKDOWN ===
    print("-" * 40)
    print("SECTION 4: BY CATEGORY BREAKDOWN")
    print("-" * 40)

    print(f"{'Category':<15} {'Total':>8} {'HasSmart':>10} {'HashMatch':>10} {'HashMismatch':>12}")
    print("-" * 55)
    for cat in sorted(by_category.keys()):
        stats = by_category[cat]
        print(f"{cat:<15} {stats['total']:>8} {stats['has_smart_content']:>10} {stats['hash_match']:>10} {stats['hash_mismatch']:>12}")
    print()

    # === SECTION 5: SAMPLE NODES ===
    print("-" * 40)
    print("SECTION 5: SAMPLE NODES")
    print("-" * 40)

    def print_node_summary(node, label):
        print(f"\n  [{label}]")
        print(f"    node_id: {getattr(node, 'node_id', 'N/A')[:80]}...")
        print(f"    category: {getattr(node, 'category', 'N/A')}")
        print(f"    name: {getattr(node, 'name', 'N/A')}")

        content = getattr(node, 'content', None)
        if content:
            print(f"    content length: {len(content)} chars")

        content_hash = getattr(node, 'content_hash', None)
        smart_content = getattr(node, 'smart_content', None)
        smart_content_hash = getattr(node, 'smart_content_hash', None)

        print(f"    content_hash: {content_hash[:16] if content_hash else 'None'}...")
        print(f"    smart_content_hash: {smart_content_hash[:16] if smart_content_hash else 'None'}...")
        print(f"    smart_content: {repr(smart_content[:50]) if smart_content else 'None'}...")

        if smart_content_hash and content_hash:
            match = "MATCH" if smart_content_hash == content_hash else "MISMATCH"
            print(f"    hash_status: {match}")

    if sample_with_smart_content:
        print("\n  === Nodes WITH smart_content ===")
        for i, node in enumerate(sample_with_smart_content):
            print_node_summary(node, f"Sample {i+1}")

    if sample_without_smart_content:
        print("\n  === Nodes WITHOUT smart_content ===")
        for i, node in enumerate(sample_without_smart_content):
            print_node_summary(node, f"Sample {i+1}")

    if sample_hash_mismatch:
        print("\n  === Nodes with HASH MISMATCH ===")
        for i, node in enumerate(sample_hash_mismatch):
            print_node_summary(node, f"Sample {i+1}")

    # === SECTION 6: HASH ANALYSIS ===
    print("\n" + "-" * 40)
    print("SECTION 6: HASH ANALYSIS")
    print("-" * 40)

    # Check for duplicate content_hashes
    content_hash_counter = Counter(
        getattr(n, "content_hash", None) for n in nodes if getattr(n, "content_hash", None)
    )
    duplicates = [(h, c) for h, c in content_hash_counter.items() if c > 1]

    print(f"Unique content_hash values: {len(content_hash_counter)}")
    print(f"Duplicate content_hash values: {len(duplicates)}")
    if duplicates:
        print("  (Duplicate hashes indicate identical content across nodes)")
        for hash_val, count in sorted(duplicates, key=lambda x: -x[1])[:5]:
            print(f"    {hash_val[:16]}...: {count} nodes")
    print()

    # === SECTION 7: CACHING EFFECTIVENESS ===
    print("-" * 40)
    print("SECTION 7: CACHING EFFECTIVENESS PREDICTION")
    print("-" * 40)

    would_be_preserved = 0
    would_need_regeneration = 0

    for node in nodes:
        smart_content = getattr(node, "smart_content", None)
        smart_content_hash = getattr(node, "smart_content_hash", None)
        content_hash = getattr(node, "content_hash", None)

        # This is the exact logic from SmartContentStage._merge_prior_smart_content
        if smart_content is not None and smart_content_hash is not None and content_hash is not None:
            if smart_content_hash == content_hash:
                would_be_preserved += 1
            else:
                would_need_regeneration += 1
        else:
            would_need_regeneration += 1

    print("On next scan (assuming no file changes):")
    print(f"  Would be PRESERVED (skip LLM): {would_be_preserved}/{len(nodes)} ({100*would_be_preserved/len(nodes):.1f}%)")
    print(f"  Would need REGENERATION: {would_need_regeneration}/{len(nodes)} ({100*would_need_regeneration/len(nodes):.1f}%)")
    print()

    if would_need_regeneration > len(nodes) * 0.5:
        print("WARNING: More than 50% of nodes would need regeneration!")
        print("         This indicates the caching system is not working as expected.")
        print()
        print("Possible causes:")
        if has_smart_content < len(nodes) * 0.5:
            print("  - smart_content is not being populated (LLM errors? config issue?)")
        if hash_mismatches > 0:
            print("  - smart_content_hash != content_hash (content changed since generation?)")
        if smart_content_none_but_hash_exists > 0:
            print("  - smart_content is None but hash exists (incomplete generation)")

    print()
    print("=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)

    return {
        "total_nodes": len(nodes),
        "has_smart_content": has_smart_content,
        "has_smart_content_hash": has_smart_content_hash,
        "hash_matches": hash_matches,
        "hash_mismatches": hash_mismatches,
        "would_be_preserved": would_be_preserved,
        "would_need_regeneration": would_need_regeneration,
    }


if __name__ == "__main__":
    # Default to .fs2/graph.pickle
    graph_path = Path(".fs2/graph.pickle")

    if len(sys.argv) > 1:
        graph_path = Path(sys.argv[1])

    analyze_graph(graph_path)
