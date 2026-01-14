# Research Dossier: LSP Integration for Cross-File Relationships

**Generated**: 2026-01-14
**Research Query**: LSP integration for cross-file semantic relationships in fs2
**FlowSpace**: Available ✅
**Findings**: 75 total (IA:10, DC:10, PS:10, QT:10, IC:10, DE:10, PL:15)

---

## Executive Summary

### What It Does
LSP integration would enable high-confidence cross-file relationship extraction by leveraging language servers' semantic understanding—resolving method calls, finding references, and navigating type hierarchies that Tree-sitter alone cannot achieve.

### Business Purpose
Enhance fs2's code graph with semantically-verified relationships (confidence 0.9-1.0) for method calls, type implementations, and symbol references. This complements the validated Tree-sitter baseline (imports at 100% accuracy) with LSP's compiler-level precision for dynamic code navigation.

### Key Insights
1. **Hybrid architecture is optimal**: Tree-sitter baseline + optional LSP "boost" for supported languages
2. **Clean Architecture adapter pattern fits perfectly**: ABC-based `LspAdapter` with thin per-language implementations
3. **CodeEdge/EdgeType models are ready**: Foundation exists (committed f53e8c5), LSP results map directly to CodeEdge

### Quick Stats
- **Prior Work**: 022-cross-file-rels validated Tree-sitter (100% import accuracy)
- **Models Ready**: CodeEdge, EdgeType, GraphStore extensions implemented
- **LSP Coverage**: All target languages have mature servers (Pyright, gopls, OmniSharp, TypeScript LS)
- **Complexity**: CS-3 (Medium) - adapter pattern is well-established
- **Prior Learnings**: 15 relevant discoveries from previous implementations

---

## Completed Foundation Work (024-cross-file-impl Phase 1)

> **IMPORTANT**: Phase 1 of 024-cross-file-impl is **COMPLETE** with 56 tests passing.
> The remaining phases (2-6) of that plan used an alternate Tree-sitter-only approach
> and will be **SKIPPED** in favor of this LSP-based approach. Do NOT duplicate this work.

### What Was Delivered

Phase 1 established the complete infrastructure for cross-file relationship storage:

| Deliverable | Status | Tests |
|-------------|--------|-------|
| EdgeType enum (4 relationship types) | ✅ Complete | 12 tests |
| CodeEdge frozen dataclass | ✅ Complete | 15 tests |
| GraphStore ABC extensions | ✅ Complete | 2 tests |
| NetworkXGraphStore implementation | ✅ Complete | 11 tests |
| FakeGraphStore implementation | ✅ Complete | 16 tests |
| PipelineContext.relationships field | ✅ Complete | - |
| RestrictedUnpickler whitelist | ✅ Complete | - |
| Model exports in `__init__.py` | ✅ Complete | - |

**Total: 56 tests passing**

### EdgeType Enum (COMPLETE)

**File**: `src/fs2/core/models/edge_type.py` (55 lines)

```python
class EdgeType(str, Enum):
    """Edge type for cross-file relationship classification."""

    IMPORTS = "imports"      # Import dependency: source file imports from target
    CALLS = "calls"          # Call relationship: source calls target function/method
    REFERENCES = "references" # Explicit reference: source contains target's node_id
    DOCUMENTS = "documents"   # Documentation link: source doc mentions target code
```

**Key Features**:
- Inherits from `str` for JSON/pickle serialization
- String equality: `EdgeType.IMPORTS == "imports"` → `True`
- Pickle-safe (whitelisted in RestrictedUnpickler)

### CodeEdge Frozen Dataclass (COMPLETE)

**File**: `src/fs2/core/models/code_edge.py` (84 lines)

```python
@dataclass(frozen=True)
class CodeEdge:
    source_node_id: str           # Origin (e.g., "file:src/app.py")
    target_node_id: str           # Destination (e.g., "file:src/auth.py")
    edge_type: EdgeType           # Relationship type (IMPORTS, CALLS, etc.)
    confidence: float             # Certainty score 0.0-1.0
    source_line: int | None = None  # Line number for navigation
    resolution_rule: str = "unknown"  # How relationship was determined

    def __post_init__(self) -> None:
        # Validates EdgeType is enum (not string)
        # Validates confidence in 0.0-1.0 range
```

