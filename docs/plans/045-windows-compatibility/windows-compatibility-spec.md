# Windows Compatibility for fs2

**Mode**: Simple

📚 This specification incorporates findings from research-dossier.md

## Research Context

The research phase (8 parallel subagents, 63 findings) verified that fs2 has **3 show-stopping bugs** and ~15 secondary issues on Windows. The codebase was developed entirely on Mac/Linux. A live scan of `C:\repos\athena-ai-architecture-enablement` confirmed:
- `fs2 init` crashes (UnicodeEncodeError)
- `fs2 scan` produces corrupt node IDs (backslash paths)
- Graph saves emit WinError 183 warnings
- Downstream features (tree, search, MCP) are broken by corrupt node IDs

The Clean Architecture design concentrates fixes at adapter/repo boundaries; service layer needs zero changes.

## Summary

fs2 must work reliably on Windows. Users should be able to run the full `init → scan → tree → search → report` workflow without crashes, data corruption, or garbled output. All fixes must be backward-compatible with Mac/Linux — no platform-specific code paths in services.

## Goals

- **G1**: `fs2 init` creates valid configuration files on Windows without crashing
- **G2**: `fs2 scan` produces node IDs with forward-slash (`/`) paths on all platforms, maintaining internal consistency
- **G3**: Graph persistence (save/load) works reliably on Windows without WinError 183
- **G4**: All text file I/O uses explicit UTF-8 encoding so non-ASCII content never crashes on Windows cp1252
- **G5**: Console output renders correctly on modern Windows terminals (Windows Terminal, PowerShell 7)
- **G6**: Error messages and help text are platform-appropriate (no Unix-only instructions on Windows)
- **G7**: Existing tests pass on Windows; platform-incompatible tests are properly skipped
- **G8**: All fixes are backward-compatible with Mac/Linux (no regressions)

## Non-Goals

- **NG1**: Changing XDG config paths to `%APPDATA%` — `~/.config/fs2` works on Windows and cross-platform consistency has value
- **NG2**: Supporting legacy Windows consoles (cmd.exe with cp437) — Windows Terminal / PowerShell 7 is the minimum target
- **NG3**: Adding Windows CI (GitHub Actions) — desirable future work but not required for this feature
- **NG4**: Refactoring service-layer path splitting to use `os.sep` — services correctly assume `/` by design; fix the source instead
- **NG5**: Windows-specific performance optimizations
- **NG6**: Supporting UNC paths (`\\server\share`) or mapped network drives

## Target Domains

| Domain | Status | Relationship | Role in This Feature |
|--------|--------|-------------|---------------------|
| adapters | existing | **modify** | Normalize file paths to POSIX at AST parser boundary; add UTF-8 encoding to file scanner/watcher |
| repos | existing | **modify** | Fix atomic file rename for cross-platform graph persistence |
| cli | existing | **modify** | Add UTF-8 encoding to init/projects/get_node; fix platform-specific messages; fix file:// URIs |
| config | existing | **modify** | Add UTF-8 encoding to YAML/config loading |
| services | existing | **consume** | No changes — services correctly assume `/` in paths (validated by research) |
| mcp | existing | **modify** | Add UTF-8 encoding to one `open()` call |

No new domains required. All changes are modifications to existing architectural layers.

## Complexity

- **Score**: CS-2 (small)
- **Breakdown**: S=2, I=0, D=0, N=0, F=0, T=1
  - Surface Area (S=2): ~15 files touched across multiple layers, but changes are mechanical
  - Integration (I=0): No external dependencies added or changed
  - Data/State (D=0): No schema changes; graph format unchanged
  - Novelty (N=0): Well-specified — every issue has a known, verified fix
  - Non-Functional (F=0): Standard cross-platform compatibility
  - Testing (T=1): Need integration verification via actual scan on Windows; some test skips to add
- **Total**: P=3 → CS-2
- **Confidence**: 0.95
- **Assumptions**:
  - Python's `os.replace()` works atomically on Windows NTFS (well-documented)
  - `Path.as_posix()` / `.replace("\\", "/")` is a no-op on Mac/Linux
  - Windows Terminal / PowerShell 7 supports UTF-8 output
  - All config/source files are UTF-8 encoded
- **Dependencies**: None — all fixes use Python stdlib
- **Risks**:
  - Low: Changing encoding default could break files that are genuinely cp1252 (unlikely for code/config)
  - Low: `os.replace()` vs `Path.rename()` behavioral difference is well-documented and safe
- **Phases**:
  1. Critical fixes (path normalization, graph save, init encoding) — ~10 lines
  2. Systemic encoding hardening (~15 locations) — ~20 lines
  3. Polish (error messages, URI, test skips) — ~15 lines

## Acceptance Criteria

### AC1: Init Creates Valid Config
`fs2 init` completes without error on Windows and produces valid UTF-8 config files at `.fs2/config.yaml` and `~/.config/fs2/config.yaml`. Both files are readable and parseable by YAML.

