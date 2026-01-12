# Phase 2: Core Extraction Scripts - Execution Log

**Phase**: Phase 2: Core Extraction Scripts
**Started**: 2026-01-12
**Completed**: 2026-01-12
**Status**: ✅ Complete

---

## Task T001: Create lib/parser.py
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Created `lib/parser.py` with:
- `LANG_MAP` dict mapping file extensions to tree-sitter language names (12 extensions)
- `detect_language(file_path)` function returning language name or None
- `parse_file(file_path, lang)` function returning Tree-sitter AST
- `parse_content(content, lang)` for parsing raw bytes
- `parse_file_cached(file_path, lang)` with simple dict-based caching
- `clear_cache()` utility

### Evidence
```bash
$ source .venv/bin/activate && python -c "from lib.parser import parse_file, detect_language; from pathlib import Path; print('Lang:', detect_language(Path('test.py'))); tree = parse_file(Path('/workspaces/flow_squared/tests/fixtures/samples/python/auth_handler.py'), 'python'); print('Tree root type:', tree.root_node.type)"
Lang: python
Tree root type: module
```

### Files Changed
- Created `/workspaces/flow_squared/scripts/cross-files-rels-research/lib/parser.py`

**Completed**: 2026-01-12

---

## Task T001a: Validate Tree-sitter Query Syntax
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Explored AST node types by parsing fixture files and printing node structures. Documented the correct node types and field names for T002 query patterns.

### AST Node Findings

#### Python
- **`import_statement`**: `import module`
  - Child: `dotted_name` containing module name as `identifier` nodes
- **`import_from_statement`**: `from module import names`
  - Child: first `dotted_name` is the module
  - Child: subsequent `dotted_name` entries are imported names
- **`call`**: Function/constructor calls
  - Child: `identifier` (for simple calls like `Foo()`)
  - Child: `attribute` (for method calls like `obj.method()`)
  - Child: `argument_list`

#### TypeScript
- **`import_statement`**: `import { names } from "source"`
  - Child: `import_clause` containing:
    - `identifier` for default import
    - `named_imports` → `import_specifier` for named imports
  - Child: `string` for source module
- Type-only imports: Use same `import_statement` but with `type` keyword inside `import_clause`

#### Go
- **`import_declaration`**: Contains `import_spec_list` or single `import_spec`
  - `import_spec`: Contains `interpreted_string_literal` with path
  - Aliased imports: `import_spec` has `identifier` child before path
  - Dot imports: `import_spec` has `dot` child
  - Blank imports: `import_spec` has `blank_identifier` child

### Evidence
```
Python import_from_statement structure:
  import_from_statement: 'from dataclasses import dataclass'
    from: 'from'
    dotted_name: 'dataclasses'       <- module
      identifier: 'dataclasses'
    import: 'import'
    dotted_name: 'dataclass'         <- imported name
      identifier: 'dataclass'

TypeScript import_statement structure:
  import_statement: 'import { EventEmitter } from "events";'
    import: 'import'
    import_clause: '{ EventEmitter }'
      named_imports: '{ EventEmitter }'
        import_specifier: 'EventEmitter'
          identifier: 'EventEmitter'
    from: 'from'
    string: '"events"'               <- source module

Go import_declaration structure:
  import_declaration: 'import (\n\t"context"\n\t...)'
    import: 'import'
    import_spec_list: '(...)'
      import_spec: '"context"'
        interpreted_string_literal: '"context"'
          interpreted_string_literal_content: 'context'
```

### Discoveries
- **insight**: Python `import_from_statement` has multiple `dotted_name` children - first is module, rest are imported names
- **insight**: Go uses `interpreted_string_literal` not `string` for import paths
- **insight**: TypeScript type imports need to check for `type` keyword in import_clause

### Files Changed
- None (console output validation only)

**Completed**: 2026-01-12

---

