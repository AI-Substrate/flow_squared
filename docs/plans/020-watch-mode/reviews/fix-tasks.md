# Watch Mode - Fix Tasks

**Plan**: `/workspaces/flow_squared/docs/plans/020-watch-mode/watch-mode-plan.md`
**Review**: `/workspaces/flow_squared/docs/plans/020-watch-mode/reviews/review.md`
**Verdict**: REQUEST_CHANGES
**Date**: 2026-01-12

---

## Priority Order

Fix tasks are ordered by severity. **Testing Approach: Full TDD** - write tests first where applicable.

---

## CRITICAL Fixes (Must Complete)

### FIX-001: Add logging to WatchService

**Finding**: OBS-002, OBS-004
**File**: `/workspaces/flow_squared/src/fs2/core/services/watch_service.py`
**Severity**: CRITICAL

**Issue**: Zero logging infrastructure in the service layer. Exception at line 213 is silently swallowed, violating DYK-5 "log and continue" pattern.

**Patch**:
```python
# At top of file, add:
import logging

logger = logging.getLogger(__name__)

# In __init__, add:
logger.debug("WatchService initialized with %d watch paths", len(self._watch_config.watch_paths or []))

# In _run_scan (line 208-217), replace exception handling:
async def _run_scan(
    self,
    triggered_by: set[tuple[str, str]] | None = None,
) -> int:
    """Execute a scan via the scan runner."""
    self._scan_in_progress = True
    logger.debug("Starting scan, triggered_by=%s", triggered_by)
    try:
        args = ["scan"] + self._scan_args
        result = await self._scan_runner.run(args, triggered_by=triggered_by)
        logger.info("Scan completed with exit code %d", result)
        return result
    except Exception as e:
        # Per DYK-5: Log and continue
        logger.exception("Scan failed: %s", e)
        return 1
    finally:
        self._scan_in_progress = False

# In _watch_loop (around line 177-179), add:
if self._scan_in_progress:
    logger.debug("Scan in progress, queueing next scan (queue-one)")
    self._scan_queued = True
else:
    logger.debug("No scan in progress, triggering immediate scan")
    await self._run_scan(triggered_by=changes)

# In stop() (line 219-226), add:
def stop(self) -> None:
    """Request graceful shutdown."""
    logger.info("Stop requested, initiating graceful shutdown")
    self._stop_event.set()
    self._file_watcher.stop()
```

**Validation**: Run tests, verify no regression. Check logs appear during manual test.

---

### FIX-002: Add logging to WatchfilesAdapter

**Finding**: OBS-003, OBS-009
**File**: `/workspaces/flow_squared/src/fs2/core/adapters/file_watcher_adapter_watchfiles.py`
**Severity**: CRITICAL

**Issue**: File watcher operations produce no logs. Filter decisions, gitignore loading, and stop events are invisible.

**Patch**:
```python
# At top of file, add:
import logging

logger = logging.getLogger(__name__)

# In GitignoreFilter.__init__ (around line 76-93), add logging:
def __init__(
    self,
    root_path: Path,
    additional_ignores: list[str] | None = None,
) -> None:
    super().__init__()
    self._root_path = root_path
    self._patterns: list[str] = list(self._BUILTIN_IGNORES)

    gitignore_path = root_path / ".gitignore"
    if gitignore_path.exists():
        gitignore_content = gitignore_path.read_text()
        for line in gitignore_content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                self._patterns.append(line)
        logger.debug("Loaded %d patterns from %s", len(self._patterns), gitignore_path)
    else:
        logger.debug("No .gitignore found at %s", gitignore_path)

    if additional_ignores:
        self._patterns.extend(additional_ignores)
        logger.debug("Added %d additional ignore patterns", len(additional_ignores))

    # Create pathspec matcher
    if self._patterns:
        self._spec = pathspec.PathSpec.from_lines("gitwildmatch", self._patterns)
        logger.debug("GitignoreFilter initialized with %d total patterns", len(self._patterns))
    else:
        self._spec = None

# In WatchfilesAdapter.__init__ (around line 168-185), add:
logger.debug(
    "WatchfilesAdapter initialized: paths=%s, debounce=%dms",
    [str(p) for p in watch_paths],
    debounce_ms,
)

# In stop() (line 245-253), add:
def stop(self) -> None:
    """Request graceful shutdown."""
    logger.debug("Stop requested for file watcher")
    self._stop_event.set()
```

