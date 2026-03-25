#!/usr/bin/env python3
"""
Benchmark: Serena via stdio transport vs HTTP.

Compares:
1. stdio (pipe to serena-mcp-server process) 
2. streamable-http (HTTP server on localhost)

Usage:
    uv run python scripts/serena-explore/benchmark_stdio.py
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
PROJECT_DIR = os.getcwd()


def load_nodes(limit: int | None = None) -> list[dict]:
    with open(GRAPH_PATH, "rb") as f:
        _, graph = pickle.load(f)
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
            "qualified_name": data.qualified_name,
            "file_path": file_path,
        })
        if limit and len(nodes) >= limit:
            break
    return nodes


async def query_node(client: Client, node: dict) -> dict:
    qname = node["qualified_name"] or ""
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

        return {"elapsed_ms": elapsed * 1000, "ref_count": ref_count, "error": None}
    except Exception as e:
        return {"elapsed_ms": (time.monotonic() - t0) * 1000, "ref_count": 0,
                "error": str(e)[:100]}


async def benchmark_stdio(nodes: list[dict]) -> dict:
    """Benchmark via stdio transport (pipe to process)."""
    config = {
        "mcpServers": {
            "serena": {
                "command": "serena-mcp-server",
                "args": ["--project", "fs2",
                         "--enable-web-dashboard", "false",
                         "--open-web-dashboard", "false",
                         "--log-level", "ERROR"],
            }
        }
    }

    print(f"\n  STDIO: Connecting...")
    overall_start = time.monotonic()

    async with Client(config, timeout=30) as client:
        connect_time = time.monotonic() - overall_start
        print(f"  STDIO: Connected in {connect_time*1000:.0f}ms")

        # Warmup
        await client.call_tool("find_symbol", {"name_path_pattern": "GraphStore"})

        results = []
        total_refs = 0
        errors = 0
        t0 = time.monotonic()

        for i, node in enumerate(nodes):
            r = await query_node(client, node)
            if r.get("skipped"):
                continue
            results.append(r)
            total_refs += r.get("ref_count", 0)
            if r.get("error"):
                errors += 1

            if (i + 1) % 50 == 0 or i == len(nodes) - 1:
                elapsed = time.monotonic() - t0
                avg = elapsed / len(results) * 1000 if results else 0
                print(f"    [{i+1}/{len(nodes)}] avg={avg:.0f}ms/node, "
                      f"refs={total_refs}, errors={errors}, elapsed={elapsed:.1f}s")

        wall_clock = time.monotonic() - t0

    times = [r["elapsed_ms"] for r in results if not r.get("error")]
    return {
        "transport": "stdio",
        "nodes": len(results),
        "refs": total_refs,
        "errors": errors,
        "wall_clock_s": wall_clock,
        "throughput": len(results) / wall_clock if wall_clock > 0 else 0,
        "avg_ms": sum(times) / len(times) if times else 0,
        "median_ms": sorted(times)[len(times) // 2] if times else 0,
        "p95_ms": sorted(times)[int(len(times) * 0.95)] if times else 0,
        "max_ms": max(times) if times else 0,
        "connect_ms": connect_time * 1000,
    }


async def benchmark_http(nodes: list[dict], port: int = 8390) -> dict:
    """Benchmark via streamable-http transport."""
    # Start HTTP server
    proc = subprocess.Popen(
        ["serena-mcp-server",
         "--project", "fs2",
         "--transport", "streamable-http",
         "--host", "127.0.0.1",
         "--port", str(port),
         "--open-web-dashboard", "false",
         "--enable-web-dashboard", "false",
         "--log-level", "ERROR"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=PROJECT_DIR,
        start_new_session=True,
    )

    print(f"\n  HTTP: Starting server on port {port}...")
    # Wait for ready
    import urllib.request, urllib.error
    start = time.monotonic()
    while time.monotonic() - start < 30:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/mcp/",
                                         method="POST", data=b"{}")
            req.add_header("Content-Type", "application/json")
            urllib.request.urlopen(req, timeout=2)
            break
        except urllib.error.HTTPError:
            break
        except Exception:
            time.sleep(0.5)

    connect_time = time.monotonic() - start
    print(f"  HTTP: Server ready in {connect_time*1000:.0f}ms")

    url = f"http://127.0.0.1:{port}/mcp/"

    try:
        async with Client(url, timeout=30) as client:
            # Warmup
            await client.call_tool("find_symbol", {"name_path_pattern": "GraphStore"})

            results = []
            total_refs = 0
            errors = 0
            t0 = time.monotonic()

            for i, node in enumerate(nodes):
                r = await query_node(client, node)
                if r.get("skipped"):
                    continue
                results.append(r)
                total_refs += r.get("ref_count", 0)
                if r.get("error"):
                    errors += 1

                if (i + 1) % 50 == 0 or i == len(nodes) - 1:
                    elapsed = time.monotonic() - t0
                    avg = elapsed / len(results) * 1000 if results else 0
                    print(f"    [{i+1}/{len(nodes)}] avg={avg:.0f}ms/node, "
                          f"refs={total_refs}, errors={errors}, elapsed={elapsed:.1f}s")

            wall_clock = time.monotonic() - t0

    finally:
        try:
            os.kill(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        # Kill children
        time.sleep(1)
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if str(port) in line and ("serena" in line or "pyright" in line):
                parts = line.split()
                if len(parts) > 1:
                    try:
                        os.kill(int(parts[1]), signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    times = [r["elapsed_ms"] for r in results if not r.get("error")]
    return {
        "transport": "streamable-http",
        "nodes": len(results),
        "refs": total_refs,
        "errors": errors,
        "wall_clock_s": wall_clock,
        "throughput": len(results) / wall_clock if wall_clock > 0 else 0,
        "avg_ms": sum(times) / len(times) if times else 0,
        "median_ms": sorted(times)[len(times) // 2] if times else 0,
        "p95_ms": sorted(times)[int(len(times) * 0.95)] if times else 0,
        "max_ms": max(times) if times else 0,
        "connect_ms": connect_time * 1000,
    }


async def main():
    sample_size = int(sys.argv[1]) if len(sys.argv) > 1 else 200

    print(f"═══ Serena Transport Benchmark: stdio vs HTTP ═══")
    print(f"Sample: {sample_size} nodes\n")

    print("Loading graph...")
    nodes = load_nodes(limit=sample_size)
    print(f"Loaded {len(nodes)} callable/type nodes\n")

    # Run stdio first
    stdio_result = await benchmark_stdio(nodes)

    # Short pause between tests
    await asyncio.sleep(2)

    # Run HTTP
    http_result = await benchmark_http(nodes)

    # Summary
    print(f"\n{'='*60}")
    print(f"  RESULTS: stdio vs HTTP ({len(nodes)} nodes)")
    print(f"{'='*60}")
    print(f"  {'Metric':<20} {'stdio':>12} {'HTTP':>12} {'Δ':>12}")
    print(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*12}")

    for key in ["wall_clock_s", "throughput", "avg_ms", "median_ms", "p95_ms", "max_ms", "connect_ms", "refs", "errors"]:
        sv = stdio_result[key]
        hv = http_result[key]
        if isinstance(sv, float):
            if key.endswith("_s"):
                delta = f"{sv/hv:.2f}x" if hv > 0 else "—"
                print(f"  {key:<20} {sv:>11.1f}s {hv:>11.1f}s {delta:>12}")
            elif key == "throughput":
                delta = f"{sv/hv:.2f}x" if hv > 0 else "—"
                print(f"  {key:<20} {sv:>10.1f}/s {hv:>10.1f}/s {delta:>12}")
            else:
                delta = f"{sv/hv:.2f}x" if hv > 0 else "—"
                print(f"  {key:<20} {sv:>10.0f}ms {hv:>10.0f}ms {delta:>12}")
        else:
            print(f"  {key:<20} {sv:>12} {hv:>12}")


if __name__ == "__main__":
    asyncio.run(main())
