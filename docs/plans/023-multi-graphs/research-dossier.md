# Research Report: Multi-Graph Support for fs2

**Generated**: 2026-01-12T23:15:00Z
**Research Query**: "Implement multi-graph support allowing MCP/CLI to access multiple named graphs from configuration"
**Mode**: Plan-Associated
**Location**: `docs/plans/023-multi-graphs/research-dossier.md`
**FlowSpace**: Available (used for exploration)
**Findings**: 70+ findings from 7 subagents

---

## Executive Summary

### What It Does
fs2 currently supports a single graph file (`.fs2/graph.pickle`) that can be overridden via `--graph-file` CLI option. The goal is to add support for multiple named graphs configured in YAML, enabling agents to explore external codebases as references.

### Business Purpose
Allow coding agents to access multiple codebases simultaneously - their local project graph plus external reference graphs (libraries, frameworks, prior projects) - for richer context during development.

### Key Insights
1. **Configuration system is ready**: The typed registry pattern with deep merge supports adding new config sections easily
2. **CLI global options work well**: `--graph-name` can follow the existing `--graph-file` pattern via `CLIContext`
3. **MCP lazy singletons need extension**: Current single-graph singletons must become a graph cache service
4. **Path resolution exists**: Relative paths are resolved from CWD; tilde expansion available via `Path.expanduser()`
5. **No caching currently**: Each command/tool creates fresh graph store; MCP needs caching for performance

### Quick Stats
- **Components**: ~15 files need modification across config, CLI, MCP, services
- **Dependencies**: NetworkX, Pydantic, FastMCP - all support the feature
- **Test Coverage**: Comprehensive fixture patterns exist for multi-graph testing
- **Complexity**: Medium - mostly additive changes following existing patterns

---

## How It Currently Works

### Entry Points

| Entry Point | Type | Location | Purpose |
|-------------|------|----------|---------|
| `fs2 tree` | CLI | `src/fs2/cli/tree.py` | Display code structure |
| `fs2 search` | CLI | `src/fs2/cli/search.py` | Search code graph |
| `fs2 get-node` | CLI | `src/fs2/cli/get_node.py` | Retrieve single node |
| `mcp__flowspace__tree` | MCP Tool | `src/fs2/mcp/server.py:354` | MCP tree exploration |
| `mcp__flowspace__search` | MCP Tool | `src/fs2/mcp/server.py:671` | MCP semantic search |
| `mcp__flowspace__get_node` | MCP Tool | `src/fs2/mcp/server.py:505` | MCP node retrieval |

### Core Execution Flow

1. **CLI Global Option Processing** (`src/fs2/cli/main.py:56-64`):
   ```python
   @app.callback()
   def main(ctx: typer.Context, graph_file: str | None = None):
       ctx.obj = CLIContext(graph_file=graph_file)
   ```

2. **Command Composition Root** (e.g., `src/fs2/cli/tree.py:167-174`):
   ```python
   config = FS2ConfigurationService()
   if ctx.obj and ctx.obj.graph_file:
       config.set(GraphConfig(graph_path=ctx.obj.graph_file))
   graph_store = NetworkXGraphStore(config)
   service = TreeService(config=config, graph_store=graph_store)
   ```

3. **Service Lazy Loading** (`src/fs2/core/services/tree_service.py:129-142`):
   ```python
   def _ensure_loaded(self) -> None:
       if self._loaded:
           return
       graph_path = Path(self._config.graph_path)
       self._graph_store.load(graph_path)
       self._loaded = True
   ```

4. **MCP Dependency Injection** (`src/fs2/mcp/dependencies.py:44-105`):
   ```python
   def get_graph_store() -> GraphStore:
       global _graph_store
       with _lock:
           if _graph_store is None:
               _graph_store = NetworkXGraphStore(get_config())
       return _graph_store
   ```

### Data Flow
```
User Request (--graph-file or --graph-name)
    ↓
CLIContext / MCP Tool Parameter
    ↓
GraphConfig override in ConfigurationService
    ↓
NetworkXGraphStore.load(path)
    ↓
Service reads from GraphStore ABC
    ↓
Response to user
```

