#!/usr/bin/env python3
"""Graph database report - analyze node distribution by language and type.

Usage:
    python scripts/graph_report.py [--graph-path .fs2/graph.pickle]
    just graph-report
"""

import argparse
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def load_graph(graph_path: Path) -> tuple[dict, dict]:
    """Load and parse the graph pickle file.

    Returns:
        Tuple of (metadata_dict, nodes_dict)
    """
    if not graph_path.exists():
        raise FileNotFoundError(f"Graph not found: {graph_path}")

    with open(graph_path, "rb") as f:
        data = pickle.load(f)

    # Graph format is (metadata_dict, networkx_graph)
    # where networkx nodes have 'data' attribute containing CodeNode
    if isinstance(data, tuple) and len(data) == 2:
        metadata = data[0] if isinstance(data[0], dict) else {}
        graph = data[1]

        # Extract CodeNode objects from NetworkX graph
        nodes_dict = {}
        if hasattr(graph, 'nodes'):
            for node_id, node_attrs in graph.nodes(data=True):
                if 'data' in node_attrs:
                    nodes_dict[node_id] = node_attrs['data']

        return metadata, nodes_dict
    else:
        return {}, {}


def analyze_nodes(nodes: dict) -> dict:
    """Analyze nodes and return statistics."""
    stats = {
        "total": len(nodes),
        "by_language": Counter(),
        "by_kind": Counter(),
        "by_language_kind": defaultdict(Counter),
        "by_category": Counter(),
        "with_content": 0,
        "with_smart_content": 0,
        "with_embedding": 0,
        "empty_content": 0,
    }

    for node in nodes.values():
        lang = getattr(node, "language", "unknown") or "unknown"
        kind = getattr(node, "ts_kind", "unknown") or "unknown"
        category = getattr(node, "category", "unknown") or "unknown"

        stats["by_language"][lang] += 1
        stats["by_kind"][kind] += 1
        stats["by_language_kind"][lang][kind] += 1
        stats["by_category"][category] += 1

        content = getattr(node, "content", None)
        if content and content.strip():
            stats["with_content"] += 1
        else:
            stats["empty_content"] += 1

        if getattr(node, "smart_content", None):
            stats["with_smart_content"] += 1

        if getattr(node, "embedding", None):
            stats["with_embedding"] += 1

    return stats


def render_report(console: Console, stats: dict, metadata: dict, graph_path: Path) -> None:
    """Render the report using Rich."""
    # Header
    console.print()
    console.print(
        Panel(
            f"[bold]Graph Database Report[/bold]\n[dim]{graph_path}[/dim]",
            border_style="blue",
        )
    )
    console.print()

    # Metadata table
    if metadata:
        meta_table = Table(title="Graph Metadata", show_header=False, box=None)
        meta_table.add_column("Key", style="dim")
        meta_table.add_column("Value", style="white")
        meta_table.add_row("Format Version", str(metadata.get("format_version", "N/A")))
        meta_table.add_row("Created", str(metadata.get("created_at", "N/A"))[:19])
        meta_table.add_row("Embedding Model", str(metadata.get("embedding_model", "N/A")))
        meta_table.add_row("Dimensions", str(metadata.get("embedding_dimensions", "N/A")))
        chunk_params = metadata.get("chunk_params", {})
        if chunk_params:
            code_max = chunk_params.get("code", {}).get("max_tokens", "?")
            doc_max = chunk_params.get("documentation", {}).get("max_tokens", "?")
            meta_table.add_row("Chunk Sizes", f"code={code_max}, doc={doc_max}")
        console.print(meta_table)
        console.print()

    # Summary table
    summary = Table(title="Summary", show_header=False, box=None)
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="green", justify="right")

    summary.add_row("Total Nodes", f"{stats['total']:,}")
    summary.add_row("With Content", f"{stats['with_content']:,}")
    summary.add_row("Empty Content", f"{stats['empty_content']:,}")
    summary.add_row("With Smart Content", f"{stats['with_smart_content']:,}")
    summary.add_row("With Embeddings", f"{stats['with_embedding']:,}")
    summary.add_row("Languages", str(len(stats["by_language"])))

    console.print(summary)
    console.print()

    # Nodes by Language
    lang_table = Table(title="Nodes by Language", box=None)
    lang_table.add_column("Language", style="cyan")
    lang_table.add_column("Count", style="green", justify="right")
    lang_table.add_column("Pct", style="yellow", justify="right")
    lang_table.add_column("Top Kinds", style="dim")

    for lang, count in stats["by_language"].most_common():
        pct = count / stats["total"] * 100
        # Get top 3 kinds for this language
        top_kinds = stats["by_language_kind"][lang].most_common(3)
        kinds_str = ", ".join(f"{k}({c})" for k, c in top_kinds)
        lang_table.add_row(lang, f"{count:,}", f"{pct:.1f}%", kinds_str)

    console.print(lang_table)
    console.print()

    # Nodes by Category
    cat_table = Table(title="Nodes by Category", box=None)
    cat_table.add_column("Category", style="cyan")
    cat_table.add_column("Count", style="green", justify="right")
    cat_table.add_column("Pct", style="yellow", justify="right")

    for cat, count in stats["by_category"].most_common():
        pct = count / stats["total"] * 100
        cat_table.add_row(cat, f"{count:,}", f"{pct:.1f}%")

    console.print(cat_table)
    console.print()

    # Top 20 Node Kinds
    kind_table = Table(title="Top 20 Node Kinds (ts_kind)", box=None)
    kind_table.add_column("Kind", style="cyan")
    kind_table.add_column("Count", style="green", justify="right")
    kind_table.add_column("Pct", style="yellow", justify="right")

    for kind, count in stats["by_kind"].most_common(20):
        pct = count / stats["total"] * 100
        kind_table.add_row(kind, f"{count:,}", f"{pct:.1f}%")

    console.print(kind_table)
    console.print()

    # Language breakdown details
    console.print("[bold]Detailed Language Breakdown[/bold]")
    console.print()

    for lang, count in stats["by_language"].most_common():
        if count < 10:  # Skip languages with few nodes
            continue

        detail_table = Table(title=f"{lang} ({count:,} nodes)", box=None)
        detail_table.add_column("Kind", style="cyan")
        detail_table.add_column("Count", style="green", justify="right")

        for kind, kcount in stats["by_language_kind"][lang].most_common(10):
            detail_table.add_row(kind, f"{kcount:,}")

        console.print(detail_table)
        console.print()


def main():
    parser = argparse.ArgumentParser(description="Graph database report")
    parser.add_argument(
        "--graph-path",
        type=Path,
        default=Path(".fs2/graph.pickle"),
        help="Path to graph pickle file",
    )
    args = parser.parse_args()

    console = Console()

    try:
        metadata, nodes = load_graph(args.graph_path)
        stats = analyze_nodes(nodes)
        render_report(console, stats, metadata, args.graph_path)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error loading graph:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
