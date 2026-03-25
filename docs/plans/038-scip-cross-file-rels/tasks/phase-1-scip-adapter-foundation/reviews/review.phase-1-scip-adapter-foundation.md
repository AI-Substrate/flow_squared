# Code Review: Phase 1: SCIP Adapter Foundation

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-spec.md
**Phase**: Phase 1: SCIP Adapter Foundation
**Date**: 2026-03-17
**Reviewer**: Automated (plan-7-v2)
**Testing Approach**: Hybrid (Phase 1 evidence is TDD-heavy adapter testing)

## A) Verdict

**APPROVE**

**Key failure areas**:
- **Testing**: TDD intent is clear, but the phase artifacts preserve GREEN-only evidence rather than explicit RED→GREEN proof, and stdlib/external filtering is not directly asserted by the changed tests.
- **Doctrine**: The new adapter contract is named `SCIPAdapterBase`, which diverges from the repository’s usual `{Name}Adapter` ABC naming idiom.

## B) Summary

Phase 1 lands the promised adapter foundation cleanly: dependency updates, generated protobuf bindings, adapter base/fake/Python implementation, fixture index, and focused unit tests all align with the approved plan. Static review, targeted runtime inspection, and reviewer reruns (`ruff` + phase pytest) did not surface any HIGH/CRITICAL correctness, safety, or domain-boundary issues.

Domain compliance is clean for the files actually introduced here, and the repo currently has no `docs/domains/` registry or domain map to keep in sync; the phase dossier explicitly anticipated that reality. The anti-reinvention check also came back clean: the work follows the existing adapter/fake/error patterns rather than recreating an existing capability.

The only meaningful findings are evidence/documentation quality issues. The tests demonstrate working behavior, deduplication, and core filtering, but the review trail does not preserve explicit RED→GREEN proof for the TDD claim, and the test suite does not directly pin stdlib/external-symbol filtering despite the execution log claiming it.

## C) Checklist

**Testing Approach: Hybrid**

- [x] Core validation tests present for the adapter foundation
- [x] Critical paths covered (protobuf loading, edge extraction, deduplication, Python mapping)
- [ ] Explicit RED→GREEN evidence preserved in phase artifacts
- [ ] Every claimed verification point is directly backed by a focused test (`stdlib` / external-symbol filtering is indirect only)
- [x] Only in-scope files changed
- [x] Linters clean on touched Python files
- [x] Phase-scoped tests pass
- [x] Domain compliance checks pass

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | MEDIUM | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-1-scip-adapter-foundation/tasks.md:107-109; /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-1-scip-adapter-foundation/execution.log.md:46-54 | testing | Phase 1 is framed as TDD, but the persisted evidence shows passing outcomes only and does not preserve any RED→GREEN or test-first proof. | Capture failing-then-passing pytest evidence or link test-first commits/log entries for the adapter work. |
| F002 | LOW | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_scip_adapter.py:96-140; /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_scip_adapter_python.py:140-149 | testing | The changed tests directly cover local-symbol and self-reference filtering, but they do not directly assert stdlib/external-symbol filtering even though the phase artifacts claim that coverage. | Add a focused stdlib/external-symbol filtering test and record its passing output in the execution log. |
| F003 | LOW | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/scip_adapter.py:28-35 | pattern | The new contract is named `SCIPAdapterBase`, which diverges from the repository’s established `{Name}Adapter` naming idiom for adapter ABCs. | Rename the ABC to `SCIPAdapter` and update subclasses/tests/docs accordingly in a follow-up cleanup. |

## E) Detailed Findings

### E.1) Implementation Quality

No material implementation-quality findings were identified.

- Reviewer reran `ruff` on the touched Python files successfully.
- Reviewer reran the phase test suite successfully (`39 passed`).
- Static inspection found no HIGH-signal correctness, security, error-handling, performance, or scope-creep defects in the changed implementation.

