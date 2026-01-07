# Research Dossier: Watch Command for fs2

**Generated**: 2026-01-06
**Research Query**: "Implement a watch command that monitors file changes and triggers scans"
**Mode**: Plan-Associated
**Plan Folder**: `docs/plans/020-watch-mode`
**FlowSpace**: Available
**Findings**: 55+ from 6 research subagents

---

## Executive Summary

### What It Does
A `fs2 watch` command will monitor specified directories for file changes and automatically trigger `fs2 scan` when changes are detected, using subprocess isolation for memory management and debouncing to coalesce rapid changes.

### Business Purpose
Enables real-time code intelligence updates during development. Developers get up-to-date code graphs without manually running `fs2 scan` after every change.

### Key Insights
1. **watchfiles library** (Rust-based) is the recommended choice - built-in debouncing, cross-platform, async-native
2. **Subprocess isolation** via `uvx` prevents memory leaks in long-running watcher
3. **Existing patterns** in fs2 (CLI composition, config loading, guard decorator) should be followed

### Quick Stats
- **Existing shell script**: 284 lines (`scripts/fs2-watch.sh`)
- **Dependencies to add**: `watchfiles` (2.3k stars, used by uvicorn)
- **Platforms**: Linux (inotify), macOS (FSEvents), Windows (ReadDirectoryChangesW)
- **Prior Learnings**: 15 relevant discoveries from previous implementations

---

## How It Currently Works (Shell Script Analysis)

### Entry Points
The existing `scripts/fs2-watch.sh` provides three backends:

| Watcher | Platform | Behavior |
|---------|----------|----------|
| watchexec | All | Recommended - kills running scan on new changes, 2s debounce |
| fswatch | macOS | Events queue during scans, no cancellation |
| inotifywait | Linux | Events may be missed during scans |

### Shell Script Implementation Details

```bash
# Key patterns from scripts/fs2-watch.sh

# Debounce: 2 seconds to batch rapid changes
--debounce 2s

# Standard ignore patterns (hardcoded)
--ignore ".fs2/**"
--ignore "**/*.pickle"
--ignore "**/__pycache__/**"
--ignore ".git/**"
--ignore "**/*.pyc"
--ignore ".uv_cache/**"

# watchexec uses --restart to kill running scan on new changes
exec watchexec "${cmd_args[@]}" \
    --debounce 2s \
    --restart \
    -- fs2 scan "${SCAN_ARGS[@]}"
```

### Current Limitations
1. **No Windows support** - requires bash, external tools (watchexec/fswatch/inotifywait)
2. **No queuing logic** - watchexec cancels in-progress scans, fswatch/inotify queue indefinitely
3. **External dependency** - requires users to install watchexec/fswatch/inotifywait separately
4. **No integration** with fs2 config system (hardcoded ignore patterns)
5. **No graceful queue-one semantics** - either cancel or queue all

### Patterns to Preserve
- 2 second debounce is reasonable for development workflows
- Standard ignore patterns for Python projects
- Support for `--no-embeddings` and `--verbose` pass-through

---

## Architecture & Design

### Component Map

```
src/fs2/
├── cli/
│   └── watch.py              # NEW: CLI command (arg parsing, Rich output)
├── core/
│   ├── services/
│   │   └── watch_service.py  # NEW: Business logic (debounce, queue, subprocess)
│   └── adapters/
│       ├── file_watcher_adapter.py      # NEW: ABC interface
│       └── file_watcher_watchfiles.py   # NEW: watchfiles implementation
└── config/
    └── objects.py            # MODIFY: Add WatchConfig
```

### Clean Architecture Compliance

Per Constitution **P9** and Prior Learning **PL-05**: Business logic MUST reside in service layer, not CLI.

```
CLI (watch.py)           Service (watch_service.py)      Adapter (file_watcher_*.py)
┌─────────────────┐      ┌────────────────────────┐      ┌─────────────────────────┐
│ • Parse args    │      │ • Debounce logic       │      │ • watchfiles wrapper    │
│ • Rich output   │      │ • Queue management     │      │ • Cross-platform events │
│ • Signal setup  │ ──►  │ • Subprocess spawning  │ ──►  │ • Gitignore filtering   │
│ • Exit codes    │      │ • Event filtering      │      │ • Stop event handling   │
└─────────────────┘      └────────────────────────┘      └─────────────────────────┘
```

