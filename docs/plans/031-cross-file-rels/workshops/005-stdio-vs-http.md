# Workshop: Serena Transport — stdio vs HTTP Performance

**Type**: Integration Pattern
**Plan**: 031-cross-file-rels
**Spec**: [cross-file-rels-spec.md](../cross-file-rels-spec.md)
**Created**: 2026-03-13
**Status**: Draft

**Related Documents**:
- [002-serena-benchmarks.md](002-serena-benchmarks.md) — HTTP benchmark data (full 3634 nodes)

---

## Purpose

Determine whether stdio transport is faster than HTTP for communicating with Serena. The hypothesis is that eliminating HTTP overhead (TCP, HTTP framing, JSON-RPC over SSE) should reduce per-call latency. This workshop provides empirical data to decide which transport the CrossFileRelsStage should use.

## Key Questions Addressed

- Is stdio faster than streamable-http for Serena MCP calls?
- Does transport choice affect the multi-instance parallelism strategy?
- Which transport should the CrossFileRelsStage use?

---

## Benchmark Setup

### Methodology

Both transports tested sequentially against the **same 200 nodes** from the fs2 graph. Each test:
1. Starts a fresh Serena instance (stdio via process pipe, HTTP via localhost server)
2. Warmup call (`find_symbol` for `GraphStore`)
3. Calls `find_referencing_symbols` for each node, measuring per-call latency
4. Computes wall clock, throughput, avg/median/p95/max latency

### Environment

Same as Workshop 002: MacBook Pro (Apple Silicon), Python 3.12, Serena 0.1.4, fs2 graph with 5332 nodes.

### Transport Mechanics

| Aspect | stdio | streamable-http |
|--------|-------|-----------------|
| Protocol | MCP over stdin/stdout pipe | MCP over HTTP POST + SSE |
| Connection | Process pipe (no TCP) | TCP localhost |
| Serialization | JSON-RPC both ways | JSON-RPC both ways |
| Process model | Parent spawns child, pipes stdio | Separate uvicorn server process |
| FastMCP Client | `MCPConfig` dict with `command` | URL string `http://127.0.0.1:PORT/mcp/` |

---

## Results

### Head-to-Head: 200 Nodes

```
$ uv run python scripts/serena-explore/benchmark_stdio.py 200
```

| Metric | stdio | HTTP | Δ |
|--------|-------|------|---|
| **Wall clock** | **25.5s** | **25.6s** | **1.00x** |
| **Throughput** | 7.8/s | 7.8/s | 1.00x |
| Avg latency | 128ms | 128ms | 1.00x |
| Median latency | 117ms | 117ms | 1.00x |
| p95 latency | 123ms | 125ms | 0.98x |
| Max latency | 2148ms | 2152ms | 1.00x |
| Connect time | 1421ms | 1548ms | 0.92x |
| **Refs found** | **25** | **25** | identical |
| **Errors** | **0** | **0** | identical |

### Analysis

**No measurable difference.** stdio and HTTP are within noise (±0.5%) on every metric.

**Why?** The bottleneck is **Pyright** — each `find_referencing_symbols` call takes ~110-130ms of LSP processing time. Transport overhead is:
- stdio: ~0.1ms (pipe write + pipe read)
- HTTP: ~1-2ms (TCP + HTTP framing + SSE parsing)

Both are **negligible** compared to 110ms of actual work. Transport is <2% of total time.

---

## Implications for Multi-Instance Strategy

### stdio: One Process Per Instance (Parent-Child)

```python
# FastMCP stdio model: parent spawns N children
config = {
    "mcpServers": {
        "serena-0": {"command": "serena-mcp-server", "args": ["--project", "fs2"]},
        "serena-1": {"command": "serena-mcp-server", "args": ["--project", "fs2"]},
        # ... N instances
    }
}
client = Client(config)  # Composite client, tools prefixed: serena-0_find_symbol
```

**Problems with stdio for multi-instance:**
1. **FastMCP composite client** prefixes tool names (`serena-0_find_referencing_symbols`) — adds complexity
2. **Process lifecycle** tied to parent — if parent crashes, all children die
3. **No port allocation** needed (simpler) but **no independent lifecycle** either
4. **Cannot easily shard** — each `Client(config)` creates ALL instances, can't create N separate clients talking to N processes independently without N separate configs

### HTTP: Independent Processes on Ports

```python
# HTTP model: N independent servers
for i in range(N):
    subprocess.Popen(["serena-mcp-server", "--port", str(8330 + i), ...])

# N independent clients
clients = [Client(f"http://127.0.0.1:{8330+i}/mcp/") for i in range(N)]
```

**Advantages of HTTP for multi-instance:**
1. **Independent processes** — each server is fully decoupled
2. **Clean sharding** — each `Client` talks to one server, simple round-robin
3. **Easy health checks** — HTTP readiness probe
4. **Process survival** — server keeps running if one client disconnects
5. **Already proven** — Workshop 002 benchmarked 10/20/30 instances successfully

---

## Decision: Use HTTP (streamable-http)

### Rationale

| Factor | stdio | HTTP | Winner |
|--------|-------|------|--------|
| **Per-call latency** | 128ms | 128ms | Tie |
| **Multi-instance** | Complex (composite client, prefixed tools) | Simple (N independent clients) | **HTTP** |
| **Process lifecycle** | Tied to parent | Independent | **HTTP** |
| **Health checks** | Not available | HTTP probe | **HTTP** |
| **Sharding** | Hard (single client, all instances) | Easy (N clients, round-robin) | **HTTP** |
| **Already benchmarked** | No (single only) | Yes (10/20/30 instances) | **HTTP** |
| **Connect overhead** | 1.4s | 1.5s | Tie |

**stdio offers zero performance advantage** and makes multi-instance management significantly harder. HTTP is the clear winner for the pool architecture.

### When stdio Would Win

- **Single instance only** — slightly simpler setup (no port allocation)
- **Embedded use** — running Serena as a library, not a server
- **Firewall constraints** — no localhost ports needed

None of these apply to the CrossFileRelsStage use case.

---

## Open Questions

### Q1: Should we offer stdio as a config option?

**RESOLVED**: No. HTTP is strictly better for our use case and there's no performance reason to choose stdio. One transport simplifies the codebase. If someone needs stdio in the future, it's a straightforward addition.

---

## Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Transport | **streamable-http** | Zero performance difference; HTTP is simpler for multi-instance pool management |
| stdio option | Not offered | No benefit; adds complexity |

### Authoritative Benchmark Reference

```
Transport comparison (200 nodes, same Serena instance):
  stdio:  128ms avg, 117ms median, 25.5s wall clock
  HTTP:   128ms avg, 117ms median, 25.6s wall clock
  Δ = 1.00x (no difference)
  
Bottleneck: Pyright LSP (~110ms/call), not transport (<2ms/call)
```
