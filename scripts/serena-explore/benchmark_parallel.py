#!/usr/bin/env python3
"""
Benchmark v2: Parallel batches of N concurrent requests to Serena.

Usage:
    uv run python scripts/serena-explore/benchmark_parallel.py [batch_size]

Default batch_size: 10
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
    with open(GRAPH_PATH, "rb") as f:
        metadata, graph = pickle.load(f)
    print(f"Graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

    nodes = []
    for node_id in graph.nodes:
        data = graph.nodes[node_id].get("data")
        if data is None:
            continue
        if data.category not in ("callable", "type"):
            continue
        parts = node_id.split(":", 2)
        file_path = parts[1] if len(parts) > 2 else None
        if file_path and not file_path.endswith(".py"):
            continue
        nodes.append({
            "node_id": node_id,
            "category": data.category,
            "name": data.name,
            "qualified_name": data.qualified_name,
            "file_path": file_path,
        })
    return nodes


async def query_node(client: Client, node: dict) -> dict:
    qname = node["qualified_name"] or node["name"]
    fpath = node["file_path"]
    if not qname or not fpath:
        return {"skipped": True}

    name_path = qname.replace(".", "/")
    t0 = time.monotonic()
    try:
        result = await client.call_tool("find_referencing_symbols", {
            "name_path": name_path,
            "relative_path": fpath,
        })
        elapsed = time.monotonic() - t0

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

        return {"elapsed_ms": elapsed * 1000, "ref_count": ref_count, "error": None,
                "name_path": name_path}
    except Exception as e:
        return {"elapsed_ms": (time.monotonic() - t0) * 1000, "ref_count": 0,
                "error": str(e)[:80], "name_path": name_path}


async def main():
    batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 10

    print(f"Loading graph...")
    nodes = load_graph_nodes()
    print(f"{len(nodes)} callable/type nodes\n")

    print(f"Connecting to Serena at {SERVER_URL}")
    print(f"Batch size: {batch_size} concurrent requests\n")

    async with Client(SERVER_URL) as client:
        # Warmup
        await client.call_tool("find_symbol", {"name_path_pattern": "GraphStore"})

        results = []
        total_refs = 0
        errors = 0
        overall_start = time.monotonic()

        # Process in batches
        for batch_start in range(0, len(nodes), batch_size):
            batch = nodes[batch_start:batch_start + batch_size]

            batch_t0 = time.monotonic()
            batch_results = await asyncio.gather(
                *[query_node(client, n) for n in batch]
            )
            batch_elapsed = time.monotonic() - batch_t0

            for r in batch_results:
                if r.get("skipped"):
                    continue
                results.append(r)
                total_refs += r.get("ref_count", 0)
                if r.get("error"):
                    errors += 1

            done = batch_start + len(batch)
            elapsed_total = time.monotonic() - overall_start
            if done % (batch_size * 5) == 0 or done >= len(nodes):
                throughput = done / elapsed_total if elapsed_total > 0 else 0
                print(f"  [{done}/{len(nodes)}] "
                      f"batch={batch_elapsed*1000:.0f}ms ({batch_elapsed/len(batch)*1000:.0f}ms/node), "
                      f"throughput={throughput:.1f} nodes/s, "
                      f"refs={total_refs}, errors={errors}, "
                      f"elapsed={elapsed_total:.1f}s")

        overall_elapsed = time.monotonic() - overall_start
        times = [r["elapsed_ms"] for r in results if not r.get("error")]

        print(f"\n{'='*60}")
        print(f"  PARALLEL BENCHMARK (batch={batch_size})")
        print(f"{'='*60}")
        print(f"  Nodes processed:  {len(results)}")
        print(f"  Errors:           {errors}")
        print(f"  Total refs:       {total_refs}")
        print(f"  Wall clock:       {overall_elapsed:.1f}s")
        print(f"  Throughput:       {len(results)/overall_elapsed:.1f} nodes/s")
        if times:
            print(f"  Avg latency:      {sum(times)/len(times):.1f}ms")
            print(f"  Median latency:   {sorted(times)[len(times)//2]:.1f}ms")
            print(f"  p95 latency:      {sorted(times)[int(len(times)*0.95)]:.1f}ms")
            print(f"  p99 latency:      {sorted(times)[int(len(times)*0.99)]:.1f}ms")
            print(f"  Max latency:      {max(times):.1f}ms")

        # Compare to sequential baseline
        seq_estimate = len(results) * 114  # ms from sequential benchmark
        print(f"\n  Sequential est:   {seq_estimate/1000:.1f}s")
        print(f"  Speedup:          {seq_estimate/1000/overall_elapsed:.1f}x")


if __name__ == "__main__":
    asyncio.run(main())
