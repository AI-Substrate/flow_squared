# Serena Architecture Research

**Date**: 2026-01-14
**Purpose**: Understand Serena's project root detection, adapter architecture, and testing patterns for adoption in fs2
**Source**: `/workspaces/flow_squared/scratch/serena`

---

## Table of Contents

1. [Project Root Detection](#a-project-root-detection)
2. [Adapter Architecture](#b-adapter-architecture)
3. [Liftability Assessment](#c-liftability-assessment)
4. [Testing Approach](#d-testing-approach)
5. [Recommendations for fs2](#e-recommendations-for-fs2)
6. [Gaps and Opportunities](#f-gaps-and-opportunities)

---

## A) Project Root Detection

### Algorithm Overview

Serena implements a hierarchical, breadth-first project root detection strategy with boundary constraints.

**File**: `/workspaces/flow_squared/scratch/serena/src/serena/cli.py` (lines 40-72)

```python
def find_project_root(root: str | Path | None = None) -> str:
    """Find project root by walking up from CWD.

    Checks for .serena/project.yml first (explicit Serena project),
    then .git (git root).
    Falls back to CWD if no marker is found.

    :param root: If provided, constrains the search to this directory
                 and below (acts as a virtual filesystem root).
                 Search stops at this boundary.
    :return: absolute path to project root (falls back to CWD if no
             marker found)
    """
    current = Path.cwd().resolve()
    boundary = Path(root).resolve() if root is not None else None

    def ancestors() -> Iterator[Path]:
        """Yield current directory and ancestors up to boundary."""
        yield current
        for parent in current.parents:
            yield parent
            if boundary is not None and parent == boundary:
                return

    # First pass: look for .serena
    for directory in ancestors():
        if (directory / ".serena" / "project.yml").is_file():
            return str(directory)

    # Second pass: look for .git
    for directory in ancestors():
        if (directory / ".git").exists():  # .git can be file (worktree) or dir
            return str(directory)

    # Fall back to CWD
    return str(current)
```

### Key Characteristics

| Feature | Implementation |
|---------|----------------|
| **Priority Order** | `.serena/project.yml` → `.git` → CWD |
| **Algorithm** | "Deepest wins" - walks up from CWD |
| **Boundary Constraint** | Optional `root` parameter prevents search beyond boundary |
| **Git Worktree Support** | Checks `.git` as both file and directory |
| **Monorepo Support** | None - simple marker detection only |

### Priority Order (Highest to Lowest)

1. `.serena/project.yml` - Explicit Serena project marker (deepest wins)
2. `.git` - Git repository root (deepest wins)
3. Current Working Directory (CWD) - Last resort fallback

### Algorithm Features

- **Boundary Constraint**: Optional `root` parameter acts as a virtual filesystem root, preventing search beyond that point (useful in containerized/sandboxed environments)
- **Multiple Passes**: Two separate passes allow for exact priority ordering without storing intermediate results
- **Git Worktree Support**: Checks for `.git` as both file and directory (git worktrees use a file instead of a directory)
- **No Monorepo Special Handling**: Uses simple "deepest marker wins" strategy; no monorepo marker detection

### Testing Strategy for Project Root

**File**: `/workspaces/flow_squared/scratch/serena/test/serena/test_cli_project_commands.py` (lines 266-329)

Tests use temporary directory fixtures and actual filesystem operations:

```python
class TestFindProjectRoot:
    """Tests for find_project_root helper with virtual chroot boundary."""

    def test_finds_serena_from_subdirectory(self, temp_project_dir):
        """Test that .serena/project.yml is found when searching
           from a subdirectory."""
        serena_dir = os.path.join(temp_project_dir, ".serena")
        os.makedirs(serena_dir)
        Path(os.path.join(serena_dir, "project.yml")).touch()
        subdir = os.path.join(temp_project_dir, "src", "nested")
        os.makedirs(subdir)

        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            result = find_project_root(root=temp_project_dir)
            assert result is not None
            assert os.path.samefile(result, temp_project_dir)
        finally:
            os.chdir(original_cwd)

    def test_serena_preferred_over_git(self, temp_project_dir):
        """Test that .serena/project.yml takes priority over .git
           at the same level."""
        # Test expects .serena to win when both exist

    def test_git_used_as_fallback(self, temp_project_dir):
        """Test that .git is found when no .serena exists."""

    def test_falls_back_to_cwd_when_no_markers(self, temp_project_dir):
        """Test falls back to CWD when no markers exist within boundary."""
```

**Fixture Pattern**:
- Uses temporary directories with real filesystem operations
- Changes CWD to test boundary behavior
- Restores original CWD in `finally` blocks
- No mocking - all tests use actual `pathlib.Path` operations

---

## B) Adapter Architecture

### Overview

Serena implements a **factory-based adapter pattern** with language-specific subclasses.

### Layer Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Project Layer                           │
│  serena/project.py - Coordinates tools and language servers     │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LanguageServerManager                         │
│  serena/ls_manager.py:54-120                                    │
│  - Manages multiple language servers                            │
│  - Selects server based on file extension                       │
│  - Parallel startup via threading                               │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LanguageServerFactory                          │
│  serena/ls_manager.py:16-52                                     │
│  - Dependency injection container                               │
│  - Creates language servers with shared configuration           │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SolidLanguageServer (ABC)                     │
│  solidlsp/ls.py:133-240                                         │
│  - Abstract base class for all language servers                 │
│  - Factory method: create() dispatches to subclasses            │
└─────────────────────────────────────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  PyrightServer  │  │ TypeScriptLS    │  │ DartLanguageLS  │
│  (Python)       │  │ (TypeScript)    │  │ (Dart)          │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Base Class: SolidLanguageServer (ABC)

**File**: `/workspaces/flow_squared/scratch/serena/src/solidlsp/ls.py` (lines 133-240)

```python
class SolidLanguageServer(ABC):
    """Language-agnostic interface to the Language Server Protocol."""

    @classmethod
    def create(
        cls,
        config: LanguageServerConfig,
        repository_root_path: str,
        timeout: float | None = None,
        solidlsp_settings: SolidLSPSettings | None = None,
    ) -> "SolidLanguageServer":
        """Factory method for language-specific instances."""
        ls_class = config.code_language.get_ls_class()
        ls = ls_class(config, repository_root_path, solidlsp_settings)
        ls.set_request_timeout(timeout)
        return ls
```

### Language Enum Registration System

**File**: `/workspaces/flow_squared/scratch/serena/src/solidlsp/ls_config.py` (lines 245-430)

Language enums dynamically map to language server implementations:

```python
class Language(str, Enum):
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    CSHARP = "csharp"
    DART = "dart"
    # ... 30+ languages

    def get_ls_class(self) -> type["SolidLanguageServer"]:
        """Dynamic lazy import of language-specific adapter."""
        match self:
            case self.PYTHON:
                from solidlsp.language_servers.pyright_server import PyrightServer
                return PyrightServer
            case self.TYPESCRIPT:
                from solidlsp.language_servers.typescript_language_server import TypeScriptLanguageServer
                return TypeScriptLanguageServer
            case self.DART:
                from solidlsp.language_servers.dart_language_server import DartLanguageServer
                return DartLanguageServer
            case self.GO:
                from solidlsp.language_servers.gopls_server import GoplsServer
                return GoplsServer
            # ... etc
```

**Key Design Decisions**:
- Uses **Python Enum with string values** for language identification
- **Lazy importing** of language server classes (only loaded when needed)
- **Match statement** (Python 3.10+) for clean dispatch
- **Single responsibility**: Each enum variant knows its adapter class

### Language-Specific Adapter Implementation Example

**File**: `/workspaces/flow_squared/scratch/serena/src/solidlsp/language_servers/dart_language_server.py` (lines 17-151)

```python
class DartLanguageServer(SolidLanguageServer):
    """Dart-specific instantiation of the LanguageServer class."""

    def __init__(
        self,
        config: LanguageServerConfig,
        repository_root_path: str,
        solidlsp_settings: SolidLSPSettings
    ) -> None:
        """Creates a DartServer instance."""
        executable_path = self._setup_runtime_dependencies(solidlsp_settings)
        super().__init__(
            config,
            repository_root_path,
            ProcessLaunchInfo(cmd=executable_path, cwd=repository_root_path),
            "dart",
            solidlsp_settings
        )

    @classmethod
    def _setup_runtime_dependencies(cls, solidlsp_settings: SolidLSPSettings) -> str:
        """Download and manage Dart SDK dependencies."""
        deps = RuntimeDependencyCollection([
            RuntimeDependency(
                id="DartLanguageServer",
                description="Dart Language Server for Linux (x64)",
                url="https://storage.googleapis.com/dart-archive/...",
                platform_id="linux-x64",
                archive_type="zip",
                binary_name="dart-sdk/bin/dart",
            ),
            # Platform-specific binaries for Windows, macOS, etc.
        ])

        dart_ls_dir = cls.ls_resources_dir(solidlsp_settings)
        dart_executable_path = deps.binary_path(dart_ls_dir)

        if not os.path.exists(dart_executable_path):
            deps.install(dart_ls_dir)

        return f"{dart_executable_path} language-server --client-id multilspy.dart"

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        """Language-specific LSP initialization parameters."""
        return {
            "capabilities": {},
            "initializationOptions": {
                "onlyAnalyzeProjectsWithOpenFiles": False,
                "closingLabels": False,
            },
            "rootPath": repository_absolute_path,
            "rootUri": pathlib.Path(repository_absolute_path).as_uri(),
            "workspaceFolders": [{"uri": root_uri, "name": os.path.basename(...)}],
        }

    def _start_server(self) -> None:
        """Language-specific server startup with LSP callbacks."""
        self.server.on_request("client/registerCapability", do_nothing)
        self.server.on_notification("language/status", do_nothing)
        # ... register other LSP callbacks
        self.server.start()
        init_response = self.server.send_request("initialize", initialize_params)
```

### Dependency Injection & Factory Pattern

**File**: `/workspaces/flow_squared/scratch/serena/src/serena/ls_manager.py` (lines 16-52)

```python
class LanguageServerFactory:
    """Dependency injection factory for creating language servers."""

    def __init__(
        self,
        project_root: str,
        encoding: str,
        ignored_patterns: list[str],
        ls_timeout: float | None = None,
        ls_specific_settings: dict | None = None,
        trace_lsp_communication: bool = False,
    ):
        self.project_root = project_root
        self.encoding = encoding
        self.ignored_patterns = ignored_patterns
        self.ls_timeout = ls_timeout
        self.ls_specific_settings = ls_specific_settings
        self.trace_lsp_communication = trace_lsp_communication

    def create_language_server(self, language: Language) -> SolidLanguageServer:
        """Create a language server instance for a specific language."""
        ls_config = LanguageServerConfig(
            code_language=language,
            ignored_paths=self.ignored_patterns,
            trace_lsp_communication=self.trace_lsp_communication,
            encoding=self.encoding,
        )

        return SolidLanguageServer.create(
            ls_config,
            self.project_root,
            timeout=self.ls_timeout,
            solidlsp_settings=SolidLSPSettings(
                solidlsp_dir=SerenaPaths().serena_user_home_dir,
                project_data_relative_path=SERENA_MANAGED_DIR_NAME,
                ls_specific_settings=self.ls_specific_settings or {},
            ),
        )
```

### Language Server Manager (Composition Layer)

**File**: `/workspaces/flow_squared/scratch/serena/src/serena/ls_manager.py` (lines 54-120)

```python
class LanguageServerManager:
    """Manages one or more language servers for a project."""

    def __init__(
        self,
        language_servers: dict[Language, SolidLanguageServer],
        language_server_factory: LanguageServerFactory | None = None,
    ):
        self._language_servers = language_servers
        self._language_server_factory = language_server_factory
        self._default_language_server = next(iter(language_servers.values()))

    @staticmethod
    def from_languages(
        languages: list[Language],
        factory: LanguageServerFactory
    ) -> "LanguageServerManager":
        """Creates manager with parallel language server startup."""
        language_servers: dict[Language, SolidLanguageServer] = {}
        threads = []

        def start_language_server(language: Language) -> None:
            language_server = factory.create_language_server(language)
            language_server.start()
            language_servers[language] = language_server

        # Start language servers in parallel threads
        for language in languages:
            thread = threading.Thread(
                target=start_language_server,
                args=(language,),
                name="StartLS:" + language.value
            )
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        return LanguageServerManager(language_servers, factory)

    def get_language_server(self, relative_path: str) -> SolidLanguageServer:
        """Select appropriate language server based on file."""
        ls: SolidLanguageServer | None = None
        if len(self._language_servers) > 1:
            for candidate in self._language_servers.values():
                if not candidate.is_ignored_path(relative_path, ignore_unsupported_files=True):
                    ls = candidate
                    break
        if ls is None:
            ls = self._default_language_server
        return ls
```

### Dependency Flow Diagram

```
Project (serena/project.py)
├── LanguageServerManager
│   ├── LanguageServerFactory
│   │   └── SolidLanguageServer.create()
│   │       └── Language.get_ls_class() → DartLanguageServer, PyRight, etc.
│   │
│   └── dict[Language, SolidLanguageServer]
│       ├── PyrightServer (Python)
│       ├── TypeScriptLanguageServer (TypeScript)
│       ├── DartLanguageServer (Dart)
│       ├── GoplsServer (Go)
│       └── ... (per configured language)
│
└── Tool System (file_tools, symbol_tools, etc.)
    └── Uses LanguageServerManager for symbol operations
```

### Clean Architecture Enforcement

| Principle | Implementation |
|-----------|----------------|
| ✅ No LSP protocol types leak into tool code | Tools receive domain objects, not LSP responses |
| ✅ Language servers managed by interface | `SolidLanguageServer` ABC defines contract |
| ✅ Factory isolates instantiation logic | `LanguageServerFactory` handles creation |
| ✅ Manager provides language selection | `LanguageServerManager` selects based on file |
| ✅ Lifecycle management centralized | Manager handles start/stop |

---

## C) Liftability Assessment

### Directly Reusable Code

#### 1. Project Root Detection Algorithm ⭐⭐⭐⭐⭐

- **File**: `/workspaces/flow_squared/scratch/serena/src/serena/cli.py:40-72`
- **Status**: Ready to lift as-is or with minimal modification
- **Code Quality**: Excellent - well-structured, documented, tested

**Adaptation for fs2**:
```python
# Extended marker priority for fs2
MARKER_PRIORITY = [
    (".fs2/config.yaml", "fs2"),
    ("fs2.yaml", "fs2"),
    ("pyproject.toml", "python"),
    ("setup.py", "python"),
    ("setup.cfg", "python"),
    ("package.json", "typescript"),
    ("tsconfig.json", "typescript"),
    ("go.mod", "go"),
    (".csproj", "csharp"),
    (".sln", "csharp"),
    (".git", "git"),
]
```

#### 2. Language Enum Pattern ⭐⭐⭐⭐

- **File**: `/workspaces/flow_squared/scratch/serena/src/solidlsp/ls_config.py:29-430`
- **Status**: Excellent pattern for fs2's language registration
- **Key Ideas**:
  - Lazy-loaded language class registry
  - Single enum value → type mapping
  - Support for experimental/deprecated variants

#### 3. Adapter Factory Pattern ⭐⭐⭐⭐

- **File**: `/workspaces/flow_squared/scratch/serena/src/serena/ls_manager.py:16-52`
- **Status**: Perfect for fs2's adapter management
- **Implementation**: Adapt for scanner adapters:
  - `ScannerAdapterFactory` replacing `LanguageServerFactory`
  - `ScannerAdapterManager` replacing `LanguageServerManager`
  - Language-specific scanner adapters replacing language server implementations

#### 4. Testing Approach ⭐⭐⭐⭐

- **File**: `/workspaces/flow_squared/scratch/serena/test/serena/test_cli_project_commands.py`
- **Status**: Excellent test patterns to adopt
- **Key Techniques**:
  - Real filesystem fixtures with cleanup
  - CWD manipulation for integration tests
  - No mocking - tests use actual file operations
  - Comprehensive boundary and edge case testing

### Utility Functions Worth Lifting

| Function | Source File | Purpose |
|----------|-------------|---------|
| `determine_programming_language_composition()` | `serena/util/inspection.py` | Language auto-detection |
| `FilenameMatcher` | `solidlsp/ls_config.py:15-26` | File filtering by extension |
| `GitignoreParser` | `serena/util/file_system.py` | `.gitignore` support |

### Patterns to Adopt

#### 1. Configuration Hierarchy

```
fs2 Adaptation:
    1. Command-line arguments
    2. Project-specific `.fs2/config.yaml`
    3. User config `~/.fs2/config.yaml`
    4. Environment variables (`FS2_*`)
    5. Defaults
```

#### 2. Dependency Injection

- Serena uses constructor injection for all dependencies
- **Recommendation**: Adopt for fs2 services and adapters
- Example: `ScannerAdapterFactory(project_root, encoding, language_priorities)`

#### 3. Error Handling

- Use custom exception hierarchies (e.g., `ScannerAdapterError`, `ProjectRootError`)
- Include actionable error messages with fix suggestions
- **File example**: `/workspaces/flow_squared/scratch/serena/src/solidlsp/ls_exceptions.py`

### What Needs Modification

#### 1. Runtime Dependency Management

- **Serena uses**: `RuntimeDependency`, `RuntimeDependencyCollection`
- **fs2 needs**: Different approach - scanner adapters use installed LSP servers
- **Adaptation**: May need registry for LSP server binary paths

#### 2. LSP Protocol Integration

- **Serena has**: Deep LSP knowledge and protocol handling
- **fs2 opportunity**: Could potentially leverage Serena's LSP adapters directly
- **Options**:
  - **A**: Direct integration with Serena's `SolidLanguageServer`
  - **B**: Extract LSP abstraction layer for fs2 use
  - **C**: Implement minimal LSP client (current Phase 0b approach)

#### 3. Caching Strategy

- **Serena caches**: Raw LSP document symbols in `.serena/cache/`
- **fs2 needs**: Cross-file relationship caching
- **Approach**: Adopt Serena's cache versioning pattern but store relationship data

---

## D) Testing Approach

### Project Root Detection Tests

**File**: `/workspaces/flow_squared/scratch/serena/test/serena/test_cli_project_commands.py:266-329`

**Pattern**: Real filesystem with temporary directories

```python
@pytest.fixture
def temp_project_dir():
    """Create a temporary directory for testing."""
    tmpdir = tempfile.mkdtemp()
    try:
        yield tmpdir
    finally:
        # Windows-specific cleanup delay to avoid PermissionError
        if os.name == "nt":
            time.sleep(0.2)
        shutil.rmtree(tmpdir, ignore_errors=True)

# Tests use actual filesystem operations
class TestFindProjectRoot:
    def test_finds_serena_from_subdirectory(self, temp_project_dir):
        # Create actual .serena/project.yml
        serena_dir = os.path.join(temp_project_dir, ".serena")
        os.makedirs(serena_dir)
        Path(os.path.join(serena_dir, "project.yml")).touch()

        # Create subdirectory
        subdir = os.path.join(temp_project_dir, "src", "nested")
        os.makedirs(subdir)

        # Change to subdirectory and test
        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            result = find_project_root(root=temp_project_dir)
            assert os.path.samefile(result, temp_project_dir)
        finally:
            os.chdir(original_cwd)
```

**Key Characteristics**:
- ✅ No mocking of filesystem
- ✅ Real `Path` operations
- ✅ Boundary testing with `root` parameter
- ✅ Windows compatibility (cleanup delay)
- ✅ CWD isolation (always restore)
- ✅ Comprehensive cases: priority, fallback, nested dirs

### LSP Integration Tests

**Pattern**: Language-specific test repositories

**File Structure**:
```
test/resources/repos/<language>/
├── test_repo/              # Real project with source files
│   ├── src/
│   ├── test/
│   └── .serena/project.yml # Serena project marker
└── conftest.py             # Language-specific test setup
```

**Test Organization**:
```
test/solidlsp/<language>/
├── test_<language>_basic.py
├── test_<language>_navigation.py
└── test_<language>_editing.py
```

### Snapshot Testing for Symbol Operations

**File**: `/workspaces/flow_squared/scratch/serena/test/serena/test_symbol_editing.py`

- Uses **inlinesnap** library for maintaining expected outputs
- Tests verify exact symbol structure changes during edits
- Snapshot failures trigger review of intentional vs. accidental changes

### Integration Test Pattern

**File**: `/workspaces/flow_squared/scratch/serena/test/serena/test_serena_agent.py`

- Full end-to-end test of SerenaAgent
- Creates projects, loads language servers, uses tools
- Tests composition and coordination of components

---

## E) Recommendations for fs2

### Short-term (Direct Lifts)

| Priority | Component | Target Location | Action |
|----------|-----------|-----------------|--------|
| 1 | Project Root Detection | `scripts/lsp/project_root.py` | Lift with extended markers |
| 2 | Language Enum | `scripts/lsp/language.py` | Adapt for scanner adapters |
| 3 | Test Patterns | `scripts/lsp/tests/` | Replicate real FS fixtures |
| 4 | Factory Pattern | `scripts/lsp/adapter_factory.py` | Adapt for LSP adapters |

### Medium-term (Integration Opportunities)

1. **Leverage Serena's LSP Infrastructure**
   - If fs2 wants deeper LSP integration: direct dependency on Serena's `SolidLanguageServer`
   - Alternative: Extract shared LSP abstraction

2. **Cross-file Relationship Caching**
   - Build on Serena's caching patterns (`cache_version` strategy)
   - Store relationship data alongside document symbols

3. **Configuration Hierarchy**
   - Adopt Serena's precedence model for fs2 config

### Code Locations for Reference

**Core Patterns**:
| Pattern | File | Lines |
|---------|------|-------|
| Project root detection | `serena/src/serena/cli.py` | 40-72 |
| Language enum | `serena/src/solidlsp/ls_config.py` | 29-430 |
| Factory pattern | `serena/src/serena/ls_manager.py` | 16-52 |
| Manager pattern | `serena/src/serena/ls_manager.py` | 54-120 |
| Adapter example | `serena/src/solidlsp/language_servers/dart_language_server.py` | 17-151 |

**Tests**:
| Test Area | File | Lines |
|-----------|------|-------|
| Project root tests | `serena/test/serena/test_cli_project_commands.py` | 266-329 |
| Integration tests | `serena/test/serena/test_serena_agent.py` | Full file |

---

## F) Gaps and Opportunities

### Current Gaps in Serena

| Gap | Description | fs2 Opportunity |
|-----|-------------|-----------------|
| No monorepo support | Simple "deepest marker wins" | Add monorepo marker detection |
| No workspace detection | Single project focus | Multi-project workspace support |
| CWD-based detection | Relies on current directory | File-path-based detection |

### Monorepo Markers to Add

```python
# Monorepo markers (check before standard markers)
MONOREPO_MARKERS = [
    ("lerna.json", "javascript"),
    ("pnpm-workspace.yaml", "javascript"),
    ("rush.json", "javascript"),
    ("Cargo.toml[workspace]", "rust"),  # Check for [workspace] section
    ("go.work", "go"),
]
```

### fs2 Enhancements Over Serena

1. **File-path-based detection** (not CWD-based)
   - `find_project_root(file_path, workspace_root)` vs Serena's CWD approach

2. **Language-specific marker awareness**
   - Different markers per language
   - Auto-detection from file extension

3. **Workspace root fallback**
   - Never return None - fall back to workspace_root or file's parent

4. **First-in-list priority** (documented)
   - When multiple markers at same level, first in list wins

---

## Appendix: Key File Paths in Serena

```
/workspaces/flow_squared/scratch/serena/
├── src/
│   ├── serena/
│   │   ├── cli.py                    # Project root detection (lines 40-72)
│   │   ├── ls_manager.py             # Factory + Manager patterns
│   │   ├── project.py                # Project coordination
│   │   └── util/
│   │       ├── inspection.py         # Language detection
│   │       └── file_system.py        # GitignoreParser
│   └── solidlsp/
│       ├── ls.py                     # SolidLanguageServer ABC
│       ├── ls_config.py              # Language enum + FilenameMatcher
│       ├── ls_exceptions.py          # Exception hierarchy
│       └── language_servers/
│           ├── dart_language_server.py
│           ├── pyright_server.py
│           ├── typescript_language_server.py
│           └── gopls_server.py
└── test/
    ├── serena/
    │   ├── test_cli_project_commands.py  # Project root tests
    │   ├── test_serena_agent.py          # Integration tests
    │   └── test_symbol_editing.py        # Snapshot tests
    └── solidlsp/
        └── <language>/                    # Per-language LSP tests
```
