# Get Node Command Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2025-12-17
**Spec**: [./get-node-command-spec.md](./get-node-command-spec.md)
**Research**: [./research-dossier.md](./research-dossier.md)
**Execution Log**: [./execution.log.md](./execution.log.md)
**Status**: COMPLETE

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Research Findings](#critical-research-findings)
3. [Implementation](#implementation)
4. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

**Problem**: Users need programmatic access to individual code nodes for scripting, CI/CD pipelines, and integration with JSON-processing tools like `jq`. Currently, no command exists to retrieve a single node by ID.

**Solution**: Add `fs2 get-node <node_id> [--file PATH]` command that:
- Retrieves a single CodeNode by ID from the graph store
- Outputs complete node data as JSON to stdout (clean for piping)
- Optionally writes to file via `--file` flag
- Routes all errors to stderr with consistent exit codes

**Expected Outcome**: Users can run `fs2 get-node "callable:src/main.py:main" | jq '.signature'` with zero non-data output.

---

## Critical Research Findings

Research synthesized from 60 findings in research-dossier.md plus 20 implementation-focused discoveries.

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | **Stdout discipline**: Use raw `print()` not `console.print()` for JSON | Create `Console(stderr=True)` for errors only |
| 02 | Critical | **Command registration**: Follow `app.command(name="get-node")(get_node)` pattern | Import and register in main.py after tree |
| 03 | Critical | **Typer annotations**: Use `Annotated[str, typer.Argument()]` for positional, `Annotated[Path \| None, typer.Option()]` for --file | Match tree.py signature patterns exactly |
| 04 | High | **JSON serialization**: Use `dataclasses.asdict(node)` + `json.dumps(indent=2, default=str)` | NOT Pydantic model_dump_json() |
| 05 | High | **Exit codes**: 0=success, 1=user error (missing graph/config/node), 2=system error (corruption) | Match tree.py exactly |
| 06 | High | **Exception handling**: Catch `MissingConfigurationError` (exit 1) and `GraphStoreError` (exit 2) at CLI boundary | Same imports as tree.py |
| 07 | High | **Config loading**: Reuse `TreeConfig.graph_path` via `FS2ConfigurationService().require(TreeConfig)` | No new config classes needed |
| 08 | High | **GraphStore lookup**: `store.get_node(node_id)` returns `CodeNode | None` with O(1) dict lookup | Check for None explicitly |
| 09 | High | **TDD test structure**: Create `tests/unit/cli/test_get_node_cli.py` with CliRunner pattern | Group tests by purpose: Help, Success, Errors, Piping |
| 10 | High | **Test fixtures**: Use `scanned_fixtures_graph` session fixture for integration tests | Use `monkeypatch.chdir()` and `NO_COLOR=1` |
| 11 | High | **CodeNode fields**: 22 fields including nullable ones (name, signature, embedding) | All serialize to JSON with None→null |
| 12 | Medium | **File output**: Write JSON via `file.write_text(json_str)`, success message to stderr | Keeps stdout clean when using --file |
| 13 | Medium | **Help text**: Docstring becomes --help output; include examples | Match tree.py docstring format |
| 14 | Medium | **Node not found**: Treat as user error (exit 1), show "Node not found: {node_id}" to stderr | Consistent with missing graph error |

---

## Implementation (Single Phase)

**Objective**: Implement `fs2 get-node` command with full TDD coverage for all 9 acceptance criteria.

**Testing Approach**: Full TDD (from spec)
**Mock Usage**: Avoid mocks entirely - use real fixtures only (from spec)
**Documentation**: No new docs - command is self-documenting via --help (from spec)

### Tasks {#tasks-full-tdd-approach}

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|------------------|------------|-------|
| [x] | T000 | Create shared CLI test fixtures in conftest.py | 2 | Setup | -- | `/workspaces/flow_squared/tests/conftest.py` | `scanned_project`, `config_only_project`, `corrupted_graph_project`, `project_without_config` fixtures available globally | Migrate from test_tree_cli.py and test_scan_cli.py; verify existing tests pass |
| [x] | T001 | Write test: command registered and --help works (AC8) | 1 | Test | T000 | `/workspaces/flow_squared/tests/unit/cli/test_get_node_cli.py` | `fs2 get-node --help` shows usage, exit 0 | TestGetNodeHelp class |
| [x] | T002 | Write test: valid node_id returns JSON, exit 0 (AC1, AC9) | 2 | Test | T001 | `/workspaces/flow_squared/tests/unit/cli/test_get_node_cli.py` | JSON contains essential fields (node_id, category, content, start_line, language), exit 0 | TestGetNodeSuccess class |
| [x] | T003 | Write test: stdout is clean JSON only (AC2) | 2 | Test | T001 | `/workspaces/flow_squared/tests/unit/cli/test_get_node_cli.py` | `json.loads(stdout)` succeeds with no extra output | TestGetNodePiping class |
| [x] | T004 | Write test: pipe to jq works (AC3) | 1 | Test | T003 | `/workspaces/flow_squared/tests/unit/cli/test_get_node_cli.py` | Validate JSON structure matches jq expectations | TestGetNodePiping class |
| [x] | T005 | Write test: --file flag writes JSON to file (AC4) | 2 | Test | T001 | `/workspaces/flow_squared/tests/unit/cli/test_get_node_cli.py` | File contains valid JSON, success msg on stderr, exit 0 | TestGetNodeFileOutput class |
| [x] | T006 | Write test: node not found returns exit 1 (AC5) | 1 | Test | T001 | `/workspaces/flow_squared/tests/unit/cli/test_get_node_cli.py` | Error on stderr, exit 1 | TestGetNodeErrors class |
| [x] | T007 | Write test: missing graph returns exit 1 (AC6) | 1 | Test | T001 | `/workspaces/flow_squared/tests/unit/cli/test_get_node_cli.py` | Error mentions "fs2 scan", exit 1 | TestGetNodeErrors class |
| [x] | T008 | Write test: corrupted graph returns exit 2 (AC7) | 1 | Test | T001 | `/workspaces/flow_squared/tests/unit/cli/test_get_node_cli.py` | Error indicates corruption, exit 2 | TestGetNodeErrors class |
| [x] | T008a | Write test: missing config returns exit 1, mentions "init" | 1 | Test | T001 | `/workspaces/flow_squared/tests/unit/cli/test_get_node_cli.py` | Error mentions "init", exit 1 | TestGetNodeErrors class; use project_without_config fixture |
| [x] | T009 | Create get_node.py with command function skeleton | 2 | Core | T001-T008a | `/workspaces/flow_squared/src/fs2/cli/get_node.py` | File exists, imports compile | Implement to make T001 pass |
| [x] | T010 | Register command in main.py | 1 | Core | T009 | `/workspaces/flow_squared/src/fs2/cli/main.py` | `app.command(name="get-node")(get_node)` added | T001 (help) should pass |
| [x] | T011 | Implement config loading and graph path check | 2 | Core | T010 | `/workspaces/flow_squared/src/fs2/cli/get_node.py` | T007 (missing graph) passes | TreeConfig reuse |
| [x] | T012 | Implement GraphStore.get_node() call and None check | 2 | Core | T011 | `/workspaces/flow_squared/src/fs2/cli/get_node.py` | T006 (node not found) passes | Returns CodeNode or None |
| [x] | T013 | Implement JSON serialization via asdict + json.dumps | 2 | Core | T012 | `/workspaces/flow_squared/src/fs2/cli/get_node.py` | T002, T003 (JSON output) pass | Use `default=str` |
| [x] | T014 | Implement --file flag with Path.write_text() | 1 | Core | T013 | `/workspaces/flow_squared/src/fs2/cli/get_node.py` | T005 (file output) passes | Success msg to stderr |
| [x] | T015 | Implement exception handling (MissingConfigurationError, GraphStoreError) | 2 | Core | T011 | `/workspaces/flow_squared/src/fs2/cli/get_node.py` | T007, T008 (errors) pass | Exit codes 1, 2 |
| [x] | T016 | Write integration test using scanned_fixtures_graph | 2 | Test | T013 | `/workspaces/flow_squared/tests/integration/test_get_node_cli_integration.py` | Real graph, real node lookup | Optional: validates end-to-end |
| [x] | T017 | Run full test suite and lint | 1 | Verify | T001-T016 | -- | All tests pass, ruff check clean | `pytest tests/ -v && ruff check` |

### Test Examples (Write First!)

```python
# tests/unit/cli/test_get_node_cli.py

import json
import pytest
from typer.testing import CliRunner

from fs2.cli.main import app

runner = CliRunner()


class TestGetNodeHelp:
    """AC8: Help text verification."""

    def test_given_help_flag_when_get_node_then_shows_usage(self):
        """
        Purpose: Proves command is registered and help is accessible
        Quality Contribution: Ensures discoverability
        Acceptance Criteria: Exit 0, shows node_id and --file in output
        """
        result = runner.invoke(app, ["get-node", "--help"])

        assert result.exit_code == 0
        assert "node_id" in result.stdout.lower() or "node-id" in result.stdout.lower()
        assert "--file" in result.stdout


class TestGetNodeSuccess:
    """AC1, AC9: Successful node retrieval."""

    def test_given_valid_node_id_when_get_node_then_outputs_json(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves core retrieval returns valid JSON with all fields
        Quality Contribution: Validates primary use case
        Acceptance Criteria: Exit 0, JSON contains all 22 CodeNode fields
        """
        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        # Use a known node_id from the scanned project
        result = runner.invoke(app, ["get-node", "file:src/main.py"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        # Check essential fields (resilient to CodeNode changes)
        assert "node_id" in data
        assert "category" in data
        assert "content" in data
        assert "start_line" in data
        assert "language" in data


class TestGetNodePiping:
    """AC2, AC3: Clean output for piping."""

    def test_given_stdout_when_get_node_then_valid_json_only(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves stdout contains ONLY JSON (no logs, no Rich markup)
        Quality Contribution: Enables piping to jq without parsing errors
        Acceptance Criteria: json.loads() succeeds on entire stdout
        """
        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["get-node", "file:src/main.py"])

        assert result.exit_code == 0
        # This MUST succeed - any extra output breaks piping
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"stdout is not valid JSON: {e}\nOutput was: {result.stdout}")

        assert isinstance(data, dict)


class TestGetNodeErrors:
    """AC5, AC6, AC7: Error handling."""

    def test_given_unknown_node_when_get_node_then_exit_one(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves missing node returns user error
        Quality Contribution: Prevents silent failures
        Acceptance Criteria: Exit 1, error message on stderr
        """
        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["get-node", "nonexistent:node:path"])

        assert result.exit_code == 1
        # Error should mention the node wasn't found
        assert "not found" in result.stdout.lower() or "error" in result.stdout.lower()

    def test_given_missing_graph_when_get_node_then_exit_one(
        self, config_only_project, monkeypatch
    ):
        """
        Purpose: Proves missing graph returns user error with guidance
        Quality Contribution: Guides user to run fs2 scan first
        Acceptance Criteria: Exit 1, mentions "scan"
        """
        monkeypatch.chdir(config_only_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["get-node", "file:src/main.py"])

        assert result.exit_code == 1
        assert "scan" in result.stdout.lower()

    def test_given_corrupted_graph_when_get_node_then_exit_two(
        self, corrupted_graph_project, monkeypatch
    ):
        """
        Purpose: Proves corrupted graph returns system error
        Quality Contribution: Distinguishes user vs system errors
        Acceptance Criteria: Exit 2
        """
        monkeypatch.chdir(corrupted_graph_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["get-node", "file:src/main.py"])

        assert result.exit_code == 2

    def test_given_missing_config_when_get_node_then_exit_one(
        self, project_without_config, monkeypatch
    ):
        """
        Purpose: Proves missing config returns user error with guidance
        Quality Contribution: Guides user to run fs2 init first
        Acceptance Criteria: Exit 1, mentions "init"
        """
        monkeypatch.chdir(project_without_config)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["get-node", "file:src/main.py"])

        assert result.exit_code == 1
        assert "init" in result.stdout.lower()
```

### Non-Happy-Path Coverage

- [x] T006: Node ID not found in graph
- [x] T007: Graph file doesn't exist
- [x] T008: Graph file is corrupted/unpicklable
- [x] T008a: Missing config file (MissingConfigurationError → "run init")
- [ ] Invalid node_id format (treated as "not found" - no special handling needed)

### Acceptance Criteria

- [x] AC1: Basic node retrieval returns JSON, exit 0
- [x] AC2: Clean stdout (JSON only, no extra output)
- [x] AC3: Pipeable to jq
- [x] AC4: --file flag writes to file, success on stderr
- [x] AC5: Node not found → exit 1
- [x] AC6: Missing graph → exit 1 with "scan" guidance
- [x] AC7: Corrupted graph → exit 2
- [x] AC8: --help shows usage
- [x] AC9: Essential CodeNode fields in output (per Insight #2)

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Stdout pollution from console.print() | Low | High | Use raw `print()` for JSON; `Console(stderr=True)` for errors |
| None value serialization | Low | Medium | Use `json.dumps(default=str)` for safe serialization |
| Test fixture isolation | Low | Medium | Use function-scoped fixtures, monkeypatch cleanup |

---

## Change Footnotes Ledger

**NOTE**: This section will be populated during implementation by plan-6a-update-progress.

[^1]: [To be added during implementation via plan-6a]
[^2]: [To be added during implementation via plan-6a]

---

## Critical Insights Discussion

**Session**: 2025-12-17
**Context**: get-node-command Implementation Plan v1.0.0
**Analyst**: AI Clarity Agent
**Reviewer**: Development Team
**Format**: Water Cooler Conversation (5 Critical Insights)

### Insight 1: Test Fixture Naming Mismatch

**Did you know**: Test examples referenced `scanned_project`, `config_only_project`, `corrupted_graph_project` fixtures that exist only in test_tree_cli.py, not globally in conftest.py.

**Implications**:
- Tests would fail with "fixture not found" errors
- Each CLI test file was duplicating fixtures
- Maintenance burden and potential drift between copies

**Options Considered**:
- Option A: Duplicate Fixtures - Copy to test_get_node_cli.py
- Option B: Move to conftest.py - Consolidate shared fixtures
- Option C: Create New Minimal Fixtures - Tailored for get-node

**AI Recommendation**: Option A (Duplicate) for speed
- Reasoning: Lowest risk, fastest path, can refactor later

**Discussion Summary**: User preferred clean architecture over speed - consolidate fixtures properly in conftest.py to avoid duplication and enable future CLI commands.

**Decision**: Create shared fixtures in conftest.py, migrate from per-file fixtures

**Action Items**:
- [x] Add T000: Create shared CLI test fixtures in conftest.py

**Affects**: Task table (added T000), test file dependencies

---

### Insight 2: Fragile Field Count Assertion

**Did you know**: The test `assert len(data) == 22` would break when CodeNode adds/removes fields, even for unrelated changes.

**Implications**:
- Tests become maintenance burden
- Testing CodeNode structure rather than get-node behavior
- Any field change breaks unrelated tests

**Options Considered**:
- Option A: Check Key Fields Only - Assert 5 essential fields
- Option B: Schema Validation - Full JSON schema
- Option C: Dynamic Field Count - Use `len(dataclasses.fields(CodeNode))`

**AI Recommendation**: Option A (Key Fields Only)
- Reasoning: Tests behavior not structure, resilient to changes

**Discussion Summary**: User agreed - test essential fields only.

**Decision**: Check 5 essential fields (node_id, category, content, start_line, language) instead of hardcoded count

**Action Items**:
- [x] Update test example in plan
- [x] Update T002 validation criteria

**Affects**: Test examples, T002 validation

---

### Insight 3: CliRunner stdout/stderr Mixing

**Did you know**: CliRunner mixes stdout and stderr into `result.stdout` by default, which could affect how we validate clean output.

**Implications**:
- `result.stdout` contains both streams
- `json.loads()` implicitly validates clean output (extra text breaks parsing)
- Tests work correctly but mechanism isn't obvious

**Options Considered**:
- Option A: Accept Current Behavior - Rely on json.loads() validation
- Option B: Add Explicit stderr Test - Separate stream capture
- Option C: Document the Implicit Behavior - Add explanatory comments

**AI Recommendation**: Option A (Accept Current Behavior)
- Reasoning: Test already catches stdout pollution, matches existing patterns

**Discussion Summary**: User agreed to accept current behavior.

**Decision**: Keep tests as planned - json.loads() is sufficient validation

**Action Items**: None

**Affects**: No changes

---

### Insight 4: Node ID Discovery Problem

**Did you know**: Users need to know exact node_id format but have no easy way to discover valid IDs without running `fs2 tree --detail max`.

**Implications**:
- Poor discoverability for new users
- Users might try invalid formats and get "not found"

**Options Considered**:
- Option A: Document in --help - Add examples (current plan)
- Option B: Add Helpful Error Message - Suggest tree command on error
- Option C: Accept Partial Node IDs - Fuzzy matching (out of scope)

**AI Recommendation**: Option B (Add Helpful Error Message)
- Reasoning: Guides users at moment of confusion, one line of code

**Discussion Summary**: User indicated query modes are planned for future which will solve discoverability.

**Decision**: Skip - future query modes will address this

**Action Items**: None

**Affects**: No changes

---

### Insight 5: Missing Test for MissingConfigurationError

**Did you know**: The Non-Happy-Path Coverage showed "Missing config file" as uncovered, with no actual test task for the MissingConfigurationError path.

**Implications**:
- Error path not explicitly tested
- Full TDD requires testing every error scenario
- Users running in unconfigured directory should see "run init" message

**Options Considered**:
- Option A: Add Explicit Test Task - T008a for missing config
- Option B: Rely on tree.py Coverage - Assume shared code is tested
- Option C: Combine with T007 - One test for multiple scenarios

**AI Recommendation**: Option A (Add Explicit Test Task)
- Reasoning: Full TDD requires explicit tests, low cost, clear coverage

**Discussion Summary**: User agreed - always guide users to run `fs2 init` when config is missing.

**Decision**: Add T008a test for missing config → exit 1 with "init" guidance

**Action Items**:
- [x] Add T008a to task table
- [x] Add `project_without_config` to T000 fixtures
- [x] Add test example for T008a
- [x] Update Non-Happy-Path Coverage checklist

**Affects**: Task table, test examples, Non-Happy-Path Coverage

---

## Session Summary

**Insights Surfaced**: 5 critical insights identified and discussed
**Decisions Made**: 4 decisions reached (1 skipped for future work)
**Action Items Created**: 4 plan updates applied
**Updates Applied**: Task table expanded, test examples improved, coverage checklist updated

**Shared Understanding Achieved**: ✓

**Confidence Level**: High - Key risks identified and mitigated through plan updates

**Next Steps**: Proceed to implementation with `/plan-6-implement-phase`

---

**Next steps:**
- **Ready to implement**: `/plan-6-implement-phase --plan "docs/plans/005-get-node-command/get-node-command-plan.md"`
- **Optional validation**: `/plan-4-complete-the-plan` (recommended but optional for CS-2)
- **Optional task expansion**: `/plan-5-phase-tasks-and-brief` (if you want a separate dossier)
