# Research Report: agents-start-here CLI Command

**Generated**: 2026-02-14T12:00:00Z
**Research Query**: "Add a CLI command 'agents-start-here' that shows agents how to use the docs system, set up fs2 configs, and configure MCP servers"
**Mode**: Plan-Associated (026-agents-start-here)
**Location**: docs/plans/026-agents-start-here/research-dossier.md
**FlowSpace**: Available
**Findings**: 55+ across 7 subagents

## Executive Summary

### What It Does
The proposed `agents-start-here` CLI command would serve as a single entry point for AI agents (and humans) to understand how to set up and use fs2 from scratch. It bridges the gap between the existing `fs2 init` (creates config) and the MCP docs system (serves documentation to connected agents).

### Business Purpose
Today, agents using fs2 MCP tools must already have a working setup to discover documentation via `docs_list`/`docs_get`. There is no command that guides an agent through the complete journey: install -> init -> configure -> scan -> connect MCP -> use tools. The `agents-start-here` command fills this bootstrap gap.

### Key Insights
1. **The docs system already exists and works well** -- 8 bundled documents served via MCP `docs_list`/`docs_get` tools. Adding a new document is straightforward (create .md, add to registry.yaml).
2. **The CLI has clear patterns for adding commands** -- unguarded commands (like `init`, `doctor`) follow a well-established Typer pattern with Rich console output.
3. **The gap is specifically the bootstrap/onboarding flow** -- no existing command combines state detection ("what's configured?") with actionable guidance ("here's what to do next") in a single output.

### Quick Stats
- **CLI Commands**: 13 commands across 11 modules
- **Bundled Docs**: 8 documents in `src/fs2/docs/`
- **Doc Categories**: how-to (5), reference (3)
- **Prior Learnings**: 15 relevant discoveries from previous implementations
- **Test Patterns**: Well-established CliRunner + monkeypatch pattern

## How It Currently Works

### Entry Points

| Entry Point | Type | Location | Purpose |
|------------|------|----------|---------|
| `fs2 init` | CLI | `src/fs2/cli/init.py` | Creates `.fs2/config.yaml` from DEFAULT_CONFIG template |
| `fs2 doctor` | CLI | `src/fs2/cli/doctor.py` | Validates config, shows health report |
| `fs2 doctor llm` | CLI | `src/fs2/cli/doctor.py` | Tests LLM/embedding provider connectivity |
| `docs_list()` | MCP | `src/fs2/mcp/server.py` | Lists available bundled documentation |
| `docs_get(id)` | MCP | `src/fs2/mcp/server.py` | Retrieves specific document content |
| `AGENTS.md` | File | Root | Dev-focused agent guidance (CLAUDE.md clone) |
| `agents.md` | Doc | `src/fs2/docs/agents.md` | Tool usage patterns for connected agents |

### Core Execution Flow

**CLI Command Registration** (`main.py`):
```python
# Guarded (require .fs2/config.yaml):
app.command(name="scan")(require_init(scan))
app.command(name="tree")(require_init(tree))

# Unguarded (always work):
app.command(name="init")(init)
app.command(name="list-graphs")(list_graphs)
app.add_typer(doctor_app, name="doctor")
```

**Docs System Flow**:
```
Agent calls docs_list(category?, tags?)
  -> server.py:docs_list()
    -> get_docs_service() [singleton]
      -> DocsService.list_documents(category, tags)
        -> Filters registry entries (loaded from registry.yaml)
        -> Returns list[DocMetadata]
    -> Returns {"docs": [...], "count": N}

Agent calls docs_get(id="agents")
  -> server.py:docs_get()
    -> get_docs_service()
      -> DocsService.get_document(doc_id)
        -> Reads content via importlib.resources
        -> Returns Doc(metadata, content) or None
```

### Data Flow

```
registry.yaml (metadata) + *.md (content)
  |-- importlib.resources.files("fs2.docs")
  |-- DocsService (loads, validates, caches metadata)
  |     |-- list_documents(category, tags) -> filter
  |     |-- get_document(id) -> fresh content read
  |-- MCP tools (docs_list, docs_get) -> JSON dict
  |-- CLI (currently NO docs command exists)
```

## Architecture & Design

### Component Map

