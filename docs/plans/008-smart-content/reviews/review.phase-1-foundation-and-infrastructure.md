# Review Report — Phase 1: Foundation & Infrastructure

**Plan**: `docs/plans/008-smart-content/smart-content-plan.md`  
**Phase Dossier**: `docs/plans/008-smart-content/tasks/phase-1-foundation-and-infrastructure/tasks.md`  
**Execution Log**: `docs/plans/008-smart-content/tasks/phase-1-foundation-and-infrastructure/execution.log.md`  
**Diff Basis**: Working tree vs `HEAD` (tracked `git diff` + untracked files via `git ls-files --others`)  
**Testing Approach (from plan)**: Full TDD  
**Mock Policy (from plan)**: Targeted mocks (fakes over mocks)  

## A) Verdict

**REQUEST_CHANGES**

Blocking reasons:
1) **Graph integrity / authority breaks**: plan footnotes ledger does not account for all diff-touched files and dossier stubs do not mirror plan ledger node lists (plan is authority).  
2) **Scope guard violation**: `AGENTS.md` is changed but not in Phase 1 scope/justification.  

## B) Summary (≤10 lines)

- Core Phase 1 deliverables look aligned: `SmartContentConfig`, TokenCounter adapter family, `content_hash` on `CodeNode`, hash utility, smart-content service exceptions.
- Full TDD evidence exists in `execution.log.md` with RED/GREEN narratives and per-task pytest evidence.
- `uv run pytest tests/unit/ -v` passes (645 tests). Targeted subset for Phase 1 also passes under `uv` with `UV_CACHE_DIR`.
- Graph integrity is not merge-ready: footnote authority + completeness requirements are not met.
- One out-of-scope file (`AGENTS.md`) is present in the diff without dossier/plan justification.

## C) Checklist (Testing Strategy–Aware)

**Testing Approach: Full TDD** · **Mock Usage: Targeted mocks**

- [x] RED evidence present per task (`execution.log.md`)
- [~] Tests precede code (cannot verify via git history; relies on execution log narrative)
- [x] Tests-as-docs (new tests include Purpose/Quality Contribution/Acceptance Criteria docstrings)
- [x] Mock policy followed for Phase 1 tests (fakes/monkeypatch used; no `unittest.mock` introduced in Phase 1 diff)
- [x] Negative/edge coverage present where specified (invalid worker count; empty/unicode hashing; tokenizer failure translation)
- [!] Graph integrity links/authority are correct (see Findings)
- [!] Only in-scope files changed (see Findings)
- [x] Unit tests clean via project-native runner (`just test-unit`)
- [!] Lint clean (project-wide `just lint` fails; Phase 1 file also has ruff import-order findings)

## D) Findings Table

| ID | Severity | File:Lines | Summary | Recommendation |
|----|----------|------------|---------|----------------|
| F-001 | CRITICAL | `docs/plans/008-smart-content/smart-content-plan.md:1441` | Plan Change Footnotes Ledger missing entries for diff-touched files (ledger completeness broken) | Add missing node IDs (plan is authority); then sync dossier stubs |
| F-002 | HIGH | `docs/plans/008-smart-content/tasks/phase-1-foundation-and-infrastructure/tasks.md:306` | Dossier Phase Footnote Stubs list only a subset of plan ledger node IDs (authority mismatch) | Expand `Affects` to mirror plan ledger node lists (or regenerate via plan-6a sync) |
| F-003 | HIGH | `AGENTS.md` | Out-of-scope file change not referenced/justified by Phase 1 dossier | Remove from diff or add explicit scope justification + footnote provenance |
| F-004 | MEDIUM | `tests/unit/adapters/test_token_counter.py:38` | Ruff import organization violations in new test file (I001) | Re-organize local import blocks or refactor imports to satisfy ruff |
| F-005 | LOW | `docs/plans/008-smart-content/tasks/phase-1-foundation-and-infrastructure/execution.log.md:10` | Execution log metadata is not fully “bidirectionally linkable” (task IDs not links) | Make `**Dossier Task**` / `**Plan Task**` lines clickable (optional) |

## E) Detailed Findings

### E.0 Cross-Phase Regression Analysis

Skipped: Phase 1 is the first phase (no prior phases in this plan to regress against).

### E.1 Doctrine & Testing Compliance

#### Graph Integrity (Step 3a)

