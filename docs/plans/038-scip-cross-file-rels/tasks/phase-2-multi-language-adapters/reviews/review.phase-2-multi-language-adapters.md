# Code Review: Phase 2: Multi-Language Adapters

**Plan**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-plan.md`
**Spec**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-spec.md`
**Phase**: `Phase 2: Multi-Language Adapters`
**Date**: `2026-03-17`
**Reviewer**: Automated (plan-7-v2)
**Testing Approach**: `Hybrid`

## A) Verdict

**REQUEST_CHANGES**

The phase is close, but the new alias/factory contract is internally inconsistent: `js` normalises to `javascript`, while `create_scip_adapter()` cannot construct a `javascript` adapter. That means AC13 is not actually satisfied even though the phase docs mark it complete.

**Key failure areas**:
- **Implementation**: JavaScript alias support is documented as complete, but `create_scip_adapter(normalise_language("js"))` raises `SCIPAdapterError`.
- **Domain compliance**: The phase diff includes `.chainglass/data/activity-log.jsonl`, which is outside the declared Phase 2 scope/manifest.
- **Testing**: Automated tests cover `normalise_language()` but not the alias-to-factory success path that exposes the `js` breakage.

## B) Summary

Most of the phase is strong. The three new language adapters are minimal, pattern-consistent subclasses of `SCIPAdapterBase`, the fixture-backed tests are substantial, and a targeted rerun of lint plus adapter tests passed cleanly (`95 passed`, with one unrelated pytest config warning).

Static review found no meaningful cross-layer or contract import violations in the changed adapter code, and the anti-reinvention pass concluded the per-language adapters are intentional specialisations rather than duplicated concepts.

The blocking issue is the new alias/factory pathway: `normalise_language("js")` returns `javascript`, but `create_scip_adapter("javascript")` fails. That directly contradicts the phase dossier/flight plan claims and leaves AC13 only partially implemented.

Separately, the phase diff contains a tracked telemetry file under `.chainglass/` that is not part of the declared adapter/tests/fixtures/doc artifacts for this phase and should be removed from the merge scope.

## C) Checklist

**Testing Approach: Hybrid**

- [x] Core validation tests present
- [x] Fixture-backed critical paths covered
- [ ] Alias/factory acceptance path fully verified

Universal:
- [ ] Only in-scope files changed
- [x] Linters/type checks clean (if applicable)
- [ ] Domain compliance checks pass

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | HIGH | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/scip_adapter.py:34-49,74-106` | correctness | `js` normalises to `javascript`, but the factory has no `javascript` mapping, so the documented alias path fails. | Map `javascript` to the shared TypeScript adapter or change normalisation so accepted aliases always produce constructible adapter keys; add direct regression tests. |
| F002 | MEDIUM | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/.chainglass/data/activity-log.jsonl` | scope | The phase diff includes tracked local telemetry outside the declared Phase 2 manifest and task paths. | Remove or split this file out before merge so the phase contains only manifest-backed artifacts. |

## E) Detailed Findings

### E.1) Implementation Quality

**F001 — HIGH — alias/factory mismatch breaks documented JS support**

`LANGUAGE_ALIASES` now accepts `js` and canonicalises it to `javascript`, and the phase docs/flight plan both claim `js` alias support is complete. However, `create_scip_adapter()` only registers `python`, `typescript`, `go`, and `dotnet`, so `create_scip_adapter(normalise_language("js"))` raises `SCIPAdapterError` instead of constructing the shared TypeScript/JavaScript adapter.

Observed evidence:
- `uv run python - <<'PY' ...` probe returned: `js -> javascript -> FACTORY_ERROR: SCIPAdapterError ...`
- `tests/unit/adapters/test_scip_adapter.py` covers `normalise_language("js") == "javascript"` but has no direct `create_scip_adapter()` success-path test for `js`/`javascript`

This is a real correctness issue rather than a documentation nit because the exported API added in this phase does not implement the contract the phase claims to support.

