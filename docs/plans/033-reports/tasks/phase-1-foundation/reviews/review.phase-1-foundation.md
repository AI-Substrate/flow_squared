# Code Review: Phase 1: Foundation — Config, CLI, Service Skeleton

**Plan**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/reports-plan.md`
**Spec**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/reports-spec.md`
**Phase**: `Phase 1: Foundation — Config, CLI, Service Skeleton`
**Date**: 2026-03-15
**Reviewer**: Automated (plan-7-v2)
**Testing Approach**: Hybrid

## A) Verdict

**REQUEST_CHANGES**

The Phase 1 slice works in live smoke checks, but `src/fs2/cli/report.py` bypasses the repository's required safe output helpers and path validation. That leaves a user-controlled write path outside the established CLI safety pattern and is the blocking issue for approval.

**Key failure areas**:
- **Implementation**: `report.py` writes report files directly instead of reusing `validate_save_path()` and `safe_write_file()`.
- **Reinvention**: `report.py` duplicates existing CLI save-path/write behavior instead of reusing the helpers already provided in `fs2.cli.utils`.
- **Testing**: `tests/unit/cli/test_report_cli.py` is missing, so the phase's CLI acceptance criteria are only reviewer-verified, not implementation-verified.
- **Doctrine**: `uv run ruff check` fails on an unused import in `tests/unit/services/test_report_service.py`.

## B) Summary

The phase is partially successful: live review runs verified `fs2 report --help`, `fs2 report codebase-graph --help`, default output generation, custom `--output`, `--graph-file`, missing-graph exit handling, and `--no-smart-content` field omission. The config and service layer tests also pass (`17 passed`), which gives good confidence in the core serialization path.

The blocking gap is in `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/report.py`, where the command resolves and writes output paths directly instead of reusing `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/utils.py` helpers that enforce the working-directory boundary and partial-write cleanup. That is both a pattern regression and a concrete safety regression relative to the phase dossier.

Evidence quality is also below the bar for a completed Full Mode phase: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_report_cli.py` is absent, and `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-1-foundation/execution.log.md` contains no task log entries. No code-level domain boundary violations were found, but `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/` and `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/project-rules/` are absent on this branch, so documentary domain/doctrine checks were N/A.

## C) Checklist

**Testing Approach: Hybrid**

- [x] TDD/service-config checks present for deterministic logic
- [ ] Lightweight CLI smoke tests present
- [ ] Manual verification steps recorded in the phase execution log
- [x] Only in-scope phase files were reviewed
- [ ] Linters/type checks clean (if applicable)
- [x] Code-level domain boundary checks pass

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | HIGH | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/report.py:65-66,99-100` | security / pattern | `report.py` resolves and writes the output path directly, bypassing `validate_save_path()` and `safe_write_file()`. | Reuse both helpers from `fs2.cli.utils` for custom and default outputs. |
| F002 | MEDIUM | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_report_cli.py` | testing / scope | The planned Phase 1 CLI smoke test file is missing, so CLI ACs are not implementation-verified. | Add `CliRunner` coverage for help, success, `--graph-file`, missing graph, `--output`, `--no-smart-content`, and `--open`. |
| F003 | MEDIUM | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-1-foundation/execution.log.md:10-13` | evidence | The execution log has no task entries or command evidence, despite Full Mode expecting task-by-task implementation records. | Populate the task log with completed work, commands, and observed outcomes. |
| F004 | MEDIUM | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_report_service.py:8` | quality | `uv run ruff check ...` fails because `json` is imported but unused. | Remove the unused import and re-run Ruff. |

## E) Detailed Findings

### E.1) Implementation Quality

- **F001 — HIGH**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/report.py:65-66,99-100` writes directly with `Path.resolve()`, `mkdir()`, and `write_text()`. The phase dossier explicitly called for `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/utils.py` reuse (`validate_save_path()` + `safe_write_file()`), and the current implementation loses the working-directory boundary check plus partial-write cleanup on failure.
- **F004 — MEDIUM**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_report_service.py:8` triggers a real lint failure. Review command output: `F401 [*] json imported but unused`.

Non-blocking positive notes:
- Live review verified that report generation succeeds against `.fs2/graph.pickle`, writes a valid HTML file, and embeds `GRAPH_DATA` + `METADATA`.
- A precise post-generation regex check found `field_key_matches=0` for `"smart_content":` in `--no-smart-content` output, so the service-level omission works end-to-end.

### E.2) Domain Compliance

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | All in-scope files align with the Phase 1 Domain Manifest in `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/reports-plan.md`. |
| Contract-only imports | ✅ | No changed file imports another domain's internal implementation across boundaries. |
| Dependency direction | ✅ | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/report_service.py` stays independent of CLI code; `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/report.py` composes service/repo access through existing CLI utilities. |
| Domain.md updated | N/A | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/**/domain.md` does not exist on this branch, so documentary updates could not be validated. |
| Registry current | N/A | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/registry.md` is absent. |
| No orphan files | ✅ | Every changed phase file maps back to the plan manifest or phase task table. |
| Map nodes current | N/A | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/domain-map.md` is absent. |
| Map edges current | N/A | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/domain-map.md` is absent. |
| No circular business deps | ✅ | No new business-to-business cycle is introduced by the changed code. |
| Concepts documented | N/A | Repository-level domain concept docs are absent, so concept-table currency could not be checked. |

