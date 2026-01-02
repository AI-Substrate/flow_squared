# Research Report: Save CLI/MCP Output to File

**Generated**: 2026-01-02
**Research Query**: Add ability to save CLI command output to file for jq processing
**Mode**: Plan-Associated
**Location**: `docs/plans/012-save-to-file/research-dossier.md`
**fs2 MCP**: Available (used for exploration)
**Findings**: 55+ findings from 7 specialized subagents

---

## Executive Summary

### What It Does
The save-to-file feature enables CLI commands and MCP tools to write their JSON output directly to files, allowing AI agents and scripts to process large results with tools like `jq` without stdout redirection complexity.

### Business Purpose
AI agents working with fs2 need to save complex search results for post-processing. Currently only `get-node` (CLI and MCP) supports file output. Adding this capability to `search` and `tree` commands enables agents to query once, save results, then run multiple jq transformations.

### Key Insights
1. **Pattern exists**: `get_node` already implements both CLI `--file` and MCP `save_to_file` with security validation
2. **Security critical**: `_validate_save_path()` prevents directory traversal - must be reused
3. **Tree needs JSON mode**: CLI tree outputs Rich formatted text, not JSON - needs `--json` flag

### Quick Stats
- **Commands affected**: 3 CLI commands, 3 MCP tools
- **Files to modify**: 4 source files + tests
- **Pattern reuse**: High (copy from get_node)
- **Complexity**: Low (CS-1)
- **Prior Learnings**: 15 relevant discoveries from previous plans

---

## How It Currently Works

### Entry Points

| Entry Point | Type | Location | Has File Output |
|------------|------|----------|-----------------|
| `fs2 get-node` | CLI | `src/fs2/cli/get_node.py:31` | ✓ `--file` option |
| `fs2 search` | CLI | `src/fs2/cli/search.py:46` | ✗ Missing |
| `fs2 tree` | CLI | `src/fs2/cli/tree.py:43` | ✗ Missing (also no JSON mode) |
| `get_node()` | MCP | `src/fs2/mcp/server.py:355` | ✓ `save_to_file` param |
| `search()` | MCP | `src/fs2/mcp/server.py:507` | ✗ Missing |
| `tree()` | MCP | `src/fs2/mcp/server.py:187` | ✗ Missing |

### Core Execution Flow

#### CLI Pattern (get_node with --file)
```
1. Parse args → typer.Option("--file", "-f")
2. Service call → GetNodeService.get_node(node_id)
3. Serialize → json.dumps(asdict(node), indent=2, default=str)
4. Output → if file: file.write_text(json_str) else: print(json_str)
5. Confirm → console.print("✓ Wrote {node_id} to {file}")
```

**Code** (`src/fs2/cli/get_node.py:102-107`):
```python
if file:
    file.write_text(json_str)
    console.print(f"[green]✓[/green] Wrote {node_id} to {file}")
else:
    print(json_str)  # stdout for piping
```

#### MCP Pattern (get_node with save_to_file)
```
1. Parse params → save_to_file: str | None
2. Service call → GetNodeService.get_node(node_id)
3. Validate path → _validate_save_path(save_to_file)
4. Write file → json.dump(result, f, indent=2)
5. Enrich response → result["saved_to"] = absolute_path
6. Return → dict with saved_to field
```

**Code** (`src/fs2/mcp/server.py:394-407`):
```python
if save_to_file is not None:
    absolute_path = _validate_save_path(save_to_file)
    with open(absolute_path, "w") as f:
        json.dump(result, f, indent=2)
    result["saved_to"] = absolute_path
return result
```

### Data Flow

```mermaid
graph LR
    A[User Request] --> B{CLI or MCP?}
    B -->|CLI| C[typer.Option --file]
    B -->|MCP| D[save_to_file param]
    C --> E[Service Call]
    D --> E
    E --> F[JSON Serialization]
    F --> G{File Output?}
    G -->|Yes| H[Path Validation]
    H --> I[Write to File]
    I --> J[Return/Confirm]
    G -->|No| K[stdout/Return dict]
```

### Security: Path Validation

**Node ID**: `callable:src/fs2/mcp/server.py:_validate_save_path`

```python
def _validate_save_path(save_to_file: str) -> str:
    """Validate save_to_file path is under current working directory.

    Per DYK Session: Security constraint - path must be at or under PWD.
    Prevents directory traversal attacks.
    """
    cwd = Path.cwd().resolve()
    target = (cwd / save_to_file).resolve()

    try:
        target.relative_to(cwd)
    except ValueError:
        raise ToolError(
            f"Path '{save_to_file}' escapes working directory. "
            "Only paths under the current directory are allowed."
        ) from None

    return str(target)
```

