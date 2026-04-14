# Research Report: fs2 scan discovers zero files in non-code repositories

**Generated**: 2026-04-14T07:40:00Z
**Research Query**: "running a scan in /Users/jordanknight/github/novels — no files scanned at all"
**Mode**: Bug Investigation
**FlowSpace**: Not Available (no graph.pickle on this branch)
**Findings**: 12 total (6 critical)

## Executive Summary

### What's Happening
When running `fs2 scan` in `/Users/jordanknight/github/novels`, zero files are discovered and the scan reports "COMPLETED WITH ERRORS — Errors: 1". The error message itself is never displayed to the user.

### Root Cause Chain
Three bugs compound to produce this failure:

1. **Broken YAML in project config** — Line 23 of `novels/.fs2/config.yaml` has an uncommented box-drawing separator (`─────────────────────────────`) that causes `yaml.safe_load()` to fail silently
2. **User-level config has restrictive scan_paths** — `~/.config/fs2/config.yaml` sets `scan_paths: ["src", "tests", "docs"]`, which becomes the effective config when project config fails to parse
3. **Scanner aborts on first missing path** — When `src/` doesn't exist in the novels repo, the scanner raises `FileScannerError` and never processes `tests/` or `docs/`

### Key Insights
1. The CLI prints "✓ Loaded .fs2/config.yaml" even when YAML parsing completely fails
2. Error messages from scanner failures are counted but never displayed to the user
3. The init template is NOT the source of the broken YAML — all separators are properly commented in `DEFAULT_CONFIG`

## How It Currently Works

### Config Loading Pipeline
```
User YAML (~/.config/fs2/config.yaml)  →  Project YAML (.fs2/config.yaml)  →  Env vars
                 ↓ deep_merge                    ↓ deep_merge (returns {} on parse fail)
                        ↓
                  Merged config → ScanConfig(scan_paths=["src","tests","docs"])
```

| Stage | File | What Happens |
|-------|------|-------------|
| YAML load | `config/loaders.py:58-81` | `load_yaml_config()` returns `{}` on YAML error, logs only at DEBUG |
| Config merge | `config/service.py:206-210` | User config wins when project config is empty |
| CLI feedback | `cli/scan.py:109-110` | "✓ Loaded" printed unconditionally after `FS2ConfigurationService()` |

### Scanner Execution
```
FileSystemScanner.scan()
  for each scan_path in scan_paths:     ← iterates ["src", "tests", "docs"]
    Path("src").resolve()               ← /Users/jordanknight/github/novels/src
    if not scan_path.exists():           ← src/ doesn't exist!
      raise FileScannerError(...)        ← ABORTS ENTIRE SCAN
```

| Stage | File | What Happens |
|-------|------|-------------|
| Discovery | `adapters/file_scanner_impl.py:111-119` | Raises on first missing path |
| Error catch | `stages/discovery_stage.py:63-68` | Catches error, sets results=[] |
| CLI display | `cli/scan.py:474-526` | Shows "Errors: 1" but not the error text |

## Critical Discoveries

### 🚨 CD-01: YAML parse failure is silent — misleading "✓ Loaded" message
**Impact**: Critical
**Files**: `src/fs2/config/loaders.py:79-81`, `src/fs2/cli/scan.py:109-110`
**What**: When `.fs2/config.yaml` contains invalid YAML, `load_yaml_config()` returns `{}` (empty dict) and logs only at DEBUG level. The CLI then prints "✓ Loaded .fs2/config.yaml" regardless.
**Why It Matters**: Users have zero indication their config wasn't loaded. They see a success checkmark.
**Required Action**: Check config parse result; show warning if YAML failed.

### 🚨 CD-02: Scanner fails hard on first missing scan_path
**Impact**: Critical
**Files**: `src/fs2/core/adapters/file_scanner_impl.py:115-119`
**What**: `FileSystemScanner.scan()` raises `FileScannerError` on the first non-existent path, aborting the entire scan. Even if 2 of 3 paths exist, zero files are returned.
**Why It Matters**: User-level config scan_paths that work for one project silently break another.
**Required Action**: Warn and skip missing scan_paths instead of aborting. Continue with remaining paths.

