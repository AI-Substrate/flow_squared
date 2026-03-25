# Workshop: SCIP Language Boot Requirements

**Type**: Integration Pattern
**Plan**: 038-scip-cross-file-rels
**Spec**: [cross-file-rels-spec.md](../cross-file-rels-spec.md)
**Created**: 2026-03-16
**Status**: Draft

**Related Documents**:
- [scip-exploration.md](../scip-exploration.md) — Hands-on testing of all 4 indexers
- [004-multi-project.md](004-multi-project.md) — Multi-language project detection (Serena-era, still relevant for detection)

---

## Purpose

Define exactly what each SCIP language indexer needs to produce an `index.scip` file — project files, toolchain prerequisites, install commands, indexing commands, and failure modes. This is the reference document for implementing per-language `SCIPLanguageAdapter` subclasses and the `fs2 discover-projects` / `fs2 setup-scip` CLI commands.

## Key Questions Addressed

- What must exist on disk before each indexer can run?
- What toolchain must be installed (and how)?
- What command produces the `index.scip` file?
- Can it work on a bare directory or does it need a project file?
- What are the common failure modes and how do we detect/report them?
- How does fs2 discover which languages are present?

---

## Boot Requirement Summary

| Language | Indexer | Install | Project File | Needs Build? | Can Index Raw Dir? |
|----------|---------|---------|-------------|-------------|-------------------|
| Python | scip-python | `npm i -g @sourcegraph/scip-python` | None (pyproject.toml optional) | ❌ | ✅ |
| TypeScript | scip-typescript | `npm i -g @sourcegraph/scip-typescript` | `tsconfig.json` | ❌ (needs `npm install`) | ⚠️ `--infer-tsconfig` |
| JavaScript | scip-typescript | Same as TypeScript | `package.json` | ❌ (needs `npm install`) | ⚠️ `--infer-tsconfig` |
| Go | scip-go | `go install github.com/sourcegraph/scip-go/cmd/scip-go@latest` | `go.mod` | ❌ | ❌ |
| C# | scip-dotnet | `dotnet tool install --global scip-dotnet` | `.csproj` or `.sln` | ✅ `dotnet build` | ❌ |
| Java | scip-java | Coursier or Docker | `pom.xml` or `build.gradle` | ✅ (Maven/Gradle) | ❌ |
| Rust | rust-analyzer | `cargo install rust-analyzer` | `Cargo.toml` | ❌ | ❌ |
| C/C++ | scip-clang | Binary from GitHub releases | `compile_commands.json` | ✅ (CMake/Bear) | ❌ |
| Ruby | scip-ruby | gem or binary release | `Gemfile` + `sorbet/config` | ❌ | ⚠️ Partial |

---

## Per-Language Boot Specifications

### Python

```
┌─────────────────────────────────────────────────────────────┐
│ PREREQUISITES                                                │
│   • Node.js v16+ (scip-python is an npm package)            │
│   • Python 3.10+ in PATH                                    │
│   • Virtual env activated with deps installed                │
│                                                              │
│ INSTALL                                                      │
│   $ npm install -g @sourcegraph/scip-python                 │
│                                                              │
│ PROJECT FILE                                                 │
│   None required. Picks up pyproject.toml if present.         │
│   Uses --project-name flag for symbol namespacing.           │
│                                                              │
│ INDEX COMMAND                                                │
│   $ cd /path/to/project                                     │
│   $ scip-python index . --project-name=my-project           │
│   → produces index.scip                                      │
│                                                              │
│ DISCOVERY MARKERS                                            │
│   pyproject.toml, setup.py, setup.cfg, requirements.txt     │
│                                                              │
│ FAILURE MODES                                                │
│   • Node.js not installed → "command not found"              │
│   • Python not in PATH → empty/partial index                 │
│   • Missing venv deps → unresolved imports (still indexes)   │
│   • OOM on large codebases → NODE_OPTIONS="--max-old-space  │
│     -size=8192"                                              │
└─────────────────────────────────────────────────────────────┘
```

**fs2 adapter config**:
```yaml
projects:
  - type: python
    path: .
    project_file: pyproject.toml  # optional, just for display
```

