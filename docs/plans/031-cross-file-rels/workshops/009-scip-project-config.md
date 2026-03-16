# Workshop: SCIP Project Configuration

**Type**: Storage Design / CLI Flow
**Plan**: 031-cross-file-rels
**Spec**: [cross-file-rels-spec.md](../cross-file-rels-spec.md)
**Created**: 2026-03-16
**Status**: Draft

**Related Documents**:
- [007-scip-language-boot.md](007-scip-language-boot.md) — Per-language boot requirements
- [008-scip-cross-language-standardisation.md](008-scip-cross-language-standardisation.md) — Adapter standardisation
- [004-multi-project.md](004-multi-project.md) — Multi-project detection (Serena-era)
- [scip-exploration.md](../scip-exploration.md) — Empirical SCIP testing

---

## Purpose

Design how users declare which language projects exist in their codebase so that SCIP indexers know what to index. This is the configuration bridge between "I have source files here" (scan_paths) and "here are the compilable projects SCIP should index" (projects).

## Key Questions Addressed

- Should we extend `scan_paths` or create a separate concept?
- What does a project entry look like in config?
- How does auto-discovery interact with explicit config?
- What's the CLI workflow for discovering and adding projects?
- How does this integrate with the existing config system (pydantic, YAML, env vars)?

---

## Current State

### scan_paths Today

```python
# src/fs2/config/objects.py — ScanConfig
class ScanConfig(BaseModel):
    __config_path__: ClassVar[str] = "scan"

    scan_paths: list[str] = ["."]       # ← Just strings. No type info.
    ignore_patterns: list[str] = []
    max_file_size_kb: int = 500
    respect_gitignore: bool = True
    follow_symlinks: bool = False
    sample_lines_for_large_files: int = 1000
```

```yaml
# .fs2/config.yaml
scan:
  scan_paths:
    - "."
  ignore_patterns:
    - "node_modules"
    - ".venv"
```

### cross_file_rels Today

```python
class CrossFileRelsConfig(BaseModel):
    __config_path__: ClassVar[str] = "cross_file_rels"

    enabled: bool = True
    parallel_instances: int = 15        # Serena-specific
    serena_base_port: int = 8330        # Serena-specific
    timeout_per_node: float = 5.0
    languages: list[str] = ["python"]   # ← Flat list, no path association
```

### The Gap