**Key Features**:
- Frozen (immutable) for thread safety
- `__post_init__` validation rejects invalid confidence/edge_type
- Pickle-safe (whitelisted in RestrictedUnpickler)

### GraphStore Extensions (COMPLETE)

**File**: `src/fs2/core/repos/graph_store.py` (added ~50 lines)

```python
# Abstract methods added to GraphStore ABC:

@abstractmethod
def add_relationship_edge(self, edge: "CodeEdge") -> None:
    """Add a relationship edge between two nodes.
    Edge direction: source → target (X imports Y = edge X→Y).
    """
    ...

@abstractmethod
def get_relationships(
    self,
    node_id: str,
    direction: str = "both",  # "outgoing" | "incoming" | "both"
) -> list[dict]:
    """Get relationship edges for a node.
    Returns: List of dicts with keys: node_id, edge_type, confidence, source_line
    """
    ...
```

### NetworkXGraphStore Implementation (COMPLETE)

**File**: `src/fs2/core/repos/graph_store_impl.py` (added ~70 lines)

```python
def add_relationship_edge(self, edge: "CodeEdge") -> None:
    self._graph.add_edge(
        edge.source_node_id,
        edge.target_node_id,
        is_relationship=True,  # Discriminator from parent-child edges
        edge_type=str(edge.edge_type),
        confidence=edge.confidence,
        source_line=edge.source_line,
        resolution_rule=edge.resolution_rule,
    )

def get_relationships(self, node_id: str, direction: str = "both") -> list[dict]:
    # Uses out_edges() for outgoing, in_edges() for incoming
    # Filters by is_relationship=True attribute
    # Returns empty list for unknown nodes (graceful)
```

### FakeGraphStore Implementation (COMPLETE)

**File**: `src/fs2/core/repos/graph_store_fake.py` (added ~90 lines)

```python
# Data structure (per Critical Discovery from execution):
self._relationship_edges: dict[tuple[str, str], dict] = {}
# Key: (source_node_id, target_node_id)
# Value: {edge_type, confidence, source_line, resolution_rule}

# Both methods implemented with:
# - call_history tracking
# - simulate_error_for support
# - Same interface as NetworkXGraphStore
```

### PipelineContext Extension (COMPLETE)

**File**: `src/fs2/core/services/pipeline_context.py` (added 1 field)

```python
# Added field for cross-file relationships:
relationships: "list[CodeEdge] | None" = None
# Populated by relationship extraction stage, consumed by storage stage
```

### RestrictedUnpickler Whitelist (COMPLETE)

**File**: `src/fs2/core/repos/graph_store_impl.py` (updated whitelist)

```python
ALLOWED_MODULES = frozenset({
    # ... existing modules ...
    "fs2.core.models.edge_type",   # ← Added
    "fs2.core.models.code_edge",   # ← Added
})
```

### How to Use (Ready Now)

```python
from fs2.core.models import EdgeType, CodeEdge

# Create a relationship edge
edge = CodeEdge(
    source_node_id="file:src/app.py",
    target_node_id="file:src/auth.py",
    edge_type=EdgeType.IMPORTS,
    confidence=0.9,
    source_line=5,
    resolution_rule="lsp:textDocument/references",
)

# Store in graph
graph_store.add_relationship_edge(edge)

# Query relationships
outgoing = graph_store.get_relationships("file:src/app.py", direction="outgoing")
incoming = graph_store.get_relationships("file:src/auth.py", direction="incoming")
```

### Test Verification Commands

```bash
# Run Phase 1 tests (56 tests)
pytest tests/unit/models/test_edge_type.py \
       tests/unit/models/test_code_edge.py \
       tests/unit/repos/test_graph_store.py -v

# Verify imports work
python -c "from fs2.core.models import EdgeType, CodeEdge; print(list(EdgeType))"
```

### What This Means for LSP Integration

**DO NOT recreate**:
- ❌ EdgeType enum - already exists
- ❌ CodeEdge model - already exists
- ❌ GraphStore.add_relationship_edge() - already exists
- ❌ GraphStore.get_relationships() - already exists
- ❌ FakeGraphStore relationship support - already exists

**LSP integration only needs to**:
- ✅ Create LspAdapter ABC and implementations
- ✅ Convert LSP responses to CodeEdge instances
- ✅ Call `graph_store.add_relationship_edge(edge)` for each relationship found

