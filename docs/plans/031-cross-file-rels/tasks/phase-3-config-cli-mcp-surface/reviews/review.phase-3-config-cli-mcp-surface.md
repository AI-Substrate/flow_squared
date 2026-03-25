# Code Review: Phase 3: Config + CLI + MCP Surface

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-spec.md
**Phase**: Phase 3: Config + CLI + MCP Surface
**Date**: 2026-03-15
**Reviewer**: Automated (plan-7-v2)
**Testing Approach**: Hybrid

## A) Verdict

**APPROVE**

Medium-severity notes remain around phase-scope drift, presentation-layer graph lookups, and partial evidence for deferred AC3/AC9 behavior, but no retained HIGH/CRITICAL issue blocked approval for this phase commit.

**Key failure areas**:
- **Implementation**: `TreeService` containment filtering now repeats identical outgoing-edge scans per child, and the phase also carries unwired incremental helpers that belong to later pipeline work.
- **Domain compliance**: CLI and MCP serializers now query repositories directly for relationships/ref counts instead of rendering service-prepared data.
- **Reinvention**: CLI serialization duplicates existing MCP serialization/ref-count logic rather than sharing a helper.
- **Testing**: AC3/AC9 are only proven at flag-acceptance level, and the new CLI-only relationship/ref-count behaviors lack direct edge-backed regression tests.
- **Doctrine**: Presentation layers now own graph enrichment work that `AGENTS.md` / `CLAUDE.md` reserve for service/read-model layers.

## B) Summary

The intended Phase 3 surface work largely landed: config model coverage is solid, MCP `get_node` relationship output is well tested, and the focused Phase 3 test slice passed cleanly. The retained concerns are mostly about *where* some of the new logic lives and *how much* of the stated behavior is actually evidenced, not about a broken happy path in the landed config/CLI/MCP surfaces.

The review found one real performance regression in `TreeService`'s containment filter and one clear phase-boundary problem: Phase 3 commits unwired incremental cross-file helper code that belongs to later pipeline work. Domain governance is otherwise mostly clean, but the diff does let CLI/MCP presentation code talk to repositories directly for relationship/ref-count enrichment, which cuts across the documented `cli -> services` layering.

Testing evidence is strongest for the MCP surface and weakest for the deferred CLI/config wiring promises in AC3/AC9. The phase should therefore be treated as approved with advisory notes to fold into Phase 4 rather than as fully closed-out against the full feature spec.

## C) Checklist

**Testing Approach: Hybrid**

For Hybrid:
- [x] Lightweight validation covers config model and MCP surface changes
- [ ] CLI-specific relationship/ref-count additions have direct edge-backed tests
- [ ] Deferred AC3/AC9 behavior is proved end-to-end in this phase

Universal (all approaches):
- [ ] Only in-scope files changed
- [ ] Linters/type checks clean (targeted `uv run ruff check ...` reported 11 findings)
- [ ] Domain compliance checks pass fully

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | MEDIUM | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/tree_service.py:384-397 | performance | `TreeService` now re-fetches the same outgoing edge list once per child, turning containment filtering into repeated quadratic work on large parents. | Fetch outgoing edges once per parent, derive the containment child-id set, and filter children against that cached set. |
| F002 | MEDIUM | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py:565-715; /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/pipeline_context.py:91-97 | scope | Phase 3 lands unwired incremental-resolution helpers and `prior_cross_file_edges` state that are outside the dossier scope and whose changed-file strategy would drop changed-caller → unchanged-target edges once wired. | Remove/defer this code to Phase 4, or redesign the incremental strategy before wiring it into `ScanPipeline` and add an integration test for changed-caller / unchanged-target edges. |
| F003 | MEDIUM | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/get_node.py:31-79; /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/tree.py:52-112,329-388; /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/mcp/server.py:201-272,275-320,501-570 | domain-compliance | CLI/MCP serializers now query `GraphStore` directly for relationships and ref counts, duplicating enrichment logic across transport layers instead of keeping graph reads behind service/read-model boundaries. | Move relationship/ref-count enrichment into `GetNodeService` / `TreeService` (or a shared core serializer/read-model helper) and keep CLI/MCP strictly presentational. |
| F004 | MEDIUM | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/get_node.py:63-77; /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/tree.py:104-110,364-370; /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_scan_cli.py:730-799; /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_get_node_cli.py:360-407; /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/config/test_cross_file_rels_config.py:13-102 | testing | AC3/AC9 are only evidenced at the flag-acceptance level, AC8 is only evidenced at the model/registry level, and the extra CLI-only relationship/ref-count behaviors do not have direct edge-backed regression tests. | Add CLI edge-backed tests plus YAML-load / Phase 4 behavior tests, and tighten execution-log wording so it distinguishes landed surface parsing from deferred pipeline wiring. |

