# Watch Mode Implementation - Execution Log

**Plan**: docs/plans/020-watch-mode/watch-mode-plan.md
**Tasks Dossier**: docs/plans/020-watch-mode/tasks/full-implementation/tasks.md
**Started**: 2026-01-11
**Testing Approach**: Full TDD

---

## Task T001: Add watchfiles dependency to pyproject.toml
**Started**: 2026-01-11
**Status**: ✅ Complete

### What I Did
Added `watchfiles>=0.21` to pyproject.toml dependencies, inserted alphabetically after tree-sitter-language-pack and before typer.

### Evidence
```bash
$ uv pip install -e .
Resolved 103 packages in 561ms
Installed 2 packages in 15ms
 ~ fs2==0.1.0 (from file:///workspaces/flow_squared)
 + watchfiles==1.1.1

$ python -c "import watchfiles; print(f'watchfiles version: {watchfiles.__version__}')"
watchfiles version: 1.1.1
```

### Files Changed
- `/workspaces/flow_squared/pyproject.toml` — Added watchfiles>=0.21 to dependencies

**Completed**: 2026-01-11

---

## Task T002: Create WatchConfig in config/objects.py
**Started**: 2026-01-11
**Status**: ✅ Complete

### What I Did
Created WatchConfig Pydantic model with:
- `debounce_ms: int = 1600` (range 100-60000)
- `watch_paths: list[str] = []` (empty defaults to scan_paths from ScanConfig)
- `additional_ignores: list[str] = []` (extra patterns beyond .gitignore)
- `scan_timeout_seconds: int = 300` (range 60-3600, per DYK-2)
- `__config_path__ = "watch"` for YAML/env loading
- Validators for debounce_ms and scan_timeout_seconds ranges
- Added to YAML_CONFIG_TYPES list

### Evidence
```python
>>> from fs2.config.objects import WatchConfig
>>> config = WatchConfig()
>>> print(f'Default debounce_ms: {config.debounce_ms}')
Default debounce_ms: 1600
>>> print(f'Default scan_timeout_seconds: {config.scan_timeout_seconds}')
Default scan_timeout_seconds: 300
>>> print(f'__config_path__: {config.__config_path__}')
__config_path__: watch

# Validator test
>>> WatchConfig(debounce_ms=50)
ValidationError: debounce_ms must be between 100 and 60000
```

### Files Changed
- `/workspaces/flow_squared/src/fs2/config/objects.py` — Added WatchConfig class and added to YAML_CONFIG_TYPES

**Completed**: 2026-01-11

---

## Task T003: Write tests for FileWatcherAdapter ABC
**Started**: 2026-01-11
**Status**: ✅ Complete

### What I Did
Created TDD tests for FileWatcherAdapter ABC contract:
- `test_file_watcher_adapter_abc_cannot_be_instantiated` - Verifies ABC cannot be directly instantiated
- `test_file_watcher_adapter_abc_defines_watch_method` - Verifies watch() is abstract
- `test_file_watcher_adapter_abc_defines_stop_method` - Verifies stop() is abstract
- `test_file_watcher_adapter_abc_inherits_from_abc` - Verifies proper ABC inheritance
- `test_file_watcher_adapter_watch_returns_async_iterator` - Verifies async contract

### Evidence (RED phase)
```bash
$ python -m pytest tests/unit/adapters/test_file_watcher_adapter.py -v
5 failed
ModuleNotFoundError: No module named 'fs2.core.adapters.file_watcher_adapter'
```
Tests fail because ABC doesn't exist yet - TDD RED phase complete.

### Files Changed
- `/workspaces/flow_squared/tests/unit/adapters/test_file_watcher_adapter.py` — Created test file with 5 tests

**Completed**: 2026-01-11

---

## Task T004: Create FileWatcherAdapter ABC
**Started**: 2026-01-11
**Status**: ✅ Complete

### What I Did
Created FileWatcherAdapter ABC with:
- `watch()` abstract async generator returning `AsyncIterator[set[FileChange]]`
- `stop()` abstract method for graceful shutdown
- `FileChange` type alias: `tuple[str, str]` for (change_type, path)
- Comprehensive docstrings documenting the contract

