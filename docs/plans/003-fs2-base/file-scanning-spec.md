# File Scanning for Flowspace v2

**Mode**: Full

📚 This specification incorporates findings from prior research on Serena (original Flowspace) codebase and fs2 initial_exploration work.

## Research Context

**Components affected**:
- `fs2/config/objects.py` - ScanConfig addition
- `fs2/core/models/` - New CodeNode model
- `fs2/core/adapters/` - FileScanner, ASTParser adapters
- `fs2/core/repos/` - GraphStore repository
- `fs2/core/services/` - ScanService
- `fs2/cli/` - scan command

**Critical dependencies**:
- `tree-sitter-language-pack` - Multi-language AST parsing
- `networkx` - Graph storage
- `pathspec` - Gitignore pattern matching

**Modification risks**:
- Low: fs2 architecture already supports this pattern (config system, adapter pattern ready)
- Medium: Tree-sitter language detection edge cases (ambiguous extensions like `.h`)

**Reference**: See initial_exploration/scripts/parse_to_json.py for prototyped parsing logic; Serena's util/file_system.py for battle-tested directory scanning patterns.

## Summary

**WHAT**: File scanning is the foundational capability that walks configured directories, respects `.gitignore` patterns, parses source files with tree-sitter, and stores the resulting code structure (files, classes, methods, functions) as nodes in a graph hierarchy.

**WHY**: Without file scanning, Flowspace has no data. This capability enables all downstream features: semantic code search, relationship mapping, documentation generation, and LLM-powered summaries. It transforms a codebase into a queryable knowledge graph.

## Goals

1. **Configurable scan paths**: Users specify which directories to scan via YAML config (`scan_paths: ["./src", "./lib"]`)
2. **Gitignore compliance**: Automatically respect `.gitignore` files at all directory levels (root and nested)
3. **Universal language support**: Parse any file type tree-sitter supports (Python, TypeScript, Rust, Markdown, YAML, Terraform, etc.)
4. **Size-aware processing**: Large files are sampled (top N lines) rather than skipped entirely
5. **Hierarchical storage**: Store nodes in a graph where file nodes contain class/function children via edges
6. **Extensibility-ready**: Node model includes placeholder fields for future smart_content and embeddings
7. **CLI accessibility**: Users can trigger scanning via `fs2 scan` command

## Non-Goals

- **Smart content generation**: LLM-generated summaries are out of scope (placeholder fields only)
- **Embedding generation**: Vector embeddings are out of scope (placeholder fields only)
- **Cross-file relationships**: Method-to-method call graphs across files are out of scope
- **Incremental scanning**: Full re-scan only; delta detection is future work
- **Remote repository scanning**: Local filesystem only; no git clone functionality
- **Language server integration**: No LSP communication; tree-sitter only

## Complexity

**Score**: CS-3 (medium)

**Breakdown**: S=2, I=1, D=0, N=1, F=0, T=1 → Total P=5

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 2 | ~9 new files across config, models, adapters, repos, services, CLI |
| Integration (I) | 1 | External deps (tree-sitter-language-pack, networkx, pathspec) but stable |
| Data/State (D) | 0 | No database; networkx graph is runtime-only, saved as file |
| Novelty (N) | 1 | Some ambiguity in node hierarchy rules and edge cases |
| Non-Functional (F) | 0 | Standard performance; no strict requirements |
| Testing/Rollout (T) | 1 | Integration tests needed for file traversal + parsing |

**Confidence**: 0.85

**Assumptions**:
- tree-sitter-language-pack works with Python 3.12
- pathspec library handles all gitignore edge cases
- networkx graph serialization is sufficient (no need for database)

**Dependencies**:
- fs2 config system (exists, ready)
- fs2 adapter pattern (exists, ready)

**Risks**:
- Tree-sitter grammar availability for niche languages
- Large monorepo performance (many files)
- Gitignore edge cases (negation patterns, nested .gitignore)

**Phases**:
1. Core models and config
2. File scanning adapter
3. AST parsing adapter
4. Graph storage
5. Service orchestration
6. CLI command

## Acceptance Criteria

### AC1: Configuration Loading
**Given** a `.fs2/config.yaml` file containing:
```yaml
scan:
  scan_paths:
    - "./src"
    - "./docs"
  max_file_size_kb: 500
  respect_gitignore: true
```
**When** the scan service initializes
**Then** it loads these settings and uses them for scanning

### AC2: Gitignore Compliance
**Given** a project with a root `.gitignore` containing `*.log` and `node_modules/`
**When** the scanner walks the directory tree
**Then** it excludes all `.log` files and the `node_modules/` directory from results

### AC3: Nested Gitignore Support
**Given** a subdirectory `src/vendor/` with its own `.gitignore` containing `*.generated.py`
**When** the scanner processes `src/vendor/`
**Then** it excludes `*.generated.py` files within that subtree only

### AC4: Language Detection
**Given** files with various extensions (`.py`, `.ts`, `.md`, `.tf`, `Dockerfile`)
**When** the parser processes each file
**Then** it correctly identifies the language and applies the appropriate tree-sitter grammar