#### CLI Layer (`src/fs2/cli/`)
- **main.py**: Typer app, CLIContext dataclass, command registration
- **guard.py**: `require_init` decorator -- checks `.fs2/config.yaml`
- **utils.py**: `resolve_graph_from_context()`, `validate_save_path()`, `safe_write_file()`
- **init.py**: Config scaffold creation with DEFAULT_CONFIG template
- **doctor.py**: Config health diagnostics (Typer sub-app pattern)
- **install.py**: `install` and `upgrade` commands
- **{command}.py**: One module per command (scan, tree, get_node, search, mcp, watch, list_graphs)

#### Docs Layer (`src/fs2/docs/`)
- **registry.yaml**: Document metadata (id, title, summary, category, tags, path)
- **\*.md**: 8 bundled markdown documents
- **\_\_init\_\_.py**: Package marker for importlib.resources

#### Service Layer
- **DocsService** (`core/services/docs_service.py`): Loads registry, validates paths, serves content
- **Dependencies** (`core/dependencies.py`): Thread-safe singleton DI container

### Design Patterns Identified

1. **Guard Pattern**: `require_init` wraps commands needing config. Unguarded commands (init, doctor, list-graphs) always work.
2. **Dual Console**: `Console()` for stdout (human-readable), `Console(stderr=True)` for errors. JSON output uses raw `print()`.
3. **Composition Root**: Each command wires its own dependencies. Three sections: DI wiring -> Service call -> Presentation.
4. **Registry + Service + MCP**: Docs follow registry-driven discovery with DocsService as the domain layer.
5. **Subcommand Group**: `doctor` uses Typer sub-app pattern (`add_typer`) for `doctor llm`.

### System Boundaries
- **CLI boundary**: Rich console output, Typer argument parsing, exit codes (0/1/2)
- **MCP boundary**: JSON-RPC over STDIO, FastMCP tool registration, ToolError translation
- **Docs boundary**: Bundled in wheel via importlib.resources, no runtime dependencies on config or graph

## Dependencies & Integration

### What agents-start-here Would Depend On

| Dependency | Type | Purpose | Required? |
|------------|------|---------|-----------|
| `DocsService` | Service | Load/serve bundled documentation | Yes |
| `Rich Console` | Presentation | Formatted terminal output | Yes |
| `typer` | CLI framework | Command registration, arguments | Yes |
| `config/paths` | Config | Check if `.fs2/config.yaml` exists | Optional |
| `get_version_string()` | Utility | Show fs2 version | Optional |

### What Would NOT Be Needed
- No graph access (works before `fs2 scan`)
- No config guard (works before `fs2 init`)
- No embedding adapter
- No LLM service

## Quality & Testing

### Test Pattern for New CLI Commands

```python
"""Tests for fs2 agents-start-here CLI command."""
import pytest
from typer.testing import CliRunner

pytestmark = pytest.mark.slow  # REQUIRED for all CLI test files

runner = CliRunner()

class TestAgentsStartHereCommand:
    def test_given_app_when_inspected_then_command_registered(self):
        from fs2.cli.main import app
        command_names = [cmd.name for cmd in app.registered_commands]
        assert "agents-start-here" in command_names

class TestAgentsStartHereHelp:
    def test_given_help_flag_when_invoked_then_shows_usage(self):
        from fs2.cli.main import app
        result = runner.invoke(app, ["agents-start-here", "--help"])
        assert result.exit_code == 0

class TestAgentsStartHereNoGuard:
    def test_given_no_config_when_invoked_then_still_works(self, tmp_path, monkeypatch):
        from fs2.cli.main import app
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["agents-start-here"])
        assert result.exit_code == 0
```

### Available Test Fixtures

| Fixture | Purpose | Use For |
|---------|---------|---------|
| `tmp_path` + `monkeypatch` | Basic isolation | Most tests |
| `config_only_project` | Config exists, no graph | Testing state-aware guidance |
| `project_without_config` | No .fs2 at all | Testing pre-init state |
| `scanned_project` | Full setup | Testing post-scan guidance |

### Known Testing Constraints
- CliRunner cannot capture `Console(stderr=True)` output -- test exit codes instead
- All CLI test files must have `pytestmark = pytest.mark.slow`
- Import `app` inside test methods (not module level) to avoid singleton pollution
- Use `NO_COLOR=1` env var to stabilize Rich output for assertions

## Modification Considerations

### Safe to Modify
1. **`src/fs2/cli/main.py`**: Add one line to register the new command (unguarded)
2. **`src/fs2/docs/registry.yaml`**: Add entry for new bundled doc
3. **`src/fs2/docs/`**: Add new markdown file