### Evidence (GREEN phase)
```bash
$ python -m pytest tests/unit/adapters/test_file_watcher_adapter.py -v
5 passed in 0.50s
```

### Files Changed
- `/workspaces/flow_squared/src/fs2/core/adapters/file_watcher_adapter.py` — Created ABC file

**Completed**: 2026-01-11

---

## Task T005: Write tests for FakeFileWatcher
**Started**: 2026-01-11
**Status**: ✅ Complete

### What I Did
Created TDD tests for FakeFileWatcher per DYK-4 (Finite Queue + Auto-Stop pattern):
- `test_fake_file_watcher_implements_abc` - Verifies ABC inheritance
- `test_fake_file_watcher_emits_programmed_changes` - Tests add_changes() and yields
- `test_fake_file_watcher_auto_stops_when_queue_empty` - Tests auto-stop behavior
- `test_fake_file_watcher_yields_multiple_changes_per_batch` - Tests batched changes
- `test_fake_file_watcher_stop_exits_loop` - Tests manual stop()
- `test_fake_file_watcher_tracks_watch_calls` - Tests call tracking
- `test_fake_file_watcher_empty_queue_yields_nothing` - Edge case
- `test_fake_file_watcher_stop_is_idempotent` - Safety test
- `test_fake_file_watcher_different_change_types` - Tests added/modified/deleted

### Evidence (RED phase)
```bash
$ python -m pytest tests/unit/adapters/test_file_watcher_adapter_fake.py -v
9 failed
ModuleNotFoundError: No module named 'fs2.core.adapters.file_watcher_adapter_fake'
```
Tests fail because FakeFileWatcher doesn't exist yet - TDD RED phase complete.

### Files Changed
- `/workspaces/flow_squared/tests/unit/adapters/test_file_watcher_adapter_fake.py` — Created test file with 9 tests

**Completed**: 2026-01-11

---

## Task T006: Create FakeFileWatcher implementation
**Started**: 2026-01-11
**Status**: ✅ Complete

### What I Did
Created FakeFileWatcher implementing FileWatcherAdapter ABC with:
- `add_changes(changes)` - Queue pre-programmed change sets
- `watch()` async generator - Yields queued changes, auto-stops when empty
- `stop()` - Request graceful shutdown (idempotent)
- `watch_call_count` property - Tracks yields for test verification

### Evidence (GREEN phase)
```bash
$ python -m pytest tests/unit/adapters/test_file_watcher_adapter_fake.py -v
9 passed in 0.44s
```

### Files Changed
- `/workspaces/flow_squared/src/fs2/core/adapters/file_watcher_adapter_fake.py` — Created FakeFileWatcher implementation

**Completed**: 2026-01-11

---

## Task T009: Write tests for GitignoreFilter
**Started**: 2026-01-11
**Status**: ✅ Complete

### What I Did
Created TDD tests for GitignoreFilter:
- 9 tests covering .gitignore patterns, additional_ignores, missing gitignore, nested directories, and change types

### Evidence (RED phase)
```bash
$ python -m pytest tests/unit/adapters/test_gitignore_filter.py -v
9 failed - ModuleNotFoundError (as expected)
```

### Files Changed
- `/workspaces/flow_squared/tests/unit/adapters/test_gitignore_filter.py` — Created test file

**Completed**: 2026-01-11

---

## Task T010: Create GitignoreFilter class
**Started**: 2026-01-11
**Status**: ✅ Complete

### What I Did
Created GitignoreFilter extending watchfiles.DefaultFilter:
- Loads .gitignore patterns from root directory
- Supports additional_ignores from WatchConfig
- Uses pathspec for gitwildmatch pattern matching
- Returns False to exclude (watchfiles convention)

### Evidence (GREEN phase)
```bash
$ python -m pytest tests/unit/adapters/test_gitignore_filter.py -v
9 passed in 0.51s
```

### Files Changed
- `/workspaces/flow_squared/src/fs2/core/adapters/file_watcher_adapter_watchfiles.py` — Created GitignoreFilter class

**Completed**: 2026-01-11

---

## Task T011: Update adapters/__init__.py exports
**Started**: 2026-01-11
**Status**: ✅ Complete

