# Code Review: Phase 2: Layout + Rendering — Treemap, Sigma.js, Cosmos Theme

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/reports-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/reports-spec.md
**Phase**: Phase 2: Layout + Rendering — Treemap, Sigma.js, Cosmos Theme
**Date**: 2026-03-15
**Reviewer**: Automated (plan-7-v2)
**Testing Approach**: Hybrid

## A) Verdict

**REQUEST_CHANGES**

Phase-complete claims outpace the evidence captured for this phase: the committed implementation still ships straight arrow edges while AC10 is marked done, and the browser/performance acceptance criteria are checked off without the manual or benchmark evidence the spec requires.

**Key failure areas**:
- **Reinvention**: `report_layout.py` duplicates directory-hierarchy construction already available in `TreeService`, and `graph-viewer.js` reintroduces a JS category-color map after the phase centralized colors in Python.
- **Testing**: Visual/browser and performance ACs are marked complete without browser or benchmark evidence, and AC10 is contradicted by the implementation.

## B) Summary

The committed source diff is structurally sound: focused service/layout tests pass, the CLI report suite passes, `ruff check` passes on the touched Python files, and no material correctness, security, or architecture defects surfaced in the code review. Domain and doctrine checks are effectively clean; this repository has no `docs/domains/` or `docs/project-rules/` governance set to enforce, and the changed code stays within the existing clean-architecture boundaries.

The review blocks on evidence and contract alignment instead. Phase artifacts mark AC10, AC19, AC20, AC22, and AC23 as complete, but the execution log does not retain browser observations, screenshots, timings, or FPS measurements, and the code still renders straight arrows with no curve/glow support. Two medium reinvention issues also remain around folder-hierarchy reuse and duplicated category-color ownership.

## C) Checklist

**Testing Approach: Hybrid**

- [ ] TDD evidence retained for promised layout/service work
- [x] Focused unit and CLI validation tests present
- [ ] Visual/manual verification steps recorded for browser-rendered behavior
- [ ] 5K and 50K performance benchmark evidence recorded

Universal (all approaches):
- [x] Only in-scope files changed
- [x] Linters/type checks clean (if applicable)
- [x] Domain compliance checks pass

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | HIGH | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/static/reports/graph-viewer.js:121-129 | testing/evidence | AC10 is checked off, but the implementation still renders straight arrow edges with no curve/glow support. | Either implement curved/glow reference edges or explicitly defer AC10 and stop marking it complete in phase artifacts. |
| F002 | HIGH | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/execution.log.md:72-77 | testing/evidence | AC19 and AC20 are marked complete without any recorded 5K/50K benchmark timings or FPS evidence. | Run reproducible browser benchmarks and log commands, environment, timings, and observations. |
| F003 | HIGH | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/execution.log.md:72-77 | testing/evidence | AC2, AC22, and AC23 are marked complete without browser-specific visual evidence, screenshots, or observed outcomes. | Open a generated report in the target browsers and record the observed offline render, theme, and font behavior. |
| F004 | MEDIUM | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/report_service.py:349-358 | scope/evidence | T009 says all vendored assets are embedded, but `_render_template()` does not inline `graphology-layout-forceatlas2.min.js`. | Either embed ForceAtlas2 in the template or correct the task/log wording and add an assertion for the actual embedded asset set. |
| F005 | MEDIUM | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/report_layout.py:47-67 | reinvention/pattern | `report_layout._build_dir_tree()` reimplements folder-tree construction the task dossier explicitly said to reuse from `TreeService`. | Extract or reuse a shared folder-hierarchy helper so one service owns the file-path tree logic. |
| F006 | MEDIUM | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/static/reports/graph-viewer.js:56-72 | reinvention/pattern | `graph-viewer.js` reintroduces a JS `catColors` map even though the phase declared Python the single source of truth for category colors. | Derive legend colors from serialized node data or a single emitted color contract instead of hard-coding a second map. |
| F007 | MEDIUM | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/execution.log.md:13-18 | testing/evidence | The phase claims TDD for layout/service work, but the retained evidence shows GREEN-only pass counts and no failing-first trace. | Capture RED→GREEN evidence in future execution logs or preserve it in separate commits/log entries. |
| F008 | LOW | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/execution.log.md:75-77 | testing/evidence | The final execution-log summary claims full-suite, lint, and generation success without pasted command output or artifact paths. | Append exact commands and summarized output so each claim is traceable. |