### State Management
- **CLI**: Stateless - fresh config/store/service per command
- **MCP**: Lazy singletons with thread-safe initialization
- **Graph Files**: Pickle format with `(metadata, nx.DiGraph)` tuple

---

## Architecture & Design

### Component Map

#### Core Components
- **ConfigurationService** (`src/fs2/config/service.py`): Typed object registry for all configs
- **GraphConfig** (`src/fs2/config/objects.py:176-197`): Single graph path configuration
- **NetworkXGraphStore** (`src/fs2/core/repos/graph_store_impl.py`): Production graph storage
- **MCP Dependencies** (`src/fs2/mcp/dependencies.py`): Lazy singleton factory functions

### Design Patterns Identified

1. **Typed Object Registry** (ConfigurationService):
   - Store/retrieve configs by type: `config.set(GraphConfig(...))`, `config.require(GraphConfig)`
   - Services extract their own configs internally

2. **Dependency Injection** (Clean Architecture):
   - Services receive `ConfigurationService` registry + `GraphStore` ABC
   - Composition roots in CLI commands and MCP tools

3. **Lazy Singleton** (MCP Dependencies):
   - Thread-safe with RLock
   - Created on first access, cached thereafter

4. **Deep Merge** (Config Loading):
   - Leaf-level override, not atomic section replacement
   - Preserves sibling fields from lower-priority sources

### System Boundaries
- **Internal**: Config → Services → Adapters/Repos
- **External**: Pickle files on filesystem
- **Integration**: MCP protocol via FastMCP

---

## Dependencies & Integration

### What Multi-Graph Depends On

| Dependency | Type | Purpose | Risk if Changed |
|------------|------|---------|-----------------|
| GraphConfig | Required | Base config model | Must extend, not replace |
| ConfigurationService | Required | Registry pattern | Add new config type |
| NetworkXGraphStore | Required | Graph loading | No changes needed |
| CLIContext | Required | Global option passing | Add new field |
| MCP dependencies.py | Required | Singleton management | Major changes needed |

### What Depends on This

| Consumer | How It Uses | Breaking Changes |
|----------|-------------|------------------|
| TreeService | Reads GraphConfig from registry | None if interface preserved |
| SearchService | Uses graph_store ABC | None |
| GetNodeService | Uses graph_store ABC | None |
| All MCP tools | Use get_graph_store() | Must update to pass graph_name |

---

## Quality & Testing

### Current Test Coverage
- **Unit Tests**: GraphStore ABC, FakeGraphStore, NetworkXGraphStore
- **Integration Tests**: ScanPipeline with real graphs
- **MCP Tests**: Tool invocation with dependency injection
- **Fixtures**: Session-scoped fixture_graph.pkl with 15+ languages

### Test Strategy for Multi-Graph
```python
# Create separate fixture graphs
@pytest.fixture
def graph1_path(tmp_path):
    return tmp_path / "graph1.pickle"

@pytest.fixture
def graph2_path(tmp_path):
    return tmp_path / "graph2.pickle"

# Test graph switching
def test_list_graphs_returns_all_configured():
    config = FakeConfigurationService(...)
    # Add OtherGraphsConfig with multiple graphs
    service = GraphService(config)
    graphs = service.list_graphs()
    assert len(graphs) == 2
```

### Known Issues & Technical Debt
- **No graph caching**: Each load creates fresh instance (acceptable for CLI, slow for MCP)
- **No format migration**: Version check warns but doesn't migrate
- **Single graph assumption**: MCP singletons assume one graph

---

## Modification Considerations

### Safe to Modify

1. **Add OtherGraphsConfig** (`src/fs2/config/objects.py`):
   - Well-tested pattern exists
   - Add to YAML_CONFIG_TYPES registry
   - Follow GraphConfig pattern

2. **Extend CLIContext** (`src/fs2/cli/main.py`):
   - Simple dataclass addition
   - No downstream impact

3. **Add list_graphs MCP tool** (`src/fs2/mcp/server.py`):
   - Follow existing tool patterns
   - Read-only operation

### Modify with Caution

