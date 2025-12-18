# Review Report — Phase 2: Template System

**Plan**: `docs/plans/008-smart-content/smart-content-plan.md`  
**Phase Dossier**: `docs/plans/008-smart-content/tasks/phase-2-template-system/tasks.md`  
**Execution Log**: `docs/plans/008-smart-content/tasks/phase-2-template-system/execution.log.md`  
**Diff Basis**: Working tree vs `HEAD` (tracked `git diff` + untracked files limited to Phase 2 dossier paths; canonical diff snapshot: `.tmp/review.phase-2-template-system.unified.diff`)  
**Testing Approach (from plan)**: Full TDD  
**Mock Policy (from plan)**: Targeted mocks (fakes over mocks)  

## A) Verdict

**REQUEST_CHANGES**

Blocking reasons:
1) **Graph integrity broken (Task↔Log / Plan↔Log)**: Phase 2 `execution.log.md` headings do not contain the `{#...}` anchors referenced by the plan and dossier, so evidence links are non-functional.
2) **Testing doctrine drift (tests-as-docs)**: Phase 2 tests do not meet the plan’s required per-test docstring fields (`Acceptance Criteria:` missing everywhere in `tests/unit/services/test_template_service.py`).

## B) Summary (≤10 lines)

- Implementation appears aligned with the Phase 2 brief: `TemplateService` loads templates via `importlib.resources`, uses `jinja2.DictLoader`, enforces strict undefined, and resolves `max_tokens` from `SmartContentConfig.token_limits`.
- Scope guard passes: diff touches only Phase 2 listed paths plus planning artifacts under `docs/plans/008-smart-content/`.
- Unit tests and ruff checks pass locally; full unit suite passes when `UV_CACHE_DIR` is set (see Commands Executed).
- Merge is blocked on documentation graph integrity (broken anchors) and missing test documentation fields required by the plan.

## C) Checklist (Testing Strategy–Aware)

**Testing Approach: Full TDD** · **Mock Usage: Targeted mocks**

- [~] Tests precede code (cannot verify via git history because work is uncommitted; relies on execution log narrative)
- [~] RED/GREEN/REFACTOR evidence present per task (evidence blocks exist, but Phase 2 log format is not linkable; see Findings)
- [!] Tests-as-docs: per-test docstrings include `Purpose`, `Quality Contribution`, `Acceptance Criteria` (missing `Acceptance Criteria` in all Phase 2 tests)
- [x] Mock policy followed (no `unittest.mock` / patch frameworks introduced; fakes used where needed)
- [x] Negative/edge cases included (missing required context var raises `TemplateError`)
- [!] Graph integrity links intact (Task↔Log / Plan↔Log anchors broken)
- [x] Only in-scope files changed
- [x] Linters/type checks are clean for touched files (ruff)

## D) Findings Table

| ID | Severity | File:Lines | Summary | Recommendation |
|----|----------|------------|---------|----------------|
| F-001 | CRITICAL | `docs/plans/008-smart-content/tasks/phase-2-template-system/execution.log.md:1` | Plan/dossier links reference `#task-...` anchors that do not exist in Phase 2 execution log headings | Add `{#task-...}` anchors to each `## Task T00X:` heading and restore Phase 1-style metadata lines so Task↔Log and Plan↔Log become navigable |
| F-002 | HIGH | `tests/unit/services/test_template_service.py:1` | Phase 2 tests violate plan “Test Documentation” requirement: all 8 tests omit `Acceptance Criteria:` in their docstrings | Update each test docstring to include `Acceptance Criteria:` (plus keep Purpose/Quality); optionally include AC IDs (AC8/AC11) explicitly |
| F-003 | LOW | `tests/unit/services/test_template_service.py:1` | File header still claims “TDD Phase: RED” although tests are now GREEN | Update module docstring to reflect current state (or remove the “RED” claim) |

## E) Detailed Findings

### E.0 Cross-Phase Regression Analysis

**Verdict**: PASS

- Prior phase(s) affected: Phase 1 (Foundation & Infrastructure)
- Tests re-run against current code state: `just test-unit` (with `UV_CACHE_DIR`) → **653 passed**
- Contracts/interfaces: no breaking changes detected for Phase 1 public surfaces used by Phase 2 (`SmartContentConfig`, `TemplateError`)

