# Universal AST Parser - Tree-sitter Exploration (Phase 0: Research)

**Mode**: Simple

📚 This specification incorporates findings from `tree-sitter-research.md`

**IMPORTANT**: This is a **research and experimentation phase**, NOT a production implementation. The goal is to understand tree-sitter behavior across diverse file formats by generating sample files and analyzing their JSON AST outputs.

## Summary

**WHAT**: Conduct systematic exploration of tree-sitter's parsing capabilities across diverse file formats by creating representative sample files, generating raw JSON AST outputs, and analyzing structural patterns. This research phase will inform the design of a future universal parser, but does NOT include building production-ready parsing infrastructure.

**WHY**: Before committing to a specific data model or parser architecture, we need empirical evidence about:

- How tree-sitter actually parses different file formats (Python classes vs Markdown sections vs Terraform blocks vs Dockerfile stages)
- What node types, field names, and structural patterns exist across 50+ language grammars
- Which structural elements are consistent vs format-specific
- What edge cases and inconsistencies exist in different grammars
- Whether a truly "universal" abstraction is feasible or if format families require different approaches

**DELIVERABLE**: A collection of sample files (16+ formats) paired with their raw tree-sitter JSON AST outputs, exploration scripts for generating outputs, and documented findings that will guide production implementation decisions.

## Goals

