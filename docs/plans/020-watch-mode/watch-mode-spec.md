# Watch Mode for fs2

**Mode**: Simple

> This specification incorporates findings from `research-dossier.md`

---

## Research Context

Based on comprehensive research (55+ findings from 6 subagents):

- **Components affected**: CLI layer (`cli/watch.py`), services (`watch_service.py`), adapters (`file_watcher_*.py`), config (`objects.py`)
- **Critical dependencies**: New `watchfiles` library, existing `pathspec` for gitignore
- **Modification risks**: Low - all new files except minor config addition
- **Prior learnings**: 15 relevant discoveries applied (PL-01 through PL-15)
- **Link**: See `research-dossier.md` for full analysis

---

## Summary

**WHAT**: Add an `fs2 watch` command that monitors directories for file changes and automatically triggers `fs2 scan` when changes are detected.

**WHY**: Developers currently must manually run `fs2 scan` after code changes. This interrupts flow and means the code graph often becomes stale. Automatic watching enables real-time code intelligence updates during development, keeping search, tree navigation, and MCP tools current without manual intervention.

---

## Goals

1. **Automatic scanning**: Detect file changes in watched directories and trigger scans without user intervention
2. **Cross-platform support**: Work reliably on Linux, macOS, and Windows using native OS notification systems
3. **Intelligent queuing**: If a scan is already running when new changes occur, queue exactly one follow-up scan (not per-file)
4. **Memory safety**: Run scans in isolated subprocess to prevent memory leaks in long-running watch processes
5. **Gitignore awareness**: Respect `.gitignore` patterns and fs2 configuration for file exclusion
6. **Debouncing**: Batch rapid file changes to avoid excessive scanning during active editing
7. **Graceful shutdown**: Handle Ctrl+C and termination signals cleanly, waiting for in-progress scans to complete
8. **Configuration integration**: Use fs2 config system for watch settings (paths, debounce timing, ignore patterns)
9. **Developer feedback**: Provide clear status messages about watched paths, detected changes, scan progress, and errors

---

## Non-Goals

1. **IDE plugin integration**: This command is CLI-only; IDE integrations are out of scope
2. **Incremental scanning**: Each triggered scan is a full scan; partial/incremental graph updates are future work
3. **Remote file watching**: Only local filesystem watching; network drives or remote mounts are not targeted
4. **Custom scan commands**: The watch command triggers `fs2 scan`; arbitrary command execution is not supported
5. **Parallel scans**: Only one scan runs at a time; parallel scanning is not supported
6. **Persistent watch daemon**: The command runs in foreground; background daemon/service mode is future work
7. **File content diffing**: Watch detects file system events, not semantic code changes

---

## Complexity

**Score**: CS-2 (small)

**Breakdown**:
| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 1 | 4-5 new files across CLI, services, adapters; minor config addition |
| Integration (I) | 1 | One new external dependency (`watchfiles`), stable and well-documented |
| Data/State (D) | 0 | No database schemas or persistent state; runtime state only |
| Novelty (N) | 0 | Requirements well-specified; reference shell script exists |
| Non-Functional (F) | 1 | Cross-platform concerns; graceful shutdown handling |
| Testing/Rollout (T) | 1 | Unit tests with fakes + integration tests |

**Total**: P = 4 → **CS-2**

**Confidence**: 0.85

**Assumptions**:
- `watchfiles` library provides advertised cross-platform support without major quirks
- Subprocess isolation via `uvx` or `sys.executable` is sufficient for memory management
- Existing pathspec/gitignore patterns work correctly for watch filtering

**Dependencies**:
- `watchfiles` package (external, Rust-based)
- `uv`/`uvx` available for subprocess isolation (or fallback to `sys.executable`)

**Risks**:
- Windows signal handling has platform-specific limitations (mitigated by asyncio.Event fallback)
- Large codebases may have many watched files (mitigated by debouncing and native OS notifications)

**Phases**:
1. Core infrastructure (adapter ABC, watchfiles implementation, config)
2. Service layer (queue semantics, subprocess management)
3. CLI integration (command registration, argument handling, Rich output)

---

## Acceptance Criteria

### AC1: Basic Watch and Scan
**Given** a user runs `fs2 watch` in an initialized fs2 project
**When** a Python file in a watched directory is modified
**Then** the watch command automatically triggers `fs2 scan` within the debounce window
**And** the scan output is streamed to the console in real-time

### AC2: Queue-One Semantics
**Given** a scan is currently in progress
**When** additional file changes occur (1, 5, or 100 files)
**Then** exactly one follow-up scan is queued (not one per file)
**And** the queued scan runs after the current scan completes

### AC3: Cross-Platform Support
**Given** the watch command is running
**When** tested on Linux, macOS, or Windows
**Then** file change detection works using native OS notifications (inotify, FSEvents, ReadDirectoryChangesW)
**And** Ctrl+C triggers graceful shutdown on all platforms

