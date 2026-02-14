#!/usr/bin/env python3
"""Simulate the smart content merge process to diagnose issues.

This script:
1. Loads the existing graph (like _load_prior_nodes would)
2. Re-parses the same files (like ParsingStage would)
3. Simulates the merge and identifies why nodes would/wouldn't be preserved

This helps diagnose why smart content is being re-processed on subsequent scans.
"""

import pickle
import sys
from collections import Counter
from pathlib import Path

# Ensure fs2 is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fs2.config.objects import GraphConfig, ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters import FileSystemScanner, TreeSitterParser
from fs2.core.repos import NetworkXGraphStore


def load_prior_nodes(graph_path: Path) -> dict:
    """Load prior nodes from graph (simulates ScanPipeline._load_prior_nodes)."""
    if not graph_path.exists():
        print(f"ERROR: Graph not found at {graph_path}")
        return {}

    with open(graph_path, "rb") as f:
        metadata, graph = pickle.load(f)

    prior_nodes = {}
    for node_id in graph.nodes:
        node_data = graph.nodes[node_id].get("data")
        if node_data:
            prior_nodes[node_id] = node_data

    print(f"Loaded {len(prior_nodes)} prior nodes from {graph_path}")
    return prior_nodes


def simulate_fresh_scan(scan_paths: list[str], graph_path: Path) -> list:
    """Run discovery + parsing to get fresh nodes (simulates first 2 stages)."""
    scan_config = ScanConfig(
        scan_paths=scan_paths,
        respect_gitignore=True,
        max_file_size_kb=500,
    )
    graph_config = GraphConfig(graph_path=str(graph_path))
    config = FakeConfigurationService(scan_config, graph_config)

    file_scanner = FileSystemScanner(config)
    ast_parser = TreeSitterParser(config)
    graph_store = NetworkXGraphStore(config)

    # Discover files
    scan_results = file_scanner.scan()
    print(f"Discovered {len(scan_results)} files")

    # Parse files to get fresh nodes
    fresh_nodes = []
    for result in scan_results:
        nodes = ast_parser.parse(result.path)
        for node in nodes:
            graph_store.add_node(node)
            if node.parent_node_id:
                import contextlib
                with contextlib.suppress(Exception):
                    graph_store.add_edge(node.parent_node_id, node.node_id)
        fresh_nodes.extend(nodes)

    print(f"Parsed {len(fresh_nodes)} fresh nodes")
    return fresh_nodes


def simulate_merge(fresh_nodes: list, prior_nodes: dict) -> dict:
    """Simulate the merge logic from SmartContentStage._merge_prior_smart_content."""
    results = {
        "would_be_preserved": [],  # Hash match, has smart_content
        "no_prior_node": [],        # Node not in prior
        "hash_mismatch": [],        # Hash differs
        "prior_has_no_smart_content": [],  # Prior exists but no smart_content
        "prior_smart_content_empty": [],   # Prior has empty string
    }

    for node in fresh_nodes:
        prior = prior_nodes.get(node.node_id)

        if prior is None:
            results["no_prior_node"].append({
                "node_id": node.node_id,
                "name": node.name,
                "category": node.category,
            })
            continue

        if node.content_hash != prior.content_hash:
            results["hash_mismatch"].append({
                "node_id": node.node_id,
                "name": node.name,
                "fresh_hash": node.content_hash[:16] + "...",
                "prior_hash": prior.content_hash[:16] + "...",
            })
            continue

        if prior.smart_content is None:
            results["prior_has_no_smart_content"].append({
                "node_id": node.node_id,
                "name": node.name,
            })
            continue

        if prior.smart_content == "":
            results["prior_smart_content_empty"].append({
                "node_id": node.node_id,
                "name": node.name,
                "smart_content_hash": prior.smart_content_hash[:16] + "..." if prior.smart_content_hash else None,
            })
            # Still counts as "would be preserved" because is not None check passes
            results["would_be_preserved"].append({
                "node_id": node.node_id,
                "name": node.name,
                "smart_content_length": 0,  # Empty!
            })
            continue

        # Would be preserved
        results["would_be_preserved"].append({
            "node_id": node.node_id,
            "name": node.name,
            "smart_content_length": len(prior.smart_content),
        })

    return results


