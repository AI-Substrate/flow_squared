# Implementation Strategy: LSP Integration for Cross-File Relationships

**Generated**: 2026-01-14
**Based On**: research-dossier.md, external-research-5-serena-solidlsp.md
**Status**: Implementation-Ready

---

## Implementation Discoveries (I1-01 through I1-10)

### I1-01: Vendoring Scope - Minimal Core + Language Servers

**Discovery**: SolidLSP can be vendored as a focused subset (~8K LOC) rather than full ~25K LOC.

**Key Files to Vendor** (from `/workspaces/flow_squared/scratch/serena/src/solidlsp/`):

| File | LOC | Purpose | Vendor? |
|------|-----|---------|---------|
| `ls.py` | ~2000 | ABC SolidLanguageServer, caching, symbol operations | **YES** (core) |
| `ls_handler.py` | 592 | JSON-RPC client, process management | **YES** (core) |
| `ls_types.py` | 446 | UnifiedSymbolInformation, Location, Range | **YES** (core) |
| `ls_config.py` | 452 | Language enum, file matchers | **PARTIAL** (extract relevant) |
| `ls_request.py` | 384 | Typed LSP request wrappers | **YES** (core) |
| `ls_exceptions.py` | ~50 | SolidLSPException | **YES** (core) |
| `language_servers/common.py` | 165 | RuntimeDependencyCollection | **YES** (dependency mgmt) |
| `settings.py` | ~80 | SolidLSPSettings | **YES** (config) |
| `lsp_protocol_handler/` | ~1000 | Low-level protocol types | **YES** (dependency) |
| `util/` | ~200 | Utility functions | **PARTIAL** |

**Language Server Implementations** (vendor initially):

| File | LOC | Priority |
|------|-----|----------|
| `language_servers/pyright_server.py` | 197 | P1 - Python |
| `language_servers/gopls.py` | 168 | P1 - Go |
| `language_servers/typescript_language_server.py` | 290 | P2 - TypeScript |
| `language_servers/omnisharp.py` | 400 | P3 - C# |

**Total Vendor Estimate**: ~6-8K LOC (not 25K)

**Target Location**: `src/fs2/vendors/solidlsp/`

---

### I1-02: LspAdapter ABC Design Following fs2 Patterns

**Discovery**: LspAdapter should mirror EmbeddingAdapter pattern exactly.

**File**: `src/fs2/core/adapters/lsp_adapter.py` (~150 LOC)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass(frozen=True)
class LspLocation:
    """LSP-agnostic location representation."""
    file_path: str           # Relative path
    line: int                # 0-indexed
    column: int              # 0-indexed
    end_line: int | None = None
    end_column: int | None = None

