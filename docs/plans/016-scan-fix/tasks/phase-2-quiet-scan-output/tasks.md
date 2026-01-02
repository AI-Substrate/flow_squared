# Phase 2: Quiet Scan Output – Tasks & Alignment Brief

**Phase**: Phase 2: Quiet Scan Output
**Spec**: [../../scan-fix-spec.md](../../scan-fix-spec.md)
**Plan**: [../../scan-fix-plan.md](../../scan-fix-plan.md)
**Date**: 2026-01-02

---

## Executive Briefing

### Purpose

This phase improves scan UX by hiding noisy per-file skip messages and showing a concise summary instead. Currently, scanning a codebase with Python cache files produces hundreds of "Unknown language for X.pyc, skipping" messages that obscure useful output.

### What We're Building

- **Quiet default behavior**: Change `logger.warning()` to `logger.debug()` for skip messages
- **Skip tracking**: Track skipped files by extension in the parser
- **Summary display**: Show "Skipped: 89 .pyc, 12 .pkl" in the final scan panel

### User Value

Users get clean scan output by default while retaining full detail with `--verbose`.

### Example

**Before**:
```
Unknown language for /path/test.pyc, skipping
Unknown language for /path/data.pkl, skipping
Unknown language for /path/cache.pyc, skipping
... (100+ more lines)

┌─ PARSING ─────────────────────┐
│ ✓ Scanned 150 files           │
│ ✓ Created 1,234 nodes         │
└───────────────────────────────┘
```

**After** (skip summary appears after PARSING, before SMART CONTENT):
```
┌─ PARSING ──────────────────────────────┐
│ ✓ Scanned 150 files                    │
│ ✓ Created 1,234 nodes                  │
│ Skipped: 89 .pyc, 12 .pkl, 3 .so       │
└────────────────────────────────────────┘

┌─ SMART CONTENT ────────────────────────┐
│ ...                                    │
```

---

## Objectives & Scope

### Objective

Reduce scan output noise while preserving skip information in summary form.

### Goals

- ✅ Change skip messages from WARNING to DEBUG level
- ✅ Track skipped files by extension in TreeSitterParser
- ✅ Expose skip counts via parser method
- ✅ Collect skip metrics in ParsingStage
- ✅ Display skip summary in CLI final panel

### Non-Goals

- ❌ Separate tracking of "unknown language" vs "binary file" skips (combined summary per user decision)
- ❌ Truncating extension list (show all per user decision)
- ❌ Adding skip info to graph/pickle (CLI display only)

---

## Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Subtasks | Notes |
|--------|-----|------|----|------|--------------|------------------|------------|----------|-------|
| [x] | T001 | Implement skip tracking and summary display | 2 | Core | -- | Multiple (see subtask) | Skip summary appears in scan output | [001](./001-subtask-skip-summary.md), [002](./002-subtask-extension-breakdown-summary.md) | Both subtasks complete |

---

## Alignment Brief

### Critical Findings Affecting This Phase

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | High | Skip messages use `logger.warning()` at lines 362, 381 in ast_parser_impl.py | Change to `logger.debug()` |
| 02 | High | ParsingStage doesn't track skips - empty results are silently ignored | Add skip metric collection |
| 03 | Medium | SmartContentService/EmbeddingService have `skipped` counter patterns to follow | Replicate pattern in parser |
| 04 | Medium | CLI uses `_display_final_summary()` function for scan output | Add skip line there |

### Invariants

- Verbose mode (`--verbose`) still shows all per-file skip messages
- No changes to graph/pickle structure
- All existing tests pass

### Files to Modify

| File | Changes |
|------|---------|
| `/workspaces/flow_squared/src/fs2/core/adapters/ast_parser_impl.py` | Change warning→debug, add skip tracking |
| `/workspaces/flow_squared/src/fs2/core/services/stages/parsing_stage.py` | Query parser for skip counts |
| `/workspaces/flow_squared/src/fs2/cli/scan.py` | Display skip summary |
| `/workspaces/flow_squared/tests/unit/adapters/test_ast_parser_impl.py` | Add skip tracking tests |

### Test Plan

**Testing Approach**: Full TDD

1. **Unit**: Test `get_skip_summary()` returns correct counts by extension
2. **Unit**: Test skip counts reset after reading
3. **Integration**: Verify skip metrics flow to ScanSummary

### Commands

```bash
# Run tests
UV_CACHE_DIR=.uv_cache uv run pytest tests/unit/adapters/test_ast_parser_impl.py -v

# Run lint
uv run ruff check src/fs2/core/adapters/ast_parser_impl.py

# Full test suite
just test
```

### Ready Check

- [x] Phase 2 added to plan
- [x] Critical findings documented
- [x] Files to modify identified
- [x] Subtask dossier created (001-subtask-skip-summary)

---

## Discoveries & Learnings

_Populated during implementation by plan-6. Log anything of interest to your future self._

| Date | Task | Type | Discovery | Resolution | References |
|------|------|------|-----------|------------|------------|
| | | | | | |

**Types**: `gotcha` | `research-needed` | `unexpected-behavior` | `workaround` | `decision` | `debt` | `insight`

---

**Execution Log**: `execution.log.md` (created by /plan-6-implement-phase)
**Status**: COMPLETE (T001 with both subtasks)
