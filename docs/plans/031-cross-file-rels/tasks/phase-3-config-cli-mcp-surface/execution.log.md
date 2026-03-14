# Execution Log: Phase 3 — Config + CLI + MCP Surface

**Plan**: [../../cross-file-rels-plan.md](../../cross-file-rels-plan.md)
**Phase**: Phase 3
**Started**: 2026-03-14
**Baseline**: 1608 passed, 25 skipped, 341 deselected (41.93s)
**Final**: 1642 passed, 25 skipped, 350 deselected (42.68s) — +34 new tests, 0 regressions

---

## T001: CrossFileRelsConfig model ✅
- Created `CrossFileRelsConfig` in `config/objects.py` with `__config_path__ = "cross_file_rels"`
- Fields: enabled, parallel_instances, serena_base_port, timeout_per_node, languages
- Validator: parallel_instances 1-50, timeout_per_node > 0
- Registered in YAML_CONFIG_TYPES
- 16 tests pass

## T002 + T003: CLI flags ✅
- Added `--no-cross-refs` and `--cross-refs-instances` to `scan()` in `scan.py`
- Follows `--no-smart-content` pattern exactly
- Not wired to pipeline yet (Phase 4)
- 4 tests pass (slow marker — run with `--override-ini='addopts='`)

## T004 + T005: MCP relationships ✅
- Updated `_code_node_to_dict` to accept `graph_store` param
- Queries incoming/outgoing edges separately (efficient — no double-query)
- `relationships` key omitted when no edges (compact output)
- Present at both min and max detail levels
- `get_node` passes `store` to `_code_node_to_dict`
- 5 tests pass

## T004b + T004c: CLI get-node fix ✅
- **DYK-P3-03**: Replaced `asdict(node)` with `_code_node_to_cli_dict()` using explicit field selection
- Prevents embedding vector leakage (pre-existing bug, can be huge)
- Added `relationships` output via `graph_store` (same pattern as MCP)
- 2 new tests + all 13 existing CLI get-node tests pass

## T006: Tree ref count ✅
- **DYK-P3-04**: Updated 3 code paths:
  1. MCP `_tree_node_to_dict` + `_render_tree_as_text` — `ref_count` in JSON, `(N refs)` in text
  2. CLI `_tree_node_to_dict` — `ref_count` in JSON output
  3. CLI `_add_tree_node_to_rich_tree` — `(N refs)` in Rich label
- All require `graph_store` threaded through
- **Discovery**: `_get_containment_children` had a within-file reference edge cycle bug. Fixed by filtering on `edge_type` attribute instead of just file_path
- 4 tests pass + all 85 existing tree tests pass

## T007: .serena/ gitignore guidance ✅
- Added cross_file_rels section to `DEFAULT_CONFIG` template in `init.py`
- Includes install instructions + `.serena/` gitignore note
- Full guide deferred to Phase 4 T4.6 (`docs/how/user/cross-file-relationships.md`)
- 3 tests pass

## T008: Incremental resolution helpers ✅
- Added `get_changed_file_paths()` — compares content_hash of file nodes vs prior
- Added `filter_nodes_to_changed()` — filters resolvable nodes to changed files
- Added `reuse_prior_edges()` — carries forward edges from unchanged files
- Added `prior_cross_file_edges` field to PipelineContext
- Phase 4 wires through ScanPipeline (extract prior edges before clear)
- 9 tests pass

---

## Discoveries

| Date | Task | Type | Discovery | Resolution |
|------|------|------|-----------|------------|
| 2026-03-14 | T004b | DYK-P3-01 | CLI get-node bypasses _code_node_to_dict | Added _code_node_to_cli_dict |
| 2026-03-14 | T004c | DYK-P3-03 | CLI get-node leaks embeddings via asdict() | Replaced with explicit field selection |
| 2026-03-14 | T006 | DYK-P3-04 | _tree_node_to_dict duplicated in 3 code paths | Updated all 3 with graph_store threading |
| 2026-03-14 | T006 | Bug | _get_containment_children had within-file ref edge cycle | Fixed: filter by edge_type attribute, not just file_path |
| 2026-03-14 | T007 | DYK-P3-05 | .serena/ is at project root, not inside .fs2/ | Comment in DEFAULT_CONFIG; full guide in Phase 4 |