## Task T002: Create lib/queries.py
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Created `lib/queries.py` with:
- `IMPORT_QUERIES` dict: Query patterns for 10 languages (python, typescript, javascript, tsx, go, rust, java, c, cpp, ruby)
- `CALL_QUERIES` dict: Query patterns for function/method calls
- `get_import_query(lang)` and `get_call_query(lang)` accessor functions
- `run_query(lang_name, query_pattern, root_node)` - runs query and returns (capture_name, node) tuples
- `run_import_query(lang_name, root_node)` - convenience wrapper
- `run_call_query(lang_name, root_node)` - convenience wrapper

### Discoveries
- **gotcha**: tree-sitter 0.25 API changed - must use `Query()` constructor + `QueryCursor()` instead of deprecated `lang.query().captures()`
- **insight**: `QueryCursor.matches()` returns list of (pattern_idx, dict_of_captures) tuples - need to iterate over dict values

### Evidence
```bash
$ python
>>> from lib.parser import parse_file
>>> from lib.queries import run_import_query
>>> tree = parse_file(Path("/workspaces/flow_squared/tests/fixtures/samples/python/auth_handler.py"), "python")
>>> results = run_import_query("python", tree.root_node)
>>> len(results)
4
>>> for name, node in results:
...     print(f"{name}: line {node.start_point[0]+1}")
import_from: line 7
import_from: line 8
import_from: line 9
import: line 174
```

### Files Changed
- Created `/workspaces/flow_squared/scripts/cross-files-rels-research/lib/queries.py`

**Completed**: 2026-01-12

---

## Task T004: Create lib/resolver.py (out of order - no dependencies)
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Created `lib/resolver.py` with confidence scoring logic:
- `calculate_confidence(rel_type, context, lang)` - main entry point
- Language-specific constructor detection per didyouknow insight #3
- Helper functions: `import_confidence()`, `call_confidence()`
- Private helpers: `_is_pascal_case()`, `_is_go_constructor_pattern()`

Confidence tiers implemented:
- 1.0: node_id (explicit fs2 references)
- 0.9: import, import_from (top-level)
- 0.8: call_self, new keyword constructor
- 0.6: function-scoped, typed, Go NewXxx()
- 0.5: type-only import, Python PascalCase
- 0.4: Go dot import
- 0.3: inferred, Go blank import
- 0.1: fuzzy/reference

### Evidence
```bash
$ python -c "from lib.resolver import calculate_confidence; assert calculate_confidence('import', {}) == 0.9; assert calculate_confidence('node_id', {}) == 1.0; print('OK')"
OK

# Python constructor (PascalCase → 0.5)
>>> calculate_confidence('call_constructor', {'name': 'AuthHandler'}, 'python')
0.5

# TypeScript with new keyword → 0.8
>>> calculate_confidence('call_constructor', {'name': 'EventEmitter', 'has_new_keyword': True}, 'typescript')
0.8

# Go NewXxx pattern → 0.6
>>> calculate_confidence('call_constructor', {'name': 'NewServer'}, 'go')
0.6
```

### Files Changed
- Created `/workspaces/flow_squared/scripts/cross-files-rels-research/lib/resolver.py`

**Completed**: 2026-01-12

---