1. **MCP dependencies.py**:
   - Risk: Thread safety, singleton lifecycle
   - Mitigation: Create GraphService that manages cache

2. **All command composition roots**:
   - Risk: 6+ files need consistent changes
   - Mitigation: Extract shared resolution logic

### Danger Zones

1. **NetworkXGraphStore internals**:
   - Many tests depend on current behavior
   - Alternative: Add caching layer above it

2. **GraphConfig schema**:
   - Don't add multiple paths here
   - Alternative: Separate OtherGraphsConfig

---

## Proposed Implementation

### 1. New Config Model (`src/fs2/config/objects.py`)

```python
class OtherGraph(BaseModel):
    """Configuration for a single external graph."""
    name: str = Field(..., description="Unique name for this graph")
    path: str = Field(..., description="Path to graph file (absolute, ~, or relative)")
    description: str | None = Field(None, description="Human-readable description")
    source_url: str | None = Field(None, description="GitHub URL or download location")

class OtherGraphsConfig(BaseModel):
    """Configuration for additional external graphs."""
    __config_path__: ClassVar[str] = "other_graphs"
    graphs: list[OtherGraph] = Field(default_factory=list)
```

**YAML Example:**
```yaml
other_graphs:
  graphs:
    - name: flowspace-original
      path: ~/projects/flowspace/.fs2/graph.pickle
      description: "Original Flowspace for reference"
      source_url: https://github.com/org/flowspace
    - name: shared-lib
      path: ../shared-library/.fs2/graph.pickle
      description: "Common utilities library"
```

### 2. GraphService for Caching (`src/fs2/core/services/graph_service.py`)

```python
class GraphService:
    """Manages loading and caching of multiple named graphs."""

    def __init__(self, config: ConfigurationService):
        self._config = config
        self._cache: dict[str, tuple[GraphStore, float, int]] = {}  # name → (store, mtime, size)
        self._lock = threading.RLock()

    def get_graph(self, name: str | None = None) -> GraphStore:
        """Get graph by name, using cache with staleness check."""
        with self._lock:
            path = self._resolve_path(name)
            cache_key = str(path)

            if cache_key in self._cache:
                store, cached_mtime, cached_size = self._cache[cache_key]
                stat = path.stat()
                if stat.st_mtime == cached_mtime and stat.st_size == cached_size:
                    return store  # Cache hit

            # Cache miss or stale - reload
            store = NetworkXGraphStore(self._config)
            store.load(path)
            stat = path.stat()
            self._cache[cache_key] = (store, stat.st_mtime, stat.st_size)
            return store

    def list_graphs(self) -> list[GraphInfo]:
        """List all available graphs with status."""
        # Default graph + other_graphs from config
```

### 3. CLI Changes (`src/fs2/cli/main.py`)

```python
@dataclass
class CLIContext:
    graph_file: str | None = None
    graph_name: str | None = None  # NEW

@app.callback()
def main(
    ctx: typer.Context,
    graph_file: Annotated[str | None, typer.Option(...)] = None,
    graph_name: Annotated[str | None, typer.Option(
        help="Name of configured graph from other_graphs section"
    )] = None,
):
    ctx.obj = CLIContext(graph_file=graph_file, graph_name=graph_name)
```

### 4. MCP Tool Changes (`src/fs2/mcp/server.py`)

```python
def list_graphs() -> dict[str, Any]:
    """List all available graphs.

    Returns graph names, paths, descriptions, and availability status.
    """
    service = get_graph_service()
    graphs = service.list_graphs()
    return {"graphs": [g.to_dict() for g in graphs], "count": len(graphs)}

def tree(
    pattern: str = ".",
    graph_name: str | None = None,  # NEW
    # ... other params
) -> dict[str, Any]:
    service = get_graph_service()
    store = service.get_graph(graph_name)
    # ... rest of implementation
```

### 5. Path Resolution Logic

```python
def resolve_graph_path(path_str: str) -> Path:
    """Resolve graph path from config to absolute path.

    Supports:
    - Absolute: /home/user/graph.pickle
    - Tilde: ~/projects/graph.pickle
    - Relative: ../other-project/.fs2/graph.pickle (from CWD)
    """
    path = Path(path_str)
    if path_str.startswith("~"):
        path = path.expanduser()
    return path.resolve()
```

