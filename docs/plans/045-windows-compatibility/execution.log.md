# Execution Log — 045 Windows Compatibility

**Plan**: docs/plans/045-windows-compatibility/windows-compatibility-plan.md
**Mode**: Simple
**Branch**: 045-windows-compatibility
**Started**: 2026-04-07

---

## Task Log

### T001: Normalize paths to POSIX in AST parser ✅
Changed `file_path=str(rel_path)` → `file_path=str(rel_path).replace("\\", "/")` at 3 locations in `ast_parser_impl.py` (lines 546, 564, 602).
**Evidence**: Graph scan produces 1091 nodes, 0 with backslash paths. Before fix: 100% had backslashes.

### T002: Fix atomic graph save ✅
Changed `tmp_path.rename(path)` → `os.replace(tmp_path, path)` at `graph_store_impl.py:338`. Added `import os`.
**Evidence**: Scan completes with zero WinError 183 warnings, all 3 courtesy saves succeed.
**Discovery**: Existing test `test_save_cleans_up_tmp_on_failure` mocked `Path.rename` — updated to mock `os.replace`.

### T003: UTF-8 encoding on init writes ✅
Added `encoding="utf-8"` to 3 `write_text()` calls in `init.py` (lines 223, 260, 264).
**Evidence**: `fs2 init` completes successfully on Windows, creates valid config files.

### T004: 0-byte global config recovery ✅
Changed condition from `global_config_file.exists()` to `global_config_file.exists() and global_config_file.stat().st_size > 0` at `init.py:218`.
**Evidence**: After cleaning up 0-byte file, `fs2 init` creates valid global config.

### T005: UTF-8 encoding sweep ✅
Added `encoding="utf-8"` to 11 file I/O locations across 8 files:
- `get_node.py:149`, `loaders.py:76`, `models.py:127`, `projects.py:225,268`
- `install.py:76`, `file_scanner_impl.py:310`, `file_watcher_adapter_watchfiles.py:82`
- `cross_file_rels_stage.py:174`, `mcp/server.py:659`

### T006: Set PYTHONUTF8 at CLI entry point ✅
Added `os.environ.setdefault("PYTHONUTF8", "1")` + `sys.stdout/stderr.reconfigure(encoding="utf-8")` to `__main__.py`.
**Discovery**: `PYTHONUTF8` via `os.environ` only affects subprocesses — the current process needs `stream.reconfigure()` for immediate effect.

### T007: Platform-detect install error message ✅
Added `sys.platform == "win32"` check in `install.py` — shows PowerShell command on Windows, curl on Unix.

### T008: Fix report file:// URI ✅
Changed `f"file://{output_path}"` → `output_path.as_uri()` in `report.py:131`.

### T009: Windows skip on symlink tests ✅
Added `@pytest.mark.skipif(sys.platform == "win32", reason="symlinks unreliable on Windows")` to `TestFileSystemScannerSymlinks` class.

### T010: Integration verify ✅
- `fs2 init`: ✅ Creates valid config (AC1, AC2)
- `fs2 scan --no-smart-content`: ✅ 624 files, 1104 nodes, zero WinError warnings (AC4)
- Node IDs: ✅ 0 backslashes out of 1091 nodes (AC3)
- `fs2 tree "ISE/myob-agent/cli/"`: ✅ Hierarchical grouping correct (AC5)
- Console rendering: ✅ Emojis render with reconfigure (AC7)

## Discoveries & Learnings

| # | Type | Discovery |
|---|------|-----------|
| D1 | gotcha | `os.environ["PYTHONUTF8"]` only affects subprocesses; current process needs `sys.stdout.reconfigure()` |
| D2 | gotcha | Existing test `test_save_cleans_up_tmp_on_failure` mocked `Path.rename` — needed update for `os.replace` |
| D3 | insight | 18 pre-existing test failures on Windows (sklearn TSNE, asyncio event loop, dotenv, XDG paths, chmod) — none caused by our changes |
| D4 | insight | Tree command fails without `--graph-file` due to pre-existing `GraphConfig` not auto-populated (not Windows-specific) |
| D5 | insight | Box-drawing chars still garble in terminals that don't support UTF-8 (e.g., cmd.exe) — by design per Non-Goal NG2 |

## Files Changed (16)

| File | Domain | Change |
|------|--------|--------|
| `src/fs2/__main__.py` | cli | PYTHONUTF8 + stdout reconfigure |
| `src/fs2/core/adapters/ast_parser_impl.py` | adapters | Path normalization (3 locations) |
| `src/fs2/core/repos/graph_store_impl.py` | repos | os.replace() + import os |
| `src/fs2/cli/init.py` | cli | UTF-8 encoding (3 writes) + 0-byte recovery |
| `src/fs2/cli/get_node.py` | cli | UTF-8 encoding |
| `src/fs2/cli/install.py` | cli | UTF-8 encoding + platform message + import sys |
| `src/fs2/cli/projects.py` | cli | UTF-8 encoding (2 locations) |
| `src/fs2/cli/report.py` | cli | Path.as_uri() |
| `src/fs2/config/loaders.py` | config | UTF-8 encoding |
| `src/fs2/config/models.py` | config | UTF-8 encoding |
| `src/fs2/core/adapters/file_scanner_impl.py` | adapters | UTF-8 encoding |
| `src/fs2/core/adapters/file_watcher_adapter_watchfiles.py` | adapters | UTF-8 encoding |
| `src/fs2/core/services/stages/cross_file_rels_stage.py` | services | UTF-8 encoding |
| `src/fs2/mcp/server.py` | mcp | UTF-8 encoding |
| `tests/unit/adapters/test_file_scanner_impl.py` | tests | Windows symlink skip |
| `tests/unit/repos/test_graph_store_impl.py` | tests | Update mock for os.replace |
