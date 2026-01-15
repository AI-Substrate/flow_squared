# Phase 0b: Multi-Project Research Results

**Date**: 2026-01-15
**Phase**: Phase 0b: Multi-Project Research
**Status**: COMPLETE
**Validation**: 31/31 tests passing

---

## Executive Summary

This phase validated Serena's project root detection patterns before committing to vendor ~25K LOC of SolidLSP in Phase 1. All patterns validated successfully and are recommended for adoption.

**Recommendation**: Proceed with Phase 1 vendoring. The researched patterns work correctly for fs2's needs.

---

## Research Objectives

| Objective | Status | Finding |
|-----------|--------|---------|
| Validate "deepest wins" algorithm | ✅ Validated | Algorithm works correctly for nested project structures |
| Validate Language enum pattern | ✅ Validated | `Language(str, Enum)` with `markers`/`file_patterns` properties is clean and extensible |
| Validate TypeScript pattern generation | ✅ Validated | Algorithmic generation of 12 patterns works correctly |
| Validate boundary constraint | ✅ Validated | `workspace_root` parameter correctly limits search scope |
| Create test fixtures | ✅ Complete | 4 language fixtures covering key scenarios |

---

## Pattern Validations

### 1. Language Enum Pattern

**Source**: `solidlsp/ls_config.py:29-102`
**Verdict**: ✅ ADOPT

```python
class Language(str, Enum):
    """Inheriting from (str, Enum) enables string comparison."""

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    GO = "go"
    CSHARP = "csharp"

    @property
    def markers(self) -> tuple[str, ...]:
        """Project root marker files (priority order)."""
        match self:
            case Language.PYTHON:
                return ("pyproject.toml", "setup.py", "setup.cfg")
            # ...

    @property
    def file_patterns(self) -> tuple[str, ...]:
        """fnmatch globs for source file detection."""
        # ...
```

**Why Adopt**:
- Clean API: `lang.markers`, `lang.file_patterns`
- Extensible: Add new languages by adding enum values + match cases
- Type-safe: Enum prevents invalid language strings
- String-comparable: `Language.PYTHON == "python"` works

**Implementation**: `scripts/lsp/language.py` (143 lines, production-ready)

---

### 2. "Deepest Wins" Algorithm

**Source**: `serena/cli.py:40-72` (adapted for LSP markers)
**Verdict**: ✅ ADOPT

**Algorithm**:
```
1. Start at file's parent directory
2. Walk UP toward filesystem root (or workspace_root boundary)
3. At each directory, check for any marker file
4. Keep FIRST match (deepest/closest to file)
5. Return deepest match, or file's directory if none found
```

**Critical Finding**: "Deepest wins" means the FIRST marker found when walking UP, not the last. Initial implementation bug overwrote candidate on each match (returning highest, not deepest).

**Implementation**: `scripts/lsp/detect_project_root.py` (152 lines, production-ready)

---

### 3. TypeScript Pattern Generation

**Source**: `solidlsp/ls_config.py:155-162`
**Verdict**: ✅ ADOPT

```python
# Algorithmic: prefix × postfix × base = 12 patterns
patterns = []
for prefix in ("c", "m", ""):      # CommonJS, ESModule, standard
    for postfix in ("x", ""):       # JSX/TSX, standard
        for base in ("ts", "js"):   # TypeScript, JavaScript
            patterns.append(f"*.{prefix}{base}{postfix}")
```

**Generated Patterns** (12 total):
- Standard: `*.ts`, `*.tsx`, `*.js`, `*.jsx`
- CommonJS: `*.cts`, `*.ctsx`, `*.cjs`, `*.cjsx`
- ES Module: `*.mts`, `*.mtsx`, `*.mjs`, `*.mjsx`

**Why Adopt**: Covers all real-world TypeScript/JavaScript variants without manual enumeration.

---

### 4. Boundary Constraint

**Source**: `serena/cli.py:53-59`
**Verdict**: ✅ ADOPT

```python
def find_project_root(file_path, language, workspace_root=None):
    boundary = Path(workspace_root).resolve() if workspace_root else None

    def ancestors(start):
        yield start
        for parent in start.parents:
            yield parent
            if boundary and parent == boundary:
                return  # Stop at boundary
```

**Why Adopt**: Essential for sandboxed environments where agents shouldn't access files outside workspace.

---

### 5. Marker File Configuration

**Verdict**: ✅ ADOPT with modifications

| Language | Markers (Priority Order) | Notes |
|----------|--------------------------|-------|
| Python | `pyproject.toml`, `setup.py`, `setup.cfg` | Modern Python prefers pyproject.toml |
| TypeScript | `tsconfig.json`, `package.json` | tsconfig more specific than package.json |
| Go | `go.mod` | Single marker; nested go.mod is anti-pattern |
| C# | `*.csproj`, `*.sln` | Use glob matching (extensions, not exact names) |

**C# Glob Matching**: Unlike other markers which are exact filenames, C# markers are file extensions. Use `directory.glob(f"*{marker}")` instead of `(directory / marker).exists()`.

