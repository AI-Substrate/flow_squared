# Code Review: Phase 3: Config & Discovery CLI

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-spec.md
**Phase**: Phase 3: Config & Discovery CLI
**Date**: 2026-03-19
**Reviewer**: Automated (plan-7-v2)
**Testing Approach**: Hybrid

## A) Verdict

**REQUEST_CHANGES**

The phase leaves the enabled cross-file-relationships path broken: the stage now consumes a `DiscoveredProject` shape and a stripped-down `CrossFileRelsConfig`, but it still expects the old `ProjectRoot.languages` contract and Serena config fields. The acceptance evidence also misses that path, so the break escaped.

**Key failure areas**:
- **Implementation**: `CrossFileRelsStage` still expects `root.languages`, `parallel_instances`, and `serena_base_port` after Phase 3 removed or reshaped those contracts.
- **Reinvention**: `project_discovery.py` introduces a new discovery model instead of extending the legacy stage contract, leaving two incompatible project-root representations in play.
- **Testing**: The “real SCIP” acceptance test and stage unit tests do not cover the enabled path that now fails at runtime.
- **Doctrine**: `add-project` keeps config mutation/YAML logic in the CLI layer instead of delegating to a service.

## B) Summary

Phase 3 successfully adds config models, a discovery module, and new CLI commands, and the file placement/import boundaries look clean against the plan manifest. However, the runtime contract between `project_discovery.py`, `CrossFileRelsConfig`, and `CrossFileRelsStage` is broken: a current rerun of the phase test bundle reproduced an `AttributeError` on `root.languages`, and direct probes confirm the stage still reads removed Serena config fields. Domain compliance itself is clean, and there are no `docs/domains/` artifacts in this repo to update, so there are no cross-domain placement/import violations to fix. Testing evidence is only moderately reliable (`57%` coverage confidence) because the acceptance path that should prove the phase behavior is not the path the changed code actually exercises.

## C) Checklist

**Testing Approach: Hybrid**

