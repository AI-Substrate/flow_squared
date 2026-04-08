# Windows Compatibility Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-04-07
**Spec**: docs/plans/045-windows-compatibility/windows-compatibility-spec.md
**Research**: docs/plans/045-windows-compatibility/research-dossier.md
**Status**: COMPLETE
**Readiness**: READY (user override on 1 HIGH — services encoding fix accepted as mechanical)

## Summary

fs2 was developed entirely on Mac/Linux and has three show-stopping bugs on Windows: node IDs contain backslashes instead of forward slashes (breaking tree/search/MCP), `fs2 init` crashes with UnicodeEncodeError, and graph saves fail with WinError 183. This plan fixes all three critical bugs plus ~15 secondary encoding/polish issues across 15 files. All fixes are backward-compatible no-ops on Mac/Linux.

## Target Domains

| Domain | Status | Relationship | Role |
|--------|--------|-------------|------|
| adapters | existing | **modify** | Normalize file paths to POSIX at AST parser boundary; add UTF-8 encoding to file scanner/watcher |
| repos | existing | **modify** | Fix atomic file rename for cross-platform graph persistence |
| cli | existing | **modify** | Add UTF-8 encoding to init/projects/get_node; fix platform messages; fix file:// URI; UTF-8 mode at entry point |
| config | existing | **modify** | Add UTF-8 encoding to YAML/config loading |
| mcp | existing | **modify** | Add UTF-8 encoding to one `open()` call |
| services | existing | **consume** | No changes — services correctly assume `/` paths |

Harness: Not applicable (user override — manual scan verification sufficient for CS-2 feature).

## Domain Manifest

| File | Domain | Classification | Rationale |
|------|--------|---------------|-----------|
| `C:\repos\flow_squared\src\fs2\core\adapters\ast_parser_impl.py` | adapters | internal | Normalize `file_path` to POSIX in 3 locations |
| `C:\repos\flow_squared\src\fs2\core\repos\graph_store_impl.py` | repos | internal | Fix `Path.rename()` → `os.replace()` |
| `C:\repos\flow_squared\src\fs2\cli\init.py` | cli | internal | UTF-8 encoding on 3 `write_text()` calls + 0-byte config recovery |
| `C:\repos\flow_squared\src\fs2\cli\get_node.py` | cli | internal | UTF-8 encoding on `write_text()` |
| `C:\repos\flow_squared\src\fs2\cli\install.py` | cli | internal | UTF-8 on `read_text()` + Windows install message |
| `C:\repos\flow_squared\src\fs2\cli\projects.py` | cli | internal | UTF-8 encoding on `open()` read/write |
| `C:\repos\flow_squared\src\fs2\cli\report.py` | cli | internal | Fix `file://` URI for Windows |
| `C:\repos\flow_squared\src\fs2\config\loaders.py` | config | internal | UTF-8 encoding on `open()` |
| `C:\repos\flow_squared\src\fs2\config\models.py` | config | internal | UTF-8 encoding on `open()` |
| `C:\repos\flow_squared\src\fs2\core\adapters\file_scanner_impl.py` | adapters | internal | UTF-8 encoding on `.gitignore` `read_text()` |
| `C:\repos\flow_squared\src\fs2\core\adapters\file_watcher_adapter_watchfiles.py` | adapters | internal | UTF-8 encoding on `.gitignore` `read_text()` |
| `C:\repos\flow_squared\src\fs2\core\services\stages\cross_file_rels_stage.py` | services | internal | UTF-8 encoding on cache `.gitignore` `write_text()` |
| `C:\repos\flow_squared\src\fs2\mcp\server.py` | mcp | internal | UTF-8 encoding on one `open("w")` |
| `C:\repos\flow_squared\src\fs2\__main__.py` | cli | internal | Set `PYTHONUTF8=1` for Windows console output |
| `C:\repos\flow_squared\tests\unit\adapters\test_file_scanner_impl.py` | (tests) | internal | Add Windows skip to symlink tests |
| `C:\repos\flow_squared\tests\unit\repos\test_graph_store_impl.py` | (tests) | internal | Update atomic-save failure test for `os.replace()` |