**Validation**: Run gitignore filter tests, verify logs appear at DEBUG level.

---

## HIGH Fixes (Should Complete)

### FIX-003: Use declared logger in watch.py

**Finding**: OBS-001
**File**: `/workspaces/flow_squared/src/fs2/cli/watch.py`
**Severity**: HIGH

**Issue**: Logger declared at line 37 but never used. All output goes to console only.

**Patch**:
```python
# Line 37 already has: logger = logging.getLogger("fs2.cli.watch")

# In watch() function, add logging at key points:

# After config loading (around line 178-180):
logger.info("Watch mode starting with %d paths", len(resolved_paths))
logger.debug("Debounce: %dms, Timeout: %ds", watch_config.debounce_ms, watch_config.scan_timeout_seconds)

# In signal handler (lines 225-227):
def handle_signal(signum, frame):
    logger.info("Received signal %d, initiating shutdown", signum)
    console.print_info("\nShutting down...")
    service.stop()

# After successful completion (line 237):
logger.info("Watch mode stopped gracefully")
console.print_success("Stopped.")

# In MissingConfigurationError handler (lines 239-243):
except MissingConfigurationError:
    logger.warning("No configuration found, suggesting 'fs2 init'")
    console.print_error(...)

# In generic exception handler (lines 248-250):
except Exception as e:
    logger.exception("Watch failed: %s", e)
    console.print_error(f"Watch failed: {e}")
    raise typer.Exit(code=1) from None
```

**Validation**: Run CLI tests, verify logs appear with `--verbose` or appropriate log level.

---

### FIX-004: Fix task leak on initial scan failure

**Finding**: COR-004
**File**: `/workspaces/flow_squared/src/fs2/core/services/watch_service.py`
**Lines**: 144-151
**Severity**: HIGH

**Issue**: If `_run_scan()` raises during initial scan, `watch_task` is never cancelled/awaited, causing task leak.

**Patch**:
```python
async def run(self) -> None:
    """Run the watch loop."""
    # Start watching immediately (DYK-3: race condition prevention)
    watch_task = asyncio.create_task(self._watch_loop())

    try:
        # Run initial scan (no timeout per DYK-2)
        await self._run_scan()

        # Wait for watch loop to complete
        await watch_task

        # Run any final queued scan
        if self._scan_queued and not self._stop_event.is_set():
            self._scan_queued = False
            await self._run_scan()

    except asyncio.CancelledError:
        pass
    except Exception:
        # Cancel watch_task if initial scan fails
        watch_task.cancel()
        try:
            await watch_task
        except asyncio.CancelledError:
            pass
        raise
    finally:
        self._file_watcher.stop()
```

**Validation**: Write a test that forces initial scan to raise, verify no asyncio warning about pending task.

---

## MEDIUM Fixes (Recommended)

### FIX-005: Signal handler thread safety

**Finding**: COR-008
**File**: `/workspaces/flow_squared/src/fs2/cli/watch.py`
**Lines**: 225-232
**Severity**: MEDIUM

**Issue**: Signal handler calls `asyncio.Event.set()` from sync context, not thread-safe on Python < 3.10.

**Patch**:
```python
# Store event loop reference before asyncio.run()
loop = None

def handle_signal(signum, frame):
    logger.info("Received signal %d", signum)
    console.print_info("\nShutting down...")
    if loop and loop.is_running():
        loop.call_soon_threadsafe(service.stop)
    else:
        service.stop()

signal.signal(signal.SIGINT, handle_signal)
if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, handle_signal)

# Run with loop reference
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    loop.run_until_complete(service.run())
finally:
    loop.close()
```

**Alternative**: Document Python 3.10+ requirement for signal safety, or accept current behavior with known limitation.