**Indexer quirks**:
- Built on Pyright (Microsoft's Python type checker) — same engine as Pylance
- Runs in Node.js despite being a Python indexer
- `--project-name` affects symbol namespacing: symbols become `scip-python python {project-name} 0.1.0 ...`
- Picks up the nearest `pyproject.toml` for project root detection
- Can index without a venv, but quality degrades (unresolved third-party imports)

---

### TypeScript / JavaScript

```
┌─────────────────────────────────────────────────────────────┐
│ PREREQUISITES                                                │
│   • Node.js v18+ (v20 recommended)                          │
│   • npm/yarn/pnpm for dependency install                    │
│                                                              │
│ INSTALL                                                      │
│   $ npm install -g @sourcegraph/scip-typescript             │
│                                                              │
│ PROJECT FILE                                                 │
│   TypeScript: tsconfig.json (required)                       │
│   JavaScript: none (use --infer-tsconfig)                    │
│                                                              │
│ PRE-INDEX SETUP                                              │
│   $ npm install  (or yarn/pnpm install)                     │
│   Must install node_modules for type resolution              │
│                                                              │
│ INDEX COMMAND (TypeScript)                                    │
│   $ cd /path/to/project                                     │
│   $ scip-typescript index --output index.scip               │
│   → produces index.scip                                      │
│                                                              │
│ INDEX COMMAND (JavaScript, no tsconfig)                       │
│   $ scip-typescript index --infer-tsconfig --output idx.scip│
│                                                              │
│ INDEX COMMAND (Monorepo - yarn workspaces)                   │
│   $ scip-typescript index --yarn-workspaces                 │
│                                                              │
│ INDEX COMMAND (Monorepo - pnpm workspaces)                   │
│   $ scip-typescript index --pnpm-workspaces                 │
│                                                              │
│ DISCOVERY MARKERS                                            │
│   tsconfig.json (TypeScript)                                 │
│   package.json (JavaScript — check for tsconfig first)       │
│                                                              │
│ FAILURE MODES                                                │
│   • Missing node_modules → "Cannot find module" warnings     │
│   • No tsconfig.json (TS) → error, must use --infer-tsconfig│
│   • OOM → NODE_OPTIONS="--max-old-space-size=16000"          │
│   • Stalled → add --progress-bar to diagnose                │
│   • Memory → --no-global-caches reduces usage               │
└─────────────────────────────────────────────────────────────┘
```

**fs2 adapter config**:
```yaml
projects:
  - type: typescript
    path: ./frontend
    project_file: tsconfig.json
  # OR for JS-only:
  - type: javascript
    path: ./scripts
    project_file: package.json
    options:
      infer_tsconfig: true
```

**Indexer quirks**:
- Same indexer handles both TypeScript and JavaScript
- `--infer-tsconfig` creates a temporary tsconfig for JS projects
- Workspace flags (`--yarn-workspaces`, `--pnpm-workspaces`) for monorepos
- `@types/*` packages significantly improve JS indexing quality
- Output path defaults to `index.scip` in cwd

---

### Go

```
┌─────────────────────────────────────────────────────────────┐
│ PREREQUISITES                                                │
│   • Go 1.19+ toolchain                                      │
│                                                              │
│ INSTALL                                                      │
│   $ go install github.com/sourcegraph/scip-go/cmd/          │
│     scip-go@latest                                           │
│   Binary lands in ~/go/bin/scip-go                          │
│                                                              │
│ PROJECT FILE                                                 │
│   go.mod (required — must be a Go module)                    │
│                                                              │
│ INDEX COMMAND                                                │
│   $ cd /path/to/module                                      │
│   $ scip-go --output=index.scip ./...                       │
│   → produces index.scip                                      │
│                                                              │
│ DISCOVERY MARKERS                                            │
│   go.mod                                                     │
│                                                              │
│ FAILURE MODES                                                │
│   • No go.mod → "not in a module" error                     │
│   • Missing deps → "cannot find package" (run go mod tidy)  │
│   • Wrong Go version → version mismatch warnings            │
└─────────────────────────────────────────────────────────────┘
```

**fs2 adapter config**:
```yaml
projects:
  - type: go
    path: ./services/auth
    project_file: go.mod
```

**Indexer quirks**:
- Simplest indexer — just point at module root and go
- `./...` pattern indexes all packages recursively
- Symbols include module path: `scip-go gomod example.com/app hash \`example.com/app/pkg\`/Symbol#`
- No separate build step needed
- Uses Go's own module resolution for cross-package references

---

### C# / .NET

```
┌─────────────────────────────────────────────────────────────┐
│ PREREQUISITES                                                │
│   • .NET SDK 8.0+ (dotnet CLI)                              │
│                                                              │
│ INSTALL                                                      │
│   $ dotnet tool install --global scip-dotnet                │
│   Binary lands in ~/.dotnet/tools/scip-dotnet               │
│   Ensure ~/.dotnet/tools is in PATH                         │
│                                                              │
│ PROJECT FILE                                                 │
│   .csproj (single project) or .sln (solution)               │
│                                                              │
│ PRE-INDEX SETUP                                              │
│   $ dotnet build  (must compile first!)                     │
│                                                              │
│ INDEX COMMAND                                                │
│   $ cd /path/to/project                                     │
│   $ scip-dotnet index                                       │
│   → produces index.scip                                      │
│                                                              │
│ INDEX COMMAND (specific project)                              │
│   $ scip-dotnet index --working-directory /path/to/project  │
│                                                              │
│ DISCOVERY MARKERS                                            │
│   *.csproj, *.sln, *.fsproj, *.vbproj                      │
│                                                              │
│ FAILURE MODES                                                │
│   • Not built → MSBuild errors during indexing              │
│   • Wrong .NET version → target framework mismatch          │
│   • Multiple projects → index at .sln level                 │
│   • net9.0 on some machines → MSBuild target errors         │
│     (we hit this — net8.0 works more reliably)              │
└─────────────────────────────────────────────────────────────┘
```

**fs2 adapter config**:
```yaml
projects:
  - type: dotnet
    path: ./api
    project_file: MyApp.sln  # or MyApp.csproj
```

**Indexer quirks**:
- **Must build before indexing** — uses Roslyn compiler APIs, needs compiled metadata
- Built on Roslyn (same compiler used by Visual Studio)
- Indexes 6 documents for 3 source files (includes generated files like GlobalUsings.g.cs)
- `ImplicitUsings` must be enabled in .csproj or add explicit `using` statements
- Docker image available: `sourcegraph/scip-dotnet:latest`
- **PATH gotcha**: `~/.dotnet/tools` must be in PATH after install

---

### Java (Not Yet Tested — From Documentation)

```
┌─────────────────────────────────────────────────────────────┐
│ PREREQUISITES                                                │
│   • JDK 8, 11, 17, or 21                                   │
│   • Maven or Gradle build system                            │
│   • Coursier (launcher) — or use Docker                     │
│                                                              │
│ INSTALL (Coursier)                                           │
│   $ brew install coursier/formulas/coursier                 │
│   $ cs launch com.sourcegraph:scip-java_2.13:LATEST --help │
│                                                              │
│ INSTALL (Docker — recommended)                               │
│   No install needed — uses sourcegraph/scip-java image      │
│                                                              │
│ PROJECT FILE                                                 │
│   pom.xml (Maven) or build.gradle / build.gradle.kts        │
│                                                              │
│ INDEX COMMAND (Docker)                                        │
│   $ docker run -v $(pwd):/sources \                         │
│       sourcegraph/scip-java:latest scip-java index          │
│   → produces index.scip                                      │
│                                                              │
│ INDEX COMMAND (Coursier)                                      │
│   $ cs launch com.sourcegraph:scip-java_2.13:LATEST -- index│
│   → produces index.scip                                      │
│                                                              │
│ DISCOVERY MARKERS                                            │
│   pom.xml, build.gradle, build.gradle.kts                   │
│                                                              │
│ FAILURE MODES                                                │
│   • Wrong JDK version → set JAVA_HOME or                    │
│     SCIP_JAVA_VERSION env var                                │
│   • Build fails → must fix build before indexing            │
│   • Side effects: may clean compile caches                  │
└─────────────────────────────────────────────────────────────┘
```

---

### Rust (Not Yet Tested — From Documentation)

```
┌─────────────────────────────────────────────────────────────┐
│ PREREQUISITES                                                │
│   • Rust toolchain (rustup + cargo)                         │
│   • rust-analyzer installed                                  │
│                                                              │
│ INSTALL                                                      │
│   $ rustup component add rust-analyzer                      │
│   (or: cargo install rust-analyzer)                         │
│                                                              │
│ PROJECT FILE                                                 │
│   Cargo.toml (required)                                      │
│                                                              │
│ INDEX COMMAND                                                │
│   $ cd /path/to/crate                                       │
│   $ rust-analyzer scip .                                    │
│   → produces index.scip                                      │
│                                                              │
│ DISCOVERY MARKERS                                            │
│   Cargo.toml                                                 │
│                                                              │
│ FAILURE MODES                                                │
│   • Missing deps → cargo fetch first                        │
│   • Workspace vs crate → index at workspace root            │
└─────────────────────────────────────────────────────────────┘
```

---

## SCIP CLI Tool (Inspector)

The `scip` CLI is essential for debugging — it reads any `index.scip` file regardless of which indexer created it.

```
┌─────────────────────────────────────────────────────────────┐
│ INSTALL                                                      │
│   Binary release from GitHub:                                │
│   $ curl -sL https://github.com/sourcegraph/scip/releases/ │
│     download/v0.6.1/scip-darwin-arm64.tar.gz | tar xz       │
│   $ mv scip ~/bin/  (or /usr/local/bin/)                    │
│                                                              │
│ COMMANDS                                                     │
│   $ scip print index.scip    # Human-readable dump          │
│   $ scip stats index.scip    # Document/occurrence counts   │
│   $ scip snapshot index.scip # Annotated source view        │
│   $ scip convert index.scip  # Convert to other formats     │
└─────────────────────────────────────────────────────────────┘
```

---

## Project Discovery Algorithm

For `fs2 discover-projects`, scan from `scan_root` downward:

```python
DISCOVERY_MARKERS: dict[str, list[str]] = {
    "python":     ["pyproject.toml", "setup.py", "setup.cfg"],
    "typescript": ["tsconfig.json"],
    "javascript": ["package.json"],
    "go":         ["go.mod"],
    "dotnet":     ["*.csproj", "*.sln"],
    "java":       ["pom.xml", "build.gradle", "build.gradle.kts"],
    "rust":       ["Cargo.toml"],
    "cpp":        ["CMakeLists.txt", "compile_commands.json"],
    "ruby":       ["Gemfile"],
}

# Priority when multiple markers in same dir:
# TypeScript > JavaScript (tsconfig.json means TS, package.json alone means JS)
# .sln > .csproj (solution encompasses projects)
# Cargo.toml at workspace root > nested crate Cargo.toml

# Skip directories:
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "bin", "obj",
             ".venv", "venv", "dist", "build", "target"}
```

### Discovery Output Example

```
$ fs2 discover-projects

  Scanning /Users/dev/myrepo...

  #  Type        Path                    Project File         SCIP Indexer
  ── ─────────── ─────────────────────── ──────────────────── ─────────────────
  1  python      .                       pyproject.toml       scip-python ✅
  2  typescript  frontend/               tsconfig.json        scip-typescript ✅
  3  go          services/auth/          go.mod               scip-go ✅
  4  dotnet      services/billing/       Billing.csproj       scip-dotnet ✅
  5  javascript  scripts/                package.json         scip-typescript ⚠️

  ✅ = indexer installed    ⚠️ = indexer installed (--infer-tsconfig needed)
  ❌ = indexer not installed

  Add to config:  fs2 add-project 1 2 3
  Install indexer: fs2 setup-scip --python --typescript --go
```

---

## Adapter Boot Sequence

Each `SCIPLanguageAdapter` subclass implements this boot contract:

```python
class SCIPLanguageAdapter(ABC):
    """Per-language SCIP adapter boot contract."""

    @abstractmethod
    def language_name(self) -> str: ...

    @abstractmethod
    def indexer_command(self) -> str:
        """The CLI command name (e.g., 'scip-python')."""
        ...

    @abstractmethod
    def is_installed(self) -> bool:
        """Check if the indexer binary is available on PATH."""
        ...

    @abstractmethod
    def install_instructions(self) -> str:
        """Human-readable install instructions."""
        ...

    @abstractmethod
    def discovery_markers(self) -> list[str]:
        """Files that indicate this language's project exists."""
        ...

    @abstractmethod
    def needs_build(self) -> bool:
        """Whether `build_command()` must run before indexing."""
        ...

    @abstractmethod
    def build_command(self, project_root: str) -> list[str] | None:
        """Pre-index build command (e.g., ['dotnet', 'build'])."""
        ...

    @abstractmethod
    def index_command(self, project_root: str, output: str) -> list[str]:
        """Command to produce index.scip."""
        ...

    @abstractmethod
    def validate_project(self, project_root: str) -> tuple[bool, str]:
        """Check project is valid for indexing. Returns (ok, message)."""
        ...
```

---

## Open Questions

### Q1: Should fs2 auto-install SCIP indexers?

**OPEN**: Options:
- **A**: `fs2 setup-scip --python` installs for you (via npm/go/dotnet)
- **B**: fs2 just tells you what to install (instructions only)
- **C**: Hybrid — offer to install, user confirms

### Q2: How to handle monorepo workspace indexers?

**OPEN**: TypeScript has `--yarn-workspaces` and `--pnpm-workspaces`. Should we:
- Auto-detect and use the right flag?
- Let the user specify in config?
- Default to per-tsconfig indexing?

### Q3: Should we support Docker-based indexers?

**OPEN**: Java's recommended path is Docker. Should we:
- Support `docker run` as an indexer command?
- Require local install only?
- Make Docker an option in config?