### Proposed WatchConfig

```python
class WatchConfig(BaseModel):
    """Configuration for watch command.

    Path: watch (e.g., FS2_WATCH__DEBOUNCE_MS)

    YAML example:
        ```yaml
        watch:
          debounce_ms: 1600
          additional_ignores:
            - "**/*.log"
        ```
    """
    __config_path__: ClassVar[str] = "watch"

    debounce_ms: int = 1600        # Match watchfiles default
    watch_paths: list[str] | None = None  # None = use scan_paths from ScanConfig
    respect_gitignore: bool = True
    additional_ignores: list[str] = [
        ".fs2/**",
        "**/__pycache__/**",
        "**/*.pyc",
        "**/*.pickle",
        ".uv_cache/**",
    ]
```

---

## Dependencies & Integration

### New Dependency: watchfiles

```toml
# pyproject.toml
dependencies = [
    "watchfiles>=1.0.0",  # Rust-based, cross-platform file watcher
]
```

**Why watchfiles over watchdog:**

| Feature | watchfiles | watchdog |
|---------|------------|----------|
| Debouncing | Built-in (Rust) | Manual (Python Timer) |
| Async support | Native `awatch()` | Threading only |
| Stop mechanism | `stop_event` parameter | `observer.stop()` |
| Memory | Rust core, efficient | Pure Python |
| Used by | uvicorn (163k projects) | Django, many others |
| kqueue (macOS) | FSEvents (better) | kqueue (FD limits) |

### Cross-Platform Support

Both libraries support all platforms with native notification systems:

| Platform | watchfiles Backend | Notes |
|----------|-------------------|-------|
| Linux | inotify via Rust notify | Best performance |
| macOS | FSEvents via Rust notify | No FD limits |
| Windows | ReadDirectoryChangesW | Full support |
| Fallback | Polling (`force_polling=True`) | Works everywhere |

**watchfiles binaries available for:**
- Linux: x86_64, aarch64, i686, armv7l, musl variants
- macOS: x86_64, aarch64 (Apple Silicon)
- Windows: x86_64, aarch64, i686

### Internal Dependencies

| Depends On | Type | Purpose |
|------------|------|---------|
| `FS2ConfigurationService` | Required | Load WatchConfig, ScanConfig |
| `ConsoleAdapter` | Required | Rich output abstraction |
| `pathspec` | Already present | Gitignore pattern matching |

---

## Proposed Implementation

### Watch Command Flow

```
User: fs2 watch ./src ./tests --no-embeddings
              │
              ▼
┌─────────────────────────────────────────────────────┐
│ CLI: watch.py                                       │
│                                                     │
│ 1. Parse args (watch_paths, scan_args)              │
│ 2. Load WatchConfig via ConfigurationService        │
│ 3. Setup signal handlers (SIGINT, SIGTERM)          │
│ 4. Create WatchService with adapter                 │
│ 5. Enter async watch loop                           │
└─────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────┐
│ Service: watch_service.py                           │
│                                                     │
│ async def watch():                                  │
│   async for changes in adapter.watch():            │
│     if self._scan_in_progress:                     │
│       self._queue_scan = True  # Don't start new   │
│       continue                                      │
│     await self._run_scan()                         │
│     if self._queue_scan:                           │
│       self._queue_scan = False                     │
│       await self._run_scan()  # Run queued scan    │
└─────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────┐
│ Subprocess: uvx fs2 scan (or python -m fs2 scan)   │
│                                                     │
│ • Process isolation (memory safety)                 │
│ • Inherits scan args (--no-embeddings, etc.)        │
│ • Output streamed to console in real-time          │
│ • Non-zero exit doesn't stop watcher                │
└─────────────────────────────────────────────────────┘
```

### Core Queue Semantics

**Requirement**: If a scan is in progress and files change, queue ONE scan (not per-file).