### E.1 Doctrine & Testing Compliance

#### Graph Integrity (Step 3a)

**Verdict**: ❌ BROKEN (blocking)

Broken edges:
- **Task↔Log**: Dossier task rows include `log#task-...` anchors, but Phase 2 `execution.log.md` headings do not define `{#task-...}` anchors.
- **Plan↔Log**: Plan Phase 2 progress table links to `execution.log.md#task-...`; these anchors are absent, so plan links are also broken.

Minimum repair target (match Phase 1 style):
- Use heading form: `## Task T00X: <title> {#task-...}`
- Include metadata block lines (at least): `**Dossier Task**`, `**Plan Task**`, `**Plan Reference**`, `**Dossier Reference**`

#### Authority Conflicts (Step 3c)

**Verdict**: PASS (no plan-vs-dossier conflicts detected for Phase 2 footnotes)

- Plan § “Change Footnotes Ledger” contains [^12]–[^19] entries covering the Phase 2 code/test/template paths.
- Phase 2 “Phase Footnote Stubs” include [^12]–[^19]. (Note: [^18] uses a glob `*.j2` in Affects; acceptable as a shorthand, but ensure all six template files remain covered by this stub.)

#### TDD Doctrine (Step 4)

**Blocking**:
- Plan requires per-test docstrings include `Acceptance Criteria:`; Phase 2 `tests/unit/services/test_template_service.py` omits it in all 8 tests.

Advisory:
- The execution log includes failing→passing evidence blocks, but without the Phase 1 metadata + anchors it is not “bidirectionally linkable” per the graph rules.

#### Mock Usage (Step 4)

**Verdict**: PASS

- No `unittest.mock` / patch frameworks introduced in Phase 2 tests.
- Tests use `FakeConfigurationService` + config objects, consistent with “Targeted mocks (fakes over mocks)”.

#### Testing Evidence & Coverage Alignment (Step 5)

Evidence artifacts declared in Phase 2 dossier exist:
- `docs/plans/008-smart-content/tasks/phase-2-template-system/execution.log.md`
- `docs/plans/008-smart-content/tasks/phase-2-template-system/tasks.md`

Coverage mapping for Phase 2-relevant acceptance criteria:
- AC8 (context vars): covered by `test_given_required_context_vars_when_rendering_then_all_ac8_vars_are_supported` and `test_given_missing_required_context_var_when_rendering_then_raises_template_error` → **75%** (behavioral + mentions “AC8”, but no explicit “AC8” ID in the test name/docstring fields)
- AC11 (category→template mapping): covered by `test_given_category_when_resolving_template_then_matches_ac11_mapping` → **75%** (behavioral + mentions “AC11”, but no explicit “AC11” ID in the required Acceptance Criteria docstring field)
- AC4 (token limits by category): covered by `test_given_category_when_resolving_max_tokens_then_uses_smart_content_config_defaults` → **50–75%** (behavioral match; consider explicitly referencing AC4 in the test docstring)

Overall Phase 2 coverage confidence (for Phase 2-scoped ACs): **~75%** (improvable via explicit AC IDs in test docstrings/names).

### E.2 Semantic Analysis (Spec/Plan Alignment)

No semantic mismatches found for Phase 2 scope:
- Template loading is package-safe (uses `importlib.resources` instead of filesystem paths).
- Category mapping matches spec AC11 table for all 9 categories.
- `max_tokens` is config-driven via `SmartContentConfig.token_limits`.
- Missing render context fails closed via strict undefined, surfaced as service-layer `TemplateError`.

### E.3 Quality & Safety Analysis

**Correctness**: No defects found in TemplateService API behavior given existing tests.  
**Security**: No path traversal / injection / secret leakage issues identified (templates are local package resources).  
**Performance**: Template loading is bounded to six required templates; no unbounded scans.  
**Observability**: No logging added in Phase 2 (acceptable at this layer); Phase 3 orchestration should add structured logs on prompt generation failures.  

## F) Coverage Map (Acceptance Criteria ↔ Tests)

Confidence scale: 100% explicit ID, 75% behavioral match, 50% inferred, 0% unclear.