### E.2) Domain Compliance

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | New implementation files live under `/src/fs2/core/adapters/`, tests under `/tests/unit/adapters/`, and plan artifacts under the phase dossier path, matching the plan manifest and repo structure. |
| Contract-only imports | ✅ | The changed adapter code imports stdlib, package-local generated protobuf bindings, and adapter-local exceptions/contracts only. |
| Dependency direction | ✅ | No adapter → service or adapter → repo dependency inversion was introduced. |
| Domain.md updated | N/A | `docs/domains/` does not exist in this repository, and the phase dossier explicitly notes there is no formal domain registry to consume. |
| Registry current | N/A | No `/docs/domains/registry.md` exists. |
| No orphan files | ✅ | Changed code/test files are represented in the plan’s Domain Manifest; plan artifacts and lockfiles were treated as non-domain implementation artifacts. |
| Map nodes current | N/A | No `/docs/domains/domain-map.md` exists. |
| Map edges current | N/A | No domain map exists to validate. |
| No circular business deps | ✅ | The changed imports do not introduce a new business-layer cycle. |
| Concepts documented | N/A | No domain documentation system exists in this repository. |

### E.3) Anti-Reinvention

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| `SCIPAdapterBase` | None (pattern reuse only: existing adapter ABC conventions) | core/adapters | proceed |
| `SCIPPythonAdapter` | None | core/adapters | proceed |
| `SCIPFakeAdapter` | None (follows existing fake-adapter pattern) | core/adapters | proceed |
| `SCIPAdapterError` hierarchy | None (extends existing exception pattern rather than duplicating a prior SCIP-specific hierarchy) | core/adapters | proceed |

### E.4) Testing & Evidence

**Coverage confidence**: 78%

| AC | Confidence | Evidence |
|----|------------|----------|
| AC1 | 76 | Reviewer reran `/tests/unit/adapters/test_scip_adapter.py` and `/tests/unit/adapters/test_scip_adapter_python.py` successfully (`39 passed`). Changed tests assert Python fixture edges are produced and edge payloads remain `{"edge_type": "references"}`. Full `fs2 scan` integration is intentionally deferred to Phase 4. |
| AC11 | 95 | Directly covered by base-adapter deduplication tests and fixture-level `test_edges_are_deduplicated`; both passed in the reviewer rerun. |
| AC12 | 64 | Directly covered for local-symbol filtering and self-reference exclusion; stdlib/external-symbol filtering is only indirectly evidenced, not directly asserted by a focused changed test. |
| AC2-AC10 / AC13 / AC15 | 0 | Explicitly deferred by Phase 1 non-goals and later phases (multi-language adapters, config/CLI, scan integration, provider selection, caching). |

### E.5) Doctrine Compliance

No project-rules bundle exists under `/docs/project-rules/`, so doctrine review fell back to repository idioms and top-level architectural guidance.

One low-severity convention issue was found:

- **F003** — `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/scip_adapter.py:28-35` introduces the ABC as `SCIPAdapterBase` instead of following the prevailing `{Name}Adapter` contract naming idiom used by files such as `sample_adapter.py`, `log_adapter.py`, and `embedding_adapter.py`.

### E.6) Harness Live Validation

N/A — no harness configured.

- The spec clarification explicitly says to continue without a harness.
- No `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/project-rules/harness.md` file exists.

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC1 | `fs2 scan` on Python project with `scip-python` produces cross-file reference edges | Phase-scoped adapter tests pass; reviewer also ran `uv run python` against `tests/fixtures/cross_file_sample/index.scip` and observed emitted edges. Full scan-path wiring is deferred to Phase 4. | 76 |
| AC2 | `fs2 scan` on TypeScript project produces edges | Deferred to Phase 2 / Phase 4. | 0 |
| AC3 | `fs2 scan` on Go project produces edges | Deferred to Phase 2 / Phase 4. | 0 |
| AC4 | `fs2 scan` on C# project produces edges | Deferred to Phase 2 / Phase 4. | 0 |
| AC5 | Missing indexer logs install instructions and scan continues | Deferred to Phase 4. | 0 |
| AC6 | `fs2 discover-projects` lists detected projects with status | Deferred to Phase 3. | 0 |
| AC7 | `fs2 add-project 1 2 3` writes projects to config | Deferred to Phase 3. | 0 |
| AC8 | `projects` config accepts declared fields | Deferred to Phase 3. | 0 |
| AC9 | Empty projects + `auto_discover=true` auto-discovers | Deferred to Phase 3 / Phase 4. | 0 |
| AC10 | `provider: serena` preserves current Serena path | Deferred to Phase 4. | 0 |
| AC11 | Deduplicated source→target edges | Directly covered by changed tests and reviewer rerun. | 95 |
| AC12 | Local symbols, stdlib refs, self-refs filtered out | Local/self-ref filtering directly tested; stdlib/external filtering only indirectly evidenced. | 64 |
| AC13 | Type aliases normalised to canonical names | Deferred to Phase 2 / Phase 3. | 0 |
| AC14 | `ref_kind` dropped; edges use `{"edge_type": "references"}` only | Spec and phase artifacts agree on the drop; edge payload format is directly asserted by changed tests. | 100 |
| AC15 | `index.scip` cached in `.fs2/scip/` | Deferred to Phase 4. | 0 |

