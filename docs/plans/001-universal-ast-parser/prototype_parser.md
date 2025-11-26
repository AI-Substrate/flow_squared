# Plan: Canonical symbols.json Data Structure

**Status: COMPLETE** ✓

## Overview

Define the canonical `symbols.json` format and build a simple Python script (`extract_symbols.py`) that transforms raw tree-sitter AST JSON into the homogeneous symbol format optimized for semantic search.

**Pipeline:**
```
sample.py → [parse_to_json.py] → outputs/sample.py.ast.json → [extract_symbols.py] → outputs/sample.py.symbols.json
```

**Naming convention:**
- Raw AST: `outputs/{filename}.ast.json`
- Symbols: `outputs/{filename}.symbols.json`

**Each script clears its output type before running:**
- `parse_to_json.py --all` removes all `*.ast.json` files first
- `extract_symbols.py --all` removes all `*.symbols.json` files first

---

## Quick Start

```bash
cd /workspaces/flow_squared/initial_exploration

# Generate all raw ASTs (clears *.ast.json first)
uv run python scripts/parse_to_json.py --all

# Generate all symbols (clears *.symbols.json first)
uv run python scripts/extract_symbols.py --all

# Or process a single file
uv run python scripts/parse_to_json.py sample_repo/python/sample.py -o outputs/sample.py.ast.json
uv run python scripts/extract_symbols.py outputs/sample.py.ast.json -o outputs/sample.py.symbols.json
```

---

## Implementation Results

### Symbol Counts by Format

| File | Symbols | Format Family | Status |
|------|---------|---------------|--------|
| sample.py | 16 | code_oop | ✓ |
| sample.ts | 29 | code_oop | ✓ |
| sample.js | 14 | code_oop | ✓ |
| sample.dart | 9 | code_oop | ✓ |
| sample.cs | 35 | code_oop | ✓ |
| sample.go | 20 | code_systems | ✓ |
| sample.rs | 28 | code_systems | ✓ |
| sample.cpp | 40 | code_systems | ✓ |
| sample.sh | 21 | shell | ✓ |
| sample.tf | 32 | iac | ✓ |
| Dockerfile | 5 | iac | ✓ |
| sample.md | 14 | markup | ✓ |
| sample.yaml | 0 | config_kv | Needs work |
| sample.json | 0 | config_kv | Needs work |
| sample.toml | 0 | config_kv | Needs work |
| sample.sql | 0 | query | Needs work |

**Total: 263 symbols extracted across 16 formats**

### Known Limitations (Future Work)

1. **Config formats (YAML, JSON, TOML)**: No symbols extracted yet - need to add handlers for top-level keys and mappings
2. **SQL**: No symbols extracted - need to add handlers for CREATE TABLE, stored procedures, etc.
3. **Docstring extraction**: Deferred - `doc` field is always `null`
4. **Signature truncation**: Some signatures get truncated at `:` character prematurely

---

## The Canonical `symbols.json` Structure

### File-Level Schema

```json
{
  "version": "1.0",
  "source": {
    "file": "sample_repo/python/sample.py",
    "language": "python",
    "format_family": "code_oop"
  },
  "root": { /* root symbol object containing entire file */ }
}
```

### Symbol Object Schema

Every symbol, regardless of source language/format, has this **nested** structure where each level contains its full content (including all descendants):

```json
{
  "id": "callable:sample_repo/python/sample.py:Calculator.add",
  "category": "callable",
  "kind": "function_definition",
  "name": "add",
  "qualified_name": "Calculator.add",
  "signature": "def add(self, a:",
  "doc": null,
  "location": {
    "start_line": 21,
    "end_line": 23,
    "start_byte": 400,
    "end_byte": 480
  },
  "content": "def add(self, a: int, b: int) -> int:\n        \"\"\"Instance method.\"\"\"\n        return a + b",
  "children": []
}
```