## Task T003: Create lib/extractors.py
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Created `lib/extractors.py` with:
- `extract_imports(tree, lang)` - extract all imports from AST
- `extract_calls(tree, lang)` - extract all function/method calls
- `_is_function_scoped(node)` - parent-traversal for scope detection (per didyouknow #2)
- Language-specific extractors for Python, TypeScript, Go, Java, C/C++

Key features:
- Function-scoped import detection via parent chain traversal
- Go multi-import block handling (import_spec_list → multiple dicts)
- TypeScript type-only import detection
- Python self/cls method call detection

### Evidence
```
Python Imports:
  dataclasses: names=['dataclass'], line=7, conf=0.9, scoped=False
  datetime: names=['datetime', 'timedelta'], line=8, conf=0.9, scoped=False
  enum: names=['Enum'], line=9, conf=0.9, scoped=False
  uuid: names=None, line=174, conf=0.6, scoped=True  # <- Function-scoped detected!

Go Imports:
  context: line=6, conf=0.9
  encoding/json: line=7, conf=0.9
  fmt: line=8, conf=0.9
```

### Discoveries
- **gotcha**: Go import blocks return list (not dict) - need to flatten in caller
- **insight**: auth_handler.py has function-scoped `import uuid` at line 174 - correctly detected with 0.6 confidence

### Files Changed
- Created `/workspaces/flow_squared/scripts/cross-files-rels-research/lib/extractors.py`

**Completed**: 2026-01-12

---

## Task T005: Create 01_nodeid_detection.py and test_data
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Created two files:
1. `test_data/sample_nodeid.md` - Test file with 11 node_id patterns
2. `experiments/01_nodeid_detection.py` - Regex scanner for fs2 node_ids

Features:
- Regex pattern: `\b(file|callable|type|class|method):[\w./]+(?::[\w.]+)?\b`
- Scans text files (md, py, ts, go, etc.)
- Outputs JSON with file, line, column, node_id, category, path, symbol
- Confidence: 1.0 for all node_id matches

### Evidence
```bash
$ python experiments/01_nodeid_detection.py test_data/
{
  "meta": {
    "files_scanned": 1,
    "files_with_matches": 1,
    "total_matches": 11
  },
  "matches": [
    {"node_id": "file:src/lib/parser.py", "category": "file", ...},
    {"node_id": "class:src/lib/parser.py:Parser", "category": "class", ...},
    {"node_id": "method:src/lib/parser.py:Parser.detect_language", ...},
    ...11 total matches
  ]
}
```

### Files Changed
- Created `/workspaces/flow_squared/scripts/cross-files-rels-research/test_data/sample_nodeid.md`
- Created `/workspaces/flow_squared/scripts/cross-files-rels-research/experiments/01_nodeid_detection.py`

**Completed**: 2026-01-12

---

## Task T006: Create 02_import_extraction.py
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Created `experiments/02_import_extraction.py` that:
- Scans directories for code files
- Uses lib/parser.py to parse files
- Uses lib/extractors.py to extract imports
- Outputs JSON with imports grouped by file

### Evidence
```bash
$ python experiments/02_import_extraction.py /workspaces/flow_squared/tests/fixtures/samples
{
  "meta": {
    "files_scanned": 11,
    "files_with_imports": 8,
    "total_imports": 45,
    "by_language": {"c": {"files": 1, "imports": 4}, "go": {...}, "python": {"files": 2, "imports": 13}, ...}
  },
  "files": [...]
}
```

Key findings:
- Python: 13 imports (including function-scoped `import uuid` with 0.6 confidence)
- TypeScript/TSX: 2 imports
- Go: 10 imports
- Java: 6 imports
- C/C++: 14 includes

### Files Changed
- Created `/workspaces/flow_squared/scripts/cross-files-rels-research/experiments/02_import_extraction.py`

**Completed**: 2026-01-12

---

## Task T007: Create 03_call_extraction.py
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Created `experiments/03_call_extraction.py` that:
- Scans directories for code files
- Uses lib/parser.py to parse files
- Uses lib/extractors.py to extract function/method calls
- Tracks constructors with language-specific confidence
- Outputs JSON with calls grouped by file

### Evidence
```bash
$ python experiments/03_call_extraction.py /workspaces/flow_squared/tests/fixtures/samples
{
  "meta": {
    "files_scanned": 11,
    "files_with_calls": 6,
    "total_calls": 212,
    "total_constructors": 36,
    "by_language": {"python": {"files": 2, "calls": 73, "constructors": 17}, "go": {...}, ...}
  },
  "files": [...]
}
```

Key findings:
- Python: 73 calls, 17 constructors detected
- Go: 51 calls, 3 constructors (NewXxx pattern)
- TypeScript/TSX: 60 calls, 12 constructors
- JavaScript: 28 calls, 4 constructors

### Files Changed
- Created `/workspaces/flow_squared/scripts/cross-files-rels-research/experiments/03_call_extraction.py`

**Completed**: 2026-01-12

---

## Task T008: Validation Run
**Started**: 2026-01-12
**Status**: ✅ Complete

### What I Did
Ran all three extraction scripts and saved output to results/:
1. `python experiments/01_nodeid_detection.py test_data/ > results/01_nodeid.json`
2. `python experiments/02_import_extraction.py /workspaces/flow_squared/tests/fixtures/samples > results/02_imports.json`
3. `python experiments/03_call_extraction.py /workspaces/flow_squared/tests/fixtures/samples > results/03_calls.json`

### Evidence
```bash
$ python -c "import json; d=json.load(open('results/01_nodeid.json')); print('01_nodeid.json: valid JSON,', d['meta']['total_matches'], 'matches')"
01_nodeid.json: valid JSON, 11 matches

$ python -c "import json; d=json.load(open('results/02_imports.json')); print('02_imports.json: valid JSON,', d['meta']['total_imports'], 'imports')"
02_imports.json: valid JSON, 45 imports

$ python -c "import json; d=json.load(open('results/03_calls.json')); print('03_calls.json: valid JSON,', d['meta']['total_calls'], 'calls')"
03_calls.json: valid JSON, 212 calls
```

### Files Changed
- Created `/workspaces/flow_squared/scripts/cross-files-rels-research/results/01_nodeid.json`
- Created `/workspaces/flow_squared/scripts/cross-files-rels-research/results/02_imports.json`
- Created `/workspaces/flow_squared/scripts/cross-files-rels-research/results/03_calls.json`

**Completed**: 2026-01-12

---

## Phase Summary

### Tasks Completed: 9/9 (100%)

| Task | Description | Status |
|------|-------------|--------|
| T001 | Create lib/parser.py | ✅ |
| T001a | Validate Tree-sitter query syntax | ✅ |
| T002 | Create lib/queries.py | ✅ |
| T003 | Create lib/extractors.py | ✅ |
| T004 | Create lib/resolver.py | ✅ |
| T005 | Create 01_nodeid_detection.py + test_data | ✅ |
| T006 | Create 02_import_extraction.py | ✅ |
| T007 | Create 03_call_extraction.py | ✅ |
| T008 | Validation run | ✅ |

### Key Deliverables

1. **Library Modules** (`lib/`):
   - `parser.py` - Tree-sitter initialization, language detection
   - `queries.py` - Import and call query patterns for 10 languages
   - `extractors.py` - Import/call extraction with parent-traversal
   - `resolver.py` - Confidence scoring with language-specific heuristics

2. **Experiment Scripts** (`experiments/`):
   - `01_nodeid_detection.py` - Node ID regex extraction
   - `02_import_extraction.py` - Import extraction from code
   - `03_call_extraction.py` - Call/constructor extraction

3. **Test Data** (`test_data/`):
   - `sample_nodeid.md` - 11 node_id patterns for testing

4. **Results** (`results/`):
   - `01_nodeid.json` - 11 node_id matches
   - `02_imports.json` - 45 imports across 11 files
   - `03_calls.json` - 212 calls with 36 constructors

### Acceptance Criteria Met

- [x] All lib modules importable and functional
- [x] All experiment scripts exit 0 with valid JSON output
- [x] Function-scoped import detection working (auth_handler.py line 174: uuid with 0.6 confidence)
- [x] Language-specific constructor confidence working (Python PascalCase→0.5, Go NewXxx→0.6)
- [x] Tree-sitter 0.25 API compatibility verified

### Key Discoveries

| Date | Task | Type | Discovery |
|------|------|------|-----------|
| 2026-01-12 | T002 | gotcha | tree-sitter 0.25 API changed - use Query() + QueryCursor() |
| 2026-01-12 | T003 | gotcha | Go import blocks return list - need to flatten |
| 2026-01-12 | T003 | insight | auth_handler.py has function-scoped import uuid at line 174 |
| 2026-01-12 | T001a | insight | Go uses interpreted_string_literal not string for paths |

### Ready for Phase 3

Phase 2 complete. Ready to proceed with Phase 3: Fixture Enrichment.

