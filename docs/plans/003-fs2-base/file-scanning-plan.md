# File Scanning Implementation Plan

**Plan Version**: 1.0.0
**Created**: 2025-12-12
**Spec**: [./file-scanning-spec.md](./file-scanning-spec.md)
**Status**: READY

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Technical Context](#technical-context)
3. [Critical Research Findings](#critical-research-findings)
4. [Testing Philosophy](#testing-philosophy)
5. [Implementation Phases](#implementation-phases)
   - [Phase 1: Core Models and Configuration](#phase-1-core-models-and-configuration)
   - [Phase 2: File Scanner Adapter](#phase-2-file-scanner-adapter)
   - [Phase 3: AST Parser Adapter](#phase-3-ast-parser-adapter)
   - [Phase 4: Graph Storage Repository](#phase-4-graph-storage-repository)
   - [Phase 5: Scan Service Orchestration](#phase-5-scan-service-orchestration)
   - [Phase 6: CLI Command and Documentation](#phase-6-cli-command-and-documentation)
6. [Cross-Cutting Concerns](#cross-cutting-concerns)
7. [Complexity Tracking](#complexity-tracking)
8. [Progress Tracking](#progress-tracking)
9. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

**Problem**: Flowspace v2 needs to scan codebases, parse source files with tree-sitter, and store the resulting code structure as nodes in a queryable graph. Without this capability, no downstream features (search, documentation, embeddings) are possible.

**Solution Approach**:
- Create frozen dataclass domain models for code nodes and scan results
- Implement FileScanner adapter for gitignore-aware directory traversal
- Implement ASTParser adapter for tree-sitter parsing with language detection
- Implement GraphStore repository for networkx graph persistence
- Orchestrate via ScanService with retry and error handling
- Expose via CLI `fs2 scan` command with Rich progress bar

**Expected Outcomes**:
- Users can configure scan paths and run `fs2 scan`
- Graph persisted to `.fs2/graph.gpickle` with all code nodes
- 10 acceptance criteria from spec verified via tests

**Success Metrics**:
- All 10 acceptance criteria pass
- Test coverage >80% on new code
- Constitution compliance verified

---

## Technical Context

### Current System State
- fs2 architecture established with config system, adapter pattern, service composition
- No file scanning capability exists
- Dependencies ready: pydantic, typer, rich, pytest

### Integration Requirements
- Add `tree-sitter-language-pack` for multi-language parsing
- Add `networkx` for graph storage
- Add `pathspec` for gitignore pattern matching
- Integrate with existing `ConfigurationService` pattern
- Follow existing adapter ABC conventions

### Constraints and Limitations
- Python 3.12+ required (tree-sitter-language-pack constraint)
- No mocks allowed (fakes only, per constitution)
- Full TDD approach (tests first)
- No SDK types in ABCs

### Assumptions
- tree-sitter-language-pack works with Python 3.12
- pathspec handles gitignore edge cases correctly
- networkx gpickle is sufficient for MVP scale (<50k files)

---

## Critical Research Findings

### 01: ConfigurationService Registry Pattern
**Impact**: Critical | **Sources**: S1-01, S1-03, S4-01
**What**: All adapters receive `ConfigurationService` (registry), not extracted config. Each component internally calls `config.require(TheirConfigType)`.
**Action Required**: FileScanner, ASTParser, GraphStore, and ScanService constructors must accept `ConfigurationService` and extract own config internally.
**Affects Phases**: Phase 1, 2, 3, 4, 5

### 02: Adapter ABC with Dual Implementation Pattern
**Impact**: Critical | **Sources**: S1-01, S1-05, S4-02
**What**: Every adapter needs ABC (no implementation), Fake (test double), and Impl (production). ABCs use domain types only.
**Action Required**: Create `file_scanner.py` (ABC), `file_scanner_fake.py`, `file_scanner_impl.py` for each adapter type.
**Affects Phases**: Phase 2, 3, 4

### 03: Tree-sitter Node Traversal Performance
**Impact**: High | **Sources**: S2-02
**What**: Using `.child(i)` is O(log i) per call. Use `.children` property or `TreeCursor` for O(n) iteration.
**Action Required**: ASTParser implementation must use `for child in node.children:` not index-based access.
**Affects Phases**: Phase 3

### 04: Pathspec Gitignore Negation Semantics
**Impact**: High | **Sources**: S2-05, S3-03
**What**: Negation patterns (`!pattern`) cannot un-exclude files whose parent directory is excluded. Nested .gitignore files need manual tree walking.
**Action Required**: FileScanner must walk directories depth-first, merging .gitignore patterns at each level.
**Affects Phases**: Phase 2

### 05: NetworkX Pickle Deprecation
**Impact**: High | **Sources**: S2-08
**What**: `nx.write_gpickle` deprecated in v3.0+. Use standard `pickle` module directly with version metadata.
**Action Required**: GraphStore must use `pickle.dump()` with format version header for future compatibility.
**Affects Phases**: Phase 4

### 06: Symlink Handling Undefined
**Impact**: High | **Sources**: S3-01
**What**: Spec silent on symlink traversal. Circular symlinks can cause infinite loops.
**Action Required**: Default `follow_symlinks=False` in ScanConfig. Log warnings when symlinks skipped.
**Affects Phases**: Phase 1, 2

### 07: Binary File Detection
**Impact**: High | **Sources**: S3-02
**What**: Binary files will crash tree-sitter. Need pre-parse validation.
**Action Required**: ASTParser must check for null bytes in first 8KB before parsing. Skip binary files gracefully.
**Affects Phases**: Phase 3

### 08: AST Hierarchy Depth Undefined
**Impact**: High | **Sources**: S3-05
**What**: Spec says "file → class → method" but doesn't specify depth limit or node type filtering.
**Action Required**: Extract only `is_named=True` nodes up to depth 4. Define language-family rules.
**Affects Phases**: Phase 3

### 09: Frozen Dataclass Domain Models
**Impact**: High | **Sources**: S1-06, S4-03
**What**: All domain models use `@dataclass(frozen=True)` with `ok()`/`fail()` factory methods.
**Action Required**: CodeNode and ScanResult must be frozen dataclasses with factory methods.
**Affects Phases**: Phase 1

### 10: Exception Translation at Adapter Boundary
**Impact**: High | **Sources**: S1-04, S4-04
**What**: Catch OS/SDK exceptions in adapters and translate to domain exceptions with actionable messages.
**Action Required**: Define `FileScannerError`, `ASTParserError` extending `AdapterError`. Translate all OS errors.
**Affects Phases**: Phase 2, 3, 4

### 11: Node ID Uniqueness
**Impact**: Medium | **Sources**: S3-07
**What**: Format `{type}:{path}:{symbol}` may have collisions with anonymous functions or overloaded methods.
**Action Required**: Use file-relative paths with counter for anonymous nodes (e.g., `<lambda_0>`).
**Affects Phases**: Phase 1, 3

### 12: Large File Truncation
**Impact**: Medium | **Sources**: S3-06
**What**: Files larger than `max_file_size_kb` should be sampled (first N lines), not skipped entirely.
**Action Required**: Add `truncated: bool` field to CodeNode. Sample first `sample_lines_for_large_files` lines.
**Affects Phases**: Phase 1, 2, 3

### 13: Language Detection Ambiguity
**Impact**: Medium | **Sources**: S3-04
**What**: Extensions like `.h` are ambiguous (C vs C++). Filename matching case-sensitive on Linux.
**Action Required**: Use static mapping with `.h` → `cpp` default. Support config override for specific extensions.
**Affects Phases**: Phase 3

### 14: Graph Format Versioning
**Impact**: Medium | **Sources**: S3-08
**What**: Pickle format is Python-version sensitive. Need version header for future compatibility.
**Action Required**: Store `(metadata, graph)` tuple where metadata includes `format_version: "1.0"`.
**Affects Phases**: Phase 4

### 15: Service Composition Pattern
**Impact**: High | **Sources**: S1-08, S4-08
**What**: Services receive both ConfigurationService AND adapter ABCs via constructor. Services handle retry, batching.
**Action Required**: ScanService receives ConfigurationService + FileScanner + ASTParser + GraphStore ABCs.
**Affects Phases**: Phase 5

---

## Testing Philosophy

### Testing Approach
- **Selected Approach**: Full TDD
- **Rationale**: Foundational feature with file I/O, external library integration, and data integrity concerns
- **Focus Areas**: Gitignore edge cases, tree-sitter parsing, graph persistence, error handling
- **Mock Usage**: Avoid mocks entirely; use real fixtures and fake adapter implementations per fs2 pattern

### Test-Driven Development
For each component:
1. Write tests FIRST (RED) - tests define expected behavior
2. Implement minimal code (GREEN) - just enough to pass
3. Refactor for quality (REFACTOR) - clean up while tests protect

### Test Documentation
Every test MUST include:
```python
"""
Purpose: [what truth this test proves]
Quality Contribution: [how this prevents bugs]
Acceptance Criteria: [measurable assertions]
"""
```

### Test Fixtures
- Use real file system with `tmp_path` pytest fixture
- Create test fixtures in `tests/fixtures/` for sample codebases
- Use `FakeConfigurationService` for all config injection
- Fake adapters record call history for verification

### Test Commands

```bash
# Run all unit tests
uv run pytest tests/unit/ -v

# Run specific phase tests
uv run pytest tests/unit/models/test_code_node.py -v          # Phase 1
uv run pytest tests/unit/config/test_scan_config.py -v        # Phase 1
uv run pytest tests/unit/adapters/test_file_scanner*.py -v    # Phase 2
uv run pytest tests/unit/adapters/test_ast_parser*.py -v      # Phase 3
uv run pytest tests/unit/repos/test_graph_store*.py -v        # Phase 4
uv run pytest tests/unit/services/test_scan_service.py -v     # Phase 5
uv run pytest tests/unit/cli/test_scan_cli.py -v              # Phase 6

# Run integration tests
uv run pytest tests/integration/test_scan_integration.py -v   # Phase 5-6

# Lint and type check
uv run ruff check src/fs2/
uv run mypy src/fs2/
```

---

## Implementation Phases

### Phase 1: Core Models and Configuration

**Objective**: Create foundational domain models and configuration types for file scanning.

**Deliverables**:
- `CodeNode` frozen dataclass in `src/fs2/core/models/code_node.py`
- `ScanConfig` Pydantic model in `src/fs2/config/objects.py`
- Domain exceptions in `src/fs2/core/adapters/exceptions.py`
- Updated `pyproject.toml` with new dependencies

**Dependencies**: None (foundational phase)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Model design changes later | Medium | Low | Design for extensibility with optional fields |
| Dependency conflicts | Low | Medium | Pin versions explicitly |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 1.1 | [x] | Add dependencies to pyproject.toml | 1 | networkx, tree-sitter-language-pack, pathspec in deps | [📋](tasks/phase-1/execution.log.md#t001-t002-dependencies-setup) | Pin versions [^1] |
| 1.2 | [x] | Write tests for CodeNode model | 2 | Tests cover: frozen, factory methods, node_id format, truncated flag | [📋](tasks/phase-1/execution.log.md#t003-t021-codenode-implementation-full-tdd) | tests/unit/models/test_code_node.py [^2] |
| 1.3 | [x] | Implement CodeNode to pass tests | 2 | All tests from 1.2 pass | [📋](tasks/phase-1/execution.log.md#t003-t021-codenode-implementation-full-tdd) | src/fs2/core/models/code_node.py [^2] |
| 1.4 | [x] | Write tests for ScanConfig | 2 | Tests cover: validation, defaults, YAML loading | [📋](tasks/phase-1/execution.log.md#t022-t027-scanconfig-implementation-full-tdd) | tests/unit/config/test_scan_config.py [^3] |
| 1.5 | [x] | Implement ScanConfig to pass tests | 2 | All tests from 1.4 pass, registered in YAML_CONFIG_TYPES | [📋](tasks/phase-1/execution.log.md#t022-t027-scanconfig-implementation-full-tdd) | src/fs2/config/objects.py [^3] |
| 1.6 | [x] | Write tests for domain exceptions | 1 | Tests cover: FileScannerError, ASTParserError, GraphStoreError | [📋](tasks/phase-1/execution.log.md#t028-t031-domain-exceptions-implementation-full-tdd) | tests/unit/adapters/test_exceptions.py [^4] |
| 1.7 | [x] | Add domain exceptions | 1 | All tests from 1.6 pass | [📋](tasks/phase-1/execution.log.md#t028-t031-domain-exceptions-implementation-full-tdd) | src/fs2/core/adapters/exceptions.py [^4] |
| 1.8 | [x] | Export models from __init__.py | 1 | Can import from fs2.core.models | [📋](tasks/phase-1/execution.log.md#t032-export-models) | Clean module exports [^5] |

### Test Examples (Write First!)

```python
# tests/unit/models/test_code_node.py
import pytest
from fs2.core.models.code_node import CodeNode

def test_given_code_node_when_created_then_is_frozen():
    """
    Purpose: Proves CodeNode immutability per Constitution P5.
    Quality Contribution: Prevents accidental mutation across async contexts.
    Acceptance Criteria: Mutation raises FrozenInstanceError.
    """
    node = CodeNode(
        node_id="file:src/main.py",
        node_type="file",
        name="main.py",
        file_path="/abs/path/src/main.py",
        start_line=1,
        end_line=100,
        content="# file content"
    )

    with pytest.raises(AttributeError):  # FrozenInstanceError
        node.name = "changed"

def test_given_method_node_when_created_then_node_id_format_correct():
    """
    Purpose: Verifies node_id format matches spec AC7.
    Quality Contribution: Ensures consistent ID scheme for graph queries.
    Acceptance Criteria: ID follows {type}:{path}:{symbol} format.
    """
    node = CodeNode(
        node_id="method:src/calc.py:Calculator.add",
        node_type="method",
        name="add",
        file_path="/abs/path/src/calc.py",
        start_line=10,
        end_line=15,
        content="def add(self, a, b): return a + b"
    )

    assert node.node_id == "method:src/calc.py:Calculator.add"
    assert node.node_type == "method"
```

### Non-Happy-Path Coverage
- [x] Empty content handling
- [x] Invalid node_id format validation
- [x] Missing required fields
- [x] Truncated flag with truncated_at_line

### Acceptance Criteria
- [x] All tests passing (236 tests)
- [x] CodeNode is frozen dataclass
- [x] ScanConfig loads from YAML and env vars
- [x] Dependencies installed and importable
- [x] No SDK types in models

---

### Phase 2: File Scanner Adapter

**Objective**: Create adapter for gitignore-aware directory traversal.

**Deliverables**:
- `FileScanner` ABC in `src/fs2/core/adapters/file_scanner.py`
- `FakeFileScanner` in `src/fs2/core/adapters/file_scanner_fake.py`
- `FileSystemScanner` impl in `src/fs2/core/adapters/file_scanner_impl.py`

**Dependencies**: Phase 1 complete

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Gitignore edge cases | Medium | Medium | Use pathspec library, test extensively |
| Symlink loops | Low | High | Default follow_symlinks=False |
| Permission errors | Medium | Low | Translate to domain exception, continue |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 2.1 | [ ] | Write tests for FileScanner ABC | 1 | Tests verify ABC cannot be instantiated | - | tests/unit/adapters/test_file_scanner.py |
| 2.2 | [ ] | Create FileScanner ABC | 1 | ABC with scan(), should_ignore() methods | - | src/fs2/core/adapters/file_scanner.py |
| 2.3 | [ ] | Write tests for FakeFileScanner | 2 | Tests cover: call history, configurable results | - | tests/unit/adapters/test_file_scanner_fake.py |
| 2.4 | [ ] | Implement FakeFileScanner | 2 | All tests from 2.3 pass | - | src/fs2/core/adapters/file_scanner_fake.py |
| 2.5 | [ ] | Write tests for FileSystemScanner gitignore | 3 | Tests cover: AC2, AC3 (root + nested gitignore) | - | tests/unit/adapters/test_file_scanner_impl.py |
| 2.6 | [ ] | Write tests for FileSystemScanner traversal | 2 | Tests cover: recursive scan, symlink handling | - | tests/unit/adapters/test_file_scanner_impl.py |
| 2.7 | [ ] | Implement FileSystemScanner | 3 | All tests from 2.5, 2.6 pass | - | src/fs2/core/adapters/file_scanner_impl.py |
| 2.8 | [ ] | Write tests for permission error handling | 1 | Tests cover: AC10 (graceful error handling) | - | tests/unit/adapters/test_file_scanner_impl.py |
| 2.9 | [ ] | Add exception translation | 1 | PermissionError → FileScannerError | - | src/fs2/core/adapters/file_scanner_impl.py |

### Test Examples (Write First!)

```python
# tests/unit/adapters/test_file_scanner_impl.py
import pytest
from pathlib import Path
from fs2.config.service import FakeConfigurationService
from fs2.config.objects import ScanConfig
from fs2.core.adapters.file_scanner_impl import FileSystemScanner

def test_given_gitignore_with_log_pattern_when_scanning_then_excludes_log_files(tmp_path):
    """
    Purpose: Verifies AC2 - root .gitignore compliance.
    Quality Contribution: Ensures ignored files don't pollute scan results.
    Acceptance Criteria: *.log files excluded, other files included.
    """
    # Arrange
    (tmp_path / ".gitignore").write_text("*.log\nnode_modules/\n")
    (tmp_path / "app.py").write_text("print('hello')")
    (tmp_path / "debug.log").write_text("log data")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("module")

    config = FakeConfigurationService(
        ScanConfig(scan_paths=[str(tmp_path)], respect_gitignore=True)
    )
    scanner = FileSystemScanner(config)

    # Act
    files = scanner.scan()

    # Assert
    file_names = [f.name for f in files]
    assert "app.py" in file_names
    assert "debug.log" not in file_names
    assert "pkg.js" not in file_names

def test_given_nested_gitignore_when_scanning_then_applies_subtree_only(tmp_path):
    """
    Purpose: Verifies AC3 - nested .gitignore scoping.
    Quality Contribution: Prevents over-exclusion from nested patterns.
    Acceptance Criteria: Pattern in vendor/ only affects vendor/ subtree.
    """
    # Arrange
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "vendor").mkdir()
    (tmp_path / "src" / "vendor" / ".gitignore").write_text("*.generated.py\n")
    (tmp_path / "src" / "vendor" / "lib.py").write_text("# lib")
    (tmp_path / "src" / "vendor" / "lib.generated.py").write_text("# generated")
    (tmp_path / "src" / "main.generated.py").write_text("# not in vendor")

    config = FakeConfigurationService(
        ScanConfig(scan_paths=[str(tmp_path)], respect_gitignore=True)
    )
    scanner = FileSystemScanner(config)

    # Act
    files = scanner.scan()

    # Assert
    file_names = [f.name for f in files]
    assert "lib.py" in file_names
    assert "lib.generated.py" not in file_names  # Excluded by nested
    assert "main.generated.py" in file_names     # Not affected by vendor/.gitignore
```

### Non-Happy-Path Coverage
- [ ] Empty directory
- [ ] Non-existent scan path
- [ ] Permission denied on directory
- [ ] Circular symlinks (when follow_symlinks=True)
- [ ] Malformed .gitignore file

### Acceptance Criteria
- [ ] All tests passing
- [ ] AC2: Root .gitignore patterns respected
- [ ] AC3: Nested .gitignore patterns scoped correctly
- [ ] Symlinks not followed by default
- [ ] Permission errors logged, scan continues

---

### Phase 3: AST Parser Adapter

**Objective**: Create adapter for tree-sitter parsing with language detection.

**Deliverables**:
- `ASTParser` ABC in `src/fs2/core/adapters/ast_parser.py`
- `FakeASTParser` in `src/fs2/core/adapters/ast_parser_fake.py`
- `TreeSitterParser` impl in `src/fs2/core/adapters/ast_parser_impl.py`
- Language detection mapping

**Dependencies**: Phase 1 complete

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Grammar missing for language | Medium | Medium | Fall back to file-only node |
| Binary file crashes parser | Medium | High | Pre-check for null bytes |
| Large file memory issues | Low | Medium | Sample first N lines |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 3.1 | [ ] | Write tests for ASTParser ABC | 1 | Tests verify ABC contract | - | tests/unit/adapters/test_ast_parser.py |
| 3.2 | [ ] | Create ASTParser ABC | 1 | ABC with parse(), detect_language() methods | - | src/fs2/core/adapters/ast_parser.py |
| 3.3 | [ ] | Write tests for FakeASTParser | 2 | Tests cover: call history, configurable results | - | tests/unit/adapters/test_ast_parser_fake.py |
| 3.4 | [ ] | Implement FakeASTParser | 2 | All tests from 3.3 pass | - | src/fs2/core/adapters/ast_parser_fake.py |
| 3.5 | [ ] | Write tests for language detection (AC4) | 2 | Tests cover: .py, .ts, .md, .tf, Dockerfile | - | tests/unit/adapters/test_ast_parser_impl.py |
| 3.6 | [ ] | Write tests for AST hierarchy extraction (AC5) | 3 | Tests cover: Python class with methods → graph nodes | - | tests/unit/adapters/test_ast_parser_impl.py |
| 3.7 | [ ] | Write tests for large file handling (AC6) | 2 | Tests cover: truncation, sample_lines | - | tests/unit/adapters/test_ast_parser_impl.py |
| 3.8 | [ ] | Implement TreeSitterParser | 3 | All tests from 3.5, 3.6, 3.7 pass | - | src/fs2/core/adapters/ast_parser_impl.py |
| 3.9 | [ ] | Write tests for binary file detection | 1 | Tests cover: binary skipped, warning logged | - | tests/unit/adapters/test_ast_parser_impl.py |
| 3.10 | [ ] | Add binary detection and error handling | 1 | Binary files return empty node list, no crash | - | src/fs2/core/adapters/ast_parser_impl.py |

### Test Examples (Write First!)

```python
# tests/unit/adapters/test_ast_parser_impl.py
import pytest
from pathlib import Path
from fs2.config.service import FakeConfigurationService
from fs2.config.objects import ScanConfig
from fs2.core.adapters.ast_parser_impl import TreeSitterParser

def test_given_python_file_when_parsing_then_detects_language(tmp_path):
    """
    Purpose: Verifies AC4 - language detection for Python.
    Quality Contribution: Ensures correct grammar applied per extension.
    Acceptance Criteria: .py files detected as Python.
    """
    # Arrange
    py_file = tmp_path / "calculator.py"
    py_file.write_text("class Calculator:\n    def add(self, a, b):\n        return a + b\n")

    config = FakeConfigurationService(ScanConfig())
    parser = TreeSitterParser(config)

    # Act
    language = parser.detect_language(py_file)

    # Assert
    assert language == "python"

def test_given_python_class_with_methods_when_parsing_then_extracts_hierarchy(tmp_path):
    """
    Purpose: Verifies AC5 - AST hierarchy extraction.
    Quality Contribution: Ensures graph contains structural code elements.
    Acceptance Criteria: File → Class → Method nodes extracted.
    """
    # Arrange
    py_file = tmp_path / "calculator.py"
    py_file.write_text('''
class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b
''')

    config = FakeConfigurationService(ScanConfig())
    parser = TreeSitterParser(config)

    # Act
    nodes = parser.parse(py_file)

    # Assert
    node_types = [n.node_type for n in nodes]
    node_names = [n.name for n in nodes]

    assert "file" in node_types
    assert "class" in node_types
    assert "method" in node_types
    assert "Calculator" in node_names
    assert "add" in node_names
    assert "subtract" in node_names
```

### Non-Happy-Path Coverage
- [ ] Unknown file extension
- [ ] Empty file
- [ ] Syntax error in source
- [ ] Binary file (null bytes)
- [ ] Encoding errors (non-UTF8)
- [ ] File larger than max_file_size_kb

### Acceptance Criteria
- [ ] All tests passing
- [ ] AC4: Language detection works for .py, .ts, .md, .tf, Dockerfile
- [ ] AC5: File → Class → Method hierarchy extracted
- [ ] AC6: Large files truncated with flag set
- [ ] Binary files skipped gracefully

---

### Phase 4: Graph Storage Repository

**Objective**: Create repository for networkx graph persistence.

**Deliverables**:
- `GraphStore` ABC in `src/fs2/core/repos/graph_store.py`
- `FakeGraphStore` in `src/fs2/core/repos/graph_store_fake.py`
- `NetworkXGraphStore` impl in `src/fs2/core/repos/graph_store_impl.py`

**Dependencies**: Phase 1 complete

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Pickle version incompatibility | Low | Medium | Add format version header |
| Large graph memory usage | Low | Medium | Profile with real data |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 4.1 | [ ] | Write tests for GraphStore ABC | 1 | Tests verify ABC contract | - | tests/unit/repos/test_graph_store.py |
| 4.2 | [ ] | Create GraphStore ABC | 1 | ABC with add_node, add_edge, get_node, save, load | - | src/fs2/core/repos/graph_store.py |
| 4.3 | [ ] | Write tests for FakeGraphStore | 2 | Tests cover: in-memory storage, call history | - | tests/unit/repos/test_graph_store_fake.py |
| 4.4 | [ ] | Implement FakeGraphStore | 2 | All tests from 4.3 pass | - | src/fs2/core/repos/graph_store_fake.py |
| 4.5 | [ ] | Write tests for graph persistence (AC8) | 2 | Tests cover: save, load, 100+ nodes recoverable | - | tests/unit/repos/test_graph_store_impl.py |
| 4.6 | [ ] | Write tests for node relationships | 2 | Tests cover: parent-child edges, get_children | - | tests/unit/repos/test_graph_store_impl.py |
| 4.7 | [ ] | Implement NetworkXGraphStore | 2 | All tests from 4.5, 4.6 pass | - | src/fs2/core/repos/graph_store_impl.py |
| 4.8 | [ ] | Add format versioning | 1 | Metadata includes format_version: "1.0" | - | src/fs2/core/repos/graph_store_impl.py |

### Test Examples (Write First!)

```python
# tests/unit/repos/test_graph_store_impl.py
import pytest
from pathlib import Path
from fs2.config.service import FakeConfigurationService
from fs2.config.objects import ScanConfig
from fs2.core.models.code_node import CodeNode
from fs2.core.repos.graph_store_impl import NetworkXGraphStore

def test_given_100_nodes_when_saved_and_loaded_then_all_recoverable(tmp_path):
    """
    Purpose: Verifies AC8 - graph persistence and recovery.
    Quality Contribution: Ensures data integrity across save/load cycles.
    Acceptance Criteria: All 100 nodes recoverable with relationships.
    """
    # Arrange
    graph_path = tmp_path / "test.gpickle"
    config = FakeConfigurationService(ScanConfig())
    store = NetworkXGraphStore(config)

    # Create 100 nodes
    for i in range(100):
        node = CodeNode(
            node_id=f"file:src/file_{i}.py",
            node_type="file",
            name=f"file_{i}.py",
            file_path=f"/abs/path/src/file_{i}.py",
            start_line=1,
            end_line=50,
            content=f"# content {i}"
        )
        store.add_node(node)

    # Act
    store.save(graph_path)

    new_store = NetworkXGraphStore(config)
    new_store.load(graph_path)

    # Assert
    for i in range(100):
        node = new_store.get_node(f"file:src/file_{i}.py")
        assert node is not None
        assert node.name == f"file_{i}.py"

def test_given_parent_child_relationship_when_queried_then_returns_children(tmp_path):
    """
    Purpose: Verifies graph edge relationships work correctly.
    Quality Contribution: Ensures hierarchy queries return correct results.
    Acceptance Criteria: get_children returns all child nodes.
    """
    # Arrange
    config = FakeConfigurationService(ScanConfig())
    store = NetworkXGraphStore(config)

    file_node = CodeNode(
        node_id="file:src/calc.py", node_type="file", name="calc.py",
        file_path="/abs/path/src/calc.py", start_line=1, end_line=100, content=""
    )
    class_node = CodeNode(
        node_id="class:src/calc.py:Calculator", node_type="class", name="Calculator",
        file_path="/abs/path/src/calc.py", start_line=1, end_line=50, content=""
    )
    method_node = CodeNode(
        node_id="method:src/calc.py:Calculator.add", node_type="method", name="add",
        file_path="/abs/path/src/calc.py", start_line=2, end_line=5, content=""
    )

    store.add_node(file_node)
    store.add_node(class_node)
    store.add_node(method_node)
    store.add_edge(file_node.node_id, class_node.node_id)
    store.add_edge(class_node.node_id, method_node.node_id)

    # Act
    file_children = store.get_children(file_node.node_id)
    class_children = store.get_children(class_node.node_id)

    # Assert
    assert len(file_children) == 1
    assert file_children[0].name == "Calculator"
    assert len(class_children) == 1
    assert class_children[0].name == "add"
```

### Non-Happy-Path Coverage
- [ ] Load non-existent file
- [ ] Load corrupted file
- [ ] Load wrong format version
- [ ] Get non-existent node
- [ ] Add duplicate node

### Acceptance Criteria
- [ ] All tests passing
- [ ] AC8: 100 nodes saved and loaded correctly
- [ ] Parent-child relationships preserved
- [ ] Format version in metadata
- [ ] Graceful error on load failure

---

### Phase 5: Scan Service Orchestration

**Objective**: Create service that orchestrates scanning, parsing, and storage.

**Deliverables**:
- `ScanService` in `src/fs2/core/services/scan_service.py`
- Integration tests verifying end-to-end flow

**Dependencies**: Phases 1, 2, 3, 4 complete

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Integration issues | Medium | Medium | Comprehensive integration tests |
| Error propagation | Low | Low | Clear error handling at each layer |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 5.1 | [ ] | Write tests for ScanService with fakes | 2 | Tests cover: constructor DI, config extraction | - | tests/unit/services/test_scan_service.py |
| 5.2 | [ ] | Write tests for scan orchestration | 3 | Tests cover: files scanned → parsed → stored | - | tests/unit/services/test_scan_service.py |
| 5.3 | [ ] | Write tests for error handling | 2 | Tests cover: partial failure continues, errors collected | - | tests/unit/services/test_scan_service.py |
| 5.4 | [ ] | Implement ScanService | 3 | All tests from 5.1, 5.2, 5.3 pass | - | src/fs2/core/services/scan_service.py |
| 5.5 | [ ] | Write integration tests with real adapters | 3 | Tests cover: AC1-AC8 end-to-end | - | tests/integration/test_scan_integration.py |
| 5.6 | [ ] | Verify all acceptance criteria | 2 | AC1-AC8 pass with real file system | - | tests/integration/test_scan_integration.py |

### Test Examples (Write First!)

```python
# tests/unit/services/test_scan_service.py
import pytest
from fs2.config.service import FakeConfigurationService
from fs2.config.objects import ScanConfig
from fs2.core.adapters.file_scanner_fake import FakeFileScanner
from fs2.core.adapters.ast_parser_fake import FakeASTParser
from fs2.core.repos.graph_store_fake import FakeGraphStore
from fs2.core.services.scan_service import ScanService

def test_given_scan_service_when_scanning_then_orchestrates_all_adapters():
    """
    Purpose: Verifies service correctly composes adapters.
    Quality Contribution: Ensures DI pattern works as designed.
    Acceptance Criteria: All adapters called in correct order.
    """
    # Arrange
    config = FakeConfigurationService(
        ScanConfig(scan_paths=["./src"])
    )
    scanner = FakeFileScanner(config)
    parser = FakeASTParser(config)
    store = FakeGraphStore(config)

    service = ScanService(
        config=config,
        file_scanner=scanner,
        ast_parser=parser,
        graph_store=store
    )

    # Act
    result = service.scan()

    # Assert
    assert result.success
    assert len(scanner.call_history) > 0  # Scanner was called
    assert len(parser.call_history) > 0   # Parser was called
    assert len(store.call_history) > 0    # Store was called

def test_given_parse_error_when_scanning_then_continues_and_collects_errors():
    """
    Purpose: Verifies AC10 - graceful error handling.
    Quality Contribution: Prevents single file failure from stopping scan.
    Acceptance Criteria: Errors collected, scan completes.
    """
    # Arrange
    config = FakeConfigurationService(
        ScanConfig(scan_paths=["./src"])
    )
    scanner = FakeFileScanner(config)
    parser = FakeASTParser(config)
    parser.simulate_error_for = ["bad_file.py"]  # Configure fake to fail
    store = FakeGraphStore(config)

    service = ScanService(
        config=config,
        file_scanner=scanner,
        ast_parser=parser,
        graph_store=store
    )

    # Act
    result = service.scan()

    # Assert
    assert result.success  # Overall success despite partial failure
    assert len(result.errors) > 0  # Errors collected
    assert "bad_file.py" in str(result.errors)
```

### Non-Happy-Path Coverage
- [ ] All files fail to parse
- [ ] Scanner returns empty list
- [ ] Graph save fails
- [ ] Config missing required fields

### Acceptance Criteria
- [ ] All tests passing
- [ ] Service correctly composes adapters
- [ ] Errors collected, scan continues
- [ ] AC1-AC8 verified in integration tests
- [ ] ConfigurationService registry pattern: All components (FileScanner, ASTParser, GraphStore, ScanService) receive `ConfigurationService` and call `config.require()` internally (no extracted configs in constructors)

---

### Phase 6: CLI Command and Documentation

**Objective**: Expose scanning via CLI and document the feature.

**Deliverables**:
- `fs2 scan` command in `src/fs2/cli/scan.py`
- Progress bar for large scans (>50 files)
- README.md quick-start section
- `docs/how/scanning.md` detailed guide

**Dependencies**: Phase 5 complete

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Rich progress bar issues | Low | Low | Test with various terminal sizes |
| Documentation drift | Medium | Low | Include in acceptance criteria |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 6.1 | [ ] | Write tests for CLI scan command | 2 | Tests cover: AC9 output format, args parsing | - | tests/unit/cli/test_scan_cli.py |
| 6.2 | [ ] | Implement CLI scan command | 2 | All tests from 6.1 pass | - | src/fs2/cli/scan.py |
| 6.3 | [ ] | Write tests for progress bar | 1 | Tests cover: shown for >50 files, hidden for small scans | - | tests/unit/cli/test_scan_cli.py |
| 6.4 | [ ] | Add Rich progress bar | 1 | Progress bar shows for large scans | - | src/fs2/cli/scan.py |
| 6.5 | [ ] | Survey existing docs/how/ structure | 1 | Document existing structure | - | Discovery step |
| 6.6 | [ ] | Update README.md with quick-start | 2 | Config example, basic usage documented | - | /workspaces/flow_squared/README.md |
| 6.7 | [ ] | Create docs/how/scanning.md | 2 | Node types, graph format, troubleshooting | - | /workspaces/flow_squared/docs/how/scanning.md |
| 6.8 | [ ] | Final acceptance criteria verification | 2 | AC1-AC10 all pass | - | Manual verification |

### Test Examples (Write First!)

```python
# tests/unit/cli/test_scan_cli.py
import pytest
from typer.testing import CliRunner
from fs2.cli.main import app

runner = CliRunner()

def test_given_scan_command_when_run_then_outputs_summary(tmp_path, monkeypatch):
    """
    Purpose: Verifies AC9 - CLI output format.
    Quality Contribution: Ensures users see clear scan results.
    Acceptance Criteria: Output includes "Scanned N files, created M nodes".
    """
    # Arrange
    (tmp_path / "test.py").write_text("x = 1")
    monkeypatch.chdir(tmp_path)

    # Act
    result = runner.invoke(app, ["scan"])

    # Assert
    assert result.exit_code == 0
    assert "Scanned" in result.stdout
    assert "files" in result.stdout
    assert "nodes" in result.stdout
```

### Documentation Content Outlines

**README.md section** (quick-start):
```markdown
## Scanning

Configure scan paths in `.fs2/config.yaml`:
```yaml
scan:
  scan_paths:
    - "./src"
    - "./lib"
  max_file_size_kb: 500
```

Run the scanner:
```bash
fs2 scan
```

Output: Graph saved to `.fs2/graph.gpickle`

See [docs/how/scanning.md](docs/how/scanning.md) for details.
```

**docs/how/scanning.md**:
- Introduction and purpose
- Configuration options (all ScanConfig fields)
- Node types and hierarchy
- Graph format and querying
- Troubleshooting common issues

### Non-Happy-Path Coverage
- [ ] Invalid config file
- [ ] No scan_paths configured
- [ ] Terminal without color support

### Acceptance Criteria
- [ ] All tests passing
- [ ] AC9: CLI outputs "Scanned N files, created M nodes"
- [ ] Progress bar shown for >50 files
- [ ] README.md updated
- [ ] docs/how/scanning.md created

---

## Cross-Cutting Concerns

### Security Considerations
- No secrets in scan output (API keys, passwords)
- Path traversal prevention (scan_paths validated)
- Binary file detection prevents code injection via malformed files

### Observability
- Logging at key stages: scan start, file processed, error, completion
- Use existing `LogAdapter` pattern
- Progress bar via Rich for CLI feedback

### Documentation
- **Location**: Hybrid (README.md + docs/how/)
- **README**: Quick-start, config example, basic command
- **docs/how/scanning.md**: Full reference, node types, troubleshooting
- **Target Audience**: Developers indexing their codebases
- **Maintenance**: Update when config options or CLI changes

---

## Complexity Tracking

| Component | CS | Label | Breakdown (S,I,D,N,F,T) | Justification | Mitigation |
|-----------|-----|-------|------------------------|---------------|------------|
| Overall Feature | 3 | Medium | S=2,I=1,D=0,N=1,F=0,T=1 | 9 files, 3 external deps, integration tests | Phased implementation |
| TreeSitterParser | 3 | Medium | S=1,I=1,D=0,N=1,F=0,T=1 | tree-sitter integration, language detection | Extensive tests |
| FileSystemScanner | 3 | Medium | S=1,I=1,D=0,N=1,F=0,T=1 | gitignore edge cases | Use pathspec library |

---

## Progress Tracking

### Phase Completion Checklist
- [x] Phase 1: Core Models and Configuration - COMPLETED (2025-12-15)
- [ ] Phase 2: File Scanner Adapter - NOT STARTED
- [ ] Phase 3: AST Parser Adapter - NOT STARTED
- [ ] Phase 4: Graph Storage Repository - NOT STARTED
- [ ] Phase 5: Scan Service Orchestration - NOT STARTED
- [ ] Phase 6: CLI Command and Documentation - NOT STARTED

### STOP Rule
**IMPORTANT**: This plan must be complete before creating tasks. After writing this plan:
1. Run `/plan-4-complete-the-plan` to validate readiness
2. Only proceed to `/plan-5-phase-tasks-and-brief` after validation passes

---

## Change Footnotes Ledger

[^1]: Task 1.1 - Added dependencies (Phase 1 - 2025-12-15)
  - `file:pyproject.toml` - Added networkx>=3.0, tree-sitter-language-pack>=0.13.0, pathspec>=0.12

[^2]: Tasks 1.2-1.3 - CodeNode implementation (Phase 1 - 2025-12-15)
  - `class:src/fs2/core/models/code_node.py:CodeNode` - Universal frozen dataclass (~17 fields)
  - `function:src/fs2/core/models/code_node.py:classify_node` - Language-agnostic classification
  - `file:tests/unit/models/test_code_node.py` - 25 tests for CodeNode

[^3]: Tasks 1.4-1.5 - ScanConfig implementation (Phase 1 - 2025-12-15)
  - `class:src/fs2/config/objects.py:ScanConfig` - Pydantic model for scan configuration
  - `file:tests/unit/config/test_scan_config.py` - 12 tests for ScanConfig

[^4]: Tasks 1.6-1.7 - Domain exceptions (Phase 1 - 2025-12-15)
  - `class:src/fs2/core/adapters/exceptions.py:FileScannerError` - File scanning errors
  - `class:src/fs2/core/adapters/exceptions.py:ASTParserError` - AST parsing errors
  - `class:src/fs2/core/adapters/exceptions.py:GraphStoreError` - Graph storage errors
  - `file:tests/unit/adapters/test_exceptions.py` - 9 new tests for exceptions

[^5]: Task 1.8 - Model exports (Phase 1 - 2025-12-15)
  - `file:src/fs2/core/models/__init__.py` - Export CodeNode, classify_node