- **G1**: Understand how tree-sitter parses diverse file formats by examining raw AST outputs for representative samples
- **G2**: Generate JSON AST dumps for 16+ formats (Python, JavaScript, TypeScript, Go, Rust, C++, C#, Dart, Markdown, Terraform, Dockerfile, YAML, JSON, TOML, SQL, shell scripts)
- **G3**: Document tree-sitter node types, field names, and structural patterns across different language grammars
- **G4**: Identify what's consistent vs inconsistent across grammars (node naming conventions, hierarchy depth, field availability)
- **G5**: Build a knowledge base of findings that will inform future production parser design decisions
- **G6**: Create reusable exploration scripts that can parse any tree-sitter-supported file and output its AST as JSON
- **G7**: Discover edge cases, grammar quirks, and potential obstacles to building a truly "universal" abstraction

## Non-Goals

- **NG1**: Building a production-ready parser with polished APIs or error handling
- **NG2**: Designing or implementing final data models for the universal parser
- **NG3**: Writing comprehensive test suites or CI/CD pipelines
- **NG4**: Optimizing performance or handling large-scale parsing workloads
- **NG5**: Creating user-facing documentation or API references
- **NG6**: Integrating with downstream tools or building a complete analysis pipeline
- **NG7**: Making design decisions before gathering empirical data from tree-sitter outputs
- **NG8**: Achieving "production quality" code—scripts should be functional but don't need to be polished

## Complexity

- **Score**: CS-2 (simple-medium)
- **Breakdown**: S=1, I=1, D=0, N=2, F=0, T=0 (Total: 4)
  - **S=1 (Surface Area)**: Contained to exploration scripts + sample files in single directory
  - **I=1 (Integration)**: Tree-sitter Python bindings (stable, well-documented API)
  - **D=0 (Data/State)**: No data models or persistence—just generating JSON files
  - **N=2 (Novelty)**: High discovery component—this IS the exploration phase
  - **F=0 (Non-Functional)**: No performance, security, or reliability requirements
  - **T=0 (Testing)**: No automated tests—manual script execution only
- **Confidence**: 0.85 (high—research phase with flexible outcomes)
- **Assumptions**:
  - Tree-sitter Python bindings work reliably for basic parsing
  - `tree-sitter-language-pack` provides stable grammar access
  - Sample files can be created manually without automation
  - JSON serialization of ASTs is straightforward
  - Findings will inform future design but don't need to be "correct"—exploration is the goal
- **Dependencies**:
  - `tree-sitter==0.25.2` — Core parsing engine (Python bindings)
  - `tree-sitter-language-pack==0.11.0` — Bundled grammars for 50+ languages
  - Python 3.12+ (already in devcontainer)
- **Risks**:
  - Some grammars may have installation issues (document and skip if necessary)
  - Raw AST outputs may be too verbose to analyze easily (focus on key patterns)
  - Findings may reveal universal parser is infeasible (that's a valid research outcome)
- **Phases**:
  1. Environment setup (install tree-sitter + language pack)
  2. Create representative sample files for 16+ formats
  3. Write exploration script to parse files and dump JSON ASTs
  4. Generate outputs for all samples
  5. Analyze outputs and document patterns, inconsistencies, and findings
  6. Write summary report proposing design directions for production implementation

## Acceptance Criteria

1. **AC1**: Sample files exist for at least 16 formats: Python, JavaScript, TypeScript, Go, Rust, C++, C#, Dart, Markdown, Terraform, Dockerfile, YAML, JSON, TOML, SQL, shell scripts
2. **AC2**: Each sample file is representative of typical real-world code (includes nested structures, multiple element types, realistic complexity)
3. **AC3**: JSON AST output files exist for each sample, showing the complete raw tree-sitter parse tree
4. **AC4**: Exploration script can parse any tree-sitter-supported file and output its AST as formatted JSON
5. **AC5**: JSON outputs include node types, field names, byte ranges, line numbers, and parent-child relationships
6. **AC6**: Documentation compares raw tree-sitter outputs across at least 5 diverse formats (e.g., Python, Markdown, Terraform, Dockerfile, YAML)
7. **AC7**: Findings document identifies patterns (what's consistent across grammars), inconsistencies (grammar-specific quirks), and edge cases
8. **AC8**: Findings document proposes at least one potential design approach for a future universal parser based on observed patterns
9. **AC9**: README.md exists with setup instructions, usage examples, and explanation of deliverables
10. **AC10**: All artifacts are organized in `initial_exploration/` directory with clear structure

## Deliverables

This research phase will produce the following artifacts in the `initial_exploration/` directory:

### 1. Sample Repository (`initial_exploration/sample_repo/`)
Representative code files demonstrating typical structures for each format:
- `python/` — Classes, methods, functions, decorators, async/await
- `javascript/` — Functions, classes, modules, arrow functions
- `typescript/` — Interfaces, types, generics, decorators
- `go/` — Packages, structs, methods, interfaces
- `rust/` — Structs, traits, impl blocks, enums
- `cpp/` — Classes, namespaces, templates, headers
- `csharp/` — Classes, namespaces, properties, LINQ
- `dart/` — Classes, mixins, extensions, async
- `markdown/` — Nested headings, code blocks, lists
- `terraform/` — Resources, data blocks, variables, modules
- `dockerfile/` — Multi-stage builds, ARG/ENV, RUN commands
- `yaml/` — Nested mappings, sequences, anchors
- `json/` — Objects, arrays, nested structures
- `toml/` — Tables, arrays, nested tables
- `sql/` — CREATE, SELECT, JOINs, CTEs
- `shell/` — Functions, conditionals, loops, pipes

### 2. JSON AST Outputs (`initial_exploration/outputs/`)
Raw tree-sitter parse tree dumps for each sample file:
- `python_sample.json` — Full AST with node types, fields, ranges
- `markdown_sample.json` — Document structure as parsed by tree-sitter
- `terraform_sample.json` — Block hierarchy and attributes
- *(etc., one JSON file per sample)*

### 3. Exploration Scripts (`initial_exploration/scripts/`)
Python utilities for generating and analyzing outputs:
- `parse_to_json.py` — Main script: parses any file, outputs JSON AST
- `compare_grammars.py` — (Optional) Side-by-side comparison tool
- `node_type_catalog.py` — (Optional) Extract all unique node types across formats

### 4. Documentation (`initial_exploration/`)
- `README.md` — Setup instructions, how to run scripts, what each deliverable contains
- `FINDINGS.md` — Core research output: patterns discovered, grammar inconsistencies, design implications, recommendations for production implementation

### 5. Cross-Format Analysis (`initial_exploration/FINDINGS.md`)
The findings document will address:
- **Consistency patterns**: What node structures appear across all/most grammars?
- **Inconsistencies**: Grammar-specific quirks, naming variations, missing fields
- **Hierarchical patterns**: How do different formats represent nesting (children arrays, field references, flat with parent pointers)?
- **Metadata availability**: Which grammars provide rich field names vs generic nodes?
- **Edge cases**: Unusual constructs that challenge universal abstraction
- **Design recommendations**: Proposed approaches for production parser based on empirical findings

## Risks & Assumptions

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Some grammars fail to install or load | Medium | Low | Document failures; research phase can proceed with subset of formats |
| Raw AST outputs are too complex to analyze manually | Medium | Medium | Focus on high-level patterns; use scripts to extract summaries |
| Findings may show universal parser is infeasible | Low | Medium | That's a valid research outcome—document why and propose alternatives |
| Time spent on samples doesn't yield actionable insights | Low | Medium | Keep sample creation lightweight; prioritize diverse formats over exhaustive coverage |

### Assumptions
- Tree-sitter Python bindings work reliably in devcontainer
- `tree-sitter-language-pack` provides most needed grammars without manual builds
- Manually creating 16 sample files is feasible within timeframe
- JSON outputs will be human-readable enough to identify patterns
- Research findings don't need to be "correct"—exploration is inherently uncertain

## Open Questions

### To Explore Through This Research

These questions will be answered by analyzing the generated JSON outputs:

1. **Node naming consistency**: Do tree-sitter grammars use consistent naming conventions for similar concepts across languages (e.g., `class_definition` vs `class_declaration` vs `class_specifier`)?

2. **Field availability**: Which grammars provide rich named fields (e.g., `name`, `parameters`, `body`) vs flat children arrays?

3. **Hierarchy representation**: How do different grammars represent nesting—through `children[]`, named fields, or other mechanisms?

4. **Taxonomy feasibility**: Can we define meaningful categories (`document`, `section`, `container`, `callable`, `declaration`, etc.) that apply across all formats, or are grammars too diverse?

5. **Markdown structure**: Do Markdown grammars create nested section nodes, or do they output flat heading nodes requiring post-processing?

6. **Configuration formats**: How do YAML, JSON, TOML, and Terraform represent key-value mappings—are patterns consistent or format-specific?

7. **Metadata richness**: Which grammars include useful metadata (types, modifiers, visibility) vs minimal structural info?

8. **Edge cases**: What unusual constructs exist (nested functions, multi-stage Dockerfiles, Terraform modules) that challenge simple abstractions?

9. **Byte vs line ranges**: Do all grammars reliably provide both byte offsets and line/column positions?

10. **Universal abstraction viability**: After examining outputs, is a single universal data model feasible, or should we consider format families (code vs markup vs config)?

## Testing Strategy

- **Approach**: Manual Exploration Only
- **Rationale**: This is a research phase, not production implementation. The goal is to generate outputs and analyze them, not to build reliable software.
- **Verification Method**:
  - Manually run `parse_to_json.py` on each sample file
  - Visually inspect JSON outputs to verify tree-sitter parsed successfully
  - Document any parsing failures or unexpected structures in FINDINGS.md
  - No automated tests, no CI/CD, no coverage requirements
- **Success Criteria**: Outputs exist and are analyzable, not that they're "correct" (there is no ground truth yet)

## Documentation Strategy

- **Location**: `./initial_exploration/` (co-located with code)
- **Rationale**: Self-contained exploration folder with scripts, samples, outputs, and documentation together—everything needed to understand the research
- **Content**:
  - `README.md` — How to set up environment, run scripts, interpret outputs
  - `FINDINGS.md` — Main research document: patterns, inconsistencies, design implications
  - Inline comments in scripts (minimal—scripts are throwaway exploration code)
- **Target Audience**: Future implementers who will build the production parser based on these findings
- **Maintenance**: Documentation updated as exploration progresses; no long-term maintenance expected (this is a one-time research phase)

## Future Design Considerations (Post-Research)

These architectural decisions will be informed by the research findings but are NOT in scope for this exploration phase:

### Generic Node Structure Design
- **When to decide**: After analyzing JSON outputs to see what patterns emerge
- **Decision Drivers**: Must represent Python classes, Markdown sections, Terraform resources, and Docker stages without special-casing; must be extensible for future formats
- **Candidate Alternatives**:
  - A) Single universal node type with `type` discriminator field
  - B) Base node class with format-family subclasses (OOP, Markup, Config)
  - C) Schema-per-format with common query interface
  - D) (May discover other options through research)
