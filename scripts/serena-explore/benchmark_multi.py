#!/usr/bin/env python3
"""
Benchmark v3: N Serena instances on different ports, true parallelism.

Spawns N serena-mcp-server processes, distributes nodes round-robin,
queries all instances concurrently.

Usage:
    uv run python scripts/serena-explore/benchmark_multi.py [num_instances]

Default: 10 instances on ports 8330-8339
"""

from __future__ import annotations

import asyncio
import json
import os
import pickle
import signal
import subprocess
import sys
import time
from pathlib import Path

from fastmcp import Client

GRAPH_PATH = Path(".fs2/graph.pickle")
BASE_PORT = 8330
PROJECT_DIR = os.getcwd()


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


def start_serena_instances(n: int) -> list[int]:
    """Start N serena-mcp-server instances on consecutive ports. Returns PIDs."""
    pids = []

    for i in range(n):
        port = BASE_PORT + i
        proc = subprocess.Popen(
            [
                "serena-mcp-server",
                "--project", "fs2",
                "--transport", "streamable-http",
                "--host", "127.0.0.1",
                "--port", str(port),
                "--open-web-dashboard", "false",
                "--enable-web-dashboard", "false",
                "--log-level", "ERROR",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=PROJECT_DIR,
            start_new_session=True,  # Detach from parent
        )
        pids.append(proc.pid)

    print(f"  Launched {n} instances (ports {BASE_PORT}-{BASE_PORT+n-1})")
    return pids


def wait_for_instances(n: int, timeout: float = 90):
    """Wait until all instances are responding to HTTP."""
    import urllib.request
    start = time.monotonic()
    for i in range(n):
        port = BASE_PORT + i
        url = f"http://127.0.0.1:{port}/mcp/"
        while True:
            elapsed = time.monotonic() - start
            if elapsed > timeout:
                raise TimeoutError(f"Instance {i} on port {port} didn't start in {timeout}s")
            try:
                # POST returns 307 when server is up (MCP protocol)
                req = urllib.request.Request(url, method="POST", data=b"{}")
                req.add_header("Content-Type", "application/json")
                urllib.request.urlopen(req, timeout=2)
                break
            except urllib.error.HTTPError:
                # Any HTTP error means server is responding
                break
            except Exception:
                time.sleep(0.5)
    elapsed = time.monotonic() - start
    print(f"  All {n} instances ready ({elapsed:.1f}s)")


def stop_instances(pids: list[int]):
    """Stop all instances by killing process groups."""
    # Find all serena-related processes
    try:
        result = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            if "serena-mcp-server" in line and "grep" not in line:
                parts = line.split()
                if len(parts) > 1:
                    pid = int(parts[1])
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
    except Exception:
        pass

    # Also kill pyright/node children
    time.sleep(1)
    try:
        result = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            if ("pyright" in line or "langserver" in line) and "grep" not in line:
                parts = line.split()
                if len(parts) > 1:
                    pid = int(parts[1])
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
    except Exception:
        pass


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


async def process_shard(instance_idx: int, shard: list[dict]) -> list[dict]:
    """Process a shard of nodes against one Serena instance."""
    port = BASE_PORT + instance_idx
    url = f"http://127.0.0.1:{port}/mcp/"
    results = []

    async with Client(url) as client:
        # Warmup
        try:
            await client.call_tool("find_symbol", {"name_path_pattern": "GraphStore"})
        except Exception:
            pass

        for node in shard:
            r = await query_node(client, node)
            results.append(r)

    return results


async def run_benchmark(num_instances: int, nodes: list[dict]):
    """Distribute nodes across instances and run concurrently."""
    # Shard nodes round-robin
    shards: list[list[dict]] = [[] for _ in range(num_instances)]
    for i, node in enumerate(nodes):
        shards[i % num_instances].append(node)

    print(f"\n  Shards: {[len(s) for s in shards]}")

    overall_start = time.monotonic()

    # Launch all shards concurrently
    shard_tasks = [
        process_shard(i, shard)
        for i, shard in enumerate(shards)
    ]

    # Progress reporting via a separate task
    async def progress():
        while True:
            await asyncio.sleep(5)
            elapsed = time.monotonic() - overall_start
            print(f"  ... {elapsed:.0f}s elapsed")

    progress_task = asyncio.create_task(progress())

    all_results = await asyncio.gather(*shard_tasks)

    progress_task.cancel()
    try:
        await progress_task
    except asyncio.CancelledError:
        pass

    overall_elapsed = time.monotonic() - overall_start

    # Flatten results
    results = []
    for shard_results in all_results:
        results.extend(shard_results)

    # Stats
    processed = [r for r in results if not r.get("skipped")]
    errors = sum(1 for r in processed if r.get("error"))
    total_refs = sum(r.get("ref_count", 0) for r in processed)
    times = [r["elapsed_ms"] for r in processed if not r.get("error")]

    print(f"\n{'='*60}")
    print(f"  MULTI-INSTANCE BENCHMARK ({num_instances} instances)")
    print(f"{'='*60}")
    print(f"  Nodes processed:  {len(processed)}")
    print(f"  Errors:           {errors}")
    print(f"  Total refs:       {total_refs}")
    print(f"  Wall clock:       {overall_elapsed:.1f}s")
    print(f"  Throughput:       {len(processed)/overall_elapsed:.1f} nodes/s")
    if times:
        times_sorted = sorted(times)
        print(f"  Avg latency:      {sum(times)/len(times):.1f}ms")
        print(f"  Median latency:   {times_sorted[len(times)//2]:.1f}ms")
        print(f"  p95 latency:      {times_sorted[int(len(times)*0.95)]:.1f}ms")
        print(f"  Max latency:      {max(times):.1f}ms")

    seq_estimate = 411.7  # from sequential benchmark
    print(f"\n  Sequential was:   {seq_estimate:.1f}s")
    print(f"  Speedup:          {seq_estimate/overall_elapsed:.1f}x")


def main():
    num_instances = int(sys.argv[1]) if len(sys.argv) > 1 else 10

    print(f"Loading graph...")
    nodes = load_graph_nodes()
    print(f"{len(nodes)} callable/type nodes\n")

    print(f"Starting {num_instances} Serena instances...")
    pids = start_serena_instances(num_instances)

    try:
        print(f"Waiting for instances to be ready...")
        wait_for_instances(num_instances)

        asyncio.run(run_benchmark(num_instances, nodes))

    finally:
        print(f"\nStopping {num_instances} instances...")
        stop_instances(pids)
        print("Done.")


if __name__ == "__main__":
    main()
