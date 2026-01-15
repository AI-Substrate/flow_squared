# LSP Project Root Detection Research

Research scripts validating the project root detection algorithm for LSP integration (Phase 0b).

## Purpose

LSP servers require the correct `rootUri` to understand workspace boundaries for cross-file analysis. This research validates the "deepest wins" algorithm before Phase 3 production implementation.

## Quick Start

```bash
# Run validation tests (31 tests)
python scripts/lsp/test_detection.py

# Example usage
python -c "
from scripts.lsp.detect_project_root import find_project_root, detect_project_root_auto
from scripts.lsp.language import Language

# Explicit language
root = find_project_root('src/app/handler.py', Language.PYTHON)
print(f'Project root: {root}')

# Auto-detect language
root, lang = detect_project_root_auto('src/app/handler.py')
print(f'Project root: {root}, Language: {lang}')
"
```

## Detection Algorithm

### "Deepest Wins" Rule

The algorithm walks up from a file's directory, finding all directories containing marker files. It returns the **deepest** (closest to the file) match.

```
workspace/
├── pyproject.toml          # ← Also matches, but NOT returned (less deep)
└── packages/
    └── auth/
        ├── pyproject.toml  # ← Returned (deepest match)
        └── handler.py      # ← File being analyzed
```

### Marker Files by Language

| Language | Markers (Priority Order) |
|----------|--------------------------|
| Python | `pyproject.toml`, `setup.py`, `setup.cfg` |
| TypeScript | `tsconfig.json`, `package.json` |
| Go | `go.mod` |
| C# | `*.csproj`, `*.sln` |

Priority order only matters when multiple markers exist at the same directory level.

### Boundary Constraint

The optional `workspace_root` parameter limits the search scope:

```python
# Search stops at /workspace, won't check parent directories
root = find_project_root(
    'workspace/packages/auth/handler.py',
    Language.PYTHON,
    workspace_root='/workspace'
)
```

This is essential for sandboxed environments where agents shouldn't access files outside the workspace.

## Scripts

| File | Description |
|------|-------------|
| `language.py` | `Language` enum with markers and file patterns |
| `detect_project_root.py` | Core detection algorithm |
| `test_detection.py` | Validation tests (31 test cases) |

## API Reference

### `find_project_root(file_path, language, workspace_root=None) -> Path`

Find project root for a file with explicit language specification.

**Parameters:**
- `file_path`: Path to the source file
- `language`: `Language` enum value
- `workspace_root`: Optional boundary (search stops here)

**Returns:** Project root directory (never None - falls back to file's directory)

### `detect_project_root_auto(file_path, workspace_root=None) -> tuple[Path, Language | None]`

Auto-detect language and find project root.

**Returns:** Tuple of (project_root, detected_language). Language is None if unrecognized extension.

### `Language.from_filename(filename) -> Language | None`

Detect language from filename using fnmatch patterns.

### `Language.markers` (property)

Tuple of marker filenames for project root detection.

### `Language.file_patterns` (property)

Tuple of fnmatch glob patterns for source file detection.

## TypeScript Pattern Generation

TypeScript/JavaScript files have many extension variants. The algorithm generates 12 patterns:

| Prefix | Meaning | Postfix | Meaning |
|--------|---------|---------|---------|
| `c` | CommonJS | `x` | JSX/TSX |
| `m` | ES Module | `` | Standard |
| `` | Standard | | |

Generated patterns: `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `*.mts`, `*.mtsx`, `*.mjs`, `*.mjsx`, `*.cts`, `*.ctsx`, `*.cjs`, `*.cjsx`

## Test Fixtures

Located in `tests/fixtures/lsp/`:

```
python_multi_project/           # Nested pyproject.toml
typescript_multi_project/       # Nested tsconfig.json
go_project/                     # Single go.mod (no nesting)
csharp_multi_project/           # .sln at root, .csproj nested
```

## Phase 3 Integration

These scripts will be cherry-picked to `src/fs2/core/utils/` in Phase 3:
- `language.py` → `src/fs2/core/utils/language.py`
- `detect_project_root.py` → `src/fs2/core/utils/project_root.py`

The code is production-quality with type hints and docstrings.
