#!/usr/bin/env python3
"""Find all duplicate node_ids across the codebase."""

import pickle
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from fs2.config.objects import ScanConfig, GraphConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters import FileSystemScanner, TreeSitterParser


def main():
    print("=" * 80)
    print("DUPLICATE NODE_ID FINDER")
    print("=" * 80)

    # Scan all files
    scan_config = ScanConfig(
        scan_paths=["src", "tests", "docs"],
        respect_gitignore=True,
        max_file_size_kb=500,
    )
    graph_config = GraphConfig(graph_path=".fs2/graph.pickle")
    config = FakeConfigurationService(scan_config, graph_config)

    file_scanner = FileSystemScanner(config)
    ast_parser = TreeSitterParser(config)

    print("\nScanning files...")
    scan_results = file_scanner.scan()
    print(f"Found {len(scan_results)} files")

    print("\nParsing files...")
    all_nodes = []
    for result in scan_results:
        nodes = ast_parser.parse(result.path)
        all_nodes.extend(nodes)

    print(f"Parsed {len(all_nodes)} nodes")

    # Find duplicates
    id_counts = Counter(n.node_id for n in all_nodes)
    duplicates = [(nid, count) for nid, count in id_counts.items() if count > 1]

    print(f"\n{'=' * 40}")
    print(f"DUPLICATES: {len(duplicates)}")
    print(f"{'=' * 40}")

    if duplicates:
        for nid, count in sorted(duplicates, key=lambda x: -x[1]):
            print(f"\n  {count}x: {nid}")
            # Show the nodes
            matching = [n for n in all_nodes if n.node_id == nid]
            for i, node in enumerate(matching[:3]):
                print(f"      [{i+1}] line {node.start_line}: {node.signature[:50]}...")
            if len(matching) > 3:
                print(f"      ... and {len(matching) - 3} more")
    else:
        print("  No duplicates found!")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