### AC5: AST Hierarchy Extraction
**Given** a Python file containing a class `Calculator` with methods `add()` and `subtract()`
**When** the parser processes this file
**Then** the graph contains:
- A file node for the Python file
- A class node for `Calculator` (child of file)
- Method nodes for `add()` and `subtract()` (children of class)

### AC6: Large File Handling
**Given** a file larger than `max_file_size_kb`
**When** the parser processes this file
**Then** it samples the first N lines (configurable) and creates a partial node with a `truncated: true` flag

### AC7: Node ID Format
**Given** a method `add` in class `Calculator` in file `src/calc.py`
**When** the node is created
**Then** its `node_id` follows the format: `method:src/calc.py:Calculator.add`

### AC8: Graph Persistence
**Given** a completed scan with 100 nodes
**When** the graph is saved
**Then** it can be loaded from disk and all 100 nodes are recoverable with their relationships

### AC9: CLI Scan Command
**Given** a user runs `fs2 scan`
**When** scanning completes
**Then** it outputs a summary: "Scanned N files, created M nodes" and saves the graph

### AC10: Graceful Error Handling
**Given** a file that cannot be parsed (binary, corrupt, or unsupported language)
**When** the scanner encounters this file
**Then** it logs a warning and continues scanning other files (no crash)

## Risks & Assumptions

### Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| Tree-sitter grammar missing for a language | Medium | Fall back to "file-only" node (no children) |
| Performance with 10k+ files | Medium | Profile and add progress reporting |
| Gitignore pattern edge cases | Low | Use pathspec library (battle-tested) |
| Memory usage with large graphs | Low | networkx is efficient; monitor in testing |

### Assumptions
- Users have Python 3.12+ installed
- Projects have reasonable size (< 50k files)
- `.gitignore` files are valid (malformed files logged, not fatal)
- Graph file format (pickle/JSON) is acceptable for MVP

## Testing Strategy

- **Approach**: Full TDD
- **Rationale**: Foundational feature with file I/O, external library integration, and data integrity concerns
- **Focus Areas**: Gitignore edge cases, tree-sitter parsing, graph persistence, error handling
- **Excluded**: N/A - comprehensive coverage required
- **Mock Usage**: Avoid mocks entirely; use real fixtures and fake adapter implementations per fs2 pattern

## Documentation Strategy

- **Location**: Hybrid (README.md + docs/how/)
- **Content Split**:
  - README: Quick-start (config example, `fs2 scan` command, basic output)
  - docs/how/scanning.md: Node types, graph format, troubleshooting, advanced config
- **Target Audience**: Developers using fs2 to index their codebases
- **Maintenance**: Update when config options or CLI changes

## Open Questions

~~All resolved in clarification session 2025-12-12~~

| Question | Resolution |
|----------|------------|
| Graph persistence format | gpickle (NetworkX native) |
| Node content storage | Full source code |
| CLI output location | `.fs2/graph.gpickle` |
| Progress reporting | Rich progress bar for >50 files |

## ADR Seeds (Optional)

### Decision: Graph Storage Format
**Decision Drivers**:
- Portability (can other tools read it?)
- Performance (load/save speed for large graphs)
- Human readability (debugging)

**Candidate Alternatives**:
- A: Pickle (fast, Python-native, not portable)
- B: JSON Lines (portable, human-readable, larger files)
- C: NetworkX native formats (GML, GraphML)

**Stakeholders**: Developer users, future tooling integrations

### Decision: Node ID Scheme
**Decision Drivers**:
- Uniqueness across codebase
- Human readability
- Stability across renames

**Candidate Alternatives**:
- A: `{type}:{path}:{symbol}` (e.g., `method:src/calc.py:Calculator.add`)
- B: Content hash-based IDs
- C: Sequential integer IDs

**Stakeholders**: Search features, relationship mapping

---

**Spec Location**: `docs/plans/003-fs2-base/file-scanning-spec.md`
**Next Step**: Run `/plan-2-clarify` for high-impact questions

## Clarifications

### Session 2025-12-12

**Q1: Workflow Mode**
- **Selected**: Full (B)
- **Rationale**: CS-3 feature with foundational importance; multi-phase plan with all gates appropriate for this complexity level

**Q2: Testing Strategy**
- **Selected**: Full TDD (A)
- **Rationale**: Foundational feature with file I/O, external library integration, and data integrity concerns warrants comprehensive testing

**Q3: Mock Usage**
- **Selected**: Avoid mocks entirely (A)
- **Rationale**: Use real fixtures and fake implementations per fs2 "fakes over mocks" pattern; test against actual file system and tree-sitter

**Q4: Documentation Strategy**
- **Selected**: Hybrid (C)
- **Content Split**: README gets quick-start (config example, `fs2 scan` command); docs/how/ gets detailed guide (node types, graph format, troubleshooting)

**Q5: Graph Persistence Format**
- **Selected**: gpickle (NetworkX native pickle format)
- **Rationale**: Fast, simple, Python-native; portability not needed for MVP

**Q6: Node Content Storage**
- **Selected**: Full source code (A)
- **Rationale**: Enables full-text search without re-reading files

**Q7: CLI Output Location**
- **Selected**: `.fs2/graph.gpickle` (convention over configuration)

**Q8: Progress Reporting**
- **Selected**: Yes, use Rich progress bar for scans >50 files