## Key Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | `str(rel_path)` in ast_parser_impl.py produces `\` on Windows, corrupting all node IDs | Fix in T001 — normalize to POSIX at 3 locations |
| 02 | Critical | `write_text()` in init.py lacks encoding; Unicode box-drawing chars (`─`) crash cp1252 | Fix in T003 — add `encoding="utf-8"` |
| 03 | Critical | `Path.rename()` fails with WinError 183 when target exists on Windows | Fix in T002 — use `os.replace()` |
| 04 | High | ~11 file I/O calls across 8 files lack `encoding="utf-8"` | Fix in T005 — systematic encoding sweep |
| 05 | High | Failed init creates 0-byte global config; subsequent runs skip it | Fix in T004 — check file size > 0 |
| 06 | Medium | Rich console garbled on Windows due to cp1252 default | Fix in T006 — set PYTHONUTF8 at entry point |
| 07 | Low | `install.py` error shows Unix-only `curl \| sh` command | Fix in T007 — platform-detect install message |
| 08 | Low | `report.py` builds `file://` URI incorrectly for Windows paths | Fix in T008 — use `Path.as_uri()` |

## Implementation

**Objective**: Make fs2 fully functional on Windows — init, scan, tree, search, report, and MCP all work without crashes, data corruption, or garbled output.
**Testing Approach**: Lightweight — run existing test suite + integration scan of `C:\repos\athena-ai-architecture-enablement`.

### Tasks

