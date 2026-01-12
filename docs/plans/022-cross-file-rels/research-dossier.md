# Research Dossier: Cross-File Relationships for fs2

**Generated**: 2026-01-12
**Research Query**: Cross-file relationship implementation without SCIP, language-agnostic approach using Python-only dependencies
**Mode**: Plan-Associated
**Plan Folder**: `docs/plans/022-cross-file-rels`
**FlowSpace**: Available
**Findings**: 55+ across 5 research subagents

---

## Executive Summary

### What We're Building

Cross-file relationship edges in the fs2 graph that connect nodes (files, classes, methods) based on imports, calls, references, and documentation links. Edges will have **confidence scores (0.0-1.0)** indicating certainty of the relationship.

### Business Purpose

Enable rapid context discovery: "What references this file?", "What calls this method?", "Where is this documented?". This powers use cases like:
- Finding execution logs that reference specific code
- Discovering test coverage for methods
- Understanding code usage patterns across the codebase
- Linking documentation to implementation

### Key Insights

1. **Infrastructure is 80% ready** - fs2's NetworkX graph already supports multi-typed edges with attributes; just needs extension
2. **Tree-sitter is the right choice** - `tree-sitter-language-pack` provides 165+ languages via pip with zero external dependencies
3. **Original Flowspace used SCIP** - Had 14 relationship types (CALLS, IMPORTS, INHERITS, etc.) but we can achieve similar results with Tree-sitter queries + heuristics
4. **Confidence scoring is established** - fs2's search system already has 0.0-1.0 scoring patterns we can reuse

### Quick Stats

| Metric | Value |
|--------|-------|
| Languages to support | 15+ (Python, TypeScript, Go, Rust, Java, C/C++, Ruby, Markdown, YAML, etc.) |
| Relationship types needed | 6-8 initially (imports, calls, references, contains, inherits, documents) |
| Test fixtures available | 21 files across 15 languages |
| Prior learnings scanned | 48 discovery documents from previous implementations |

---

## The "Vibe" - Why We're Doing This

Cross-file node edges are about **quickly finding context and documentation** for code elements.

### Use Case 1: Reference Discovery
When looking at `home.py`, see that it's referenced from line X of README. This is helpful as when searching you can see references like documentation.

### Use Case 2: Execution Log Linkage
Node IDs will be prevalent in execution logs. Part of this is to ensure we can very quickly find the execution logs incoming to any file, callable, method. This means we can use fs2 to very quickly find a bit of code's history.

### Use Case 3: Transitive Test Coverage (Future)
Cross-file rels for method calls enable "special" searches to find "all tests that transitively call a method" - discovering test coverage without running tests.

### Reference Resolution Examples

| In File | Reference | Resolves To | Confidence |
|---------|-----------|-------------|------------|
| README.md | `./src/cli/home.py` | `file:src/cli/home.py` | 1.0 |
| execution.log | `callable:src/calc.py:Calculator.add` | Direct node link | 1.0 |
| app.py | `from auth_handler import AuthHandler` | `file:src/auth_handler.py` | 0.9 |
| service.py | `handler.validate()` | `callable:...:AuthHandler.validate` | 0.6 |

---

## How Original Flowspace Implemented Cross-File Relationships

### RelationType Enum (from Flowspace)

```python
class RelationType(str, Enum):
    """Graph edge relationship types."""

    DEFINES = "defines"
    CONTAINS = "contains"
    IMPORTS = "imports"
    INHERITS = "inherits"
    CALLS = "calls"
    CALLED_BY = "called_by"
    IMPORTED_BY = "imported_by"
    INHERITED_BY = "inherited_by"
    CONTAINED_BY = "contained_by"
    DEFINED_BY = "defined_by"
    TEST = "test"
    ENTRY_POINT = "entry_point"
    FILE_REFERENCE = "file_reference"
    REFERENCED_BY = "referenced_by"
```

### SCIP Architecture (What We're Replacing)

Flowspace used a three-layer SCIP integration:

1. **SCIP Data Structures**: `SCIPIndex`, `Document`, `Occurrence`, `SymbolInformation`, `Relationship`
2. **Base Enricher**: Abstract `BaseSCIPEnricher` with project-wide indexing via `prepare()` method
3. **Direct Extractors**: `DirectSCIPClassExtractor`, `DirectSCIPMethodCallExtractor`, `DirectSCIPTypeUsageExtractor`

