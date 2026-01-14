# External Research: Serena's SolidLSP Implementation

**Research Date**: 2026-01-14
**Source**: Serena codebase at `/workspaces/flow_squared/scratch/serena`
**Purpose**: Extract innovations and patterns for fs2's LSP integration

---

## Executive Summary

Serena's SolidLSP is a production-tested LSP client framework supporting **40+ programming languages** with a unified abstraction layer. The architecture demonstrates several innovations that could significantly simplify fs2's LSP integration, particularly around:

1. **Thin wrapper pattern** - Most languages need only ~100-150 lines of code
2. **RuntimeDependencyCollection** - Unified binary/npm/download management
3. **Two-tier caching** - Separates raw LSP responses from processed symbols
4. **Parallel startup with error aggregation** - Multiple servers start concurrently
5. **Auto-restart on health check failure** - Transparent recovery

---

## 1. Architecture Overview

### 1.1 Layered Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Application Layer (Serena)                        │
│  - LanguageServerManager: Orchestrates multiple servers              │
│  - Project: Multi-language context                                   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 SolidLanguageServer (ABC) - ~2000 LOC               │
│  Location: src/solidlsp/ls.py                                        │
│  - Language-agnostic high-level API                                  │
│  - Symbol management and caching                                     │
│  - Reference-counted file buffers                                    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│            SolidLanguageServerHandler - ~600 LOC                     │
│  Location: src/solidlsp/ls_handler.py                                │
│  - JSON-RPC 2.0 client implementation                                │
│  - Process lifecycle and thread management                           │
│  - Request/response correlation with Queue                           │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│               Language Server Process (stdin/stdout)                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Key Files Reference

| File | LOC | Purpose |
|------|-----|---------|
| `src/solidlsp/ls.py` | ~2000 | ABC, caching, symbol operations |
| `src/solidlsp/ls_handler.py` | 592 | JSON-RPC client, process management |
| `src/solidlsp/ls_config.py` | 452 | Language enum, file matchers, factory |
| `src/solidlsp/ls_types.py` | 446 | UnifiedSymbolInformation, Location |
| `src/solidlsp/ls_request.py` | 384 | Typed LSP request wrappers |
| `src/solidlsp/language_servers/common.py` | ~200 | RuntimeDependencyCollection |
| `src/serena/ls_manager.py` | ~200 | Multi-server orchestration |

---

## 2. Innovation #1: Thin Wrapper Pattern

### The Problem
Our original plan assumed each language needs a dedicated adapter class with significant code.

### Serena's Solution
Most languages need only **100-150 lines** because:
1. Base class handles all LSP protocol details
2. Per-language class only specifies:
   - How to locate/install the binary
   - InitializeParams customization
   - Ignored directories
   - Cross-file wait times

### Code Example (Minimal Server ~90 lines)

```python
class MinimalLanguageServer(SolidLanguageServer):
    def __init__(self, config, repository_root_path, solidlsp_settings):
        executable_path = self._setup_runtime_dependencies(solidlsp_settings)
        super().__init__(
            config, repository_root_path,
            ProcessLaunchInfo(cmd=f"{executable_path} --stdio", cwd=repository_root_path),
            "language_id",
            solidlsp_settings,
        )

    @classmethod
    def _setup_runtime_dependencies(cls, solidlsp_settings) -> str:
        deps = RuntimeDependencyCollection([
            RuntimeDependency(
                id="server",
                command="npm install --prefix ./ server@1.0.0",
                platform_id="any",
            )
        ])
        ls_dir = cls.ls_resources_dir(solidlsp_settings)
        executable = os.path.join(ls_dir, "node_modules", ".bin", "server")
        if not os.path.exists(executable):
            deps.install(ls_dir)
        return executable

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        root_uri = pathlib.Path(repository_absolute_path).as_uri()
        return {
            "processId": os.getpid(),
            "rootUri": root_uri,
            "capabilities": {
                "textDocument": {
                    "definition": {},
                    "references": {},
                    "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                },
            },
            "workspaceFolders": [{"uri": root_uri, "name": os.path.basename(repository_absolute_path)}],
        }

    def _start_server(self) -> None:
        self.server.on_notification("window/logMessage", lambda msg: None)
        self.server.on_notification("$/progress", lambda p: None)
        self.server.start()
        self.server.send.initialize(self._get_initialize_params(self.repository_root_path))
        self.server.notify.initialized({})
```