| Criterion | Evidence | Test(s) | Confidence |
|----------|----------|---------|------------|
| AC8 (Template Context Variables) | Rendered output includes all required context fields; missing field raises `TemplateError` | `tests/unit/services/test_template_service.py` (`test_given_required_context_vars_when_rendering_then_all_ac8_vars_are_supported`, `test_given_missing_required_context_var_when_rendering_then_raises_template_error`) | 75% |
| AC11 (Category-to-Template Mapping) | Category→template mapping matches spec table (specialized + fallback) | `tests/unit/services/test_template_service.py` (`test_given_category_when_resolving_template_then_matches_ac11_mapping`) | 75% |
| AC4 (Token Limits by Category) | Max tokens resolved from `SmartContentConfig.token_limits` | `tests/unit/services/test_template_service.py` (`test_given_category_when_resolving_max_tokens_then_uses_smart_content_config_defaults`) | 75% |

## G) Commands Executed (copy/paste)

- Canonical diff snapshot used for review (tracked + Phase 2-scoped untracked files): `.tmp/review.phase-2-template-system.unified.diff`
- `UV_CACHE_DIR=/workspaces/flow_squared/.uv_cache uv run pytest -q tests/unit/services/test_template_service.py`
- `UV_CACHE_DIR=/workspaces/flow_squared/.uv_cache uv run ruff check src/fs2/core/services/smart_content/template_service.py tests/unit/services/test_template_service.py`
- `just test-unit` (fails in this environment without `UV_CACHE_DIR` due to uv cache permission)
- `UV_CACHE_DIR=/workspaces/flow_squared/.uv_cache just test-unit`

## H) Decision & Next Steps

- Fix the blocking items in `docs/plans/008-smart-content/reviews/fix-tasks.phase-2-template-system.md`.
- Re-run the Phase 2 validation commands listed in the dossier (and above).
- Re-run `plan-7-code-review` for Phase 2 after fixes; if graph integrity and test-doc doctrine are clean, this phase should be mergeable.

## I) Footnotes Audit (Diff Paths ↔ Footnote Tags ↔ Node IDs)

| Diff Path | Footnote Tag(s) | Plan Ledger Node IDs (summary) |
|----------|------------------|--------------------------------|
| `pyproject.toml` | `[^12]` | `file:pyproject.toml` |
| `uv.lock` | `[^12]` | `file:uv.lock` |
| `src/fs2/core/templates/__init__.py` | `[^13]` | `file:src/fs2/core/templates/__init__.py` |
| `src/fs2/core/templates/smart_content/__init__.py` | `[^13]` | `file:src/fs2/core/templates/smart_content/__init__.py` |
| `src/fs2/core/services/smart_content/template_service.py` | `[^17]` | `file:...template_service.py`, `class:...:TemplateService`, methods listed in plan |
| `src/fs2/core/services/smart_content/__init__.py` | `[^17]` | `file:.../__init__.py` |
| `src/fs2/core/templates/smart_content/smart_content_file.j2` | `[^18]` | `file:.../smart_content_file.j2` |
| `src/fs2/core/templates/smart_content/smart_content_type.j2` | `[^18]` | `file:.../smart_content_type.j2` |
| `src/fs2/core/templates/smart_content/smart_content_callable.j2` | `[^18]` | `file:.../smart_content_callable.j2` |
| `src/fs2/core/templates/smart_content/smart_content_section.j2` | `[^18]` | `file:.../smart_content_section.j2` |
| `src/fs2/core/templates/smart_content/smart_content_block.j2` | `[^18]` | `file:.../smart_content_block.j2` |
| `src/fs2/core/templates/smart_content/smart_content_base.j2` | `[^18]` | `file:.../smart_content_base.j2` |
| `tests/unit/services/test_template_service.py` | `[^14] [^15] [^16] [^19]` | `file:tests/unit/services/test_template_service.py`, functions listed in plan |
| `docs/plans/008-smart-content/tasks/phase-2-template-system/execution.log.md` | N/A (artifact) | N/A |
| `docs/plans/008-smart-content/tasks/phase-2-template-system/tasks.md` | N/A (artifact) | N/A |
| `docs/plans/008-smart-content/smart-content-plan.md` | N/A (authority doc) | N/A |