## E) Detailed Findings

### E.1) Implementation Quality

Subagent result: no material correctness, security, error-handling, performance, or scope defects were found in the committed source diff.

Validation rerun during review:
- `uv run python -m pytest -q tests/unit/services/test_report_layout.py tests/unit/services/test_report_service.py` → `31 passed`
- `uv run python -m pytest -q --override-ini='addopts=' tests/unit/cli/test_report_cli.py` → `8 passed`
- `uv run ruff check src/fs2/core/services/report_layout.py src/fs2/core/services/report_service.py tests/unit/services/test_report_layout.py tests/unit/services/test_report_service.py` → clean

### E.2) Domain Compliance

Repository note: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/` and `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/project-rules/` do not exist in this repo, so domain validation used the plan's Domain Manifest plus the repo's AGENTS/CLAUDE clean-architecture guidance.

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | New source files land under `/src/fs2/core/services/`, `/src/fs2/core/static/reports/`, and `/tests/unit/services/` exactly where the phase dossier placed them. |
| Contract-only imports | ✅ | `report_service.py` consumes config service, `GraphStore`, and `CodeNode`; no cross-domain internal imports were introduced. |
| Dependency direction | ✅ | The diff preserves clean-architecture flow: services depend on abstractions/models and static assets remain passive resources. |
| Domain.md updated | ✅ | No `docs/domains/<slug>/domain.md` system exists in this repository, so there was nothing governance-specific to update. |
| Registry current | ✅ | No `/docs/domains/registry.md` file exists. |
| No orphan files | ✅ | All substantive product files map cleanly to services/static-assets/templates/tests. Planning artifacts were treated as workflow output, not domain-owned source. |
| Map nodes current | ✅ | No `/docs/domains/domain-map.md` exists to maintain. |
| Map edges current | ✅ | No domain-map edge catalog exists to maintain. |
| No circular business deps | ✅ | The diff adds no new cross-business domain edges or cycles. |
| Concepts documented | N/A | No domain docs/contract registry exists, so concepts-table validation is not applicable. |

### E.3) Anti-Reinvention

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| `report_layout.py` directory-tree builder | `TreeService._compute_folder_hierarchy()` already owns file-path tree construction at `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/tree_service.py:436-470` | services | ⚠️ Extend/reuse shared helper |
| `graph-viewer.js` legend color map | `_CATEGORY_COLORS` already centralizes category colors at `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/report_service.py:47-58` | services/static-assets | ⚠️ Reuse single source |
| `graph-viewer.css` Cosmos theme | None | static-assets | ✅ Proceed |
| Vendored Sigma/Graphology assets | None | static-assets | ✅ Proceed |

### E.4) Testing & Evidence

**Coverage confidence**: 53%

Violations synthesized from the testing validator:
- **HIGH**: Visual/browser ACs are marked complete without browser versions, screenshots, or observed outcomes.
- **HIGH**: AC19/AC20 performance claims are marked complete without 5K/50K benchmark data.
- **HIGH**: AC10 is marked complete even though the implementation ships straight arrows and no glow.
- **MEDIUM**: TDD claims are not reviewable from retained evidence.
- **MEDIUM**: T009 overstates embedded assets; ForceAtlas2 is vendored but not inlined.
- **LOW**: Final execution-log claims are not backed by pasted command output or artifact paths.

| AC | Confidence | Evidence |
|----|------------|----------|
| AC2 | 50 | Static proof only: the template inlines data/CSS/JS/fonts and no external `src`/`href` URLs are present; CLI report tests pass, but no logged browser observations exist. |
| AC7 | 85 | Focused layout/service tests pass and cover empty/single/single-dir/multi-dir/deep-nesting/determinism/mixed-category/canvas cases. |
| AC8 | 78 | `_CATEGORY_COLORS` is defined in Python and focused tests assert callable/type/file colors; section/folder colors remain unasserted. |
| AC9 | 88 | Layout tests verify the log size formula and service tests verify `size` is emitted into report JSON. |
| AC10 | 10 | `_serialize_edge()` and `graph-viewer.js` emit straight `arrow` edges only; no curve/glow implementation or browser evidence exists. |
| AC19 | 5 | No 5K-node render-time or FPS benchmark was found in the diff or execution log. |
| AC20 | 0 | No 50K-node benchmark evidence was found. |
| AC21 | 88 | Service tests cover threshold/no-threshold clustering behavior and preservation of file nodes. |
| AC22 | 60 | Static CSS matches the Cosmos palette, but there is no browser-recorded visual validation. |
| AC23 | 65 | Inline `@font-face` data URIs and vendored woff2 assets exist, but no browser evidence shows embedded fonts winning over fallback. |

### E.5) Doctrine Compliance

N/A — no `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/project-rules/*.md` files were found. Against the repo's AGENTS/CLAUDE guidance, the diff still respects the documented layer boundaries and interface-driven service composition.

### E.6) Harness Live Validation

N/A — no harness configured (`/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/project-rules/harness.md` is absent).

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC2 | Self-contained HTML renders without external dependencies | Template embeds graph JSON, JS, CSS, and fonts inline; CLI report suite passes; no browser-recorded observations. | 50 |
| AC7 | Treemap layout positions all nodes | `test_report_layout.py` and `test_report_service.py` pass with deterministic/canvas/layout coverage. | 85 |
| AC8 | Nodes are colored by category | Python `_CATEGORY_COLORS` map is applied during serialization; focused color assertions pass. | 78 |
| AC9 | Node size scales logarithmically with line count | Layout tests verify min/large/capped size behavior and service tests confirm size emission. | 88 |
| AC10 | Cross-file reference edges are curved amber lines with subtle glow | Code emits straight arrows only; no curve/glow renderer or visual evidence exists. | 10 |
| AC19 | 5K nodes render in <2s and maintain 60fps | No benchmark or FPS trace exists. | 5 |
| AC20 | 50K nodes render in <5s and maintain 30fps | No benchmark or FPS trace exists. | 0 |
| AC21 | Clustering kicks in above `--max-nodes` | Threshold clustering tests pass and metadata exposes `clustered`. | 88 |
| AC22 | Cosmos dark theme is rendered correctly | CSS values match the intended palette; browser verification is missing. | 60 |
| AC23 | Embedded Inter + JetBrains Mono fonts are actually used | Inline font data URIs exist, but no browser confirmation of rendered typography exists. | 65 |

**Overall coverage confidence**: 53%

## G) Commands Executed

```bash
git --no-pager diff --stat
git --no-pager diff --staged --stat
git --no-pager status --short
git --no-pager log --oneline -12
mkdir -p docs/plans/033-reports/tasks/phase-2-layout-rendering/reviews && PHASE_COMMIT=b13c6fb && BASE_COMMIT=$(git rev-parse ${PHASE_COMMIT}^) && git --no-pager diff --binary --find-renames ${BASE_COMMIT}..${PHASE_COMMIT} > docs/plans/033-reports/tasks/phase-2-layout-rendering/reviews/_computed.diff && git --no-pager diff --name-status ${BASE_COMMIT}..${PHASE_COMMIT} && git --no-pager diff --numstat ${BASE_COMMIT}..${PHASE_COMMIT}
uv run python -m pytest -q tests/unit/services/test_report_layout.py tests/unit/services/test_report_service.py
uv run python -m pytest -q --override-ini='addopts=' tests/unit/cli/test_report_cli.py
uv run ruff check src/fs2/core/services/report_layout.py src/fs2/core/services/report_service.py tests/unit/services/test_report_layout.py tests/unit/services/test_report_service.py
```

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: REQUEST_CHANGES

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/reports-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/reports-spec.md
**Phase**: Phase 2: Layout + Rendering — Treemap, Sigma.js, Cosmos Theme
**Tasks dossier**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/tasks.md
**Execution log**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/execution.log.md
**Review file**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/reviews/review.phase-2-layout-rendering.md

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/execution.log.md | A | planning-docs | Yes |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/tasks.fltplan.md | A | planning-docs | No |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/tasks.md | A | planning-docs | Yes |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/report_layout.py | A | services | Yes |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/report_service.py | M | services | Yes |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/static/reports/graph-viewer.css | A | static-assets | No |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/static/reports/graph-viewer.js | A | static-assets | Yes |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/static/reports/graphology-layout-forceatlas2.min.js | A | static-assets | Yes |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/static/reports/graphology.min.js | A | static-assets | No |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/static/reports/inter-latin.woff2 | A | static-assets | No |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/static/reports/jetbrains-mono-latin.woff2 | A | static-assets | No |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/static/reports/sigma.min.js | A | static-assets | No |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/templates/reports/codebase_graph.html.j2 | M | templates | Yes |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_report_layout.py | A | tests | No |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_report_service.py | M | tests | No |

### Required Fixes (if REQUEST_CHANGES)

| # | File (absolute path) | What To Fix | Why |
|---|---------------------|-------------|-----|
| 1 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/report_service.py<br>/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/static/reports/graph-viewer.js<br>/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/reports-plan.md<br>/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/tasks.md<br>/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/execution.log.md | Align AC10 with reality: either implement curved/glow reference rendering or formally defer it and clear all `[x]`/"complete" claims. | The current code emits straight arrows only, while the phase artifacts still claim curved/glow edges shipped. |
| 2 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/execution.log.md | Add browser/manual evidence for AC2, AC22, and AC23 (browser name/version, offline behavior, theme verification, font verification, screenshots or equivalent artifact paths). | The spec requires visual acceptance for browser-rendered behavior, and the current log has no traceable observations. |
| 3 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/execution.log.md | Add reproducible 5K/50K benchmark evidence for AC19 and AC20. | Performance ACs are checked off without measured timings or FPS. |
| 4 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/report_layout.py | Remove the duplicated folder-tree builder by reusing or extracting the `TreeService` folder-hierarchy logic. | The phase dossier explicitly pointed at existing hierarchy logic, but the phase introduced a second implementation. |
| 5 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/static/reports/graph-viewer.js | Remove the hard-coded JS `catColors` legend map and derive colors from serialized node data or one emitted contract. | The phase declared Python as the single source of truth for category colors. |
| 6 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/report_service.py<br>/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/templates/reports/codebase_graph.html.j2<br>/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/tasks.md<br>/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/execution.log.md | Either embed the vendored ForceAtlas2 asset or stop claiming that all vendored assets are inlined in Phase 2. | The task/log wording currently overstates what `_render_template()` actually embeds. |

### Domain Artifacts to Update (if any)

| File (absolute path) | What's Missing |
|---------------------|----------------|
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/reports-plan.md | AC10/AC19/AC20 completion state may need alignment if Phase 2 remains straight-arrow-only; Domain Manifest font filenames are also slightly stale (`inter.woff2`/`jetbrains-mono.woff2` vs `*-latin.woff2`). |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/tasks.md | T009 asset-embedding note still mentions `{{ force_atlas_js }}` and DYK-08 says JS should not own a second color map. |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-2-layout-rendering/execution.log.md | Browser/manual evidence, benchmark evidence, exact command output, and corrected asset-embedding statement. |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/reports-spec.md | Update only if AC10 is formally re-scoped out of Phase 2 rather than implemented. |

### Next Step

/plan-6-v2-implement-phase --plan /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/reports-plan.md --phase 'Phase 2: Layout + Rendering — Treemap, Sigma.js, Cosmos Theme'