---

## How It Currently Works

### Entry Points for Cross-File Relationships
| Entry Point | Type | Location | Purpose |
|-------------|------|----------|---------|
| `ScanPipeline` | Service | `src/fs2/core/services/scan_pipeline.py` | Orchestrates scanning |
| `ASTParser` | Adapter | `src/fs2/core/adapters/ast_parser.py` | Tree-sitter extraction |
| `GraphStore.add_relationship_edge()` | Repository | `src/fs2/core/repos/graph_store.py` | Edge persistence |

### Current Extraction Flow (Tree-sitter Only)
1. **ScanPipeline** discovers files in workspace
2. **ASTParser** parses each file with Tree-sitter
3. Import statements extracted via language-specific queries
4. **CodeEdge** instances created with confidence scoring
5. Edges stored in **NetworkXGraphStore** as edge attributes

### What Tree-sitter Can Do (Validated in 022)
| Capability | Accuracy | Confidence |
|------------|----------|------------|
| File-to-file imports | 100% | 0.9-0.95 |
| Node ID patterns in text | 100% | 1.0 |
| Raw filename heuristics | ~80% | 0.4-0.5 |
| Constructor calls (`AuthHandler()`) | ~70% | 0.5-0.8 |

### What Tree-sitter Cannot Do (LSP Needed)
| Capability | Tree-sitter | LSP |
|------------|-------------|-----|
| Method calls on typed receivers (`self.auth.validate()`) | ❌ Low confidence | ✅ 0.9+ |
| Find all references to a symbol | ❌ Not possible | ✅ Native |
| Navigate to definition across files | ❌ Not possible | ✅ Native |
| Resolve type inheritance chains | ❌ Not possible | ✅ Partial |

---

## LSP Feature Support Matrix

Based on external research (external-research-1.md):

| Language | Server | Definition | References | Implementation | Workspace Symbol |
|----------|--------|------------|-----------|----------------|------------------|
| **Python** | Pyright | ✅ | ✅ | ❌ | ✅ |
| **TypeScript/JS** | TypeScript LS | ✅ | ✅ | ✅ | ✅ |
| **Go** | gopls | ✅ | ✅ | ✅ | ✅ |
| **C#** | OmniSharp | ✅ | ✅ | ✅ | ✅ |
| **Java** | JDT LS | ✅ | ✅ | ✅ | ✅ |
| **C++** | Clangd | ✅ | ✅ | Partial | ✅ |
| **Rust** | rust-analyzer | ✅ | ✅ | ✅ | ✅ |
| **Ruby** | Solargraph | ⚠️ Best-effort | ⚠️ Best-effort | ❌ | ✅ |
| **GDScript** | Godot LSP | ✅ | ✅ (v4.2+) | N/A | Limited |

**Initial Target Languages**: Python, TypeScript/JS, Go, C# (all have strong LSP support)

---

## Proposed Architecture

### Design Principle: Thin Wrappers, Maximum Reuse

```
┌─────────────────────────────────────────────────────────────────┐
│                      LspAdapter (ABC)                            │
│  - initialize() → ServerCapabilities                             │
│  - shutdown()                                                    │
│  - get_definition(file, line, col) → Location?                  │
│  - get_references(file, line, col) → list[Location]             │
│  - get_document_symbols(file) → list[SymbolInformation]         │
│  - provider_name → str                                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
    ┌────────────────────┼────────────────────┐
    │                    │                    │
    ▼                    ▼                    ▼
┌──────────┐      ┌──────────┐        ┌──────────┐
│ Pyright  │      │  gopls   │        │OmniSharp │
│ Adapter  │      │ Adapter  │        │ Adapter  │
└──────────┘      └──────────┘        └──────────┘
```

### Per-Language Configuration (Thin Wrapper Pattern)

From external-research-2.md, each language needs only a configuration dataclass:

```python
@dataclass(frozen=True)
class LspServerConfig:
    """Thin wrapper: how to launch server + minimal per-language config."""
    name: str                          # "pyright", "gopls", "omnisharp"
    command: list[str]                 # ["pyright-langserver", "--stdio"]
    language_id: str                   # "python", "go", "csharp"
    initialization_options: dict = field(default_factory=dict)
    settings: dict = field(default_factory=dict)
    file_extensions: list[str] = field(default_factory=list)  # [".py"]
```

