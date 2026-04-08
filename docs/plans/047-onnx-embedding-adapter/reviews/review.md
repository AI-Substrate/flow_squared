# Code Review: ONNX Embedding Adapter

**Plan**: /Users/jordanknight/substrate/fs2/045-windows-compat/docs/plans/047-onnx-embedding-adapter/onnx-embedding-adapter-plan.md  
**Spec**: /Users/jordanknight/substrate/fs2/045-windows-compat/docs/plans/047-onnx-embedding-adapter/onnx-embedding-adapter-spec.md  
**Phase**: Simple Mode  
**Date**: 2026-04-08  
**Reviewer**: Automated (plan-7-v2)  
**Testing Approach**: Hybrid

## A) Verdict

**REQUEST_CHANGES**

High-severity issues remain in embedding metadata correctness, cached error handling, and verification evidence, and the commit-scoped lint claim is false.

**Key failure areas**:
- **Implementation**: `/Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/core/services/embedding/embedding_service.py` still persists `embedding_model="onnx"` instead of the actual model ID, and `/Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/core/adapters/embedding_adapter_onnx.py` caches a generic restart-only error after load failure.
- **Domain compliance**: `/Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/core/services/embedding/embedding_service.py` extends service-layer coupling to a concrete adapter implementation and ONNX-specific config defaulting.
- **Testing**: The phase does not directly verify numeric equivalence, config-driven pooling detection, or scan/search/warmup behavior, and the new ONNX test file fails `ruff`.
- **Doctrine**: The ONNX test suite diverges from the repo's canonical test format and fake-first/deterministic testing rules.

## B) Summary

The core ONNX adapter work is substantial and mostly coherent: the new adapter fits the existing embedding-adapter family, file placement matches the plan manifest, and no genuine reinvention was introduced. This repository also does not currently maintain a formal `docs/domains/` registry or domain map, so most domain-documentation checks are N/A for this phase. The review turns on three real quality gaps: `EmbeddingService.get_metadata()` still stores the mode name instead of the actual ONNX model identifier, `_session_error` loses actionable user guidance after warmup or a first failed load, and the phase artifacts do not directly verify several of the feature's highest-risk acceptance criteria. Because the reviewed commit also fails the lint gate it claims to satisfy, the phase is not approvable yet.

## C) Checklist

**Testing Approach: Hybrid**

- [x] Core validation tests present
- [ ] Critical paths covered
- [ ] Key verification points documented with concrete output
- [x] Only in-scope files changed
- [ ] Linters/type checks clean (if applicable)
- [ ] Domain compliance checks pass

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | HIGH | /Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/core/services/embedding/embedding_service.py:105-113 | correctness | `get_metadata()` still persists `embedding_model` as the mode name (`"onnx"`) instead of the actual HuggingFace model ID, so switching between same-dimension ONNX models can silently reuse stale embeddings. | Persist the actual ONNX model identifier in graph metadata and add a regression test proving model changes force re-embed. |
| F002 | HIGH | /Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/core/adapters/embedding_adapter_onnx.py:175-179,220-224 | error-handling | The adapter constructs an actionable missing-ONNX-export error, then overwrites it with a generic cached restart-only error for later calls. | Preserve and re-raise the original `EmbeddingAdapterError` when caching `_session_error`, or wrap it while keeping the original fix guidance visible. |
| F003 | HIGH | /Users/jordanknight/substrate/fs2/045-windows-compat/tests/unit/adapters/test_embedding_adapter_onnx.py:130-190,432-447; /Users/jordanknight/substrate/fs2/045-windows-compat/docs/plans/047-onnx-embedding-adapter/onnx-embedding-adapter-spec.md:108-126; /Users/jordanknight/substrate/fs2/045-windows-compat/docs/plans/047-onnx-embedding-adapter/execution.log.md:36-39 | testing | The phase's highest-risk promises are not directly regression-tested or evidenced: numeric equivalence, config-driven pooling detection, scan-path wiring, and warmup/search behavior remain mostly inferred. | Add deterministic commit-local regression tests and concrete command output for the hard ACs instead of relying on workshop prose or indirect reasoning. |
| F004 | HIGH | /Users/jordanknight/substrate/fs2/045-windows-compat/tests/unit/adapters/test_embedding_adapter_onnx.py:14,272-274,306,376; /Users/jordanknight/substrate/fs2/045-windows-compat/docs/plans/047-onnx-embedding-adapter/execution.log.md:63-67 | testing | The reviewed commit does not satisfy its own lint claim: the ONNX test file still fails `ruff`, so `execution.log.md` overstates the verification status. | Fix the test-file lint errors, rerun `ruff` on the reviewed scope, and record actual command/output evidence instead of summary-only tables. |
| F005 | MEDIUM | /Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/core/services/embedding/embedding_service.py:170-176 | dependency-direction | The new ONNX branch makes `EmbeddingService.create()` import `OnnxEmbeddingAdapter` and materialize `OnnxEmbeddingConfig()` directly, extending concrete adapter/config knowledge in the service layer. | Delegate ONNX adapter selection/defaulting to the adapter factory or composition root so the service depends only on contracts and injected config. |
| F006 | MEDIUM | /Users/jordanknight/substrate/fs2/045-windows-compat/tests/unit/adapters/test_embedding_adapter_onnx.py:1-447 | doctrine | The new tests do not follow the repo's canonical test format and deterministic fake-first rules: names/docstrings are lightweight, `MagicMock` is used for config/runtime collaborators, and `time.sleep()` coordinates concurrency. | Convert the suite to the repo's given/when/then + Purpose/Quality Contribution format, prefer fakes where feasible, and replace sleep-based coordination with threading primitives. |

