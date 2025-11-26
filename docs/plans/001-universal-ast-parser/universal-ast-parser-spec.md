# Universal AST Parser with Generic Hierarchy

**Mode**: Simple

📚 This specification incorporates findings from `tree-sitter-research.md`

## Summary

**WHAT**: Build a universal code/document parser using tree-sitter that extracts structural elements from ANY supported file format into a single, generic hierarchical data structure—without requiring per-language special cases or format-specific shims.

**WHY**: Code analysis tools typically require separate parsers or adapters for each language/format (Python classes vs Markdown sections vs Terraform blocks). This creates maintenance burden, inconsistent behavior, and limits extensibility. A truly universal parser enables:

- Single codebase supporting 50+ file formats immediately
- Consistent API for querying structure regardless of source format
- Future language support "for free" via tree-sitter grammars
- Foundation for cross-language code intelligence tools

## Goals

- **G1**: Establish a generic hierarchical structure that naturally represents ANY file format's logical organization (classes/methods in Python, sections/subsections in Markdown, resources/blocks in Terraform, stages/commands in Dockerfile)
- **G2**: Implement a single parser entry point that works identically across all tree-sitter-supported formats—zero conditional logic per language
- **G3**: Preserve semantic meaning: the hierarchy should capture what IS in each format, not force alien concepts (no "classes" in Markdown)
- **G4**: Extract actionable metadata: line ranges, content, signatures/parameters where applicable
- **G5**: Enable experimentation: understand tree-sitter's actual output for diverse formats before committing to final structure
- **G6**: Support nested hierarchies of arbitrary depth (file → module → class → method → nested function)

## Non-Goals

- **NG1**: Building language-specific analyzers or linters (we only extract structure)
- **NG2**: Semantic analysis beyond tree-sitter's parse tree (no type inference, flow analysis)
- **NG3**: Real-time/incremental parsing (batch processing is sufficient for initial exploration)
- **NG4**: IDE integration or LSP implementation (this is the foundation layer)
- **NG5**: Converting between formats or generating code
- **NG6**: Handling syntax errors gracefully (assume valid input for now)

## Complexity

- **Score**: CS-3 (medium)
- **Breakdown**: S=1, I=2, D=1, N=2, F=0, T=1 (Total: 7)
  - **S=1 (Surface Area)**: Multiple files but contained to parser module + sample files
  - **I=2 (Integration)**: Tree-sitter + multiple language grammars (external, potentially unstable APIs across versions)
  - **D=1 (Data/State)**: New data structure design, but no persistence/migration
  - **N=2 (Novelty)**: High discovery component—must experiment to understand tree-sitter output variations
  - **F=0 (Non-Functional)**: Standard requirements, no special perf/security constraints
  - **T=1 (Testing)**: Integration tests across languages needed, but no staged rollout
- **Confidence**: 0.70 (medium-high—tree-sitter behavior across grammars is uncertain)
- **Assumptions**:
  - Tree-sitter Python bindings are mature and stable
  - All target language grammars are available and installable via standard mechanisms
  - Tree-sitter's AST structure follows consistent patterns across grammars (needs validation)
  - uv package manager will handle dependencies smoothly
- **Dependencies**:
  - `tree-sitter==0.25.2` — Core parsing engine (Python bindings)
  - `tree-sitter-language-pack==0.11.0` — Bundled grammars for 50+ languages (eliminates need for individual grammar packages)
  - `uv` for dependency management
- **Risks**:
  - Tree-sitter grammar inconsistencies may require more abstraction than anticipated
  - Some formats (Dockerfile, Terraform) may have unofficial/less-maintained grammars
  - "Truly universal" may prove impossible—fallback strategy needed
- **Phases**:
  1. Environment setup & tree-sitter installation with all grammars
  2. Create diverse sample files for testing
  3. Explore raw tree-sitter output for each format
  4. Design generic hierarchy model based on empirical findings
  5. Implement universal parser prototype
  6. Validate across all sample formats

## Acceptance Criteria

1. **AC1**: Running the parser on a Python file extracts: file path, classes (with line ranges), methods within classes (with signatures including parameter names/types), standalone functions
2. **AC2**: Running the parser on a Markdown file extracts: file path, sections by heading level (h1→h2→h3 hierarchy), content boundaries for each section
3. **AC3**: Running the parser on a Dockerfile extracts: file path, stages (FROM blocks), instruction groups with line ranges
4. **AC4**: Running the parser on Terraform (.tf) extracts: file path, resource blocks, data blocks, variable definitions with their boundaries
5. **AC5**: The SAME code path handles all formats—no `if language == 'python'` branches in the parser core
6. **AC6**: Output format is consistent: every result has `file`, `nodes[]` where each node has at minimum: `type`, `name` (if applicable), `start_line`, `end_line`, `children[]`
7. **AC7**: Hierarchy depth is unbounded—nested structures (class inside class, function inside function) are properly represented
8. **AC8**: Sample repository includes working examples for: Python, JavaScript, TypeScript, Go, Rust, C++, C#, Dart, Markdown, Terraform, Dockerfile, YAML, JSON, TOML, SQL, and shell scripts
9. **AC9**: Documentation exists showing raw tree-sitter output vs unified output for at least 3 diverse formats

