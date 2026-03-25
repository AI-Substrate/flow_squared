# Code Review: Phase 1 — Implementation

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/032-local-embeddings/local-embeddings-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/032-local-embeddings/local-embeddings-spec.md
**Phase**: Phase 1: Implementation (Simple Mode)
**Date**: 2026-03-15
**Reviewer**: Automated (plan-7-v2)
**Testing Approach**: Full TDD

## A) Verdict

**REQUEST_CHANGES**

The phase is close, but it is not approvable yet: the new local-mode wiring crosses architecture boundaries, the new force-guidance points users at a command the CLI does not support, and the critical dimension-mismatch/`--force` path is not backed by the tests and execution evidence the phase claims.

**Key failure areas**:
- **Implementation**: New force-mode guidance tells users to run `fs2 scan --embed --force`, but `scan --help` shows no `--embed` option.
- **Domain compliance**: Local provider resolution leaked into the service layer and an adapter contract file instead of staying behind adapter-layer boundaries.
- **Testing**: The central `--force` mismatch flow is not covered by the claimed tests, and the execution log overstates what was verified.
- **Doctrine**: `src/fs2/core/adapters/embedding_adapter.py` now imports `sentence_transformers` directly, violating the repo's adapter-boundary rule.

## B) Summary

The config and adapter basics are mostly solid: local mode defaults, local config validation, factory creation, and return-type behavior all have credible unit-test coverage. Reinvention risk is low; the new local adapter extends existing embedding patterns rather than duplicating a capability that already exists elsewhere.

However, the review found two meaningful architectural regressions. First, `src/fs2/core/adapters/embedding_adapter.py` now probes `sentence_transformers` directly, pulling provider-SDK knowledge into a contract-layer module. Second, `src/fs2/core/services/embedding/embedding_service.py` duplicates local provider construction instead of reusing a single adapter-layer factory path.

There is also a user-facing correctness problem: both the new runtime mismatch message and the new local-embeddings guide tell users to run `fs2 scan --embed --force`, but the actual CLI exposes `--force` and `--no-embeddings`, not `--embed`. Finally, the phase claims T008/AC13 were covered, but the scoped diff contains no new embedding-stage or scan CLI tests for the mismatch/force path, and the execution log names a stage-test path that does not exist.

## C) Checklist

**Testing Approach: Full TDD**

