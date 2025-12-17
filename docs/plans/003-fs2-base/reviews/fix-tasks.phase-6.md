# Phase 6 Fix Tasks

**Review**: [review.phase-6.md](review.phase-6.md)
**Verdict**: REQUEST_CHANGES
**Date**: 2025-12-17

---

## Priority: BLOCKING (Must fix before merge)

### FIX-001: Implement exit code 2 for total failure [CRITICAL]

**File**: `/workspaces/flow_squared/src/fs2/cli/scan.py`
**Lines**: 91-99

**Issue**: Specification requires exit code 2 when all files fail to parse, but implementation only handles exit codes 0 and 1.

**TDD Approach** (test first):

1. Add test to `tests/unit/cli/test_scan_cli.py`:

```python
class TestExitCodes:
    # ... existing tests ...

    def test_given_all_files_fail_when_scan_then_exit_two(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies exit code 2 for total failure.
        Quality Contribution: Ensures CI/CD can detect total scan failures.
        Acceptance Criteria: Exit code is 2 when all files error.
        """
        from fs2.cli.main import app

        # Create project with only unparseable files
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(f"""scan:
  scan_paths:
    - "{tmp_path}"
  respect_gitignore: false
""")

        # Create only binary files that will fail parsing
        (tmp_path / "binary.py").write_bytes(b"\x00\x01\x02\x03")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        # Should exit with code 2 for total failure
        assert result.exit_code == 2, f"Expected exit 2 for total failure, got {result.exit_code}: {result.stdout}"
```

2. Run test (should fail - RED phase):
```bash
uv run pytest tests/unit/cli/test_scan_cli.py::TestExitCodes::test_given_all_files_fail_when_scan_then_exit_two -v
```

3. Implement fix in `scan.py` (GREEN phase):

```python
# After line 92: _display_summary(summary, verbose=verbose)
# Add total failure check:

# Check for total failure (all files errored)
if summary.files_scanned > 0 and len(summary.errors) >= summary.files_scanned:
    raise typer.Exit(code=2)
```

4. Run test again (should pass):
```bash
uv run pytest tests/unit/cli/test_scan_cli.py::TestExitCodes -v
```

---

### FIX-002: Use _should_show_progress() return value [HIGH]

**File**: `/workspaces/flow_squared/src/fs2/cli/scan.py`
**Lines**: 65-66

**Issue**: Return value is discarded; --no-progress and --progress flags have no effect.

**TDD Approach**:

1. Existing tests already check flags work, but verify the flag effect:

```python
class TestProgressFlags:
    def test_given_no_progress_flag_when_checking_should_show_then_returns_false(
        self, monkeypatch
    ):
        """
        Purpose: Verifies --no-progress flag correctly disables progress.
        Quality Contribution: Ensures flag has functional effect.
        Acceptance Criteria: _should_show_progress returns False with --no-progress.
        """
        from fs2.cli.scan import _should_show_progress

        result = _should_show_progress(no_progress=True, force_progress=False)
        assert result is False

    def test_given_progress_flag_when_checking_should_show_then_returns_true(
        self, monkeypatch
    ):
        """
        Purpose: Verifies --progress flag forces progress display.
        Quality Contribution: Ensures flag has functional effect.
        Acceptance Criteria: _should_show_progress returns True with --progress.
        """
        from fs2.cli.scan import _should_show_progress

        result = _should_show_progress(no_progress=False, force_progress=True)
        assert result is True
```

2. Implement fix:

```python
# Line 65-66: Change from:
#     _should_show_progress(no_progress, progress)
# To:
    show_progress = _should_show_progress(no_progress, progress)

# Line 85-89: Use show_progress for future progress bar
# (For now, this stores the value; actual progress bar implementation
# can use this in a future enhancement)
```

3. Optional: Rename parameter for clarity:

```python
def scan(
    verbose: Annotated[...] = False,
    no_progress: Annotated[...] = False,
    force_progress: Annotated[  # Renamed from 'progress'
        bool,
        typer.Option("--progress", help="Force progress spinner even in non-TTY"),
    ] = False,
) -> None:
```

---

## Priority: RECOMMENDED (Post-merge OK)

### FIX-003: Add structured logging at pipeline boundary [HIGH]

**File**: `/workspaces/flow_squared/src/fs2/cli/scan.py`
**Lines**: 68-99

**Patch hint**:
```python
try:
    # Load configuration
    config = FS2ConfigurationService()
    # ... existing pipeline setup ...
    summary = pipeline.run()
    _display_summary(summary, verbose=verbose)

except MissingConfigurationError:
    # ... existing handler ...

except Exception as e:
    logger.error(f"Scan failed: {type(e).__name__}: {e}")
    console.print(f"[red]Error:[/red] {e}")
    raise typer.Exit(code=1) from None
```

---

### FIX-004: Log pipeline errors at WARNING level [HIGH]

**File**: `/workspaces/flow_squared/src/fs2/cli/scan.py`
**Lines**: 133-172

**Patch hint** in `_display_summary()`:
```python
def _display_summary(summary: ScanSummary, verbose: bool = False) -> None:
    # ... existing indicator logic ...

    if summary.errors:
        # Always log errors (not just in verbose mode)
        for error in summary.errors[:5]:  # Show top 5
            console.print(f"  [dim]- {error}[/dim]")
        if len(summary.errors) > 5:
            console.print(f"  [dim]... and {len(summary.errors) - 5} more errors[/dim]")
```

---

### FIX-005: Add type annotation to _display_summary [MEDIUM]

**File**: `/workspaces/flow_squared/src/fs2/cli/scan.py`
**Line**: 133

```python
from fs2.core.models import ScanSummary

def _display_summary(summary: ScanSummary, verbose: bool = False) -> None:
```

---

### FIX-006: Simplify indicator selection logic [MEDIUM]

**File**: `/workspaces/flow_squared/src/fs2/cli/scan.py`
**Lines**: 140-146

```python
# Simplify from:
if summary.success:
    indicator = "[green]✓[/green]"
elif summary.errors:
    indicator = "[yellow]⚠[/yellow]"
else:
    indicator = "[red]✗[/red]"

# To:
if summary.errors:
    indicator = "[yellow]⚠[/yellow]"
else:
    indicator = "[green]✓[/green]"
```

---

### FIX-007: Remove or use logger instance [LOW]

**File**: `/workspaces/flow_squared/src/fs2/cli/scan.py`
**Lines**: 21-22

Option A (remove if not using):
```python
# Delete line 22:
# logger = logging.getLogger("fs2.cli.scan")
```

Option B (use for verbose logging):
```python
# In _setup_verbose_logging():
logger = logging.getLogger("fs2.cli.scan")
logger.setLevel(logging.DEBUG)
```

---

## Verification Commands

After fixes, run:

```bash
# Run all CLI tests
uv run pytest tests/unit/cli/ tests/integration/test_fs2_cli_integration.py -v

# Run lint
uv run ruff check src/fs2/cli/

# Run type check
uv run mypy src/fs2/cli/ --ignore-missing-imports

# Verify exit code 2 works
cd /tmp && mkdir test-fail && cd test-fail
fs2 init
echo -e '\x00\x01' > binary.py
fs2 scan; echo "Exit code: $?"
# Should show: Exit code: 2
```

---

## Re-review Checklist

After fixing BLOCKING issues:

- [ ] FIX-001 test passes
- [ ] FIX-002 return value stored
- [ ] All 33+ tests pass (32 original + 1 new)
- [ ] Lint clean
- [ ] Type check clean
- [ ] Rerun `/plan-7-code-review --phase 6` for final approval