**Protects against**:
- `../escape.json` - parent directory traversal
- `/tmp/outside.json` - absolute paths outside cwd
- `subdir/../../../etc/passwd` - complex traversal

---

## Architecture & Design

### Component Map

```
src/fs2/
├── cli/
│   ├── get_node.py    # ✓ Has --file option
│   ├── search.py      # ✗ Needs --file option
│   └── tree.py        # ✗ Needs --file AND --json options
└── mcp/
    └── server.py
        ├── get_node()     # ✓ Has save_to_file param
        ├── search()       # ✗ Needs save_to_file param
        ├── tree()         # ✗ Needs save_to_file param
        └── _validate_save_path()  # Shared security function
```

### Design Patterns Identified

#### PS-01: CLI Stdout Discipline
- `print()` for JSON data → stdout (for piping)
- `Console(stderr=True)` for messages → stderr

#### PS-02: Naming Convention
- CLI: `--file` (`-f`) with `Path` type
- MCP: `save_to_file` with `str` type

#### PS-03: JSON Serialization
- `json.dumps(data, indent=2, default=str)` for stdout
- `json.dump(result, f, indent=2)` for file

#### PS-04: MCP Response Enrichment
- Add `saved_to` field with absolute path when saving
- Return full result + metadata (not just confirmation)

#### PS-05: Detail Level Filtering
- Use explicit field selection (not `asdict()`)
- Min mode: 7-9 fields, Max mode: 12-13 fields
- NEVER include embeddings

---

## Dependencies & Integration

### Internal Dependencies

| Dependency | Type | Purpose | Risk if Changed |
|------------|------|---------|-----------------|
| `json` | stdlib | Serialization | None |
| `pathlib.Path` | stdlib | Path handling | None |
| `typer` | external | CLI framework | Low |
| `fastmcp.ToolError` | external | MCP errors | Medium |
| `_validate_save_path()` | internal | Security | High |

### External Dependencies

| Library | Purpose | Criticality |
|---------|---------|-------------|
| `typer` | CLI argument parsing | High |
| `rich` | Console output formatting | Medium |
| `fastmcp` | MCP server framework | High |

### What Depends on This

#### Direct Consumers
- **AI Agents**: Call MCP tools, expect `saved_to` field
- **Shell scripts**: Use `fs2 search ... | jq`, need clean stdout
- **Tests**: 80+ MCP tests, 100+ CLI tests

---

## Quality & Testing

### Current Test Coverage

#### CLI Tests (`tests/unit/cli/test_get_node_cli.py`)
- `TestGetNodeFileOutput` class (lines 168-234)
- Tests: file creation, JSON validity, empty stdout with --file

#### MCP Tests (`tests/mcp_tests/test_get_node_tool.py`)
- `TestGetNodeSaveToFile` class (lines 341-563)
- 7 tests: file creation, valid JSON, `saved_to` field, security

### Test Patterns to Follow

```python
# CLI file output test
def test_given_file_flag_when_search_then_writes_to_file(scanned_project, tmp_path, monkeypatch):
    monkeypatch.chdir(scanned_project)
    output_file = tmp_path / "results.json"
    result = runner.invoke(app, ["search", "test", "--file", str(output_file)])
    assert result.exit_code == 0
    assert output_file.exists()
    data = json.loads(output_file.read_text())
    assert "meta" in data
    assert "results" in data

# MCP save_to_file test
def test_search_save_returns_saved_to_field(search_test_graph_store, tmp_path):
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
    finally:
        os.chdir(original_cwd)
```

### Coverage Gaps to Address

| Gap | Priority | Notes |
|-----|----------|-------|
| CLI search `--file` tests | P0 | New feature |
| MCP search `save_to_file` tests | P0 | New feature |
| CLI tree `--file` + `--json` tests | P1 | New features |
| MCP tree `save_to_file` tests | P1 | New feature |
| Security: CLI `--file` path validation | P0 | Currently no validation! |

---

## Modification Considerations

### ✅ Safe to Modify

1. **`src/fs2/cli/search.py`**: Add `--file` option
   - Pattern: Copy from `get_node.py`
   - Risk: Low (additive change)

2. **`src/fs2/mcp/server.py:search()`**: Add `save_to_file` param
   - Pattern: Copy from `get_node()`
   - Risk: Low (new optional parameter)

### ⚠️ Modify with Caution

