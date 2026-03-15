# Fix Tasks: Phase 2: CrossFileRels Pipeline Stage

Apply in order. Re-run review after fixes.

## Critical / High Fixes

### FT-001: Scope project detection to the real scan roots and route work per project
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py
- **Issue**: `detect_project_roots()` is fed from `context.graph_path`, detects `.venv` / fixture roots in this repo, `process()` starts only one pool for `project_roots[0]`, and `shard_nodes()` ignores `project_roots` entirely.
- **Fix**: Derive scan scope from `context.scan_config.scan_paths` (or an explicit scan-root field), detect roots only within that scope, assign each node to its most-specific `ProjectRoot`, compute root-relative paths per node, and skip unmatched nodes with metrics/logging.
- **Patch hint**:
  ```diff
  - scan_root = str(Path(context.graph_path).parent.parent)
  - project_roots = detect_project_roots(scan_root)
  + scan_roots = [Path(p).resolve() for p in context.scan_config.scan_paths]
  + scan_root = str(Path(os.path.commonpath(scan_roots)))
  + project_roots = detect_project_roots(scan_root)
  ...
  - pool.start(n_instances, DEFAULT_BASE_PORT, project_roots[0].path)
  - shards = shard_nodes(context.nodes, project_roots, pool.ports)
  + for project_root, project_nodes in group_nodes_by_project(context.nodes, project_roots).items():
  +     ports = pool.start(instances_for(project_nodes), next_base_port, project_root.path)
  +     shards = shard_nodes(project_nodes, [project_root], ports)
  ```

### FT-002: Parse the documented Serena reference payload shape
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py, /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/stages/test_cross_file_rels_stage.py
- **Issue**: `DefaultSerenaClient` stringifies reference objects and `resolve_node_batch()` looks those strings up as qualified names, which does not match the documented `{name_path, ...}` payload shape from workshop 002.
- **Fix**: Extract `name_path` (or equivalent symbol identity) from each reference object, normalize it into the same format used by `build_node_lookup()`, and add a regression test that uses the real response structure.
- **Patch hint**:
  ```diff
  - "symbol": sym if isinstance(sym, str) else str(sym),
  + "name_path": sym.get("name_path", "") if isinstance(sym, dict) else str(sym),
  ...
  - ref_symbol = ref.get("symbol", "")
  - source_id = node_lookup.get((ref_file, ref_symbol))
  + ref_name_path = ref.get("name_path", "")
  + ref_qname = ref_name_path.replace("/", ".")
  + source_id = node_lookup.get((ref_file, ref_qname))
  ```

### FT-003: Use the Serena pool concurrently and only across ready instances
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py
- **Issue**: The stage starts multiple instances but resolves each shard serially with per-port `asyncio.run()` calls, and it still schedules work on ports that failed readiness.
- **Fix**: Track the ready-port subset, skip or abort cleanly when none are healthy, and resolve one micro-batch per ready port with a single async gather so the pool is actually used in parallel.
- **Patch hint**:
  ```diff
  - if not pool.wait_ready(timeout=60.0):
  -     logger.warning("Some Serena instances failed to start. Continuing with available.")
  + ready_ports = pool.wait_ready(timeout=60.0)
  + if not ready_ports:
  +     context.metrics["cross_file_rels_skipped"] = True
  +     context.metrics["cross_file_rels_reason"] = "serena_pool_unavailable"
  +     return context
  ...
  - for port, port_nodes in shards.items():
  -     for batch_start in range(0, len(port_nodes), DEFAULT_MICRO_BATCH_SIZE):
  -         batch_edges = asyncio.run(resolve_node_batch(batch, port, node_lookup, known_ids))
  -         all_edges.extend(batch_edges)
  + for batch_start in range(0, max(len(nodes) for nodes in shards.values()), DEFAULT_MICRO_BATCH_SIZE):
  +     batch_tasks = [
  +         resolve_node_batch(nodes[batch_start:batch_start + DEFAULT_MICRO_BATCH_SIZE], port, node_lookup, known_ids)
  +         for port, nodes in shards.items()
  +         if nodes[batch_start:batch_start + DEFAULT_MICRO_BATCH_SIZE]
  +     ]
  +     for batch_edges in asyncio.run(asyncio.gather(*batch_tasks)):
  +         all_edges.extend(batch_edges)
  ```

### FT-004: Add orchestration/pool coverage and refresh the execution evidence
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/stages/test_cross_file_rels_stage.py, /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-2-crossfilerels-pipeline-stage/execution.log.md
- **Issue**: The current tests do not exercise the successful `CrossFileRelsStage.process()` path, partial startup, cleanup, or multi-project routing, even though the execution log says those behaviors are complete.
- **Fix**: Add fake-backed happy-path orchestration tests (including multi-project and partial-start cases), then update `execution.log.md` so it cites the actual passing test names/commands instead of unsupported coverage claims.
- **Patch hint**:
  ```diff
  + def test_process_resolves_edges_across_two_project_roots(...):
  +     fake_pool = FakeSerenaPool(...)
  +     fake_client = FakeSerenaClient(...)
  +     result = CrossFileRelsStage(...).process(ctx)
  +     assert result.cross_file_edges == [...]
  +     assert fake_pool.stop_called is True
  +
  + def test_process_skips_when_no_ready_ports(...):
  +     ...
  ```

### FT-005: Move concrete Serena adapters to core/adapters/
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py
- **Issue**: The stage currently owns concrete FastMCP, subprocess, and PID-file behavior directly inside `core/services`.
- **Fix**: Move `DefaultSubprocessRunner`, `SerenaPool`, and `DefaultSerenaClient` to `src/fs2/core/adapters/` (e.g., `serena_adapter.py` or split per component). Keep the protocols (`SubprocessRunnerProtocol`, `SerenaPoolProtocol`, `SerenaClientProtocol`) in the stage file. The stage imports only protocols; `ScanPipeline` (Phase 4) wires the concrete adapters.
- **Patch hint**:
  ```diff
  - class DefaultSerenaClient:
  - class SerenaPool:
  + class SerenaClient(Protocol): ...
  + class SerenaProcessPool(Protocol): ...
  + # concrete implementations live under core/adapters/
  ```

## Medium / Low Fixes

### FT-006: Clear the touched-file ruff failures
- **Severity**: LOW
- **File(s)**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py, /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/stages/test_cross_file_rels_stage.py
- **Issue**: Targeted `uv run ruff check ...` fails on touched files (unused imports/variables, preferred exception style, quoted annotation, etc.).
- **Fix**: Clean the reported ruff findings after the functional fixes land.
- **Patch hint**:
  ```diff
  - skipped = 0
  +
  - except asyncio.TimeoutError:
  + except TimeoutError:
  ```

## Re-Review Checklist

- [ ] All critical/high fixes applied
- [ ] Re-run `/plan-7-v2-code-review` and achieve zero HIGH/CRITICAL