### Adding a New Language (Elegant & Easy)

To add support for a new language, developer creates ONE configuration:

```python
# In lsp_server_configs.py
LSP_CONFIGS = {
    "python": LspServerConfig(
        name="pyright",
        command=["pyright-langserver", "--stdio"],
        language_id="python",
        file_extensions=[".py", ".pyi"],
        settings={"python.analysis.autoSearchPaths": True},
    ),
    "go": LspServerConfig(
        name="gopls",
        command=["gopls"],
        language_id="go",
        file_extensions=[".go"],
    ),
    "csharp": LspServerConfig(
        name="omnisharp",
        command=["OmniSharp", "-lsp"],
        language_id="csharp",
        file_extensions=[".cs"],
    ),
    "typescript": LspServerConfig(
        name="typescript-language-server",
        command=["typescript-language-server", "--stdio"],
        language_id="typescript",
        file_extensions=[".ts", ".tsx", ".js", ".jsx"],
    ),
}
```

**That's it.** No per-language adapter code needed for standard LSP features.

### Generic LSP Client (From Reference Implementation)

The generic `LspClient` class handles:
- JSON-RPC over stdio (spawn subprocess)
- Request/response correlation
- Server lifecycle (initialize/shutdown)
- Standard LSP requests (definition, references, symbols)

```python
class LspClient:
    """Generic LSP client - works with any compliant server."""

    def __init__(self, config: LspServerConfig, workspace_root: Path):
        self.config = config
        self.root = workspace_root
        self._proc: subprocess.Popen | None = None

    async def initialize(self) -> dict:
        """Standard LSP initialize handshake."""
        return await self.request("initialize", {
            "rootUri": self.root.as_uri(),
            "capabilities": {...},
        })

    async def get_references(self, file: Path, line: int, col: int) -> list[dict]:
        """textDocument/references - uniform across all servers."""
        return await self.request("textDocument/references", {
            "textDocument": {"uri": file.as_uri()},
            "position": {"line": line, "character": col},
        })
```

---

## Mapping LSP Results to CodeEdge

### LSP Request → CodeEdge Mapping

| LSP Request | EdgeType | Confidence | Example |
|-------------|----------|------------|---------|
| `textDocument/definition` | REFERENCES | 1.0 | Jump to where symbol is defined |
| `textDocument/references` | REFERENCES | 0.9 | All usages of a symbol |
| `textDocument/implementation` | CALLS | 0.9 | Classes implementing interface |
| Import extraction (Tree-sitter) | IMPORTS | 0.95 | Import statements |

### Conversion Function

```python
def lsp_location_to_edge(
    source_node_id: str,
    lsp_location: dict,
    edge_type: EdgeType,
    resolution_rule: str,
) -> CodeEdge:
    """Convert LSP Location to CodeEdge."""
    target_file = uri_to_path(lsp_location["uri"])
    target_node_id = f"file:{target_file}"  # Or resolve to symbol

    return CodeEdge(
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        edge_type=edge_type,
        confidence=0.9,  # LSP = high confidence
        source_line=lsp_location["range"]["start"]["line"],
        resolution_rule=resolution_rule,
    )
```

---

## File Structure (Following fs2 Conventions)

```
src/fs2/core/adapters/
├── lsp_adapter.py                    # ABC definition
├── lsp_adapter_generic.py            # Generic LSP client implementation
├── lsp_adapter_fake.py               # Test double with call_history
├── lsp_server_configs.py             # Per-language LspServerConfig registry
└── exceptions.py                     # Add LspAdapterError hierarchy

src/fs2/config/
└── lsp_config.py                     # LspConfig pydantic model

tests/unit/adapters/
├── test_lsp_adapter.py               # ABC contract tests
├── test_lsp_adapter_generic.py       # Generic client tests
└── test_lsp_adapter_fake.py          # Fake behavior tests

tests/integration/
└── test_lsp_integration.py           # Real server tests (Python, Go)
```

---

## Prior Learnings (Critical for Implementation)

### 📚 PL-01: STDIO Protocol Requires Strict Stdout Isolation
**Source**: 011-mcp Phase 1
**What They Found**: Any stdout during import breaks JSON-RPC communication.
**Action**: Configure stderr-only logging BEFORE importing any LSP libraries.