**Key design: Content redundancy for embedding**
- `root.content` = entire file (includes all classes, all methods)
- `class.content` = entire class (includes all methods)
- `method.content` = just that method

This redundancy is intentional - each level will be embedded/summarized independently later.

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier: `{category}:{file}:{qualified_name}` |
| `category` | enum | Yes | One of: `file`, `type`, `callable`, `section`, `block`, `definition` |
| `kind` | string | Yes | Original tree-sitter node type (e.g., `class_definition`, `function_declaration`) |
| `name` | string | Yes | Simple name (e.g., `add`) |
| `qualified_name` | string | Yes | Full path within file (e.g., `Calculator.add`) |
| `signature` | string | No | Declaration line(s) - syntax varies by language |
| `doc` | string | No | Extracted documentation (deferred - null for now) |
| `location.*` | int | Yes | Position in source file (1-indexed lines) |
| `content` | string | Yes | Full source text of the symbol (includes children) |
| `children` | array | No | Nested symbol objects (not IDs - actual objects) |

### Category Definitions

| Category | What it represents | Code examples | Non-code examples |
|----------|-------------------|---------------|-------------------|
| `file` | The root/file level | `module`, `program`, `source_file` | `document` |
| `type` | Type/class definitions | `class`, `struct`, `interface`, `enum` | - |
| `callable` | Functions/methods | `function`, `method`, `lambda` | - |
| `section` | Document sections | - | Markdown headings |
| `block` | Named blocks | Terraform `resource`, Dockerfile `FROM` stage | HCL blocks |
| `definition` | Other named definitions | `const`, `variable`, `type alias` | - |

### Format Family Mappings

| Family | Languages | Primary symbol types |
|--------|-----------|---------------------|
| `code_oop` | Python, JS, TS, Dart, C#, Java | `type`, `callable` |
| `code_systems` | Go, Rust, C++, C | `type`, `callable` |
| `markup` | Markdown | `section` |
| `config_kv` | YAML, JSON, TOML | `section`, `definition` (not implemented) |
| `iac` | Terraform/HCL, Dockerfile | `block` |
| `query` | SQL | `callable`, `definition` (not implemented) |
| `shell` | Bash | `callable` |

---

## Implementation Details

### File Locations

```
initial_exploration/
├── scripts/
│   ├── parse_to_json.py      # Raw AST generation (updated)
│   └── extract_symbols.py    # Symbol extraction (new)
├── outputs/
│   ├── *.ast.json            # Raw tree-sitter ASTs (16 files)
│   └── *.symbols.json        # Extracted symbols (16 files)
├── samples/
│   ├── symbols_sample.json       # Python reference
│   ├── symbols_sample_go.json    # Go reference
│   └── symbols_sample_markdown.json  # Markdown reference
└── sample_repo/                  # Source files (16 formats)
```

### Key Functions in extract_symbols.py

```python
# Category classification
def get_category(node_type: str, language: str) -> str | None:
    """Determine category (file, type, callable, section, block, definition) from node type."""

# Name extraction (multi-strategy)
def extract_name(node: dict, source_bytes: bytes) -> str | None:
    """Extract name using: field_name="name", type_identifier, identifier, declarator fallbacks."""

# Signature extraction
def extract_signature(node: dict, source_bytes: bytes) -> str | None:
    """Extract first line(s) of declaration up to body marker."""

# Content extraction
def extract_content(node: dict, source_bytes: bytes) -> str:
    """Extract full source text for embedding."""

# AST walking
def walk_ast(node, source_bytes, file_path, language, parent_qualified_name, is_root) -> list[dict]:
    """Recursively walk AST and build nested symbol hierarchy."""

# Markdown special handling
def process_markdown(root, source_bytes, file_path) -> dict:
    """Convert flat headings to nested section hierarchy based on heading level."""
```

### Symbol Identification Patterns