**Why SCIP was problematic:**
- Required external language-specific indexers (`scip-typescript`, `scip-python`, etc.)
- Each language needed separate binary installation
- Limited to languages with SCIP support (~10 languages)
- Maintenance risk: depends on external tooling

### Flowspace Cross-File Resolution Strategy

1. **SCIP Symbol Parsing**: Parse SCIP symbol format containing file paths
2. **Symbol Cache Fallback**: Map qualified names → file locations
3. **Project-wide SCIP Index**: Single index built for entire project
4. **Line-based Context Resolution**: `LineMethodIndex` maps line numbers to containing methods

---

## Recommended Approach: Tree-sitter + Confidence Scoring

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Cross-File Relationship Pipeline             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  Tree-sitter │ -> │  Extractors  │ -> │  Resolver with   │  │
│  │   Parsing    │    │  (per-lang)  │    │  Confidence      │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│         │                   │                      │            │
│         v                   v                      v            │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  AST Trees   │    │   Imports    │    │  Resolved Edges   │  │
│  │  (per file)  │    │  Definitions │    │  with Confidence  │  │
│  │              │    │   Calls      │    │  (0.0 - 1.0)      │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│                                                  │              │
│                                                  v              │
│                              ┌────────────────────────────────┐ │
│                              │       NetworkX Graph           │ │
│                              │   (edges with rel_type,        │ │
│                              │    confidence, source_line)    │ │
│                              └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Confidence Scoring Tiers

| Score | Meaning | Example |
|-------|---------|---------|
| **1.0** | Direct fs2 node_id in file | `callable:src/calc.py:Calculator.add` in execution log |
| **0.9** | Explicit import with resolution | `from auth_handler import AuthHandler` → resolves to file |
| **0.8** | Type-annotated reference | `handler: AuthHandler = AuthHandler()` |
| **0.7** | Constructor pattern | `p = Calculator()` → inferred type |
| **0.6** | Import-bound call | `import calc; calc.add()` |
| **0.5** | Method call with known receiver type | `self.handler.validate()` |
| **0.3** | Name match in same package | `add()` → likely `Calculator.add` in same module |
| **0.2** | Global name match | `add` exists somewhere in codebase |
| **0.1** | Fuzzy match (substring) | "Calc" in comment → might reference Calculator |

---

## Current fs2 Infrastructure Status

### What Already Exists

| Component | Status | Location |
|-----------|--------|----------|
| Graph edge storage | Ready | `GraphStore.add_edge()` |
| NetworkX DiGraph | Supports edge attributes | `NetworkXGraphStore._graph` |
| Confidence scoring pattern | Established | `ChunkMatch.score`, `SearchResult.score` |
| Test infrastructure | Complete | `FakeGraphStore`, fixtures |
| Pickle persistence | Preserves edge data | `NetworkXGraphStore.save()` |
| 15+ language samples | Available | `tests/fixtures/samples/` |

### Current Edge Infrastructure

**GraphStore ABC** (`src/fs2/core/repos/graph_store.py`):
- `add_edge(parent_id: str, child_id: str) -> None`
- Graph direction: parent → child (successors/predecessors pattern)
- Already handles edge validation and GraphStoreError exceptions

**NetworkXGraphStore Implementation** (`src/fs2/core/repos/graph_store_impl.py`):
- Uses `networkx.DiGraph` internally
- NetworkX natively supports edge attributes: `graph.add_edge(u, v, rel_type="calls", confidence=0.85)`
- Pickle serialization automatically preserves edge attributes

**Confidence Scoring Pattern** (from `ChunkMatch`):
```python
@dataclass(frozen=True)
class ChunkMatch:
    score: float  # 0.0 - 1.0 range

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be between 0.0 and 1.0")
```

### What Needs to Be Added

| Component | Description |
|-----------|-------------|
| **EdgeType enum** | `IMPORTS`, `CALLS`, `INHERITS`, `REFERENCES`, `DOCUMENTS` |
| **Edge metadata fields** | `rel_type`, `confidence`, `source_line`, `target_line` |
| **Relationship extractors** | Tree-sitter queries per language for imports/calls/refs |
| **Resolver service** | Confidence-based resolution with heuristics |
| **Extended query methods** | `get_edges(node_id, type)`, `get_incoming(node_id)` |

---

## Implementation Strategy

### Phase 1: File-to-File Dependencies (Imports/Includes)

**Goal**: Extract import statements and resolve to target files with high confidence.