### 🚨 CD-03: Error messages never shown to user
**Impact**: Critical  
**Files**: `src/fs2/cli/scan.py:474-526`
**What**: The scan summary shows "Errors: 1" but never prints the actual error strings from `summary.errors`. The error text "Scan path does not exist: /path/to/src" is collected but discarded at display time.
**Why It Matters**: Users see there's an error but have no idea what it is or how to fix it.
**Required Action**: Display error messages in the summary panel.

### 🚨 CD-04: User-level config overrides project config when project YAML breaks
**Impact**: High
**Files**: `src/fs2/config/service.py:179-210`
**What**: The config merge pipeline `deep_merge(user_raw, project_raw)` works correctly in normal operation. But when project config fails to parse (`{}`), the user config "wins" for ALL settings including scan_paths.
**Why It Matters**: A single YAML typo in the project config silently changes which directories get scanned.
**Required Action**: This is a consequence of CD-01. Fixing the warning would alert users.

### ⚠️ CD-05: Broken YAML NOT from init template
**Impact**: Informational
**Files**: `src/fs2/cli/init.py:18-138` (DEFAULT_CONFIG)
**What**: The `DEFAULT_CONFIG` template in `init.py` has all box-drawing separators properly commented with `#`. The broken line 23 in the novels config was introduced by manual edit or copy-paste.
**Why It Matters**: Not a systemic init bug — isolated to this specific config file.

### ⚠️ CD-06: DiscoveryStage discards partial results on error
**Impact**: Medium
**Files**: `src/fs2/core/services/stages/discovery_stage.py:63-68`
**What**: If the scanner processes some paths successfully before hitting a missing one, the DiscoveryStage catches the error and sets `scan_results = []`, discarding any files already found.
**Why It Matters**: Even if the scanner were fixed to warn-and-skip, the stage would need updating to handle partial results.

## Immediate Fix (for the novels repo)

Fix line 23 in `/Users/jordanknight/github/novels/.fs2/config.yaml`:

```diff
- ─────────────────────────────
+ # ─────────────────────────────
```

This allows the project config to parse, which sets `scan_paths: ["."]`, overriding the user-level `["src", "tests", "docs"]`.

## Recommended fs2 Fixes (3 improvements)

### Fix 1: Warn on YAML parse failure (CD-01)
**File**: `src/fs2/config/loaders.py` + `src/fs2/cli/scan.py`
- `load_yaml_config()` should return a sentinel or flag indicating parse failure
- CLI should show "⚠️ Failed to parse .fs2/config.yaml — using defaults" instead of "✓ Loaded"

### Fix 2: Skip missing scan_paths with warning (CD-02)
**File**: `src/fs2/core/adapters/file_scanner_impl.py`
- Change `raise FileScannerError(...)` to `logger.warning(...)` + `continue`
- Collect warnings for display but don't abort

### Fix 3: Display error messages in summary (CD-03)
**File**: `src/fs2/cli/scan.py`
- In `_display_final_summary()`, iterate `summary.errors` and print each one
- Use `console.print_error()` or similar for visibility

## File Inventory

### Core Files Investigated
| File | Purpose | Relevance |
|------|---------|-----------|
| `src/fs2/config/loaders.py` | YAML config loading | Silent parse failure |
| `src/fs2/config/service.py` | Config merge pipeline | User/project merge |
| `src/fs2/config/objects.py` | ScanConfig defaults | `scan_paths=["."]` |
| `src/fs2/core/adapters/file_scanner_impl.py` | File discovery | Hard fail on missing path |
| `src/fs2/core/services/stages/discovery_stage.py` | Discovery pipeline stage | Error swallowing |
| `src/fs2/cli/scan.py` | CLI scan command | Misleading feedback |
| `src/fs2/cli/init.py` | Init template | Template is correct |

### External Files Involved
| File | Purpose |
|------|---------|
| `~/.config/fs2/config.yaml` | User-level config with scan_paths: ["src","tests","docs"] |
| `/Users/jordanknight/github/novels/.fs2/config.yaml` | Broken YAML on line 23 |

## Next Steps

- **Quick fix**: Comment out line 23 in the novels config.yaml
- **Proper fix**: Run `/plan-1b-specify` to create a spec for the 3 fs2 improvements above
- **Alternative**: Run `/plan-3-architect` if jumping straight to implementation plan

---

**Research Complete**: 2026-04-14T07:42:00Z
**Report Location**: docs/plans/049-scan-zero-files-bug/research-dossier.md