| Status | ID | Task | Domain | Path(s) | Done When | Notes |
|--------|-----|------|--------|---------|-----------|-------|
| [x] | T001 | Normalize file paths to POSIX in AST parser | adapters | `C:\repos\flow_squared\src\fs2\core\adapters\ast_parser_impl.py` | All 3 `file_path=str(rel_path)` changed to `file_path=str(rel_path).replace("\\", "/")` at lines 546, 564, 602 | Finding 01. ROOT CAUSE fix. Mac/Linux no-op. |
| [x] | T002 | Fix atomic graph save for Windows | repos | `C:\repos\flow_squared\src\fs2\core\repos\graph_store_impl.py` | Line 338: `tmp_path.rename(path)` → `os.replace(tmp_path, path)`. Add `import os` if not present. | Finding 03. `os.replace()` works identically on Unix. |
| [x] | T003 | Add UTF-8 encoding to init file writes | cli | `C:\repos\flow_squared\src\fs2\cli\init.py` | Lines 223, 260, 264: all `write_text()` calls include `encoding="utf-8"` | Finding 02. Unblocks first-run on Windows. |
| [x] | T004 | Fix 0-byte global config recovery | cli | `C:\repos\flow_squared\src\fs2\cli\init.py` | Line 218: condition changed from `global_config_file.exists()` to `global_config_file.exists() and global_config_file.stat().st_size > 0` | Finding 05. Prevents "already exists" skip for empty files. |
| [x] | T005 | Add UTF-8 encoding to all remaining file I/O | config, cli, adapters, mcp | See list below | All 11 locations have explicit `encoding="utf-8"` | Finding 04. Prevents cp1252 crashes on any non-ASCII content. |
| [x] | T006 | Set PYTHONUTF8 at CLI entry point | cli | `C:\repos\flow_squared\src\fs2\__main__.py` | `os.environ.setdefault("PYTHONUTF8", "1")` added before app import | Finding 06. Fixes Rich console garbling on Windows. |
| [x] | T007 | Platform-detect install error message | cli | `C:\repos\flow_squared\src\fs2\cli\install.py` | Line ~213: shows Windows PowerShell command when `sys.platform == "win32"`, Unix curl otherwise | Finding 07. |
| [x] | T008 | Fix report file:// URI for Windows | cli | `C:\repos\flow_squared\src\fs2\cli\report.py` | Line 131: `f"file://{output_path}"` → `output_path.as_uri()` | Finding 08. `Path.as_uri()` handles Windows drive letters correctly. |
| [x] | T009 | Add Windows skip to symlink tests | (tests) | `C:\repos\flow_squared\tests\unit\adapters\test_file_scanner_impl.py` | Symlink test functions (~lines 452-547) have `@pytest.mark.skipif(sys.platform == "win32", reason="symlinks unreliable on Windows")` | AC10 |
| [x] | T010 | Integration verify: scan + tree on Windows | — | — | `fs2 init && fs2 scan --no-smart-content && fs2 tree "."` succeeds on `C:\repos\athena-ai-architecture-enablement`. No node_id contains `\`. No WinError warnings. | AC1-AC5, AC7 |

**T005 detail — 11 encoding fix locations:**

| # | File | Line | Current Code | Fix |
|---|------|------|-------------|-----|
| 5a | `C:\repos\flow_squared\src\fs2\cli\get_node.py` | 149 | `file.write_text(json_str)` | Add `encoding="utf-8"` |
| 5b | `C:\repos\flow_squared\src\fs2\config\loaders.py` | 76 | `with open(path) as f:` | Add `encoding="utf-8"` |
| 5c | `C:\repos\flow_squared\src\fs2\config\models.py` | 127 | `with open(config_path) as f:` | Add `encoding="utf-8"` |
| 5d | `C:\repos\flow_squared\src\fs2\cli\projects.py` | 225 | `with open(config_path) as f:` | Add `encoding="utf-8"` |
| 5e | `C:\repos\flow_squared\src\fs2\cli\projects.py` | 268 | `with open(config_path, "w") as f:` | Add `encoding="utf-8"` |
| 5f | `C:\repos\flow_squared\src\fs2\cli\install.py` | 76 | `content = file.read_text()` | Add `encoding="utf-8"` |
| 5g | `C:\repos\flow_squared\src\fs2\core\adapters\file_scanner_impl.py` | 310 | `patterns = gitignore_path.read_text().splitlines()` | Add `encoding="utf-8"` |
| 5h | `C:\repos\flow_squared\src\fs2\core\adapters\file_watcher_adapter_watchfiles.py` | 82 | `gitignore_content = gitignore_path.read_text()` | Add `encoding="utf-8"` |
| 5i | `C:\repos\flow_squared\src\fs2\core\services\stages\cross_file_rels_stage.py` | 174 | `gitignore.write_text(...)` | Add `encoding="utf-8"` |
| 5j | `C:\repos\flow_squared\src\fs2\mcp\server.py` | 659 | `with open(absolute_path, "w") as f:` | Add `encoding="utf-8"` |

### Acceptance Criteria

- [ ] **AC1**: `fs2 init` completes without error on Windows (no UnicodeEncodeError)
- [ ] **AC2**: `fs2 init` recovers from 0-byte global config left by prior failed init
- [ ] **AC3**: After `fs2 scan`, no node_id in the graph contains `\` — all use `/`
- [ ] **AC4**: `fs2 scan` completes with zero WinError 183 warnings
- [ ] **AC5**: `fs2 tree "."` shows hierarchical folder grouping (not flat)
- [ ] **AC6**: All `write_text()`/`read_text()`/text `open()` calls specify `encoding="utf-8"`
- [ ] **AC7**: Rich console output renders correctly on Windows Terminal
- [ ] **AC8**: `install.py` error shows Windows-appropriate `powershell` install command
- [ ] **AC9**: `fs2 report` opens HTML correctly in browser on Windows
- [ ] **AC10**: `uv run python -m pytest` passes on Windows with no new failures
- [ ] **AC11**: All changes are no-ops or equivalent on Mac/Linux — no regressions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Encoding change breaks legitimate cp1252 files | Low | Medium | All code/config files are UTF-8; `.gitignore` and YAML are ASCII-safe |
| `os.replace()` not atomic on some filesystems | Very Low | Low | NTFS supports atomic replace; FAT32 is not a target |
| PYTHONUTF8 env var affects subprocess behavior | Low | Low | Only affects Python subprocesses; desirable for consistency |
| Old graphs with backslash node_ids | Medium | Low | Re-scanning overwrites; no migration needed |
