# Agent Onboarding CLI Commands Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-02-14
**Spec**: [./agents-start-here-spec.md](./agents-start-here-spec.md)
**Status**: COMPLETE
**Workshops**:
- [agent-onboarding-experience.md](./workshops/agent-onboarding-experience.md) - CLI Flow

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Research Findings](#critical-research-findings)
3. [Implementation](#implementation)
4. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

AI agents cannot discover fs2 documentation without an already-working MCP connection --
a bootstrap paradox. Two new unguarded CLI commands (`fs2 agents-start-here` and `fs2 docs`)
break this paradox, giving agents a CLI bootstrap path to orient, configure, scan, and
connect MCP entirely from shell commands. MCP is the destination; CLI is the stepping stone.

---

## Critical Research Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | **MCP stdout contamination**: All CLI modules are imported at `main.py` top level. Any stdout during import breaks MCP JSON-RPC (PL-01). | Zero side effects at module level in new files. `Console()` construction is safe; all output inside command functions only. |
| 02 | Critical | **Unguarded registration required**: Both commands must work before `fs2 init`. Accidental `require_init` wrap = broken onboarding (AC-8). | Register in "not guarded" section of `main.py` (lines 109-114 pattern). Write explicit no-guard tests. |
| 03 | High | **Malformed YAML crashes state detector**: Empty/invalid config, or `llm: true` instead of dict, causes `AttributeError` on `.get()` calls. | Use `load_yaml_config()` (returns `{}` for broken YAML) + `isinstance(section, dict)` guard before `.get()`. |
| 04 | High | **DocsService must NOT come from MCP layer**: Importing from `fs2.mcp.server` pulls in FastMCP and risks stdout contamination. | Import `DocsService` directly from `fs2.core.services.docs_service`. Use `get_docs_service()` from dependencies. |
| 05 | High | **CliRunner captures stdout only**: `Console(stderr=True)` output is invisible to test runner. JSON via `print()` is captured. | Use `Console()` (stdout) for primary human output. Use `print()` for JSON. Use `Console(stderr=True)` only for errors. Test errors via exit codes. |
| 06 | High | **`docs` command must be single function, not sub-app**: Typer sub-apps don't support positional arguments as selectors. `fs2 docs <id>` needs optional `Argument`, not subcommand. | Use simple `app.command(name="docs")(docs)` with `doc_id: str | None = None` as optional `typer.Argument`. |
| 07 | Medium | **Graph path may be overridden in config**: Default `.fs2/graph.pickle` but users can set `graph.graph_path`. State detection must respect this. | Read `graph.graph_path` from YAML with `.fs2/graph.pickle` fallback. Lightweight -- no full `ConfigurationService` needed. |
| 08 | Medium | **YAML date coercion (PL-08)**: Unquoted `azure_api_version: 2024-12-01` becomes `datetime.date`. State detector must not do string ops on raw values. | Use truthiness checks only (`bool(section.get("provider"))`). Coerce with `str()` before display. |
| 09 | Medium | **No `ctx: typer.Context` needed**: Commands that don't use graph access shouldn't accept context. Follows `init` command pattern, avoids coupling. | Omit `ctx` parameter. Use only `typer.Argument` and `typer.Option` parameters. |
| 10 | Medium | **Test fixtures already handle DI cleanup**: Autouse `reset_dependencies_after_test` in root `conftest.py` calls `dependencies.reset_services()`. | No manual cleanup needed in tests. But must inject per-test since singleton resets between tests. |
| 11 | Medium | **DocsService API**: `list_documents(category, tags)` returns `list[DocMetadata]` (empty if no matches). `get_document(id)` returns `Doc | None`. Tags use OR logic. | Match this API in CLI: list returns grouped output, get returns content or exits 1. JSON mirrors MCP format. |
| 12 | Low | **Doc ID validation**: Registry `id` field has pattern `^[a-z0-9-]+$`. Invalid IDs simply return `None` from `get_document()`. | No input validation needed -- just check for `None` return and show helpful error with available IDs. |
| 13 | Low | **8 existing bundled docs across 2 categories**: how-to (5), reference (3). No "getting-started" category yet -- `agents.md` has `getting-started` tag. | Group display: show `getting-started`-tagged docs first, then how-to, then reference. Per workshop design. |

---

## Implementation

**Objective**: Implement `fs2 docs` and `fs2 agents-start-here` CLI commands using TDD,
providing agents a complete CLI bootstrap path from zero to MCP-connected.

**Testing Approach**: Full TDD (tests first, then implementation)
**Mock Usage**: Avoid mocks -- use real `DocsService` with real bundled docs, `tmp_path` +
`monkeypatch` for filesystem isolation

### Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|-------------------|------------|-------|
| [x] | T001 | Write tests for `fs2 docs` command (list mode, read mode, JSON mode, filters, error handling) | CS-2 | Test | -- | `/Users/jak/github/fs2-az-login/tests/unit/cli/test_docs_cmd.py` | Tests cover AC-3 through AC-9; all tests fail (RED) because command doesn't exist yet | Per workshop: list grouped by category, read renders content, JSON mirrors MCP format |
| [x] | T002 | Implement `docs` command + register in main.py | CS-2 | Core | T001 | `/Users/jak/github/fs2-az-login/src/fs2/cli/docs_cmd.py`, `/Users/jak/github/fs2-az-login/src/fs2/cli/main.py` | All T001 tests pass (GREEN); `fs2 docs` lists docs, `fs2 docs agents` shows content, `fs2 docs --json` outputs valid JSON | Uses `DocsService` via `get_docs_service()`. Console(stdout) for Rich output, print() for JSON. Unguarded registration. |
| [x] | T003 | Write tests for `fs2 agents-start-here` command (5 project states, output sections, unguarded access) | CS-2 | Test | -- | `/Users/jak/github/fs2-az-login/tests/unit/cli/test_agents_start_here.py` | Tests cover AC-1, AC-2, AC-8, AC-10; all fail (RED) | Each state needs its own test fixture: tmp_path with appropriate .fs2/ setup |
| [x] | T004 | Implement `agents-start-here` command + register in main.py | CS-2 | Core | T003, T002 | `/Users/jak/github/fs2-az-login/src/fs2/cli/agents_start_here.py`, `/Users/jak/github/fs2-az-login/src/fs2/cli/main.py` | All T003 tests pass (GREEN); state-adaptive output with correct next steps per state; State 5 points to MCP setup | State detection via `load_yaml_config` + isinstance guards. Depends on T002 because agents-start-here references `fs2 docs` commands in output. |
| [x] | T005 | Refactor both commands for code quality | CS-1 | Refactor | T002, T004 | Same as T002, T004 | All tests still pass; code follows project idioms (Rich markup, error patterns, docstrings) | Extract shared helpers if any; verify `NO_COLOR=1` degrades gracefully |
| [x] | T006 | Optional: Create bundled `agents-start-here.md` doc + update `agents.md` with setup pointer + add registry entry | CS-1 | Docs | T004 | `/Users/jak/github/fs2-az-login/src/fs2/docs/agents-start-here.md`, `/Users/jak/github/fs2-az-login/src/fs2/docs/agents.md`, `/Users/jak/github/fs2-az-login/src/fs2/docs/registry.yaml` | New doc accessible via `fs2 docs agents-start-here`; `agents.md` has "Getting Started" pointer at top; registry validates | Per spec OQ-1 (leaning yes) and OQ-4 (leaning yes). Tags: getting-started, onboarding, setup, init, mcp, agents, config |

### Test Design: `test_docs_cmd.py` (T001)

```python
"""Tests for fs2 docs CLI command."""
import json
import pytest
from typer.testing import CliRunner

pytestmark = pytest.mark.slow
runner = CliRunner()


class TestDocsCommandRegistered:
    """AC-8: Command is unguarded and registered."""

    def test_given_app_when_inspected_then_docs_command_registered(self):
        from fs2.cli.main import app
        names = [c.name for c in app.registered_commands]
        assert "docs" in names

    def test_given_no_config_when_docs_invoked_then_exits_zero(self, tmp_path, monkeypatch):
        from fs2.cli.main import app
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["docs"])
        assert result.exit_code == 0


class TestDocsListMode:
    """AC-3: Lists all documents grouped by category."""

    def test_given_no_args_when_docs_then_lists_all_documents(self, tmp_path, monkeypatch):
        from fs2.cli.main import app
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["docs"])
        assert result.exit_code == 0
        assert "agents" in result.output
        assert "configuration-guide" in result.output

    def test_given_category_flag_when_docs_then_filters(self, tmp_path, monkeypatch):
        """AC-9: Category filtering."""
        from fs2.cli.main import app
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["docs", "--category", "reference"])
        assert result.exit_code == 0
        assert "configuration-guide" in result.output

    def test_given_tags_flag_when_docs_then_filters(self, tmp_path, monkeypatch):
        """AC-9: Tag filtering."""
        from fs2.cli.main import app
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["docs", "--tags", "config"])
        assert result.exit_code == 0
        assert "configuration" in result.output


class TestDocsReadMode:
    """AC-4, AC-5: Read specific document or show error."""

    def test_given_valid_id_when_docs_then_shows_content(self, tmp_path, monkeypatch):
        from fs2.cli.main import app
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["docs", "agents"])
        assert result.exit_code == 0
        assert "Agent" in result.output  # Title from agents.md

    def test_given_invalid_id_when_docs_then_exits_one(self, tmp_path, monkeypatch):
        from fs2.cli.main import app
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["docs", "nonexistent"])
        assert result.exit_code == 1


class TestDocsJsonMode:
    """AC-6, AC-7: JSON output mirrors MCP format."""

    def test_given_json_flag_when_list_then_valid_json(self, tmp_path, monkeypatch):
        from fs2.cli.main import app
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["docs", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "docs" in data
        assert "count" in data
        assert isinstance(data["docs"], list)

    def test_given_json_flag_when_read_then_valid_json(self, tmp_path, monkeypatch):
        from fs2.cli.main import app
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["docs", "agents", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "agents"
        assert "content" in data
        assert "metadata" in data
```

### Test Design: `test_agents_start_here.py` (T003)

```python
"""Tests for fs2 agents-start-here CLI command."""
import pytest
from typer.testing import CliRunner

pytestmark = pytest.mark.slow
runner = CliRunner()


class TestAgentsStartHereRegistered:
    """AC-8: Command is unguarded and registered."""

    def test_given_app_when_inspected_then_command_registered(self):
        from fs2.cli.main import app
        names = [c.name for c in app.registered_commands]
        assert "agents-start-here" in names

    def test_given_no_config_when_invoked_then_exits_zero(self, tmp_path, monkeypatch):
        from fs2.cli.main import app
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["agents-start-here"])
        assert result.exit_code == 0


class TestAgentsStartHereState1:
    """AC-1: Nothing set up -- points to fs2 init."""

    def test_given_no_fs2_dir_when_invoked_then_shows_not_initialized(
        self, tmp_path, monkeypatch
    ):
        from fs2.cli.main import app
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["agents-start-here"])
        assert result.exit_code == 0
        assert "not initialized" in result.output.lower() or "fs2 init" in result.output


class TestAgentsStartHereState5:
    """AC-10: Fully configured -- points to MCP setup."""

    def test_given_fully_configured_when_invoked_then_points_to_mcp(
        self, tmp_path, monkeypatch
    ):
        from fs2.cli.main import app
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        # Set up State 5: config + graph + providers
        fs2_dir = tmp_path / ".fs2"
        fs2_dir.mkdir()
        config = fs2_dir / "config.yaml"
        config.write_text(
            "scan:\n  scan_paths: ['.']\n"
            "llm:\n  provider: azure\n"
            "embedding:\n  mode: azure\n"
        )
        graph = fs2_dir / "graph.pickle"
        graph.write_bytes(b"fake")

        result = runner.invoke(app, ["agents-start-here"])
        assert result.exit_code == 0
        assert "mcp" in result.output.lower()
```

### Implementation Pattern: `docs_cmd.py` (T002)

```python
"""fs2 docs -- Browse bundled documentation via CLI."""

import json
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown

console = Console()
stderr_console = Console(stderr=True)


def docs(
    doc_id: Annotated[
        str | None,
        typer.Argument(help="Document ID to read (omit to list all)"),
    ] = None,
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Filter by category"),
    ] = None,
    tags: Annotated[
        str | None,
        typer.Option("--tags", "-t", help="Filter by tags (comma-separated)"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Browse fs2 documentation. ..."""
    from fs2.core.dependencies import get_docs_service

    service = get_docs_service()

    if doc_id is None:
        _list_docs(service, category, tags, json_output)
    else:
        _read_doc(service, doc_id, json_output)
```

### Implementation Pattern: `agents_start_here.py` (T004)

```python
"""fs2 agents-start-here -- Orientation for AI agents and new users."""

from pathlib import Path

from rich.console import Console

from fs2.config.loaders import load_yaml_config

console = Console()


def agents_start_here() -> None:
    """Get started with fs2 - orientation for AI agents and new users. ..."""
    state = _detect_project_state()
    _render_header()
    _render_status(state)
    _render_next_step(state)
    _render_docs_section(state)
    _render_commands()


def _detect_project_state() -> ...:
    config_path = Path.cwd() / ".fs2" / "config.yaml"
    if not config_path.exists():
        return "nothing"
    config = load_yaml_config(config_path)
    # ... isinstance guards per Finding 03 ...
```

### Acceptance Criteria

- [ ] AC-1: `fs2 agents-start-here` works before init (exit 0, shows status + next step)
- [ ] AC-2: Output adapts across 5 project states with different recommendations
- [ ] AC-3: `fs2 docs` lists all documents grouped by category
- [ ] AC-4: `fs2 docs agents` displays document content
- [ ] AC-5: `fs2 docs nonexistent` exits 1 with helpful error
- [ ] AC-6: `fs2 docs --json` outputs `{"docs": [...], "count": N}`
- [ ] AC-7: `fs2 docs agents --json` outputs `{id, title, content, metadata}`
- [ ] AC-8: Both commands are unguarded (no `require_init`)
- [ ] AC-9: `fs2 docs --category reference` and `--tags config` filter correctly
- [ ] AC-10: State 5 (fully configured) points to MCP as next step
- [ ] All tests written before implementation (TDD RED-GREEN)
- [ ] No mocks used -- real DocsService with real bundled docs

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| State detection edge cases (empty YAML, non-dict sections) | Medium | Low | `isinstance(section, dict)` guards + `load_yaml_config` fallback to `{}` |
| MCP stdout contamination from new module imports | Low | Critical | Zero side effects at module level; follow existing pattern exactly |
| CliRunner can't capture stderr Rich output | Medium | Low | Use `Console()` (stdout) for primary output; test JSON via `print()`; test errors via exit codes |

---

## Change Footnotes Ledger

[^1]: [To be added during implementation via plan-6a]

---

**Next steps:**
- **Ready to implement**: `/plan-6-implement-phase --plan "docs/plans/026-agents-start-here/agents-start-here-plan.md"`
- **Optional validation**: `/plan-4-complete-the-plan` (recommended for CS-3+ tasks)
