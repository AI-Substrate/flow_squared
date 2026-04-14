# Scan Silent Failure: Surface Config & Discovery Errors

**Mode**: Simple

📚 This specification incorporates findings from research-dossier.md

## Research Context

Research dossier identified a three-bug compound failure where `fs2 scan` reports zero files with no actionable feedback. The root cause chain: (1) broken project YAML silently ignored, (2) user-level config with restrictive scan_paths takes over, (3) scanner aborts on first missing path. Doctor already detects the YAML issue — but scan never calls it. Error messages from scanner failures are counted but never displayed.

## Summary

When `fs2 scan` encounters configuration errors (broken YAML, missing scan paths), it silently proceeds with wrong settings and displays misleading success messages. Users see "✓ Loaded .fs2/config.yaml" even when the file failed to parse, and "Errors: 1" with no explanation of what the error actually is.

**What**: Make scan self-diagnosing — run doctor's config validation silently before scanning, surface any issues as warnings, and display actual error messages when scan-time errors occur.

**Why**: Users shouldn't need to know to run `fs2 doctor` when `fs2 scan` already knows something is wrong. A zero-file scan with a misleading success checkmark wastes time and erodes trust.

## Goals

- **Scan calls doctor silently**: Before scanning, run `validate_configs()` from the doctor module. If issues found, display them as warnings. If clean, show the existing "✓ Loaded" checkmark — transparent when healthy.
- **Scanner errors are visible**: When `summary.errors` exist, display the actual error messages in the summary panel, not just "Errors: N".
- **Scanner skips missing paths gracefully**: When a scan_path doesn't exist, warn and continue with remaining paths instead of aborting the entire scan.

## Non-Goals

- Changing doctor's own behavior or output format
- Adding new doctor checks beyond what already exists
- Changing the config loading pipeline or merge precedence logic
- Auto-fixing broken config files
- Changing exit codes (scan should still exit non-zero when errors occur)
- Changing exit code for config warnings — if scan completes, config issues are warnings only

## Target Domains

| Domain | Status | Relationship | Role in This Feature |
|--------|--------|-------------|---------------------|
| cli | existing | **modify** | scan.py gets pre-flight doctor check and improved error display |
| adapters | existing | **modify** | file_scanner_impl.py changes from hard-fail to warn-and-skip |
| doctor | existing | **consume** | Reuse `validate_configs()` — no changes to doctor itself |

No new domains required. All changes stay within existing module boundaries.

## Complexity

- **Score**: CS-2 (small)
- **Breakdown**: S=1, I=0, D=0, N=0, F=0, T=1
  - Surface Area (1): Three files across two layers (cli/scan.py, adapters/file_scanner_impl.py, stages/discovery_stage.py)
  - Integration (0): Purely internal, reusing existing doctor functions
  - Data/State (0): No schema changes
  - Novelty (0): Well-understood from research — exact lines identified
  - Non-Functional (0): No perf/security concerns
  - Testing (1): Need integration-level test for the doctor-in-scan flow
- **Confidence**: 0.90
- **Assumptions**: `validate_configs()` is fast enough to call on every scan without noticeable delay
- **Dependencies**: None
- **Risks**: Doctor import adds slight startup overhead; mitigated by lazy import

## Acceptance Criteria

1. **AC1 — Silent doctor on clean config**: When `.fs2/config.yaml` is valid YAML and passes schema validation, scan output is unchanged — "✓ Loaded .fs2/config.yaml" appears as before.

2. **AC2 — Doctor warning on broken YAML**: When `.fs2/config.yaml` has a YAML syntax error, scan shows a warning with the error location (e.g., "⚠ YAML error in .fs2/config.yaml line 23: ...") and a pointer to run `fs2 doctor` for details. The "✓ Loaded" checkmark does NOT appear.

3. **AC3 — Doctor warning on schema error**: When config has valid YAML but invalid schema (e.g., `max_file_size_kb: -1`), scan shows a warning with the validation error.

4. **AC4 — Missing scan_path warns and continues**: When `scan_paths: ["src", "tests", "docs"]` and only `docs/` exists, scan warns about the missing paths, processes `docs/`, and reports the files it found (not zero).

5. **AC5 — Error messages displayed in summary**: When the scan summary has errors, the summary panel shows each error message (not just "Errors: 1").

6. **AC6 — All paths missing still reports errors clearly**: When ALL configured scan_paths are missing, scan completes with zero files and the summary shows exactly which paths were missing.

7. **AC7 — Existing tests pass**: All existing scan CLI tests (excluding pre-existing failures) continue to pass.

## Risks & Assumptions

- **Risk**: `validate_configs()` imports doctor module which may pull in dependencies not needed for scan. *Mitigation*: Use lazy import inside the scan function.
- **Assumption**: Doctor's `validate_configs()` function is stateless and safe to call without side effects.
- **Assumption**: The pre-existing test failure (`test_given_verbose_flag_when_scan_then_shows_more_output`) is unrelated and already failing on the base branch.

## Open Questions

None — all resolved in clarifications session.

## Testing Strategy

- **Approach**: Lightweight — targeted tests for new behavior
- **Rationale**: Changes are surgical (3 files); existing test suite covers baseline behavior
- **Focus Areas**: (1) scan output with broken config YAML, (2) scanner behavior with missing scan_paths, (3) error message display in summary
- **Mock Usage**: No mocks — use real temp directories with broken/valid config files
- **Excluded**: Full TDD red-green-refactor cycle; existing test coverage is sufficient for unchanged code paths

## Documentation Strategy

- **Location**: No new documentation
- **Rationale**: Behavior is self-evident from scan output — warnings appear when config is broken

## Clarifications

### Session 2026-04-14

**Q1 — Workflow Mode**: Simple (CS-2, single phase, quick path)

**Q2 — Testing Strategy**: Lightweight — targeted tests for new behavior, no full TDD

**Q3 — Mock Usage**: Avoid mocks entirely — use real temp dirs with broken/valid configs

**Q4 — Documentation Strategy**: No new documentation — behavior is self-evident from output

**Q5 — Exit Code on Config Warning**: No — config warnings do NOT change exit code. Scan succeeded, config is a warning only. Updated Non-Goals accordingly.

**Q6 — Domain Review**: Domains confirmed as specified — cli (modify), adapters (modify), doctor (consume). No new domains.

## Workshop Opportunities

| Topic | Type | Why Workshop | Key Questions |
|-------|------|--------------|---------------|
| None identified | — | Changes are surgical and well-scoped from research | — |