1. **`src/fs2/cli/tree.py`**: Add `--file` AND `--json` options
   - Risk: Tree outputs Rich text, not JSON
   - Need: Add JSON output mode before file save makes sense
   - Pattern: `--json` outputs JSON to stdout, `--file` saves it

2. **`src/fs2/mcp/server.py:tree()`**: Add `save_to_file` param
   - Risk: Return type changes from `list[dict]` to `dict` with wrapper
   - Design choice: `{"result": [...], "saved_to": "..."}` vs just add to list?

### 🚫 Danger Zones

1. **`_validate_save_path()`**: DO NOT modify
   - Security-critical function
   - Any changes require security review

2. **MCP annotations**: Must update `readOnlyHint`
   - If adding `save_to_file` to tree/search, set `readOnlyHint=False`

---

## Prior Learnings (From Previous Implementations)

### 📚 PL-01: Clean Piping Requires Bypassing Rich Console
**Source**: `docs/plans/005-get-node-command/research-dossier.md`
**Type**: Pattern

**What They Found**:
> Use raw `print()` for JSON output, not `console.print()`

**Action for Current Work**:
Continue using `print(json_str)` for stdout, `console.print()` for messages only.

---

### 📚 PL-02: Never Use asdict() on CodeNode
**Source**: `docs/plans/011-mcp/tasks/phase-5-cli-integration/tasks.md`
**Type**: Gotcha

**What They Found**:
> Don't use `asdict()` - leaks embeddings. Use `_code_node_to_dict()` with explicit field selection.

**Action for Current Work**:
For search results, use `SearchResult.to_dict(detail)`. For tree nodes, use `_tree_node_to_dict()`.

---

### 📚 PL-03: STDIO Transport Requires stderr-Only Logging
**Source**: `docs/plans/011-mcp/tasks/phase-5-cli-integration/tasks.md`
**Type**: Gotcha

**What They Found**:
> MCPLoggingConfig().configure() MUST be called as first line. Any stdout pollution breaks JSON-RPC.

**Action for Current Work**:
No changes needed - logging is already configured. Just ensure file operations don't print to stdout.

---

### 📚 PL-08: save_to_file Path Validation Required
**Source**: `docs/plans/011-mcp/tasks/phase-3-get-node-tool-implementation/tasks.md`
**Type**: Security

**What They Found**:
> Path validation required - `_validate_save_path()` raises ToolError. Using pathlib's `relative_to()` for security check.

**Action for Current Work**:
Reuse existing `_validate_save_path()` function for all new save_to_file implementations.

---

### 📚 PL-13: readOnlyHint Must Be False for File Writers
**Source**: `docs/plans/011-mcp/tasks/phase-5-cli-integration/tasks.md`
**Type**: Decision

**What They Found**:
> Don't set readOnlyHint=True for tools that write files. Agents use hints to decide tool safety.

**Action for Current Work**:
When adding `save_to_file` to search/tree MCP tools, update annotations to `readOnlyHint=False`.

---

### Prior Learnings Summary

| ID | Type | Key Insight | Action |
|----|------|-------------|--------|
| PL-01 | Pattern | Use `print()` not `console.print()` for JSON | Follow pattern |
| PL-02 | Gotcha | No `asdict()`, use explicit field selection | Use `to_dict()` methods |
| PL-03 | Gotcha | stderr-only logging for MCP | Already handled |
| PL-04 | Pattern | `Console(stderr=True)` for errors | Follow pattern |
| PL-05 | Pattern | `json.dumps(default=str)` for Path/datetime | Follow pattern |
| PL-06 | Testing | CliRunner can't capture stderr | Test stdout empty |
| PL-08 | Security | Path validation required | Reuse `_validate_save_path()` |
| PL-09 | Pattern | None for not-found, ToolError for errors | Follow pattern |
| PL-13 | Decision | readOnlyHint=False for file writers | Update annotations |

---

## Critical Discoveries

### 🚨 Critical Finding 01: CLI `--file` Has No Path Validation

**Impact**: Security vulnerability
**Source**: Implementation Archaeologist (IA-01)

**What**: The CLI `get-node --file` option uses `Path` type directly without validation.

**Code** (`src/fs2/cli/get_node.py:41-42`):
```python
file: Annotated[
    Path | None,
    typer.Option("--file", "-f", help="Write JSON to file instead of stdout"),
] = None,
```

**Risk**: User could potentially write to paths like `--file /etc/cron.d/evil`.

**Required Action**:
- Add path validation for CLI `--file` option (similar to MCP)
- Or document this as acceptable since CLI runs as user's own permissions

---

