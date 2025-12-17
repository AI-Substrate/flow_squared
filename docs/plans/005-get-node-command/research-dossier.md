# Research Report: `get-node` Command Implementation

**Generated**: 2025-12-17
**Research Query**: "need a new command now, that will enable the user to either save a node to a file or to just show it on screen (basically its like read file). call it get-node and it will take the nodeid as positional and --file as optional, otherwise it will jump to output. It should not have any other output when in just file show mode, so it can pipe in to things like jq - so make sure we are suppressing logs for this command when it's worked, errors are allowed, but there should be no non-error output."
**Mode**: Plan-Associated
**Location**: `docs/plans/005-get-node-command/research-dossier.md`
**FlowSpace**: Available
**Findings**: 60 findings across 6 subagents

---

## Executive Summary

### What It Does
A new CLI command `fs2 get-node <node_id>` that retrieves a single CodeNode from the graph store and outputs it as JSON - either to stdout (for piping to `jq`) or to a file via `--file`.

### Business Purpose
Enables programmatic access to individual code nodes for scripting, CI/CD pipelines, and integration with JSON-processing tools like `jq`.

### Key Insights
1. **Clean piping requires bypassing Rich Console** - Use raw `print()` for JSON output, not `console.print()`
2. **CodeNode serialization via `dataclasses.asdict()` + `json.dumps()`** - Not Pydantic, no `model_dump_json()`
3. **GraphStore.get_node() is O(1) lookup** - Direct dict access via node_id key

### Quick Stats
- **Reference Command**: `tree.py` (312 lines)
- **Core Dependencies**: GraphStore, CodeNode, TreeConfig
- **Test Infrastructure**: CliRunner, FakeGraphStore, session fixtures
- **Complexity**: Low (single node lookup + JSON serialization)

---

## How It Should Work

### Entry Point
```
fs2 get-node <node_id> [--file PATH]
```

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `node_id` | positional | Yes | - | Node ID to retrieve (e.g., `callable:src/main.py:main`) |
| `--file` | option | No | None | Output file path; if omitted, output to stdout |

### Core Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                       fs2 get-node                               │
├─────────────────────────────────────────────────────────────────┤
│  1. Parse args: node_id (positional), --file (optional)         │
│  2. Load config via FS2ConfigurationService                     │
│  3. Load graph from TreeConfig.graph_path                       │
│  4. Call graph_store.get_node(node_id)                          │
│  5. If None: error to stderr, exit 1                            │
│  6. Serialize: asdict(node) → json.dumps()                      │
│  7. Output:                                                      │
│     - --file: write to file, optional success to stderr         │
│     - stdout: print raw JSON only (no decoration)               │
│  8. Exit 0                                                       │
└─────────────────────────────────────────────────────────────────┘
```

### Critical Output Requirement

**For stdout mode (no `--file`)**: ZERO non-error output besides the JSON. This enables:
```bash
fs2 get-node "callable:src/main.py:main" | jq '.signature'
```

**Implementation approach**:
- Do NOT use `console.print()` for JSON data
- Use raw `print(json_str)` or `sys.stdout.write(json_str + "\n")`
- Errors go to `sys.stderr` (allowed per user spec)
- No logging, no progress, no Rich formatting on stdout

---

## Architecture & Design

### Component Map

```
src/fs2/cli/
├── main.py          # app.command(name="get-node")(get_node)
└── get_node.py      # NEW: Command implementation

src/fs2/config/
└── objects.py       # TreeConfig (reuse graph_path)

src/fs2/core/repos/
├── graph_store.py   # GraphStore.get_node() ABC
└── graph_store_impl.py  # NetworkXGraphStore implementation
```

### Key APIs Used

| Component | Method | Purpose |
|-----------|--------|---------|
| `FS2ConfigurationService` | `require(TreeConfig)` | Get graph path |
| `NetworkXGraphStore` | `load(path)` | Load graph from pickle |
| `NetworkXGraphStore` | `get_node(node_id)` | O(1) node lookup |
| `dataclasses` | `asdict(node)` | Convert CodeNode to dict |
| `json` | `dumps(dict, indent=2)` | Serialize to JSON |

### Design Pattern: Conditional Output

```python
import sys
import json
from dataclasses import asdict