```python
class WatchService:
    """Service for watching files and triggering scans.

    Implements queue-one semantics: if changes occur during a scan,
    exactly one follow-up scan is queued regardless of how many
    files changed.
    """

    def __init__(
        self,
        config: ConfigurationService,
        file_watcher: FileWatcherAdapter,
        console: ConsoleAdapter,
        scan_args: list[str] | None = None,
    ):
        self._config = config
        self._watcher = file_watcher
        self._console = console
        self._scan_args = scan_args or []

        self._scan_in_progress = False
        self._scan_queued = False
        self._stop_event = asyncio.Event()

    async def _on_changes(self, changes: set[tuple[str, str]]):
        """Handle file changes with queue-one semantics."""
        change_count = len(changes)

        if self._scan_in_progress:
            # Scan running - queue one follow-up scan
            self._scan_queued = True
            self._console.print_info(
                f"{change_count} change(s) queued (scan in progress)"
            )
            return

        self._console.print_info(f"{change_count} file(s) changed, starting scan...")
        await self._run_scan()

        # After scan completes, check if more changes queued
        if self._scan_queued:
            self._scan_queued = False
            self._console.print_info("Running queued scan...")
            await self._run_scan()
```

### Subprocess Isolation Pattern

Per user requirement: Use subprocess + uvx for memory isolation.

```python
async def _run_scan(self) -> int:
    """Run scan in isolated subprocess.

    Uses uvx for full environment isolation, preventing memory
    leaks from accumulating in long-running watch processes.
    """
    self._scan_in_progress = True
    start_time = time.monotonic()

    # Build command: uvx fs2 scan [args]
    cmd = ["uvx", "fs2", "scan"] + self._scan_args

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=Path.cwd(),
        )

        # Stream output in real-time
        async for line in proc.stdout:
            self._console.print(line.decode().rstrip())

        await proc.wait()

        elapsed = time.monotonic() - start_time
        if proc.returncode == 0:
            self._console.print_success(f"Scan completed in {elapsed:.1f}s")
        else:
            self._console.print_warning(
                f"Scan exited with code {proc.returncode} ({elapsed:.1f}s)"
            )

        return proc.returncode

    except FileNotFoundError:
        self._console.print_error("uvx not found - install uv first")
        return 1
    finally:
        self._scan_in_progress = False
```

### Cross-Platform Signal Handling

Per Signal Handling research **SH-02**: Windows has limited signals.

```python
def _setup_signals(self):
    """Cross-platform graceful shutdown.

    SIGINT (Ctrl+C) works everywhere.
    SIGTERM only available on Unix.
    """
    loop = asyncio.get_running_loop()

    def handler():
        self._console.print_info("\nStopping watcher...")
        self._stop_event.set()

    # SIGINT works everywhere (Ctrl+C)
    loop.add_signal_handler(signal.SIGINT, handler)

    # SIGTERM only on Unix
    if hasattr(signal, 'SIGTERM'):
        try:
            loop.add_signal_handler(signal.SIGTERM, handler)
        except NotImplementedError:
            pass  # Windows doesn't support add_signal_handler for SIGTERM
```

### Gitignore Integration

Reuse existing fs2 gitignore handling via pathspec:

```python
from watchfiles import awatch, Change, DefaultFilter
import pathspec

class GitignoreFilter(DefaultFilter):
    """Filter that respects .gitignore patterns and additional ignores."""

    def __init__(self, root: Path, additional_ignores: list[str]):
        super().__init__()
        self.root = root
        self.specs: list[pathspec.PathSpec] = []

        # Load .gitignore if present
        gitignore = root / ".gitignore"
        if gitignore.exists():
            lines = gitignore.read_text().splitlines()
            # Filter empty lines and comments
            patterns = [l for l in lines if l.strip() and not l.startswith("#")]
            if patterns:
                self.specs.append(
                    pathspec.PathSpec.from_lines("gitwildmatch", patterns)
                )

        # Add additional ignore patterns
        if additional_ignores:
            self.specs.append(
                pathspec.PathSpec.from_lines("gitwildmatch", additional_ignores)
            )

    def __call__(self, change: Change, path: str) -> bool:
        """Return True to watch this path, False to ignore."""
        # First apply default filters (hidden files, etc.)
        if not super().__call__(change, path):
            return False

        # Then apply gitignore patterns
        try:
            rel_path = Path(path).relative_to(self.root)
            rel_str = str(rel_path).replace("\\", "/")  # Normalize for Windows
            return not any(spec.match_file(rel_str) for spec in self.specs)
        except ValueError:
            return True  # Path not under root, allow it
```