## E) Detailed Findings

### E.1) Implementation Quality

1. **F001 — containment filtering regresses to repeated edge scans**
   - `TreeService._get_containment_children()` now calls `get_edges(node.node_id, direction="outgoing")` inside the loop over `all_children`.
   - That means every parent node re-traverses the same outgoing edge list once per child, which is unnecessary and can noticeably slow large file/class trees.
   - The fix is straightforward: fetch outgoing edges once, cache containment child ids, and filter the child list against that cache.

2. **F002 — Phase 3 carries unwired incremental helper code with a future correctness trap**
   - `get_changed_file_paths()`, `filter_nodes_to_changed()`, `reuse_prior_edges()`, and `PipelineContext.prior_cross_file_edges` are not wired into `ScanPipeline` or any production call path in this phase; they are only exercised by new tests/docs.
   - More importantly, the helper design does not match the current `resolve_node_batch()` algorithm. The stage derives **incoming** references for each target node; filtering resolution to changed-file nodes would miss the common case where a changed caller now points at an unchanged target.
   - Because this is dead code today, it does not break the landed Phase 3 behavior, but it should not be merged forward as if Phase 4-ready logic already exists.

### E.2) Domain Compliance

Repository note: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/` does not exist, so domain validation was anchored to `AGENTS.md`, `CLAUDE.md`, the plan Domain Manifest, and the phase dossier.

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | All changed files remain under existing repo/domain trees (`config`, `cli`, `mcp`, `core/services`, `tests`, `docs/plans`). |
| Contract-only imports | ✅ | The diff does not introduce cross-domain internal imports; it uses existing repo/service entry points and `GraphStore` interfaces. |
| Dependency direction | ❌ | CLI and MCP presentation helpers now call `graph_store.get_edges()` directly instead of consuming service-prepared data, creating `presentation -> repository` reads that bypass the documented `cli -> services` boundary. |
| Domain.md updated | N/A | No `docs/domains/<slug>/domain.md` files exist in this repository. |
| Registry current | N/A | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/registry.md` does not exist. |
| No orphan files | ❌ | `cross_file_rels_stage.py` and `pipeline_context.py` picked up deferred incremental-resolution work outside the Phase 3 dossier scope. |
| Map nodes current | N/A | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/domain-map.md` does not exist. |
| Map edges current | N/A | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/domain-map.md` does not exist. |
| No circular business deps | N/A | No domain map exists to validate topology independently. |
| Concepts documented | N/A | No domain-doc Concepts tables exist in this repository. |

Retained domain/doctrine finding:

- **F003 — presentation layers now perform repository enrichment work directly**
  - `src/fs2/cli/get_node.py` assembles `relationships` by querying `graph_store.get_edges()` inside `_code_node_to_cli_dict()`.
  - `src/fs2/cli/tree.py` and `src/fs2/mcp/server.py` do the same for `ref_count` / `relationships`, duplicating graph-query logic across transport boundaries.
  - The review recommendation is to let services/read-model helpers compute these values once and keep CLI/MCP purely presentational.