- [x] Config and local-adapter unit tests were added for core local-mode behavior
- [ ] RED/GREEN evidence exists for the dimension-mismatch block and `--force` override path
- [ ] Device-detection tests exercise the real implementation and assert required log output
- [ ] Only in-scope files changed
- [ ] Linters/type checks clean (if applicable)
- [ ] Domain compliance checks pass

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | HIGH | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/embedding_adapter.py:155-162` | pattern | Adapter contract/factory module imports `sentence_transformers` directly | Move the dependency probe behind an implementation-owned helper or the local adapter itself so the contract file remains SDK-free |
| F002 | HIGH | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/embedding/embedding_service.py:160-178` | pattern | Service layer duplicates local adapter construction and imports implementation internals | Reuse a single adapter-layer factory path and remove provider-specific imports/probes from `EmbeddingService.create()` |
| F003 | HIGH | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/embedding_stage.py:85-95`; `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/local-embeddings.md:15-18,77-83,104-109` | correctness | New force guidance points to nonexistent `fs2 scan --embed --force` command | Change guidance to a command the CLI actually supports, or add a real `--embed` alias |
| F004 | HIGH | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/embedding_stage.py:80-115`; `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/scan.py:82-88,292-314` | testing | Critical `--force` mismatch behavior is not backed by the claimed tests/evidence | Add stage/pipeline/CLI regression tests and update the execution log with the real commands and files |
| F005 | MEDIUM | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_embedding_adapter_local.py:132-224` | pattern | Device-detection tests stub out `_detect_device()` with lambdas and skip required log assertions; the file also fails Ruff | Test the real `_detect_device()` via mocked `torch` + `caplog`, and make the file lint-clean |
| F006 | MEDIUM | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/embedding_stage.py:61-62,97-115,159-160` | correctness | Force mode clears preserved embeddings but still reports the pre-clear preserved count in metrics | Recompute `embedding_preserved` after the force-clear path or derive it from post-clear state |
| F007 | LOW | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/embedding/embedding_service.py:160-178` | scope | Actual touched service-layer work is missing from the phase manifest/execution artifacts | Update the plan/log/manifest to reflect the real touched surface, including `embedding_service.py` |

## E) Detailed Findings

### E.1) Implementation Quality

**F003 — Invalid force guidance**

`EmbeddingStage.process()` now emits a runtime error telling users to run `fs2 scan --embed --force`, and the new guide repeats the same command in quick-start, migration, and troubleshooting examples. But `uv run python -m fs2.cli.main scan --help` shows only `--force` and `--no-embeddings`, not `--embed`, so the new guidance is not executable.

**F006 — Stale preserved metrics in force mode**

`preserved_count` is calculated before the force-mode branch clears existing embeddings. When the force path runs, `embedding_preserved` still reports the pre-clear count even though those embeddings were explicitly nulled and regenerated, so the summary metrics overstate preservation.

### E.2) Domain Compliance

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | New files are under expected trees: adapter impl in `src/fs2/core/adapters/`, tests in `tests/unit/adapters/`, docs in `docs/how/user/`. |
| Contract-only imports | ❌ | `EmbeddingService.create()` imports `LocalEmbeddingConfig` and `SentenceTransformerEmbeddingAdapter` directly from implementation modules instead of going through a public adapter-layer factory. |
| Dependency direction | ❌ | Provider-specific local wiring now exists in both `embedding_adapter.py` and `embedding_service.py`, leaking local provider selection into contract/service layers. |
| Domain.md updated | ✅ | `docs/domains/*/domain.md` does not exist in this repo; no domain-doc system to update for this phase. |
| Registry current | ✅ | `docs/domains/registry.md` does not exist in this repo; no registry artifact to update. |
| No orphan files | ❌ | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/embedding/embedding_service.py` appears in the scoped diff but not in the plan Domain Manifest. |
| Map nodes current | ✅ | `docs/domains/domain-map.md` does not exist in this repo; no map artifact to update. |
| Map edges current | ✅ | No domain map exists, so edge-label currency is not applicable here. |
| No circular business deps | ✅ | No new business-to-business cycle was identified in the reviewed local-embeddings surfaces. |
| Concepts documented | N/A | No domain documentation system exists in this repo. |

The absence of `docs/domains/` artifacts means the review could only validate file placement, import direction, and manifest fidelity. Within that reduced scope, the local provider wiring is the main compliance problem.

### E.3) Anti-Reinvention

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| `SentenceTransformerEmbeddingAdapter` | `scripts/embeddings/benchmark.py` contains similar device-detection/benchmark setup only | scripts | Proceed |
| Local embedding config/defaults | Existing nested provider config pattern (`AzureEmbeddingConfig`, `OpenAIEmbeddingConfig`) | config | Extend existing pattern |
| Force re-embed on dimension mismatch | Existing embedding-stage mismatch warning path and smart-content prior-state preservation patterns | services | Extend existing pattern |

No genuine reinvention problem was found.

### E.4) Testing & Evidence

**Coverage confidence**: 40%

| AC | Confidence | Evidence |
|----|------------|----------|
| AC1 | 30% | Unit evidence only: local adapter encode flow and local factory wiring are covered, but no scoped `scan` transcript proves local embeddings were actually generated without API/network usage. |
| AC2 | 5% | No scoped test or execution-log transcript demonstrates semantic search using locally generated embeddings. |
| AC3 | 25% | CUDA path has a unit test, but it replaces the implementation with patched logic and does not assert the required GPU-name log output. |
| AC4 | 10% | The MPS test stubs `_detect_device` to return `"mps"`; it does not exercise the real implementation or its log output. |
| AC5 | 10% | The CPU fallback test stubs `_detect_device` to return `"cpu"`; it does not exercise the real implementation. |
| AC6 | 10% | The unavailable-device fallback test stubs `_detect_device` to return `"cpu"`; it does not assert the required warning. |
| AC7 | 25% | `_get_model()` raises `EmbeddingAdapterError`, but the factory returns `None` when dependencies are missing, leaving the user-visible behavior inconsistent with the spec. |
| AC8 | 92% | Strong unit coverage in `tests/unit/config/test_embedding_config.py` for local defaults and dimension auto-default behavior. |
| AC9 | 12% | Source logs a dimension warning, but no scoped test asserts that warning despite the execution log claiming such coverage. |
| AC10 | 96% | `test_given_texts_when_embed_batch_then_returns_list_of_list_float` directly validates list-of-float return type. |
| AC11 | 93% | Darwin `pool=None` and Linux-no-pool behavior are directly asserted in `test_embedding_adapter_local.py`. |
| AC12 | 93% | Factory returns a `SentenceTransformerEmbeddingAdapter` for `mode="local"`, and missing `local:` config is defaulted in the factory tests. |
| AC13 | 22% | Code exists in `embedding_stage.py` and `scan.py`, but the scoped diff contains no new stage/pipeline/CLI tests for mismatch blocking, force propagation, or exact command guidance. |

Additional evidence gathered during review:

- `uv run python -m pytest -q tests/unit/config/test_embedding_config.py tests/unit/adapters/test_embedding_adapter.py tests/unit/adapters/test_embedding_adapter_local.py tests/unit/services/test_embedding_stage.py tests/unit/services/test_pipeline_context.py tests/unit/services/test_scan_pipeline.py tests/unit/cli/test_init_cli.py tests/unit/cli/test_scan_cli.py` → 118 passed, 57 deselected, 1 warning
- `uv run python -m pytest -q --override-ini='addopts=' tests/unit/cli/test_init_cli.py tests/unit/cli/test_scan_cli.py` → 55 passed, 2 failed (both pre-existing CLI assertions unrelated to local-embeddings behavior)
- `uv run ruff check ...` failed on `tests/unit/adapters/test_embedding_adapter_local.py`

### E.5) Doctrine Compliance

N/A — no `docs/project-rules/` files exist in this repo, so doctrine was evaluated against the repository's standing instructions and the phase plan.

**F001 — Contract file imports provider SDK**

`src/fs2/core/adapters/embedding_adapter.py` is the public adapter contract/factory surface. The new local branch probes `sentence_transformers` there, which violates the repo rule that provider SDK imports belong in implementation files only.

**F002 — Service layer duplicates provider construction**

`EmbeddingService.create()` adds a second local-mode construction path that imports `LocalEmbeddingConfig` and `SentenceTransformerEmbeddingAdapter` directly. That duplicates the adapter-selection logic already added to `create_embedding_adapter_from_config()` and makes local mode behave differently depending on which path is used.

### E.6) Harness Live Validation

N/A — no `docs/project-rules/harness.md` exists in this repo, and the phase execution log explicitly records harness unavailability.

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC1 | Local scan generates embeddings without API/network | No scoped integration transcript; only adapter/factory unit tests | 30% |
| AC2 | Semantic search returns results from local embeddings | No scoped evidence | 5% |
| AC3 | CUDA auto-detects and logs GPU name | Weak unit test with patched logic, no log assertion | 25% |
| AC4 | Apple Silicon auto-detects MPS and logs it | Stubbed test only, no real implementation/log assertion | 10% |
| AC5 | CPU fallback on machines without GPU | Stubbed test only | 10% |
| AC6 | Requested unavailable device falls back with warning | Stubbed test only, no warning assertion | 10% |
| AC7 | Missing deps produce actionable error | Adapter-level error test conflicts with factory-level graceful `None` path | 25% |
| AC8 | `dimensions` auto-defaults to 384 for local mode | Strong config-model tests | 92% |
| AC9 | Dimension mismatch warning when config vs model differs | Source path exists, but no warning assertion in scoped tests | 12% |
| AC10 | Return type is `list[list[float]]` | Direct unit test | 96% |
| AC11 | macOS sets `pool=None` | Direct unit test | 93% |
| AC12 | Factory returns local adapter | Direct unit test | 93% |
| AC13 | Stored-vs-current dimension mismatch blocks scan; `--force` overrides | Code exists, but no matching scoped regression tests/evidence | 22% |

**Overall coverage confidence**: 40%

## G) Commands Executed

```bash
git --no-pager diff --stat && printf '\n---STAGED---\n' && git --no-pager diff --staged --stat && printf '\n---STATUS---\n' && git --no-pager status --short && printf '\n---LOG---\n' && git --no-pager log --oneline -12

# phase-scoped diff artifact (writes reviews/_computed.diff and reviews/_manifest.txt)
set -euo pipefail
REPO=/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2
PLAN_DIR="$REPO/docs/plans/032-local-embeddings"
REVIEW_DIR="$PLAN_DIR/reviews"
mkdir -p "$REVIEW_DIR"
...

uv run python -m pytest -q tests/unit/config/test_embedding_config.py tests/unit/adapters/test_embedding_adapter.py tests/unit/adapters/test_embedding_adapter_local.py tests/unit/services/test_embedding_stage.py tests/unit/services/test_pipeline_context.py tests/unit/services/test_scan_pipeline.py tests/unit/cli/test_init_cli.py tests/unit/cli/test_scan_cli.py

uv run ruff check src/fs2/config/objects.py src/fs2/core/adapters/embedding_adapter.py src/fs2/core/adapters/embedding_adapter_local.py src/fs2/core/services/embedding/embedding_service.py src/fs2/core/services/pipeline_context.py src/fs2/core/services/scan_pipeline.py src/fs2/core/services/stages/embedding_stage.py src/fs2/cli/init.py src/fs2/cli/scan.py tests/unit/config/test_embedding_config.py tests/unit/adapters/test_embedding_adapter.py tests/unit/adapters/test_embedding_adapter_local.py

uv run python -m pytest -q --override-ini='addopts=' tests/unit/cli/test_init_cli.py tests/unit/cli/test_scan_cli.py

uv run python -m fs2.cli.main scan --help | sed -n '1,160p'
```

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: REQUEST_CHANGES

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/032-local-embeddings/local-embeddings-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/032-local-embeddings/local-embeddings-spec.md
**Phase**: Phase 1: Implementation (Simple Mode)
**Tasks dossier**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/032-local-embeddings/tasks/implementation/tasks.md
**Execution log**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/032-local-embeddings/tasks/implementation/execution.log.md
**Review file**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/032-local-embeddings/reviews/review.md

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/configuration-guide.md | modified | docs | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/local-embeddings.md | created | docs | Fix invalid `scan --embed` guidance |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/pyproject.toml | modified | config | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/uv.lock | modified | dependencies | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/init.py | modified | cli | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/scan.py | modified | cli | Add/verify `--force` regression coverage |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/config/objects.py | modified | config | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/__init__.py | modified | adapters | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/embedding_adapter.py | modified | adapters | Remove direct SDK probe from contract/factory file |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/embedding_adapter_local.py | created | adapters | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/embedding/embedding_service.py | modified | services | Remove duplicate provider-specific wiring; route via adapter-layer factory |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/pipeline_context.py | modified | services | Verify/support force-path tests |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/scan_pipeline.py | modified | services | Verify/support force-path tests |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/embedding_stage.py | modified | services | Fix invalid command text and preserved metric; add force-path tests |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_embedding_adapter.py | modified | tests | Reconcile missing-dependency behavior with spec |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_embedding_adapter_local.py | created | tests | Strengthen real device-detection assertions and make Ruff clean |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/config/test_embedding_config.py | modified | tests | None |

### Required Fixes (if REQUEST_CHANGES)

| # | File (absolute path) | What To Fix | Why |
|---|---------------------|-------------|-----|
| 1 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/embedding_adapter.py | Remove `sentence_transformers` probing from the contract/factory module | Contract-layer adapter code must remain provider-SDK free |
| 2 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/embedding/embedding_service.py | Stop constructing the local adapter directly in services; reuse a single adapter-layer creation path | Current local-mode wiring duplicates provider logic and violates intended dependency direction |
| 3 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/embedding_stage.py | Replace invalid `fs2 scan --embed --force` guidance and fix stale preserved metrics in force mode | Users are currently told to run a command the CLI does not support, and metrics overstate preservation after a forced re-embed |
| 4 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/local-embeddings.md | Update quick-start/migration/troubleshooting commands to a real CLI invocation | Current docs tell users to run an unsupported command |
| 5 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_embedding_stage.py; /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_scan_pipeline.py; /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_scan_cli.py | Add regression coverage for mismatch blocking, `--force` propagation, and force-mode re-embed behavior | AC13 is central to the phase but is not verified by the scoped tests |
| 6 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_embedding_adapter_local.py | Exercise the real `_detect_device()` logic with mocked `torch`, assert required logs, and make the file pass Ruff | Current tests weakly evidence AC3-AC6 and fail lint |

### Domain Artifacts to Update (if any)

| File (absolute path) | What's Missing |
|---------------------|----------------|
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/032-local-embeddings/local-embeddings-plan.md | Domain Manifest omits `src/fs2/core/services/embedding/embedding_service.py` even though it is in the reviewed phase scope |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/032-local-embeddings/tasks/implementation/execution.log.md | Claims T008 stage-test coverage not present in the scoped diff and does not reflect the final reviewed file/test set |

### Next Step

/plan-6-v2-implement-phase --plan /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/032-local-embeddings/local-embeddings-plan.md --phase 'Phase 1: Implementation'