## E) Detailed Findings

### E.1) Implementation Quality

- **F001** — `EmbeddingService.get_metadata()` stores `embedding_model` as `self._config.mode` at lines 107-112 instead of the actual ONNX model identifier. `EmbeddingStage._detect_metadata_mismatch()` compares `embedding_model`, so switching between same-dimension ONNX models can silently preserve stale vectors and mix embedding spaces.
- **F002** — `OnnxEmbeddingAdapter._get_session()` raises a detailed error for missing `onnx/model.onnx`, but then caches a new generic `_session_error` at lines 220-224. After warmup or a first failed load, later user-facing calls lose the actionable root cause that AC-7 and the repo's error doctrine require.
- Outside those issues, the reviewed implementation follows the planned shape reasonably well: lazy imports avoid pulling torch, offline-first download flow is sensible, and the pooling/normalization pipeline is structurally consistent with the intended design.
- No material security issue stood out in the reviewed diff.

### E.2) Domain Compliance

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | All 10 commit-scoped files align with the plan manifest and expected repo layout. |
| Contract-only imports | ❌ | `/Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/core/services/embedding/embedding_service.py:170-176` imports `OnnxEmbeddingAdapter` directly instead of staying on the `EmbeddingAdapter` contract/factory boundary. |
| Dependency direction | ❌ | The same ONNX branch extends service-layer knowledge of infrastructure implementation and ONNX-specific config defaulting. |
| Domain.md updated | ✅ | N/A — the spec/plan explicitly state that no formal `docs/domains/<slug>/domain.md` system exists for this repo. |
| Registry current | ✅ | N/A — `/Users/jordanknight/substrate/fs2/045-windows-compat/docs/domains/registry.md` does not exist. |
| No orphan files | ✅ | Every reviewed file appears in the simple-mode manifest for this phase. |
| Map nodes current | ✅ | N/A — `/Users/jordanknight/substrate/fs2/045-windows-compat/docs/domains/domain-map.md` does not exist. |
| Map edges current | ✅ | N/A — no formal domain-map artifact exists in this repository. |
| No circular business deps | ✅ | No new business-layer cycle was introduced by the reviewed commit. |
| Concepts documented | N/A | No formal per-domain concept tables exist in this repository. |

The repository's domain-doc system is absent by design for this feature, so the substantive domain concern is the new service-layer coupling, not missing registry/map files.

### E.3) Anti-Reinvention

No genuine duplication was found.

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| OnnxEmbeddingAdapter | Existing embedding-adapter family pattern only (`SentenceTransformerEmbeddingAdapter`, API adapters) | embedding-adapters | Proceed |
| OnnxEmbeddingConfig | Analogous config-object pattern already used by `LocalEmbeddingConfig` and provider-specific embedding config models | config | Proceed |
| ONNX factory wiring | Existing adapter-selection flow already exists in adapter factory and `EmbeddingService.create()` | embedding-adapters / embedding-service | Proceed — extension, not duplicate capability |

### E.4) Testing & Evidence

**Coverage confidence**: **56%**

Violations:
- **F003 (HIGH)** — The phase does not directly verify AC-2/AC-5 and only indirectly covers AC-9/AC-10.
- **F004 (HIGH)** — Commit-scoped lint evidence is false: `ruff` fails on the new ONNX test file, contradicting the execution log.
- **Additional gap (MEDIUM)** — AC-3/AC-4/AC-11 rely on indirect reasoning and summary claims rather than concrete MCP/search/scan smoke output.