`scan_paths` tells fs2 **where to find files** for AST parsing. But it says nothing about:
- What **language projects** exist (Python? Go? C#?)
- Where the **project root** is (where `go.mod` or `tsconfig.json` lives)
- What **project file** to use (which `.csproj`? which `tsconfig.json`?)

SCIP indexers need all three. Today's auto-detection (from workshop 004) walks the directory tree looking for marker files — but this is fragile and can't handle ambiguity (two `tsconfig.json` files? which one?).

---

## Design Decision: scan_paths vs Projects

### Why NOT Extend scan_paths

`scan_paths` and "projects" are **different concerns**:

| Concern | scan_paths | projects |
|---------|-----------|----------|
| **Purpose** | Which dirs to scan for files | Which roots to run SCIP against |
| **Granularity** | Directory paths | Language + root + project file |
| **Overlap** | May scan `tests/fixtures/go/` | But that's NOT a Go project |
| **Scope** | ALL files (AST parsing) | ONLY compilable projects |
| **Failure** | Missing path → warning | Missing project file → skip SCIP |

**Example of the mismatch**:
```yaml
scan:
  scan_paths:
    - "."   # ← Scans EVERYTHING including test fixtures

# But SCIP should only index the real Python project at root,
# NOT the Go/Rust/Java fixture files in tests/fixtures/samples/
```

If we shoved project type info into `scan_paths`, we'd conflate "scan this directory for files" with "this is a compilable project for SCIP". These should stay separate.

### Recommendation: Separate `projects` Section

```yaml
scan:
  scan_paths: ["."]    # ← Unchanged. Still just "where to find files."

projects:              # ← NEW. "What language projects exist here."
  - type: python
    path: .
  - type: typescript
    path: frontend
    project_file: tsconfig.json
```

**Why**:
- Clean separation of concerns
- Non-breaking — existing configs keep working
- Discoverable — `fs2 discover-projects` populates this section
- Optional — if missing, fall back to auto-detection or skip SCIP
- Each project entry maps 1:1 to one SCIP indexer invocation

---

## The `projects` Config Model

### Pydantic Model

```python
class ProjectConfig(BaseModel):
    """A single language project for SCIP indexing.

    Represents one compilable project root that a SCIP indexer
    should process. Each entry produces one index.scip file.

    Attributes:
        type: Language identifier (python, typescript, javascript,
              go, dotnet, java, rust, cpp, ruby).
        path: Path to project root, relative to scan_root.
              This is where the SCIP indexer runs.
        project_file: Specific project file to use (optional).
              e.g., "tsconfig.json", "MyApp.sln", "go.mod".
              If omitted, indexer uses its default discovery.
        enabled: Whether to index this project (default: True).
              Lets users temporarily skip a project.
        options: Indexer-specific options (optional).
              e.g., {"infer_tsconfig": true} for JS projects.
    """

    type: str  # Validated against known types
    path: str = "."
    project_file: str | None = None
    enabled: bool = True
    options: dict[str, Any] = {}

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        known = {
            "python", "typescript", "javascript",
            "go", "dotnet", "java", "rust", "cpp", "ruby",
        }
        if v not in known:
            raise ValueError(
                f"Unknown project type '{v}'. "
                f"Known types: {', '.join(sorted(known))}"
            )
        return v


class ProjectsConfig(BaseModel):
    """Configuration for SCIP project indexing.

    Path: projects (e.g., FS2_PROJECTS in env)
    """

    __config_path__: ClassVar[str] = "projects"

    projects: list[ProjectConfig] = []
    auto_discover: bool = True  # Fall back to marker detection
    scip_cache_dir: str = ".fs2/scip"  # Where to store index.scip files

    @property
    def enabled_projects(self) -> list[ProjectConfig]:
        return [p for p in self.projects if p.enabled]
```

### YAML Examples

#### Minimal (single Python project)

```yaml
projects:
  - type: python
    path: .
```

#### Full-stack app (Python + TypeScript)

```yaml
projects:
  - type: python
    path: .
    project_file: pyproject.toml
  - type: typescript
    path: frontend
    project_file: tsconfig.json
```

#### Monorepo

```yaml
projects:
  - type: python
    path: services/auth
  - type: go
    path: services/billing
    project_file: go.mod
  - type: typescript
    path: web
    project_file: tsconfig.json
  - type: dotnet
    path: services/payments
    project_file: Payments.sln
```

#### JavaScript with options

```yaml
projects:
  - type: javascript
    path: scripts
    options:
      infer_tsconfig: true
```

#### Temporarily disable one project

```yaml
projects:
  - type: python
    path: .
  - type: typescript
    path: frontend
    enabled: false  # ← Skip for now (broken tsconfig)
```

---

## Auto-Discovery Fallback

When `projects` is empty or `auto_discover: true`, fs2 walks the scan root looking for marker files. This is the **same algorithm** from workshop 004, now producing `ProjectConfig` entries:

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

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "bin", "obj",
    ".venv", "venv", "dist", "build", "target",
}
```

### Discovery Priority Rules

When multiple markers exist in the same directory:
1. `tsconfig.json` → TypeScript (takes precedence over `package.json` → JavaScript)
2. `.sln` → .NET solution (takes precedence over `.csproj` for the same path)
3. `Cargo.toml` at workspace root → Rust workspace (skip nested crate `Cargo.toml`)
4. Don't discover projects under `tests/fixtures/`, `node_modules/`, or other excluded dirs

### Explicit Config Overrides Discovery

```
IF projects.projects is non-empty:
    use explicit projects only (even if auto_discover=true,
    explicit projects take precedence for their paths)
    auto_discover fills in additional paths NOT covered by explicit entries

IF projects.projects is empty AND auto_discover is true:
    run full discovery

IF projects.projects is empty AND auto_discover is false:
    skip SCIP entirely (no cross-file rels from SCIP)
```

---

## CLI Workflow: `fs2 discover-projects`

### Command Design

```
$ fs2 discover-projects

  Scanning /Users/dev/myrepo for language projects...

  #  Type         Path                    Project File         Indexer
  ── ──────────── ─────────────────────── ──────────────────── ──────────────────
  1  python       .                       pyproject.toml       scip-python ✅
  2  typescript   frontend/               tsconfig.json        scip-typescript ✅
  3  go           services/auth/          go.mod               scip-go ✅
  4  javascript   scripts/                package.json         scip-typescript ⚠️

  ✅ = indexer installed    ⚠️ = needs --infer-tsconfig    ❌ = indexer not found

  Add to config:
    fs2 add-project 1 2 3          # Add specific projects
    fs2 add-project --all          # Add all discovered projects
```

### Command: `fs2 add-project`

```
$ fs2 add-project 1 2 3

  Added 3 projects to .fs2/config.yaml:

    projects:
      - type: python
        path: .
        project_file: pyproject.toml
      - type: typescript
        path: frontend
        project_file: tsconfig.json
      - type: go
        path: services/auth
        project_file: go.mod

  Run `fs2 scan` to index cross-file relationships.
```

### Edge Cases

```
$ fs2 discover-projects

  Scanning /Users/dev/empty-repo...

  No language projects found.

  Tip: fs2 looks for project markers like pyproject.toml, tsconfig.json,
  go.mod, etc. If your project uses a non-standard layout, add projects
  manually:

    fs2 add-project --type python --path . --project-file pyproject.toml

  Or edit .fs2/config.yaml directly:

    projects:
      - type: python
        path: .
```

```
$ fs2 discover-projects

  # When some indexers aren't installed:

  3  dotnet       services/billing/       Billing.csproj       scip-dotnet ❌

  Install missing indexers:
    dotnet tool install --global scip-dotnet