---

### FIX-006: Add timeout to post-kill wait

**Finding**: COR-001
**File**: `/workspaces/flow_squared/src/fs2/cli/watch.py`
**Lines**: 119-130
**Severity**: MEDIUM

**Issue**: After killing timed-out subprocess, `proc.wait()` could hang if process refuses to die.

**Patch**:
```python
except TimeoutError:
    # Kill the subprocess
    proc.kill()
    try:
        await asyncio.wait_for(proc.wait(), timeout=5.0)
    except TimeoutError:
        logger.warning("Subprocess did not respond to kill after 5s")
    self._console.print_error(
        f"Scan timed out after {self._timeout_seconds}s"
    )
    return 124
```

---

### FIX-007: Update docstring examples to use absolute paths

**Finding**: UNI-005, UNI-006
**Files**: `file_watcher_adapter_watchfiles.py`, `watch_service.py`
**Severity**: HIGH (documentation)

**Issue**: Docstring examples show relative paths like `Path("./src")` which could mislead implementers.

**Patch**:
```python
# In WatchfilesAdapter docstring:
"""
Usage:
    ```python
    from pathlib import Path

    project_root = Path("/absolute/path/to/project")
    adapter = WatchfilesAdapter(
        watch_paths=[project_root / "src", project_root / "tests"],
        debounce_ms=1600,
    )
    ```
"""

# In WatchService docstring:
"""
Usage:
    ```python
    project_root = Path("/absolute/path/to/project")
    watcher = WatchfilesAdapter(watch_paths=[project_root / "src"])
    ```
"""
```

---

## LOW Fixes (Optional)

### FIX-008: Fix returncode handling

**Finding**: COR-002
**File**: `/workspaces/flow_squared/src/fs2/cli/watch.py`
**Line**: 135

```python
# Change:
return proc.returncode or 0
# To:
return proc.returncode if proc.returncode is not None else 0
```

### FIX-009: Use deque for FakeFileWatcher queue

**Finding**: PERF-003
**File**: `/workspaces/flow_squared/src/fs2/core/adapters/file_watcher_adapter_fake.py`

```python
from collections import deque

# Change _change_queue from list to deque:
self._change_queue: deque[set[FileChange]] = deque()

# Change pop(0) to popleft():
changes = self._change_queue.popleft()
```

### FIX-010: Remove redundant stop check

**Finding**: COR-007
**File**: `/workspaces/flow_squared/src/fs2/core/adapters/file_watcher_adapter_watchfiles.py`
**Lines**: 237-239

```python
# Remove these lines (dead code - awatch handles stop_event):
# Check if stop was requested during processing
if self._stop_event.is_set():
    break
```

---

## Execution Order

1. **FIX-001** (CRITICAL) - Add logging to WatchService
2. **FIX-002** (CRITICAL) - Add logging to WatchfilesAdapter
3. **FIX-003** (HIGH) - Use logger in watch.py
4. **FIX-004** (HIGH) - Fix task leak
5. Run tests: `pytest tests/unit/services/test_watch_service.py tests/unit/cli/test_watch_cli.py -v`
6. Run manual test: `fs2 watch --verbose` in a test directory
7. Verify logs appear in output
8. Rerun code review: `/plan-7-code-review --plan "..."`

---

## Verification Commands

```bash
# Run all watch-related tests
pytest tests/unit/adapters/test_file_watcher*.py \
       tests/unit/adapters/test_gitignore*.py \
       tests/unit/services/test_watch_service.py \
       tests/unit/cli/test_watch_cli.py -v

# Check linting
ruff check src/fs2/cli/watch.py src/fs2/core/services/watch_service.py \
           src/fs2/core/adapters/file_watcher_adapter*.py

# Manual verification (requires initialized project)
cd /path/to/test/project
fs2 init
fs2 watch --verbose --no-embeddings
# Make a file change, verify scan triggers with logs
```

---

**Next step after fixes**: Rerun `/plan-7-code-review --plan "docs/plans/020-watch-mode/watch-mode-plan.md"` to verify all findings addressed.