---

## Critical Discoveries

### Critical Finding 01: Config Composition from Multiple Sources
**Impact**: Critical
**Source**: PL-01, PL-02
**What**: Configs are composed from user (~/.config/fs2/) AND project (./.fs2/) with deep merge
**Why It Matters**: `other_graphs` from both sources must be combined, not replaced
**Required Action**: Implement list concatenation in OtherGraphsConfig, not dict merge

### Critical Finding 02: MCP Singleton Lifecycle
**Impact**: Critical
**Source**: PS-04, IC-03
**What**: MCP uses lazy singletons that persist across tool calls
**Why It Matters**: Graph cache must handle multiple graphs and staleness
**Required Action**: Replace `get_graph_store()` singleton with `get_graph_service()` that manages cache

### Critical Finding 03: Path Resolution Timing
**Impact**: High
**Source**: PL-05, PL-04
**What**: Relative paths resolved from CWD at service execution time
**Why It Matters**: MCP server CWD may differ from user expectation
**Required Action**: Document that relative paths in `other_graphs` are relative to MCP server CWD

### Critical Finding 04: Scan is Intentionally Not Exposed
**Impact**: High
**Source**: PS-11
**What**: MCP spec explicitly excludes scan functionality
**Why It Matters**: `list_graphs` should show unavailable graphs gracefully, not offer to scan them
**Required Action**: Return `available: false` status for missing graph files

---

## Detailed Findings by Category

### Configuration System (IA Findings)

#### IA-01: Configuration Service Pattern - Typed Object Registry
**Location**: `src/fs2/config/service.py:34-77` (ABC), `80-177` (Production)

- `ConfigurationService` is an abstract base class implementing a typed object registry pattern
- Services store and retrieve config objects by type using `set(config)`, `get(ConfigType)`, and `require(ConfigType)`
- No singleton - explicit construction via dependency injection in each command's composition root

```python
config = FS2ConfigurationService()  # Loads YAML/env on construction
azure = config.require(AzureOpenAIConfig)  # Raises if missing
graph_cfg = config.get(GraphConfig)  # Returns None if missing
```

#### IA-02: Multi-Stage Configuration Loading Pipeline
**Location**: `src/fs2/config/service.py:96-122`

Loading stages (executed in order):
1. Load secrets into environment (`load_secrets_to_env()`)
2. Build raw config dict from YAML files (user → project)
3. Expand ${VAR} placeholders
4. Create typed config objects

**Precedence** (highest to lowest):
1. Environment variables (`FS2_AZURE__OPENAI__TIMEOUT=120`)
2. Project YAML (`.fs2/config.yaml`)
3. User YAML (`~/.config/fs2/config.yaml`)
4. Default values in model definitions

#### IA-03: Config Objects Registry - YAML_CONFIG_TYPES
**Location**: `src/fs2/config/objects.py:809-823`

A list of all Pydantic BaseModel subclasses that should be auto-loaded from YAML/environment:
```python
YAML_CONFIG_TYPES = [
    AzureOpenAIConfig,           # Path: "azure.openai"
    ScanConfig,                  # Path: "scan"
    GraphConfig,                 # Path: "graph"
    LLMConfig,                   # Path: "llm"
    EmbeddingConfig,             # Path: "embedding"
    # ... more config types
]
```

**For multi-graph**: Add `OtherGraphsConfig` to this list with `__config_path__ = "other_graphs"`

#### IA-04: GraphConfig - The Central Graph Path Configuration
**Location**: `src/fs2/config/objects.py:176-197`

```python
class GraphConfig(BaseModel):
    __config_path__: ClassVar[str] = "graph"
    graph_path: str = ".fs2/graph.pickle"
```

### CLI Architecture (DC Findings)

#### DC-01: Typer App Structure with Global Options via Callback
**Location**: `src/fs2/cli/main.py:48-78`