### What I Did
Added FileWatcherAdapter and FakeFileWatcher to adapters/__init__.py exports.

### Evidence
```python
>>> from fs2.core.adapters import FileWatcherAdapter, FakeFileWatcher
>>> # Works!
```

### Files Changed
- `/workspaces/flow_squared/src/fs2/core/adapters/__init__.py` — Added imports and __all__ entries

**Completed**: 2026-01-11

---

## Implementation Progress Summary

## Task T016: Update services/__init__.py exports
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Added WatchService to services/__init__.py imports and __all__ list.

### Evidence
```bash
$ python -c "from fs2.core.services import WatchService; print('WatchService imported successfully')"
WatchService imported successfully
```

### Files Changed
- `/workspaces/flow_squared/src/fs2/core/services/__init__.py` — Added WatchService import and export

**Completed**: 2026-01-12

---

## Tasks T017-T019: Watch CLI command
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Created the watch CLI command and tests:

**T017 - CLI Tests** (4 tests):
- `test_given_no_config_when_watch_then_fails` - Guard blocks uninitialized
- `test_given_any_directory_when_watch_help_then_succeeds` - Help always works
- `test_watch_accepts_no_embeddings_flag` - Argument handling
- `test_watch_accepts_verbose_flag` - Argument handling

**T018 - watch CLI command**:
- Created `/workspaces/flow_squared/src/fs2/cli/watch.py` with Typer command
- Supports --no-embeddings, --no-smart-content, --verbose flags
- Uses SubprocessScanRunner for scan isolation
- Displays startup info (paths, debounce, Ctrl+C message)
- Handles SIGINT for graceful shutdown

**T019 - CLI Registration**:
- Added `from fs2.cli.watch import watch` to main.py
- Added `app.command(name="watch")(require_init(watch))` to register with guard

### Evidence
```bash
$ python -m pytest tests/unit/cli/test_watch_cli.py -v
4 passed in 0.91s

$ fs2 watch --help
 Usage: fs2 watch [OPTIONS]
 ...
 --no-embeddings    Pass --no-embeddings to scan commands
 --no-smart-content Pass --no-smart-content to scan commands
 --verbose     -v   Show detailed output
 --help             Show this message and exit.

$ python -m pytest tests/unit/adapters/test_file_watcher*.py tests/unit/adapters/test_gitignore*.py tests/unit/services/test_watch_service.py tests/unit/cli/test_watch_cli.py -v
49 passed in 9.39s
```

### Files Changed
- `/workspaces/flow_squared/tests/unit/cli/test_watch_cli.py` — Created CLI tests (4 tests)
- `/workspaces/flow_squared/src/fs2/cli/watch.py` — Created watch CLI command
- `/workspaces/flow_squared/src/fs2/cli/main.py` — Added watch import and registration

**Completed**: 2026-01-12

---

### Completed Tasks (20 of 22)
- [x] T001: Add watchfiles dependency
- [x] T002: Create WatchConfig
- [x] T003: Write tests for FileWatcherAdapter ABC
- [x] T004: Create FileWatcherAdapter ABC
- [x] T005: Write tests for FakeFileWatcher
- [x] T006: Create FakeFileWatcher
- [x] T007: Write tests for WatchfilesAdapter
- [x] T008: Create WatchfilesAdapter
- [x] T009: Write tests for GitignoreFilter
- [x] T010: Create GitignoreFilter
- [x] T011: Update adapters/__init__.py exports
- [x] T012: Write tests for WatchService queue-one semantics
- [x] T013: Write tests for WatchService subprocess execution
- [x] T014: Write tests for WatchService graceful shutdown
- [x] T015: Create WatchService implementation
- [x] T016: Update services/__init__.py exports
- [x] T017: Write tests for watch CLI command
- [x] T018: Create watch CLI command
- [x] T019: Register watch command in main.py
- [x] T022: Add scan timeout for change-triggered scans

### Remaining Tasks (2 of 22)
- [ ] T020: Integration test (optional)
- [ ] T021: Update README (optional)

### Test Count: 49 passing
```bash
$ python -m pytest tests/unit/adapters/test_file_watcher*.py tests/unit/adapters/test_gitignore*.py tests/unit/services/test_watch_service.py tests/unit/cli/test_watch_cli.py -v
49 passed
```