### AC4: Gitignore Respect
**Given** a project with `.gitignore` containing `*.pyc` and `__pycache__/`
**When** a `.pyc` file is created or `__pycache__/` contents change
**Then** no scan is triggered for these ignored files

### AC5: Debounce Behavior
**Given** the watch command is running with default debounce (1600ms)
**When** 10 files are modified in rapid succession within 500ms
**Then** only one scan is triggered after the debounce window closes
**And** all 10 changes are batched together

### AC6: Subprocess Isolation
**Given** the watch command runs for an extended period (e.g., 1 hour)
**When** multiple scans have been triggered
**Then** each scan runs in an isolated subprocess
**And** the watch process memory usage remains stable (no accumulation)

### AC7: Graceful Shutdown
**Given** a scan is in progress
**When** the user presses Ctrl+C
**Then** the watch command displays "Stopping watcher..."
**And** waits for the current scan to complete before exiting
**And** exits with code 0

### AC8: Scan Argument Pass-through
**Given** a user runs `fs2 watch --no-embeddings --verbose`
**When** a scan is triggered
**Then** the scan command receives `--no-embeddings --verbose` arguments

### AC9: Configuration Integration
**Given** a `.fs2/config.yaml` with `watch.debounce_ms: 3000`
**When** the watch command is started without `--debounce` flag
**Then** the 3000ms debounce value from config is used

### AC10: Error Resilience
**Given** a triggered scan fails (exit code non-zero)
**When** the scan completes
**Then** the watch command logs the failure
**And** continues watching for further changes (does not exit)

### AC11: Startup Information
**Given** a user runs `fs2 watch ./src ./tests`
**When** the watch command starts
**Then** it displays the paths being watched, debounce setting, and gitignore status

---

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Windows signal handling limitations | Medium | Low | Use `asyncio.Event` and `threading.Event` fallbacks |
| `watchfiles` has undocumented platform quirks | Low | Medium | Library is battle-tested (uvicorn); fallback to polling if needed |
| Large codebases overwhelm file watcher | Low | Medium | Debouncing + native OS notifications handle this well |
| `uvx` not installed on user system | Medium | Low | Fallback to `sys.executable -m fs2` if uvx unavailable |

### Assumptions

1. Users have `uv`/`uvx` installed (standard for fs2 users) or Python in PATH
2. File system supports native change notifications (not NFS or network mounts)
3. Users expect foreground operation (not a background daemon)
4. Debounce of 1600ms is acceptable for development workflows
5. Single-scan-at-a-time with queue-one is the desired behavior (not cancel-and-restart)

---

## Open Questions

1. **[NEEDS CLARIFICATION: uvx vs sys.executable]** Should we require `uvx` for subprocess isolation, or fallback gracefully to `sys.executable -m fs2`? Research recommends uvx for full isolation.

2. **[NEEDS CLARIFICATION: Default watch paths]** When no paths are specified, should we use `scan_paths` from ScanConfig, or require explicit paths? Research suggests using config defaults.

3. **[NEEDS CLARIFICATION: Initial scan on startup]** Should `fs2 watch` run an immediate scan when started, or wait for the first file change?

4. **[NEEDS CLARIFICATION: Session statistics]** Should the graceful shutdown message include session statistics (e.g., "5 scans completed in session")?

---

## ADR Seeds (Optional)

### ADR-001: File Watching Library Selection

**Decision Drivers**:
- Must support Linux, macOS, Windows with native notifications
- Debouncing should be built-in or easily implemented
- Memory efficiency for long-running processes
- Active maintenance and community adoption

**Candidate Alternatives**:
- A: `watchfiles` - Rust-based, built-in debouncing, async-native, used by uvicorn
- B: `watchdog` - Pure Python, more established, requires manual debouncing
- C: Custom implementation with `inotify`/`FSEvents`/`ReadDirectoryChangesW` - Maximum control, high effort

**Stakeholders**: fs2 maintainers, users on all platforms

### ADR-002: Scan Subprocess Strategy

**Decision Drivers**:
- Memory isolation for long-running watch processes
- Consistent environment for scan execution
- Cross-platform subprocess management

**Candidate Alternatives**:
- A: `uvx fs2 scan` - Full environment isolation, requires uv installed
- B: `sys.executable -m fs2 scan` - Uses current Python, simpler but shares memory space
- C: `subprocess.run(["fs2", "scan"])` - Relies on PATH, simplest but least isolated

**Stakeholders**: fs2 maintainers, users with varying environments

---

## Next Steps

1. Run `/plan-2-clarify` to resolve open questions
2. Run `/plan-3-architect` to design implementation phases

---

**Spec Created**: 2026-01-06
**Plan Folder**: `docs/plans/020-watch-mode/`
**Research**: Incorporated from `research-dossier.md`