- **Stakeholders**: Core parser developers, downstream tool builders

### Grammar Management (Already Decided for Research Phase)
- **Decision**: Use `tree-sitter-language-pack==0.11.0` which bundles 50+ language grammars
- **Rationale**: Simplifies setup for exploration—no need to manage individual grammar packages
- **Note**: Production implementation may revisit if we need more control over grammar versions

---

## Clarifications

### Session 2025-01-26

**Q1: Workflow Mode**
- **Selected**: Simple (A)
- **Rationale**: Greenfield project, exploration-focused, no existing code constraints. Single-phase approach allows faster iteration during discovery.

**Q2: Testing Strategy**
- **Selected**: Manual Only (D)
- **Rationale**: This is explicitly a research/exploration phase, not production implementation. We're experimenting with tree-sitter to understand outputs across formats. Deliverables are sample files, JSON outputs, exploration scripts, and findings documentation that will inform future production implementation. No automated tests needed for throwaway research code.

**Q3: Documentation Location**
- **Selected**: `./initial_exploration/` (co-located with scripts and samples)
- **Rationale**: Keep all exploration artifacts together—scripts, sample files, JSON outputs, README, and findings. Self-contained experimentation folder that future implementers can reference.

---

*Spec Version: 2.0.0 - RESEARCH PHASE*
*Created: Initial exploration phase (Phase 0)*
*Updated: Reframed as research/experimentation, not production implementation*
*Status: READY - Research scope clarified*