def get_node(node_id: str, file: Path | None = None) -> None:
    # ... load graph, get node ...

    json_str = json.dumps(asdict(node), indent=2, default=str)

    if file:
        # Write to file
        file.write_text(json_str)
        # Optional: confirmation to stderr (user can see it, jq won't)
        print(f"✓ Wrote node to {file}", file=sys.stderr)
    else:
        # Raw stdout - NO Rich, NO console.print()
        print(json_str)  # Goes to stdout, clean for piping
```

---

## Implementation Specification

### Command Signature

```python
# src/fs2/cli/get_node.py

import sys
import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from fs2.config.objects import TreeConfig
from fs2.config.service import FS2ConfigurationService, MissingConfigurationError
from fs2.core.repos.graph_store_impl import NetworkXGraphStore, GraphStoreError

# Console for errors only (stderr)
console = Console(stderr=True)

def get_node(
    node_id: Annotated[
        str,
        typer.Argument(
            help="Node ID to retrieve (e.g., 'callable:src/main.py:main')",
        ),
    ],
    file: Annotated[
        Path | None,
        typer.Option(
            "--file", "-f",
            help="Output file path. If omitted, outputs to stdout.",
        ),
    ] = None,
) -> None:
    """Retrieve a node by ID and output as JSON.

    Output is clean JSON suitable for piping to jq or other tools.
    Errors are written to stderr.

    Examples:
        fs2 get-node "callable:src/main.py:main"
        fs2 get-node "file:src/main.py" | jq '.signature'
        fs2 get-node "type:src/models.py:User" --file user.json
    """
    try:
        config = FS2ConfigurationService()
        tree_config = config.require(TreeConfig)
        graph_path = Path(tree_config.graph_path)

        if not graph_path.exists():
            console.print("[red]Error:[/red] No graph found. Run [bold]fs2 scan[/bold] first.")
            raise typer.Exit(code=1)

        graph_store = NetworkXGraphStore(config)
        graph_store.load(graph_path)

        node = graph_store.get_node(node_id)

        if node is None:
            console.print(f"[red]Error:[/red] Node not found: {node_id}")
            raise typer.Exit(code=1)

        # Serialize to JSON
        json_str = json.dumps(asdict(node), indent=2, default=str)

        if file:
            file.write_text(json_str)
            # Success message to stderr (doesn't pollute stdout)
            console.print(f"[green]✓[/green] Wrote node to {file}")
        else:
            # Raw stdout - clean for piping
            print(json_str)

    except MissingConfigurationError:
        console.print(
            "[red]Error:[/red] No configuration found.\n"
            "  Run [bold]fs2 init[/bold] first to create .fs2/config.yaml"
        )
        raise typer.Exit(code=1) from None

    except GraphStoreError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=2) from None
```

### Registration in main.py

```python
# src/fs2/cli/main.py (add to existing)

from fs2.cli.get_node import get_node

# In the existing command registration section:
app.command(name="get-node")(get_node)
```

---

## CodeNode JSON Schema

The output JSON contains all 22 CodeNode fields:

```json
{
  "node_id": "callable:src/calc.py:Calculator.add",
  "category": "callable",
  "ts_kind": "function_definition",
  "name": "add",
  "qualified_name": "Calculator.add",
  "start_line": 10,
  "end_line": 15,
  "start_column": 4,
  "end_column": 0,
  "start_byte": 245,
  "end_byte": 389,
  "content": "def add(self, a: int, b: int) -> int:\n        return a + b",
  "signature": "def add(self, a: int, b: int) -> int:",
  "language": "python",
  "is_named": true,
  "field_name": null,
  "is_error": false,
  "parent_node_id": "type:src/calc.py:Calculator",
  "truncated": false,
  "truncated_at_line": null,
  "smart_content": null,
  "embedding": null
}
```

---

## Exit Codes

| Code | Meaning | Example |
|------|---------|---------|
| 0 | Success | Node found and output |
| 1 | User error | Node not found, missing config, missing graph |
| 2 | System error | Corrupted graph file, I/O error |

---

## Test Plan

### Test File: `tests/unit/cli/test_get_node_cli.py`

```python
class TestGetNodeHelp:
    """Verify help text and command discovery."""
    def test_given_help_flag_when_get_node_then_shows_usage(self): ...
    def test_given_get_node_when_no_args_then_shows_error(self): ...