### Summary
The core watch mode feature is fully implemented with:
- Full adapter layer (FileWatcherAdapter ABC, FakeFileWatcher, WatchfilesAdapter, GitignoreFilter)
- WatchService with queue-one semantics and graceful shutdown
- watch CLI command with argument pass-through
- Scan timeout support for change-triggered scans (per DYK-2)
- 49 passing tests covering unit and CLI behavior

Remaining (optional):
- T020: Integration test with real file changes (smoke test)
- T021: README documentation update

---

## Task T022: Add scan timeout for change-triggered scans
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Added timeout support to SubprocessScanRunner per DYK-2:
- Added `timeout_seconds` parameter to SubprocessScanRunner
- Uses `asyncio.timeout()` to enforce timeout on scan subprocess
- Kills subprocess and returns exit code 124 (standard timeout code) on timeout
- watch CLI passes `watch_config.scan_timeout_seconds` to runner
- No timeout on initial scan (per DYK-2), configurable timeout for subsequent scans

### Evidence
```bash
$ python -m pytest tests/unit/cli/test_watch_cli.py tests/unit/services/test_watch_service.py -v
15 passed in 1.46s
```

### Files Changed
- `/workspaces/flow_squared/src/fs2/cli/watch.py` — Added timeout support to SubprocessScanRunner

**Completed**: 2026-01-12

### Key Decisions Applied
- DYK-2: scan_timeout_seconds added to WatchConfig (default 300s, no timeout on initial scan)
- DYK-4: FakeFileWatcher uses Finite Queue + Auto-Stop pattern
- DYK-5: KISS - log errors and continue (per AC10)

---

## Task T007: Write tests for WatchfilesAdapter
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Created TDD tests for WatchfilesAdapter covering:
- `test_watchfiles_adapter_implements_abc` - Verifies ABC inheritance
- `test_watchfiles_adapter_detects_file_modification` - Core change detection
- `test_watchfiles_adapter_detects_file_creation` - New file detection
- `test_watchfiles_adapter_detects_file_deletion` - Deleted file detection
- `test_watchfiles_adapter_respects_gitignore` - Gitignore pattern filtering (AC4)
- `test_watchfiles_adapter_respects_additional_ignores` - Config-driven exclusions (AC9)
- `test_watchfiles_adapter_stop_exits_loop` - Graceful shutdown (AC7)
- `test_watchfiles_adapter_stop_is_idempotent` - Stop safety
- `test_watchfiles_adapter_watches_multiple_paths` - Multi-path support
- `test_watchfiles_adapter_debounces_rapid_changes` - Debounce batching (AC5)
- `test_watchfiles_adapter_yields_change_tuples` - ABC contract compliance

### Evidence (RED phase)
```bash
$ python -m pytest tests/unit/adapters/test_file_watcher_adapter_watchfiles.py -v
11 failed
ImportError: cannot import name 'WatchfilesAdapter' from 'fs2.core.adapters.file_watcher_adapter_watchfiles'
```
Tests fail because WatchfilesAdapter doesn't exist yet - TDD RED phase complete.

### Files Changed
- `/workspaces/flow_squared/tests/unit/adapters/test_file_watcher_adapter_watchfiles.py` — Created test file with 11 tests

**Completed**: 2026-01-12

---

## Task T008: Create WatchfilesAdapter implementation
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Created WatchfilesAdapter class implementing FileWatcherAdapter ABC:
- Wraps `watchfiles.awatch()` for cross-platform file watching
- Uses `GitignoreFilter` for pattern filtering
- Supports `debounce_ms` configuration (default 1600ms)
- Supports `additional_ignores` configuration
- Uses `asyncio.Event` for graceful stop() handling
- Converts watchfiles `Change` enum to our string format ("added", "modified", "deleted")

Also added WatchfilesAdapter to adapters/__init__.py exports.

### Evidence (GREEN phase)
```bash
$ python -m pytest tests/unit/adapters/test_file_watcher_adapter_watchfiles.py -v
11 passed in 8.42s

$ python -m pytest tests/unit/adapters/test_file_watcher*.py tests/unit/adapters/test_gitignore*.py -v
34 passed in 8.46s

$ python -c "from fs2.core.adapters import WatchfilesAdapter; print(f'WatchfilesAdapter imported successfully')"
WatchfilesAdapter imported successfully
```