## Risks & Assumptions

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Tree-sitter grammars have incompatible node naming conventions | Medium | High | Build node-type mapping layer as last resort |
| Some grammars unavailable or poorly maintained | Medium | Medium | Document supported vs experimental formats |
| Generic model loses important format-specific semantics | Medium | Medium | Allow optional `metadata` field for format-specific data |
| Performance issues with large files | Low | Low | Out of scope for initial exploration |

### Assumptions
- Tree-sitter's Python bindings work on Linux/macOS/Windows
- All grammars can be installed via pip or built from source
- The team is comfortable with Python for prototyping
- "Universal" means 80%+ coverage, not 100% perfect for every format

## Open Questions

### Resolved by Research

1. **~~[Naming]~~** → Use **"nodes"** (tree-sitter native) with `category` field for taxonomy classification. Keep `raw_kind` for debugging.

2. **~~[Hierarchy representation]~~** → **Nested objects** with `children[]` array. This matches tree-sitter's natural structure.

3. **~~[Content inclusion]~~** → **Store byte ranges only**; extract text lazily via `source[start_byte:end_byte]`. Avoids memory bloat.

4. **~~[Signature format]~~** → Use **tree-sitter's field structure** (`name`, `parameters`, `body` fields). Already parsed by grammar.

5. **~~[Unknown node types]~~** → **Include as-is** with `category: "other"` and preserve `raw_kind`. No filtering, no warnings.

### To Validate During Exploration

- Does the proposed taxonomy (`document`, `section`, `container`, `callable`, `declaration`, `block`, `mapping`, `sequence`, `directive`, `other`) cover all formats adequately?
- Do heuristics based on `is_named` + type name patterns work across grammars, or do we need `node-types.json` metadata?
- How do Markdown grammars handle section hierarchy (flat headings vs nested sections)?

## Testing Strategy

- **Approach**: Manual Only
- **Rationale**: Research/exploration phase—not production code. Experiments drive understanding.
- **Focus Areas**: Verify tree-sitter outputs across formats via interactive scripts
- **Excluded**: Automated test suites (deferred to production implementation phase)
- **Verification Method**: Run scripts, inspect output, document findings in READMEs

## Documentation Strategy

- **Location**: `./initial_exploration/` (co-located with code)
- **Rationale**: Self-contained exploration folder with scripts, samples, and documentation together
- **Content**: README.md (setup/usage), findings documentation, output examples
- **Target Audience**: Future implementers building the production parser
- **Maintenance**: Updated as experiments reveal new insights

## ADR Seeds (Optional)

### ADR-001: Generic Node Structure Design
- **Decision Drivers**: Must represent Python classes, Markdown sections, Terraform resources, and Docker stages without special-casing; must be extensible for future formats
- **Candidate Alternatives**:
  - A) Single universal node type with `type` discriminator field
  - B) Base node class with format-family subclasses (OOP, Markup, Config)
  - C) Schema-per-format with common query interface
- **Stakeholders**: Core parser developers, downstream tool builders

### ADR-002: Tree-sitter Grammar Management
- **Decision Drivers**: Need reliable grammar installation; some grammars are official, others community-maintained; version compatibility matters
- **Candidate Alternatives**:
  - A) ~~Install individual grammar packages~~ (obsolete)
  - B) ~~Build grammars from source at runtime~~ (obsolete)
  - C) **Use `tree-sitter-language-pack`** — Bundled grammars for 50+ languages in single package (RECOMMENDED)
- **Decision**: Use `tree-sitter-language-pack==0.11.0` which bundles all major language grammars, eliminating individual package management
- **Stakeholders**: Package maintainers, CI/CD pipeline

---

## Clarifications

### Session 2025-01-26

**Q1: Workflow Mode**
- **Selected**: Simple (A)
- **Rationale**: Greenfield project, exploration-focused, no existing code constraints. Single-phase approach allows faster iteration during discovery.

**Q2: Testing Strategy**
- **Selected**: Manual Only (D)
- **Rationale**: This is a research/exploration phase, not production implementation. We're experimenting with tree-sitter to understand outputs across formats. Deliverables will be exploratory scripts and documentation that inform the actual implementation later.

**Q3: Documentation Location**
- **Selected**: `./initial_exploration/` (co-located with scripts and samples)
- **Rationale**: Keep all exploration artifacts together—scripts, sample files, README, and findings. Self-contained experimentation folder.

---

*Spec Version: 1.2.0*
*Created: Initial exploration phase*
*Status: READY - Clarification complete*
