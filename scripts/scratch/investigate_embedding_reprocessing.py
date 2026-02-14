#!/usr/bin/env python3
"""Investigate why fs2 scan detects files needing enrichment even when unchanged.

This script:
1. Runs fs2 scan twice with verbose output
2. Saves outputs to files for comparison
3. Loads graph pickle before and after each run
4. Identifies which nodes are being re-processed and WHY

Usage:
    python scripts/scratch/investigate_embedding_reprocessing.py
"""

import hashlib
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Ensure fs2 is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from fs2.core.repos.graph_store_impl import RestrictedUnpickler


@dataclass
class ScanResult:
    """Results from a scan run."""
    output: str
    graph_metadata: dict
    nodes: dict  # node_id -> CodeNode
    timestamp: str


def load_graph_safely(graph_path: Path) -> tuple[dict, dict]:
    """Load graph using RestrictedUnpickler for security."""
    if not graph_path.exists():
        return {}, {}

    with open(graph_path, "rb") as f:
        unpickler = RestrictedUnpickler(f)
        metadata, graph = unpickler.load()

    # Extract nodes
    nodes = {}
    for node_id in graph.nodes:
        node_data = graph.nodes[node_id].get("data")
        if node_data is not None:
            nodes[node_id] = node_data

    return metadata, nodes