### AC2: Init Recovers from 0-Byte Global Config
If a prior failed init left a 0-byte global config file, `fs2 init` detects this and overwrites it rather than skipping with "already exists".

### AC3: Node IDs Use Forward Slashes
After `fs2 scan`, all node IDs in the persisted graph use `/` as the path separator, regardless of OS. Verified by loading the graph and checking that no node_id contains `\`.

### AC4: Graph Save Succeeds Without Warnings
`fs2 scan` completes with zero `WinError 183` warnings. Courtesy saves and final save both succeed on Windows.

### AC5: Tree Displays Correctly
`fs2 tree "."` shows a hierarchical folder structure after scanning, with proper folder grouping (not flat output caused by backslash paths).

### AC6: All File I/O Uses UTF-8
Every `write_text()`, `read_text()`, and text-mode `open()` call in the codebase specifies `encoding="utf-8"` explicitly.

### AC7: Console Output Renders Correctly
Rich box-drawing characters, progress bars, and stage banners render correctly on Windows Terminal / PowerShell 7 (not garbled as `ΓöîΓöÇ`).

### AC8: Platform-Appropriate Error Messages
When `uv` is not found, the install error message shows the Windows-appropriate install command (`powershell -c "irm ... | iex"`) rather than the Unix command (`curl | sh`).

### AC9: Report Opens in Browser
`fs2 report` opens the generated HTML file correctly in the default browser on Windows (proper `file:///C:/...` URI format).

### AC10: Tests Pass on Windows
`uv run python -m pytest` passes on Windows with no new failures. Platform-incompatible tests (symlinks, chmod) are skipped with `@pytest.mark.skipif(sys.platform == "win32", ...)`.

### AC11: Mac/Linux Unaffected
All changes are no-ops or equivalent behavior on Mac/Linux. The existing test suite continues to pass on Mac/Linux without modifications.

## Risks & Assumptions

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Changing default encoding breaks legitimate cp1252 files | Low | Medium | All code/config files should be UTF-8; .gitignore and YAML are ASCII-safe |
| `os.replace()` not atomic on some Windows filesystems | Very Low | Low | NTFS supports atomic replace; FAT32 is not a target |
| PYTHONUTF8 env var affects subprocess behavior | Low | Low | Only affects Python subprocesses; desirable for consistency |
| Existing Windows users have graphs with backslash node_ids | Medium | Low | Re-scanning creates correct node_ids; old graphs are overwritten |
| Some `.gitignore` files might use non-UTF-8 encoding | Very Low | Low | `.gitignore` is almost always ASCII; `errors="replace"` fallback if needed |

## Open Questions

No open questions remain — all issues are well-characterized with verified fixes from the research phase.

## Workshop Opportunities

No workshops needed. All fixes are mechanical and well-understood:
- Path normalization: add `.replace("\\", "/")` at 3 locations
- Encoding: add `encoding="utf-8"` parameter at ~15 locations
- Atomic rename: change `Path.rename()` to `os.replace()` at 1 location
- Error messages: platform detection at 1 location
- URI: use `Path.as_uri()` at 1 location

## Testing Strategy

- **Approach**: Lightweight
- **Rationale**: Changes are mechanical (encoding params, `.replace()`, `os.replace()`). The existing 1600+ test suite covers all affected code paths. Primary verification is integration: `fs2 init && fs2 scan && fs2 tree` on Windows.
- **Focus Areas**:
  - Run existing test suite (`uv run python -m pytest`) — confirm no regressions
  - Integration scan of `C:\repos\athena-ai-architecture-enablement` — verify node IDs use `/`
  - Verify `fs2 init`, `fs2 scan --no-smart-content`, `fs2 tree "."` complete without errors
- **Mock Usage**: Avoid mocks — real scan as integration test
- **Excluded**: No new unit tests; existing tests provide sufficient coverage

## Documentation Strategy

- **Location**: No new documentation
- **Rationale**: All changes are internal bug fixes with no user-facing API changes. The spec and research dossier provide complete reference.

## Clarifications

### Session 2026-04-06

**Q1: Workflow Mode** → **Simple** — CS-2 complexity, single-phase plan, inline tasks.

**Q2: Testing Strategy** → **Lightweight** — verify scan produces correct node IDs, run existing tests.

**Q3: Mock Usage** → **Avoid mocks** — real scan of `C:\repos\athena-ai-architecture-enablement` as integration test.

**Q4: Documentation Strategy** → **No new documentation** — fixes are internal, spec + research dossier suffice.

**Q5: Domain Review** → **Confirmed** — 5 existing domains modified (adapters, repos, cli, config, mcp), services unchanged, no new domains, all changes respect existing contracts.

**Q6: Harness** → **Continue without harness** — manual scan verification is sufficient for this feature.
