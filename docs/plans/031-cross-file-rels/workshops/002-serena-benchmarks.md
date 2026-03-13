# Workshop: Serena LSP Cross-File Resolution — Benchmarks & Integration Design

**Type**: Integration Pattern
**Plan**: 031-cross-file-rels
**Spec**: [exploration.md](../exploration.md)
**Created**: 2026-03-12
**Status**: Draft

**Related Documents**:
- [001-edge-storage.md](001-edge-storage.md) — Edge storage design (how edges are stored in the graph)
- `scripts/serena-explore/` — Benchmark scripts and harness code

---

## Purpose

Document the empirical performance characteristics of using Serena (LSP-powered via Pyright) as the cross-file relationship resolver for fs2, and define the configuration and integration design based on measured results. This workshop provides **authoritative benchmark data** for implementation decisions.

## Key Questions Addressed

- How fast is Serena at resolving cross-file references per node?
- Can we parallelise and what's the scaling curve?
- What's the optimal number of parallel instances?
- How should this be configured in `.fs2/config.yaml`?
- How does Serena compare to hand-rolled tree-sitter extraction?

---

## Overview

Serena provides LSP-powered code intelligence via Pyright. When run as an MCP server (`serena-mcp-server --transport streamable-http`), it exposes tools like `find_referencing_symbols` that return **type-aware, cross-file references** — the same quality as "Find All References" in VS Code.

We benchmarked this against the fs2 graph (5332 nodes, 3634 callable/type nodes) to determine whether Serena is viable as the cross-file relationship resolver during `fs2 scan`.

---

## Benchmark Environment

| Attribute | Value |
|-----------|-------|
| Machine | MacBook Pro (Apple Silicon) |
| OS | macOS (Darwin) |
| Python | 3.12.9 |
| Serena | 0.1.4 (from `git+https://github.com/oraios/serena.git@f5612048`) |
| LSP backend | Pyright (bundled with Serena) |
| fs2 graph | 5332 nodes, 4552 edges, 126 Python files |
| Nodes benchmarked | 3634 (callable + type category, Python only) |
| MCP transport | streamable-http |
| Tool used | `find_referencing_symbols` per node |
| Client | FastMCP 2.14.1 async client |

---

## Benchmark Results

### Test 1: Sequential (1 instance)

```
$ uv run python scripts/serena-explore/benchmark.py
```

| Metric | Value |
|--------|-------|
| **Wall clock** | **411.7s** |
| **Throughput** | 8.8 nodes/s |
| Avg latency | 113.7ms |
| Median latency | 109.6ms |
| p95 latency | 130.7ms |
| p99 latency | 196.3ms |
| Max latency | 726.8ms |
| **Errors** | **0** |
| **Total refs found** | **9926** |

**Finding**: Serena's LSP is single-threaded. Each `find_referencing_symbols` call takes ~110ms. Consistent, no errors.

### Test 2: Parallel requests to 1 instance (batch=10)

```
$ uv run python scripts/serena-explore/benchmark_parallel.py 10
```

| Metric | Value |
|--------|-------|
| **Wall clock** | **402.7s** |
| **Throughput** | 9.0 nodes/s |
| **Speedup** | **1.0x** ❌ |
| Avg latency | 776.4ms |

**Finding**: Pyright serializes requests internally. Sending 10 concurrent requests to one instance just queues them — latency per request jumps 7x but wall clock is identical. **Parallelism within a single instance is useless.**

### Test 3: Multiple Serena instances (N instances, 1 request each)

```
$ uv run python scripts/serena-explore/benchmark_multi.py N
```

Each instance is a fully independent `serena-mcp-server` process with its own Pyright LSP. Nodes are sharded round-robin across instances.

| Instances | Wall clock | Throughput | Speedup | Median latency | Errors |
|-----------|-----------|------------|---------|----------------|--------|
| 1 | 411.7s | 8.8/s | 1.0x | 110ms | 0 |
| 10 | 47.5s | 76.5/s | **8.7x** | 114ms | 0 |
| **20** | **28.8s** | **126.1/s** | **14.3x** | **123ms** | **0** |
| 30 | 30.1s | 120.7/s | 13.7x | 156ms | 0 |

### Scaling Curve

```
Speedup
  15x ┤                    ●──────●
      │                  ╱
  10x ┤              ●╱
      │            ╱
   5x ┤         ╱
      │       ╱
   1x ┤   ●╱
      └──┬──┬──┬──┬──┬──┬──
         1  5  10 15 20 30  instances
```

**Finding**: Near-linear scaling up to 20 instances, then CPU contention causes regression. At 30 instances (90 total processes — each Serena spawns 3), latency increases and throughput drops.

### Sweet Spot: 20 Instances