### E.3) Anti-Reinvention

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| CLI output-file handling in `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/report.py` | `fs2.cli.utils.validate_save_path()` and `fs2.cli.utils.safe_write_file()` | cli | ❌ Reuse required — this overlap is the blocking finding F001. |
| Reference-edge filtering in `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/report_service.py` | `GraphStore.get_all_edges(edge_type="references")` and prior filtering logic in scan pipeline | repos / services | ⚠ Reuse recommended — not escalated beyond a note. |

### E.4) Testing & Evidence

**Coverage confidence**: 84%

| AC | Confidence | Evidence |
|----|------------|----------|
| AC1 | 95 | Live command `uv run fs2 --graph-file .fs2/graph.pickle report codebase-graph` wrote `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/.fs2/reports/codebase-graph.html` and the file existed before cleanup. |
| AC3 | 95 | Live command `uv run fs2 --graph-file .fs2/graph.pickle report codebase-graph --output .fs2/reports/review-phase1-smoke.html` succeeded and produced a valid HTML file. |
| AC4 | 60 | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/report.py:112-118` wraps `webbrowser.open()` with fallback messaging, but `--open` was not exercised live. |
| AC5 | 95 | Live report generation used `--graph-file .fs2/graph.pickle` successfully. |
| AC6 | 100 | Live command with `/tmp/definitely-missing-graph.pickle` printed the expected error and exited `1`. |
| AC27 | 100 | Live `uv run fs2 report --help` showed the `codebase-graph` subcommand. |
| AC28 | 100 | Live `uv run fs2 report codebase-graph --help` showed `--output`, `--open`, and `--no-smart-content`. |
| AC29 | 90 | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/config/objects.py:1049-1084` defines `ReportsConfig`, and `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/config/test_reports_config.py` passed. No YAML integration test was present. |
| AC30 | 95 | Service unit test passed, live `--no-smart-content` generation succeeded, and a regex check found zero `"smart_content":` keys in the generated HTML. |

Additional evidence notes:
- `uv run python -m pytest -q tests/unit/config/test_reports_config.py tests/unit/services/test_report_service.py` → `17 passed`.
- `uv run ruff check ...` → failed with unused import in `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_report_service.py:8`.
- `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_report_cli.py` is missing, so the CLI path lacks committed automated coverage.

### E.5) Doctrine Compliance

N/A — `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/project-rules/` is absent, so `rules.md`, `idioms.md`, `architecture.md`, and `constitution.md` could not be validated.

### E.6) Harness Live Validation