**Proposed Edge Model:**
```python
@dataclass(frozen=True)
class CodeEdge:
    """Cross-file relationship edge."""
    source_node_id: str  # e.g., "file:src/app.py"
    target_node_id: str  # e.g., "file:src/auth_handler.py"
    edge_type: EdgeType  # e.g., EdgeType.IMPORTS
    confidence: float    # 0.0 - 1.0
    source_line: int     # Line in source where relationship occurs
    resolution_rule: str # "explicit_import", "constructor_pattern", "heuristic"

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
```

**Languages to cover (with Tree-sitter queries):**

| Language | Grammar Nodes |
|----------|---------------|
| Python | `import_statement`, `import_from_statement` |
| TypeScript/JS | `import_statement`, `import_clause` |
| Go | `import_declaration`, `import_spec` |
| Rust | `use_declaration`, `scoped_identifier` |
| Java | `import_declaration` |
| C/C++ | `preproc_include` |

### Phase 2: Symbol-to-Symbol (Definitions & References)

**Goal**: Extract class/function definitions and link call sites to definitions.

**Python Definition Query:**
```scheme
(class_definition
  name: (identifier) @class.name) @class

(function_definition
  name: (identifier) @function.name) @function
```

**Python Call Query:**
```scheme
(call
  function: (identifier) @call.name)

(call
  function: (attribute
    object: (identifier) @call.receiver
    attribute: (identifier) @call.method))
```

### Phase 3: Documentation & Non-Code References

**Goal**: Link markdown files, execution logs, and config files to code nodes.

**Patterns to detect:**
- fs2 node_id strings: `callable:src/calc.py:Calculator.add`
- File paths: `./src/cli/home.py`, `src/services/auth.py`
- Class/method names: "Calculator", "AuthHandler.validate"
- Module references in YAML/JSON config files

---

## Test Fixture Analysis

### Current Fixtures (21 files)

```
tests/fixtures/samples/
├── python/           # auth_handler.py, data_parser.py
├── javascript/       # app.ts, component.tsx, utils.js
├── go/              # server.go
├── rust/            # lib.rs
├── java/            # UserService.java
├── c/               # algorithm.c, main.cpp
├── ruby/            # tasks.rb
├── bash/            # deploy.sh
├── sql/             # schema.sql
├── terraform/       # main.tf
├── docker/          # Dockerfile
├── yaml/            # deployment.yaml
├── toml/            # config.toml
├── json/            # package.json
├── markdown/        # README.md
├── gdscript/        # player.gd
└── cuda/            # vector_add.cu
```

### Current State: No Cross-File Imports

All fixture files currently import **only standard library** modules. This is actually good - it provides a clean slate for adding deliberate cross-file relationships.

### Recommended Fixture Additions

**1. Python cross-file import** (`tests/fixtures/samples/python/app_service.py`):
```python
from auth_handler import AuthHandler, AuthToken, AuthRole
from data_parser import JSONParser, ParseResult

class AppService:
    def __init__(self):
        self.auth = AuthHandler()
        self.parser = JSONParser()

    async def process_request(self, token_id: str, data: str):
        token = await self.auth.validate_token(token_id)
        result = self.parser.parse(data)
        return result
```

**Expected Relationships:**
- File `app_service.py` imports from `auth_handler.py` (confidence: 0.9)
- File `app_service.py` imports from `data_parser.py` (confidence: 0.9)
- `AppService.__init__` calls `AuthHandler.__init__` (confidence: 0.8)
- `AppService.process_request` calls `AuthHandler.validate_token` (confidence: 0.7)

**2. TypeScript module chain** (`tests/fixtures/samples/javascript/index.ts`):
```typescript
import { Application, AppConfig } from "./app";
import { debounce, throttle } from "./utils";
import { Button, ThemeProvider } from "./component";

const config: AppConfig = { /* ... */ };
const app = new Application(config);
```

**3. Markdown with node_ids** (`tests/fixtures/samples/markdown/execution-log.md`):
```markdown
## Execution Log - 2026-01-12

### Called Nodes
- `callable:tests/fixtures/samples/python/auth_handler.py:AuthHandler.authenticate`
- `callable:tests/fixtures/samples/python/data_parser.py:JSONParser.parse`

### Files Modified
- `file:tests/fixtures/samples/python/auth_handler.py`
```

---

## Dependencies Required