| AC | Confidence | Evidence |
|----|------------|----------|
| AC1 | 58 | Workshop timing supports the import-time claim, but the phase log contains no branch-local benchmark output. |
| AC2 | 48 | Workshop 001 validated equivalence, but `test_embedding_adapter_onnx.py` does not compare production output to reference vectors. |
| AC3 | 38 | No MCP semantic-search transcript or ranked-results artifact appears in the phase evidence. |
| AC4 | 32 | `EmbeddingService.create()` has an ONNX branch, but there is no service-factory test or `fs2 scan --embed` transcript. |
| AC5 | 42 | Pooling math is tested only by forcing `_use_cls_pooling`; config-driven detection from `1_Pooling/config.json` is not exercised. |
| AC6 | 72 | Factory degradation is directly covered by `test_factory_returns_none_when_onnxruntime_missing`. |
| AC7 | 35 | The first-failure path builds an actionable missing-export error, but cached warmup failures replace it with a generic restart-only message. |
| AC8 | 92 | Config-model defaults, validation, and auto-dimensions are directly covered. |
| AC9 | 52 | Concurrency is tested with a custom slow-loader stub rather than the production `_get_session()` path. |
| AC10 | 46 | `warmup()` no-raise behavior is covered, but there is no real preload transcript or production-path regression. |
| AC11 | 54 | "No regression" is inferred from suite counts rather than explicit multi-mode smoke evidence. |
| AC12 | 93 | Return-type expectations are directly asserted. |

### E.5) Doctrine Compliance

Doctrine was validated against the repo's canonical governance docs under `/Users/jordanknight/substrate/fs2/045-windows-compat/docs/rules-idioms-architecture/`.

- **F002** violates **R3.3 / Constitution P8**: cached errors must remain actionable.
- **F004** violates **R2.4 / R7.1**: the reviewed commit is not lint-clean despite the logged claim.
- **F005** violates **R2.1 / R3.2 / Constitution P1,P3**: the service layer gains implementation-specific adapter/config knowledge.
- **F006** violates **R4.2 / R4.3 / R4.4 / R4.6 / Constitution P4,P7**: the test suite does not match the repo's canonical fake-first, documented, deterministic style.

### E.6) Harness Live Validation

N/A — no harness configured in this repository (`docs/project-rules/harness.md` not found, and no equivalent harness doc is present for this plan).

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC1 | Import time under 2 seconds, no torch import | Workshop timing only; no branch-local benchmark artifact in `execution.log.md` | 58 |
| AC2 | Numeric equivalence to sentence-transformers | Workshop-backed claim only; no commit-local reference-vector regression test | 48 |
| AC3 | MCP search works with `mode: "onnx"` | No MCP semantic-search transcript in the phase artifacts | 38 |
| AC4 | `fs2 scan --embed` works via `EmbeddingService` | ONNX branch exists, but no service test or scan transcript proves the path | 32 |
| AC5 | Reads `1_Pooling/config.json` and selects CLS/mean correctly | Detection code exists; tests only force `_use_cls_pooling` manually | 42 |
| AC6 | Missing `onnxruntime` degrades gracefully | Factory unit test covers `None` return when `onnxruntime` is absent | 72 |
| AC7 | Missing ONNX export raises actionable error | First-failure message is actionable, but cached warmup failures lose that detail | 35 |
| AC8 | Config integration (`mode`, defaults, validation) | Direct config tests cover defaults, override, validation, auto-dimensions | 92 |
| AC9 | Thread-safe lazy session loading | Concurrency test uses a custom stub rather than the production load path | 52 |
| AC10 | `warmup()` preload support | `warmup()` no-raise behavior is tested, but no production preload evidence exists | 46 |
| AC11 | Existing modes unaffected | Inferred from suite summary; no explicit multi-mode smoke evidence | 54 |
| AC12 | Return type contract | Direct unit tests assert Python `list[float]` / `list[list[float]]` outputs | 93 |

**Overall coverage confidence**: **56%**

## G) Commands Executed

```bash
git --no-pager diff --stat
git --no-pager diff --staged --stat
git --no-pager log --oneline -10
git --no-pager show --stat --name-status --format=fuller b5b2b5d
git --no-pager diff b5b2b5d^..b5b2b5d > /Users/jordanknight/substrate/fs2/045-windows-compat/docs/plans/047-onnx-embedding-adapter/reviews/_computed.diff
git --no-pager show b5b2b5d:src/fs2/core/services/embedding/embedding_service.py | nl -ba | sed -n '160,180p'
git --no-pager show b5b2b5d:src/fs2/core/adapters/embedding_adapter_onnx.py | nl -ba | sed -n '214,230p'
git --no-pager show b5b2b5d:tests/unit/adapters/test_embedding_adapter_onnx.py | nl -ba | sed -n '130,190p'
uv run ruff check tests/unit/adapters/test_embedding_adapter_onnx.py
uv run pytest -q tests/unit/adapters/test_embedding_adapter_onnx.py -q
tmpdir=$(mktemp -d) && git show b5b2b5d:<file> > "$tmpdir/<file>" ... && uv run ruff check "$tmpdir/src/fs2/config/objects.py" "$tmpdir/src/fs2/core/adapters/embedding_adapter.py" "$tmpdir/src/fs2/core/adapters/embedding_adapter_onnx.py" "$tmpdir/src/fs2/core/services/embedding/embedding_service.py" "$tmpdir/tests/unit/adapters/test_embedding_adapter_onnx.py"
```

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: REQUEST_CHANGES