### 🚨 Critical Finding 02: Tree Output Type Mismatch

**Impact**: Design decision required
**Source**: Interface Analyst (IC-02)

**What**: CLI tree outputs Rich formatted text, MCP tree returns `list[dict]`. Adding `--file` to CLI tree without `--json` flag would save Rich markup text.

**Options**:
1. Add `--json` flag that changes output to JSON (recommended)
2. Save Rich text as-is (confusing for jq workflows)
3. Only add file output to MCP tree (inconsistent)

**Required Action**: Add `--json` flag to CLI tree command before or alongside `--file`.

---

### 🚨 Critical Finding 03: MCP Tree Return Type Change

**Impact**: Breaking change potential
**Source**: Interface Analyst (IC-05)

**What**: MCP `tree()` returns `list[dict]`. Adding `save_to_file` with `saved_to` field requires changing return type.

**Options**:
1. Return `{"result": [...], "saved_to": "..."}` when saving (type change)
2. Don't add `saved_to` to response (inconsistent with get_node)
3. Always return wrapper dict (breaking change)

**Recommended**: Option 1 - only change when `save_to_file` is used. Document this behavior.

---

## Recommendations

### If Modifying This System

1. **Start with search** - simplest case, already returns dict envelope
2. **Add CLI `--file` first, then MCP `save_to_file`** - easier to test
3. **Reuse `_validate_save_path()`** - don't reinvent security
4. **Update MCP annotations** - `readOnlyHint=False` when file output added

### If Extending This System

1. **Follow the get_node pattern** - it's well-tested
2. **Add tests for security** - path escape, absolute paths
3. **Document the `saved_to` field** - agents expect it

### If Refactoring This System

1. **Consider shared helper** - `_save_json_to_file(data, path)` for DRY
2. **Unify CLI path validation** - CLI currently lacks what MCP has
3. **Standardize output wrapper** - all tools could use `{"result": ..., "saved_to": ...}`

---

## Implementation Roadmap

### Phase 1: CLI `search --file` (Lowest risk)
- Add `--file` option to `src/fs2/cli/search.py`
- Pattern: Copy from `get_node.py`
- Tests: Add `TestSearchFileOutput` class

### Phase 2: MCP `search(save_to_file=...)`
- Add `save_to_file` param to `src/fs2/mcp/server.py:search()`
- Reuse `_validate_save_path()`
- Add `saved_to` to envelope response
- Update `readOnlyHint=False`
- Tests: Add `TestSearchSaveToFile` class

### Phase 3: CLI `tree --json` + `--file`
- Add `--json` flag for JSON output mode
- Add `--file` option (only works with `--json`)
- Tests: Add tree file output tests

### Phase 4: MCP `tree(save_to_file=...)`
- Add `save_to_file` param
- Handle return type: wrap in `{"result": [...], "saved_to": "..."}`
- Update `readOnlyHint=False`
- Tests: Add tree save tests

---

## Appendix: File Inventory

### Core Files to Modify

| File | Purpose | Changes Needed |
|------|---------|----------------|
| `src/fs2/cli/search.py` | CLI search | Add `--file` option |
| `src/fs2/cli/tree.py` | CLI tree | Add `--json` and `--file` options |
| `src/fs2/mcp/server.py` | MCP tools | Add `save_to_file` to search, tree |

### Test Files to Create/Modify

| File | Purpose |
|------|---------|
| `tests/unit/cli/test_search_cli.py` | Add `TestSearchFileOutput` class |
| `tests/unit/cli/test_tree_cli.py` | Add tree file output tests |
| `tests/mcp_tests/test_search_tool.py` | Add `TestSearchSaveToFile` class |
| `tests/mcp_tests/test_tree_tool.py` | Add tree save_to_file tests |

### Reference Files (Patterns to Copy)

| File | Pattern |
|------|---------|
| `src/fs2/cli/get_node.py:38-43` | CLI `--file` option definition |
| `src/fs2/cli/get_node.py:102-107` | CLI file write logic |
| `src/fs2/mcp/server.py:355-420` | MCP `save_to_file` implementation |
| `src/fs2/mcp/server.py:323-352` | `_validate_save_path()` security |
| `tests/mcp_tests/test_get_node_tool.py:341-563` | save_to_file test patterns |

---

## Next Steps

**Research complete. Ready for specification.**

- Next step: Run `/plan-1b-specify "Add save-to-file capability for CLI and MCP commands"`
- This will create the feature specification based on this research

---

**Research Complete**: 2026-01-02
**Report Location**: `docs/plans/012-save-to-file/research-dossier.md`
