# Review Report — Phase 3: Core Service Implementation

**Plan**: `/workspaces/flow_squared/docs/plans/008-smart-content/smart-content-plan.md`  
**Phase Dossier**: `/workspaces/flow_squared/docs/plans/008-smart-content/tasks/phase-3-core-service-implementation/tasks.md`  
**Execution Log**: `/workspaces/flow_squared/docs/plans/008-smart-content/tasks/phase-3-core-service-implementation/execution.log.md`  
**Diff Basis**: `HEAD (9e22dd0) -> working tree + untracked files`  

## A) Verdict

**REQUEST_CHANGES**

Blocking issues are primarily **graph integrity / provenance** (broken bidirectional links and unsynced footnote stubs) plus an **out-of-scope file** in the diff.

## B) Summary

- Implementation largely matches Phase 3 brief (SmartContentService + tests) and unit tests pass (`671 passed`).
- **Graph integrity is broken**: Phase 3 execution log does not follow the Phase 1 anchor/metadata pattern, so plan links likely do not resolve.
- **Footnote synchronization is broken**: dossier “Phase Footnote Stubs” are not synced to the plan ledger and tasks do not reference footnotes/log anchors.
- One **out-of-scope** change (`.claude/settings.local.json`) appears unrelated to Phase 3 deliverables.

## C) Checklist

**Testing Approach: Full TDD**  
**Mock Usage: Targeted mocks**

- [x] Tests exist for AC5/6/8/9/10/13 and service behavior
- [x] Test docs include Purpose / Quality Contribution / Acceptance Criteria (18/18)
- [x] Mock policy aligns (fakes used; no mocking frameworks detected)
- [x] Unit tests pass (see Section G)
- [ ] Tests precede code (RED→GREEN evidence exists in log, but cannot be verified in git history since changes are uncommitted)
- [ ] Graph integrity links (Task↔Log, Task↔Footnote, Plan↔Dossier) intact
- [ ] Only in-scope files changed

## D) Findings Table

| ID | Severity | File:Lines | Summary | Recommendation |
|----|----------|------------|---------|----------------|
| F-001 | CRITICAL | `docs/plans/008-smart-content/tasks/phase-3-core-service-implementation/execution.log.md:38` | Execution log missing stable `{#...}` anchors + required metadata/backlinks, breaking Task↔Log navigation | Add `{#task-...}` anchors + Dossier/Plan task metadata per Phase 1 log conventions |
| F-002 | CRITICAL | `docs/plans/008-smart-content/tasks/phase-3-core-service-implementation/tasks.md:163` | Dossier tasks lack `log#anchor` and `[^N]` links in Notes column for completed tasks | Add per-task log anchor links + footnote tags aligned to plan ledger |
| F-003 | CRITICAL | `docs/plans/008-smart-content/tasks/phase-3-core-service-implementation/tasks.md:478` | Dossier “Phase Footnote Stubs” not synchronized to Plan §9 ledger (missing node IDs; missing `[^27]`) | Sync stubs to match plan ledger; ensure sequential + complete |
| F-004 | HIGH | `.claude/settings.local.json:1` | Out-of-scope file modified for Phase 3 | Revert/remove from diff or justify + add provenance |
| F-005 | MEDIUM | `src/fs2/core/services/smart_content/smart_content_service.py:153` | TokenCounter adapter failures would leak adapter-layer exception across service boundary | Catch `TokenCounterError` and raise `SmartContentProcessingError` with node context; add a unit test |
| F-006 | LOW | `tests/unit/services/test_smart_content_service.py:1` | Test file header says “RED - SmartContentService does not exist yet” but service exists | Update header to avoid confusion |

## E) Detailed Findings

### E.0 Cross-Phase Regression Analysis

**Result: PASS**

- Re-ran prior-phase unit suite against current working tree: `671 passed`.
- No new failures observed; no evidence of breaking prior phase contracts in the touched modules.

### E.1 Doctrine & Testing Compliance

**Graph Integrity Verdict: ❌ BROKEN** (requires changes before merge)

**F-001 (CRITICAL) — Task↔Log links broken**
- **Observed**: Phase 3 execution log headings omit the Phase 1-style `{#task-...}` anchors (e.g., compare Phase 1 headings with explicit IDs vs. Phase 3 at `execution.log.md:38`).
- **Observed**: Phase 3 log entries also omit required metadata blocks (e.g., `**Dossier Task**`, `**Plan Task**`, and backlinks) used by the Task↔Log validator.
- **Impact**: Plan links like `smart-content-plan.md:782` will not reliably resolve to evidence; traversal across Plan↔Dossier↔Log is brittle.
- **Fix**: Apply the Phase 1 execution log heading format and include metadata/backlinks for each task section.

**F-002 (CRITICAL) — Task↔Footnote & Task↔Log missing in dossier tasks table**
- **Observed**: Phase 3 dossier tasks table (`tasks.md:163`) has completed tasks but Notes do not include required `log#anchor` links nor `[^N]` footnote tags.
- **Impact**: Cannot navigate from a task row to evidence (log) or provenance (footnote ledger).
- **Fix**: Add `log#...` + `[^20]`… references per row; ensure the anchors match actual log IDs.

