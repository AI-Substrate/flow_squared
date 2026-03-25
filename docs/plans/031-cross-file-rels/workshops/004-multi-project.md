# Workshop: Multi-Language & Multi-Project Serena Resolution

**Type**: Integration Pattern
**Plan**: 031-cross-file-rels
**Spec**: [cross-file-rels-spec.md](../cross-file-rels-spec.md)
**Created**: 2026-03-12
**Status**: Draft

**Related Documents**:
- [002-serena-benchmarks.md](002-serena-benchmarks.md) — Benchmark data, instance pool design
- [001-edge-storage.md](001-edge-storage.md) — Edge storage in DiGraph

---

## Purpose

Design how the CrossFileRelsStage handles real-world codebases that contain:
- **Multiple languages** (e.g., Python + TypeScript in one repo)
- **Multiple project roots** (e.g., monorepo with `backend/`, `frontend/`, `shared/`)
- **Test fixtures in other languages** (e.g., `tests/fixtures/ast_samples/` containing Go, Rust, C# files that are parsed by fs2 but aren't real projects)
- **Multiple distinct applications** (e.g., a monorepo with two unrelated Node apps)

The key question: **Serena instances are bound to a project root and language set — how do we map fs2's scanned files to the right Serena instances?**

## Key Questions Addressed

- Can one Serena instance handle multiple languages?
- Can one Serena instance handle multiple project roots?
- How do we detect distinct projects within a single fs2 scan?
- What do we do with files that don't belong to any resolvable project?
- What's the instance pool strategy for multi-project repos?

---

## How Serena Projects Work

### One Project = One Root + N Languages

A Serena project is defined by `.serena/project.yml`:

```yaml
project_name: "my-app"
languages:
  - python
  - typescript
```

Key facts (from source analysis):
- **Multiple languages**: ✅ A single project supports multiple languages. Serena starts a **separate LSP per language** (`LanguageServerManager` holds `dict[Language, SolidLanguageServer]`)
- **Single root**: Each project has one `project_root`. The LSP servers are initialized against this root
- **Project switching**: `activate_project` can switch at runtime, but **restarts language servers** — expensive (~2-3s)
- **50+ languages supported**: Python, TypeScript, Go, Rust, C#, Java, C/C++, Swift, Dart, and many more

### What This Means for fs2

A Serena instance pool (20 instances) can handle **any combination of languages** within a single project root. But when the scanned codebase has **multiple distinct project roots**, each root needs its own Serena project configuration.

---

## Scenario Analysis

### Scenario 1: Single-Language, Single-Root (Simple)

```
my-python-app/
├── .fs2/config.yaml
├── .serena/project.yml     ← languages: [python]
├── src/
│   └── *.py
└── tests/
    └── *.py
```

**Strategy**: One Serena project, one pool of N instances. All nodes resolved against the same root. This is the common case and what we benchmarked.

### Scenario 2: Multi-Language, Single-Root (Full-Stack App)

```
fullstack-app/
├── .fs2/config.yaml
├── .serena/project.yml     ← languages: [python, typescript]
├── backend/
│   └── *.py
├── frontend/
│   └── *.ts, *.tsx
└── shared/
    └── types.ts
```

**Strategy**: One Serena project with `languages: [python, typescript]`. Serena starts Pyright + tsserver. Each `find_referencing_symbols` call routes to the correct LSP based on file extension. **The pool of 20 instances all share the same project config** — each starts both language servers.

**Cost**: ~600MB per instance (two LSPs) instead of ~300MB. 20 instances = ~12GB. Configurable via `parallel_instances`.

### Scenario 3: Monorepo with Distinct Project Roots

```
monorepo/
├── .fs2/config.yaml        ← scan_paths: ["."]
├── services/
│   ├── auth-service/       ← Python project with its own deps
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   └── tests/
│   └── billing-service/    ← Go project with its own go.mod
│       ├── go.mod
│       └── cmd/
├── web/
│   ├── package.json        ← React/TS project
│   └── src/
└── libs/
    └── shared-types/       ← TypeScript shared lib
        ├── package.json
        └── src/
```

**Problem**: If we create one Serena project at `monorepo/`, Pyright can't resolve `auth-service`'s Python imports (it doesn't know about `pyproject.toml` dependencies). Go's `gopls` won't work without being rooted at `billing-service/` where `go.mod` lives. The TypeScript LSP needs `package.json` for module resolution.

**Strategy: Detect sub-projects, create separate Serena projects per root.**

### Scenario 4: Test Fixtures (Not Real Projects)

```
fs2/
├── src/fs2/             ← Real Python project
├── tests/
│   └── fixtures/
│       └── ast_samples/
│           ├── python/   ← Python sample files (not a project)
│           ├── go/       ← Go sample files (not a project)
│           ├── csharp/   ← C# sample files (not a project)
│           └── rust/     ← Rust sample files (not a project)
```

**Problem**: These fixture files are parsed by fs2 (they're in `scan_paths`), creating nodes like `callable:tests/fixtures/ast_samples/go/sample.go:main`. But they're not real projects — no `go.mod`, no `pyproject.toml`. Running Serena against them would fail or return garbage.

**Strategy: Skip files that don't belong to a detected project root.**

---

## Decision 1: Project Detection

### How to Detect Project Roots

Walk the scanned directory tree looking for **project marker files**:

```python
PROJECT_MARKERS = {
    "python": ["pyproject.toml", "setup.py", "setup.cfg", "Pipfile", "requirements.txt"],
    "typescript": ["package.json", "tsconfig.json"],
    "javascript": ["package.json"],
    "go": ["go.mod"],
    "rust": ["Cargo.toml"],
    "csharp": ["*.csproj", "*.sln"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
    "dart": ["pubspec.yaml"],
    "ruby": ["Gemfile"],
    "swift": ["Package.swift"],
}
```

### Detection Algorithm

```python
def detect_project_roots(scan_root: str) -> list[ProjectRoot]:
    """Walk scan_root, find directories with project markers.
    
    Returns list of (path, languages) tuples, sorted deepest-first
    so child projects are checked before parent projects.
    """
    roots = []
    for dirpath, dirnames, filenames in os.walk(scan_root):
        languages = set()
        for lang, markers in PROJECT_MARKERS.items():
            for marker in markers:
                if any(fnmatch(f, marker) for f in filenames):
                    languages.add(lang)
        if languages:
            roots.append(ProjectRoot(
                path=dirpath,
                languages=list(languages),
            ))
    
    # Sort: deepest paths first (so we match files to most specific root)
    roots.sort(key=lambda r: r.path.count(os.sep), reverse=True)
    return roots
```

### Mapping Files to Project Roots

```python
def get_project_root_for_file(file_path: str, roots: list[ProjectRoot]) -> ProjectRoot | None:
    """Find the most specific project root containing this file.
    
    Returns None if file doesn't belong to any detected project.
    """
    for root in roots:  # Already sorted deepest-first
        if file_path.startswith(root.path):
            return root
    return None
```

### What Happens to Unmatched Files

Files not belonging to any detected project root (like test fixtures) are **skipped** for cross-file resolution. They still exist as nodes in the graph — they just won't have cross-file edges.

Log: `"Skipping cross-file resolution for N files not in any detected project root"`

---

## Decision 2: Serena Instance Pool Strategy

### Per-Project Pools

Each detected project root gets its own pool of Serena instances. The total instance count (`parallel_instances` from config) is divided across projects proportionally by node count.

```python
def allocate_instances(
    project_roots: list[ProjectRoot],
    node_counts: dict[str, int],  # root_path → number of resolvable nodes
    total_instances: int,
) -> dict[str, int]:
    """Allocate instance count per project root, proportional to node count."""
    total_nodes = sum(node_counts.values())
    if total_nodes == 0:
        return {}
    
    allocation = {}
    for root in project_roots:
        count = node_counts.get(root.path, 0)
        # Proportional allocation, minimum 1 instance per project
        instances = max(1, round(count / total_nodes * total_instances))
        allocation[root.path] = instances
    
    return allocation
```

**Example** (monorepo with 20 total instances):

| Project Root | Nodes | Instances |
|-------------|-------|-----------|
| `services/auth-service/` | 2000 | 10 |
| `services/billing-service/` | 500 | 3 |
| `web/` | 1000 | 5 |
| `libs/shared-types/` | 400 | 2 |
| **Total** | **3900** | **20** |

### Serena Project Auto-Creation

For each detected project root that doesn't already have `.serena/project.yml`:

```python
def ensure_serena_project(root: ProjectRoot) -> None:
    """Create Serena project config if not exists."""
    project_yml = Path(root.path) / ".serena" / "project.yml"
    if project_yml.exists():
        return
    
    lang_args = []
    for lang in root.languages:
        lang_args.extend(["--language", lang])
    
    subprocess.run(
        ["serena", "project", "create", root.path,
         "--index", "--log-level", "ERROR"] + lang_args,
        check=True,
        capture_output=True,
    )
```

### Instance Startup Per Project

Each project root's instances are started with `--project <path>`:

```python
for root in project_roots:
    n = allocation[root.path]
    for i in range(n):
        port = base_port + port_offset
        start_serena_instance(
            project=root.path,
            port=port,
            languages=root.languages,
        )
        port_offset += 1
```

---

## Decision 3: Node Sharding Across Projects

### Two-Level Sharding

1. **Level 1**: Group nodes by project root
2. **Level 2**: Shard each group across that project's instance pool

```python
def shard_nodes(
    nodes: list[CodeNode],
    project_roots: list[ProjectRoot],
    allocation: dict[str, int],  # root_path → instance count
) -> dict[str, list[list[CodeNode]]]:
    """Group nodes by project, then shard across instances.
    
    Returns: {root_path: [[shard1_nodes], [shard2_nodes], ...]}
    """
    # Group by project
    by_project: dict[str, list[CodeNode]] = {}
    skipped = 0
    
    for node in nodes:
        file_path = extract_file_path(node.node_id)
        root = get_project_root_for_file(file_path, project_roots)
        if root is None:
            skipped += 1
            continue
        by_project.setdefault(root.path, []).append(node)
    
    # Shard each project's nodes across its instances
    result = {}
    for root_path, project_nodes in by_project.items():
        n_instances = allocation.get(root_path, 1)
        shards = [[] for _ in range(n_instances)]
        for i, node in enumerate(project_nodes):
            shards[i % n_instances].append(node)
        result[root_path] = shards
    
    return result
```

---

## Decision 4: Single-Project Fast Path

Most codebases are single-project (one language, one root). The multi-project detection should be **fast and invisible** for this case:

```python
def resolve_cross_file_edges(context: PipelineContext, config: CrossFileRelsConfig):
    scan_root = get_scan_root(context)
    
    # Detect project roots
    roots = detect_project_roots(scan_root)
    
    if len(roots) == 0:
        log.info("No project roots detected. Skipping cross-file resolution.")
        return
    
    if len(roots) == 1:
        # FAST PATH: single project, no sharding overhead
        log.info(f"Single project: {roots[0].path} ({roots[0].languages})")
        pool = start_pool(roots[0], config.parallel_instances)
        resolve_all(context.nodes, pool)
        stop_pool(pool)
    else:
        # MULTI-PROJECT: per-project pools with proportional allocation
        log.info(f"Multi-project: {len(roots)} projects detected")
        for root in roots:
            log.info(f"  {root.path}: {root.languages}")
        run_multi_project_resolution(context, roots, config)
```

---

## Decision 5: The fs2 Fixture Case

For `tests/fixtures/ast_samples/`:

```
tests/fixtures/ast_samples/
├── python/sample.py    ← No pyproject.toml, not a project
├── go/sample.go        ← No go.mod, not a project
├── csharp/sample.cs    ← No .csproj, not a project
└── rust/sample.rs      ← No Cargo.toml, not a project
```

These directories have **no project markers**. The detection algorithm returns no roots for them. Nodes from these files are skipped for cross-file resolution but remain in the graph.

**No special case needed** — the generic "no project root → skip" logic handles this naturally.

---

## Decision 6: Cross-Project References

### Can we resolve references ACROSS project roots?

**Example**: `web/src/api.ts` imports types from `libs/shared-types/src/types.ts`. These are separate project roots but have a real dependency.

**v1 answer: No.** Each Serena instance pool is scoped to one project root. Cross-project references require the LSP to understand the dependency relationship (e.g., `tsconfig.json` paths, `go.mod` replace directives), which only works when both are under the same LSP project.

**Workaround**: If the user wants cross-project resolution, they can:
1. Configure the Serena project manually with a broader root
2. Use a `tsconfig.json` / `pyproject.toml` that spans both directories

**Future**: Could detect workspace files (`pnpm-workspace.yaml`, `lerna.json`, Cargo workspaces) and treat the workspace root as a single project.

---

## Scan Output for Multi-Project

```
$ fs2 scan

  Resolving cross-file relationships...
  ├ Detected 3 project roots:
  │   auth-service/ (python) → 10 instances, 2000 nodes
  │   billing-service/ (go) → 3 instances, 500 nodes
  │   web/ (typescript) → 7 instances, 1000 nodes
  ├ Skipped: 150 nodes (no project root)
  ╰ Progress: ████████████████████████████████████████ 3500/3500 (32s)
✓ Cross-file refs: 8500 references across 3 projects (32.1s)
```

---

## Config Changes

The `cross_file_rels` config from Workshop 002 is sufficient — no changes needed:

```yaml
cross_file_rels:
  enabled: true
  parallel_instances: 20     # Total across all detected projects
  serena_base_port: 8330
  timeout_per_node: 5.0
  languages: "auto"          # Auto-detect from scanned files (recommended)
  # Or explicit list:
  # languages:
  #   - python
  #   - typescript
  #   - go
```

The `languages` field controls which languages get cross-file resolution:
- `"auto"` (default): detect from scanned file extensions, map to Serena language names
- Explicit list: only resolve for listed languages

---

## Open Questions

### Q1: Should we detect project roots at scan time or cache them?

**RESOLVED**: Detect at scan time. It's a simple filesystem walk (~50ms for typical repos). Caching adds complexity and staleness risk for negligible performance gain.

### Q2: Should `.serena/` dirs be created inside sub-project roots?

**RESOLVED**: Yes. Each detected project root gets its own `.serena/project.yml` and cache. This is how Serena is designed to work. These should be in `.gitignore`.

### Q3: What about Cargo workspaces / pnpm workspaces?

**OPEN**: Deferred to future. These define "workspace roots" that span multiple packages. Detection would look for `pnpm-workspace.yaml`, `Cargo.toml` with `[workspace]`, etc. For v1, each package directory with a marker file is a separate project root.

### Q4: What if two project roots have conflicting port ranges?

**RESOLVED**: Ports are allocated sequentially from `serena_base_port`. Total instances across all projects cannot exceed `parallel_instances`. The allocation is `base_port + 0` through `base_port + total_instances - 1`.

---

## Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Multi-language | One Serena project supports multiple languages | Serena's LanguageServerManager holds per-language LSPs |
| Project detection | Walk for marker files (pyproject.toml, go.mod, etc.) | Simple, accurate, no config needed |
| Instance allocation | Proportional to node count per project | Balances work across projects |
| Unmatched files | Skip (no edges, no error) | Test fixtures and samples handled naturally |
| Cross-project refs | Not in v1 | Requires workspace-level LSP config |
| Fast path | Single-project detected → skip sharding overhead | Most repos are single-project |

---

## Appendix: Empirical Validation

### Test Run: `tests/fixtures/samples/` (7 languages, 12 files)

Ran `scripts/serena-explore/test_multi_lang.py` against the fs2 fixture samples directory. Each language subdirectory was auto-detected and got its own Serena project + instance.

**Script**: `scripts/serena-explore/test_multi_lang.py`
**Date**: 2026-03-12

#### Project Detection Results

- **Marker-based detection** found 1 root: `json/` (has `package.json`)
- **Extension-based detection** found 7 language groups across 12 files
- Each language subdir got a separate `.serena/project.yml` auto-created

#### Per-Language Results

| Language | Files | Symbols Found | Refs Found | Status | Notes |
|----------|-------|---------------|------------|--------|-------|
| **Python** | 2 | 11 | 20 | ✅ | Pyright works perfectly — found AuthRole (9 refs), ParseError (11 refs) |
| **TypeScript/JS** | 3 | 39 | 0 | ✅ | tsserver started, symbols resolved. No cross-file refs (files are standalone) |
| **C/C++** | 2 | 14 | 5 | ✅ | clangd found Comparator with 5 intra-file refs |
| **Java** | 1 | 5 | 0 | ✅ | jdtls started, symbols found. No refs (single file) |
| **Go** | 1 | 0 | — | ✅ | gopls started but returned 0 symbols (no `go.mod` — expected) |
| **Rust** | 1 | 0 | — | ✅ | rust-analyzer started but 0 symbols (no `Cargo.toml` — expected) |
| **Ruby** | 1 | — | — | ⏳ | Solargraph LS hung (>60s timeout). Known issue with Ruby LS startup |

#### Key Findings

1. **6 out of 7 languages worked** — Ruby was the only failure (LS startup timeout)
2. **Python is the strongest** — Pyright returns rich symbol + reference data immediately
3. **Go and Rust need project markers** — LSPs return 0 symbols without `go.mod`/`Cargo.toml`. This validates the project detection design: no marker → no resolution → no edges (graceful skip)
4. **C/C++ works without project markers** — clangd is more tolerant, found 14 symbols and 5 refs in standalone `.c`/`.cpp` files
5. **TypeScript works** — tsserver found 39 symbols across 3 files (`.ts`, `.tsx`, `.js`)
6. **Auto-project-creation worked for all 7 languages** — `serena project create` with `--language` succeeded every time
7. **Sequential per-language startup** takes ~3-5s per language (LS initialization). In production with the pool approach, all instances for one project start in parallel (~3s total)

#### Implications for Config

The `languages` config field should default to all languages Serena supports, not just Python:

```yaml
cross_file_rels:
  languages:           # Default: all supported languages
    - python           # Pyright — best coverage
    - typescript       # tsserver — JS/TS/TSX
    - go               # gopls — needs go.mod
    - rust             # rust-analyzer — needs Cargo.toml
    - java             # jdtls
    - cpp              # clangd — C and C++
    - csharp           # csharp LS
    # Ruby excluded from default due to LS reliability issues
```

However, more languages = more LSP processes per Serena instance = more memory. Each additional language adds ~100-300MB per instance. **Recommend: auto-detect from scanned file extensions** rather than a fixed list.

#### Revised Config Design

```yaml
cross_file_rels:
  enabled: true
  parallel_instances: 20
  serena_base_port: 8330
  timeout_per_node: 5.0
  languages: "auto"          # NEW: auto-detect from scanned files
  # Or explicit list:
  # languages:
  #   - python
  #   - typescript
```

When `languages: "auto"`, the stage:
1. Scans `context.nodes` for distinct `node.language` values
2. Maps to Serena language names (e.g., `javascript` → `typescript`)
3. Filters to languages Serena supports
4. Creates projects with only the detected languages