```toml
# pyproject.toml additions
[project.dependencies]
tree-sitter = ">=0.23.0"
tree-sitter-language-pack = ">=0.2.0"
```

**Why these packages:**

| Package | Purpose | Size |
|---------|---------|------|
| `tree-sitter` | Core parsing library with Python bindings | ~2MB wheel |
| `tree-sitter-language-pack` | 165+ pre-compiled language grammars | ~50MB wheel |

**No external binaries required.** Everything is pip-installable with pre-compiled wheels.

---

## Integration with Existing fs2 Architecture

### GraphStore Extension

```python
# src/fs2/core/repos/graph_store.py (extend ABC)
class GraphStore(ABC):
    # Existing methods...

    @abstractmethod
    def add_relationship_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        confidence: float,
        source_line: int | None = None,
        **metadata: Any,
    ) -> None:
        """Add a cross-file relationship edge with confidence score."""

    @abstractmethod
    def get_relationships(
        self,
        node_id: str,
        edge_types: list[EdgeType] | None = None,
        direction: Literal["outgoing", "incoming", "both"] = "both",
        min_confidence: float = 0.0,
    ) -> list[tuple[str, EdgeType, float]]:
        """Get relationships for a node, optionally filtered by type/confidence."""
```

### NetworkXGraphStore Implementation

```python
# src/fs2/core/repos/graph_store_impl.py
def add_relationship_edge(
    self,
    source_id: str,
    target_id: str,
    edge_type: EdgeType,
    confidence: float,
    source_line: int | None = None,
    **metadata: Any,
) -> None:
    """Store relationship edge with attributes in NetworkX graph."""
    self._graph.add_edge(
        source_id,
        target_id,
        edge_type=edge_type.value,
        confidence=confidence,
        source_line=source_line,
        is_relationship=True,  # Distinguish from parent-child edges
        **metadata,
    )
```

---

## Key Design Decisions

### 1. Confidence-First Approach

Instead of binary "exists/doesn't exist" relationships, every edge has a confidence score. This allows:
- Showing "certain" relationships (confidence >= 0.8) in default views
- Allowing discovery of "possible" relationships (confidence >= 0.3) when searching
- Filtering out noise (confidence < 0.2) unless explicitly requested

### 2. Bidirectional Edges via Query (Not Storage)

Store edges in one direction (source → target), compute reverse via graph queries:
```python
# Forward: "what does this file import?"
graph.successors(node_id)

# Reverse: "what imports this file?"
graph.predecessors(node_id)
```

### 3. fs2 Node ID as First-Class Reference

When a file contains an fs2 node_id string (e.g., in execution logs), create a **confidence 1.0** edge directly to that node. This is the "gold standard" for cross-file relationships.

### 4. Language-Specific Extractors, Generic Resolver

Each language has its own Tree-sitter query for imports/calls, but the resolver applies language-agnostic heuristics:
- Same directory = higher confidence
- Matching filename = higher confidence
- Already imported = higher confidence

### 5. Perfect is the Enemy of Good

From the user's requirements:
> "Calc" in a file might get a 0.1 linkage to a calc class, as it's just a ref... we could choose to ignore it later - this way we do get all rels, just some might be wrong.

**Implication**: Capture relationships even with low confidence. Let filtering happen at query time.

---

## External Research Opportunities

### Research Opportunity 1: Stack Graphs for Enhanced Resolution

**Why Needed**: The external research document mentions `stack-graphs-python-bindings` as an optional enhancement for better "go to definition" in supported languages (JS/TS/Python/Java).

**Ready-to-use prompt:**
```
/deepresearch "Evaluate stack-graphs-python-bindings for cross-file name resolution.
Context: Building code relationship graph using Tree-sitter as base.
Questions:
1. What languages does stack-graphs support in 2026?
2. Was the github/stack-graphs repository archived and is there an active fork?
3. How does stack graphs compare to pure Tree-sitter heuristics for Python/TypeScript?
4. What's the performance overhead for indexing a 100k LOC project?"
```

**Results location**: `docs/plans/022-cross-file-rels/external-research/stack-graphs.md`

### Research Opportunity 2: graph-sitter Package Evaluation

**Why Needed**: The `graph-sitter` PyPI package claims to build function/class/import graphs for Python/TypeScript/JavaScript. Could potentially accelerate implementation.