**F-003 (CRITICAL) — Plan authority conflicts / unsynced footnote stubs**
- **Observed**: Plan ledger defines Phase 3 footnotes `[^20]`–`[^27]` with node IDs (`smart-content-plan.md:1544`), but dossier “Phase Footnote Stubs” are empty placeholders and omit `[^27]` (`tasks.md:478`).
- **Authority**: Plan §9 ledger is primary; dossier stubs must be derived and synced.
- **Impact**: File→Footnote→Task provenance traversal is broken.
- **Fix**: Populate dossier stubs with the same numbers + node IDs/descriptions as plan ledger; add missing `[^27]`.

**TDD & Mock Policy**
- **TDD evidence**: Execution log includes explicit RED failing test evidence followed by GREEN passing evidence; unit suite passes.
- **Mock policy**: Targeted mocks honored; fakes used; no mocking framework usage detected in the Phase 3 test file.

### E.2 Semantic Analysis (Spec Alignment)

- AC5/AC6 behavior implemented via `SmartContentService._should_skip()` and setting `smart_content_hash` on success (`src/fs2/core/services/smart_content/smart_content_service.py:86`).
- AC13 implemented by token counting + truncation marker + WARNING logging (`src/fs2/core/services/smart_content/smart_content_service.py:153`).
- AC8 context variables are satisfied in practice because `TemplateService.render_for_category()` injects `max_tokens` if not provided.

### E.3 Quality & Safety Analysis

**Safety Score: 90/100** (CRITICAL: 0, HIGH: 0, MEDIUM: 1, LOW: 1)  
**Verdict: APPROVE (code safety)** — separate from the overall merge verdict, which is blocked by graph/provenance issues.

- **[MEDIUM]** `src/fs2/core/services/smart_content/smart_content_service.py:153`: token counter failures are not translated to service-layer errors (exception layering drift).
- **[LOW]** `tests/unit/services/test_smart_content_service.py:1`: stale header comment.

## F) Coverage Map (Acceptance Criteria ↔ Tests)

Overall coverage confidence: **100%** (explicit IDs/criteria in test docblocks + behavioral match)

| AC | Confidence | Test(s) | Notes |
|----|------------|---------|------|
| AC5 | 100% | `tests/unit/services/test_smart_content_service.py:test_given_matching_hash_when_processing_then_skips_llm_call` | Explicit AC5 mention + asserts no LLM calls |
| AC6 | 100% | `tests/unit/services/test_smart_content_service.py:test_given_mismatched_hash_when_processing_then_regenerates`, `...:test_given_none_smart_content_hash_when_processing_then_generates` | Explicit AC6 mention + asserts regeneration + hash update |
| AC8 | 100% | `tests/unit/services/test_smart_content_service.py:test_given_node_when_processing_then_renders_correct_context` | Verifies TemplateService context contract |
| AC9 | 100% | `tests/unit/services/test_smart_content_service.py:test_given_service_when_constructed_then_extracts_config_internally` | Verifies DI + `config.require()` extraction |
| AC10 | 100% | `tests/unit/services/test_smart_content_service.py:test_integration_end_to_end_with_fake_llm` | Verifies FakeLLMAdapter integration and prompt capture |
| AC13 | 100% | `tests/unit/services/test_smart_content_service.py:test_given_large_content_when_processing_then_truncates_with_marker` | Verifies truncation marker in prompt + WARNING logged |

## G) Commands Executed

```bash
git status --porcelain=v1
git diff --name-only

UV_CACHE_DIR=/workspaces/flow_squared/.uv_cache uv run pytest tests/unit/services/test_smart_content_service.py -q
UV_CACHE_DIR=/workspaces/flow_squared/.uv_cache uv run pytest tests/unit -q
```

## H) Decision & Next Steps

- Apply `docs/plans/008-smart-content/reviews/fix-tasks.phase-3-core-service-implementation.md`.
- Re-run `/plan-6` for Phase 3 to regenerate artifacts with correct anchors/links and then re-run `/plan-7`.

## I) Footnotes Audit (Diff Paths ↔ Footnote Tags ↔ Node IDs)

| Diff Path | Footnote Tag(s) | Example Node ID(s) (Plan Ledger) |
|----------|------------------|-----------------------------------|
| `src/fs2/core/services/smart_content/smart_content_service.py` | [^21] [^22] [^23] [^24] [^25] | `class:src/fs2/core/services/smart_content/smart_content_service.py:SmartContentService` |
| `tests/unit/services/test_smart_content_service.py` | [^20] [^26] | `file:tests/unit/services/test_smart_content_service.py` |
| `src/fs2/core/models/code_node.py` | [^27] | `field:src/fs2/core/models/code_node.py:CodeNode.smart_content_hash` |
| `src/fs2/core/adapters/llm_adapter_fake.py` | [^27] | `method:src/fs2/core/adapters/llm_adapter_fake.py:FakeLLMAdapter.set_delay` |
| `src/fs2/core/services/smart_content/__init__.py` | [^21] | `file:src/fs2/core/services/smart_content/__init__.py` |
| `.claude/settings.local.json` | (missing) | (missing) |

