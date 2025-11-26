# Universal AST Parser - Tree-sitter Exploration Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2025-01-26
**Spec**: [./universal-ast-parser-spec.md](./universal-ast-parser-spec.md)
**Research**: [./tree-sitter-research.md](./tree-sitter-research.md)
**Status**: READY

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Research Findings](#critical-research-findings)
3. [Implementation](#implementation)
4. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

**Problem**: Before building a universal code parser, we need empirical evidence about how tree-sitter parses diverse file formats—what's consistent, what varies, and whether a truly universal abstraction is feasible.

**Solution**: Create 16+ sample files across diverse formats (Python, JS, Markdown, Terraform, Dockerfile, etc.), generate raw JSON AST outputs using tree-sitter, and document patterns and inconsistencies to inform future production design.

**Expected Outcome**: A self-contained `initial_exploration/` folder with sample files, JSON outputs, exploration scripts, and a FINDINGS.md document that answers key design questions about universal parsing.

---

## Critical Research Findings

Research synthesized from `tree-sitter-research.md` and spec analysis:

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | **Named vs Anonymous nodes**: `is_named` property universally distinguishes structural (grammar rules) from syntactic (punctuation) nodes | Use `is_named` filter as primary structural selector in exploration script |
| 02 | Critical | **tree-sitter-language-pack API**: Use `get_parser(language)` to get parser, `get_language(language)` for language object | Import from `tree_sitter_language_pack`, not individual grammar packages |
| 03 | Critical | **Text extraction**: Tree-sitter stores byte ranges, not text; use `source[node.start_byte:node.end_byte]` | Store source bytes and slice; don't rely on `node.text` property |
| 04 | High | **Common node patterns**: Most grammars use `*_definition`, `*_declaration`, `*_statement`, `*_block` naming | Look for these suffix patterns when analyzing outputs |
| 05 | High | **Field availability varies**: Some grammars have rich fields (`name`, `body`, `parameters`), others use flat children | Document which grammars have fields vs flat children in FINDINGS.md |
| 06 | High | **Markdown hierarchy uncertainty**: Some grammars use `section` nodes, others flat `atx_heading` | Test markdown grammar specifically to determine hierarchy approach |
| 07 | High | **Root node types vary**: `module` (Python), `program` (JS), `document` (Markdown), `source_file` (others) | Don't hardcode root expectations; observe and document per-grammar |
| 08 | Medium | **TreeCursor more efficient**: Use `node.walk()` cursor for traversal instead of recursive `children` iteration | Implement cursor-based traversal in exploration script |
| 09 | Medium | **Supertypes exist**: Grammars define `_declaration`, `_expression` supertypes grouping related nodes | Look for supertype patterns in node-types metadata if needed |
| 10 | Medium | **Error handling built-in**: `node.has_error` and `node.is_error` indicate parse failures | Include error flags in JSON output for debugging |
| 11 | Medium | **Language detection not included**: `tree-sitter-language-pack` doesn't map file extensions to languages | Build simple extension→language mapping table in script |
| 12 | Low | **HCL for Terraform**: Terraform files use `hcl` grammar, not `terraform` | Use `hcl` as language key for `.tf` files |
| 13 | Low | **Point vs byte coordinates**: `start_point`/`end_point` give row/column; `start_byte`/`end_byte` give offsets | Include both in JSON output for flexibility |

---

## Implementation

**Objective**: Generate sample files and JSON AST outputs for 16+ formats, creating a knowledge base to inform universal parser design.

**Testing Approach**: Manual Only (run scripts, inspect outputs visually)
**Mock Usage**: N/A (no mocks—real tree-sitter parsing only)

### Phases

| Phase | Name | Description |
|-------|------|-------------|
| 0 | Setup | Create directory structure, initialize uv project, install dependencies, verify grammar availability |
| 1 | Exploration | Create sample files, write parsing script, generate JSON outputs, analyze and document findings |

### Directory Structure

```
/workspaces/flow_squared/initial_exploration/
├── README.md                    # Setup, usage, deliverables explanation
├── FINDINGS.md                  # Patterns, inconsistencies, design recommendations
├── GRAMMAR_AVAILABILITY.md      # Enumeration of available grammars in language-pack
├── sample_repo/                 # Sample files by format
│   ├── python/
│   │   └── sample.py
│   ├── javascript/
│   │   └── sample.js
│   ├── typescript/
│   │   └── sample.ts
│   ├── go/
│   │   └── sample.go
│   ├── rust/
│   │   └── sample.rs
│   ├── cpp/
│   │   └── sample.cpp
│   ├── csharp/
│   │   └── sample.cs
│   ├── dart/
│   │   └── sample.dart
│   ├── markdown/
│   │   └── sample.md
│   ├── terraform/
│   │   └── sample.tf
│   ├── dockerfile/
│   │   └── Dockerfile
│   ├── yaml/
│   │   └── sample.yaml
│   ├── json/
│   │   └── sample.json
│   ├── toml/
│   │   └── sample.toml
│   ├── sql/
│   │   └── sample.sql
│   └── shell/
│       └── sample.sh
├── outputs/                     # JSON AST dumps
│   ├── python_sample.json
│   ├── javascript_sample.json
│   └── ... (one per sample)
└── scripts/
    └── parse_to_json.py         # Main exploration script
```

### Phase 0: Setup

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|------------------|------------|-------|
| [ ] | P0-T1 | Create initial_exploration directory structure | 1 | Setup | -- | /workspaces/flow_squared/initial_exploration/ | Directories exist: sample_repo/, outputs/, scripts/ | mkdir -p for all dirs |
| [ ] | P0-T2 | Initialize uv project and install dependencies | 1 | Setup | P0-T1 | /workspaces/flow_squared/initial_exploration/pyproject.toml | `uv sync` succeeds, tree-sitter importable | tree-sitter==0.25.2, tree-sitter-language-pack==0.11.0 |
| [ ] | P0-T3 | Verify grammar availability and document | 1 | Setup | P0-T2 | /workspaces/flow_squared/initial_exploration/GRAMMAR_AVAILABILITY.md | Lists all available grammars, confirms 16 target languages | Enumerate tree-sitter-language-pack, note any missing |

### Phase 1: Exploration

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|------------------|------------|-------|
| [ ] | P1-T1 | Create Python sample file | 1 | Sample | P0-T3 | /workspaces/flow_squared/initial_exploration/sample_repo/python/sample.py | File contains class, methods, function, decorator, async | Representative OOP code |
| [ ] | P1-T2 | Create JavaScript sample file | 1 | Sample | P0-T3 | /workspaces/flow_squared/initial_exploration/sample_repo/javascript/sample.js | File contains function, class, arrow function, module | ES6+ features |
| [ ] | P1-T3 | Create TypeScript sample file | 1 | Sample | P0-T3 | /workspaces/flow_squared/initial_exploration/sample_repo/typescript/sample.ts | File contains interface, type, generic, class | TS-specific constructs |
| [ ] | P1-T4 | Create Go sample file | 1 | Sample | P0-T3 | /workspaces/flow_squared/initial_exploration/sample_repo/go/sample.go | File contains package, struct, method, interface | Go idioms |
| [ ] | P1-T5 | Create Rust sample file | 1 | Sample | P0-T3 | /workspaces/flow_squared/initial_exploration/sample_repo/rust/sample.rs | File contains struct, trait, impl, enum | Rust ownership patterns |
| [ ] | P1-T6 | Create C++ sample file | 1 | Sample | P0-T3 | /workspaces/flow_squared/initial_exploration/sample_repo/cpp/sample.cpp | File contains class, namespace, template | C++ OOP |
| [ ] | P1-T7 | Create C# sample file | 1 | Sample | P0-T3 | /workspaces/flow_squared/initial_exploration/sample_repo/csharp/sample.cs | File contains class, namespace, property, LINQ | .NET patterns |
| [ ] | P1-T8 | Create Dart sample file | 1 | Sample | P0-T3 | /workspaces/flow_squared/initial_exploration/sample_repo/dart/sample.dart | File contains class, mixin, extension, async | Flutter-style Dart |
| [ ] | P1-T9 | Create Markdown sample file | 1 | Sample | P0-T3 | /workspaces/flow_squared/initial_exploration/sample_repo/markdown/sample.md | File contains h1, h2, h3, code blocks, lists | Nested structure |
| [ ] | P1-T10 | Create Terraform sample file | 1 | Sample | P0-T3 | /workspaces/flow_squared/initial_exploration/sample_repo/terraform/sample.tf | File contains resource, data, variable, module ref | IaC patterns |
| [ ] | P1-T11 | Create Dockerfile sample | 1 | Sample | P0-T3 | /workspaces/flow_squared/initial_exploration/sample_repo/dockerfile/Dockerfile | File contains multi-stage, ARG, ENV, RUN, CMD | Docker best practices |
| [ ] | P1-T12 | Create YAML sample file | 1 | Sample | P0-T3 | /workspaces/flow_squared/initial_exploration/sample_repo/yaml/sample.yaml | File contains nested maps, sequences, anchors | K8s-style YAML |
| [ ] | P1-T13 | Create JSON sample file | 1 | Sample | P0-T3 | /workspaces/flow_squared/initial_exploration/sample_repo/json/sample.json | File contains nested objects, arrays | Config-style JSON |
| [ ] | P1-T14 | Create TOML sample file | 1 | Sample | P0-T3 | /workspaces/flow_squared/initial_exploration/sample_repo/toml/sample.toml | File contains tables, arrays, nested tables | pyproject.toml style |
| [ ] | P1-T15 | Create SQL sample file | 1 | Sample | P0-T3 | /workspaces/flow_squared/initial_exploration/sample_repo/sql/sample.sql | File contains CREATE, SELECT, JOIN, CTE | Database patterns |
| [ ] | P1-T16 | Create shell script sample | 1 | Sample | P0-T3 | /workspaces/flow_squared/initial_exploration/sample_repo/shell/sample.sh | File contains function, conditional, loop, pipe | Bash idioms |
| [ ] | P1-T17 | Write parse_to_json.py exploration script | 2 | Core | P0-T3 | /workspaces/flow_squared/initial_exploration/scripts/parse_to_json.py | Script parses file, outputs formatted JSON AST | Use TreeCursor, include all node metadata |
| [ ] | P1-T18 | Add extension→language mapping to script | 1 | Core | P1-T17 | /workspaces/flow_squared/initial_exploration/scripts/parse_to_json.py | Script auto-detects language from file extension | Handle .tf→hcl, Dockerfile special case |
| [ ] | P1-T19 | Generate JSON output for Python sample | 1 | Output | P1-T17,P1-T1 | /workspaces/flow_squared/initial_exploration/outputs/python_sample.json | JSON file exists with complete AST | Verify class/method nodes present |
| [ ] | P1-T20 | Generate JSON output for JavaScript sample | 1 | Output | P1-T17,P1-T2 | /workspaces/flow_squared/initial_exploration/outputs/javascript_sample.json | JSON file exists with complete AST | Verify function/class nodes present |
| [ ] | P1-T21 | Generate JSON output for TypeScript sample | 1 | Output | P1-T17,P1-T3 | /workspaces/flow_squared/initial_exploration/outputs/typescript_sample.json | JSON file exists with complete AST | Verify interface/type nodes present |
| [ ] | P1-T22 | Generate JSON output for Go sample | 1 | Output | P1-T17,P1-T4 | /workspaces/flow_squared/initial_exploration/outputs/go_sample.json | JSON file exists with complete AST | Verify struct/method nodes present |
| [ ] | P1-T23 | Generate JSON output for Rust sample | 1 | Output | P1-T17,P1-T5 | /workspaces/flow_squared/initial_exploration/outputs/rust_sample.json | JSON file exists with complete AST | Verify struct/impl nodes present |
| [ ] | P1-T24 | Generate JSON output for C++ sample | 1 | Output | P1-T17,P1-T6 | /workspaces/flow_squared/initial_exploration/outputs/cpp_sample.json | JSON file exists with complete AST | Verify class/namespace nodes present |
| [ ] | P1-T25 | Generate JSON output for C# sample | 1 | Output | P1-T17,P1-T7 | /workspaces/flow_squared/initial_exploration/outputs/csharp_sample.json | JSON file exists with complete AST | Verify class/namespace nodes present |
| [ ] | P1-T26 | Generate JSON output for Dart sample | 1 | Output | P1-T17,P1-T8 | /workspaces/flow_squared/initial_exploration/outputs/dart_sample.json | JSON file exists with complete AST | Verify class/mixin nodes present |
| [ ] | P1-T27 | Generate JSON output for Markdown sample | 1 | Output | P1-T17,P1-T9 | /workspaces/flow_squared/initial_exploration/outputs/markdown_sample.json | JSON file exists with complete AST | Note: check for section vs flat headings |
| [ ] | P1-T28 | Generate JSON output for Terraform sample | 1 | Output | P1-T17,P1-T10 | /workspaces/flow_squared/initial_exploration/outputs/terraform_sample.json | JSON file exists with complete AST | Use hcl grammar |
| [ ] | P1-T29 | Generate JSON output for Dockerfile sample | 1 | Output | P1-T17,P1-T11 | /workspaces/flow_squared/initial_exploration/outputs/dockerfile_sample.json | JSON file exists with complete AST | Verify instruction nodes present |
| [ ] | P1-T30 | Generate JSON output for YAML sample | 1 | Output | P1-T17,P1-T12 | /workspaces/flow_squared/initial_exploration/outputs/yaml_sample.json | JSON file exists with complete AST | Verify mapping/sequence nodes present |
| [ ] | P1-T31 | Generate JSON output for JSON sample | 1 | Output | P1-T17,P1-T13 | /workspaces/flow_squared/initial_exploration/outputs/json_sample.json | JSON file exists with complete AST | Verify object/array nodes present |
| [ ] | P1-T32 | Generate JSON output for TOML sample | 1 | Output | P1-T17,P1-T14 | /workspaces/flow_squared/initial_exploration/outputs/toml_sample.json | JSON file exists with complete AST | Verify table nodes present |
| [ ] | P1-T33 | Generate JSON output for SQL sample | 1 | Output | P1-T17,P1-T15 | /workspaces/flow_squared/initial_exploration/outputs/sql_sample.json | JSON file exists with complete AST | Verify statement nodes present |
| [ ] | P1-T34 | Generate JSON output for shell sample | 1 | Output | P1-T17,P1-T16 | /workspaces/flow_squared/initial_exploration/outputs/shell_sample.json | JSON file exists with complete AST | Verify function/command nodes present |
| [ ] | P1-T35 | Write README.md with setup and usage | 1 | Docs | P1-T17 | /workspaces/flow_squared/initial_exploration/README.md | README explains setup, running scripts, interpreting outputs | Include uv commands |
| [ ] | P1-T36 | Analyze outputs and write FINDINGS.md | 3 | Docs | P1-T19 to P1-T34 | /workspaces/flow_squared/initial_exploration/FINDINGS.md | Document patterns, inconsistencies, design recommendations | Answer spec's 10 open questions; compare OOP vs Config vs IaC formats; identify cross-format patterns; propose production design approach |

### Acceptance Criteria

- [ ] All 16 sample files created with representative content (AC1, AC2)
- [ ] All 16 JSON AST output files generated (AC3)
- [ ] parse_to_json.py script works for any supported file (AC4)
- [ ] JSON outputs include node types, fields, byte/line ranges, children (AC5)
- [ ] FINDINGS.md compares at least 5 diverse formats (AC6)
- [ ] FINDINGS.md identifies patterns and inconsistencies (AC7)
- [ ] FINDINGS.md proposes design approach for production parser (AC8)
- [ ] README.md exists with setup and usage instructions (AC9)
- [ ] All artifacts in `initial_exploration/` directory (AC10)

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Some grammars not in language-pack | Low | Low | Document which formats unavailable; proceed with available ones |
| JSON outputs too verbose to analyze | Medium | Medium | Focus on named nodes; consider summary script |
| Unexpected grammar behavior | Medium | Low | Document quirks in FINDINGS.md—that's the point of research |

---

## Change Footnotes Ledger

[^1]: [To be added during implementation via plan-6a]
[^2]: [To be added during implementation via plan-6a]

---

**Next steps:**
- **Phase 0 first**: Execute setup tasks (P0-T1 → P0-T2 → P0-T3) before exploration
- **Ready to implement**: `/plan-6-implement-phase --plan "docs/plans/001-universal-ast-parser/universal-ast-parser-plan.md"`

---

## Critical Insights Discussion

**Session**: 2025-11-26
**Context**: Universal AST Parser - Tree-sitter Exploration Plan v1.0
**Analyst**: AI Clarity Agent
**Reviewer**: Development Team
**Format**: Water Cooler Conversation (5 Critical Insights)

### Insight 1: Grammar Availability Risk

**Did you know**: The plan assumed all 16 languages are in `tree-sitter-language-pack==0.11.0`, but this hadn't been verified—some grammars like Dart, C#, or HCL might not be included or might be lower quality.

**Implications**:
- Some research questions could go unanswered
- Time wasted creating samples for unsupported languages
- Comparison findings biased toward well-supported grammars

**Options Considered**:
- Option A: Verify Upfront - Add task to enumerate grammars before samples
- Option B: Best-Effort - Proceed and document failures
- Option C: Reduce Scope - Start with known-good grammars only

**AI Recommendation**: Option A (Verify Upfront)
- Reasoning: 15 minutes of verification could save hours of debugging; proactive is better than reactive for research.

**Discussion Summary**: User chose Option A but wanted output as a proper markdown doc in the exploration folder rather than just a task artifact.

**Decision**: Add P0-T3 task to verify grammar availability and output to `GRAMMAR_AVAILABILITY.md`

**Action Items**:
- [x] Add T000/P0-T3 task to plan
- [x] Add GRAMMAR_AVAILABILITY.md to directory structure

**Affects**: Phase 0 tasks, directory structure

---

### Insight 2: JSON Output Size Problem

**Did you know**: Raw tree-sitter JSON outputs can be thousands of lines for simple files—a 50-line Python class could produce 500+ lines of JSON, making manual analysis of 16 files impractical.

**Implications**:
- Opening JSON files = wall of noise
- Finding structural nodes = needle in haystack
- Cross-format comparison becomes superficial

**Options Considered**:
- Option A: Named-Only Filter - Add `--named-only` flag to script
- Option B: Summary Statistics - Create separate summarize script
- Option C: Raw Only - Use jq/grep for ad-hoc filtering
- Option D: Depth Limit - Add `--max-depth` flag

**AI Recommendation**: Option A (Named-Only Filter)
- Reasoning: Research Finding #01 already identified `is_named` as key filter; filtered files 60-70% smaller.

**Discussion Summary**: User chose to generate everything first, then iterate backwards to determine final formats. "Large is fine for now" - maximize data capture, refine later.

**Decision**: Keep full raw output, defer filtering decisions until after seeing real data

**Action Items**: None - proceed with current plan

**Affects**: No changes needed

---

### Insight 3: "Representative" Sample Files Undefined

**Did you know**: Sample tasks say "file contains class, methods, function" but there's no actual checklist—different authors could make different implicit choices, affecting what patterns get discovered.

**Implications**:
- "Representative" is subjective and unverifiable
- Key spec questions might go unanswered if samples miss constructs
- Inconsistent coverage across samples

**Options Considered**:
- Option A: Construct Checklist - Define explicit checklist per format
- Option B: Map Spec Questions - Extract required constructs from 10 spec questions
- Option C: Keep Loose - Create reasonable samples, iterate if gaps emerge

**AI Recommendation**: Option B (Map Spec Questions)
- Reasoning: Lightweight approach tied directly to research goals.

**Discussion Summary**: User preferred Option C - stay agile, iterate using jq, work through it as we go.

**Decision**: Keep sample requirements loose, iterate based on actual findings

**Action Items**: None - proceed with current task descriptions

**Affects**: No changes needed

---

### Insight 4: FINDINGS.md Complexity Underestimated

**Did you know**: T038 (write FINDINGS.md) was marked CS-2, but it requires synthesizing 16 JSON outputs, answering 10 spec questions, identifying cross-format patterns, and proposing design approaches—that's CS-3 or higher.

**Implications**:
- T038 is the entire point of the research
- If rushed, whole exploration loses value
- CS-2 label sets wrong expectations

**Options Considered**:
- Option A: Re-score to CS-3 - Update complexity and add explicit sub-deliverables
- Option B: Split into Multiple Tasks - Separate analysis by format family
- Option C: Keep As-Is - Accept it's meaty, don't change plan

**AI Recommendation**: Option A (Re-score and Add Structure)
- Reasoning: CS score should reflect reality; explicit sub-deliverables ensure nothing missed.

**Discussion Summary**: User agreed with Option A.

**Decision**: Re-score T038 to CS-3, add explicit deliverables to Notes

**Action Items**:
- [x] Update T038 complexity: CS-2 → CS-3
- [x] Add sub-deliverables to Notes column

**Affects**: Task P1-T36 (formerly T038)

---

### Insight 5: Task Dependency Order Incorrect

**Did you know**: T000 (verify grammar availability) was listed with "Dependencies: --" but actually requires T002 (install dependencies) to run first—you can't enumerate grammars without installing the package.

**Implications**:
- Following task IDs sequentially would cause T000 to fail
- Dependency column contradicted Notes ("Run after T002")
- Sample creation ideally waits for T000 to confirm availability

**Options Considered**:
- Option A: Fix Dependencies - Change T000 deps from "--" to "T002"
- Option B: Renumber Tasks - Make IDs match execution order
- Option C: Leave As-Is - Trust human judgment

**AI Recommendation**: Option A (Fix Dependencies)
- Reasoning: Dependency column should be accurate; one small edit fixes it.

**Discussion Summary**: User went further—add a Phase 0 for setup to make the flow explicit. "Violate the 1 phase rule and add phase 0 which is setup."

**Decision**: Create Phase 0 (Setup) and Phase 1 (Exploration) with proper task IDs and dependencies

**Action Items**:
- [x] Add Phases table to plan
- [x] Rename tasks: P0-T1, P0-T2, P0-T3 for setup; P1-T1 through P1-T36 for exploration
- [x] Fix all dependency references

**Affects**: Entire task structure, plan format

---

## Session Summary

**Insights Surfaced**: 5 critical insights identified and discussed
**Decisions Made**: 5 decisions reached through collaborative discussion
**Action Items Created**: 3 plan updates completed
**Areas Updated**:
- Added Phase 0/Phase 1 structure
- Added GRAMMAR_AVAILABILITY.md to deliverables
- Re-scored T038 (now P1-T36) to CS-3
- Renumbered all tasks with phase prefixes
- Fixed dependency chain

**Shared Understanding Achieved**: ✓

**Confidence Level**: High - Key risks identified and mitigated through plan improvements

**Next Steps**:
Execute Phase 0 (P0-T1 → P0-T2 → P0-T3) to set up environment and verify grammar availability before proceeding to Phase 1 exploration tasks.