**Ready-to-use prompt:**
```
/deepresearch "Evaluate graph-sitter Python package for code relationship extraction.
Context: Need cross-file relationship graph for 15+ languages.
Questions:
1. What languages does graph-sitter actually support (beyond marketing claims)?
2. Does it extract method-level call graphs or just file-level imports?
3. What's the API for extracting relationships?
4. Can it be used selectively (just for TS/JS) while using custom Tree-sitter for others?"
```

**Results location**: `docs/plans/022-cross-file-rels/external-research/graph-sitter.md`

---

## Experimental Scripts Needed

Based on the research, here are the experimental scripts to write in `scratch/`:

### 1. `scratch/cross-file-rels/test_treesitter_imports.py`
Test import extraction with Tree-sitter queries on fixture files.

### 2. `scratch/cross-file-rels/test_call_extraction.py`
Test function/method call site extraction and resolution.

### 3. `scratch/cross-file-rels/test_nodeid_detection.py`
Test detection of fs2 node_id patterns in markdown/text files.

### 4. `scratch/cross-file-rels/test_confidence_resolver.py`
Test the confidence scoring heuristics with known cross-file relationships.

---

## Tree-sitter Query Reference

### Python Import Extraction

```scheme
; Simple import: import os
(import_statement
  name: (dotted_name) @import.module) @import

; From import: from pathlib import Path
(import_from_statement
  module_name: (dotted_name) @import.from_module
  name: (dotted_name) @import.name) @import.from

; Aliased import: import numpy as np
(import_statement
  name: (aliased_import
    name: (dotted_name) @import.module
    alias: (identifier) @import.alias))
```

### TypeScript/JavaScript Import Extraction

```scheme
; Default import: import fs from 'fs'
(import_statement
  (import_clause
    (identifier) @import.default)
  source: (string) @import.source)

; Named imports: import { readFile } from 'fs/promises'
(import_statement
  (import_clause
    (named_imports
      (import_specifier
        name: (identifier) @import.named)))
  source: (string) @import.source)

; Namespace import: import * as path from 'path'
(import_statement
  (import_clause
    (namespace_import
      (identifier) @import.namespace))
  source: (string) @import.source)
```

### Go Import Extraction

```scheme
; Single import: import "fmt"
(import_declaration
  (import_spec
    path: (interpreted_string_literal) @import.path))

; Grouped imports with optional alias
(import_declaration
  (import_spec_list
    (import_spec
      name: (package_identifier)? @import.alias
      path: (interpreted_string_literal) @import.path)))
```

### Rust Import Extraction

```scheme
; Simple use: use std::fs
(use_declaration
  argument: (scoped_identifier) @import.path)

; Use with alias: use HashMap as Map
(use_declaration
  argument: (use_as_clause
    path: (scoped_identifier) @import.path
    alias: (identifier) @import.alias))

; Use list: use std::io::{Read, Write}
(use_declaration
  argument: (scoped_use_list
    path: (scoped_identifier)? @import.base
    list: (use_list
      (identifier) @import.item)))
```

---

## Recommendations

### If Implementing This Feature

1. **Start with imports** - File-to-file import relationships give 80% of the value with 20% of the complexity
2. **Use tree-sitter-language-pack** - One pip install, 165 languages, no external binaries
3. **Leverage existing GraphStore** - NetworkX already supports edge attributes
4. **Reuse scoring patterns** - Copy `ChunkMatch` validation approach for confidence scores
5. **Add fixtures incrementally** - Create cross-file relationships in `tests/fixtures/samples/` as you build extractors

### Testing Strategy

1. **Unit tests per extractor** - Test each language's import/call extraction in isolation
2. **Integration tests** - Full pipeline from file → edge creation → graph query
3. **Fixture-based validation** - Known relationships in fixtures validate resolver accuracy

### Priority Order

1. **fs2 node_id detection** (confidence 1.0) - Immediate value for execution logs
2. **Python imports** - Most common language in codebase
3. **TypeScript/JS imports** - Second most common
4. **Markdown file references** - Documentation links
5. **Method calls** - More complex, lower priority

---

## Next Steps

1. **Write experimental scripts** in `scratch/cross-file-rels/` to validate Tree-sitter approach
2. **Add cross-file fixtures** - Create files that import each other in `tests/fixtures/samples/`
3. **Run `/plan-1b-specify`** to create formal specification based on this research
4. **Prototype EdgeType enum** and `add_relationship_edge()` extension

---

**Research Complete**: 2026-01-12
**Report Location**: `docs/plans/022-cross-file-rels/research-dossier.md`