### Files Changed
- `/workspaces/flow_squared/src/fs2/core/adapters/file_watcher_adapter_watchfiles.py` — Added WatchfilesAdapter class
- `/workspaces/flow_squared/src/fs2/core/adapters/__init__.py` — Added WatchfilesAdapter export

**Completed**: 2026-01-12

---

## Tasks T012-T014: Write tests for WatchService
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Created comprehensive TDD tests for WatchService covering:

**T012 - Queue-One Semantics Tests (3 tests)**:
- `test_queue_one_exactly_one_queued_scan` - Multiple changes during scan = one queued scan
- `test_queue_one_no_queue_when_idle` - Normal case without queueing
- `test_queue_one_clears_after_queued_scan_runs` - Queue properly resets

**T013 - Subprocess Execution Tests (2 tests)**:
- `test_subprocess_receives_scan_command` - Correct command construction
- `test_subprocess_passes_no_embeddings_flag` - Argument pass-through per AC8

**T014 - Graceful Shutdown Tests (3 tests)**:
- `test_graceful_shutdown_exits_cleanly` - Clean shutdown path
- `test_graceful_shutdown_waits_for_current_scan` - No interrupted scans
- `test_stop_is_idempotent` - Multiple stop() calls safe

**Additional Tests**:
- `test_scan_failure_continues_watching` - Error resilience per AC10/DYK-5
- `test_initial_scan_runs_on_startup` - AC12 compliance
- `test_watcher_starts_before_initial_scan` - DYK-3 race condition prevention

Also created FakeScanRunner helper class for testing subprocess behavior without actual processes.

### Evidence (RED phase)
```bash
$ python -m pytest tests/unit/services/test_watch_service.py -v
11 failed
ModuleNotFoundError: No module named 'fs2.core.services.watch_service'
```
Tests fail because WatchService doesn't exist yet - TDD RED phase complete.

### Files Changed
- `/workspaces/flow_squared/tests/unit/services/test_watch_service.py` — Created test file with 11 tests

**Completed**: 2026-01-12

---

## Task T015: Create WatchService implementation
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Created WatchService with full queue-one semantics:
- Receives ConfigurationService registry, extracts WatchConfig and ScanConfig internally
- Receives FileWatcherAdapter ABC and ScanRunner protocol for DI
- Implements queue-one semantics: only one scan queued regardless of change count
- Uses asyncio.Event for graceful shutdown signaling
- Starts watcher BEFORE initial scan (DYK-3 race condition prevention)
- Continues watching after scan failures (AC10/DYK-5 KISS)

Also created ScanRunner Protocol for subprocess abstraction.

### Evidence (GREEN phase)
```bash
$ python -m pytest tests/unit/services/test_watch_service.py -v
11 passed in 1.10s

$ python -m pytest tests/unit/adapters/test_file_watcher*.py tests/unit/adapters/test_gitignore*.py tests/unit/services/test_watch_service.py -v
45 passed in 8.98s
```

### Files Changed
- `/workspaces/flow_squared/src/fs2/core/services/watch_service.py` — Created WatchService and ScanRunner protocol

### Discovery
- debounce_ms validator has minimum of 100, tests needed to use 100 instead of 50

**Completed**: 2026-01-12

---

## Task T016: Update services/__init__.py exports
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Added WatchService to services/__init__.py exports.

### Files Changed
- `/workspaces/flow_squared/src/fs2/core/services/__init__.py` — Added WatchService to __all__

**Completed**: 2026-01-12

---

## Task T017: Write tests for watch CLI command
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Created TDD tests for watch CLI command:
- `test_given_no_config_when_watch_then_fails` - Guard test for @require_init
- `test_given_any_directory_when_watch_help_then_succeeds` - Help flag test
- `test_watch_accepts_no_embeddings_flag` - Arg pass-through test
- `test_watch_accepts_verbose_flag` - Verbose flag test