### Complexity Tiers

| Tier | LOC | Examples | Characteristics |
|------|-----|----------|-----------------|
| Simple | 100-150 | YAML, Bash, Lua | npm install, single process |
| Medium | 150-250 | Go, PHP, Perl | System prerequisites |
| Complex | 300-500 | C#, Java, Python | Binary downloads, runtimes |
| Very Complex | 500+ | Vue | Multiple servers |

### fs2 Application
- Adopt declarative config approach
- Create templates per complexity tier
- Target 50-100 lines per language for fs2's needs (we only need references/definitions)

---

## 3. Innovation #2: RuntimeDependencyCollection

### The Problem
Different language servers have different acquisition methods:
- System binary (gopls, pyright)
- npm package (typescript-language-server)
- Platform-specific download (OmniSharp, Eclipse JDTLS)
- NuGet package (C# Roslyn)

### Serena's Solution
A unified `RuntimeDependencyCollection` handles all cases:

```python
@dataclass(kw_only=True)
class RuntimeDependency:
    id: str
    platform_id: str | None = None    # "linux-x64", "win-x64", "any"
    url: str | None = None            # Download URL
    archive_type: str | None = None   # "zip", "gz", "tar.gz", "nupkg", "binary"
    binary_name: str | None = None    # Path within extracted archive
    command: str | list[str] | None = None  # Alternative: run command

class RuntimeDependencyCollection:
    def __init__(self, dependencies: list[RuntimeDependency]):
        self._dependencies = dependencies

    def install(self, target_dir: str) -> dict[str, str]:
        """Install platform-appropriate dependencies, return paths."""
        for dep in self._get_platform_dependencies():
            if dep.command:
                self._run_command(dep, target_dir)
            elif dep.url:
                self._download_and_extract(dep, target_dir)
```

### Examples from Serena

**Go (system binary)**:
```python
@staticmethod
def _setup_runtime_dependency() -> bool:
    if not shutil.which("gopls"):
        raise RuntimeError("gopls is not installed")
    return True
```

**TypeScript (npm)**:
```python
deps = RuntimeDependencyCollection([
    RuntimeDependency(
        id="typescript-language-server",
        command="npm install --prefix ./ typescript-language-server@4.0.0",
        platform_id="any",
    )
])
```

**C# (platform-specific NuGet + runtime)**:
```python
deps = RuntimeDependencyCollection([
    RuntimeDependency(
        id="CSharpLanguageServer",
        package_name="Microsoft.CodeAnalysis.LanguageServer.linux-x64",
        platform_id="linux-x64",
        archive_type="nupkg",
    ),
    RuntimeDependency(
        id="DotNetRuntime",
        url="https://builds.dotnet.microsoft.com/.../dotnet-runtime-linux-x64.tar.gz",
        platform_id="linux-x64",
        archive_type="tar.gz",
    ),
])
```

### fs2 Application
- Adopt this pattern for our external-research-3-binary-distribution.md findings
- Provides clean API for Phase 3/4 server setup
- Consider lazy download on first use

---

## 4. Innovation #3: Two-Tier Symbol Caching

### The Problem
LSP responses can be slow; repeated queries hurt performance.
Cache invalidation is tricky when file contents change.

### Serena's Solution
Two separate caches with different invalidation strategies:

**Tier 1: Raw Document Symbols Cache**
```python
_raw_document_symbols_cache: dict[str, tuple[str, list[DocumentSymbol] | None]]
# Key: relative_path
# Value: (content_hash, raw_lsp_response)
```
- Stores unprocessed LSP responses
- Invalidated only when file content hash changes
- Survives code processing changes

**Tier 2: Processed Document Symbols Cache**
```python
_document_symbols_cache: dict[str, tuple[str, DocumentSymbols]]
# Key: relative_path
# Value: (content_hash, processed_symbols_with_parent_links)
```
- Stores symbols with parent links, bodies extracted
- Derived from Tier 1 + file content
- Separate version number for processing changes

**Cache Persistence**:
```
.serena/cache/{language}/
  raw_document_symbols.pkl    # Tier 1
  document_symbols.pkl        # Tier 2
```

**Version Control**:
```python
def __init__(self, ..., cache_version_raw_document_symbols: Hashable = 1):
    # Bump version to invalidate when LS behavior changes
```

### fs2 Application
- Apply to our graph persistence layer
- Separate raw parse results from enriched graph with edges
- Use content hashing for invalidation

---

## 5. Innovation #4: Parallel Startup with Error Aggregation

### The Problem
Starting multiple language servers sequentially is slow.
If one fails, others might have started successfully.

### Serena's Solution
Parallel startup with proper error handling:

```python
# From src/serena/ls_manager.py:76-120
@classmethod
def from_languages(cls, languages: list[Language], ...) -> "LanguageServerManager":
    threads: list[threading.Thread] = []
    exceptions: dict[Language, Exception] = {}
    language_servers: dict[Language, SolidLanguageServer] = {}
    lock = threading.Lock()

    def start_language_server(language: Language) -> None:
        try:
            ls = factory.create(language)
            ls.start()
            with lock:
                language_servers[language] = ls
        except Exception as e:
            with lock:
                exceptions[language] = e

    # Start all in parallel
    for language in languages:
        thread = threading.Thread(target=start_language_server, args=(language,))
        thread.start()
        threads.append(thread)

    # Wait for all
    for thread in threads:
        thread.join()

    # If any failed, stop all and raise combined error
    if exceptions:
        for ls in language_servers.values():
            ls.stop()
        raise LanguageServerStartupError(exceptions)

    return cls(language_servers, factory, ...)
```

### fs2 Application
- Apply to pipeline stage that starts LSP servers
- Start all needed servers in parallel
- Clean rollback if any fail
- Matches our "graceful degradation" requirement (AC13)

---

## 6. Innovation #5: Auto-Restart on Health Check

### The Problem
Language servers can crash mid-session.
Manual restart handling is error-prone.

### Serena's Solution
Transparent health check and restart:

```python
# From src/serena/ls_manager.py:125-140
def get_language_server(self, relative_path: str) -> SolidLanguageServer:
    ls = self._select_language_server(relative_path)
    return self._ensure_functional_ls(ls)

def _ensure_functional_ls(self, ls: SolidLanguageServer) -> SolidLanguageServer:
    if not ls.is_running():
        log.warning(f"Language server for {ls.language} is not running; restarting...")
        ls = self.restart_language_server(ls.language)
    return ls
```

### fs2 Application
- Wrap every LSP call with health check
- Automatic recovery without caller awareness
- Essential for long scan operations

---

## 7. Innovation #6: Process Tree Cleanup

### The Problem
Some language servers spawn child processes.
Standard process termination leaves zombies.

### Serena's Solution
Use psutil for tree termination:

```python
# From src/solidlsp/ls_handler.py:267-297
def _signal_process_tree(self, process, terminate: bool = True):
    try:
        import psutil
        parent = psutil.Process(process.pid)
        for child in parent.children(recursive=True):
            getattr(child, "terminate" if terminate else "kill")()
        getattr(parent, "terminate" if terminate else "kill")()
    except Exception:
        # Fallback to direct signaling
        process.terminate() if terminate else process.kill()
```

### fs2 Application
- Add psutil as dependency
- Use for LSP server cleanup
- Prevents resource leaks during long scans

---

## 8. Innovation #7: Language Enum as Registry

### The Problem
Language server configuration is scattered.
Adding a new language requires changes in multiple places.

### Serena's Solution
Single-source-of-truth enum with lazy loading:

```python
# From src/solidlsp/ls_config.py
class Language(str, Enum):
    PYTHON = "python"
    GO = "go"
    CSHARP = "csharp"
    # ... 40+ languages

    def get_source_fn_matcher(self) -> FilenameMatcher:
        match self:
            case self.PYTHON: return FilenameMatcher("*.py", "*.pyi")
            case self.GO: return FilenameMatcher("*.go")
            case self.CSHARP: return FilenameMatcher("*.cs")

    def get_ls_class(self) -> type["SolidLanguageServer"]:
        match self:
            case self.PYTHON:
                from .pyright_server import PyrightServer
                return PyrightServer
            case self.GO:
                from .gopls import Gopls
                return Gopls
            # Lazy imports prevent loading 40+ modules at startup
```

### fs2 Application
- Adopt similar pattern for LspServerConfig registry
- Single file to edit when adding languages
- Lazy loading prevents import overhead

---

## 9. Innovation #8: UnifiedSymbolInformation

### The Problem
LSP responses differ between servers (SymbolInformation vs DocumentSymbol).
No standard way to navigate symbol trees.

### Serena's Solution
Extended type with parent links and body:

```python
# From src/solidlsp/ls_types.py
class UnifiedSymbolInformation(TypedDict):
    name: str
    kind: SymbolKind
    location: NotRequired[Location]
    selectionRange: NotRequired[Range]
    containerName: NotRequired[str]
    detail: NotRequired[str]
    body: NotRequired[str]                           # Full source code
    children: list[UnifiedSymbolInformation]         # Child symbols
    parent: NotRequired[UnifiedSymbolInformation | None]  # Parent reference
    overload_idx: NotRequired[int]                   # For method overloading
```

**Bidirectional Navigation**:
```python
def convert_symbols_with_common_parent(symbols, parent):
    for symbol in symbols:
        usymbol = convert_to_unified_symbol(symbol)
        usymbol["parent"] = parent  # Add parent link
        if "children" in symbol:
            usymbol["children"] = convert_symbols_with_common_parent(
                symbol["children"], usymbol
            )
```

### fs2 Application
- Similar to our CodeNode model
- Parent link useful for tree navigation
- Overload index needed for Java/C# support

---

## 10. Innovation #9: Name Path Addressing

### The Problem
Symbols need human-readable addresses for tooling.
Must handle nested structures and overloads.

### Serena's Solution
Path-based addressing with pattern matching:

```python
NAME_PATH_SEP = "/"

# Examples:
"MyClass"                    # Simple name
"MyClass/my_method"          # Method in class
"/MyClass/my_method"         # Absolute (leading / = exact match)
"MyClass/my_method[0]"       # First overload

# Pattern matching
class NamePathMatcher:
    def matches(self, name_path: str) -> bool:
        # Supports substring matching unless absolute
```

### fs2 Application
- Consider for MCP tool symbol addressing
- Maps well to our node_id format
- Could enhance tree() and search() tools

---

## 11. Innovation #10: Cross-File Reference Wait

### The Problem
Language servers need time to index.
References return empty immediately after startup.

### Serena's Solution
Configurable per-language wait:

```python
# From src/solidlsp/ls.py:333-344
def _get_wait_time_for_cross_file_referencing(self) -> float:
    return 2  # Default 2 seconds, override per language

def request_references(self, ...):
    if not self._has_waited_for_cross_file_references:
        sleep(self._get_wait_time_for_cross_file_referencing())
        self._has_waited_for_cross_file_references = True
    return self._send_references_request(...)
```

**Language-specific overrides**:
- Ruby: 0.5 seconds
- Default: 2 seconds
- Some servers: 5+ seconds for large projects

### fs2 Application
- Essential for our cross-file edge detection
- Configure per LspServerConfig
- Matches our external-research-4 findings on startup times

---

## 12. Testing Patterns

### 12.1 Real LSP Servers
Serena tests against **real language servers**, not mocks:
```python
@pytest.fixture(scope="module")
def language_server(request):
    language = request.param
    with start_default_ls_context(language) as ls:
        yield ls
```

### 12.2 Parameterized Multi-Language Tests
Single test, multiple languages:
```python
@pytest.mark.parametrize("language_server", [Language.PYTHON, Language.GO], indirect=True)
def test_symbols(language_server):
    symbols = language_server.request_full_symbol_tree()
    assert SymbolUtils.symbol_tree_contains_name(symbols, "main")
```

### 12.3 Test Repository Structure
Each language has a minimal test repo:
```
test/resources/repos/{language}/test_repo/
  models.{ext}      # Classes for symbol testing
  services.{ext}    # Cross-file references
  nested.{ext}      # Nested scopes
```

### 12.4 Language Availability Guards
```python
def is_clojure_cli_available() -> bool:
    try:
        verify_clojure_cli()
        return True
    except (FileNotFoundError, RuntimeError):
        return False

pytestmark = pytest.mark.skipif(
    not is_clojure_cli_available(),
    reason="Clojure CLI not installed"
)
```

### fs2 Application
- Adopt parameterized fixture pattern (AC17)
- Create test repos per language (AC02)
- Use availability guards for CI (AC19)

---

## 13. Summary: Key Takeaways for fs2

### High-Impact Adoptions

| Innovation | Benefit | Effort |
|------------|---------|--------|
| Thin wrapper pattern | Reduce per-language code from ~300 to ~100 lines | Medium |
| RuntimeDependencyCollection | Unified binary management | Low |
| Two-tier caching | Better cache invalidation | Medium |
| Parallel startup | Faster multi-language scans | Low |
| Auto-restart | Transparent recovery | Low |
| Process tree cleanup | No zombie processes | Low |

### Recommended Changes to Our Plan

1. **Phase 1**: Adopt RuntimeDependencyCollection pattern for LspServerConfig
2. **Phase 2**: Implement generic client based on Serena's ls_handler.py (queue-based correlation)
3. **Phase 3-4**: Use thin wrapper pattern - target ~100 LOC per language
4. **Phase 5**: Add parallel startup and auto-restart to pipeline stage
5. **Phase 7**: Adopt parameterized test fixtures

### Total LOC Estimate

Based on Serena's patterns:
- Generic client: ~600 LOC (adapt from ls_handler.py)
- Base adapter: ~500 LOC (adapt from ls.py, simplified for our needs)
- Per-language config: ~50-100 LOC each
- **Total for 4 languages**: ~1500-2000 LOC (vs original ~3000+ estimate)

---

## Appendix: File Inventory

### Core Architecture
- `src/solidlsp/ls.py` - Main ABC and operations
- `src/solidlsp/ls_handler.py` - JSON-RPC client
- `src/solidlsp/ls_config.py` - Language registry
- `src/solidlsp/ls_types.py` - Type definitions

### Language Servers (exemplars)
- `src/solidlsp/language_servers/common.py` - RuntimeDependencyCollection
- `src/solidlsp/language_servers/pyright_server.py` - Python (medium complexity)
- `src/solidlsp/language_servers/gopls.py` - Go (simple)
- `src/solidlsp/language_servers/omnisharp.py` - C# (complex)
- `src/solidlsp/language_servers/typescript_language_server.py` - TypeScript
- `src/solidlsp/language_servers/vue_language_server.py` - Vue (very complex, dual server)

### Management
- `src/serena/ls_manager.py` - Multi-server orchestration
- `src/serena/project.py` - Project context
- `src/solidlsp/settings.py` - Configuration

### Testing
- `test/conftest.py` - Fixtures and lifecycle
- `test/solidlsp/{language}/test_{language}_basic.py` - Per-language tests

---

**Research Complete**: 2026-01-14
**Findings**: 10 key innovations identified
**Recommendation**: Adopt thin wrapper pattern and RuntimeDependencyCollection to significantly reduce implementation effort
