# Save Output to File Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-01-02
**Spec**: [save-to-file-spec.md](/workspaces/flow_squared/docs/plans/012-save-to-file/save-to-file-spec.md)
**Status**: READY

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Critical Research Findings](#critical-research-findings)
3. [Implementation](#implementation)
4. [Commands to Run](#commands-to-run)
5. [Known Limitations](#known-limitations)
6. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

**Problem**: AI agents and scripts using fs2 need to save complex search results for post-processing with tools like `jq`. Currently only `get-node` supports file output via `--file` (CLI) and `save_to_file` (MCP). The `search` and `tree` commands lack this capability.

**Solution**: Add `--file` option to CLI `search` and `tree` commands, add `save_to_file` parameter to MCP `search()` and `tree()` tools. Follow established patterns from `get_node` implementation. Add `--json` flag to CLI tree for JSON output mode. Ensure security parity with path validation for all file output operations.

**Expected Outcome**: Users can save search results as JSON and tree output as JSON or Rich text to files, enabling query-once-process-many workflows essential for agent automation.

---

## Critical Research Findings (Concise)

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | CLI `--file` has NO path validation (security gap) | Add `_validate_cli_save_path()` wrapper using same logic as MCP's `_validate_save_path()` |
| 02 | Critical | Pattern exists in `get_node` for both CLI and MCP | Copy patterns from `get_node.py:102-107` (CLI) and `server.py:394-407` (MCP) |
| 03 | High | Tree CLI outputs Rich text, not JSON | Add `--json` flag to enable JSON output mode before/alongside `--file` |
| 04 | High | MCP tree return type changes when saving | Wrap in `{"tree": [...], "saved_to": "..."}` only when `save_to_file` is used |
| 05 | High | MCP annotations say `readOnlyHint=True` for tree/search | Change to `readOnlyHint=False` since file-writing tools must not lie about side effects |
| 06 | High | stdout/stderr discipline required | Use `print()` for JSON stdout, `Console(stderr=True)` for confirmation messages |
| 07 | Medium | `_tree_node_to_dict()` exists in MCP server | Move to `fs2.core.serialization` for CLI and MCP to share (avoid layer violation) |
| 08 | Medium | Subdirectory auto-creation required (AC10) | Use `Path.parent.mkdir(parents=True, exist_ok=True)` before file write |
| 09 | Medium | Empty results must still save file (AC9) | Write envelope even when `results: []` - file existence indicates command ran |
| 10 | Low | Serialization pattern: avoid `asdict()` | Use explicit `to_dict(detail)` methods to prevent embedding leakage |

**Prior Learnings Applied**:
- PL-01: Use `print()` not `console.print()` for JSON output
- PL-02: Never use `asdict()` on CodeNode (leaks embeddings)
- PL-08: Path validation required - reuse `_validate_save_path()` pattern
- PL-13: `readOnlyHint=False` for file writers

---

## Implementation (Single Phase)

**Objective**: Add file output capability to CLI `search` and `tree` commands, and MCP `search()` and `tree()` tools.

**Testing Approach**: Full TDD (per spec)
**Mock Usage**: Targeted mocks - use FakeGraphStore, FakeConfigurationService; real file I/O with `tmp_path`

### Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|------------------|------------|-------|
| [ ] | T001 | Write tests for CLI search `--file` option | 2 | Test | -- | `/workspaces/flow_squared/tests/unit/cli/test_search_cli.py` | Tests cover: file creation, valid JSON envelope, empty stdout, stderr confirmation, path validation rejection, empty results save, subdirectory creation | Create `TestSearchFileOutput` class |
| [ ] | T002 | Create shared CLI path validation utility | 1 | Core | T001 | `/workspaces/flow_squared/src/fs2/cli/utils.py` | Create `validate_save_path(file: Path) -> Path` + `safe_write_file(path, content)` with cleanup on error | New shared module; Insight #2: cleanup partial files |
| [ ] | T003 | Add `--file` option to CLI search command | 2 | Core | T002 | `/workspaces/flow_squared/src/fs2/cli/search.py` | Tests from T001 pass: file write works, stdout empty, confirmation on stderr, path validated, subdirs created | Add to function signature + output logic |
| [ ] | T004 | Write tests for MCP search `save_to_file` | 2 | Test | -- | `/workspaces/flow_squared/tests/mcp_tests/test_search_tool.py` | Tests cover: `saved_to` field in response, file creation, valid JSON, path validation ToolError, subdirectory creation | Create `TestSearchSaveToFile` class |
| [ ] | T005 | Add `save_to_file` parameter to MCP search | 2 | Core | T004 | `/workspaces/flow_squared/src/fs2/mcp/server.py` | Tests from T004 pass: envelope enriched with `saved_to`, file written, path validated | Add param + logic after line 650 |
| [ ] | T006 | Update MCP search annotation to readOnlyHint=False | 1 | Core | T005 | `/workspaces/flow_squared/src/fs2/mcp/server.py` | Annotation at line ~701 has `readOnlyHint: False` | AC8 compliance |
| [ ] | T007 | Write tests for CLI tree `--json` flag | 2 | Test | -- | `/workspaces/flow_squared/tests/unit/cli/test_tree_cli.py` | Tests cover: `--json` outputs valid JSON to stdout, parseable by json.loads, has expected structure | Create `TestTreeJsonOutput` class |
| [ ] | T008 | Write tests for CLI tree `--file` options | 2 | Test | T007 | `/workspaces/flow_squared/tests/unit/cli/test_tree_cli.py` | Tests cover: `--file` saves plain text (ANSI stripped), `--json --file` saves JSON, path validation, subdirectory creation | Add to or extend test class; Insight #1: strip ANSI for readability |
| [ ] | T009 | Add `--json` and `--file` options to CLI tree | 3 | Core | T007, T008 | `/workspaces/flow_squared/src/fs2/cli/tree.py` | Tests from T007/T008 pass: JSON mode works, file save uses `Console(no_color=True)` | Add flags + branch logic; Insight #1: strip ANSI for file output |
| [ ] | T010 | Move `_tree_node_to_dict` to shared location | 2 | Core | T009 | `/workspaces/flow_squared/src/fs2/core/serialization.py`, `/workspaces/flow_squared/src/fs2/mcp/server.py`, `/workspaces/flow_squared/src/fs2/cli/tree.py` | Function moved to core/serialization.py; MCP server imports from there; CLI tree imports from there | Avoids CLI→MCP layer violation |
| [ ] | T011 | Import shared path validation in tree.py | 1 | Core | T002, T009 | `/workspaces/flow_squared/src/fs2/cli/tree.py` | Path escape attempts exit with code 1; uses `validate_save_path` from `fs2.cli.utils` | Import from shared utils created in T002 |
| [ ] | T012 | Write tests for MCP tree `save_to_file` | 2 | Test | -- | `/workspaces/flow_squared/tests/mcp_tests/test_tree_tool.py` | Tests cover: ALWAYS return `{"tree": [...]}` wrapper, `saved_to` only when saving | Insight #5: consistent like search |
| [ ] | T013 | Add `save_to_file` parameter to MCP tree | 2 | Core | T012 | `/workspaces/flow_squared/src/fs2/mcp/server.py` | Always return `{"tree": [...]}`, add `saved_to` when saving; UTF-8 encoding | Insight #5: consistent return type |
| [ ] | T014 | Update MCP tree annotation to readOnlyHint=False | 1 | Core | T013 | `/workspaces/flow_squared/src/fs2/mcp/server.py` | Annotation at line ~261 has `readOnlyHint: False` | AC8 compliance |
| [ ] | T015 | Update MCP tool descriptions for save_to_file | 1 | Docs | T005, T013 | `/workspaces/flow_squared/src/fs2/mcp/server.py` | Tool docstrings mention `save_to_file` param, tree suggests JSON for programmatic use | Update docstrings in search() and tree() |
| [ ] | T016 | Update README.md with `--file` examples | 1 | Docs | T003, T009 | `/workspaces/flow_squared/README.md` | README CLI section shows `--file` usage examples | Add 1-2 examples per command |
| [ ] | T017 | Update MCP server guide with save_to_file | 1 | Docs | T015 | `/workspaces/flow_squared/docs/how/mcp-server-guide.md` | Guide documents `save_to_file` parameter for all tools | Add parameter documentation |

### Test Examples (TDD - Write First)

**CLI Search File Output Tests** (`tests/unit/cli/test_search_cli.py`):

```python
class TestSearchFileOutput:
    """Tests for fs2 search --file option (AC1, AC2, AC4b, AC9, AC10)."""

    def test_given_file_flag_when_search_then_writes_to_file(
        self, scanned_project, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves --file option writes JSON envelope to specified file
        Quality Contribution: Validates core file output functionality
        Acceptance Criteria:
        - File is created with valid JSON
        - JSON contains 'meta' and 'results' keys
        - stdout is empty (AC1)
        """
        monkeypatch.chdir(tmp_path)
        output_file = tmp_path / "results.json"
        result = runner.invoke(app, ["search", "test", "--file", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()
        assert result.stdout == ""  # AC1: stdout empty

        data = json.loads(output_file.read_text())
        assert "meta" in data
        assert "results" in data

    def test_given_file_flag_when_search_then_shows_confirmation_on_stderr(
        self, scanned_project, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves confirmation message goes to stderr
        Quality Contribution: Ensures piping works correctly
        Acceptance Criteria: stderr contains confirmation (AC2)
        """
        monkeypatch.chdir(tmp_path)
        output_file = tmp_path / "results.json"
        result = runner.invoke(app, ["search", "test", "--file", str(output_file)])

        assert "✓" in result.stderr or "Wrote" in result.stderr  # AC2

    def test_given_path_escape_when_search_file_then_exits_with_error(
        self, scanned_project, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves path validation prevents directory traversal
        Quality Contribution: Security - prevents writes outside cwd
        Acceptance Criteria: Exit code 1 for path escape (AC4b)
        """
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["search", "test", "--file", "../escape.json"])

        assert result.exit_code == 1
        assert "escape" in result.stderr.lower() or "directory" in result.stderr.lower()

    def test_given_empty_results_when_file_flag_then_still_saves_envelope(
        self, scanned_project, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves empty results still create valid file
        Quality Contribution: Consistent behavior for agent workflows
        Acceptance Criteria: Empty envelope saved (AC9)
        """
        monkeypatch.chdir(tmp_path)
        output_file = tmp_path / "results.json"
        result = runner.invoke(app, ["search", "NONEXISTENT_PATTERN_XYZ", "--file", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["results"] == []

    def test_given_nested_path_when_file_flag_then_creates_subdirectory(
        self, scanned_project, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves subdirectories are auto-created
        Quality Contribution: Convenience for nested output paths
        Acceptance Criteria: Subdirectory created (AC10)
        """
        monkeypatch.chdir(tmp_path)
        output_file = tmp_path / "subdir" / "nested" / "results.json"
        result = runner.invoke(app, ["search", "test", "--file", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()
```

**MCP Search save_to_file Tests** (`tests/mcp_tests/test_search_tool.py`):

```python
class TestSearchSaveToFile:
    """Tests for MCP search save_to_file parameter (AC3, AC4)."""

    def test_search_save_returns_saved_to_field(
        self, search_test_graph_store, tmp_path
    ):
        """
        Purpose: Proves save_to_file adds saved_to to response
        Quality Contribution: Enables agent confirmation of file save
        Acceptance Criteria: Response contains saved_to with absolute path (AC3)
        """
        store, config = search_test_graph_store
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = asyncio.run(search(
                pattern="test",
                save_to_file="results.json"
            ))

            assert "saved_to" in result
            assert result["saved_to"] == str(tmp_path / "results.json")
            assert Path(result["saved_to"]).exists()
        finally:
            os.chdir(original_cwd)

    def test_search_save_rejects_path_escape(
        self, search_test_graph_store, tmp_path
    ):
        """
        Purpose: Proves path validation prevents directory traversal
        Quality Contribution: Security - prevents writes outside cwd
        Acceptance Criteria: ToolError raised for path escape (AC4)
        """
        store, config = search_test_graph_store
        dependencies.set_config(config)
        dependencies.set_graph_store(store)

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(ToolError) as exc_info:
                asyncio.run(search(
                    pattern="test",
                    save_to_file="../escape.json"
                ))
            assert "escapes" in str(exc_info.value).lower()
        finally:
            os.chdir(original_cwd)
```

### Non-Happy-Path Coverage

- [ ] Path escape with `../` rejected (CLI and MCP)
- [ ] Absolute path outside cwd rejected
- [ ] Complex traversal `./a/../../../escape.json` rejected
- [ ] Empty results still save valid envelope/JSON
- [ ] Permission denied on directory creation (graceful error)
- [ ] Search/tree errors do not create partial files

### Acceptance Criteria

- [ ] AC1: CLI `fs2 search "pattern" --file results.json` writes envelope, stdout empty
- [ ] AC2: CLI search with `--file` shows confirmation on stderr
- [ ] AC3: MCP `search(save_to_file="results.json")` returns `saved_to` field
- [ ] AC4: MCP path escape raises ToolError
- [ ] AC4b: CLI path escape exits with code 1
- [ ] AC5: CLI `fs2 tree --json` outputs JSON to stdout
- [ ] AC6: CLI `fs2 tree --file tree.txt` saves Rich text
- [ ] AC6b: CLI `fs2 tree --json --file tree.json` saves JSON
- [ ] AC7: MCP `tree(save_to_file="tree.json")` returns wrapped dict with `saved_to`
- [ ] AC8: MCP tree and search have `readOnlyHint=False` annotation
- [ ] AC9: Empty results still save file
- [ ] AC10: Subdirectories auto-created

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CLI path validation inconsistent with MCP | Low | High | Use identical logic in `_validate_cli_save_path()`, test both |
| Tree `--json` flag confuses users | Low | Medium | Clear help text, document in README |
| MCP tree return type change breaks agents | Medium | Medium | Only change when `save_to_file` used, document in tool description |
| Annotation change (`readOnlyHint`) overlooked | Low | High | Dedicated task (T006, T014), test annotation values |

---

## Commands to Run

### Test Commands

```bash
# Run tests for specific features (as implemented)
pytest tests/unit/cli/test_search_cli.py::TestSearchFileOutput -v
pytest tests/unit/cli/test_tree_cli.py::TestTreeJsonOutput -v
pytest tests/unit/cli/test_tree_cli.py::TestTreeFileOutput -v
pytest tests/mcp_tests/test_search_tool.py::TestSearchSaveToFile -v
pytest tests/mcp_tests/test_tree_tool.py::TestTreeSaveToFile -v

# Full test suite
pytest tests/ -v

# Quick validation (after all tasks complete)
pytest tests/unit/cli/test_search_cli.py tests/unit/cli/test_tree_cli.py tests/mcp_tests/test_search_tool.py tests/mcp_tests/test_tree_tool.py -v
```

### Lint/Format Commands

```bash
# Lint modified files
ruff check src/fs2/cli/search.py src/fs2/cli/tree.py src/fs2/cli/utils.py src/fs2/mcp/server.py src/fs2/core/serialization.py

# Format check
ruff format --check src/fs2/

# Type check (if applicable)
mypy src/fs2/cli/search.py src/fs2/cli/tree.py src/fs2/mcp/server.py --ignore-missing-imports
```

### Manual Validation Commands

```bash
# CLI search file output
fs2 search "test" --file /tmp/results.json && cat /tmp/results.json | jq '.meta'

# CLI tree JSON output
fs2 tree --json | jq '.[0].node_id'

# CLI tree file output
fs2 tree --json --file /tmp/tree.json && cat /tmp/tree.json | jq 'length'

# Path escape rejection (should fail with exit 1)
fs2 search "test" --file ../escape.json; echo "Exit code: $?"
```

---

## Known Limitations

### Existing `get_node` CLI Has No Path Validation (Out of Scope)

**Finding**: Research identified that the existing `fs2 get-node --file` CLI command (implemented before this plan) does not validate the output path. It uses `Path` type directly from Typer without security checks.

**Location**: `/workspaces/flow_squared/src/fs2/cli/get_node.py:39-42`

**Risk**: User could potentially write to arbitrary paths like `--file /etc/cron.d/evil`.

**Decision**: This is a **pre-existing issue outside the scope of this plan**. The scope is specifically "add save-to-file to search and tree commands" per the spec. Fixing `get_node` would be scope creep.

**Mitigation**:
1. The new `search` and `tree` CLI commands WILL have proper path validation via T002 (shared utility)
2. A separate issue/plan should be created to backport path validation to `get_node` CLI
3. CLI runs with user's own permissions, so impact is limited to user's own filesystem

**Future Work**: Create follow-up task to add path validation to existing `get_node` CLI for consistency.

---

## Change Footnotes Ledger

[^1]: [To be added during implementation via plan-6a]
[^2]: [To be added during implementation via plan-6a]
[^3]: [To be added during implementation via plan-6a]
[^4]: [To be added during implementation via plan-6a]

---

**Next steps:**
- **Ready to implement**: `/plan-6-implement-phase --plan "docs/plans/012-save-to-file/save-to-file-plan.md"`
- **Optional task expansion**: `/plan-5-phase-tasks-and-brief` (if you want a separate dossier with alignment brief)
