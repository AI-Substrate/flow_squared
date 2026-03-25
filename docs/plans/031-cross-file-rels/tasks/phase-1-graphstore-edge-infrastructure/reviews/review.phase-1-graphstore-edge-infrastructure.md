# Code Review: Phase 1: GraphStore Edge Infrastructure

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-spec.md
**Phase**: Phase 1: GraphStore Edge Infrastructure
**Date**: 2026-03-13
**Reviewer**: Automated (plan-7-v2)
**Testing Approach**: Hybrid

## A) Verdict

**APPROVE**

**Key failure areas**:
- **Implementation**: `FakeGraphStore` reverse-edge bookkeeping diverges from `NetworkXGraphStore` when the same edge is added more than once, and `add_edge(**edge_data)` still accepts values that can later make persisted graphs unloadable.
- **Domain compliance**: Phase 1 modified `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/models/code_node.py` even though the plan marked `core/models` as consume-only and did not manifest that file.
- **Reinvention**: `CodeNode.file_path` duplicates existing file-path extraction helpers in `core/services`.
- **Testing**: Execution evidence is strong on passing tests, but the log does not capture explicit RED→GREEN TDD evidence and AC10 lacks an active valid-1.0-load regression.

## B) Summary

Overall implementation quality is solid and independently re-verified: the phase-focused suite passed with `118 passed, 1 skipped`, and a fresh repo-wide run passed with `1581 passed, 25 skipped, 341 deselected`. The GraphStore API changes, edge round-trip persistence, and containment-parent filtering all behave as intended for this phase's current cross-file reference invariant.

Domain-boundary checks were mostly clean at the import/dependency level, but the phase reached into `core/models` without updating the plan/spec manifest and did so by introducing a helper that overlaps existing service-layer extraction logic. Domain-document currency checks were largely not applicable because this repository currently has no `docs/domains/` tree, so manifest compliance was assessed against the plan itself.

Testing evidence quality is good but not perfect. AC5 is strongly backed by direct tests and fresh reruns, while AC10 is only partially evidenced because there is no active passing regression that loads a valid `1.0` graph and proves the compatibility clause end to end.

## C) Checklist

**Testing Approach: Hybrid**

For Hybrid:
- [ ] TDD-designated tasks show explicit RED → GREEN evidence in the execution log
- [x] Lightweight validation covers version bump and edge roundtrip behavior
- [x] Critical phase paths are covered by automated tests
- [ ] All acceptance-criterion clauses are actively verified (`AC10` is partial)

Universal (all approaches):
- [ ] Only in-scope files changed (`/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/models/code_node.py` was not in the phase manifest)
- [x] Tests clean (`118 passed, 1 skipped`; `1581 passed, 25 skipped, 341 deselected`)
- [ ] Domain compliance checks pass fully (manifest/orphan gap for `core/models`)

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | MEDIUM | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/repos/graph_store_fake.py:130-135,190-225 | correctness | Re-adding the same edge leaves stale duplicate reverse-edge entries in `FakeGraphStore`, so incoming-edge behavior can diverge from `NetworkXGraphStore`. | Replace/update reverse-edge entries on repeated `add_edge()` calls and add a parity test against `NetworkXGraphStore`. |
| F002 | MEDIUM | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/repos/graph_store_impl.py:149-174 | error-handling | `add_edge(**edge_data)` accepts values that can be written successfully but later fail `RestrictedUnpickler` on load. | Validate edge attribute values before persistence and add a negative test for unsupported types. |
| F003 | MEDIUM | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/models/code_node.py:201-211 | domain-compliance | The phase changed a shared `core/models` surface that the plan/spec marked as consume-only and did not list in the Domain Manifest. | Either move file-path extraction back into a manifested phase file or update the plan/spec domain artifacts to explicitly allow the `core/models` change. |
| F004 | MEDIUM | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-1-graphstore-edge-infrastructure/execution.log.md:16-62 | testing | TDD-designated tasks are logged with passing counts, but the review cannot see explicit RED→GREEN evidence. | Record failing and passing commands (or commit chronology) for each TDD task in the execution log. |
| F005 | MEDIUM | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/repos/test_graph_store_impl.py:570-575 | testing | AC10's compatibility clause is only partially evidenced because there is no active passing test that loads a valid `1.0` graph successfully. | Add an unskipped regression that constructs a valid `1.0` graph pickle, loads it, and asserts successful compatibility behavior. |
| F006 | LOW | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/models/code_node.py:201-211 | reinvention | `CodeNode.file_path` duplicates file-path extraction logic that already exists in service-layer helpers. | Reuse or centralize existing extraction logic instead of introducing another helper if the `core/models` change is kept. |

## E) Detailed Findings

### E.1) Implementation Quality

Retained implementation findings:

1. **F001 — FakeGraphStore duplicate reverse-edge bookkeeping**
   - `FakeGraphStore.add_edge()` overwrites `_edges[parent_id][child_id]` but always appends to `_reverse_edges[child_id]`.
   - Repeated `add_edge(a, b, ...)` calls can therefore produce stale incoming-edge state that `networkx.DiGraph` would have replaced.
   - Recommendation: make repeated-edge semantics match `NetworkXGraphStore` and add a regression test.

2. **F002 — Unsupported persisted edge-data values are accepted**
   - The public `add_edge(**edge_data)` API accepts arbitrary objects, but persisted graphs are only reloadable when edge attributes remain within the `RestrictedUnpickler`-safe builtin set.
   - Recommendation: reject unsupported values early with `GraphStoreError` instead of allowing a future load-time failure.

No retained security or performance issues were identified.

Note: a same-file-reference concern raised during static review was not retained as a finding because this phase and spec explicitly scope `edge_type="references"` to **cross-file** relationships; the current same-file filter matches that invariant.

### E.2) Domain Compliance

Repository note: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/` does not exist, so manifest-level validation relied on the plan/spec instead of domain registry files.

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | All modified implementation files remain under established domain trees (`core/repos`, `core/services`, `core/models`, `tests`). |
| Contract-only imports | ✅ | No new cross-domain internal import violation was introduced in the changed code. |
| Dependency direction | ✅ | Changed dependencies remain `core/services -> core/repos/core/models` and `core/repos -> core/models`; no reverse infrastructure→business edge was introduced. |
| Domain.md updated | N/A | No `docs/domains/<slug>/domain.md` files exist in this repository, so currency could not be validated. |
| Registry current | N/A | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/registry.md` does not exist. |
| No orphan files | ❌ | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/models/code_node.py` was modified even though the Phase 1 Domain Manifest did not include it and the spec described `core/models` as consume-only. |
| Map nodes current | N/A | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/domain-map.md` does not exist. |
| Map edges current | N/A | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/domain-map.md` does not exist. |
| No circular business deps | N/A | No domain map is present to validate graph topology formally; no cycle was apparent in the changed code itself. |
| Concepts documented | N/A | No domain docs tree exists, so Concepts-table validation was not applicable. |

Retained domain finding:

- **F003 — Unmanifested `core/models` change**
  - The phase added `CodeNode.file_path` in `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/models/code_node.py`.
  - The plan/spec described `core/models` as consumed-as-is and the plan's Domain Manifest did not declare this file.
  - Recommendation: either keep extraction logic in a manifested service/repo file or update the domain artifacts so reviewers and later implementors see the model change as intentional.

### E.3) Anti-Reinvention

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| `GraphStore.get_edges(node_id, direction, edge_type)` | None | None | proceed |
| Edge metadata on `GraphStore.add_edge(..., **edge_data)` | None | None | proceed |
| `CodeNode.file_path` property | `GraphUtilitiesService.extract_file_path`, `TreeService._extract_file_path` | `core/services` | extend existing helper (`F006`) |
| TreeService containment-child filtering | None | None | proceed |
| `get_parent()` containment-edge filtering in graph stores | None | None | proceed |

### E.4) Testing & Evidence

**Coverage confidence**: 84%

| AC | Confidence | Evidence |
|----|------------|----------|
| AC5 | 96% | Directly covered by the changed GraphStore contract tests plus NetworkX/Fake `get_edges()` tests. Independently re-run with `uv run python -m pytest tests/unit/repos/test_graph_store.py tests/unit/repos/test_graph_store_fake.py tests/unit/repos/test_graph_store_impl.py tests/unit/services/test_graph_service.py tests/unit/services/test_tree_service.py` → `118 passed, 1 skipped`. |
| AC10 | 57% | Version bump is covered by `test_save_includes_format_version_metadata`, fixture updates, and a fresh repo-wide pass. However, there is no active passing regression that loads a valid `1.0` graph and proves compatibility directly. |
| Phase extras | 92% | Backward-compatible `add_edge()` behavior, edge-attribute roundtrip, containment-only `get_parent()`, and tree filtering all have changed tests and passed in the focused rerun. |

Retained testing findings:

- **F004 — Missing explicit RED→GREEN evidence**
  - The execution log records staged passing counts per task group.
  - It does not show the failing state first for tasks marked TDD in the dossier.

- **F005 — AC10 compatibility proof is incomplete**
  - Current evidence proves the version bump and general stability.
  - It does not directly prove that a valid `1.0` graph loads successfully without error.

### E.5) Doctrine Compliance

N/A — `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/project-rules/rules.md`, `idioms.md`, `architecture.md`, and `constitution.md` are all absent. No separate doctrine/rules violation was retained beyond the manifest drift already captured in **F003**.

### E.6) Harness Live Validation

N/A — no harness configured. `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/project-rules/harness.md` is absent, and the plan explicitly records harness as not applicable for this feature.

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC5 | `get_edges()` returns edges filtered by `edge_type` and `direction` | GraphStore contract tests; NetworkX/Fake `get_edges()` tests; focused rerun (`118 passed, 1 skipped`) | 96% |
| AC10 | Graph format version is 1.1; old 1.0 graphs load without error | Version-metadata test; fixture updates using `FORMAT_VERSION`; fresh repo-wide pass (`1581 passed, 25 skipped, 341 deselected`); **missing active valid-1.0 load regression** | 57% |
| P1-BC | Existing callers of `add_edge()` remain backward compatible | `test_add_edge_without_edge_data_is_backward_compatible`; focused rerun | 95% |
| P1-RT | Edge attributes survive save/load roundtrip | `test_edge_attributes_survive_save_load_roundtrip`; focused rerun | 96% |
| P1-TREE | Tree output ignores cross-file references and remains unchanged for containment-only graphs | `TestTreeServiceCrossFileFiltering` tests; focused rerun | 94% |

**Overall coverage confidence**: 84%

## G) Commands Executed

```bash
git --no-pager diff --stat
git --no-pager diff --staged --stat
git --no-pager status --short
git --no-pager log --oneline -10