**Code formats** - Node types matching:
```python
CODE_SYMBOL_PATTERNS = [
    r'class_definition', r'class_declaration', r'class_specifier',
    r'struct_item', r'struct_declaration', r'struct_specifier',
    r'interface_declaration', r'enum_definition', r'enum_declaration',
    r'type_declaration', r'type_alias_declaration',
    r'function_definition', r'function_declaration', r'function_item',
    r'method_definition', r'method_declaration', r'impl_item',
]
```

**Markdown** - `atx_heading` nodes with level detection via marker type (`atx_h1_marker`, etc.)

**Terraform/HCL** - `block` nodes with name from type + labels

**Dockerfile** - `from_instruction` nodes

---

## Tasks Completed

### Phase 1: Update parse_to_json.py ✓
- [x] Add `--all` flag to process all sample files
- [x] Change output naming to `{filename}.ast.json`
- [x] Add cleanup of existing `*.ast.json` files when using `--all`
- [x] Add `SCRIPT_DIR`, `SAMPLE_REPO`, `OUTPUTS_DIR` constants

### Phase 2: Core Extraction Script ✓
- [x] Create `scripts/extract_symbols.py` with:
  - [x] CLI argument parsing (input, output, `--all` flag)
  - [x] Raw AST JSON loading
  - [x] Source file loading (for extracting source text)
  - [x] Recursive AST walker with `is_root` handling
  - [x] Category classification logic
  - [x] Name extraction with multiple fallback strategies
  - [x] Signature extraction
  - [x] Parent-child relationship building (nested structure)
  - [x] symbols.json output generation
  - [x] Cleanup of `*.symbols.json` when using `--all`

### Phase 3: Format-Specific Handlers ✓
- [x] Code formats (Python, JS, TS, Go, Rust, C++, C#, Dart)
- [x] Markdown (heading → section hierarchy with level-based nesting)
- [ ] Config formats (YAML, JSON, TOML) - **needs implementation**
- [x] IaC formats (Terraform/HCL, Dockerfile)
- [x] Shell (Bash functions)
- [ ] SQL - **needs implementation**

### Phase 4: Generate All Symbols Files ✓
- [x] Run extraction on all 16 sample raw ASTs
- [x] Review outputs and iterate on edge cases
- [x] Fix Go type alias name extraction
- [x] Fix duplicate module node issue

---

## Future Work

### High Priority
1. **Config format handlers**: Implement symbol extraction for YAML, JSON, TOML
   - Extract top-level keys as `section` category
   - Handle nested structures as children

2. **SQL handlers**: Implement symbol extraction for SQL
   - Extract `CREATE TABLE` as `definition`
   - Extract stored procedures/functions as `callable`

3. **Docstring extraction**: Implement `doc` field population
   - Python: first string literal in function body
   - JS/TS/Go/Rust: preceding comment with `/**`, `///`, `//`

### Medium Priority
4. **Signature improvement**: Fix truncation at `:` character
5. **Cross-file references**: Track imports/exports for dependency analysis
6. **Incremental updates**: Hash-based change detection for large codebases

### Low Priority
7. **JSON Schema validation**: Create `schemas/symbols.schema.json`
8. **Additional languages**: Kotlin, Swift, Ruby, PHP, etc.

---

## Reference Samples

See `initial_exploration/samples/` for hand-crafted reference examples:
- `symbols_sample.json` - Python with classes and nested methods
- `symbols_sample_go.json` - Go with structs and functions
- `symbols_sample_markdown.json` - Markdown with nested sections

---

## Success Criteria

1. **Homogeneous structure** ✓ - All formats produce valid symbols.json with identical schema
2. **Complete extraction** ✓ - Classes, functions, sections, blocks captured for supported formats
3. **Accurate nesting** ✓ - Parent-child relationships correctly reflect hierarchy
4. **Full source** ✓ - Every symbol includes complete source text (content includes children)
5. **Language agnostic** ✓ - Same fields work across Python, Go, Markdown, etc.