**Plan**: /Users/jordanknight/substrate/fs2/045-windows-compat/docs/plans/047-onnx-embedding-adapter/onnx-embedding-adapter-plan.md  
**Spec**: /Users/jordanknight/substrate/fs2/045-windows-compat/docs/plans/047-onnx-embedding-adapter/onnx-embedding-adapter-spec.md  
**Phase**: Simple Mode  
**Tasks dossier**: inline in plan  
**Execution log**: /Users/jordanknight/substrate/fs2/045-windows-compat/docs/plans/047-onnx-embedding-adapter/execution.log.md  
**Review file**: /Users/jordanknight/substrate/fs2/045-windows-compat/docs/plans/047-onnx-embedding-adapter/reviews/review.md

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| /Users/jordanknight/substrate/fs2/045-windows-compat/docs/plans/047-onnx-embedding-adapter/execution.log.md | created | plan/docs | Add concrete command/output evidence |
| /Users/jordanknight/substrate/fs2/045-windows-compat/docs/plans/047-onnx-embedding-adapter/onnx-embedding-adapter-plan.md | modified | plan/docs | None |
| /Users/jordanknight/substrate/fs2/045-windows-compat/pyproject.toml | modified | project | None |
| /Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/config/objects.py | modified | config | None |
| /Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/core/adapters/embedding_adapter.py | modified | embedding-adapters | None |
| /Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/core/adapters/embedding_adapter_onnx.py | created | embedding-adapters | Preserve actionable cached errors |
| /Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/core/services/embedding/embedding_service.py | modified | embedding-service | Persist actual ONNX model metadata and reduce service-layer coupling to concrete ONNX adapter/config details |
| /Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/docs/configuration-guide.md | modified | docs | None |
| /Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/docs/local-embeddings.md | modified | docs | None |
| /Users/jordanknight/substrate/fs2/045-windows-compat/tests/unit/adapters/test_embedding_adapter_onnx.py | created | tests | Add direct coverage, fix lint failures, align with test doctrine |

### Required Fixes (if REQUEST_CHANGES)

| # | File (absolute path) | What To Fix | Why |
|---|---------------------|-------------|-----|
| 1 | /Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/core/services/embedding/embedding_service.py | Persist the actual ONNX model identifier in graph metadata | Storing only `"onnx"` can hide same-dimension model changes and silently reuse stale embeddings |
| 2 | /Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/core/adapters/embedding_adapter_onnx.py | Preserve the original actionable `EmbeddingAdapterError` when caching `_session_error` | Warmup/first-failure caching currently strips the user-facing fix guidance promised by AC-7 |
| 3 | /Users/jordanknight/substrate/fs2/045-windows-compat/tests/unit/adapters/test_embedding_adapter_onnx.py | Add direct regression coverage for equivalence, pooling detection, and the real load/warmup path | Core ACs are still mostly inferred rather than directly protected |
| 4 | /Users/jordanknight/substrate/fs2/045-windows-compat/tests/unit/adapters/test_embedding_adapter_onnx.py | Fix the commit-scoped `ruff` failures | The phase currently fails its own recorded lint gate |
| 5 | /Users/jordanknight/substrate/fs2/045-windows-compat/docs/plans/047-onnx-embedding-adapter/execution.log.md | Record actual MCP/search/scan/preload verification output | Execution evidence is currently summary-only and too weak for several ACs |
| 6 | /Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/core/services/embedding/embedding_service.py | Remove direct ONNX implementation/config construction from the service layer | The phase extends a service -> adapter-implementation dependency |

### Domain Artifacts to Update (if any)

| File (absolute path) | What's Missing |
|---------------------|----------------|
| N/A | No formal `docs/domains/` registry, map, or `domain.md` artifacts exist for this repository/plan, so no phase-specific domain-doc update is required. |

### Next Step

/plan-6-v2-implement-phase --plan /Users/jordanknight/substrate/fs2/045-windows-compat/docs/plans/047-onnx-embedding-adapter/onnx-embedding-adapter-plan.md