### Extension Points
1. **New CLI module**: Create `src/fs2/cli/agents_start_here.py`
2. **New bundled doc**: Create `src/fs2/docs/agents-start-here.md`
3. **Registry entry**: Add to `src/fs2/docs/registry.yaml`
4. **New test file**: Create `tests/unit/cli/test_agents_start_here_cli.py`

## Prior Learnings (From Previous Implementations)

### PL-01: MCP stdout is fatal
**Source**: Plan 011, Phase 1, Critical Discovery 01
**Type**: gotcha
> STDIO protocol requires stderr-only logging BEFORE first import. Any stdout during import breaks MCP JSON-RPC.
**Action**: Document in agents-start-here that MCP server requires zero stdout pollution.

### PL-02: Test directory naming collisions
**Source**: Plan 011, Phase 1, T007
**Type**: gotcha
> `tests/mcp/` directory shadows installed `mcp` package. Renamed to `tests/mcp_tests/`.
**Action**: Use `test_agents_start_here_cli.py` naming (no collision risk).

### PL-04: importlib.resources requires __init__.py
**Source**: Plan 014, Phase 2, T005
**Type**: gotcha
> `importlib.resources.files()` requires `__init__.py` in all parent directories.
**Action**: `src/fs2/docs/__init__.py` already exists. No action needed for bundled docs.

### PL-05: Bundled docs can drift from source
**Source**: Plan 014, Phase 4, DYK-4
**Type**: debt
> Bundled docs are static snapshots. Won't auto-update when features change.
**Action**: Include a "Last Updated" note in any new bundled doc. Follow `just doc-build` pipeline.

### PL-06: Agent discoverability requires comprehensive tags
**Source**: Plan 014, Phase 4, DYK-5
**Type**: insight
> If an agent searches `docs_list(tags=['search'])` looking for help, tags must be comprehensive for discovery.
**Action**: Tag the new agents-start-here doc with `[getting-started, onboarding, setup, init, mcp, agents, config]`.

### PL-08: YAML parses date-like values as datetime.date
**Source**: Plan 009, Phase 2 and Plan 025
**Type**: gotcha (repeat offender)
> YAML parses `2024-06-01` as datetime.date, not string. Quote all date-like values.
**Action**: Mention in setup guidance that `api_version` values must be quoted in config.

### PL-10: fs2 init now has full provider examples
**Source**: Plan 025
**Type**: decision
> Expanded DEFAULT_CONFIG with commented Azure/OpenAI examples for LLM and embedding.
**Action**: agents-start-here can reference this -- "the config template has worked examples."

### PL-11: Typer global options must come BEFORE subcommand
**Source**: Plan 010, Phase 0
**Type**: gotcha
> `fs2 --graph-file PATH scan` (correct) vs `fs2 scan --graph-file PATH` (incorrect).
**Action**: Include correct option ordering in agent guidance.

### Prior Learnings Summary

| ID | Type | Source Plan | Key Insight | Action |
|----|------|-------------|-------------|--------|
| PL-01 | gotcha | 011 (MCP) | MCP stdout breaks JSON-RPC | Document constraint |
| PL-02 | gotcha | 011 (MCP) | Test dir naming collisions | Use safe naming |
| PL-04 | gotcha | 014 (Docs) | importlib needs __init__.py | Already handled |
| PL-05 | debt | 014 (Docs) | Bundled docs drift | Follow doc-build pipeline |
| PL-06 | insight | 014 (Docs) | Tags must be comprehensive | Wide tagging |
| PL-08 | gotcha | 009/025 | YAML date parsing | Mention in guidance |
| PL-10 | decision | 025 | Config has provider examples | Reference in guidance |
| PL-11 | gotcha | 010 | Global options before subcommand | Include in guidance |

## Critical Discoveries

### Critical Finding 01: No CLI Path to Documentation
**Impact**: Critical
**What**: The docs system (8 bundled documents) is only accessible via MCP tools (`docs_list`/`docs_get`). There is NO CLI command to browse or read documentation. An agent must already be connected via MCP to discover the docs that would help them connect via MCP -- a bootstrap paradox.
**Required Action**: The agents-start-here command must surface documentation content directly in the terminal, bypassing the MCP dependency.