```python
@app.callback()
def main(
    ctx: typer.Context,
    graph_file: Annotated[str | None, typer.Option(...)] = None,
    version: Annotated[bool | None, typer.Option(...)] = None,
) -> None:
    ctx.obj = CLIContext(graph_file=graph_file)
```

#### DC-02: CLIContext - The Global Options Carrier
**Location**: `src/fs2/cli/main.py:34-38`

```python
@dataclass
class CLIContext:
    """Context object for passing global options to subcommands."""
    graph_file: str | None = None
```

To add `--graph-name`, simply add a field here.

#### DC-06: Pattern for Adding --graph-name Global Option

**Step 1** - Update `CLIContext`:
```python
@dataclass
class CLIContext:
    graph_file: str | None = None
    graph_name: str | None = None  # New field
```

**Step 2** - Add to `main()` callback:
```python
@app.callback()
def main(
    ctx: typer.Context,
    graph_file: Annotated[str | None, typer.Option(...)] = None,
    graph_name: Annotated[str | None, typer.Option(...)] = None,  # New
):
    ctx.obj = CLIContext(graph_file=graph_file, graph_name=graph_name)
```

### MCP Server (PS Findings)

#### PS-02: FastMCP Tool Registration Pattern
**Location**: `src/fs2/mcp/server.py:416-427`

```python
_tree_tool = mcp.tool(
    annotations={
        "title": "Explore Code Tree",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)(tree)
```

#### PS-04: Dependency Injection via Lazy Singletons
**Location**: `src/fs2/mcp/dependencies.py:44-105`

```python
_config: ConfigurationService | None = None
_graph_store: GraphStore | None = None
_lock = threading.RLock()

def get_graph_store() -> GraphStore:
    global _graph_store
    with _lock:
        if _graph_store is None:
            _graph_store = NetworkXGraphStore(get_config())
    return _graph_store
```

#### PS-11: Scan is Intentionally Hidden from MCP
**Location**: `src/fs2/cli/main.py:82`

Scan is registered as a CLI command but NOT exposed to MCP (per spec). The MCP spec explicitly states: "Not exposing scan functionality - Agents cannot trigger indexing; they consume pre-indexed graphs."

### Graph Storage (QT Findings)

#### QT-01: GraphStore ABC Interface
**Location**: `src/fs2/core/repos/graph_store.py:21-180`

Key methods:
- `add_node(node: CodeNode)` - Upsert behavior
- `get_node(node_id)` - O(1) lookup
- `save(path)` / `load(path)` - Pickle persistence
- `get_metadata()` - Format version and stats

#### QT-03: Pickle Security - RestrictedUnpickler
**Location**: `src/fs2/core/repos/graph_store_impl.py:55-94`

```python
class RestrictedUnpickler(pickle.Unpickler):
    ALLOWED_MODULES = frozenset({
        "builtins", "collections", "datetime", "pathlib",
        "networkx", "networkx.classes.digraph",
        "fs2.core.models.code_node",
        "fs2.core.models.content_type",
    })
```

#### QT-06: Fixture Graph Loading - FixtureIndex Caching
**Location**: `tests/conftest.py:453-604`

Tests use session-scoped fixture graph with FixtureIndex providing O(1) lookup caching.

### Service Layer (IC Findings)

#### IC-01: Service Constructor Pattern
**Location**: `src/fs2/core/services/tree_service.py:110-127`

Services receive `ConfigurationService` (the registry), NOT pre-extracted config objects:

```python
def __init__(
    self,
    config: ConfigurationService,
    graph_store: GraphStore,
) -> None:
    self._config = config.require(GraphConfig)
    self._graph_store = graph_store
```

#### IC-10: Multi-Graph Service Architecture - Extensibility
**Location**: `src/fs2/mcp/dependencies.py:44-105`

The architecture supports multiple graphs via composition:

```python
class GraphService:
    """Manages multiple named graphs."""
    def __init__(self, config: ConfigurationService):
        self._config = config
        self._graphs: dict[str, GraphStore] = {}

    def get_or_create_graph(self, graph_name: str) -> GraphStore:
        # Create/cache graph stores by name
```

### Test Patterns (DE Findings)

