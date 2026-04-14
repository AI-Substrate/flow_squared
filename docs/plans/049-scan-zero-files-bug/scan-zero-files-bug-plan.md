# Scan Silent Failure Fix — Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-04-14
**Spec**: `docs/plans/049-scan-zero-files-bug/scan-zero-files-bug-spec.md`
**Status**: COMPLETE

## Summary

`fs2 scan` silently fails when config YAML is broken or scan paths are missing — showing misleading "✓ Loaded" and "Errors: 1" with no detail. This plan adds a silent doctor pre-flight check, changes the scanner to warn-and-continue on missing paths (instead of aborting), and displays actual error messages in the scan summary.

## Target Domains

| Domain | Status | Relationship | Role |
|--------|--------|-------------|------|
| cli | existing | **modify** | scan.py: pre-flight doctor check + error display |
| adapters | existing | **modify** | file_scanner.py (ABC), file_scanner_impl.py, file_scanner_fake.py: add missing_paths contract, warn-and-skip |
| services | existing | **modify** | discovery_stage.py: read scanner.missing_paths, append to context.errors |
| doctor | existing | **consume** | Reuse `validate_configs()` as-is |

## Domain Manifest

| File | Domain | Classification | Rationale |
|------|--------|---------------|-----------|
| `src/fs2/cli/scan.py` | cli | internal | Add doctor call + error display |
| `src/fs2/core/adapters/file_scanner.py` | adapters | contract | Add `missing_paths` property to ABC |
| `src/fs2/core/adapters/file_scanner_impl.py` | adapters | internal | Warn-and-skip + implement missing_paths |
| `src/fs2/core/adapters/file_scanner_fake.py` | adapters | internal | Implement missing_paths (default empty) |
| `src/fs2/core/services/stages/discovery_stage.py` | services | internal | Read scanner.missing_paths, append to context.errors |
| `tests/unit/adapters/test_file_scanner_impl.py` | adapters | internal | Update test for warn-and-skip behavior |
| `tests/unit/cli/test_scan_cli.py` | cli | internal | Add tests for doctor pre-flight + error display |

## Key Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | Scanner abort on missing path bypasses DiscoveryStage — if we just warn instead of raise, missing paths won't enter `context.errors` and `ScanSummary.success` stays True | Scanner must still collect missing paths. Use `logger.warning()` + `continue` but also collect error strings. Expose via public `missing_paths` property on ABC. |
| 02 | High | `ScanSummary` has no `warnings` field — only `errors` | Don't add a new field. Missing paths go into `context.errors` via DiscoveryStage. The scanner collects them; DiscoveryStage reads `scanner.missing_paths` and appends. |
| 03 | High | `test_file_scanner_impl.py:827-847` asserts `FileScannerError` on missing path | Must update test to expect warn-and-continue + check `scanner.missing_paths` |
| 04 | High | No CLI cross-module call precedent — scan.py→doctor.py is new coupling | Keep it minimal: one lazy import, one function call. Wrap in try/except so doctor failures never abort scan. |
| 05 | High | `validate_configs()` and `FS2ConfigurationService` both use same `get_project_config_dir()` (cwd-relative) | No extra risk — both resolve from same CWD. Not a new issue. |
| 06 | High | T002 accesses private `_missing_paths` — violates adapter boundary | Add public `missing_paths` property to FileScanner ABC. Implement in both real and fake. |
| 07 | Medium | `scan_paths` containing a file (not dir) causes `NotADirectoryError` in `_walk_directory` | Handle `is_dir()` check alongside `exists()` in T001 — treat non-directories as missing with clear error. |

## Implementation

**Objective**: Make `fs2 scan` self-diagnosing — surface config and discovery errors transparently.
**Testing Approach**: Lightweight — targeted tests for new behavior, no mocks, real temp dirs.

### Tasks