### Critical Finding 02: The agents.md Doc Assumes Working Setup
**Impact**: High
**What**: The bundled `agents.md` (183 lines) covers tree/get_node/search tool usage but assumes the agent already has a working fs2 installation with a scanned graph. It does not cover: installation, init, config, scanning, or MCP client setup.
**Required Action**: Create a new document (or extend agents.md) that covers the full onboarding journey from zero.

### Critical Finding 03: Doctor Spec Explicitly Deferred This Feature
**Impact**: Medium
**What**: The doctor spec (Plan 017) explicitly listed "Interactive configuration wizard" as a non-goal and deferred it as a separate feature. The agents-start-here command is the natural successor to that deferred work.
**Required Action**: This is a green-light signal -- the architecture was designed to accommodate this feature later.

### Critical Finding 04: The Config Template Now Has Worked Examples
**Impact**: Medium (positive)
**What**: Plan 025 expanded the DEFAULT_CONFIG template to include commented LLM and embedding provider examples (Azure API key, Azure AD / az login, OpenAI). This means `fs2 init` already provides configuration guidance inline.
**Required Action**: agents-start-here can leverage this -- the config template serves as documentation. The command should reference it rather than duplicating provider setup instructions.

### Critical Finding 05: Unguarded Command Pattern Is Required
**Impact**: High
**What**: The command must work before `fs2 init` (no `.fs2/config.yaml`) since its purpose is to guide agents through initial setup. It must be registered like `init` and `doctor` (no `require_init` wrapper).
**Required Action**: Register as `app.command(name="agents-start-here")(agents_start_here)` in main.py.

## Supporting Documentation

### Related Existing Documents
- `src/fs2/docs/agents.md` -- Tool usage patterns (183 lines)
- `src/fs2/docs/mcp-server-guide.md` -- MCP setup for 5 platforms (451 lines)
- `src/fs2/docs/configuration-guide.md` -- Full config reference (732 lines)
- `src/fs2/docs/cli.md` -- CLI command reference (830 lines)
- `README.md` -- Comprehensive end-to-end overview (400 lines, not MCP-accessible)

### Related Plan Documents
- `docs/plans/014-mcp-doco/` -- Established the bundled docs system
- `docs/plans/017-doctor/` -- Deferred "interactive wizard" as separate feature
- `docs/plans/025-config-template/` -- Expanded config template with provider examples

### Key Code References
- `src/fs2/cli/main.py` -- Command registration (13 commands)
- `src/fs2/cli/guard.py` -- `require_init` decorator
- `src/fs2/cli/init.py` -- `DEFAULT_CONFIG` template, init flow
- `src/fs2/cli/doctor.py` -- Closest diagnostic analog (sub-app pattern)
- `src/fs2/core/services/docs_service.py` -- DocsService API
- `src/fs2/core/dependencies.py` -- Shared DI container
- `src/fs2/docs/registry.yaml` -- Document registry (8 entries)

## Recommendations

### If Implementing This Command
1. Create `src/fs2/cli/agents_start_here.py` with an unguarded command function
2. Register in `main.py` without `require_init` wrapper
3. Use `DocsService` to surface relevant bundled docs content
4. Detect project state (config exists? graph exists? embeddings?) and provide next-step guidance
5. Consider adding a new bundled doc (`agents-start-here.md`) with the complete onboarding journey

### Command Output Should Include
1. A sequential checklist with state detection (green check / red X):
   - fs2 installed? (always yes if command is running)
   - Config exists? (`fs2 init` done?)
   - Graph exists? (`fs2 scan` done?)
   - LLM configured? (optional, for smart content)
   - Embeddings configured? (optional, for semantic search)
2. MCP client setup snippets for Claude Code, Claude Desktop, GitHub Copilot
3. Reference to `docs_list()` / `docs_get()` for further reading
4. First-use workflow: `fs2 init` -> edit config -> `fs2 scan` -> connect MCP

### What to Avoid
- Do not duplicate the full config reference (point to `docs_get(id="configuration-guide")`)
- Do not require graph or config to run (must work from zero)
- Do not make it interactive (follow doctor precedent -- display-only)

## Next Steps

- Research-Only: Review findings and decide on action
- To proceed: Run `/plan-1b-specify "agents-start-here CLI command"` to create specification

---

**Research Complete**: 2026-02-14
**Report Location**: docs/plans/026-agents-start-here/research-dossier.md
