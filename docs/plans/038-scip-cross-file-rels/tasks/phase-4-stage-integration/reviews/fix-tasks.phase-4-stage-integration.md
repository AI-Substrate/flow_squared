# Fix Tasks: Phase 4: Stage Integration

Apply in order. Re-run review after fixes.

## Critical / High Fixes

### FT-001: Normalize SCIP document paths before fs2 node-id matching
- **Severity**: HIGH
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/integration/test_cross_file_acceptance.py`
- **Issue**: The stage successfully generates `index.scip`, but the adapter sees project-relative files like `service.py` while fs2 node IDs are repo-relative like `tests/fixtures/cross_file_sample/service.py`. Real indexing therefore produces `0` mapped edges.
- **Fix**: Carry enough project-root context into the mapping step to rewrite SCIP document paths into the same repo-relative shape used by fs2 node IDs, then keep the real acceptance test passing.
- **Patch hint**:
  ```diff
  - project_edges = adapter.extract_cross_file_edges(index_path, known_ids)
  + project_root = Path(project_path).resolve()
  + repo_root_path = Path(repo_root).resolve()
  + project_prefix = project_root.relative_to(repo_root_path).as_posix()
  + project_edges = adapter.extract_cross_file_edges(
  +     index_path,
  +     known_ids,
  +     path_prefix=f"{project_prefix}/" if project_prefix else "",
  + )
  ```
  If changing the adapter API is undesirable, normalize `ref_file` / `def_file` before calling the existing mapping helpers.

## Medium / Low Fixes

### FT-002: Deduplicate merged incremental edges
- **Severity**: MEDIUM
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/stages/test_cross_file_rels_stage.py`
- **Issue**: `reused_edges` are preserved for unchanged files, but `fresh_edges` still come from full project indexes. The stage merges both lists without a final deduplication pass.
- **Fix**: Deduplicate the merged list by `(source_id, target_id)` before assigning `context.cross_file_edges`, and add a regression test for a mixed changed/unchanged scan.
- **Patch hint**:
  ```diff
  - context.cross_file_edges = reused_edges + fresh_edges
  + merged_edges = reused_edges + fresh_edges
  + seen: set[tuple[str, str]] = set()
  + deduped: list[tuple[str, str, dict[str, Any]]] = []
  + for src, tgt, data in merged_edges:
  +     key = (src, tgt)
  +     if key in seen:
  +         continue
  +     seen.add(key)
  +     deduped.append((src, tgt, data))
  + context.cross_file_edges = deduped
  ```

### FT-003: Update the user-facing cross-file guide to SCIP
- **Severity**: MEDIUM
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/cross-file-relationships.md`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/README.md`
- **Issue**: The README now describes SCIP, but `docs/how/user/cross-file-relationships.md` still tells users to install Serena, tune parallel Serena instances, and manage `.serena/`.
- **Fix**: Rewrite the guide to the SCIP workflow (discover-projects, add-project, supported indexers, `.fs2/scip` cache, troubleshooting) or remove/redirect the file so surfaced docs no longer contradict runtime behavior.
- **Patch hint**:
  ```diff
  - fs2 resolves cross-file references between code nodes using Serena...
  - uv tool install "serena-agent @ git+https://github.com/oraios/serena.git"
  - parallel_instances: 20
  + fs2 resolves cross-file references between code nodes using SCIP indexers...
  + npm install -g @sourcegraph/scip-python
  + projects:
  +   entries:
  +     - type: python
  +       path: .
  +   auto_discover: true
  +   scip_cache_dir: .fs2/scip
  ```

## Re-Review Checklist

- [ ] All critical/high fixes applied
- [ ] `uv run ruff check src/fs2/cli/scan.py src/fs2/core/services/pipeline_context.py src/fs2/core/services/scan_pipeline.py src/fs2/core/services/stages/cross_file_rels_stage.py tests/integration/test_cross_file_acceptance.py tests/unit/services/stages/test_cross_file_rels_stage.py` passes
- [ ] `uv run python -m pytest -q tests/unit/services/stages/test_cross_file_rels_stage.py tests/integration/test_cross_file_acceptance.py --override-ini='addopts='` passes
- [ ] Re-run `/plan-7-v2-code-review` and achieve zero HIGH/CRITICAL