### E.3) Anti-Reinvention

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| `CrossFileRelsConfig` configuration object | None | config | proceed |
| CLI get-node explicit serialization helper (`_code_node_to_cli_dict`) | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/mcp/server.py::_code_node_to_dict` | node serialization | extend |
| CLI tree ref-count serialization additions | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/mcp/server.py::_tree_node_to_dict` | tree serialization | extend |
| Incremental helpers `get_changed_file_paths` / `filter_nodes_to_changed` | None | pipeline incremental processing | proceed |
| `reuse_prior_edges` file-path extraction | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/graph_utilities_service.py::extract_file_path` | graph utilities | extend |

No blocking duplication finding was retained, but the serializer/ref-count duplication risk is already reflected in **F003**.

### E.4) Testing & Evidence

**Coverage confidence**: 52%

Observed validation evidence:
- `uv run python -m pytest -q tests/unit/config/test_cross_file_rels_config.py tests/unit/cli/test_scan_cli.py tests/unit/cli/test_init_cli.py tests/unit/cli/test_get_node_cli.py tests/mcp_tests/test_get_node_tool.py tests/mcp_tests/test_tree_tool.py tests/unit/services/stages/test_cross_file_rels_stage.py` → `134 passed, 70 deselected`
- `pytest -q tests/unit/cli/test_scan_cli.py tests/unit/cli/test_init_cli.py -k 'CrossRefs or CrossFileRelsGuidance' --override-ini='addopts='` → completed successfully (exit 0)
- `uv run ruff check ...` on touched files → 11 findings (including touched `src/fs2/mcp/server.py` and newly added/modified test files)

| AC | Confidence | Evidence |
|----|------------|----------|
| AC2 | 85 | `tests/mcp_tests/test_get_node_tool.py` verifies incoming/outgoing relationship output at min and max detail for MCP `get_node`. CLI gained the same behavior through a separate helper, but that extra CLI path is not directly exercised with reference-edge fixtures. |
| AC3 | 15 | `tests/unit/cli/test_scan_cli.py:730-763` proves `--no-cross-refs` is accepted and scan still creates a graph. `src/fs2/cli/scan.py` never consumes `no_cross_refs`, so there is no proof that the flag produces zero cross-file edges yet. |
| AC6 | 88 | MCP `get_node` relationship behavior is strongly covered by `tests/mcp_tests/test_get_node_tool.py`, including omission when no edges exist and inclusion at both detail levels. |
| AC8 | 65 | `tests/unit/config/test_cross_file_rels_config.py` covers defaults, validators, custom values, and `YAML_CONFIG_TYPES` membership, but it does not load an actual `.fs2/config.yaml` file through the configuration service. |
| AC9 | 10 | `tests/unit/cli/test_scan_cli.py:766-799` proves `--cross-refs-instances` is accepted by Typer. The parameter is never read after parsing, so there is no evidence that scan uses 5 Serena instances yet. |
| AC11 | 45 | `tests/mcp_tests/test_tree_tool.py` proves MCP JSON/text ref-count output at max detail. The diff also changes CLI tree JSON/Rich rendering, but there is no direct CLI edge-backed regression test proving `(N refs)` or `ref_count` through `fs2 tree`. |

Retained testing finding:

- **F004 — the evidence is strongest for MCP/config surfaces and weakest for the extra CLI/deferred pipeline promises**
  - The execution log frames the phase as fully landed, but AC3/AC9 remain deferred to Phase 4 in practice, and the extra CLI-only relationship/ref-count behaviors are not directly covered.
  - This is a documentation/evidence quality issue rather than a demonstrated broken happy path for the landed MCP/config work.

### E.5) Doctrine Compliance

N/A for `docs/project-rules/*` — this repository does not contain `rules.md`, `idioms.md`, `architecture.md`, `constitution.md`, or `harness.md`. `AGENTS.md` and `CLAUDE.md` therefore served as the governing doctrine for this review.

Doctrine notes that matter in this diff are already captured in **F003**: the phase places repository reads in CLI/MCP serializers instead of keeping them in services/read-model helpers.

### E.6) Harness Live Validation

N/A — no harness configured. `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/project-rules/harness.md` is absent, and the plan records harness as not applicable for this feature.

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC2 | `get-node` returns `relationships.referenced_by` list | MCP `get_node` relationship tests at min/max detail and outgoing reference coverage in `tests/mcp_tests/test_get_node_tool.py` | 85% |
| AC3 | `--no-cross-refs` produces zero cross-file edges | CLI flag-acceptance tests only; `src/fs2/cli/scan.py` defines but does not consume `no_cross_refs` | 15% |
| AC6 | MCP `get_node` includes `relationships` in output | MCP tests cover include/omit behavior and both detail levels | 88% |
| AC8 | `cross_file_rels` config section parses from `.fs2/config.yaml` | Model + validator + registry tests in `tests/unit/config/test_cross_file_rels_config.py`; no real YAML-load proof | 65% |
| AC9 | `--cross-refs-instances 5` uses 5 instances | CLI flag-acceptance tests only; source never uses `cross_refs_instances` after parsing | 10% |
| AC11 | `tree --detail max` shows ref count per node | MCP tree tests prove JSON/text ref-count output; CLI-specific edge-backed proof is missing | 45% |

**Overall coverage confidence**: 52%

## G) Commands Executed

```bash
git --no-pager diff --stat
git --no-pager diff --staged --stat
git --no-pager log --oneline -12

git --no-pager diff 6ae5d21..0e076cc > /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-3-config-cli-mcp-surface/reviews/_computed.diff
git --no-pager diff --name-status 6ae5d21..0e076cc
git --no-pager diff --stat 6ae5d21..0e076cc

uv run python -m pytest -q tests/unit/config/test_cross_file_rels_config.py tests/unit/cli/test_scan_cli.py tests/unit/cli/test_init_cli.py tests/unit/cli/test_get_node_cli.py tests/mcp_tests/test_get_node_tool.py tests/mcp_tests/test_tree_tool.py tests/unit/services/stages/test_cross_file_rels_stage.py

uv run ruff check src/fs2/cli/get_node.py src/fs2/cli/init.py src/fs2/cli/scan.py src/fs2/cli/tree.py src/fs2/config/objects.py src/fs2/core/services/pipeline_context.py src/fs2/core/services/stages/cross_file_rels_stage.py src/fs2/core/services/tree_service.py src/fs2/mcp/server.py tests/mcp_tests/test_get_node_tool.py tests/mcp_tests/test_tree_tool.py tests/unit/cli/test_get_node_cli.py tests/unit/cli/test_init_cli.py tests/unit/cli/test_scan_cli.py tests/unit/config/test_cross_file_rels_config.py tests/unit/services/stages/test_cross_file_rels_stage.py

pytest -q tests/unit/cli/test_scan_cli.py tests/unit/cli/test_init_cli.py -k 'CrossRefs or CrossFileRelsGuidance' --override-ini='addopts='
```

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: APPROVE

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-spec.md
**Phase**: Phase 3: Config + CLI + MCP Surface
**Tasks dossier**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-3-config-cli-mcp-surface/tasks.md
**Execution log**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-3-config-cli-mcp-surface/execution.log.md
**Review file**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-3-config-cli-mcp-surface/reviews/review.phase-3-config-cli-mcp-surface.md

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-plan.md | Modified | docs/plans | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-3-config-cli-mcp-surface/execution.log.md | Added | docs/plans | Advisory: tighten wording so deferred AC3/AC9 wiring and Phase 4 spillover are explicit |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-3-config-cli-mcp-surface/tasks.fltplan.md | Added | docs/plans | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-3-config-cli-mcp-surface/tasks.md | Added | docs/plans | Optional: update dossier if extra CLI/security fix work is intentionally retained |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/get_node.py | Modified | cli | Advisory: move relationship lookup into service/shared serializer |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/init.py | Modified | cli | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/scan.py | Modified | cli | Advisory: Phase 4 should add behavior-level coverage once flags are wired |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/tree.py | Modified | cli | Advisory: move ref-count lookup into service/shared tree model |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/config/objects.py | Modified | config | Advisory: add real YAML-load coverage when config is wired end-to-end |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/pipeline_context.py | Modified | core/services | Advisory: defer/remove `prior_cross_file_edges` until Phase 4 wiring exists |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py | Modified | core/services/stages | Advisory: move/defer incremental helpers or redesign them before wiring |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/tree_service.py | Modified | core/services | Advisory: cache outgoing edges once per parent to avoid repeated scans |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/mcp/server.py | Modified | mcp | Advisory: move relationship/ref-count enrichment into service/shared helper |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/mcp_tests/test_get_node_tool.py | Modified | tests | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/mcp_tests/test_tree_tool.py | Modified | tests | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_get_node_cli.py | Modified | tests | Advisory: add relationship assertions if CLI feature is retained |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_init_cli.py | Modified | tests | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_scan_cli.py | Modified | tests | Advisory: add behavior-level AC3/AC9 coverage when Phase 4 wires flags |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/config/test_cross_file_rels_config.py | Added | tests | Advisory: add YAML-load coverage if end-to-end config parsing matters before merge |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/stages/test_cross_file_rels_stage.py | Modified | tests | Advisory: keep T008 tests aligned with whichever phase actually owns incremental work |

### Domain Artifacts to Update (if any)

| File (absolute path) | What's Missing |
|---------------------|----------------|
| None | This repository does not use a `docs/domains/` domain-doc system, so no domain artifacts were required for this review. |

### Next Step

`/plan-5-v2-phase-tasks-and-brief --phase "Phase 4: Integration + Documentation" --plan /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-plan.md`