---

## Discoveries & Gotchas

### Critical: "Deepest Wins" Semantics

**Problem**: Initial implementation tracked the LAST marker found (highest in tree).

**Root Cause**: Walking UP from file means first match is deepest, but code overwrote candidate:
```python
# BUG: Overwrites on each match (returns highest)
for directory in ancestors(start_dir):
    if marker_exists(directory):
        candidate = directory  # Always overwrites!
```

**Fix**: Only set candidate if None:
```python
# CORRECT: Keeps first match (deepest)
for directory in ancestors(start_dir):
    if marker_exists(directory):
        if candidate is None:
            candidate = directory
```

### Non-Existent File Handling

**Problem**: `Path.is_file()` returns False for non-existent paths.

**Impact**: When analyzing a file that doesn't exist yet (e.g., planning where to create a new file), the algorithm treated the path as a directory.

**Fix**: Check suffix as fallback:
```python
is_file = file_path.is_file() or (file_path.suffix and not file_path.is_dir())
start_dir = file_path.parent if is_file else file_path
```

### Go Anti-Pattern

**Finding**: Nested `go.mod` files are an anti-pattern in Go. Real-world Go projects have a single `go.mod` at the repository root.

**Impact**: Go fixture should NOT have nested `go.mod` (unlike Python/TypeScript/C#).

---

## Test Coverage

### Validation Tests: 31/31 Passing

| Category | Tests | Coverage |
|----------|-------|----------|
| Deepest Wins | 4 | Python, TypeScript, Go, C# |
| Boundary Constraint | 2 | At package level, at project level |
| Auto-Detection | 3 | Python, TypeScript, unknown extension |
| TypeScript Patterns | 9 | 12 patterns generated, key patterns verified |
| Language Detection | 10 | All extensions + unknown cases |
| Fallback Behavior | 1 | No marker → file's directory |
| Find All Roots | 2 | Multiple roots, sorted deepest first |

### Test Fixtures

| Fixture | Structure | Validates |
|---------|-----------|-----------|
| `python_multi_project/` | Root + nested pyproject.toml | Deepest wins |
| `typescript_multi_project/` | Root + nested tsconfig.json | TS detection |
| `go_project/` | Single go.mod at root | No-nesting pattern |
| `csharp_multi_project/` | .sln at root, .csproj nested | Multi-marker priority |

---

## Deliverables for Phase 1/3

### Production-Ready Code

| File | Lines | Target Location (Phase 3) |
|------|-------|---------------------------|
| `scripts/lsp/language.py` | 143 | `src/fs2/core/utils/language.py` |
| `scripts/lsp/detect_project_root.py` | 152 | `src/fs2/core/utils/project_root.py` |

### Import Path Changes Required

When cherry-picking to production:
```python
# FROM (research)
from scripts.lsp.language import Language

# TO (production)
from fs2.core.utils.language import Language
```

### Integration Points

**Phase 3 (SolidLspAdapter)**:
- Use `Language` enum for language detection
- Use `find_project_root()` to determine `rootUri` for LSP servers
- Use `workspace_root` boundary for sandboxed environments

**Phase 4+ (Multi-Language)**:
- Extend `Language` enum with additional languages
- Add markers and file patterns following established pattern

---

## Recommendations

### Proceed with Vendoring (Phase 1)

All researched patterns validated successfully. The ~25K LOC vendoring investment is justified.

### Adopt These Patterns

1. **Language Enum**: Use `Language(str, Enum)` pattern with `markers` and `file_patterns` properties
2. **Detection Algorithm**: Use "deepest wins" with boundary constraint
3. **TypeScript Patterns**: Use algorithmic generation (prefix × postfix × base)
4. **C# Markers**: Use glob matching for extension-based markers

### Address These in Phase 3

1. **Import paths**: Update from `scripts.lsp.*` to `fs2.core.utils.*`
2. **Additional markers**: Consider adding `requirements.txt` for legacy Python projects
3. **Edge cases**: Handle symlinks (Path.resolve() already called)

---

## Appendix: API Reference

### `Language` Enum

```python
class Language(str, Enum):
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    GO = "go"
    CSHARP = "csharp"

    @property
    def markers(self) -> tuple[str, ...]: ...

    @property
    def file_patterns(self) -> tuple[str, ...]: ...

    @classmethod
    def from_filename(cls, filename: str) -> Language | None: ...

    def matches_filename(self, filename: str) -> bool: ...
```

### `find_project_root()`

```python
def find_project_root(
    file_path: Path | str,
    language: Language,
    workspace_root: Path | str | None = None,
) -> Path:
    """
    Find project root using "deepest wins" algorithm.

    Returns: Project root (never None - falls back to file's directory)
    """
```

### `detect_project_root_auto()`

```python
def detect_project_root_auto(
    file_path: Path | str,
    workspace_root: Path | str | None = None,
) -> tuple[Path, Language | None]:
    """
    Auto-detect language and find project root.

    Returns: (project_root, detected_language)
    """
```