#### DE-01: Multi-Layer Fixture Architecture
**Location**: `tests/conftest.py:152-259`

- **Session-scoped**: Load expensive resources once
- **Function-scoped wrappers**: Reset state per test

#### DE-04: TreeService Compatibility - Empty Graph File Requirement
**Location**: `tests/mcp_tests/conftest.py:182-252`

`TreeService._ensure_loaded()` checks `Path.exists()` BEFORE calling `load()`. Solution:
```python
graph_path = tmp_path / "graph.pickle"
graph_path.touch()  # Create 0-byte file to satisfy existence check
```

### Config Composition (PL Findings)

#### PL-01: Two-Tier Config File Loading
**Location**: `src/fs2/config/service.py:96-121`

- User config (`~/.config/fs2/config.yaml`): Lowest priority
- Project config (`./.fs2/config.yaml`): Overrides user config

Uses `deep_merge()` to preserve non-overridden fields.

#### PL-07: Leaf-Level Override Behavior
**Location**: `tests/unit/config/test_config_precedence.py:196-230`

When merging config from multiple sources, only specified fields are overridden; sibling fields from lower-priority sources are preserved.

---

## Recommendations

### If Implementing This Feature

1. **Start with config model**: Add `OtherGraphsConfig` following existing pattern
2. **Create GraphService**: Centralized caching with staleness detection
3. **Update MCP dependencies first**: Replace singleton with service
4. **Add list_graphs tool**: Read-only, safe starting point
5. **Update existing tools incrementally**: Add `graph_name` parameter one by one
6. **CLI last**: Less critical since stateless anyway

### Testing Strategy

1. Use `tests/fixtures/fixture_graph.pkl` as one test graph
2. Create second test graph from `tests/fixtures/ast_samples/`
3. Test config composition from user + project configs
4. Test path resolution (absolute, tilde, relative)
5. Test cache invalidation on file change

### Extension Points

1. **Graph metadata in list_graphs**: Include node_count, last_modified from pickle metadata
2. **Graph aliasing**: Allow `--graph-name local` as shorthand for default graph
3. **Graph discovery**: Future: scan for `.fs2/graph.pickle` in sibling directories

---

## File Inventory

### Files to Create
| File | Purpose |
|------|---------|
| `src/fs2/core/services/graph_service.py` | Graph loading, caching, listing |
| `tests/unit/services/test_graph_service.py` | Unit tests for new service |

### Files to Modify
| File | Changes |
|------|---------|
| `src/fs2/config/objects.py` | Add OtherGraph, OtherGraphsConfig |
| `src/fs2/cli/main.py` | Add graph_name to CLIContext and callback |
| `src/fs2/cli/tree.py` | Use graph_name in composition root |
| `src/fs2/cli/search.py` | Use graph_name in composition root |
| `src/fs2/cli/get_node.py` | Use graph_name in composition root |
| `src/fs2/mcp/dependencies.py` | Add get_graph_service(), update get_graph_store() |
| `src/fs2/mcp/server.py` | Add list_graphs tool, add graph_name to existing tools |

### Test Fixtures Available
| Location | Purpose |
|----------|---------|
| `tests/fixtures/fixture_graph.pkl` | Pre-computed graph with embeddings |
| `tests/fixtures/samples/` | 15+ language samples |
| `tests/fixtures/ast_samples/` | Additional Python samples |
| `scratch/flowspace/graph.pickle` | Original Flowspace graph (manual testing only) |

---

## Next Steps

1. **Run `/plan-1b-specify`** to create a formal feature specification from these findings
2. **Or `/plan-2-clarify`** if there are ambiguities to resolve first
3. **Then `/plan-3-architect`** to create implementation plan

Key decisions to make during specification:
- Exact config schema for `other_graphs` section
- Whether `--graph-name` should be mutually exclusive with `--graph-file`
- How to handle graphs that are configured but file is missing
- Whether to support graph aliases (e.g., "local" for default graph)

---

**Research Complete**: 2026-01-12T23:15:00Z
**Report Location**: `docs/plans/023-multi-graphs/research-dossier.md`