| Status | ID | Task | Domain | Path(s) | Done When | Notes |
|--------|-----|------|--------|---------|-----------|-------|
| [x] | T001 | Scanner: warn-and-skip missing/invalid scan_paths | adapters | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/core/adapters/file_scanner_impl.py` | Scanner logs warning + continues on missing path (or non-directory). Collects missing paths in `self._missing_paths: list[str]`. Returns results from valid paths. Also handles `is_dir()` check. | Per findings 01, 07 |
| [x] | T001a | FileScanner ABC: add `missing_paths` property | adapters | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/core/adapters/file_scanner.py` | ABC has `@property missing_paths -> list[str]` with docstring. Default abstract. | Per finding 06: public contract, not private access |
| [x] | T001b | FakeFileScanner: implement `missing_paths` | adapters | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/core/adapters/file_scanner_fake.py` | Fake returns empty list by default. Can be set for testing. | Per finding 06 |
| [x] | T002 | DiscoveryStage: read scanner.missing_paths | services | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/core/services/stages/discovery_stage.py` | After `scanner.scan()`, reads `scanner.missing_paths` (public property) and appends each to `context.errors`. Partial results preserved — does NOT reset scan_results on missing paths. | Per findings 01, 02, 06 |
| [x] | T003 | Scan CLI: silent doctor pre-flight check | cli | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/cli/scan.py` | After `FS2ConfigurationService()`, lazy-import `validate_configs()` and call it inside try/except. If config errors → print warnings + "run `fs2 doctor`". If clean → print "✓ Loaded" as before. If validate_configs() itself fails → log debug, show "✓ Loaded" (best-effort). | Per findings 04, catch unexpected exceptions |
| [x] | T004 | Scan CLI: display error messages in summary | cli | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/cli/scan.py` | `_display_final_summary()` iterates `summary.errors` and appends each as a bullet line in the panel. | Currently shows only "Errors: N" |
| [x] | T005 | Update scanner test for warn-and-skip | adapters | `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/unit/adapters/test_file_scanner_impl.py` | Existing test (~lines 827-847) updated: missing path no longer raises, instead scanner returns results from valid paths + exposes missing_paths list. Add test for non-directory path. | Per finding 03 |
| [x] | T005a | Add scan CLI tests for doctor pre-flight + error display | cli | `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/unit/cli/test_scan_cli.py` | New tests: clean config shows "✓ Loaded" (AC1), broken YAML shows warning (AC2), summary lists actual errors (AC5). Use real temp dirs, no mocks. | Covers AC1, AC2, AC5 |
| [x] | T006 | Verify existing tests pass | all | — | All existing scan CLI + adapter tests pass (excluding pre-existing `test_verbose_flag` failure). | AC7 |

### Acceptance Criteria

- [ ] AC1 — Silent doctor on clean config: "✓ Loaded .fs2/config.yaml" appears when config is valid
- [ ] AC2 — Doctor warning on broken YAML: warning with error location shown, no checkmark
- [ ] AC3 — Doctor warning on schema error: validation error shown as warning
- [ ] AC4 — Missing scan_path warns and continues: partial results returned from valid paths
- [ ] AC5 — Error messages displayed in summary: each error shown, not just count
- [ ] AC6 — All paths missing: zero files + clear error messages per path
- [ ] AC7 — Existing tests pass (excluding pre-existing failures)

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Doctor import slows scan startup | Low | Low | Lazy import inside function; doctor shares most deps with scan already |
| Scanner contract change breaks downstream | Low | Medium | Only DiscoveryStage consumes FileScanner; update ABC + both impls + stage together (T001/T001a/T001b/T002) |
| Tests that check exact "✓ Loaded" output | Medium | Low | Search for string matches before implementing; update if found |
| `validate_configs()` throws unexpected exception | Low | High | Wrap in try/except — doctor failure degrades gracefully to "✓ Loaded" (per T003) |
| `scan_paths` contains a file not a directory | Low | Medium | Add `is_dir()` check in T001 alongside `exists()` |

---

## Validation Record (2026-04-14)

| Agent | Lenses Covered | Issues | Verdict |
|-------|---------------|--------|---------|
| Coherence | System Behavior, Domain Boundaries, Integration & Ripple | 2 HIGH, 2 MEDIUM — all fixed | ✅ |
| Risk | Edge Cases, Performance, Concept Documentation | 1 HIGH, 4 MEDIUM — high fixed, mediums noted | ✅ |
| Completeness | Technical Constraints, Hidden Assumptions, User Experience | 1 HIGH, 2 MEDIUM — all fixed | ✅ |

Overall: ⚠️ VALIDATED WITH FIXES — 4 HIGH issues fixed (ABC contract, exception guard, missing tests task, domain manifest), 7 MEDIUM noted/addressed.
