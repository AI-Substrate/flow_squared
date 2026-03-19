# Execution Log: Phase 3 — Config & Discovery CLI

**Plan**: [scip-cross-file-rels-plan.md](../../scip-cross-file-rels-plan.md)
**Phase**: Phase 3: Config & Discovery CLI
**Started**: 2026-03-19
**Completed**: 2026-03-19

---

## Baseline

- 463 relevant tests passing (unit/config, unit/adapters/test_scip_*, unit/services/stages)
- 231 pre-existing failures (async/embedding/report — unrelated to Phase 3)
- Lint clean on Phase 3 target files

---

## T000: Add ruamel.yaml — `ruamel-yaml>=0.18` added, installed 0.18.12
## T001: ProjectConfig + ProjectsConfig — type alias normalisation, entries field
## T002: Serena cleanup — 14 files cleaned, CrossFileRelsConfig reduced to `enabled` only
## T003: Register config — ProjectsConfig added to YAML_CONFIG_TYPES
## T004: Extract discovery — project_discovery.py, no child dedup, C#/Ruby markers, one entry per (path, lang)
## T005: discover-projects CLI — Rich table with indexer status (✅/❌), JSON output, install hints
## T006: add-project CLI — ruamel.yaml comment-preserving write, idempotent, creates .fs2/ if needed
## T007: Register commands — main.py, no require_init guard
## T008: Tests — 84 tests across 6 test files, all passing

**Evidence**: 489 tests passing (broader suite), lint clean