**Verdict**: ❌ BROKEN (blocking)

Key issues:
- **Authority + completeness**: plan ledger must cover every diff-touched file/method; it currently omits at least:
  - `tests/unit/services/test_smart_content_exceptions.py` (new test)
  - `src/fs2/core/services/smart_content/__init__.py` (export surface)
  - `AGENTS.md` (if this file remains in scope)
- **Plan↔Dossier**: dossier stubs exist but do not mirror plan ledger node lists (plan is authority).

#### Authority Conflicts (Step 3c)

**Verdict**: FAIL (blocking)

- Plan § “Change Footnotes Ledger” is PRIMARY; dossier Phase Footnote Stubs must be DERIVED and synchronized.
- Dossier stubs currently summarize each footnote to a single node ID (subset), which conflicts with the plan ledger’s detailed list.

#### TDD Doctrine (Step 4)

- RED/GREEN evidence per task is present in `execution.log.md` and includes failing→passing transitions.
- “Tests precede code” cannot be verified via git history because the work is currently uncommitted (review basis is working tree). This is recorded as advisory only.

#### Mock Usage (Step 4)

- Phase 1 tests use fakes (`FakeConfigurationService`, `FakeTokenCounterAdapter`) and targeted `monkeypatch` for `tiktoken` to enforce offline determinism.
- No new `unittest.mock` usage introduced by Phase 1 diff.

#### Testing Evidence & Coverage Alignment (Step 5)

Evidence artifacts declared in dossier exist:
- `docs/plans/008-smart-content/tasks/phase-1-foundation-and-infrastructure/execution.log.md`
- `docs/plans/008-smart-content/tasks/phase-1-foundation-and-infrastructure/tasks.md`

Coverage mapping is strong for Phase 1 deliverables (see Section F).

### E.2 Semantic Analysis (Spec/Plan Alignment)

No semantic mismatches found for Phase 1 scope:
- `SmartContentConfig` implements defaults and registry binding as documented.
- `CodeNode.content_hash` is computed via SHA-256 helper in all factories.
- TokenCounter adapter translates tokenizer errors into `TokenCounterError` and caches encoder per instance.
- Smart-content service exceptions are service-layer only (no adapter exception duplication).

### E.3 Quality & Safety Analysis

**Correctness**: No functional defects identified in Phase 1 implementation diff.  
**Security**: No path traversal / injection / secret leakage issues identified.  
**Performance**: Encoder caching and hashing are appropriate for Phase 1.  
**Observability**: No logging introduced in Phase 1 (acceptable at this layer); later phases should add structured logs at service orchestration points.  

Notable quality debt surfaced by toolchain:
- `uv run ruff check ...` flags import organization in `tests/unit/adapters/test_token_counter.py` (see F-004).

## F) Coverage Map (Acceptance Criteria ↔ Tests)

Confidence scale: 100% explicit, 75% behavioral match, 50% inferred, 0% unclear.

| Criterion | Evidence | Test(s) | Confidence |
|----------|----------|---------|------------|
| Spec AC1 (CodeNode hash field) | Factory computes SHA-256 hash | `tests/unit/models/test_code_node.py` (`test_create_file_when_called_then_populates_content_hash`) | 75% |
| Phase 1 / T001 (SmartContentConfig defaults + YAML/env binding) | Defaults + `__config_path__` + YAML/env precedence | `tests/unit/config/test_smart_content_config.py` | 75% |
| Phase 1 / T003–T005 (TokenCounter adapter family) | ABC, fake behavior, encoder caching, error translation | `tests/unit/adapters/test_token_counter.py` | 75% |
| Phase 1 / T006–T007 (Hash utilities) | SHA-256 hexdigest, empty/unicode | `tests/unit/models/test_hash_utils.py` | 75% |
| Phase 1 / T011 (Service exception hierarchy) | Inheritance contract | `tests/unit/services/test_smart_content_exceptions.py` | 75% |

Overall coverage confidence (Phase 1 deliverables): **75%** (behavioral match, limited explicit AC-ID tagging).

## G) Commands Executed (copy/paste)

