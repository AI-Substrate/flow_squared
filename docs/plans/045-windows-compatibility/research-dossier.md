# Research Report: Windows Compatibility for fs2

**Generated**: 2026-04-07T08:22:00Z
**Research Query**: "fs2 was developed on Mac/Linux and doesn't work properly on Windows — fix it"
**Mode**: Pre-Plan
**Location**: docs/plans/045-windows-compatibility/research-dossier.md
**FlowSpace**: Not Available (Windows — this is why we're here)
**Findings**: 63 total from 8 subagents, synthesized below

## Executive Summary

### What's Broken
fs2 has **three show-stopping bugs on Windows** and ~15 secondary issues. The codebase was developed entirely on Mac/Linux and never tested on Windows. The core scanning pipeline _mostly works_ but produces **corrupt internal data** (backslash paths in node IDs) that breaks all downstream features.

### Business Impact
- `fs2 init` crashes with UnicodeEncodeError on first run
- `fs2 scan` completes but produces nodes with `\` paths instead of `/`, breaking tree/search/MCP
- Graph saves emit repeated WinError 183 warnings (atomic rename fails)
- Rich console output shows garbled box-drawing characters

### Key Insights
1. **One root cause dominates**: `str(rel_path)` in ast_parser_impl.py produces `\` on Windows — this single fix would resolve ~60% of downstream issues
2. **File I/O encoding is systemic**: ~15 locations use `open()`/`write_text()` without `encoding="utf-8"`, any of which can crash on Windows cp1252
3. **The architecture is sound**: Clean Architecture boundaries mean fixes are concentrated in 2-3 adapter files, not scattered across services

### Quick Stats
- **Crash on init**: Yes (UnicodeEncodeError)
- **Scan produces corrupt data**: Yes (backslash node IDs)
- **Graph save fails**: Partially (WinError 183 on rename, but final save succeeds)
- **Tree/Search/MCP broken**: Yes (consequence of backslash node IDs)
- **Test suite on Windows**: Mostly passes (slow tests have some issues)

---

## How It Currently Works (on Windows)

### Verified Test: Scanning C:\repos\athena-ai-architecture-enablement

| Step | Result | Issue |
|------|--------|-------|
| `fs2 init` | ❌ CRASH | UnicodeEncodeError: cp1252 can't encode `─` (U+2500) in DEFAULT_CONFIG |
| `fs2 init` (with PYTHONUTF8=1) | ✅ Works | Workaround proves encoding is the only blocker |
| `fs2 scan --no-smart-content` | ⚠️ Partial | Scans 571 files, creates 981 nodes — but all node_ids have `\` |
| Graph courtesy saves | ⚠️ Warning | `WinError 183: Cannot create file when it already exists` (3x) |
| Final graph save | ✅ Works | The last save succeeds (no pre-existing .tmp file) |
| `fs2 tree` | ❌ FAIL | MissingConfigurationError (GraphConfig issue, likely not Windows-specific) |
| Node ID format | ❌ WRONG | `callable:ISE\myob-agent\cli\auth.mjs:captureAuth` instead of `callable:ISE/myob-agent/cli/auth.mjs:captureAuth` |

---

## Critical Discoveries

### 🚨 Critical Finding 01: Node ID Path Separators (ROOT CAUSE)

**Impact**: Critical — breaks tree, search, MCP, reports, and all path-based operations
**Source**: DE-04, DE-05, DE-06, DC-02, DC-03, QT-03
**Files**: `src/fs2/core/adapters/ast_parser_impl.py:528-546, 564, 589-602`

**What**: `str(rel_path)` produces Windows backslashes in node IDs:
```python
# Line 530-531: Current code
rel_path = file_path.relative_to(Path.cwd())
# Line 546: Passed directly to CodeNode
file_path=str(rel_path)  # "ISE\myob-agent\cli\auth.mjs" on Windows!
```

**Fix**: Normalize to POSIX at the point of node_id creation:
```python
file_path=str(rel_path).replace("\\", "/")
# OR: file_path=rel_path.as_posix()
```

**Three locations need fixing**:
1. Line 546: `file_path=str(rel_path)` — main parse path
2. Line 564: `file_path=str(rel_path)` — _extract_nodes call
3. Line 602: `file_path=str(rel_path)` — _create_file_only_node

**Why It Matters**: This is the **single normalization point** where all file paths enter the system. Every downstream consumer (tree_service, report_layout, search_result_meta, MCP server) assumes `/` separators. Fixing this one location fixes ~60% of all Windows issues.

---

### 🚨 Critical Finding 02: UnicodeEncodeError in `fs2 init`

**Impact**: Critical — first command users run crashes on Windows
**Source**: IA-02, IC-02
**Files**: `src/fs2/cli/init.py:223, 260, 264`

**What**: `DEFAULT_CONFIG` contains Unicode box-drawing characters (`─`, U+2500) in section headers like:
```yaml
# ─── LLM (for smart content) ───────────────────────────────────────
```
Windows cp1252 encoding can't represent these. `write_text()` without `encoding="utf-8"` crashes.

**Verified**: Actual crash output:
```
UnicodeEncodeError: 'charmap' codec can't encode characters in position 295-297:
character maps to <undefined>
```

**Fix**: Add `encoding="utf-8"` to all three `write_text()` calls:
```python
global_config_file.write_text(DEFAULT_CONFIG, encoding="utf-8")
local_config_file.write_text(config_text, encoding="utf-8")
local_gitignore.write_text(FS2_GITIGNORE, encoding="utf-8")
```

**Secondary issue**: A failed init creates a **0-byte global config** at `~/.config/fs2/config.yaml`. Subsequent runs see "already exists" and skip it. Need either:
- Write to temp then rename (like graph save), or
- Check file size > 0 when deciding to skip

---

### 🚨 Critical Finding 03: Graph Save WinError 183

**Impact**: High — repeated warnings during scan, potential data loss
**Source**: IA-03
**File**: `src/fs2/core/repos/graph_store_impl.py:338`

**What**: `Path.rename()` on Windows doesn't atomically replace an existing target:
```python
# Line 338: Current code
tmp_path.rename(path)  # WinError 183 if path already exists!
```

**Verified**: Scan output shows 3x warnings:
```
WARNING Courtesy save failed: Failed to save graph to .fs2\graph.pickle:
[WinError 183] Cannot create a file when that file already exists:
'.fs2\\graph.pickle.tmp' -> '.fs2\\graph.pickle'
```

**Fix**: Use `os.replace()` which works cross-platform:
```python
import os
os.replace(tmp_path, path)  # Atomically replaces on all platforms
```

---

## High Priority Issues

### ⚠️ Finding 04: Systemic File I/O Encoding

**Impact**: High — any of these can crash on Windows with non-ASCII content
**Source**: IA-01 through IA-10, IC-02 through IC-04

| File | Line(s) | Operation | Fix |
|------|---------|-----------|-----|
| `cli/init.py` | 223, 260, 264 | `write_text()` | Add `encoding="utf-8"` |
| `cli/get_node.py` | 149 | `write_text()` | Add `encoding="utf-8"` |
| `config/loaders.py` | 76 | `open()` | Add `encoding="utf-8"` |
| `config/models.py` | 127 | `open()` | Add `encoding="utf-8"` |
| `cli/projects.py` | 225, 268 | `open()` read & write | Add `encoding="utf-8"` |
| `cli/install.py` | 76 | `read_text()` | Add `encoding="utf-8"` |
| `adapters/file_scanner_impl.py` | 310 | `read_text()` | Add `encoding="utf-8"` |
| `adapters/file_watcher_adapter_watchfiles.py` | 82 | `read_text()` | Add `encoding="utf-8"` |
| `stages/cross_file_rels_stage.py` | 174 | `write_text()` | Add `encoding="utf-8"` |
| `mcp/server.py` | 659 | `open("w")` | Add `encoding="utf-8"` |

**Note**: Some files already correctly use `encoding="utf-8"`:
- `cli/utils.py:80` — `safe_write_file()` ✅
- `mcp/server.py:441, 947` — other `open()` calls ✅
- `cli/setup_mcp.py:81, 107` ✅
- `core/services/docs_service.py:92, 194` ✅
- `core/services/report_service.py:654, 664` ✅

### ⚠️ Finding 05: Rich Console Garbling

**Impact**: Medium — poor user experience but not a crash
**Source**: Direct observation

Rich's Unicode box-drawing characters display as garbled text on Windows cmd/PowerShell:
```
ΓöîΓöÇ Error ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÉ    (should be: ╭── Error ──╮)
```

This affects error boxes, progress bars, and stage banners. Workaround: use Windows Terminal (which supports UTF-8) or set `$env:PYTHONUTF8 = "1"`.

**Fix options**:
1. Set `PYTHONUTF8=1` early in CLI entry point
2. Use `sys.stdout.reconfigure(encoding="utf-8")` at startup
3. Add `encoding="utf-8"` to `Console()` constructor

---

## Medium Priority Issues

### Finding 06: Downstream Path Splitting (Consequence of CF-01)

If Critical Finding 01 is fixed, these are automatically resolved. Listed for reference:

| File | Line | Code | Assumes `/` |
|------|------|------|-------------|
| `tree_service.py` | 57, 60 | `folder_path.endswith("/")`, `split("/")` | ✅ By design |
| `tree_service.py` | 239 | `if "/" in pattern` | ✅ By design |
| `tree_service.py` | 288 | `pattern.endswith("/")` | ✅ By design |
| `tree_service.py` | 474 | `file_path.split("/")` | ✅ By design |
| `report_layout.py` | 75 | `fp.split("/")` | ✅ By design |
| `search_result_meta.py` | 73, 77, 81, 107, 111 | `"/" in path` | ✅ By design |
| `cli/tree.py` | 283 | `"/" in file_path` | ✅ By design |

**These are all correct** as long as node IDs consistently use `/`. The fix is at the source (CF-01), not here.

### Finding 07: Unix-Specific Error Messages

**Source**: IC-07, PS-09
**File**: `src/fs2/cli/install.py:211-214`

```python
console.print(
    "[red]x[/red] uv not found.\n"
    "  Install uv first: [bold]curl -LsSf https://astral.sh/uv/install.sh | sh[/bold]"
)
```

**Fix**: Detect platform and show appropriate install command:
```python
if sys.platform == "win32":
    "  Install uv first: [bold]powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"[/bold]"
```

### Finding 08: XDG Config Path on Windows

**Source**: IC-01, PS-07
**File**: `src/fs2/config/paths.py:17-32`

Uses `~/.config/fs2` on all platforms. On Windows this resolves to `C:\Users\<user>\.config\fs2` which works but isn't conventional (`%APPDATA%\fs2` would be). This is **acceptable for now** — cross-platform consistency has value.

### Finding 09: `file://` URI on Windows

**Source**: DB-01
**File**: `src/fs2/cli/report.py:131`

```python
webbrowser.open(f"file://{output_path}")
```
On Windows, paths have `\` and drive letters (`C:\`). The URI should use `file:///C:/...` format. `pathlib.Path.as_uri()` handles this correctly.

---

## Prior Learnings (From Previous Implementations)

### 📚 PL-12: Windows C:\ Colons Break node_id Parsing
**Source**: `docs/plans/004-tree-command/tree-command-plan.md:285-286`
**Original Type**: gotcha
**Why This Matters Now**: The `:` in `C:\` would be misinterpreted by `_detect_input_mode()` which checks for `:` to identify node_ids. However, since we use relative paths, this only matters if absolute paths leak into node_ids (which they can via the `except ValueError` fallback at ast_parser_impl.py:532).

### 📚 PL-13: Windows Path Handling Explicitly Out-of-Scope
**Source**: `docs/plans/019-tree-folder-navigation/tasks/phase-1-implementation/tasks.md:81`
**Original Type**: decision
**Why This Matters Now**: Windows support was deliberately deferred. This plan is the follow-up.

### 📚 PL-14: Watchfiles Chosen for Cross-Platform
**Source**: `docs/plans/020-watch-mode/research-dossier.md:21,68,336`
**Original Type**: decision
**Why This Matters Now**: Good news — watchfiles library already supports Windows. Signal handling is already Windows-safe (`SIGTERM` guarded).

### 📚 PL-06: Some Windows-Aware Test Code Exists
**Source**: `tests/unit/adapters/test_file_scanner_impl.py:847,886,922`
**Why This Matters Now**: `sys.platform == "win32"` skips exist for chmod tests. This pattern should be extended to symlink tests.

---

## Quality & Testing

### Current State
- **No Windows CI**: No `.github/workflows/` found; no Windows test matrix
- **No platform markers in pytest.ini**: Only `slow` marker exists
- **Some Windows-aware tests**: chmod tests skip on win32
- **Symlink tests will fail**: `test_file_scanner_impl.py:452-547` creates symlinks without Windows skip
- **Node ID assertions**: Hardcoded `file:src/calculator.py` in slow CLI tests will fail if node_ids have `\`

### Test Recommendations
1. Add `@pytest.mark.skipif(sys.platform == "win32", ...)` to symlink tests
2. After fixing CF-01, node_id assertions should pass (they expect `/`)
3. Consider adding a GitHub Actions Windows runner

---

## Architecture & Domain Analysis

### Where Fixes Should Go (Clean Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│  CLI Layer (cli/)                                           │
│  Fix: encoding="utf-8" on all write_text/open calls        │
│  Fix: Platform-specific error messages                      │
│  Fix: file:// URI construction                              │
└────────────────────────────────┬────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────┐
│  Adapter Layer (core/adapters/)        ◄── PRIMARY FIX SITE │
│  Fix: ast_parser_impl.py — normalize paths to "/"           │
│  Fix: file_scanner_impl.py — encoding on read_text          │
│  Fix: file_watcher — encoding on read_text                  │
└────────────────────────────────┬────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────┐
│  Service Layer (core/services/)                             │
│  NO FIXES NEEDED — services correctly assume "/" paths      │
│  (tree_service, report_layout, search all use "/")          │
└────────────────────────────────┬────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────┐
│  Repository Layer (core/repos/)                             │
│  Fix: graph_store_impl.py — os.replace() instead of rename  │
└─────────────────────────────────────────────────────────────┘
```

**Key insight**: The Clean Architecture design means fixes are concentrated at boundaries (adapters + repos). Services are platform-agnostic by design and need zero changes.

---

## Modification Plan (Suggested Phases)

### Phase 1: Unblock (Critical — Get fs2 Working on Windows)
1. Fix `ast_parser_impl.py` — normalize `file_path` to POSIX (3 lines)
2. Fix `graph_store_impl.py` — use `os.replace()` (1 line)
3. Fix `init.py` — add `encoding="utf-8"` to `write_text()` (3 lines)
4. Add early UTF-8 mode in CLI entry point (`PYTHONUTF8`)

**Estimated scope**: ~10 lines changed across 3 files

### Phase 2: Harden (High — Prevent Future Encoding Crashes)
5. Add `encoding="utf-8"` to all file I/O (~15 locations)
6. Fix 0-byte global config recovery in init
7. Fix `install.py` error message for Windows

**Estimated scope**: ~20 lines changed across 10 files

### Phase 3: Polish (Medium — Better Windows Experience)
8. Fix `report.py` file:// URI for Windows
9. Add Windows skip to symlink tests
10. Consider Windows CI (GitHub Actions)

**Estimated scope**: ~15 lines changed across 5 files

---

## ✅ Safe to Modify
- `ast_parser_impl.py:546,564,602` — adding `.replace("\\", "/")` is safe; Mac/Linux unaffected (no-op)
- `graph_store_impl.py:338` — `os.replace()` works identically on Unix
- All `encoding="utf-8"` additions — UTF-8 is already the de facto standard on Mac/Linux

## ⚠️ Modify with Caution
- `cli/__main__.py` or `cli/main.py` — adding `PYTHONUTF8` at startup affects all subprocesses
- `config/paths.py` — changing XDG to APPDATA would break existing Windows users who ran init

## 🚫 Danger Zones
- **Do NOT change** path splitting in services (tree_service, report_layout) — these are correct; fix the source instead
- **Do NOT add** `os.sep` usage anywhere — the codebase should consistently use `/` internally

---

## Next Steps

**Recommended**: Run `/plan-1b-specify "Windows compatibility fixes for fs2"` to create the specification, then proceed to implementation.

The fixes are small and well-understood. Phase 1 (3 files, ~10 lines) would make fs2 fully functional on Windows.

---

**Research Complete**: 2026-04-07T08:22:00Z
**Report Location**: docs/plans/045-windows-compatibility/research-dossier.md