```

---

## Integration with CrossFileRelsConfig

### Migration: Serena → SCIP

The existing `CrossFileRelsConfig` gains a `provider` field:

```python
class CrossFileRelsConfig(BaseModel):
    __config_path__: ClassVar[str] = "cross_file_rels"

    enabled: bool = True
    provider: str = "scip"  # NEW: "scip" or "serena"

    # SCIP-specific (new):
    # (projects come from ProjectsConfig, not here)

    # Serena-specific (existing, deprecated):
    parallel_instances: int = 15
    serena_base_port: int = 8330
    timeout_per_node: float = 5.0
    languages: list[str] = ["python"]  # Deprecated — use projects instead
```

### How Scan Uses Projects

```python
# In CrossFileRelsStage:

async def execute(self, context: PipelineContext) -> PipelineContext:
    config = self._config.require(CrossFileRelsConfig)

    if not config.enabled:
        return context  # Skip

    if config.provider == "scip":
        projects_config = self._config.require(ProjectsConfig)
        projects = projects_config.enabled_projects

        if not projects and projects_config.auto_discover:
            projects = self._discover_projects(context.scan_root)

        for project in projects:
            adapter = self._get_adapter(project.type)
            if not adapter.is_installed():
                log.warning(f"Skipping {project.type}: {adapter.install_instructions()}")
                continue

            index_path = adapter.run_indexer(project)
            edges = adapter.extract_cross_file_edges(index_path, context.known_node_ids)
            context.cross_file_edges.extend(edges)

    elif config.provider == "serena":
        # Existing Serena path (deprecated)
        ...
```

---

## Config File Layout: Before and After

### Before (current)

```yaml
# .fs2/config.yaml
scan:
  scan_paths: ["."]
  ignore_patterns: ["node_modules", ".venv"]

cross_file_rels:
  enabled: true
  parallel_instances: 15
  serena_base_port: 8330
  languages: ["python"]
```

### After (with SCIP)

```yaml
# .fs2/config.yaml
scan:
  scan_paths: ["."]
  ignore_patterns: ["node_modules", ".venv"]

projects:                          # ← NEW section
  - type: python
    path: .
  - type: typescript
    path: frontend
    project_file: tsconfig.json

cross_file_rels:
  enabled: true
  provider: scip                   # ← NEW field (default)
  # Serena fields still work for backward compat
```

### Minimal Config (auto-discover)

```yaml
# .fs2/config.yaml — nothing to add!
# auto_discover: true is the default.
# fs2 scan will find projects automatically.
```

---

## Environment Variable Support

Following the existing `FS2_` prefix pattern:

```bash
# Disable cross-file rels
FS2_CROSS_FILE_RELS__ENABLED=false

# Override provider
FS2_CROSS_FILE_RELS__PROVIDER=serena

# Projects can't easily be expressed as env vars (nested list).
# This is fine — projects are a YAML/CLI concern.
```

---

## Integration with `fs2 init`

When `fs2 init` creates a new `.fs2/config.yaml`, it should:

1. Run project discovery silently
2. Include discovered projects as commented-out examples:

```yaml
# .fs2/config.yaml (generated by fs2 init)
scan:
  scan_paths: ["."]
  ignore_patterns: ["node_modules", ".venv"]

# Detected language projects (uncomment to pin):
# projects:
#   - type: python
#     path: .
#     project_file: pyproject.toml
```

---

## Open Questions

### Q1: Should `projects` be top-level or nested under `scan`?

**Option A** (recommended): Top-level `projects:` section
```yaml
scan:
  scan_paths: ["."]
projects:
  - type: python
```

**Option B**: Nested under `scan`
```yaml
scan:
  scan_paths: ["."]
  projects:
    - type: python
```

**Recommendation**: **Option A** — `projects` is a distinct concern from scan file discovery. It's used by cross-file rels, not by the file scanner. Top-level keeps it visually separate and allows independent evolution.

### Q2: Should auto_discover be the default?

**RESOLVED**: Yes. If no `projects` section exists, fs2 auto-discovers using marker files. This means zero-config works for most repos. Users only need explicit config when:
- Auto-discovery picks up the wrong project
- They want to exclude a project
- They need indexer-specific options
- The project layout is non-standard

### Q3: Should `type` allow aliases?

**OPEN**: Should we accept `ts` for `typescript`, `cs` for `dotnet`, `csharp` for `dotnet`?

Options:
- **A**: Strict names only (python, typescript, go, dotnet) — simple, unambiguous
- **B**: Accept aliases, normalize internally — friendlier
- **C**: Accept aliases in CLI, strict in YAML — compromise

### Q4: Should `project_file` be validated at config load time?

**RESOLVED**: No. Validate at index time. The project file might not exist yet (pre-build), or might be on a different branch. Config validation checks types and field formats; file existence is a runtime concern.

### Q5: What about projects that span multiple scan_paths?

**OPEN**: If `scan_paths` is `["src", "lib"]` and a Python project spans both, the project `path` should probably be `.` (the common parent). This is fine — SCIP indexes from the project root, not from scan_paths.
