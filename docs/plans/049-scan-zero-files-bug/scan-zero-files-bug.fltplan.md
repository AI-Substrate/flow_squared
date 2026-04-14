# ✈️ Flight Plan: Scan Silent Failure Fix

**Plan**: 049-scan-zero-files-bug
**Status**: Ready
**Complexity**: CS-2 (small)
**Generated**: 2026-04-14

## Mission

Make `fs2 scan` self-diagnosing: surface config errors via silent doctor check, display scanner error messages, and gracefully skip missing scan paths.

## Artifacts

| Artifact | Status | Path |
|----------|--------|------|
| Research Dossier | ✅ Complete | `research-dossier.md` |
| Specification | ✅ Complete | `scan-zero-files-bug-spec.md` |
| Clarification | ✅ Complete | Session 2026-04-14 in spec |
| Plan | ✅ Complete | `scan-zero-files-bug-plan.md` |

## Key Decisions

- Reuse doctor's `validate_configs()` — no new validation logic
- Warn-and-skip for missing scan_paths (not hard fail)
- Lazy import to avoid startup overhead
- Missing paths go into `context.errors` (not a new `warnings` field)
- Scanner exposes `_missing_paths` list for DiscoveryStage to read

## Tasks (6)

| ID | Task | Domain | AC |
|----|------|--------|----|
| T001 | Scanner warn-and-skip | adapters | AC4, AC6 |
| T002 | DiscoveryStage read missing_paths | adapters | AC4, AC6 |
| T003 | Silent doctor pre-flight | cli | AC1, AC2, AC3 |
| T004 | Display errors in summary | cli | AC5 |
| T005 | Update scanner test | adapters | AC7 |
| T006 | Verify existing tests | all | AC7 |

## Acceptance Criteria Summary

| AC | Description | Status |
|----|-------------|--------|
| AC1 | Silent doctor on clean config — no output change | ⬜ |
| AC2 | Warning shown on broken YAML | ⬜ |
| AC3 | Warning shown on schema error | ⬜ |
| AC4 | Missing scan_path warns and continues | ⬜ |
| AC5 | Error messages displayed in summary | ⬜ |
| AC6 | All paths missing still reports clearly | ⬜ |
| AC7 | Existing tests pass | ⬜ |
