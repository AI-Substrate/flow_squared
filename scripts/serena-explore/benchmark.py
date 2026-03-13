#!/usr/bin/env python3
"""
Benchmark: Walk every node in graph.pickle, query Serena for callers/callees.

Loads the fs2 graph, iterates every callable/type node, and asks Serena
for find_referencing_symbols (callers/incoming) for each one.

Expects serena-mcp-server running at http://127.0.0.1:8321

Usage:
    uv run python scripts/serena-explore/benchmark.py
"""

from __future__ import annotations

import asyncio
import json
import pickle
import sys
import time
from pathlib import Path

from fastmcp import Client

SERVER_URL = "http://127.0.0.1:8321/mcp/"
GRAPH_PATH = Path(".fs2/graph.pickle")


def load_graph_nodes() -> list[dict]:
    """Load graph.pickle and extract node info.

    CodeNode has: node_id (category:file_path:qualified_name),
    category, name, qualified_name. The file_path is embedded
    in the node_id between the first and second colon.
    """
    with open(GRAPH_PATH, "rb") as f:
        metadata, graph = pickle.load(f)

    print(f"Graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
    print(f"Format: {metadata.get('format_version')}")

    nodes = []
    for node_id in graph.nodes:
        data = graph.nodes[node_id].get("data")
        if data is None:
            continue
        category = data.category
        # Only callable and type nodes — these have callers/callees
        if category not in ("callable", "type"):
            continue

        # node_id = "callable:src/fs2/core/foo.py:MyClass.method"
        # Split on ":" with max 2 splits → [category, file_path, qualified_name]
        parts = node_id.split(":", 2)
        file_path = parts[1] if len(parts) > 2 else None
        qualified_name = data.qualified_name

        # Only Python files (Serena project is Python)
        if file_path and not file_path.endswith(".py"):
            continue

        nodes.append({
            "node_id": node_id,
            "category": category,
            "name": data.name,
            "qualified_name": qualified_name,
            "file_path": file_path,
        })

    return nodes


async def benchmark_node(client: Client, node: dict) -> dict:
    """Query Serena for references to a single node. Returns timing + counts."""
    qualified_name = node["qualified_name"] or node["name"]
    file_path = node["file_path"]

    if not qualified_name or not file_path:
        return {"node_id": node["node_id"], "skipped": True, "reason": "missing name/path"}

    # Serena name_path uses "/" separator (e.g. "MyClass/my_method")
    name_path = qualified_name.replace(".", "/")

    t0 = time.monotonic()
    try:
        result = await client.call_tool("find_referencing_symbols", {
            "name_path": name_path,
            "relative_path": file_path,
        })
        elapsed = time.monotonic() - t0

        # Count references from result
        ref_count = 0
        if hasattr(result, "content"):
            for item in result.content:
                text = getattr(item, "text", "")
                if text:
                    try:
                        data = json.loads(text)
                        for file_refs in data.values():
                            for kind_refs in file_refs.values():
                                ref_count += len(kind_refs)
                    except (json.JSONDecodeError, TypeError):
                        pass

        return {
            "node_id": node["node_id"],
            "name_path": name_path,
            "elapsed_ms": elapsed * 1000,
            "ref_count": ref_count,
            "error": None,
        }

    except Exception as e:
        elapsed = time.monotonic() - t0
        return {
            "node_id": node["node_id"],
            "name_path": name_path,
            "elapsed_ms": elapsed * 1000,
            "ref_count": 0,
            "error": str(e)[:100],
        }


async def main():
    print(f"Loading graph from {GRAPH_PATH}...")
    nodes = load_graph_nodes()
    print(f"Found {len(nodes)} callable/type nodes to benchmark\n")

    print(f"Connecting to Serena at {SERVER_URL}...")
    async with Client(SERVER_URL) as client:
        # Warm up — first call is always slow
        print("Warming up Serena (first call)...")
        t0 = time.monotonic()
        try:
            await client.call_tool("find_symbol", {"name_path_pattern": "GraphStore"})
        except Exception:
            pass
        warmup = time.monotonic() - t0
        print(f"Warmup: {warmup*1000:.0f}ms\n")

        # Benchmark all nodes
        results = []
        errors = 0
        skipped = 0
        total_refs = 0

        overall_start = time.monotonic()

        for i, node in enumerate(nodes):
            r = await benchmark_node(client, node)
            results.append(r)

            if r.get("skipped"):
                skipped += 1
                continue
            if r.get("error"):
                errors += 1

            total_refs += r.get("ref_count", 0)

            # Progress every 50 nodes
            if (i + 1) % 50 == 0 or i == len(nodes) - 1:
                elapsed_so_far = time.monotonic() - overall_start
                avg = elapsed_so_far / (i + 1 - skipped) * 1000 if (i + 1 - skipped) > 0 else 0
                print(f"  [{i+1}/{len(nodes)}] avg={avg:.0f}ms/node, "
                      f"refs={total_refs}, errors={errors}, "
                      f"elapsed={elapsed_so_far:.1f}s")

        overall_elapsed = time.monotonic() - overall_start

        # Summary
        processed = [r for r in results if not r.get("skipped")]
        times = [r["elapsed_ms"] for r in processed if not r.get("error")]

        print(f"\n{'='*60}")
        print(f"  BENCHMARK RESULTS")
        print(f"{'='*60}")
        print(f"  Total nodes:     {len(nodes)}")
        print(f"  Processed:       {len(processed)}")
        print(f"  Skipped:         {skipped}")
        print(f"  Errors:          {errors}")
        print(f"  Total refs:      {total_refs}")
        print(f"  Total time:      {overall_elapsed:.1f}s")
        if times:
            print(f"  Avg per node:    {sum(times)/len(times):.1f}ms")
            print(f"  Median:          {sorted(times)[len(times)//2]:.1f}ms")
            print(f"  Min:             {min(times):.1f}ms")
            print(f"  Max:             {max(times):.1f}ms")
            print(f"  p95:             {sorted(times)[int(len(times)*0.95)]:.1f}ms")
            print(f"  p99:             {sorted(times)[int(len(times)*0.99)]:.1f}ms")

        # Top 10 slowest
        if times:
            print(f"\n  Top 10 slowest:")
            slowest = sorted(processed, key=lambda r: r.get("elapsed_ms", 0), reverse=True)[:10]
            for r in slowest:
                print(f"    {r['elapsed_ms']:7.0f}ms  refs={r.get('ref_count',0):3d}  {r['name_path']}")

        # Top 10 most referenced
        if processed:
            print(f"\n  Top 10 most referenced:")
            most_refs = sorted(processed, key=lambda r: r.get("ref_count", 0), reverse=True)[:10]
            for r in most_refs:
                print(f"    refs={r.get('ref_count',0):3d}  {r['elapsed_ms']:7.0f}ms  {r['name_path']}")


if __name__ == "__main__":
    asyncio.run(main())