### Evidence (RED phase)
```bash
$ python -m pytest tests/unit/cli/test_watch_cli.py -v
4 failed
ModuleNotFoundError: No module named 'fs2.cli.watch'
```
Tests fail because CLI doesn't exist yet - TDD RED phase complete.

### Files Changed
- `/workspaces/flow_squared/tests/unit/cli/test_watch_cli.py` — Created test file with 4 tests

**Completed**: 2026-01-12

---

## Task T018: Create watch CLI command
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Created watch CLI command with:
- SubprocessScanRunner class for production subprocess isolation
- Uses `uv run fs2 scan` (with fallback to sys.executable)
- Streams subprocess output to console
- Configurable timeout support (per DYK-2)
- RichConsoleAdapter for formatted output
- Graceful shutdown via signal handlers (SIGINT, SIGTERM with guard)

### Files Changed
- `/workspaces/flow_squared/src/fs2/cli/watch.py` — Created CLI command with SubprocessScanRunner

**Completed**: 2026-01-12

---

## Task T019: Register watch command in main.py
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Registered watch command in main.py with @require_init guard:
```python
from fs2.cli.watch import watch
app.command(name="watch")(require_init(watch))
```

### Evidence (GREEN phase)
```bash
$ python -m pytest tests/unit/cli/test_watch_cli.py -v
4 passed in 0.91s

$ fs2 watch --help
Usage: fs2 watch [OPTIONS]
  Watch for file changes and automatically run scans.
```

### Files Changed
- `/workspaces/flow_squared/src/fs2/cli/main.py` — Added watch command registration

**Completed**: 2026-01-12

---

## Task T022: Add scan timeout for change-triggered scans
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Added configurable scan timeout to SubprocessScanRunner:
- No timeout on initial scan (can take 40+ minutes with embeddings)
- Configurable timeout for change-triggered scans (default 300s)
- Subprocess killed after timeout with exit code 124
- Watch continues after timeout (error logged)

Per DYK-2: This prevents hung scans from blocking the watcher indefinitely.

### Files Changed
- `/workspaces/flow_squared/src/fs2/cli/watch.py` — Added timeout_seconds parameter to SubprocessScanRunner
- `/workspaces/flow_squared/src/fs2/config/objects.py` — Added scan_timeout_seconds field to WatchConfig

**Completed**: 2026-01-12

---

## Bug Fixes During Testing

### Fix 1: WatchConfig not in registry for WatchService
**Issue**: watch.py used `config.get(WatchConfig) or WatchConfig()` but didn't set it back, causing WatchService.require() to fail
**Fix**: Added `config.set(watch_config)` after fallback creation
**File**: `/workspaces/flow_squared/src/fs2/cli/watch.py`

### Fix 2: uvx vs uv run for subprocess
**Issue**: `uvx fs2` runs isolated PyPI version, not local development version
**Fix**: Changed to `uv run fs2 scan` which uses local project
**File**: `/workspaces/flow_squared/src/fs2/cli/watch.py`

### Fix 3: Subprocess output formatting
**Issue**: print_info() added extra indentation/styling to subprocess output
**Fix**: Changed to print() for raw output passthrough
**File**: `/workspaces/flow_squared/src/fs2/cli/watch.py`

### Enhancement: Display triggering files
**Added**: ScanRunner.run() now accepts `triggered_by` parameter to show which files triggered the scan
**Files**:
- `/workspaces/flow_squared/src/fs2/core/services/watch_service.py`
- `/workspaces/flow_squared/src/fs2/cli/watch.py`

---

## Summary

**Implementation Status**: Core complete (T001-T019, T022)
**Optional Remaining**: T020 (Integration test), T021 (README update)

**Test Results**:
```bash
$ python -m pytest tests/unit/adapters/test_file_watcher*.py tests/unit/adapters/test_gitignore*.py tests/unit/services/test_watch_service.py tests/unit/cli/test_watch_cli.py -v
49 passed
```

**All Acceptance Criteria Met**:
- AC1-AC12: All verified through unit tests and manual testing

**Justfile Commands Added**:
- `just watch` - Full scans with embeddings + smart content
- `just watch-verbose` - With verbose output
- `just watch-quick` - Fast mode without embeddings/smart content
- `just watch-demo` - Demo mode with instructions
- `just watch-trigger` - Trigger file change for testing