class LspAdapter(ABC):
    """Abstract base class for Language Server Protocol adapters.

    This interface defines the contract for LSP integration,
    enabling language-agnostic semantic code analysis.

    Implementations:
    - SolidLspAdapter: Production wrapper around vendored SolidLSP
    - FakeLspAdapter: Test double with call_history
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the LSP server name (e.g., 'pyright', 'gopls')."""
        ...

    @property
    @abstractmethod
    def language_id(self) -> str:
        """Return the language identifier (e.g., 'python', 'go')."""
        ...

    @abstractmethod
    def initialize(self, workspace_root: str) -> dict:
        """Initialize the language server for a workspace.

        Returns:
            Server capabilities dict.

        Raises:
            LspAdapterError: If initialization fails.
        """
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Gracefully shutdown the language server."""
        ...

    @abstractmethod
    def get_references(
        self,
        file_path: str,
        line: int,
        column: int
    ) -> list[LspLocation]:
        """Find all references to the symbol at position.

        Args:
            file_path: Relative path to file
            line: 0-indexed line number
            column: 0-indexed column number

        Returns:
            List of locations where symbol is referenced.

        Raises:
            LspAdapterError: For server communication failures.
        """
        ...

    @abstractmethod
    def get_definition(
        self,
        file_path: str,
        line: int,
        column: int
    ) -> list[LspLocation]:
        """Find definition(s) of the symbol at position.

        Returns:
            List of definition locations (usually 1, may be multiple).
        """
        ...
```

**Key Pattern Alignments**:
- `provider_name` property (like EmbeddingAdapter)
- `call_history` in FakeLspAdapter (like FakeEmbeddingAdapter)
- Exception translation at boundary (like EmbeddingAdapterError)

---

### I1-03: SolidLspAdapter Implementation Strategy

**Discovery**: SolidLspAdapter wraps vendored SolidLSP with thin translation layer.

**File**: `src/fs2/core/adapters/lsp_adapter_solid.py` (~350 LOC)

**Key Integration Points**:

```python
from fs2.vendors.solidlsp.ls import SolidLanguageServer
from fs2.vendors.solidlsp.language_servers.pyright_server import PyrightServer
from fs2.vendors.solidlsp.language_servers.gopls import Gopls

class SolidLspAdapter(LspAdapter):
    """Production LSP adapter using vendored SolidLSP."""

    def __init__(
        self,
        server_class: type[SolidLanguageServer],
        workspace_root: str,
        language_id: str,
    ):
        self._server_class = server_class
        self._workspace_root = workspace_root
        self._language_id = language_id
        self._server: SolidLanguageServer | None = None

    def initialize(self, workspace_root: str) -> dict:
        """Start the underlying SolidLanguageServer."""
        config = self._create_config()
        settings = self._create_settings()
        self._server = self._server_class(config, workspace_root, settings)
        self._server.start()
        return self._server.capabilities  # Return server capabilities

    def get_references(
        self, file_path: str, line: int, column: int
    ) -> list[LspLocation]:
        """Translate SolidLSP references to fs2 LspLocation."""
        if not self._server:
            raise LspAdapterError("Server not initialized")

        try:
            # SolidLSP returns ls_types.Location list
            raw_refs = self._server.request_references(file_path, line, column)
            return [self._translate_location(loc) for loc in raw_refs]
        except Exception as e:
            raise LspAdapterError(
                f"Failed to get references: {e}",
                fix_instructions="Check if language server is running"
            ) from e

    def _translate_location(self, loc: dict) -> LspLocation:
        """Convert SolidLSP Location to fs2 LspLocation."""
        return LspLocation(
            file_path=loc.get("relativePath") or self._uri_to_path(loc["uri"]),
            line=loc["range"]["start"]["line"],
            column=loc["range"]["start"]["character"],
            end_line=loc["range"]["end"]["line"],
            end_column=loc["range"]["end"]["character"],
        )
```

---

### I1-04: CodeEdge Mapping from LSP Results

**Discovery**: LSP responses map directly to existing CodeEdge model with high confidence.

**Mapping Table**:

| LSP Request | EdgeType | Confidence | resolution_rule |
|-------------|----------|------------|-----------------|
| `textDocument/references` | REFERENCES | 0.95 | `lsp:references` |
| `textDocument/definition` | REFERENCES | 1.0 | `lsp:definition` |
| `textDocument/implementation` | CALLS | 0.9 | `lsp:implementation` |

**Conversion Function** (in `src/fs2/core/adapters/lsp_edge_converter.py`):

```python
from fs2.core.models import CodeEdge, EdgeType

def lsp_reference_to_edge(
    source_node_id: str,
    source_line: int,
    lsp_location: LspLocation,
    workspace_root: str,
) -> CodeEdge:
    """Convert LSP reference location to CodeEdge.

    Args:
        source_node_id: The node_id of the symbol being analyzed
        source_line: Line in source file where reference originates
        lsp_location: LSP location of the reference target
        workspace_root: Workspace root for path resolution

    Returns:
        CodeEdge with REFERENCES type and 0.95 confidence
    """
    # Convert file path to node_id format
    target_node_id = f"file:{lsp_location.file_path}"

    return CodeEdge(
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        edge_type=EdgeType.REFERENCES,
        confidence=0.95,
        source_line=source_line,
        resolution_rule="lsp:references",
    )

def lsp_definition_to_edge(
    source_node_id: str,
    source_line: int,
    lsp_location: LspLocation,
) -> CodeEdge:
    """Convert LSP definition to CodeEdge with confidence 1.0."""
    return CodeEdge(
        source_node_id=source_node_id,
        target_node_id=f"file:{lsp_location.file_path}",
        edge_type=EdgeType.REFERENCES,
        confidence=1.0,
        source_line=source_line,
        resolution_rule="lsp:definition",
    )
```

---

### I1-05: Phase Breakdown with Dependencies

**Discovery**: Implementation should be 5 phases with clear dependencies.

```
Phase 1: Vendor SolidLSP Core (No dependencies)
    │
    └──► Phase 2: LspAdapter ABC + FakeLspAdapter (Depends on Phase 1)
            │
            └──► Phase 3: SolidLspAdapter + Pyright (Depends on Phase 2)
                    │
                    ├──► Phase 4: Multi-Language Expansion (Depends on Phase 3)
                    │
                    └──► Phase 5: Pipeline Integration (Depends on Phase 3)
```

| Phase | Deliverables | LOC | Tests | Duration |
|-------|--------------|-----|-------|----------|
| 1 | Vendor solidlsp/ to fs2/vendors/ | ~6K | 0 | 0.5 day |
| 2 | LspAdapter ABC, FakeLspAdapter, LspAdapterError | ~300 | 20+ | 1 day |
| 3 | SolidLspAdapter, Pyright integration, edge converter | ~500 | 15+ | 1.5 days |
| 4 | gopls, TypeScript LS, OmniSharp configs | ~300 | 12+ | 1 day |
| 5 | `--with-lsp` CLI flag, lazy init, benchmarks | ~200 | 10+ | 1 day |

**Total**: ~7.3K LOC, 57+ tests, 5 days

---

### I1-06: Testing Strategy Based on fs2 Infrastructure

**Discovery**: Testing follows existing fs2 patterns with real server integration tests.

**Unit Test Structure** (`tests/unit/adapters/`):

```
tests/unit/adapters/
├── test_lsp_adapter.py           # ABC contract tests (like test_embedding_adapter.py)
├── test_lsp_adapter_fake.py      # Fake behavior tests
├── test_lsp_adapter_solid.py     # SolidLspAdapter unit tests (mocked server)
└── test_lsp_edge_converter.py    # Edge conversion tests
```

**Integration Test Structure** (`tests/integration/`):

```
tests/integration/
├── test_lsp_pyright.py           # Real Pyright server tests
├── test_lsp_gopls.py             # Real gopls tests
├── test_lsp_typescript.py        # Real TypeScript LS tests
└── conftest.py                   # Fixtures with availability guards
```

**Fixture Pattern** (from Serena):

```python
import pytest
from fs2.core.adapters import LspAdapter, SolidLspAdapter

def is_pyright_available() -> bool:
    """Check if pyright is installed."""
    try:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "pyright.langserver", "--version"],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False

@pytest.fixture(scope="module")
def pyright_adapter(tmp_path_factory):
    """Real Pyright adapter for integration tests."""
    if not is_pyright_available():
        pytest.skip("Pyright not available")

    workspace = tmp_path_factory.mktemp("workspace")
    # Create minimal Python project
    (workspace / "main.py").write_text("def hello(): pass")

    adapter = SolidLspAdapter.create_for_language("python", str(workspace))
    adapter.initialize(str(workspace))
    yield adapter
    adapter.shutdown()
```

**Test Repository Structure**:

```
tests/fixtures/lsp_test_repos/
├── python/
│   ├── main.py              # Entry point with imports
│   ├── services/
│   │   └── auth.py          # Cross-file references
│   └── expected_edges.json  # Ground truth for validation
├── go/
│   ├── main.go
│   └── pkg/utils/utils.go
└── typescript/
    ├── src/index.ts
    └── src/utils.ts
```

---

### I1-07: Exception Hierarchy Following fs2 Patterns

**Discovery**: LspAdapterError follows existing exception patterns in exceptions.py.

**File**: `src/fs2/core/adapters/exceptions.py` (add to existing)

```python
# LSP Adapter Exceptions
# ----------------------
class LspAdapterError(AdapterError):
    """Base exception for LSP adapter failures.

    All LSP-related exceptions include actionable fix instructions.
    """
    pass

class LspServerNotFoundError(LspAdapterError):
    """Raised when the language server executable is not found."""

    def __init__(self, server_name: str, install_instructions: str):
        super().__init__(
            message=f"Language server '{server_name}' not found",
            fix_instructions=install_instructions,
        )
        self.server_name = server_name

class LspServerCrashError(LspAdapterError):
    """Raised when the language server process terminates unexpectedly."""

    def __init__(self, server_name: str, exit_code: int | None = None):
        fix = f"Restart the scan. If persistent, check {server_name} installation."
        super().__init__(
            message=f"Language server '{server_name}' crashed (exit={exit_code})",
            fix_instructions=fix,
        )

class LspTimeoutError(LspAdapterError):
    """Raised when LSP request times out."""

    def __init__(self, operation: str, timeout_seconds: float):
        super().__init__(
            message=f"LSP operation '{operation}' timed out after {timeout_seconds}s",
            fix_instructions="Increase timeout or reduce codebase size",
        )

class LspInitializationError(LspAdapterError):
    """Raised when language server fails to initialize."""
    pass
```

---

### I1-08: Factory Function Pattern

**Discovery**: Create adapter factory following create_embedding_adapter_from_config pattern.

**File**: `src/fs2/core/adapters/lsp_adapter.py` (add to ABC file)

```python
from fs2.config import LspConfig

def create_lsp_adapter_from_config(
    config: "LspConfig",
    workspace_root: str,
) -> LspAdapter:
    """Create appropriate LspAdapter based on configuration.

    Factory function that instantiates the correct LSP adapter
    implementation based on config settings.

    Args:
        config: LSP configuration from fs2.config
        workspace_root: Absolute path to workspace root

    Returns:
        Configured LspAdapter instance

    Raises:
        LspServerNotFoundError: If configured server not available
    """
    from fs2.core.adapters.lsp_adapter_solid import SolidLspAdapter

    language = config.language  # e.g., "python"

    # Map language to server class
    server_map = {
        "python": ("pyright", PyrightServer),
        "go": ("gopls", Gopls),
        "typescript": ("typescript-language-server", TypeScriptLanguageServer),
        "csharp": ("omnisharp", OmniSharp),
    }

    if language not in server_map:
        raise ValueError(f"Unsupported language: {language}")

    server_name, server_class = server_map[language]

    return SolidLspAdapter(
        server_class=server_class,
        workspace_root=workspace_root,
        language_id=language,
    )
```

---

### I1-09: FakeLspAdapter Pattern

**Discovery**: FakeLspAdapter mirrors FakeEmbeddingAdapter with call_history.

**File**: `src/fs2/core/adapters/lsp_adapter_fake.py` (~200 LOC)

```python
from fs2.core.adapters.lsp_adapter import LspAdapter, LspLocation

class FakeLspAdapter(LspAdapter):
    """Test double for LspAdapter with call history and configurable responses.

    Usage in tests:
        fake = FakeLspAdapter()
        fake.set_references_response("file.py", 10, 5, [
            LspLocation(file_path="other.py", line=20, column=0),
        ])

        refs = fake.get_references("file.py", 10, 5)
        assert fake.call_history[-1] == {
            "method": "get_references",
            "args": ("file.py", 10, 5),
        }
    """

    def __init__(
        self,
        provider_name: str = "fake",
        language_id: str = "python",
    ):
        self._provider_name = provider_name
        self._language_id = language_id
        self._call_history: list[dict] = []
        self._references_responses: dict[tuple, list[LspLocation]] = {}
        self._definition_responses: dict[tuple, list[LspLocation]] = {}
        self._error_for: set[str] = set()
        self._initialized = False

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def language_id(self) -> str:
        return self._language_id

    @property
    def call_history(self) -> list[dict]:
        """Return recorded call history for test assertions."""
        return list(self._call_history)

    def set_references_response(
        self,
        file_path: str,
        line: int,
        column: int,
        response: list[LspLocation],
    ) -> None:
        """Configure response for specific get_references call."""
        key = (file_path, line, column)
        self._references_responses[key] = response

    def simulate_error_for(self, method: str) -> None:
        """Configure method to raise LspAdapterError."""
        self._error_for.add(method)

    def initialize(self, workspace_root: str) -> dict:
        self._call_history.append({
            "method": "initialize",
            "args": (workspace_root,),
        })
        if "initialize" in self._error_for:
            raise LspAdapterError("Simulated initialization error")
        self._initialized = True
        return {"capabilities": {"referencesProvider": True}}

    def shutdown(self) -> None:
        self._call_history.append({"method": "shutdown", "args": ()})
        self._initialized = False

    def get_references(
        self, file_path: str, line: int, column: int
    ) -> list[LspLocation]:
        self._call_history.append({
            "method": "get_references",
            "args": (file_path, line, column),
        })
        if "get_references" in self._error_for:
            raise LspAdapterError("Simulated get_references error")

        key = (file_path, line, column)
        return self._references_responses.get(key, [])

    def get_definition(
        self, file_path: str, line: int, column: int
    ) -> list[LspLocation]:
        self._call_history.append({
            "method": "get_definition",
            "args": (file_path, line, column),
        })
        if "get_definition" in self._error_for:
            raise LspAdapterError("Simulated get_definition error")

        key = (file_path, line, column)
        return self._definition_responses.get(key, [])
```

---

### I1-10: Pipeline Integration Points

**Discovery**: LSP integration hooks into ScanPipeline via PipelineContext.

**Integration Points in Existing Code**:

| File | Purpose | Modification |
|------|---------|--------------|
| `src/fs2/core/services/scan_pipeline.py` | Orchestration | Add LSP stage after AST parsing |
| `src/fs2/core/services/pipeline_context.py` | Context | Already has `relationships: list[CodeEdge]` |
| `src/fs2/cli/scan.py` | CLI | Add `--with-lsp` flag |
| `src/fs2/config/scan_config.py` | Config | Add `lsp_enabled: bool` |

**New Pipeline Stage** (`src/fs2/core/services/lsp_relationship_stage.py`):

```python
from fs2.core.services.pipeline_context import PipelineContext
from fs2.core.adapters import LspAdapter
from fs2.core.models import CodeEdge

class LspRelationshipStage:
    """Pipeline stage that extracts cross-file relationships using LSP."""

    def __init__(self, lsp_adapter: LspAdapter):
        self._adapter = lsp_adapter

    def execute(self, context: PipelineContext) -> PipelineContext:
        """Extract relationships for all callable nodes in context.

        For each method/function node:
        1. Request references from LSP
        2. Convert to CodeEdge instances
        3. Append to context.relationships
        """
        relationships: list[CodeEdge] = context.relationships or []

        for node in context.nodes:
            if node.category != "callable":
                continue

            # Extract file path and position from node
            file_path = self._node_to_file_path(node)
            line, col = self._node_to_position(node)

            # Get references via LSP
            refs = self._adapter.get_references(file_path, line, col)

            # Convert to edges
            for ref in refs:
                edge = lsp_reference_to_edge(
                    source_node_id=node.node_id,
                    source_line=line,
                    lsp_location=ref,
                )
                relationships.append(edge)

        return PipelineContext(
            **context.__dict__,
            relationships=relationships,
        )
```

---

## Implementation Order

### Phase 1: Vendor SolidLSP Core (Day 1, Morning)

**Tasks**:
1. Create `src/fs2/vendors/` directory structure
2. Copy core files from Serena's solidlsp/:
   - `ls.py` (strip Serena-specific imports)
   - `ls_handler.py`
   - `ls_types.py`
   - `ls_exceptions.py`
   - `ls_request.py`
   - `language_servers/common.py`
   - `lsp_protocol_handler/` subdirectory
3. Create `__init__.py` with public exports
4. Fix import paths to use `fs2.vendors.solidlsp`
5. Add `psutil` to dependencies (for process tree cleanup)

**Validation**: `python -c "from fs2.vendors.solidlsp.ls import SolidLanguageServer"`

---

### Phase 2: LspAdapter ABC + FakeLspAdapter (Day 1, Afternoon + Day 2, Morning)

**Tasks**:
1. Create `src/fs2/core/adapters/lsp_adapter.py`:
   - LspLocation dataclass
   - LspAdapter ABC with 5 abstract methods
   - create_lsp_adapter_from_config factory (stub)
2. Create `src/fs2/core/adapters/lsp_adapter_fake.py`:
   - FakeLspAdapter with call_history
   - Response configuration methods
   - Error simulation
3. Add LspAdapterError hierarchy to `exceptions.py`
4. Write unit tests:
   - `test_lsp_adapter.py` - ABC contract tests
   - `test_lsp_adapter_fake.py` - Fake behavior tests

**Validation**: All unit tests pass, ABC enforces interface

---

### Phase 3: SolidLspAdapter + Pyright (Day 2, Afternoon + Day 3)

**Tasks**:
1. Vendor `language_servers/pyright_server.py`
2. Create `src/fs2/core/adapters/lsp_adapter_solid.py`:
   - SolidLspAdapter implementation
   - Location translation layer
   - Error translation
3. Create `src/fs2/core/adapters/lsp_edge_converter.py`:
   - lsp_reference_to_edge()
   - lsp_definition_to_edge()
4. Integration test with real Pyright:
   - Create Python test repository
   - Verify reference detection
   - Validate edge conversion

**Validation**: Integration tests pass with real Pyright server

---

### Phase 4: Multi-Language Expansion (Day 4)

**Tasks**:
1. Vendor language servers:
   - `language_servers/gopls.py`
   - `language_servers/typescript_language_server.py`
   - `language_servers/omnisharp.py`
2. Create test repositories for each language
3. Write parameterized integration tests
4. Add availability guards (skip if server not installed)

**Validation**: Parameterized tests pass for all available servers

---

### Phase 5: Pipeline Integration (Day 5)

**Tasks**:
1. Create `LspRelationshipStage` service
2. Add `--with-lsp` flag to `fs2 scan` CLI
3. Add `lsp_enabled` to ScanConfig
4. Implement lazy LSP initialization
5. Integration test: full pipeline with LSP
6. Performance benchmarking

**Validation**: `fs2 scan --with-lsp` produces edges in graph

---

## Key SolidLSP Files Summary

### Must Vendor (Core)

| File | Source Path | Target Path | LOC |
|------|-------------|-------------|-----|
| ls.py | src/solidlsp/ls.py | src/fs2/vendors/solidlsp/ls.py | 2000 |
| ls_handler.py | src/solidlsp/ls_handler.py | src/fs2/vendors/solidlsp/ls_handler.py | 592 |
| ls_types.py | src/solidlsp/ls_types.py | src/fs2/vendors/solidlsp/ls_types.py | 446 |
| ls_exceptions.py | src/solidlsp/ls_exceptions.py | src/fs2/vendors/solidlsp/ls_exceptions.py | 50 |
| ls_request.py | src/solidlsp/ls_request.py | src/fs2/vendors/solidlsp/ls_request.py | 384 |
| common.py | language_servers/common.py | vendors/solidlsp/language_servers/common.py | 165 |
| lsp_protocol_handler/ | src/solidlsp/lsp_protocol_handler/ | vendors/solidlsp/lsp_protocol_handler/ | ~1000 |

### Must Vendor (Language Servers - Phase 3-4)

| File | Source Path | LOC | Phase |
|------|-------------|-----|-------|
| pyright_server.py | language_servers/pyright_server.py | 197 | 3 |
| gopls.py | language_servers/gopls.py | 168 | 4 |
| typescript_language_server.py | language_servers/typescript_language_server.py | 290 | 4 |
| omnisharp.py | language_servers/omnisharp.py | 400 | 4 |

### May Need (Utilities)

| File | Purpose | Vendor If |
|------|---------|-----------|
| ls_utils.py | FileUtils, PathUtils | Used by core |
| settings.py | SolidLSPSettings | Required by constructors |
| util/subprocess_util.py | Subprocess helpers | Used by ls_handler.py |
| util/cache.py | Cache persistence | If we want caching |

---

## CodeEdge Model Compatibility

**Existing CodeEdge** (from `src/fs2/core/models/code_edge.py`):

```python
@dataclass(frozen=True)
class CodeEdge:
    source_node_id: str           # "file:src/app.py" or "method:src/app.py:main"
    target_node_id: str           # Target node_id
    edge_type: EdgeType           # IMPORTS, CALLS, REFERENCES, DOCUMENTS
    confidence: float             # 0.0-1.0
    source_line: int | None       # Line number for navigation
    resolution_rule: str          # How relationship was determined
```

**SolidLSP Location** (from `ls_types.py`):

```python
class Location(TypedDict):
    uri: DocumentUri              # file:///path/to/file.py
    range: Range                  # {start: {line, char}, end: {line, char}}
    absolutePath: str             # /absolute/path/to/file.py
    relativePath: str | None      # src/file.py
```

**Translation**:

| SolidLSP Field | CodeEdge Field | Transformation |
|----------------|----------------|----------------|
| `relativePath` | `target_node_id` | Prefix with `"file:"` |
| `range.start.line` | `source_line` | Direct (0-indexed in both) |
| N/A | `edge_type` | Always `EdgeType.REFERENCES` for LSP |
| N/A | `confidence` | 0.95 for references, 1.0 for definitions |
| N/A | `resolution_rule` | `"lsp:references"` or `"lsp:definition"` |

---

## Success Criteria

1. **Phase 1**: `from fs2.vendors.solidlsp import SolidLanguageServer` works
2. **Phase 2**: FakeLspAdapter passes 20+ unit tests with call_history
3. **Phase 3**: Pyright integration test finds real references in Python code
4. **Phase 4**: All 4 language servers work with parameterized tests
5. **Phase 5**: `fs2 scan --with-lsp` produces valid CodeEdge instances

---

**Strategy Complete**: 2026-01-14
**Ready for Implementation**: Yes