class TestGetNodeSuccess:
    """Verify successful node retrieval."""
    def test_given_valid_node_id_when_get_node_then_outputs_json(self): ...
    def test_given_valid_node_id_when_get_node_then_exit_zero(self): ...
    def test_given_file_flag_when_get_node_then_writes_file(self): ...
    def test_given_stdout_when_get_node_then_no_extra_output(self): ...

class TestGetNodeErrors:
    """Verify error handling."""
    def test_given_missing_graph_when_get_node_then_exit_one(self): ...
    def test_given_unknown_node_when_get_node_then_exit_one(self): ...
    def test_given_corrupted_graph_when_get_node_then_exit_two(self): ...

class TestGetNodePiping:
    """Verify clean output for piping."""
    def test_given_stdout_when_get_node_then_valid_json(self): ...
    def test_given_stdout_when_get_node_then_parseable_by_json_loads(self): ...
```

### Critical Test: Clean Piping

```python
def test_given_stdout_when_get_node_then_no_extra_output(self, scanned_project, monkeypatch):
    """Verify stdout contains ONLY JSON, nothing else."""
    monkeypatch.chdir(scanned_project)
    monkeypatch.setenv("NO_COLOR", "1")

    result = runner.invoke(app, ["get-node", "file:src/main.py"])

    assert result.exit_code == 0

    # The entire stdout should be valid JSON
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"stdout is not valid JSON: {e}\nOutput was: {result.stdout}")

    # Verify it's a CodeNode structure
    assert "node_id" in data
    assert "category" in data
    assert data["node_id"] == "file:src/main.py"
```

---

## Modification Considerations

### Safe to Modify
- Create new `src/fs2/cli/get_node.py` - isolated new file
- Register in `main.py` - single line addition
- Reuse `TreeConfig.graph_path` - no config changes needed

### Considerations
- **Rich Console for errors**: Using `Console(stderr=True)` ensures errors go to stderr while keeping stdout clean
- **No logging**: The command should not configure logging at all for clean output

### Avoid
- Don't add `--verbose` flag - contradicts clean piping requirement
- Don't use `console.print()` for the JSON data
- Don't add progress indicators or spinners

---

## Commands Reference

```bash
# Basic usage
fs2 get-node "callable:src/main.py:main"

# Pipe to jq
fs2 get-node "callable:src/main.py:main" | jq '.signature'
fs2 get-node "file:src/main.py" | jq '.content'

# Save to file
fs2 get-node "type:src/models.py:User" --file user-node.json

# Error handling
fs2 get-node "nonexistent:node" 2>/dev/null || echo "Node not found"