### 📚 PL-02: Lazy Service Initialization Enables Fast Startup
**Source**: 011-mcp Phase 1
**What They Found**: Services should be created on first access.
**Action**: Initialize LSP servers lazily on first semantic query, not at startup.

### 📚 PL-03: Version Pinning Prevents Silent Breakage
**Source**: 022-cross-file-rels Phase 1
**What They Found**: Unpinned dependencies can break mid-experiment.
**Action**: Pin LSP server versions and document tested configurations.

### 📚 PL-04: Non-Code Files Have Extractable Semantic References
**Source**: 022-cross-file-rels Phase 1
**What They Found**: Markdown, YAML, Dockerfile have cross-file references.
**Action**: LSP is code-only; keep Tree-sitter for documentation relationships.

### 📚 PL-05: Error Translation Requires Actionable Guidance
**Source**: 011-mcp Phase 1
**What They Found**: Domain exceptions must translate to agent-friendly responses.
**Action**: Create `LspErrorTranslator` mapping server errors to recovery actions.

### 📚 PL-06: Protocol-Level Testing Is Essential
**Source**: 011-mcp Phase 2
**What They Found**: Testing Python functions directly doesn't test JSON serialization.
**Action**: Create `lsp_client` fixture that sends actual JSON-RPC requests.

### 📚 PL-07: Filesystem Checks Require Real Files
**Source**: 011-mcp Phase 2
**What They Found**: Services check file existence before using fakes.
**Action**: Create temp files for workspace paths in tests.

### 📚 PL-08: Detail Levels Must Always Include Node IDs
**Source**: 011-mcp Phase 2
**What They Found**: Agents always need node_id/location for navigation.
**Action**: Always include file path + line/column in LSP responses.

### 📚 PL-09: Use Native Protocol Error Handling
**Source**: 011-mcp Phase 2
**What They Found**: Return JSON-RPC errors, not error data in success responses.
**Action**: Use LSP error codes (-32600, -32700, etc.) for failures.

### 📚 PL-10: Decorator-Based Handler Registration Is Cleaner
**Source**: 011-mcp Phase 2
**What They Found**: `@mcp.tool()` pattern is cleaner than explicit lists.
**Action**: Use `@server.feature()` decorators for LSP handlers.

### 📚 PL-11: Use Fakes, Not Mocks
**Source**: 011-mcp Phase 2
**What They Found**: Fakes inherit from ABCs; mocks don't catch interface changes.
**Action**: Create `FakeLspAdapter` inheriting from `LspAdapter` ABC.

### 📚 PL-12: Language Server Consistency Varies
**Source**: 025-lsp-research
**What They Found**: Pyright lacks implementation queries; servers need specific configuration.
**Action**: Check server capabilities; fall back gracefully for unsupported features.

### 📚 PL-13: Cross-File Relationships Need Ground Truth
**Source**: 022-cross-file-rels Phase 1
**What They Found**: Validation requires known-correct relationship data.
**Action**: Create test fixtures with documented expected relationships.

### 📚 PL-14: Adapter Pattern Enables Language-Agnostic Integration
**Source**: 002-project-skele
**What They Found**: ABC-based adapters decouple fs2 from implementations.
**Action**: Create `LspAdapter` ABC; implementations are thin wrappers.

### 📚 PL-15: Execution Logs Are Gold
**Source**: 011-mcp Phase 1
**What They Found**: Detailed logs capture discoveries and gotchas.
**Action**: Document LSP server versions, quirks, and workarounds in execution logs.

---

## Modification Considerations

### ✅ Safe to Modify
1. **Add new adapter files** (`lsp_adapter.py`, etc.) - isolated addition
2. **Extend GraphStore** - `add_relationship_edge()` already defined
3. **Add LspConfig** - follows existing pydantic config pattern

### ⚠️ Modify with Caution
1. **ScanPipeline integration** - must be backward compatible
2. **CLI options** - `--with-lsp` flag needs careful design

### 🚫 Danger Zones
1. **Don't make LSP required** - must remain optional enhancement
2. **Don't leak LSP types into services** - use domain types only
3. **Don't hardcode server paths** - use configuration

---

## Recommended Implementation Phases