### E.2) Domain Compliance

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | New adapter files live under `src/fs2/core/adapters/`, new tests under `tests/unit/adapters/`, and fixtures under `scripts/scip/fixtures/`, matching the phase dossier. |
| Contract-only imports | ✅ | Changed adapter code imports only base adapter/protobuf/exception modules inside `core/adapters`; no cross-domain internal imports were introduced. |
| Dependency direction | ✅ | No forbidden infrastructure→business or adapter→service/repo/cli imports were added. |
| Domain.md updated | N/A | `docs/domains/` is not present in this repository, so domain.md currency could not be checked. |
| Registry current | N/A | `docs/domains/registry.md` is absent. No new domains were introduced. |
| No orphan files | ❌ | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/.chainglass/data/activity-log.jsonl` is included in the phase diff but is outside the declared Phase 2 scope/manifest. |
| Map nodes current | N/A | `docs/domains/domain-map.md` is absent. |
| Map edges current | N/A | `docs/domains/domain-map.md` is absent, so edge-label validation is not applicable here. |
| No circular business deps | ✅ | Best-effort static review of changed code/imports found no business-layer cycle introduction. |
| Concepts documented | N/A | No `docs/domains/*/domain.md` files exist, so Concepts-table validation is not applicable. |

**F002 — MEDIUM — orphan/out-of-scope tracked file**

The phase diff includes `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/.chainglass/data/activity-log.jsonl`. That file is not in the plan Domain Manifest, not listed in the phase task paths, and not part of the intended adapter/tests/fixtures/doc outputs for Phase 2.

### E.3) Anti-Reinvention

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| `SCIPTypeScriptAdapter` | `SCIPPythonAdapter` + shared template logic in `scip_adapter.py` | `core/adapters` | Proceed |
| `SCIPGoAdapter` | `SCIPPythonAdapter` + shared descriptor parsing in `scip_adapter.py` | `core/adapters` | Proceed |
| `SCIPDotNetAdapter` | `SCIPPythonAdapter` + `should_skip_document()` hook in `scip_adapter.py` | `core/adapters` | Proceed |
| `LANGUAGE_ALIASES` / `normalise_language()` / `create_scip_adapter()` | Existing factory/canonicalisation idioms elsewhere in adapters and parser code | `core/adapters` | Extend existing pattern |

No blocking duplication was found. The new adapter classes are intentional language-specific extensions of the existing SCIP adapter hierarchy rather than reinventions of already-owned behavior.

### E.4) Testing & Evidence

**Coverage confidence**: `83%`

Additional observed evidence from this review:
- `uv run ruff check ...` on all changed adapter/test Python files: **passed**
- `uv run python -m pytest -q tests/unit/adapters/test_scip_adapter.py tests/unit/adapters/test_scip_adapter_typescript.py tests/unit/adapters/test_scip_adapter_go.py tests/unit/adapters/test_scip_adapter_dotnet.py`: **95 passed**, 1 unrelated pytest config warning

| AC | Confidence | Evidence |
|----|------------|----------|
| AC2 | 78 | `tests/unit/adapters/test_scip_adapter_typescript.py` passed with real fixture coverage for handler→service, service→model, edge format, no self-refs, and dedup. |
| AC3 | 78 | `tests/unit/adapters/test_scip_adapter_go.py` passed with real fixture coverage for main→service, service→model, edge format, no self-refs, dedup, and Go backtick/import-path parsing. |
| AC4 | 80 | `tests/unit/adapters/test_scip_adapter_dotnet.py` passed with real fixture coverage for Program→Service, Service→Model, dedup, and `obj/` generated-document filtering. |
| AC11 | 94 | Deduplication is asserted in `test_scip_adapter.py` and in each fixture-backed language suite; targeted rerun passed cleanly. |
| AC12 | 82 | Strong evidence for local symbol filtering, self-ref filtering, and generated C# document filtering; stdlib filtering is only indirectly evidenced. |
| AC13 | 25 | `normalise_language()` tests cover aliases, but there is no factory-path test and a direct probe showed `js -> javascript -> FACTORY_ERROR`. |

### E.5) Doctrine Compliance

N/A — no `docs/project-rules/` directory exists in this repository.

Best-effort review against `AGENTS.md` and `CLAUDE.md` found no additional layer-boundary or naming violations beyond **F001**, which already captures the only meaningful idiom drift: accepted canonical names should line up with constructible factory outputs.

### E.6) Harness Live Validation

N/A — no harness configured.

The plan/spec explicitly say harness validation is not applicable for this feature, and `docs/project-rules/harness.md` is absent.

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC2 | TypeScript project produces edges | Fixture-backed TypeScript adapter tests passed; handler→service and service→model edges asserted. | 78 |
| AC3 | Go project produces edges | Fixture-backed Go adapter tests passed; main→service and service→model edges asserted. | 78 |
| AC4 | C# project produces edges | Fixture-backed dotnet adapter tests passed; Program→Service and Service→Model edges asserted; generated docs filtered. | 80 |
| AC11 | Edges deduplicated | Deduplication tested in base suite and all new language suites; targeted rerun passed. | 94 |
| AC12 | Local/stdlib/self refs filtered | Local symbol and self-ref checks pass; C# generated docs filtered; stdlib filtering is only indirectly evidenced. | 82 |
| AC13 | Type aliases normalised to canonical names | Alias normalisation tests pass, but `js` canonicalises to unsupported `javascript` at factory time; direct probe fails. | 25 |

**Overall coverage confidence**: `83%`

## G) Commands Executed

```bash
git --no-pager diff --stat && printf '\n---STAGED---\n' && git --no-pager diff --staged --stat && printf '\n---STATUS---\n' && git --no-pager status --short && printf '\n---LOG---\n' && git --no-pager log --oneline -12

git --no-pager show --stat --oneline --name-only 13c107e && printf '\n---\n' && git --no-pager show --stat --oneline --name-only ff8837d && printf '\n---\n' && git --no-pager show --stat --oneline --name-only 9e1baa4

git --no-pager diff --name-status c9daf1d..HEAD

git --no-pager diff c9daf1d..HEAD > docs/plans/038-scip-cross-file-rels/tasks/phase-2-multi-language-adapters/reviews/_computed.diff

uv run python - <<'PY'
from fs2.core.adapters.scip_adapter import normalise_language, create_scip_adapter
for raw in ['ts','js','javascript','typescript','cs','csharp','dotnet','go','python']:
    try:
        canon = normalise_language(raw)
        try:
            adapter = create_scip_adapter(canon)
            print(raw, '->', canon, '->', type(adapter).__name__)
        except Exception as e:
            print(raw, '->', canon, '-> FACTORY_ERROR:', type(e).__name__, e)
    except Exception as e:
        print(raw, '-> NORMALISE_ERROR:', type(e).__name__, e)
PY

uv run ruff check src/fs2/core/adapters/scip_adapter.py src/fs2/core/adapters/scip_adapter_dotnet.py src/fs2/core/adapters/scip_adapter_fake.py src/fs2/core/adapters/scip_adapter_go.py src/fs2/core/adapters/scip_adapter_python.py src/fs2/core/adapters/scip_adapter_typescript.py tests/unit/adapters/test_scip_adapter.py tests/unit/adapters/test_scip_adapter_dotnet.py tests/unit/adapters/test_scip_adapter_go.py tests/unit/adapters/test_scip_adapter_typescript.py

uv run python -m pytest -q tests/unit/adapters/test_scip_adapter.py tests/unit/adapters/test_scip_adapter_typescript.py tests/unit/adapters/test_scip_adapter_go.py tests/unit/adapters/test_scip_adapter_dotnet.py
```

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: `REQUEST_CHANGES`

**Plan**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-plan.md`
**Spec**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-spec.md`
**Phase**: `Phase 2: Multi-Language Adapters`
**Tasks dossier**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-2-multi-language-adapters/tasks.md`
**Execution log**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-2-multi-language-adapters/execution.log.md`
**Review file**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-2-multi-language-adapters/reviews/review.phase-2-multi-language-adapters.md`

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/.chainglass/data/activity-log.jsonl` | modified | out-of-scope tracked artifact | Remove from phase diff (F002) |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-2-multi-language-adapters/execution.log.md` | created | phase artifact | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-2-multi-language-adapters/tasks.fltplan.md` | modified | phase artifact | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-2-multi-language-adapters/tasks.md` | modified | phase artifact | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/scripts/scip/fixtures/dotnet/index.scip` | created | fixtures | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/scripts/scip/fixtures/go/index.scip` | created | fixtures | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/scripts/scip/fixtures/typescript/index.scip` | created | fixtures | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/scip_adapter.py` | modified | core/adapters | Fix alias/factory contract and add regression coverage (F001) |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/scip_adapter_dotnet.py` | created | core/adapters | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/scip_adapter_fake.py` | modified | core/adapters | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/scip_adapter_go.py` | created | core/adapters | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/scip_adapter_python.py` | modified | core/adapters | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/scip_adapter_typescript.py` | created | core/adapters | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_scip_adapter.py` | modified | tests | Add direct factory coverage for `js`/`javascript` success path (F001) |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_scip_adapter_dotnet.py` | created | tests | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_scip_adapter_go.py` | created | tests | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_scip_adapter_typescript.py` | created | tests | None |

### Required Fixes (if REQUEST_CHANGES)

| # | File (absolute path) | What To Fix | Why |
|---|---------------------|-------------|-----|
| 1 | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/scip_adapter.py` and `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_scip_adapter.py` | Make accepted aliases resolve to constructible adapters and add regression tests for the `js`/`javascript` path. | AC13 currently fails in practice because `js` canonicalises to unsupported `javascript`. |
| 2 | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/.chainglass/data/activity-log.jsonl` | Remove or split the tracked telemetry file out of the Phase 2 diff. | The file is outside the declared Phase 2 scope and breaks the in-scope/orphan-file checks. |

### Domain Artifacts to Update (if any)

| File (absolute path) | What's Missing |
|---------------------|----------------|
| *(none)* | No `docs/domains` artifacts exist in this repository; no domain-document update is required for the recommended FT-001 remediation. |

### Next Step

`/plan-6-v2-implement-phase --plan /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-plan.md --phase 'Phase 2: Multi-Language Adapters'`
