# Fix Tasks: Phase 1: Foundation — Config, CLI, Service Skeleton

Apply in order. Re-run review after fixes.

## Critical / High Fixes

### FT-001: Reuse CLI save-path and safe-write helpers
- **Severity**: HIGH
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/report.py`
- **Issue**: The command resolves and writes the output file directly, bypassing `validate_save_path()` and `safe_write_file()` from `fs2.cli.utils`.
- **Fix**: Import `validate_save_path` and `safe_write_file`, validate both custom and default output destinations, and write the generated HTML through the shared helper instead of direct `mkdir()` / `write_text()`.
- **Patch hint**:
  ```diff
  - from fs2.cli.utils import (
  -     resolve_graph_from_context,
  - )
  + from fs2.cli.utils import (
  +     resolve_graph_from_context,
  +     safe_write_file,
  +     validate_save_path,
  + )
  ...
  -         if output:
  -             output_path = Path(output).resolve()
  +         if output:
  +             output_path = validate_save_path(Path(output), stderr_console)
            else:
  ...
  -             output_path = (output_dir / "codebase-graph.html").resolve()
  +             output_path = validate_save_path(
  +                 output_dir / "codebase-graph.html",
  +                 stderr_console,
  +             )
  ...
  -         output_path.parent.mkdir(parents=True, exist_ok=True)
  -         output_path.write_text(result.html, encoding="utf-8")
  +         safe_write_file(output_path, result.html, stderr_console)
  ```

## Medium / Low Fixes

### FT-002: Add the missing CLI smoke test file
- **Severity**: MEDIUM
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_report_cli.py`
- **Issue**: T007 promised CLI smoke tests, but the file is missing, so the phase depends on reviewer manual checks.
- **Fix**: Add `CliRunner` tests that cover `fs2 report --help`, `fs2 report codebase-graph --help`, successful generation, `--graph-file`, missing graph exit `1`, `--output`, `--no-smart-content`, and `--open` fallback behavior.
- **Patch hint**:
  ```diff
  + from typer.testing import CliRunner
  + from fs2.cli.main import app
  +
  + runner = CliRunner()
  +
  + def test_report_help():
  +     result = runner.invoke(app, ["report", "--help"])
  +     assert result.exit_code == 0
  +     assert "codebase-graph" in result.stdout
  +
  + def test_missing_graph_exits_1():
  +     result = runner.invoke(
  +         app,
  +         ["--graph-file", "/tmp/missing.pickle", "report", "codebase-graph"],
  +     )
  +     assert result.exit_code == 1
  +     assert "Graph file not found" in result.stdout or result.stderr
  ```

### FT-003: Restore a clean Ruff pass
- **Severity**: MEDIUM
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_report_service.py`
- **Issue**: Ruff currently fails on an unused `json` import.
- **Fix**: Remove the unused import and re-run the scoped Ruff command used in review.
- **Patch hint**:
  ```diff
  - import json
  -
    import pytest
  ```

### FT-004: Record implementation evidence in the execution log
- **Severity**: MEDIUM
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/033-reports/tasks/phase-1-foundation/execution.log.md`
- **Issue**: The execution log is still empty, so the phase lacks Full Mode evidence for what was completed and how it was verified.
- **Fix**: Append task entries describing completed work, the files touched, and the concrete commands/results used to validate the implementation.
- **Patch hint**:
  ```diff
    ## Task Log
  
  - _Entries appended per task completion._
  + - 2026-03-15 — T001/T003/T005: Added `ReportsConfig`, `ReportService`, and `report` CLI command.
  +   Evidence: `uv run python -m pytest -q tests/unit/config/test_reports_config.py tests/unit/services/test_report_service.py`
  + - 2026-03-15 — T002/T004/T006: Added template/static package scaffolds and CLI registration.
  +   Evidence: `uv run fs2 report --help` and `uv run fs2 --graph-file .fs2/graph.pickle report codebase-graph`
  ```

## Re-Review Checklist

- [ ] All critical/high fixes applied
- [ ] Re-run `/plan-7-v2-code-review` and achieve zero HIGH/CRITICAL