git --no-pager diff --name-status c9ede34..HEAD -- \
  src/fs2/core/models/code_node.py \
  src/fs2/core/repos/graph_store.py \
  src/fs2/core/repos/graph_store_fake.py \
  src/fs2/core/repos/graph_store_impl.py \
  src/fs2/core/services/tree_service.py \
  tests/unit/repos/test_graph_store.py \
  tests/unit/repos/test_graph_store_fake.py \
  tests/unit/repos/test_graph_store_impl.py \
  tests/unit/services/test_graph_service.py \
  tests/unit/services/test_tree_service.py

git --no-pager diff --unified=3 c9ede34..HEAD -- \
  src/fs2/core/models/code_node.py \
  src/fs2/core/repos/graph_store.py \
  src/fs2/core/repos/graph_store_fake.py \
  src/fs2/core/repos/graph_store_impl.py \
  src/fs2/core/services/tree_service.py \
  tests/unit/repos/test_graph_store.py \
  tests/unit/repos/test_graph_store_fake.py \
  tests/unit/repos/test_graph_store_impl.py \
  tests/unit/services/test_graph_service.py \
  tests/unit/services/test_tree_service.py \
  > /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-1-graphstore-edge-infrastructure/reviews/_computed.diff

uv run python -m pytest tests/unit/repos/test_graph_store.py tests/unit/repos/test_graph_store_fake.py tests/unit/repos/test_graph_store_impl.py tests/unit/services/test_graph_service.py tests/unit/services/test_tree_service.py
uv run python -m pytest -x
```

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: APPROVE

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-spec.md
**Phase**: Phase 1: GraphStore Edge Infrastructure
**Tasks dossier**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-1-graphstore-edge-infrastructure/tasks.md
**Execution log**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-1-graphstore-edge-infrastructure/execution.log.md
**Review file**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-1-graphstore-edge-infrastructure/reviews/review.phase-1-graphstore-edge-infrastructure.md

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/models/code_node.py | Modified | core/models | Optional follow-up: reconcile manifest/scope and centralize file-path extraction |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/repos/graph_store.py | Modified | core/repos | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/repos/graph_store_fake.py | Modified | core/repos | Optional follow-up: match repeated-edge semantics to `NetworkXGraphStore` |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/repos/graph_store_impl.py | Modified | core/repos | Optional follow-up: validate persisted edge-data types |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/tree_service.py | Modified | core/services | None for current phase invariant |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/repos/test_graph_store.py | Modified | tests | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/repos/test_graph_store_fake.py | Modified | tests | Optional follow-up: add repeated-edge parity coverage |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/repos/test_graph_store_impl.py | Modified | tests | Optional follow-up: add active valid-1.0-load regression |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_graph_service.py | Modified | tests | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_tree_service.py | Modified | tests | None |

### Required Fixes (if REQUEST_CHANGES)

Not applicable — this phase is approved. Optional follow-ups are captured in findings **F001-F006**.

### Domain Artifacts to Update (if any)

| File (absolute path) | What's Missing |
|---------------------|----------------|
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-plan.md | `## Domain Manifest` and `## Target Domains` do not account for the `core/models/code_node.py` change |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-spec.md | `Target Domains` still describe `core/models` as consume-only even though Phase 1 introduced a model-surface helper |

### Next Step

/plan-5-v2-phase-tasks-and-brief --phase "Phase 2: CrossFileRels Pipeline Stage" --plan /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-plan.md
