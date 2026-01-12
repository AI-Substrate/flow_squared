# Watch Mode Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-01-11
**Spec**: [./watch-mode-spec.md](./watch-mode-spec.md)
**Research**: [./research-dossier.md](./research-dossier.md)
**Status**: READY

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Research Findings](#critical-research-findings)
3. [Implementation](#implementation)
4. [Acceptance Criteria](#acceptance-criteria)
5. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

**Problem**: Developers must manually run `fs2 scan` after code changes, interrupting flow and causing stale code graphs.

**Solution**: Add `fs2 watch` command that monitors directories for file changes and automatically triggers `fs2 scan` using subprocess isolation, debouncing, and queue-one semantics.

**Expected Outcome**: Real-time code intelligence updates during development with cross-platform support (Linux, macOS, Windows).

---

## Critical Research Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | **CLI Registration**: Commands use `app.command(name="X")(require_init(X))` pattern in main.py | Register watch with `@require_init` guard |
| 02 | Critical | **Adapter ABC Pattern**: Three files required - ABC interface, Fake test double, Impl production | Create `file_watcher_adapter.py`, `_fake.py`, `_watchfiles.py` |
| 03 | Critical | **Service DI Pattern**: Services receive ConfigurationService registry, extract config internally | WatchService takes `config: ConfigurationService`, calls `config.require(WatchConfig)` |
| 04 | Critical | **Config Objects**: Pydantic BaseModel with `__config_path__` ClassVar for YAML/env mapping | Add WatchConfig with `__config_path__ = "watch"` |
| 05 | High | **ConsoleAdapter ABC**: CLI uses RichConsoleAdapter, passes to services via callbacks | Use `console: ConsoleAdapter = RichConsoleAdapter()` in watch.py |
| 06 | High | **Fake Adapters for Testing**: Use FakeFileWatcher (not mocks), state-driven assertions | Implement FakeFileWatcher with `add_changes()` and `watch_calls` |
| 07 | High | **Async Testing**: Use `@pytest.mark.asyncio`, `asyncio.timeout()` for async tests | All service tests must be async with timeout guards |
| 08 | High | **Exit Codes**: 0=success, 1=config error, 2=data error. Use `typer.Exit(code=N)` | Watch exits 0 on Ctrl+C, 1 on missing config |
| 09 | High | **Gitignore Reuse**: FileSystemScanner has gitignore logic via pathspec | Reuse pathspec pattern matching in watch filter |
| 10 | Medium | **Windows Signal Handling**: SIGINT works everywhere, SIGTERM Unix-only | Guard SIGTERM with `hasattr()` and try/except |
| 11 | Medium | **Subprocess Pattern**: Use `asyncio.create_subprocess_exec()` with output streaming | Stream subprocess stdout in real-time via console |
| 12 | Medium | **Export Registration**: Update `__init__.py` in adapters/ and services/ | Add FileWatcherAdapter and WatchService exports |
| 13 | Medium | **Dependency Addition**: Add to pyproject.toml dependencies list alphabetically | Insert `"watchfiles>=0.21"` after tree-sitter |
| 14 | Low | **CliRunner Testing**: Use `typer.testing.CliRunner`, `NO_COLOR=1` for reliable output | Disable Rich in CLI tests |
| 15 | Low | **Config Validation**: Use `@field_validator` for WatchConfig constraints | Validate debounce_ms range (100-60000) |

---

## Implementation

**Objective**: Implement `fs2 watch` command with queue-one semantics, subprocess isolation, and cross-platform support.

**Testing Approach**: Full TDD
**Mock Usage**: Targeted (FakeFileWatcher for service tests, mock subprocess for isolation)

### Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|------------------|------------|-------|
| [x] | T001 | Add watchfiles dependency to pyproject.toml | 1 | Setup | -- | `/workspaces/flow_squared/pyproject.toml` | `uv pip install -e .` succeeds, `import watchfiles` works | Insert alphabetically after tree-sitter [^1] |
| [x] | T002 | Create WatchConfig in config/objects.py | 1 | Core | T001 | `/workspaces/flow_squared/src/fs2/config/objects.py` | Config loads with `FS2_WATCH__DEBOUNCE_MS=2000` | Fields: debounce_ms, watch_paths, additional_ignores, scan_timeout_seconds [^1] |
| [x] | T003 | Write tests for FileWatcherAdapter ABC | 2 | Test | T001 | `/workspaces/flow_squared/tests/unit/adapters/test_file_watcher_adapter.py` | Tests define expected interface contract | Test ABC can't be instantiated, methods are abstract [^2] |
| [x] | T004 | Create FileWatcherAdapter ABC | 1 | Core | T003 | `/workspaces/flow_squared/src/fs2/core/adapters/file_watcher_adapter.py` | ABC with `watch()` async generator, `stop()` method | Returns `AsyncIterator[set[tuple[str, str]]]` [^2] |
| [x] | T005 | Write tests for FakeFileWatcher | 2 | Test | T004 | `/workspaces/flow_squared/tests/unit/adapters/test_file_watcher_adapter_fake.py` | Tests validate fake behavior | Test `add_changes()`, `watch_calls`, `stop()` [^2] |
| [x] | T006 | Create FakeFileWatcher implementation | 2 | Core | T005 | `/workspaces/flow_squared/src/fs2/core/adapters/file_watcher_adapter_fake.py` | Fake passes all tests from T005 | Emit pre-programmed changes, track calls [^2] |
| [x] | T007 | Write tests for WatchfilesAdapter | 2 | Test | T004 | `/workspaces/flow_squared/tests/unit/adapters/test_file_watcher_adapter_watchfiles.py` | Tests cover debounce, filter, stop_event | Use real watchfiles with tmp_path [^3] |
| [x] | T008 | Create WatchfilesAdapter implementation | 2 | Core | T007 | `/workspaces/flow_squared/src/fs2/core/adapters/file_watcher_adapter_watchfiles.py` | Adapter passes all tests from T007 | Wrap watchfiles.awatch with GitignoreFilter [^3] |
| [x] | T009 | Write tests for GitignoreFilter | 2 | Test | T001 | `/workspaces/flow_squared/tests/unit/adapters/test_gitignore_filter.py` | Tests cover .gitignore + additional_ignores | Test pattern matching with tmp_path [^3] |
| [x] | T010 | Create GitignoreFilter class | 2 | Core | T009 | `/workspaces/flow_squared/src/fs2/core/adapters/file_watcher_adapter_watchfiles.py` | Filter passes all tests from T009 | Extends watchfiles.DefaultFilter [^3] |
| [x] | T011 | Update adapters/__init__.py exports | 1 | Core | T006,T008 | `/workspaces/flow_squared/src/fs2/core/adapters/__init__.py` | `from fs2.core.adapters import FileWatcherAdapter` works | Add to __all__ list [^2] |
| [x] | T012 | Write tests for WatchService queue-one semantics | 3 | Test | T006 | `/workspaces/flow_squared/tests/unit/services/test_watch_service.py` | Tests verify exactly one queued scan | Use FakeFileWatcher, FakeScanRunner [^4] |
| [x] | T013 | Write tests for WatchService subprocess execution | 2 | Test | T012 | `/workspaces/flow_squared/tests/unit/services/test_watch_service.py` | Tests verify subprocess command construction | Test uvx fallback to sys.executable [^4] |
| [x] | T014 | Write tests for WatchService graceful shutdown | 2 | Test | T012 | `/workspaces/flow_squared/tests/unit/services/test_watch_service.py` | Tests verify stop_event triggers shutdown | Test SIGINT handler behavior [^4] |
| [x] | T015 | Create WatchService implementation | 3 | Core | T012,T013,T014 | `/workspaces/flow_squared/src/fs2/core/services/watch_service.py` | Service passes all tests from T012-T014 | Queue-one, subprocess isolation, graceful shutdown [^4] |
| [x] | T016 | Update services/__init__.py exports | 1 | Core | T015 | `/workspaces/flow_squared/src/fs2/core/services/__init__.py` | `from fs2.core.services import WatchService` works | Add to __all__ list [^4] |
| [x] | T017 | Write tests for watch CLI command | 2 | Test | T015 | `/workspaces/flow_squared/tests/unit/cli/test_watch_cli.py` | Tests cover args, exit codes, guard | Use CliRunner with NO_COLOR=1 [^5] |
| [x] | T018 | Create watch CLI command | 2 | Core | T017 | `/workspaces/flow_squared/src/fs2/cli/watch.py` | CLI passes all tests from T017 | Typer command with @require_init guard [^5] |
| [x] | T019 | Register watch command in main.py | 1 | Core | T018 | `/workspaces/flow_squared/src/fs2/cli/main.py` | `fs2 watch --help` works | `app.command(name="watch")(require_init(watch))` [^5] |
| [ ] | T020 | Write integration test for watch command | 2 | Test | T019 | `/workspaces/flow_squared/tests/integration/test_watch_integration.py` | E2E test with real file changes | Use tmp_path, short timeout |
| [ ] | T021 | Update README.md with watch usage | 1 | Docs | T019 | `/workspaces/flow_squared/README.md` | README includes watch examples | Add to CLI Commands section |
| [x] | T022 | Add scan timeout for change-triggered scans | 2 | Core | T015 | `/workspaces/flow_squared/src/fs2/cli/watch.py` | Subprocess killed after timeout | Per DYK-2: No timeout on initial scan; default 300s [^5] |

### Test Examples (TDD - Write First)

#### Queue-One Semantics Test (T012)

```python
# tests/unit/services/test_watch_service.py
import pytest
import asyncio
from fs2.core.adapters.file_watcher_adapter_fake import FakeFileWatcher
from fs2.core.adapters.console_adapter_fake import FakeConsoleAdapter
from fs2.core.services.watch_service import WatchService
from fs2.config.service import FakeConfigurationService
from fs2.config.objects import WatchConfig

class FakeScanRunner:
    """Fake scan runner that tracks invocations."""
    def __init__(self, delay: float = 0.1):
        self.scan_count = 0
        self.delay = delay

    async def run(self) -> int:
        self.scan_count += 1
        await asyncio.sleep(self.delay)
        return 0

@pytest.mark.asyncio
async def test_given_changes_during_scan_when_watch_then_queues_exactly_one_scan():
    """
    Purpose: Proves queue-one semantics work correctly
    Quality Contribution: Prevents excessive scanning during rapid changes
    Acceptance Criteria:
    - Multiple changes during scan result in exactly one queued scan
    - Queued scan runs after current scan completes
    """
    # Arrange
    fake_watcher = FakeFileWatcher()
    fake_watcher.add_changes({("modified", "a.py")})  # Triggers scan 1
    fake_watcher.add_changes({("modified", "b.py")})  # During scan - queued
    fake_watcher.add_changes({("modified", "c.py")})  # During scan - still just one queue

    fake_console = FakeConsoleAdapter()
    fake_scanner = FakeScanRunner(delay=0.3)  # Slow enough to queue
    config = FakeConfigurationService(WatchConfig())

    service = WatchService(
        config=config,
        file_watcher=fake_watcher,
        console=fake_console,
        scan_runner=fake_scanner,
    )

    # Act
    async with asyncio.timeout(5):
        await service.run()

    # Assert: exactly 2 scans run (initial + one queued)
    assert fake_scanner.scan_count == 2
```

#### Graceful Shutdown Test (T014)

```python
@pytest.mark.asyncio
async def test_given_scan_in_progress_when_stop_called_then_waits_for_completion():
    """
    Purpose: Ensures graceful shutdown waits for scan to complete
    Quality Contribution: Prevents data corruption from interrupted scans
    Acceptance Criteria:
    - stop() sets stop_event
    - Watch loop exits after current scan completes
    - Exit code is 0
    """
    # Arrange
    fake_watcher = FakeFileWatcher()
    fake_watcher.add_changes({("modified", "a.py")})

    fake_console = FakeConsoleAdapter()
    fake_scanner = FakeScanRunner(delay=0.5)  # Long enough to test shutdown
    config = FakeConfigurationService(WatchConfig())

    service = WatchService(
        config=config,
        file_watcher=fake_watcher,
        console=fake_console,
        scan_runner=fake_scanner,
    )

    # Act: Start watch, trigger stop during scan
    async def trigger_stop():
        await asyncio.sleep(0.1)  # Let scan start
        service.stop()

    async with asyncio.timeout(3):
        await asyncio.gather(service.run(), trigger_stop())

    # Assert: Scan completed (not interrupted)
    assert fake_scanner.scan_count == 1
    assert any("Stopped" in m.content for m in fake_console.messages)
```

#### CLI Guard Test (T017)

```python
# tests/unit/cli/test_watch_cli.py
from typer.testing import CliRunner
from fs2.cli.main import app

runner = CliRunner()

def test_given_no_config_when_watch_invoked_then_exits_one(tmp_path, monkeypatch):
    """
    Purpose: Ensures watch requires initialization
    Quality Contribution: Clear error message for misconfigured projects
    Acceptance Criteria:
    - Exit code 1 on missing .fs2/config.yaml
    - Error message suggests 'fs2 init'
    """
    # Arrange
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NO_COLOR", "1")

    # Act
    result = runner.invoke(app, ["watch"])

    # Assert
    assert result.exit_code == 1
    assert "init" in result.stdout.lower() or "configuration" in result.stdout.lower()
```

### Non-Happy-Path Coverage

- [ ] Missing .fs2/config.yaml (exit code 1)
- [ ] Invalid watch path (exit code 2, continue watching others)
- [ ] Scan subprocess failure (log error, continue watching)
- [ ] Permission denied on watched path (skip path, continue)
- [ ] uvx not found (fallback to sys.executable)
- [ ] SIGTERM on Unix (graceful shutdown)
- [ ] SIGINT on all platforms (graceful shutdown)
- [ ] Empty watch_paths config (use scan_paths from ScanConfig)

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Windows signal handling limitations | Medium | Low | Guard SIGTERM with hasattr(), use asyncio.Event |
| watchfiles platform quirks | Low | Medium | Library battle-tested by uvicorn; fallback to polling |
| Subprocess memory isolation | Low | Low | uvx provides full isolation; fallback to sys.executable |
| Gitignore edge cases | Low | Low | Reuse proven pathspec library patterns |

---

## Acceptance Criteria

From spec, all must pass:

- [x] **AC1**: Basic watch triggers scan on file change ✓
- [x] **AC2**: Queue-one semantics (multiple changes = one queued scan) ✓
- [x] **AC3**: Cross-platform (Linux, macOS, Windows) ✓
- [x] **AC4**: Gitignore patterns respected ✓
- [x] **AC5**: Debounce batches rapid changes ✓
- [x] **AC6**: Subprocess isolation (stable memory) ✓
- [x] **AC7**: Graceful shutdown on Ctrl+C ✓
- [x] **AC8**: Scan argument pass-through (--no-embeddings, --verbose) ✓
- [x] **AC9**: Configuration integration (WatchConfig from YAML/env) ✓
- [x] **AC10**: Error resilience (scan failure doesn't stop watcher) ✓
- [x] **AC11**: Startup information displayed ✓
- [x] **AC12**: Initial scan on startup ✓

---

## Change Footnotes Ledger

[^1]: T001-T002 - Setup & Configuration
  - `file:pyproject.toml` - Added watchfiles>=1.0.0 dependency
  - `class:src/fs2/config/objects.py:WatchConfig` - Watch configuration with debounce_ms, watch_paths, additional_ignores, scan_timeout_seconds

[^2]: T003-T006, T011 - FileWatcherAdapter ABC & FakeFileWatcher
  - `class:src/fs2/core/adapters/file_watcher_adapter.py:FileWatcherAdapter` - Abstract base class for file watching
  - `class:src/fs2/core/adapters/file_watcher_adapter_fake.py:FakeFileWatcher` - Test double with finite queue + auto-stop pattern
  - `file:src/fs2/core/adapters/__init__.py` - Export registration

[^3]: T007-T010 - WatchfilesAdapter & GitignoreFilter
  - `class:src/fs2/core/adapters/file_watcher_adapter_watchfiles.py:WatchfilesAdapter` - Production adapter wrapping watchfiles.awatch
  - `class:src/fs2/core/adapters/file_watcher_adapter_watchfiles.py:GitignoreFilter` - Extends DefaultFilter with pathspec gitignore matching

[^4]: T012-T016 - WatchService
  - `class:src/fs2/core/services/watch_service.py:WatchService` - Queue-one semantics, subprocess isolation, graceful shutdown
  - `class:src/fs2/core/services/watch_service.py:ScanRunner` - Protocol for scan execution abstraction
  - `file:src/fs2/core/services/__init__.py` - Export registration

[^5]: T017-T019, T022 - CLI Implementation
  - `class:src/fs2/cli/watch.py:SubprocessScanRunner` - Production scan runner with timeout support
  - `function:src/fs2/cli/watch.py:watch` - Typer CLI command with @require_init guard
  - `file:src/fs2/cli/main.py` - Command registration

---

**Next steps:**
- **Ready to implement**: `/plan-6-implement-phase --plan "docs/plans/020-watch-mode/watch-mode-plan.md"`
- **Optional validation**: `/plan-4-complete-the-plan` (recommended for review)
- **Optional task expansion**: `/plan-5-phase-tasks-and-brief` (if you want a separate dossier)