> **Note**: Foundation work (CodeEdge, EdgeType, GraphStore) is **ALREADY COMPLETE** from 024 Phase 1.
> These phases focus only on the LSP adapter layer.

### Phase 1: LSP Adapter Foundation ← START HERE
- Create `LspAdapter` ABC following fs2 patterns
- Create `LspServerConfig` frozen dataclass (thin wrapper pattern)
- Create `FakeLspAdapter` for testing (with call_history)
- Add `LspAdapterError` hierarchy to exceptions.py

### Phase 2: Generic LSP Client
- Implement `GenericLspClient` (stdio JSON-RPC)
- Port reference implementation from external-research-2.md
- Add async request/response handling
- Implement server lifecycle management (initialize/shutdown)

### Phase 3: Python Integration (First Language)
- Add Pyright configuration to `LSP_CONFIGS`
- Implement `get_references()` → CodeEdge conversion
- Integration tests with real Pyright server
- Validate against ground truth fixtures

### Phase 4: Multi-Language Expansion
- Add gopls (Go), OmniSharp (C#), TypeScript LS configs
- Test across all 4 initial languages
- Document per-language setup requirements

### Phase 5: Pipeline Integration
- Add `--with-lsp` flag to `fs2 scan`
- Lazy LSP initialization on first supported file
- Performance benchmarking
- Integration with existing `PipelineContext.relationships`

---

## Critical Discoveries from Subagent Research

### Finding IA-01: Manual Tree-Sitter Approach Achieved 100% Accuracy
The 022 experimentation phase validated Tree-sitter-based import detection with perfect accuracy (100% precision and recall) for Python and TypeScript. This establishes the baseline that LSP should enhance, not replace.

### Finding IA-10: Cross-File Method Calls Require Type Inference or LSP
Tree-sitter alone cannot resolve method calls on typed receivers (e.g., `self.auth.validate_token()`) without type inference. This is the strongest case for LSP integration—LSP servers have built-in type inference.

### Finding DC-01: Adapter ABC Base Pattern
Every fs2 adapter defines an ABC with `@abstractmethod` decorators. The ABC lives in `{name}_adapter.py`, implementations in `{name}_adapter_{impl}.py`. LSP adapters must follow this pattern.

### Finding DC-06: Factory Function Pattern for Adapter Creation
Adapters provide factory functions like `create_embedding_adapter_from_config(config)`. LSP should have `create_lsp_adapter_from_config(config, language)`.

### Finding PS-04: Exception Translation at Adapter Boundary
Adapters catch SDK exceptions and translate to domain exceptions. LSP must translate JSON-RPC errors to `LspAdapterError` hierarchy.

### Finding IC-01: CodeEdge Frozen Dataclass Ready
The CodeEdge model is implemented with validation, ready for LSP results:
```python
@dataclass(frozen=True)
class CodeEdge:
    source_node_id: str
    target_node_id: str
    edge_type: EdgeType
    confidence: float  # 0.0-1.0
    source_line: int | None = None
    resolution_rule: str = "unknown"
```

### Finding DE-05: Avoid Flowspace SCIP Mistake
The original Flowspace required external language-specific SCIP indexers. fs2 must NOT repeat this—LSP servers should be optional enhancements, not required infrastructure.

---

## External Research Opportunities

### Research Opportunity 1: LSP Server Binary Distribution

**Why Needed**: How to distribute language server binaries with fs2? Users need Pyright/gopls installed.

**Ready-to-use prompt:**
```
/deepresearch "Best practices for distributing Python applications that depend on external language server binaries (like pyright, gopls, rust-analyzer). Research options including:
1. pip dependencies that install servers (pyright npm package)
2. Optional dependency groups in pyproject.toml
3. Runtime detection and graceful degradation
4. Docker-based LSP servers
5. LSP server version management
Context: fs2 is a pip-installable Python tool. We want LSP features to be optional but easy to enable."
```

### Research Opportunity 2: LSP Session Management for Large Codebases

**Why Needed**: How to efficiently query LSP for thousands of files without overwhelming the server?

**Ready-to-use prompt:**
```
/deepresearch "Strategies for efficiently querying Language Server Protocol servers across large codebases (10,000+ files). Research:
1. Batch request patterns vs individual queries
2. Server-side indexing wait strategies
3. Request throttling and rate limiting
4. Incremental vs full workspace analysis
5. Memory management for long-running LSP sessions
Context: fs2 scans entire repositories to build code graphs. Need to extract references for many symbols without server timeout/memory issues."
```

---

## Appendix: Key Files Inventory

### Core Models (COMPLETE - from 024 Phase 1)
| File | Purpose | Status | Tests |
|------|---------|--------|-------|
| `src/fs2/core/models/code_edge.py` | CodeEdge frozen dataclass | ✅ Complete | 15 |
| `src/fs2/core/models/edge_type.py` | EdgeType enum (IMPORTS, CALLS, REFERENCES, DOCUMENTS) | ✅ Complete | 12 |

### GraphStore (COMPLETE - from 024 Phase 1)
| File | Purpose | Status | Tests |
|------|---------|--------|-------|
| `src/fs2/core/repos/graph_store.py` | ABC with `add_relationship_edge()`, `get_relationships()` | ✅ Complete | 2 |
| `src/fs2/core/repos/graph_store_impl.py` | NetworkX implementation + RestrictedUnpickler whitelist | ✅ Complete | 11 |
| `src/fs2/core/repos/graph_store_fake.py` | Test double with call_history | ✅ Complete | 16 |

### Pipeline (COMPLETE - from 024 Phase 1)
| File | Purpose | Status |
|------|---------|--------|
| `src/fs2/core/services/pipeline_context.py` | `relationships: list[CodeEdge] \| None` field | ✅ Complete |
| `src/fs2/core/models/__init__.py` | Exports EdgeType, CodeEdge | ✅ Complete |

### LSP Adapter (TO CREATE - this plan)
| File | Purpose | Status |
|------|---------|--------|
| `src/fs2/core/adapters/lsp_adapter.py` | ABC definition | 🔲 To create |
| `src/fs2/core/adapters/lsp_adapter_generic.py` | Generic LSP client (stdio JSON-RPC) | 🔲 To create |
| `src/fs2/core/adapters/lsp_server_configs.py` | Per-language LspServerConfig registry | 🔲 To create |
| `src/fs2/core/adapters/lsp_adapter_fake.py` | Test double with call_history | 🔲 To create |
| `src/fs2/core/adapters/exceptions.py` | Add LspAdapterError hierarchy | 🔲 To modify |

### Tests (TO CREATE - this plan)
| File | Purpose | Status |
|------|---------|--------|
| `tests/unit/adapters/test_lsp_adapter.py` | ABC contract tests | 🔲 To create |
| `tests/unit/adapters/test_lsp_adapter_generic.py` | Generic client unit tests | 🔲 To create |
| `tests/unit/adapters/test_lsp_adapter_fake.py` | Fake behavior tests | 🔲 To create |
| `tests/integration/test_lsp_integration.py` | Real server tests (Pyright, gopls) | 🔲 To create |

---

## Conclusion

LSP integration is **highly feasible** and **well-aligned** with fs2's architecture:

1. **Clean Architecture fit**: LSP servers are external tools → adapter pattern is perfect
2. **Thin wrappers work**: Per-language config is ~10 lines; generic client handles protocol
3. **Models are ready**: CodeEdge/EdgeType/GraphStore already support relationship storage
4. **Hybrid approach validated**: Tree-sitter baseline + LSP boost is the optimal architecture

**Recommended next step**: Run `/plan-1b-specify "LSP adapter integration for cross-file relationships"` to create the formal specification.

---

## Subagent Findings Reference

Full findings are available from the research subagents:

- **Implementation Archaeologist (IA-01 to IA-10)**: Existing 022/024 plans, Tree-sitter validation, LSP feasibility
- **Dependency Cartographer (DC-01 to DC-10)**: fs2 adapter architecture patterns
- **Pattern & Convention Scout (PS-01 to PS-10)**: Design patterns (ABC, DI, exceptions)
- **Quality & Testing Investigator (QT-01 to QT-10)**: Testing patterns and fixtures
- **Interface & Contract Analyst (IC-01 to IC-10)**: CodeEdge, EdgeType, GraphStore models
- **Documentation & Evolution Historian (DE-01 to DE-10)**: Documentation and plan evolution
- **Prior Learnings Scout (PL-01 to PL-15)**: Institutional knowledge from previous implementations

---

**Research Complete**: 2026-01-14