def main():
    print("=" * 80)
    print("SMART CONTENT MERGE SIMULATION")
    print("=" * 80)
    print()

    # Paths - same as config
    graph_path = Path(".fs2/graph.pickle")
    scan_paths = ["src", "tests", "docs"]

    # Step 1: Load prior nodes
    print("-" * 40)
    print("STEP 1: LOAD PRIOR NODES")
    print("-" * 40)
    prior_nodes = load_prior_nodes(graph_path)
    if not prior_nodes:
        print("No prior nodes - cannot simulate merge")
        return

    # Check smart_content distribution in prior nodes
    prior_none = sum(1 for n in prior_nodes.values() if n.smart_content is None)
    prior_empty = sum(1 for n in prior_nodes.values() if n.smart_content == "")
    prior_content = sum(1 for n in prior_nodes.values() if n.smart_content and n.smart_content != "")
    print(f"  Prior nodes with smart_content=None: {prior_none}")
    print(f"  Prior nodes with smart_content='': {prior_empty}")
    print(f"  Prior nodes with actual content: {prior_content}")
    print()

    # Step 2: Simulate fresh scan
    print("-" * 40)
    print("STEP 2: SIMULATE FRESH SCAN")
    print("-" * 40)
    fresh_nodes = simulate_fresh_scan(scan_paths, graph_path)
    print()

    # Step 3: Simulate merge
    print("-" * 40)
    print("STEP 3: SIMULATE MERGE")
    print("-" * 40)
    results = simulate_merge(fresh_nodes, prior_nodes)

    print(f"\nMerge simulation results for {len(fresh_nodes)} fresh nodes:")
    print(f"  Would be PRESERVED: {len(results['would_be_preserved'])}")
    print(f"  No prior node (new file/node): {len(results['no_prior_node'])}")
    print(f"  Hash mismatch (content changed): {len(results['hash_mismatch'])}")
    print(f"  Prior has no smart_content: {len(results['prior_has_no_smart_content'])}")
    print(f"  Prior has empty string: {len(results['prior_smart_content_empty'])}")
    print()

    # Show details for each category
    if results["no_prior_node"]:
        print("\n" + "-" * 40)
        print("NODES NOT IN PRIOR (New or renamed):")
        print("-" * 40)
        # Group by category
        by_cat = Counter(n["category"] for n in results["no_prior_node"])
        for cat, count in by_cat.most_common():
            print(f"  {cat}: {count}")
        # Show first 5
        print("\n  First 5 examples:")
        for item in results["no_prior_node"][:5]:
            print(f"    {item['node_id'][:70]}...")

    if results["hash_mismatch"]:
        print("\n" + "-" * 40)
        print("NODES WITH HASH MISMATCH (Content changed):")
        print("-" * 40)
        print(f"  Total: {len(results['hash_mismatch'])}")
        print("\n  First 5 examples:")
        for item in results["hash_mismatch"][:5]:
            print(f"    {item['node_id'][:60]}...")
            print(f"      fresh_hash: {item['fresh_hash']}")
            print(f"      prior_hash: {item['prior_hash']}")

    if results["prior_has_no_smart_content"]:
        print("\n" + "-" * 40)
        print("NODES WHERE PRIOR HAS NO SMART CONTENT:")
        print("-" * 40)
        print(f"  Total: {len(results['prior_has_no_smart_content'])}")
        print("\n  First 5 examples:")
        for item in results["prior_has_no_smart_content"][:5]:
            print(f"    {item['node_id'][:70]}...")

    if results["prior_smart_content_empty"]:
        print("\n" + "-" * 40)
        print("NODES WHERE PRIOR HAS EMPTY STRING:")
        print("-" * 40)
        print(f"  Total: {len(results['prior_smart_content_empty'])}")
        print("  NOTE: Empty string passes 'is not None' check - these would be 'preserved' but useless!")
        print("\n  First 5 examples:")
        for item in results["prior_smart_content_empty"][:5]:
            print(f"    {item['node_id'][:70]}...")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    total_fresh = len(fresh_nodes)
    would_need_llm = (
        len(results["no_prior_node"])
        + len(results["hash_mismatch"])
        + len(results["prior_has_no_smart_content"])
    )
    would_be_preserved = len(results["would_be_preserved"])

    print("\nOn next scan (based on current graph):")
    print(f"  Total nodes to process: {total_fresh}")
    print(f"  Would need LLM calls: {would_need_llm} ({100*would_need_llm/total_fresh:.1f}%)")
    print(f"  Would be preserved: {would_be_preserved} ({100*would_be_preserved/total_fresh:.1f}%)")

    if len(results["prior_smart_content_empty"]) > 0:
        print(f"\n  WARNING: {len(results['prior_smart_content_empty'])} nodes have empty string smart_content!")
        print("           These pass 'is not None' check but have no useful content.")

    # Check for orphaned prior nodes
    fresh_ids = {n.node_id for n in fresh_nodes}
    orphaned = [n for n in prior_nodes if n not in fresh_ids]
    if orphaned:
        print(f"\n  INFO: {len(orphaned)} prior nodes not in fresh scan (deleted files?)")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