- [ ] Critical enabled-path behavior covered by tests
- [x] Lightweight CLI/config tests exist
- [ ] Evidence artifacts capture reproducible command output
- [x] Only in-scope files changed
- [ ] Linters/type checks clean (if applicable)
- [x] Domain compliance checks pass

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | HIGH | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py:835-862` | correctness | Stage consumes `DiscoveredProject` values as if they were legacy `ProjectRoot`s, then dereferences missing `.languages` and collapses multi-language roots by path. | Make the stage and discovery layer share one contract before shipping the extraction. |
| F002 | HIGH | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py:906-910` | correctness | Stage still reads removed Serena config fields (`parallel_instances`, `serena_base_port`) from `CrossFileRelsConfig`. | Finish the stage migration or restore a temporary compatibility contract until Phase 4 lands. |
| F003 | HIGH | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/integration/test_cross_file_acceptance.py:21-71` | testing | The acceptance path that is supposed to prove SCIP behavior still routes through Serena-era stage logic, and the enabled path was never exercised in the changed test set. | Add enabled-path regression coverage and align the acceptance test with the runtime path the phase actually changed. |
| F004 | MEDIUM | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_projects_cli.py:1457-1497` | testing | AC6 coverage is partial: discovery tests do not assert marker/project-file display, indexer status, or install hints. | Add CLI assertions for `marker_file`, indexer status icons/flags, and install-hint output. |
| F005 | MEDIUM | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_projects_cli.py:1499-1559` | testing | AC7 coverage is partial: tests never prove comment-preserving YAML writes or non-default `project_file` persistence. | Add `ruamel.yaml` preservation and `project_file` serialization cases. |
| F006 | MEDIUM | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/projects.py:155-274` | doctrine | `add-project` owns YAML parsing, deduplication, and config mutation in the CLI layer. | Move selection/config-write logic into a service or config helper and keep the CLI presentation-only. |
| F007 | MEDIUM | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/project_discovery.py:46-62` | doctrine | Core service code exports concrete SCIP binary names and shell install commands for CLI use. | Move indexer/install metadata to the CLI or an infrastructure-facing metadata module. |

## E) Detailed Findings

### E.1) Implementation Quality

- **F001 (HIGH, correctness)** — `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py:835-862`
  - `detect_project_roots()` now returns `DiscoveredProject(path, language, marker_file)`, but `process()` still deduplicates by `pr.path` and then calls `ensure_serena_project(root.path, languages=root.languages)`.
  - That breaks two requirements at once: it collapses the new “one entry per `(path, language)`” discovery model and it crashes the enabled path with `AttributeError: 'DiscoveredProject' object has no attribute 'languages'`.
  - Reproduced directly by re-running `tests/integration/test_cross_file_acceptance.py::TestRealSCIPAcceptance::test_scan_with_real_scip_produces_reference_edges`.

- **F002 (HIGH, correctness)** — `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py:906-910`
  - Phase 3 reduced `CrossFileRelsConfig` to `enabled` only, but the stage still reads `config.parallel_instances` and `config.serena_base_port`.
  - A direct runtime probe confirmed both attributes are absent on `CrossFileRelsConfig(enabled=True)`, so the stage has a second enabled-path crash even after F001 is fixed.

### E.2) Domain Compliance

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | Changed code stays within the phase manifest (`config`, `cli`, `core/services`, `tests`). |
| Contract-only imports | ✅ | No new cross-domain internal import violations found; config models do not import adapters. |
| Dependency direction | ✅ | No infrastructure→business leak detected in the changed files. |
| Domain.md updated | ✅ | N/A — repository has no `docs/domains/*/domain.md`. |
| Registry current | ✅ | N/A — repository has no `docs/domains/registry.md`. |
| No orphan files | ✅ | Every changed file is accounted for by the phase task table or plan manifest. |
| Map nodes current | ✅ | N/A — repository has no `docs/domains/domain-map.md`. |
| Map edges current | ✅ | N/A — no domain map present to refresh. |
| No circular business deps | ✅ | N/A — no domain map present; import review found no new cycle signal. |
| Concepts documented | ✅ | N/A — no domain contract docs exist in this repo. |

### E.3) Anti-Reinvention

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| Project root discovery service/model (`DiscoveredProject`) | Legacy `ProjectRoot` abstraction and path-level dedup flow in `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py` | core/services/stages | ❌ Split contract — extend the existing model or adapt the stage fully before removing the old contract |

No other genuine duplication was surfaced for `ProjectConfig` / `ProjectsConfig` or the new CLI commands.

### E.4) Testing & Evidence

**Coverage confidence**: 57%

- **F003 (HIGH, testing)** — `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/integration/test_cross_file_acceptance.py:21-71`
  - The changed tests never execute the enabled stage path with the extracted discovery shape.
  - Re-running the phase-targeted suite produced `AttributeError: 'DiscoveredProject' object has no attribute 'languages'` from the acceptance test.
  - The current “real SCIP” acceptance test is therefore not proving the runtime behavior Phase 3 claims to deliver.

- **F004 (MEDIUM, testing)** — `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_projects_cli.py:1457-1497`
  - `discover-projects` coverage proves detection, JSON output, count, and `--scan-path`, but not the required marker/project-file display, indexer status, or install-hint output.

- **F005 (MEDIUM, testing)** — `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_projects_cli.py:1499-1559`
  - `add-project` coverage proves file creation and idempotency, but not the promised comment-preserving write path or `project_file` persistence for non-default markers.

| AC | Confidence | Evidence |
|----|------------|----------|
| AC6 | 74 | `tests/unit/cli/test_projects_cli.py` covers discovery, count, JSON, empty-dir handling, and `--scan-path`; `src/fs2/cli/projects.py` renders `Type/Path/Marker/Indexer` and computes install hints. Gap: no assertion of missing-indexer status/hints. |
| AC7 | 79 | `tests/unit/cli/test_projects_cli.py` covers add-by-number, `--all`, idempotency, invalid selection, and config-dir creation. Gap: no explicit test for comment preservation or `project_file` serialization. |
| AC8 | 89 | `tests/unit/config/test_projects_config.py` plus `src/fs2/config/objects.py` prove `type`, `path`, `project_file`, `enabled`, and `options` are modeled and validated. |
| AC13 | 96 | `tests/unit/config/test_projects_config.py` explicitly covers `ts`, `js`, `cs`, `csharp`, `c#`, case-insensitivity, and whitespace normalization. |
| T002 Serena removal | 8 | `tests/unit/config/test_cross_file_rels_config.py` proves the config model now has one field, but the stage still contains live Serena-only logic and the enabled path currently crashes. |
| T003 config registration | 93 | `tests/unit/config/test_projects_config.py` asserts `ProjectsConfig in YAML_CONFIG_TYPES`, and `src/fs2/config/objects.py` registers it. |
| T004 discovery extraction | 31 | `tests/unit/services/test_project_discovery.py` strongly covers discovery behavior, but there is no process-level contract test and the extracted shape is incompatible with the enabled stage path. |

Current direct rerun of the phase-targeted test files: `4 failed, 136 passed in 143.47s`. The blocker relevant to Phase 3 is the enabled-path failure above; three additional failures in `tests/unit/cli/test_init_cli.py` and `tests/unit/cli/test_scan_cli.py` fall outside the Phase 3 diff hunks and were not counted as phase blockers.

### E.5) Doctrine Compliance

N/A — no `docs/project-rules/*.md` files exist in this repository, so doctrine was checked against the repo’s architecture guidance in `AGENTS.md` and `CLAUDE.md`.

- **F006 (MEDIUM, doctrine)** — `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/projects.py:155-274`
  - `add_project()` keeps YAML parsing/writing, idempotency checks, and config mutation in the CLI layer instead of delegating that work to a service or config component.

- **F007 (MEDIUM, doctrine)** — `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/project_discovery.py:46-62`
  - `INDEXER_BINARIES` and `INDEXER_INSTALL` export concrete external-tool names/install commands from core/services, leaking CLI/infrastructure concerns into the service layer.

### E.6) Harness Live Validation

N/A — no harness configured.

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC6 | `fs2 discover-projects` lists detected projects with type, path, project file, and indexer status | CLI tests cover discovery/count/JSON, but not status/install-hint assertions. | 74 |
| AC7 | `fs2 add-project 1 2 3` writes selected projects to `.fs2/config.yaml` | CLI tests prove add-by-number / `--all` / idempotency / config creation, but not comment preservation or `project_file` persistence. | 79 |
| AC8 | `projects` config accepts `type`, `path`, `project_file`, `enabled`, and `options` | Config-model tests and `ProjectConfig` / `ProjectsConfig` definitions are strong. | 89 |
| AC13 | Type aliases normalize to canonical names | Config-model tests cover all documented aliases and normalization behavior. | 96 |
| T002 | Serena-specific config/reference cleanup leaves no broken runtime dependencies | Current test rerun and direct probes contradict this claim. | 8 |
| T003 | `ProjectsConfig` is registered in `YAML_CONFIG_TYPES` | Registry membership is explicitly tested and visible in source. | 93 |
| T004 | `detect_project_roots()` extraction works end-to-end | Unit discovery tests are good, but the enabled stage path is still incompatible with the extracted shape. | 31 |

**Overall coverage confidence**: 57%

## G) Commands Executed

```bash
git --no-pager diff --stat
git --no-pager diff --staged --stat
git --no-pager status --short
git --no-pager log --oneline -12
git --no-pager show --name-status --format=medium faae900
git --no-pager show --name-status --format=medium 2985ac9
git --no-pager diff --find-renames 2985ac9 faae900 > /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-3-config-discovery-cli/reviews/_computed.diff
git --no-pager diff --name-status 2985ac9 faae900
uv run ruff check src/fs2/cli/init.py src/fs2/cli/main.py src/fs2/cli/projects.py src/fs2/cli/scan.py src/fs2/cli/watch.py src/fs2/config/objects.py src/fs2/config/paths.py src/fs2/core/services/pipeline_context.py src/fs2/core/services/project_discovery.py src/fs2/core/services/stages/cross_file_rels_stage.py tests/integration/test_cross_file_acceptance.py tests/integration/test_cross_file_integration.py tests/unit/cli/test_init_cli.py tests/unit/cli/test_projects_cli.py tests/unit/cli/test_scan_cli.py tests/unit/config/test_cross_file_rels_config.py tests/unit/config/test_projects_config.py tests/unit/services/stages/test_cross_file_rels_stage.py tests/unit/services/test_project_discovery.py
uv run python -m pytest -q --override-ini="addopts=" tests/integration/test_cross_file_acceptance.py tests/integration/test_cross_file_integration.py tests/unit/cli/test_init_cli.py tests/unit/cli/test_projects_cli.py tests/unit/cli/test_scan_cli.py tests/unit/config/test_cross_file_rels_config.py tests/unit/config/test_projects_config.py tests/unit/services/stages/test_cross_file_rels_stage.py tests/unit/services/test_project_discovery.py
uv run python - <<'PY'
from fs2.config.objects import CrossFileRelsConfig
cfg = CrossFileRelsConfig(enabled=True)
print('has_parallel_instances', hasattr(cfg, 'parallel_instances'))
print('has_serena_base_port', hasattr(cfg, 'serena_base_port'))
try:
    print(cfg.serena_base_port)
except Exception as e:
    print(type(e).__name__, str(e))
PY
uv run python - <<'PY'
from fs2.core.services.project_discovery import detect_project_roots
from pathlib import Path
root = Path('tests/fixtures/samples').resolve()
projects = detect_project_roots(str(root))
print(type(projects[0]).__name__ if projects else 'none')
if projects:
    p = projects[0]
    print('fields', sorted(p.__dict__.keys()))
    print('has_languages', hasattr(p, 'languages'))
PY
```

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: REQUEST_CHANGES

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-spec.md
**Phase**: Phase 3: Config & Discovery CLI
**Tasks dossier**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-3-config-discovery-cli/tasks.md
**Execution log**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-3-config-discovery-cli/execution.log.md
**Review file**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-3-config-discovery-cli/reviews/review.phase-3-config-discovery-cli.md

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-3-config-discovery-cli/execution.log.md` | Created | phase-artifact | Update evidence after fixes |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-3-config-discovery-cli/tasks.fltplan.md` | Modified | phase-artifact | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-3-config-discovery-cli/tasks.md` | Modified | phase-artifact | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/pyproject.toml` | Modified | config | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/init.py` | Modified | cli | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/main.py` | Modified | cli | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/projects.py` | Created | cli | Refactor YAML / config logic; extend AC6 / AC7 coverage |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/scan.py` | Modified | cli | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/watch.py` | Modified | cli | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/config/objects.py` | Modified | config | Resolve stage / config contract mismatch |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/config/paths.py` | Modified | config | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/pipeline_context.py` | Modified | core/services | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/project_discovery.py` | Created | core/services | Align discovery contract; move tool metadata out of service |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py` | Modified | core/services/stages | Fix enabled-path runtime contract |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/docs/cross-file-relationships.md` | Modified | docs | Re-check wording after runtime fix |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/integration/test_cross_file_acceptance.py` | Modified | tests | Align acceptance test with actual enabled path |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/integration/test_cross_file_integration.py` | Modified | tests | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_init_cli.py` | Modified | tests | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_projects_cli.py` | Created | tests | Add AC6 / AC7 evidence cases |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_scan_cli.py` | Modified | tests | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/config/test_cross_file_rels_config.py` | Modified | tests | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/config/test_projects_config.py` | Created | tests | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/stages/test_cross_file_rels_stage.py` | Modified | tests | Add enabled-path regression coverage |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_project_discovery.py` | Created | tests | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/uv.lock` | Modified | dependency-lock | None |

### Required Fixes (if REQUEST_CHANGES)

| # | File (absolute path) | What To Fix | Why |
|---|---------------------|-------------|-----|
| 1 | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py` | Stop treating `DiscoveredProject` as legacy `ProjectRoot`; preserve one `(path, language)` entry per discovered project and remove `.languages` dereference. | The current enabled path crashes with `AttributeError` and drops multi-language roots. |
| 2 | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py` and `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/config/objects.py` | Resolve the removed Serena config field dependency (`parallel_instances`, `serena_base_port`) coherently. | Phase 3 removed those fields from config but the stage still reads them. |
| 3 | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/integration/test_cross_file_acceptance.py` and `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/stages/test_cross_file_rels_stage.py` | Add enabled-path regression coverage and make the acceptance test prove the actual phase behavior. | The current tests missed the runtime break and do not truly validate SCIP behavior for this phase. |
| 4 | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_projects_cli.py` | Add assertions for marker / project-file display, indexer status / install hints, comment preservation, and `project_file` serialization. | AC6 and AC7 are only partially evidenced today. |
| 5 | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/projects.py` and `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/project_discovery.py` | Move config mutation and tool-install metadata out of the CLI / service layers into more appropriate modules. | Current placement violates the repository’s presentation / service separation rules. |

### Domain Artifacts to Update (if any)

| File (absolute path) | What's Missing |
|---------------------|----------------|
| `None` | No `docs/domains/*` artifacts exist in this repository; no domain-document updates are required for this phase review. |

### Next Step

`/plan-6-v2-implement-phase --plan /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-plan.md --phase 'Phase 3: Config & Discovery CLI'`