**Overall coverage confidence**: 78% (phase-scope)

## G) Commands Executed

```bash
git --no-pager diff --stat && printf '\n---STAGED---\n' && git --no-pager diff --staged --stat && printf '\n---LOG---\n' && git --no-pager log --oneline -12

PHASE_DIR='/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-1-scip-adapter-foundation'
REVIEW_DIR="$PHASE_DIR/reviews"
mkdir -p "$REVIEW_DIR"
PHASE_COMMIT=4c62f2d
PARENT=$(git rev-parse ${PHASE_COMMIT}^)
git --no-pager diff "$PARENT".."$PHASE_COMMIT" > "$REVIEW_DIR/_computed.diff"
git --no-pager diff --name-status "$PARENT".."$PHASE_COMMIT"
git --no-pager diff --stat "$PARENT".."$PHASE_COMMIT"
git --no-pager show --no-patch --stat --format=fuller "$PHASE_COMMIT"

uv run ruff check pyproject.toml src/fs2/core/adapters/exceptions.py src/fs2/core/adapters/scip_adapter.py src/fs2/core/adapters/scip_adapter_fake.py src/fs2/core/adapters/scip_adapter_python.py tests/unit/adapters/test_scip_adapter.py tests/unit/adapters/test_scip_adapter_python.py

uv run python -m pytest -q tests/unit/adapters/test_scip_adapter.py tests/unit/adapters/test_scip_adapter_python.py

uv run python - <<'PY'
from pathlib import Path
from fs2.core.adapters.scip_adapter_python import SCIPPythonAdapter
known_node_ids = {
    'file:model.py',
    'class:model.py:Item',
    'callable:model.py:Item.__init__',
    'callable:model.py:Item.display',
    'file:service.py',
    'class:service.py:ItemService',
    'callable:service.py:ItemService.__init__',
    'callable:service.py:ItemService.create_item',
    'callable:service.py:ItemService.format_item',
    'file:handler.py',
    'callable:handler.py:handle_request',
}
index = Path('tests/fixtures/cross_file_sample/index.scip')
edges = SCIPPythonAdapter().extract_cross_file_edges(index, known_node_ids)
for edge in edges:
    print(edge)
PY
```

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: APPROVE

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-spec.md
**Phase**: Phase 1: SCIP Adapter Foundation
**Tasks dossier**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-1-scip-adapter-foundation/tasks.md
**Execution log**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-1-scip-adapter-foundation/execution.log.md
**Review file**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-1-scip-adapter-foundation/reviews/review.phase-1-scip-adapter-foundation.md

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-1-scip-adapter-foundation/execution.log.md | Created | phase-artifact | Optional: preserve explicit RED→GREEN evidence for TDD claims |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-1-scip-adapter-foundation/tasks.fltplan.md | Modified | phase-artifact | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-1-scip-adapter-foundation/tasks.md | Modified | phase-artifact | Optional: align TDD claims with preserved evidence wording |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/pyproject.toml | Modified | config | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/exceptions.py | Modified | core/adapters | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/scip_adapter.py | Created | core/adapters | Optional follow-up: rename `SCIPAdapterBase` to `SCIPAdapter` for convention alignment |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/scip_adapter_fake.py | Created | core/adapters | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/scip_adapter_python.py | Created | core/adapters | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/scip_pb2.py | Created | core/adapters | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/fixtures/cross_file_sample/index.scip | Created | tests-fixture | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_scip_adapter.py | Created | tests | Optional: add explicit stdlib/external-symbol filtering coverage |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_scip_adapter_python.py | Created | tests | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/uv.lock | Modified | dependency-lock | None |

### Required Fixes (if REQUEST_CHANGES)

None — verdict is APPROVE.

### Domain Artifacts to Update (if any)

None. This repository does not currently have `/docs/domains/` artifacts, and the phase dossier explicitly notes that no formal domain registry exists to update.

### Next Step

/plan-5-v2-phase-tasks-and-brief --phase "Phase 2: Multi-Language Adapters" --plan /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-plan.md