# Check exit code
fs2 get-node "file:src/main.py" > /dev/null && echo "Found" || echo "Not found"
```

---

## Detailed Research Findings

### CLI Structure (CLI-01 to CLI-10)

1. **CLI-01**: Typer app initialization with `typer.Typer(name="fs2", help="...", no_args_is_help=True)`
2. **CLI-02**: Command registration via `app.command(name="get-node")(get_node)`
3. **CLI-03**: Positional arguments with `Annotated[str, typer.Argument(help="...")]`
4. **CLI-04**: Optional arguments with `Annotated[Path | None, typer.Option("--file", "-f", help="...")]`
5. **CLI-05**: Config loading via `FS2ConfigurationService().require(TreeConfig)`
6. **CLI-06**: Config objects are Pydantic BaseModel with `__config_path__`
7. **CLI-07**: Exit codes: 0=success, 1=user error, 2=system error
8. **CLI-08**: Rich Console for formatted output with markup
9. **CLI-09**: Verbose logging via `--verbose` flag (NOT needed for get-node)
10. **CLI-10**: Exception handling at command boundary with typer.Exit()

### GraphStore (GS-01 to GS-10)

1. **GS-01**: `GraphStore.get_node(node_id) -> CodeNode | None` ABC interface
2. **GS-02**: NetworkXGraphStore uses DiGraph with O(1) dict lookup
3. **GS-03**: Node ID format: `{category}:{file_path}:{qualified_name}`
4. **GS-04**: Pickle persistence with `(metadata, DiGraph)` tuple
5. **GS-05**: RestrictedUnpickler for security (whitelisted classes only)
6. **GS-06**: Format versioning (FORMAT_VERSION = "1.0")
7. **GS-07**: FakeGraphStore for testing with call_history
8. **GS-08**: Edge direction: parent → child
9. **GS-09**: Upsert behavior on duplicate node_ids
10. **GS-10**: ConfigurationService injection pattern

### CodeNode Serialization (CN-01 to CN-10)

1. **CN-01**: Frozen dataclass with 22 fields
2. **CN-02**: Dual classification: `category` (universal) + `ts_kind` (grammar-specific)
3. **CN-03**: Deterministic node_id format for REST APIs
4. **CN-04**: Factory methods for safe construction
5. **CN-05**: Immutability enforced (frozen=True)
6. **CN-06**: Dual-format positions: byte offsets + line/column
7. **CN-07**: Full source content in `content` field
8. **CN-08**: Pickle preserves all fields perfectly
9. **CN-09**: `dataclasses.asdict()` for dict conversion
10. **CN-10**: Custom JSONEncoder option for frameworks

### Logging Suppression (LOG-01 to LOG-10)

1. **LOG-01**: LogAdapterConfig min_level filtering
2. **LOG-02**: Level filtering in ConsoleLogAdapter
3. **LOG-03**: Stream separation: stdout vs stderr
4. **LOG-04**: TTY detection via `sys.stdout.isatty()`
5. **LOG-05**: Rich Console output control
6. **LOG-06**: Exit code conventions
7. **LOG-07**: Verbose mode as output control
8. **LOG-08**: Data model results for programmatic output
9. **LOG-09**: NO_COLOR environment variable support
10. **LOG-10**: Structured logging with context

### Output Patterns (OUT-01 to OUT-10)

1. **OUT-01**: Rich Console for formatted terminal output
2. **OUT-02**: `Path.write_text()` for file writing
3. **OUT-03**: Pickle for complex data structures
4. **OUT-04**: stderr for errors, stdout for info
5. **OUT-05**: Frozen dataclasses for domain models
6. **OUT-06**: `dataclasses.asdict()` + `json.dumps()` (not Pydantic)
7. **OUT-07**: Dual output pattern: console + file
8. **OUT-08**: Exception translation at CLI boundary
9. **OUT-09**: Typer Option/Argument for CLI flags
10. **OUT-10**: Exit code convention: 0/1/2

### Testing Patterns (TEST-01 to TEST-10)

1. **TEST-01**: CliRunner for Typer command invocation
2. **TEST-02**: Exit code testing (0, 1, 2)
3. **TEST-03**: Stdout output verification
4. **TEST-04**: Regex pattern matching for complex output
5. **TEST-05**: monkeypatch.chdir and NO_COLOR fixtures
6. **TEST-06**: Graph file fixtures (empty, corrupted, valid)
7. **TEST-07**: FakeConfigurationService for test DI
8. **TEST-08**: FakeGraphStore call history verification
9. **TEST-09**: Icon and symbol verification in output
10. **TEST-10**: Session-scoped fixtures for expensive setup

---

## Summary

The `get-node` command is a straightforward implementation that:

1. **Follows existing patterns** from `tree.py` for config loading and graph access
2. **Uses `Console(stderr=True)`** for error messages, keeping stdout pristine
3. **Uses raw `print()`** for JSON output, bypassing Rich formatting
4. **Leverages `dataclasses.asdict()`** for CodeNode serialization
5. **Supports both stdout and file output** via `--file` option

The key innovation is the **strict stdout discipline** - no logging, no Rich formatting, no progress indicators - ensuring the output is directly pipeable to `jq` and other JSON tools.

---

**Research Complete**: 2025-12-17
**Report Location**: `docs/plans/005-get-node-command/research-dossier.md`
**Next Step**: Run `/plan-1b-specify "get-node command"` to create specification, or proceed directly to implementation