def run_scan(scan_num: int, output_dir: Path) -> ScanResult:
    """Run fs2 scan --verbose and capture output."""
    print(f"\n{'='*60}")
    print(f"SCAN #{scan_num}")
    print(f"{'='*60}")

    timestamp = datetime.now().isoformat()
    output_file = output_dir / f"scan_{scan_num}_output.txt"

    # Run scan with verbose flag
    result = subprocess.run(
        ["fs2", "scan", "--verbose"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    # Save output
    full_output = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
    output_file.write_text(full_output)
    print(f"Output saved to: {output_file}")

    # Load graph after scan
    graph_path = Path(".fs2/graph.pickle")
    metadata, nodes = load_graph_safely(graph_path)

    print(f"  Return code: {result.returncode}")
    print(f"  Nodes in graph: {len(nodes)}")
    print(f"  Metadata: {metadata.get('format_version', 'unknown')}")

    return ScanResult(
        output=full_output,
        graph_metadata=metadata,
        nodes=nodes,
        timestamp=timestamp,
    )


def analyze_enrichment_state(nodes: dict) -> dict:
    """Analyze the enrichment state of all nodes."""
    states = defaultdict(list)

    for node_id, node in nodes.items():
        content_hash = getattr(node, "content_hash", None)

        # Smart content state
        smart_content = getattr(node, "smart_content", None)
        smart_content_hash = getattr(node, "smart_content_hash", None)

        # Embedding state
        embedding = getattr(node, "embedding", None)
        embedding_hash = getattr(node, "embedding_hash", None)

        # Classify smart content state
        if smart_content is None:
            sc_state = "sc_none"
        elif smart_content == "":
            sc_state = "sc_empty"
        elif smart_content_hash is None:
            sc_state = "sc_no_hash"
        elif smart_content_hash != content_hash:
            sc_state = "sc_hash_mismatch"
        else:
            sc_state = "sc_ok"

        # Classify embedding state
        if embedding is None or (hasattr(embedding, '__len__') and len(embedding) == 0):
            emb_state = "emb_none"
        elif embedding_hash is None:
            emb_state = "emb_no_hash"
        elif embedding_hash != content_hash:
            emb_state = "emb_hash_mismatch"
        else:
            emb_state = "emb_ok"

        states[f"{sc_state}|{emb_state}"].append(node_id)

    return dict(states)


def compare_nodes(nodes1: dict, nodes2: dict) -> dict:
    """Compare nodes between two scan runs."""
    all_ids = set(nodes1.keys()) | set(nodes2.keys())

    comparison = {
        "only_in_first": [],
        "only_in_second": [],
        "content_hash_changed": [],
        "smart_content_hash_changed": [],
        "embedding_hash_changed": [],
        "smart_content_changed": [],
        "embedding_changed": [],
        "unchanged": [],
    }

    for node_id in all_ids:
        n1 = nodes1.get(node_id)
        n2 = nodes2.get(node_id)

        if n1 is None:
            comparison["only_in_second"].append(node_id)
            continue
        if n2 is None:
            comparison["only_in_first"].append(node_id)
            continue

        # Compare fields
        changes = []

        if getattr(n1, "content_hash", None) != getattr(n2, "content_hash", None):
            comparison["content_hash_changed"].append(node_id)
            changes.append("content_hash")

        if getattr(n1, "smart_content_hash", None) != getattr(n2, "smart_content_hash", None):
            comparison["smart_content_hash_changed"].append(node_id)
            changes.append("smart_content_hash")

        if getattr(n1, "embedding_hash", None) != getattr(n2, "embedding_hash", None):
            comparison["embedding_hash_changed"].append(node_id)
            changes.append("embedding_hash")

        if getattr(n1, "smart_content", None) != getattr(n2, "smart_content", None):
            comparison["smart_content_changed"].append(node_id)
            changes.append("smart_content")

        emb1 = getattr(n1, "embedding", None)
        emb2 = getattr(n2, "embedding", None)
        if emb1 != emb2:
            comparison["embedding_changed"].append(node_id)
            changes.append("embedding")

        if not changes:
            comparison["unchanged"].append(node_id)

    return comparison


def find_reprocessing_candidates(nodes: dict) -> list:
    """Find nodes that would be re-processed on next scan."""
    candidates = []

    for node_id, node in nodes.items():
        content_hash = getattr(node, "content_hash", None)
        reasons = []

        # Check smart content
        smart_content = getattr(node, "smart_content", None)
        smart_content_hash = getattr(node, "smart_content_hash", None)

        if smart_content is None:
            reasons.append("no_smart_content")
        elif smart_content_hash is None:
            reasons.append("no_smart_content_hash")
        elif smart_content_hash != content_hash:
            reasons.append(f"smart_content_hash_mismatch (sc_hash={smart_content_hash[:8]}... vs content={content_hash[:8]}...)")

        # Check embedding
        embedding = getattr(node, "embedding", None)
        embedding_hash = getattr(node, "embedding_hash", None)

        has_content = node.content and node.content.strip() if hasattr(node, 'content') else False

        if has_content and (embedding is None or (hasattr(embedding, '__len__') and len(embedding) == 0)):
            reasons.append("no_embedding_but_has_content")
        elif embedding_hash is None and embedding is not None:
            reasons.append("no_embedding_hash")
        elif embedding_hash is not None and embedding_hash != content_hash:
            reasons.append(f"embedding_hash_mismatch (emb_hash={embedding_hash[:8]}... vs content={content_hash[:8]}...)")

        # Check smart content embedding
        smart_content_embedding = getattr(node, "smart_content_embedding", None)
        if smart_content is not None and (smart_content_embedding is None or (hasattr(smart_content_embedding, '__len__') and len(smart_content_embedding) == 0)):
            reasons.append("has_smart_content_but_no_smart_content_embedding")

        if reasons:
            candidates.append((node_id, reasons))

    return candidates


def deep_compare_node(n1, n2, node_id: str) -> dict:
    """Deep compare two nodes and report all differences."""
    diffs = {}

    fields = [
        "node_id", "name", "category", "file_path",
        "start_line", "end_line", "content", "content_hash",
        "smart_content", "smart_content_hash",
        "embedding", "embedding_hash", "smart_content_embedding",
    ]

    for field in fields:
        v1 = getattr(n1, field, "MISSING")
        v2 = getattr(n2, field, "MISSING")

        if v1 != v2:
            # For large fields, show hash instead
            if field in ("content", "smart_content", "embedding", "smart_content_embedding"):
                if isinstance(v1, str) and len(v1) > 100:
                    v1_display = f"<{len(v1)} chars, hash={hashlib.sha256(v1.encode()).hexdigest()[:16]}>"
                elif isinstance(v1, (tuple, list)) and len(v1) > 0:
                    v1_display = f"<{len(v1)} vectors>"
                else:
                    v1_display = repr(v1)[:100]

                if isinstance(v2, str) and len(v2) > 100:
                    v2_display = f"<{len(v2)} chars, hash={hashlib.sha256(v2.encode()).hexdigest()[:16]}>"
                elif isinstance(v2, (tuple, list)) and len(v2) > 0:
                    v2_display = f"<{len(v2)} vectors>"
                else:
                    v2_display = repr(v2)[:100]
            else:
                v1_display = repr(v1)[:100] if v1 != "MISSING" else "MISSING"
                v2_display = repr(v2)[:100] if v2 != "MISSING" else "MISSING"

            diffs[field] = {"before": v1_display, "after": v2_display}

    return diffs


def main():
    print("=" * 80)
    print("EMBEDDING REPROCESSING INVESTIGATION")
    print("=" * 80)
    print(f"Started: {datetime.now().isoformat()}")

    # Setup output directory
    output_dir = Path("scripts/scratch/investigation_output")
    output_dir.mkdir(exist_ok=True)

    # Check if graph exists
    graph_path = Path(".fs2/graph.pickle")

    # Load initial state
    print("\n" + "-" * 40)
    print("INITIAL STATE")
    print("-" * 40)

    if graph_path.exists():
        initial_metadata, initial_nodes = load_graph_safely(graph_path)
        print(f"Initial graph exists: {len(initial_nodes)} nodes")

        # Analyze initial enrichment state
        initial_states = analyze_enrichment_state(initial_nodes)
        print("\nInitial enrichment states:")
        for state, node_ids in sorted(initial_states.items()):
            print(f"  {state}: {len(node_ids)}")

        # Find nodes that would be reprocessed
        initial_candidates = find_reprocessing_candidates(initial_nodes)
        print(f"\nNodes needing enrichment BEFORE any scan: {len(initial_candidates)}")
        if initial_candidates:
            print("First 10 candidates:")
            for node_id, reasons in initial_candidates[:10]:
                print(f"  {node_id}")
                for reason in reasons:
                    print(f"    - {reason}")
    else:
        print("No initial graph found - will be created by first scan")
        initial_nodes = {}

    # Run first scan
    result1 = run_scan(1, output_dir)

    # Analyze after first scan
    print("\n" + "-" * 40)
    print("AFTER FIRST SCAN")
    print("-" * 40)

    states1 = analyze_enrichment_state(result1.nodes)
    print("Enrichment states after scan 1:")
    for state, node_ids in sorted(states1.items()):
        print(f"  {state}: {len(node_ids)}")

    # Find nodes that would STILL be reprocessed
    candidates_after_1 = find_reprocessing_candidates(result1.nodes)
    print(f"\nNodes STILL needing enrichment after scan 1: {len(candidates_after_1)}")
    if candidates_after_1:
        print("These nodes will be re-processed on next scan:")
        for node_id, reasons in candidates_after_1[:20]:
            print(f"  {node_id}")
            for reason in reasons:
                print(f"    - {reason}")

    # Run second scan
    result2 = run_scan(2, output_dir)

    # Analyze after second scan
    print("\n" + "-" * 40)
    print("AFTER SECOND SCAN")
    print("-" * 40)

    states2 = analyze_enrichment_state(result2.nodes)
    print("Enrichment states after scan 2:")
    for state, node_ids in sorted(states2.items()):
        print(f"  {state}: {len(node_ids)}")

    # Compare scans
    print("\n" + "-" * 40)
    print("COMPARISON: SCAN 1 vs SCAN 2")
    print("-" * 40)

    comparison = compare_nodes(result1.nodes, result2.nodes)

    print("\nNode changes between scans:")
    for category, node_ids in comparison.items():
        if node_ids:
            print(f"  {category}: {len(node_ids)}")

    # Deep dive into changed nodes
    if comparison["embedding_hash_changed"]:
        print(f"\n*** EMBEDDING HASH CHANGED ({len(comparison['embedding_hash_changed'])}) ***")
        print("These nodes had their embedding_hash change between scans:")
        for node_id in comparison["embedding_hash_changed"][:10]:
            n1 = result1.nodes[node_id]
            n2 = result2.nodes[node_id]
            print(f"\n  {node_id}")
            print(f"    Scan 1 embedding_hash: {getattr(n1, 'embedding_hash', None)}")
            print(f"    Scan 2 embedding_hash: {getattr(n2, 'embedding_hash', None)}")
            print(f"    Scan 1 content_hash:   {getattr(n1, 'content_hash', None)}")
            print(f"    Scan 2 content_hash:   {getattr(n2, 'content_hash', None)}")

    if comparison["content_hash_changed"]:
        print(f"\n*** CONTENT HASH CHANGED ({len(comparison['content_hash_changed'])}) ***")
        print("CRITICAL: These nodes have DIFFERENT content_hash between scans!")
        print("This means the parsed content is changing even though files are unchanged!")

        for node_id in comparison["content_hash_changed"][:10]:
            n1 = result1.nodes[node_id]
            n2 = result2.nodes[node_id]
            print(f"\n  {node_id}")
            diffs = deep_compare_node(n1, n2, node_id)
            for field, diff in diffs.items():
                print(f"    {field}:")
                print(f"      before: {diff['before']}")
                print(f"      after:  {diff['after']}")

    if comparison["embedding_changed"]:
        print(f"\n*** EMBEDDINGS CHANGED ({len(comparison['embedding_changed'])}) ***")
        print("Nodes where actual embedding vectors changed:")
        for node_id in comparison["embedding_changed"][:5]:
            print(f"  {node_id}")

    # Check for nodes that STILL need processing after 2 scans
    candidates_after_2 = find_reprocessing_candidates(result2.nodes)
    print(f"\n\nNodes STILL needing enrichment after scan 2: {len(candidates_after_2)}")
    if candidates_after_2:
        print("BUG: These nodes will be re-processed AGAIN on next scan:")
        for node_id, reasons in candidates_after_2[:20]:
            print(f"  {node_id}")
            for reason in reasons:
                print(f"    - {reason}")

    # Parse output for enrichment counts
    print("\n" + "-" * 40)
    print("ENRICHMENT COUNTS FROM OUTPUT")
    print("-" * 40)

    import re

    for i, result in enumerate([result1, result2], 1):
        print(f"\nScan {i}:")

        # Look for "Enriched: X nodes" pattern
        enriched_matches = re.findall(r"Enriched: (\d+) nodes?", result.output)
        preserved_matches = re.findall(r"Preserved: (\d+) nodes?", result.output)

        print(f"  Enriched counts found: {enriched_matches}")
        print(f"  Preserved counts found: {preserved_matches}")

    # Save detailed report
    report_path = output_dir / "investigation_report.md"
    with open(report_path, "w") as f:
        f.write("# Embedding Reprocessing Investigation Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        f.write("## Summary\n\n")
        f.write(f"- Nodes after scan 1: {len(result1.nodes)}\n")
        f.write(f"- Nodes after scan 2: {len(result2.nodes)}\n")
        f.write(f"- Nodes needing enrichment after scan 2: {len(candidates_after_2)}\n")

        f.write("\n## Content Hash Changes\n\n")
        if comparison["content_hash_changed"]:
            for node_id in comparison["content_hash_changed"]:
                n1 = result1.nodes[node_id]
                n2 = result2.nodes[node_id]
                f.write(f"### {node_id}\n")
                diffs = deep_compare_node(n1, n2, node_id)
                for field, diff in diffs.items():
                    f.write(f"- **{field}**:\n")
                    f.write(f"  - before: `{diff['before']}`\n")
                    f.write(f"  - after: `{diff['after']}`\n")
                f.write("\n")
        else:
            f.write("No content hash changes detected.\n")

        f.write("\n## Persistent Reprocessing Candidates\n\n")
        for node_id, reasons in candidates_after_2:
            f.write(f"### {node_id}\n")
            for reason in reasons:
                f.write(f"- {reason}\n")
            f.write("\n")

    print(f"\nDetailed report saved to: {report_path}")

    print("\n" + "=" * 80)
    print("INVESTIGATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