### FileWatcher Adapter ABC

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator

class FileWatcherAdapter(ABC):
    """Abstract interface for file watching.

    Implementations wrap platform-specific file watching libraries.
    """

    @abstractmethod
    async def watch(self) -> AsyncIterator[set[tuple[str, str]]]:
        """Watch for file changes.

        Yields:
            Sets of (change_type, path) tuples where change_type is
            one of: "added", "modified", "deleted"
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Signal the watcher to stop."""
        ...
```

### watchfiles Implementation

```python
from watchfiles import awatch, Change

class WatchfilesAdapter(FileWatcherAdapter):
    """watchfiles-based file watcher implementation."""

    CHANGE_MAP = {
        Change.added: "added",
        Change.modified: "modified",
        Change.deleted: "deleted",
    }

    def __init__(
        self,
        paths: list[Path],
        debounce_ms: int,
        watch_filter: GitignoreFilter,
    ):
        self._paths = [str(p) for p in paths]
        self._debounce_ms = debounce_ms
        self._filter = watch_filter
        self._stop_event = asyncio.Event()

    async def watch(self) -> AsyncIterator[set[tuple[str, str]]]:
        """Watch paths for changes using watchfiles."""
        async for changes in awatch(
            *self._paths,
            watch_filter=self._filter,
            debounce=self._debounce_ms,
            stop_event=self._stop_event,
            recursive=True,
        ):
            # Convert watchfiles Change enum to string
            yield {
                (self.CHANGE_MAP[change_type], path)
                for change_type, path in changes
            }

    def stop(self) -> None:
        """Signal watcher to stop."""
        self._stop_event.set()
```

---

## CLI Interface Design

### Command Signature

```
fs2 watch [OPTIONS] [PATHS...]

Watch for file changes and automatically run fs2 scan.

Arguments:
  PATHS    Directories to watch (default: scan_paths from config)

Options:
  --debounce INT       Milliseconds to wait for changes to settle [default: 1600]
  --no-embeddings      Pass --no-embeddings to scan command
  --no-smart-content   Pass --no-smart-content to scan command
  --verbose, -v        Show verbose output from scans
  --help               Show this message and exit

Examples:
  fs2 watch                        # Watch paths from config
  fs2 watch ./src ./tests          # Watch specific directories
  fs2 watch --no-embeddings        # Fast mode (no API calls)
  fs2 watch --debounce 3000        # 3 second debounce
```

### CLI Implementation Pattern

Following established patterns from **PS-01** through **PS-10**:

```python
from typing import Annotated
import typer
import asyncio

from fs2.cli.guard import require_init
from fs2.core.adapters.console_adapter import ConsoleAdapter, RichConsoleAdapter