N/A — no harness configured. `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/project-rules/harness.md` is absent.

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC1 | Default output path generation | Live generation to `.fs2/reports/codebase-graph.html` | 95 |
| AC3 | Custom output path | Live generation to `.fs2/reports/review-phase1-smoke.html` | 95 |
| AC4 | `--open` browser handoff | Static code path only in `report.py:112-118` | 60 |
| AC5 | `--graph-file` support | Live generation using `.fs2/graph.pickle` | 95 |
| AC6 | Missing-graph error | Live missing-graph run printed error and exited `1` | 100 |
| AC27 | `fs2 report --help` | Live help output listed `codebase-graph` | 100 |
| AC28 | `fs2 report codebase-graph --help` | Live help output listed all phase flags | 100 |
| AC29 | `reports:` config model | `ReportsConfig` present + config tests passed | 90 |
| AC30 | `--no-smart-content` exclusion | Live regex check + service test | 95 |

**Overall coverage confidence**: 84%

## G) Commands Executed

```bash
git --no-pager status --short
git --no-pager diff --staged --stat
git --no-pager diff --stat
git --no-pager log --oneline -12

python - <<'PY'
# built phase-scoped reviews/_computed.diff and reviews/_manifest.tsv
PY

uv run python -m pytest -q tests/unit/config/test_reports_config.py tests/unit/services/test_report_service.py
uv run ruff check src/fs2/cli/main.py src/fs2/config/objects.py src/fs2/cli/report.py src/fs2/core/services/report_service.py tests/unit/config/test_reports_config.py tests/unit/services/test_report_service.py

uv run fs2 report --help
uv run fs2 report codebase-graph --help
uv run fs2 --graph-file /tmp/definitely-missing-graph.pickle report codebase-graph
uv run fs2 --graph-file .fs2/graph.pickle report codebase-graph --output .fs2/reports/review-phase1-smoke.html
uv run fs2 --graph-file .fs2/graph.pickle report codebase-graph
uv run fs2 --graph-file .fs2/graph.pickle report codebase-graph --no-smart-content --output .fs2/reports/review-phase1-nosmart.html

python - <<'PY'
# verified generated HTML contains GRAPH_DATA/METADATA and checked no `"smart_content":` keys in --no-smart-content output
PY
```

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: REQUEST_CHANGES

**Plan**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/reports-plan.md`
**Spec**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/reports-spec.md`
**Phase**: `Phase 1: Foundation — Config, CLI, Service Skeleton`
**Tasks dossier**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-1-foundation/tasks.md`
**Execution log**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-1-foundation/execution.log.md`
**Review file**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-1-foundation/reviews/review.phase-1-foundation.md`

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/pyproject.toml` | modified | config | No |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/main.py` | modified | cli | No |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/config/objects.py` | modified | config | No |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/report.py` | created | cli | Yes |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/report_service.py` | created | services | No |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/static/__init__.py` | created | static-assets | No |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/static/reports/__init__.py` | created | static-assets | No |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/templates/reports/__init__.py` | created | templates | No |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/templates/reports/codebase_graph.html.j2` | created | templates | No |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/config/test_reports_config.py` | created | tests | No |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_report_service.py` | created | tests | Yes |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_report_cli.py` | missing (planned) | tests | Yes |

### Required Fixes (if REQUEST_CHANGES)

| # | File (absolute path) | What To Fix | Why |
|---|---------------------|-------------|-----|
| 1 | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/report.py` | Reuse `validate_save_path()` and `safe_write_file()` for both custom and default output handling. | Restores the repository's output-path safety boundary and partial-write cleanup. |
| 2 | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_report_cli.py` | Add the missing CLI smoke tests promised by T007. | Phase completion currently depends on reviewer manual checks instead of committed test coverage. |
| 3 | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_report_service.py` | Remove the unused `json` import. | `uv run ruff check ...` currently fails. |
| 4 | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-1-foundation/execution.log.md` | Record completed tasks and command evidence. | Full Mode execution evidence is currently missing. |

### Domain Artifacts to Update (if any)

| File (absolute path) | What's Missing |
|---------------------|----------------|
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains` | Formal domain registry / map / per-domain docs are absent on this branch, so documentary domain validation was N/A. No phase-specific code boundary violation was found. |

### Next Step

`/plan-6-v2-implement-phase --plan /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/reports-plan.md --phase 'Phase 1: Foundation — Config, CLI, Service Skeleton'`