```bash
# Diff + file inventory
git status --porcelain=v1
git diff --name-only
git ls-files --others --exclude-standard
git diff --stat

# Tests (NOTE: plain pytest fails without uv-managed deps; see output in review notes)
pytest -q tests/unit/config/test_smart_content_config.py \
  tests/unit/adapters/test_token_counter.py \
  tests/unit/models/test_hash_utils.py \
  tests/unit/models/test_code_node.py \
  tests/unit/services/test_smart_content_exceptions.py

# Project-native passing runs
UV_CACHE_DIR=/workspaces/flow_squared/.uv_cache uv run pytest -q tests/unit/config/test_smart_content_config.py \
  tests/unit/adapters/test_token_counter.py \
  tests/unit/models/test_hash_utils.py \
  tests/unit/models/test_code_node.py \
  tests/unit/services/test_smart_content_exceptions.py

UV_CACHE_DIR=/workspaces/flow_squared/.uv_cache just test-unit

# Lint (fails repo-wide; also flags Phase 1 import-order issues)
UV_CACHE_DIR=/workspaces/flow_squared/.uv_cache just lint
UV_CACHE_DIR=/workspaces/flow_squared/.uv_cache uv run ruff check \
  src/fs2/config/objects.py src/fs2/core/adapters/exceptions.py \
  src/fs2/core/adapters/token_counter_adapter.py \
  src/fs2/core/adapters/token_counter_adapter_fake.py \
  src/fs2/core/adapters/token_counter_adapter_tiktoken.py \
  src/fs2/core/models/code_node.py \
  src/fs2/core/services/smart_content/exceptions.py \
  src/fs2/core/services/smart_content/__init__.py \
  src/fs2/core/utils/__init__.py src/fs2/core/utils/hash.py \
  tests/unit/config/test_smart_content_config.py \
  tests/unit/adapters/test_token_counter.py \
  tests/unit/models/test_hash_utils.py \
  tests/unit/services/test_smart_content_exceptions.py
```

## H) Decision & Next Steps

To reach **APPROVE**:
1) Apply `docs/plans/008-smart-content/reviews/fix-tasks.phase-1-foundation-and-infrastructure.md`.
2) Re-run `/plan-6` for fixes, then re-run `/plan-7` to confirm graph integrity + scope guard + lint signal.

## I) Footnotes Audit (Diff Paths ↔ Footnote Tags ↔ Node IDs)

Plan ledger coverage summary (Phase 1): **partial** (missing entries; see F-001).

| Path | Footnote(s) (plan ledger) | Example node ID(s) (plan ledger) |
|------|----------------------------|----------------------------------|
| `tests/unit/config/test_smart_content_config.py` | [^1] | `file:tests/unit/config/test_smart_content_config.py` |
| `src/fs2/config/objects.py` | [^2] | `class:src/fs2/config/objects.py:SmartContentConfig` |
| `tests/unit/adapters/test_token_counter.py` | [^3] [^4] | `file:tests/unit/adapters/test_token_counter.py` |
| `src/fs2/core/adapters/exceptions.py` | [^4] | `class:src/fs2/core/adapters/exceptions.py:TokenCounterError` |
| `src/fs2/core/adapters/token_counter_adapter*.py` | [^5] | `class:src/fs2/core/adapters/token_counter_adapter.py:TokenCounterAdapter` |
| `src/fs2/core/adapters/__init__.py` | [^5] | `file:src/fs2/core/adapters/__init__.py` |
| `pyproject.toml` / `uv.lock` | [^5] | `file:pyproject.toml` |
| `tests/unit/models/test_hash_utils.py` | [^6] | `file:tests/unit/models/test_hash_utils.py` |
| `src/fs2/core/utils/hash.py` / `src/fs2/core/utils/__init__.py` | [^7] ([^9] also references `hash.py`) | `function:src/fs2/core/utils/hash.py:compute_content_hash` |
| `tests/unit/models/test_code_node.py` | [^8] | `file:tests/unit/models/test_code_node.py` |
| `src/fs2/core/models/code_node.py` | [^9] | `class:src/fs2/core/models/code_node.py:CodeNode` |
| `tests/unit/services/test_get_node_service.py` / `tests/unit/repos/test_graph_store_impl.py` | [^10] | `file:tests/unit/services/test_get_node_service.py` |
| `src/fs2/core/services/smart_content/exceptions.py` | [^11] | `file:src/fs2/core/services/smart_content/exceptions.py` |

Missing in plan ledger (must be addressed if these files remain in diff):
- `tests/unit/services/test_smart_content_exceptions.py`
- `src/fs2/core/services/smart_content/__init__.py`
- `AGENTS.md`