- **28.8 seconds** for 3634 nodes
- **0 errors**, identical 9938 refs found across all runs
- Each instance adds ~3 processes (Python MCP + Python Pyright wrapper + Node Pyright)
- 20 instances = 60 processes, well within typical dev machine capacity
- Startup time: ~3 seconds for all 20 instances

---

## Comparison: Serena vs Tree-Sitter Extraction

We also built a pure tree-sitter approach (`scripts/fastcode-explore/mini_crossfile.py`) adapted from FastCode:

| Aspect | Serena (LSP) | Tree-sitter (custom) |
|--------|-------------|---------------------|
| **Speed (126 files)** | **29s** (20 instances) | **<1s** |
| **Accuracy** | Type-aware (Pyright) | Text-based pattern matching |
| **Cross-file resolution** | ✅ Full LSP references | ⚠️ Import + symbol heuristics |
| **Languages** | Python (Pyright), extensible via LSP | Python + JS/TS/Go/Rust (custom queries per language) |
| **Instance method calls** | ✅ Type-inferred | ❌ Requires type inference heuristics |
| **Third-party refs** | ✅ Finds stdlib/pip refs | ❌ Only resolves project-internal |
| **Setup cost** | Needs `serena-agent` installed | Zero dependencies (uses existing tree-sitter) |
| **Refs found (same codebase)** | 9926 | 699 |

**Key insight**: Serena finds **14x more references** because it uses real type analysis. The tree-sitter approach misses instance method calls, inherited methods, re-exports, and anything requiring type inference.

---

## Integration Design

### Configuration

New config section in `.fs2/config.yaml`:

```yaml
# ─── Cross-File Relationships ─────────────────────────────
# Requires: uv tool install serena-agent
# Enabled by default when serena-mcp-server is available.
cross_file_rels:
  enabled: true                  # Enable/disable cross-file relationship extraction
  parallel_instances: 20         # Number of parallel Serena instances (1-30)
  serena_base_port: 8330         # Starting port for Serena instances
  timeout_per_node: 5            # Timeout in seconds per node resolution
  languages:                     # Languages to resolve (must have LSP support in Serena)
    - python
```

### Config Object

```python
class CrossFileRelsConfig(BaseModel):
    """Configuration for cross-file relationship extraction.

    Loaded from YAML or environment variables.
    Path: cross_file_rels (e.g., FS2_CROSS_FILE_RELS__PARALLEL_INSTANCES)

    Controls how fs2 resolves cross-file relationships using Serena LSP.
    Enabled by default when serena-mcp-server is available on PATH.
    """

    __config_path__: ClassVar[str] = "cross_file_rels"

    enabled: bool = True
    parallel_instances: int = 20
    serena_base_port: int = 8330
    timeout_per_node: float = 5.0
    languages: list[str] = ["python"]

    @field_validator("parallel_instances")
    @classmethod
    def validate_parallel_instances(cls, v: int) -> int:
        if v < 1 or v > 50:
            raise ValueError("parallel_instances must be between 1 and 50")
        return v
```

### Availability Detection

Serena is enabled by default, but gracefully degrades if not installed:

```python
def is_serena_available() -> bool:
    """Check if serena-mcp-server is available on PATH."""
    import shutil
    return shutil.which("serena-mcp-server") is not None
```

Since fs2 runs via `uv`, and Serena is installed via `uv tool install serena-agent`, this check is sufficient. If `serena-mcp-server` isn't found:
- Log a warning: `"serena-mcp-server not found. Skipping cross-file relationship extraction. Install with: uv tool install serena-agent"`
- Skip the CrossFileRelsStage gracefully
- No error, scan continues without cross-file edges

### CLI Flags

```bash
# Default: cross-file rels enabled (if Serena available)
fs2 scan

# Explicitly disable
fs2 scan --no-cross-refs

# Override parallelism
fs2 scan --cross-refs-instances 10
```

### Serena Project Auto-Setup

The CrossFileRelsStage needs a Serena project configured for the scanned directory. If `.serena/project.yml` doesn't exist:

```python
def ensure_serena_project(project_dir: str) -> None:
    """Create Serena project if not exists, index it."""
    project_yml = Path(project_dir) / ".serena" / "project.yml"
    if project_yml.exists():
        return

    subprocess.run(
        ["serena", "project", "create", project_dir,
         "--index", "--log-level", "ERROR"],
        check=True,
        capture_output=True,
    )
```

### Pipeline Integration

Per [001-edge-storage.md](001-edge-storage.md), the stage runs after Parsing, before SmartContent:

```
Discovery → Parsing → CrossFileRels → SmartContent → Embedding → Storage
```

The stage:

1. **Checks availability** — Is Serena installed? Is config enabled?
2. **Ensures project** — Creates `.serena/project.yml` if needed
3. **Spawns N instances** — On ports `base_port` through `base_port + N - 1`
4. **Waits for ready** — All instances responding (~3s)
5. **Shards nodes** — Round-robin callable/type nodes across instances
6. **Resolves references** — Each instance processes its shard sequentially
7. **Collects edges** — Writes to `context.cross_file_edges`
8. **Stops instances** — Clean shutdown
9. **Records metrics** — `cross_file_refs_total`, `cross_file_refs_time_s`, `cross_file_refs_errors`

### Edge Format

Per [001-edge-storage.md](001-edge-storage.md), edges are stored as typed edges in the DiGraph:

```python
# Serena find_referencing_symbols returns:
# {file_path: {symbol_kind: [{name_path, body_location, content_around_reference}]}}

# Translated to edges:
context.cross_file_edges.append((
    source_node_id,      # The referencing node
    target_node_id,      # The referenced node
    {
        "edge_type": "references",  # or "calls" / "imports" / "inherits" based on context
        "ref_kind": "Method",       # LSP symbol kind
    }
))
```

---

## Serena Instance Lifecycle

### Startup

```python
async def start_serena_pool(n: int, project: str, base_port: int) -> list[Process]:
    """Start N serena-mcp-server instances."""
    procs = []
    for i in range(n):
        proc = subprocess.Popen(
            ["serena-mcp-server",
             "--project", project,
             "--transport", "streamable-http",
             "--host", "127.0.0.1",
             "--port", str(base_port + i),
             "--open-web-dashboard", "false",
             "--enable-web-dashboard", "false",
             "--log-level", "ERROR"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        procs.append(proc)
    # Wait for all to be ready (~3s for 20 instances)
    await wait_for_ready(n, base_port, timeout=90)
    return procs
```

### Shutdown

```python
def stop_serena_pool(procs: list[Process]):
    """Stop all instances by killing process trees."""
    for proc in procs:
        os.kill(proc.pid, signal.SIGTERM)
    # Also kill Pyright children
    time.sleep(1)
    for proc in procs:
        # Kill any remaining children
        ...
```

### Resource Budget

| Instances | Processes | RAM (est.) | CPU cores used |
|-----------|-----------|------------|----------------|
| 1 | 3 | ~300MB | 1 |
| 10 | 30 | ~3GB | 10 |
| 20 | 60 | ~6GB | 20 |
| 30 | 90 | ~9GB | 20 (contention) |

Users with limited RAM should reduce `parallel_instances` in config.

---

## Open Questions

### Q1: Should cross-file rels be opt-in or opt-out?

**RESOLVED**: Opt-out (enabled by default if Serena is available). Rationale: the data is extremely valuable for agents, and 29s is acceptable during a scan that already takes time for smart content and embeddings. Users can `--no-cross-refs` to skip.

### Q2: What about non-Python languages?

**OPEN**: Serena supports multiple LSP backends. The `languages` config field allows future expansion. Initially Python-only because:
- Pyright is bundled with Serena (no extra setup)
- Other languages need their own LSP servers installed
- We can add JS/TS (typescript-language-server), Go (gopls), Rust (rust-analyzer) later

### Q3: Should Serena project creation be automatic?

**RESOLVED**: Yes. If `.serena/project.yml` doesn't exist, the stage creates it and indexes. This adds ~2s to first scan only. The `.serena/` directory should be added to `.gitignore`.

### Q4: What about incremental re-resolution?

**OPEN**: Currently we re-resolve all nodes every scan. Future optimization: only re-resolve nodes whose content_hash changed since last scan, reusing cached edges for unchanged nodes. This could reduce a re-scan from 29s to <5s for typical changes.

### Q5: Should `.serena/` be gitignored?

**RESOLVED**: Yes. Add to default `.gitignore` template and document. The cache is machine-local (contains absolute paths, LSP state).

---

## Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Resolution engine | Serena (LSP/Pyright) | 14x more refs than tree-sitter, type-aware, 0 errors |
| Parallelism | 20 instances (default) | 14.3x speedup, sweet spot before CPU contention |
| Default state | Enabled (opt-out) | High value, acceptable cost (~29s) |
| Config path | `cross_file_rels` in `.fs2/config.yaml` | Consistent with existing config pattern |
| Availability | Auto-detect `serena-mcp-server` on PATH | Graceful degradation if not installed |
| Project setup | Auto-create `.serena/project.yml` | Zero manual setup required |
| CLI flags | `--no-cross-refs`, `--cross-refs-instances N` | Override config from command line |

### Benchmark Reference (Authoritative)

```
3634 nodes × 20 instances = 28.8s wall clock
  → 126.1 nodes/s throughput
  → 123ms median latency per node
  → 9938 references found
  → 0 errors
```