def watch(
    ctx: typer.Context,
    paths: Annotated[
        list[str] | None,
        typer.Argument(help="Directories to watch (default: scan_paths from config)"),
    ] = None,
    debounce: Annotated[
        int,
        typer.Option("--debounce", help="Milliseconds to wait for changes to settle"),
    ] = 1600,
    no_embeddings: Annotated[
        bool,
        typer.Option("--no-embeddings", help="Pass --no-embeddings to scan"),
    ] = False,
    no_smart_content: Annotated[
        bool,
        typer.Option("--no-smart-content", help="Pass --no-smart-content to scan"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show verbose scan output"),
    ] = False,
) -> None:
    """Watch for file changes and automatically run fs2 scan.

    Monitors directories for changes and triggers scans automatically.
    Uses debouncing to batch rapid changes. If a scan is already running
    when new changes occur, queues exactly one follow-up scan.

    \b
    Examples:
        $ fs2 watch                     # Watch paths from config
        $ fs2 watch ./src               # Watch specific directory
        $ fs2 watch --no-embeddings     # Fast mode

    \b
    Exit codes:
        0 - Clean shutdown (Ctrl+C)
        1 - Configuration error
        2 - Watch setup error
    """
    console: ConsoleAdapter = RichConsoleAdapter()

    # Build scan args to pass through
    scan_args = []
    if no_embeddings:
        scan_args.append("--no-embeddings")
    if no_smart_content:
        scan_args.append("--no-smart-content")
    if verbose:
        scan_args.append("--verbose")

    # Pass through --graph-file if set globally
    if ctx.obj and ctx.obj.graph_file:
        scan_args.extend(["--graph-file", ctx.obj.graph_file])

    try:
        asyncio.run(_watch_async(
            console=console,
            paths=paths,
            debounce_ms=debounce,
            scan_args=scan_args,
        ))
    except KeyboardInterrupt:
        console.print_info("Stopped")
        raise typer.Exit(0)
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Clean shutdown (Ctrl+C or SIGTERM) |
| 1 | Configuration error (missing config, invalid WatchConfig) |
| 2 | Watch setup error (permission denied, path not found) |

---

## Prior Learnings Applied

| ID | Learning | Application to Watch Command |
|----|----------|------------------------------|
| **PL-01** | Decorator guards block --help | Apply `@require_init` correctly before `@app.command()` |
| **PL-02** | DI for config access | Inject `ConfigurationService`, call `require(WatchConfig)` |
| **PL-03** | Frozen dataclasses need `replace()` | Any watch state objects should be immutable |
| **PL-05** | Business logic in service layer | `WatchService` holds debounce/queue logic, not CLI |
| **PL-07** | Input mode detection order | Careful path validation in watch_paths |
| **PL-10** | Icon mapping for Rich | `WATCH_ICONS = {"added": "+", "modified": "~", "deleted": "-"}` |
| **PL-12** | Fakes over mocks | Create `FakeFileWatcher` for testing, not `unittest.mock` |
| **PL-14** | Use `.exists()` over `.is_dir()` | Robust path checking for watch directories |
| **PL-15** | Conservative defaults | 1600ms debounce (not 100ms), don't over-filter |

---

## Quality & Testing

### Test Strategy

**Unit Tests** - Test queue semantics with `FakeFileWatcher`:

```python
# tests/unit/services/test_watch_service.py

class FakeFileWatcher(FileWatcherAdapter):
    """Fake watcher for testing queue semantics."""

    def __init__(self):
        self.changes_to_emit: list[set[tuple[str, str]]] = []
        self._stopped = False

    async def watch(self):
        for changes in self.changes_to_emit:
            if self._stopped:
                break
            yield changes

    def stop(self):
        self._stopped = True


class FakeScanRunner:
    """Fake scan runner that tracks invocations."""

    def __init__(self, delay: float = 0.1):
        self.scan_count = 0
        self.delay = delay

    async def run(self) -> int:
        self.scan_count += 1
        await asyncio.sleep(self.delay)
        return 0


async def test_given_changes_during_scan_when_watch_then_queues_one_scan():
    """Changes during scan result in exactly one queued follow-up."""
    watcher = FakeFileWatcher()
    watcher.changes_to_emit = [
        {("modified", "a.py")},  # Triggers scan 1
        {("modified", "b.py")},  # During scan - queued
        {("modified", "c.py")},  # During scan - still just one queue
    ]

    scanner = FakeScanRunner(delay=0.5)  # Slow enough to queue
    service = WatchService(watcher=watcher, scan_runner=scanner, ...)

    await service.run()

    # Assert: exactly 2 scans run (initial + one queued)
    assert scanner.scan_count == 2
```

**Integration Tests** - Test with real filesystem:

```python
# tests/integration/test_watch_cli.py

async def test_given_file_change_when_watching_then_triggers_scan(tmp_path):
    """Watch command triggers scan on file modification."""
    # Setup: Create minimal project
    fs2_dir = tmp_path / ".fs2"
    fs2_dir.mkdir()
    (fs2_dir / "config.yaml").write_text("scan:\n  scan_paths: ['.']")
    (tmp_path / "test.py").write_text("x = 1")

    # Initial scan to create graph
    result = subprocess.run(
        ["python", "-m", "fs2", "scan"],
        cwd=tmp_path,
        capture_output=True,
    )
    assert result.returncode == 0

    # Start watcher in background, make change, verify scan triggered
    # ... (async test with timeout)
```

### Test Coverage Goals

- Queue-one semantics (multiple changes = one queued scan)
- Graceful shutdown on SIGINT
- Gitignore pattern filtering
- Debounce behavior (rapid changes batched)
- Scan argument pass-through
- Error handling (missing paths, permission errors)

---

## What a Robust Watch Should Report

Based on user requirement: "consider what else a robust scan should do and report"

### 1. Startup Information

```
fs2 watch started
  Watching: ./src, ./tests (2 paths)
  Debounce: 1600ms
  Gitignore: enabled (.gitignore + 5 additional patterns)
  Files in scope: ~847 files
  Press Ctrl+C to stop
```

### 2. Per-Change Information

```
[12:34:56] 3 file(s) changed:
  ~ src/core/services/scan_service.py
  + src/core/services/watch_service.py
  - tests/old_test.py

[12:34:56] Starting scan...
  ... (streamed scan output) ...
[12:34:58] Scan completed in 2.3s (1,247 nodes)
```

### 3. Queue Status

```
[12:35:01] 2 file(s) changed (scan in progress, queued)
[12:35:03] Scan completed in 1.8s
[12:35:03] Running queued scan...
```

### 4. Error Handling

```
[12:36:00] Scan failed (exit code 2)
  Continuing to watch...

[12:37:00] Permission denied: /root/secrets
  Skipping path, continuing to watch others...
```

### 5. Graceful Shutdown

```
^C
[12:40:00] Stopping watcher...
[12:40:00] Waiting for scan to complete...
[12:40:02] Stopped (5 scans completed in session)
```

---

## Recommendations

### Implementation Approach

1. **Add `watchfiles` dependency** to pyproject.toml
2. **Create WatchConfig** in `config/objects.py`
3. **Implement FileWatcherAdapter ABC** in `core/adapters/`
4. **Implement WatchfilesAdapter** with gitignore filtering
5. **Implement WatchService** with queue-one semantics
6. **Add CLI command** following established patterns
7. **Write comprehensive tests** with FakeFileWatcher

### Key Decisions to Make

| Decision | Option A | Option B | Recommendation |
|----------|----------|----------|----------------|
| Subprocess command | `uvx fs2` | `sys.executable -m fs2` | `uvx` for full isolation |
| Default watch paths | Require explicit | Use `scan_paths` from config | Use config defaults |
| Output streaming | Real-time | Buffer and summarize | Real-time |
| Cancel vs Queue | Cancel running scan | Queue one follow-up | Queue (per requirements) |

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| watchfiles dependency size | Medium | Rust binary is ~2MB, acceptable |
| Windows async signal handling | Low | Use threading.Event fallback |
| Memory in subprocess | Low | uvx provides full isolation |
| Gitignore edge cases | Low | Reuse proven pathspec library |

---

## External Research Opportunities

No critical external research gaps identified. The codebase patterns and library documentation provide sufficient guidance.

**Optional research** if implementation encounters issues:
- watchfiles Windows-specific quirks (if any)
- uvx subprocess environment inheritance details

---

## Next Steps

1. **Proceed to specification**: Run `/plan-1b-specify "watch command"` to create formal spec
2. **Or proceed directly to architecture**: Run `/plan-3-architect` if spec is clear enough

---

**Research Complete**: 2026-01-06
**Report Location**: `docs/plans/020-watch-mode/research-dossier.md`
**Recommended Library**: watchfiles
**Estimated Components**: 4-5 new files (CLI, service, adapter ABC, adapter impl, config)
