# Subtask 002: Tree-Sitter Call Expression Extraction for LSP Integration

**Parent Plan:** [View Plan](../../lsp-integration-plan.md)  
**Parent Phase:** Phase 8: Pipeline Integration  
**Parent Task(s):** [T003: Implement RelationshipExtractionStage](../tasks.md#task-t003), [T016: Update LSP adapter](../tasks.md#task-t016)  
**Plan Task Reference:** [Task 8.3 and 8.16 in Plan](../../lsp-integration-plan.md#phase-8-pipeline-integration)

**Why This Subtask:**  
The current LSP `get_definition` approach was fundamentally flawed—it scanned every line at fixed column positions (4,8,12,16,20,24,28,32), generating 100K+ useless queries. 99%+ returned None because random positions don't contain call expressions. The fix requires extracting call expression positions from tree-sitter AST and querying LSP only at those precise locations.

**Created:** 2026-01-23  
**Requested By:** Development Team (code review finding)

---

## Executive Briefing

### Purpose
This subtask implements proper "what do I call" detection by extracting call expression positions from tree-sitter AST and querying LSP `get_definition` only at those precise locations. This replaces the removed naive line-scanning approach with a correct implementation that reduces LSP queries from ~100K+ to ~1K-2K per scan.

### What We're Building
A call expression extractor that:
- Re-parses callable node content using tree-sitter to find `call` (Python) / `call_expression` (TS/JS/Go) nodes
- Extracts exact (line, column) positions from tree-sitter `start_point`
- Queries LSP `get_definition` only at those call site positions
- Creates `EdgeType.CALLS` edges pointing to definitions
- Complements existing `get_references` (who calls me) with `get_definition` (what do I call)

### Unblocks
- **Full bidirectional call graph**: Currently only "who calls me" works; this adds "what do I call"
- **Accurate method→method edges**: Proper symbol-level resolution for outgoing calls
- **Performance**: Reduces LSP queries from O(lines × 8) to O(call_sites) per function

### Example
**Before (removed approach)**:
```python
# For function with 50 lines: 50 × 8 = 400 queries
for line in range(start, end):
    for col in [4, 8, 12, 16, 20, 24, 28, 32]:
        lsp.get_definition(file, line, col)  # 99%+ return None
```

**After (this subtask)**:
```python
# Extract calls from AST: find ~5-10 actual call sites
call_positions = extract_call_positions(node.content, "python")
# [(5, 12), (7, 8), (15, 20)]  # Exact positions where foo() appears

for line, col in call_positions:
    lsp.get_definition(file, line, col)  # Each returns meaningful result
```

---

## Objectives & Scope

### Objective
Implement tree-sitter call expression extraction to enable accurate LSP `get_definition` queries, restoring the "what do I call" direction of call graph construction.

### Goals

- ✅ Implement `_extract_call_positions(content, language)` utility
- ✅ Support Python (`call`), TypeScript/JavaScript (`call_expression`), Go (`call_expression`)
- ✅ Integrate with RelationshipExtractionStage to query LSP at call sites
- ✅ Create `EdgeType.CALLS` edges with `resolution_rule="lsp:definition"`
- ✅ Add comprehensive unit tests for call extraction
- ✅ Add integration tests validating outgoing call detection
- ✅ Document approach in code comments for future maintainers

### Non-Goals

- ❌ Modify CodeNode model to store call positions (Option A rejected)
- ❌ Extract calls for non-callable nodes (already filtered)
- ❌ Handle macro expansions or dynamic calls (AST-visible only)
- ❌ Performance optimization with caching (defer to profiling)
- ❌ Handle Terraform `function_call` (out of Phase 8 scope)

---

## Architecture Map

### Component Diagram
<!-- Status: grey=pending, orange=in-progress, green=completed, red=blocked -->
<!-- Updated by plan-6 during implementation -->

```mermaid
flowchart TD
    classDef pending fill:#9E9E9E,stroke:#757575,color:#fff
    classDef inprogress fill:#FF9800,stroke:#F57C00,color:#fff
    classDef completed fill:#4CAF50,stroke:#388E3C,color:#fff
    classDef blocked fill:#F44336,stroke:#D32F2F,color:#fff

    style Parent fill:#F5F5F5,stroke:#E0E0E0
    style Subtask fill:#F5F5F5,stroke:#E0E0E0
    style Files fill:#F5F5F5,stroke:#E0E0E0

    subgraph Parent["Parent Context"]
        T003["T003: Implement stage (COMPLETE)"]:::completed
        T016["T016: LSP edge update (COMPLETE but partial)"]:::inprogress
    end

    subgraph Subtask["Subtask 002: Tree-Sitter Call Extraction"]
        ST001["ST001: Research call node types"]:::pending
        ST002["ST002: Write extraction tests (RED)"]:::pending
        ST003["ST003: Implement _extract_call_positions"]:::pending
        ST004["ST004: Write integration tests (RED)"]:::pending
        ST005["ST005: Integrate with stage"]:::pending
        ST006["ST006: Validate with scan"]:::pending

        ST001 --> ST002 --> ST003
        ST003 --> ST004 --> ST005 --> ST006
    end

    subgraph Files["Files"]
        F1["/research-dossier-ast-lsp-integration.md"]:::completed
        F2["/relationship_extraction_stage.py"]:::pending
        F3["/test_call_extraction.py"]:::pending
        F4["/test_call_extraction_integration.py"]:::pending
    end

    ST001 -.-> F1
    ST003 -.-> F2
    ST002 -.-> F3
    ST004 -.-> F4
    ST006 -.->|restores| T016
```

### Task-to-Component Mapping

<!-- Status: ⬜ Pending | 🟧 In Progress | ✅ Complete | 🔴 Blocked -->

| Task | Component(s) | Files | Status | Comment |
|------|-------------|-------|--------|---------|
| ST001 | Research | research-dossier-ast-lsp-integration.md | ✅ Complete | Already documented in dossier |
| ST002 | Unit Tests | test_call_extraction.py | ⬜ Pending | TDD RED phase |
| ST003 | Extraction Utility | relationship_extraction_stage.py | ⬜ Pending | TDD GREEN phase |
| ST004 | Integration Tests | test_call_extraction_integration.py | ⬜ Pending | TDD RED phase |
| ST005 | Stage Integration | relationship_extraction_stage.py | ⬜ Pending | Wire extraction to LSP |
| ST006 | Validation | fs2 scan | ⬜ Pending | End-to-end verification |

---

## Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Subtasks | Notes |
|--------|------|------|-----|------|--------------|------------------|------------|----------|-------|
| [x] | ST001 | Document tree-sitter call node types per language | 1 | Research | – | /workspaces/flow_squared/docs/plans/025-lsp-research/research-dossier-ast-lsp-integration.md | Dossier contains call types | – | ✅ Already complete in research dossier |
| [ ] | ST002 | Write failing unit tests for `_extract_call_positions()` | 2 | Test | ST001 | /workspaces/flow_squared/tests/unit/stages/test_call_extraction.py | Tests fail with ImportError or NotImplemented | – | TDD RED; covers Python, TS, Go |
| [ ] | ST003 | Implement `_extract_call_positions(content, language)` | 2 | Core | ST002 | /workspaces/flow_squared/src/fs2/core/services/stages/relationship_extraction_stage.py | ST002 tests pass | – | Uses tree_sitter_language_pack; returns list[(line, col)] |
| [ ] | ST004 | Write failing integration tests for outgoing call detection | 2 | Test | ST003 | /workspaces/flow_squared/tests/integration/test_call_extraction_integration.py | Tests fail with no edges or wrong edges | – | TDD RED; tests `get_definition` at call sites |
| [ ] | ST005 | Integrate call extraction with `_extract_lsp_relationships()` | 2 | Core | ST003, ST004 | /workspaces/flow_squared/src/fs2/core/services/stages/relationship_extraction_stage.py | ST004 tests pass; `get_definition` called at call sites | – | Query LSP at extracted positions |
| [ ] | ST006 | Run `fs2 scan` and validate outgoing call edges created | 1 | QA | ST005 | /workspaces/flow_squared/scripts/validate_lsp_graph_integration.py | Script shows CALLS edges; no excessive warnings | – | End-to-end verification |

---

## Alignment Brief

### Objective Recap

**Parent Phase Goal**: Integrate RelationshipExtractionStage into scan pipeline with symbol-level resolution.

**This Subtask's Contribution**: Restore the "what do I call" direction of call graph construction by:
1. Extracting call expression positions from tree-sitter AST
2. Querying LSP `get_definition` only at those positions
3. Creating `method:X → method:Y` edges for outgoing calls

### Critical Findings Affecting This Subtask

**From Research Dossier (CD-01)**: Call Expressions Are Already Parsed But Discarded
- **Constraint**: Tree-sitter parses call expressions but they're filtered out by category
- **Implication**: We need to re-parse content specifically to find calls
- **Addressed by**: ST003 (implements extraction utility)

**From Research Dossier (CD-02)**: Position Conversion Is Straightforward
- **Constraint**: Both tree-sitter and LSP use 0-indexed positions
- **Implication**: Minimal conversion needed (just add node.start_line offset)
- **Addressed by**: ST005 (handles position conversion)

**From Plan (DYK-8)**: LSP get_definition Must Be Called at Call-Site Positions
- **Constraint**: Querying at `def foo():` returns nothing—need to query at `bar()` call expressions
- **Addressed by**: ST003, ST005 (extract and query at call sites)

### ADR Decision Constraints

No ADRs directly affect this subtask. However, the decision to use **Option B (re-parse on-demand)** from the research dossier is binding:
- No CodeNode model changes
- Extraction isolated to RelationshipExtractionStage
- Lazy evaluation only for callable nodes

### Invariants & Guardrails

**Inherited from Parent Phase**:
- LSP edges `confidence=1.0`
- All edges MUST have `resolution_rule` with source prefix (`lsp:definition`)
- Errors collected, not raised; scan continues
- Symbol-level node IDs when possible

**Subtask-Specific**:
- Only extract calls for `node.category in ("callable", "method", "function")`
- Tree-sitter parser must match node's `language` field
- Position conversion: `file_line = node.start_line + relative_line - 1` (0-indexed for LSP)

### Inputs to Read

| File | Purpose |
|------|---------|
| `/workspaces/flow_squared/docs/plans/025-lsp-research/research-dossier-ast-lsp-integration.md` | Full research on AST+LSP integration |
| `/workspaces/flow_squared/src/fs2/core/services/stages/relationship_extraction_stage.py` | Current stage implementation (lines 230-285) |
| `/workspaces/flow_squared/src/fs2/core/adapters/ast_parser_impl.py` | Tree-sitter usage patterns (lines 560-680) |
| `/workspaces/flow_squared/tests/integration/test_lsp_integration.py` | Existing LSP test patterns |

### Visual Alignment Aids

#### Call Extraction Flow

```mermaid
flowchart LR
    subgraph Stage["RelationshipExtractionStage"]
        N[CodeNode<br/>callable:auth.py:login]
        E[_extract_call_positions]
        L[_lsp_adapter.get_definition]
    end

    subgraph TreeSitter["Tree-Sitter Parse"]
        C[content]
        T[AST Tree]
        CA[call nodes]
    end

    subgraph LSP["LSP Query"]
        P[Position<br/>line, column]
        D[Definition<br/>location]
    end

    N -->|content| E
    E -->|parse| C
    C --> T
    T -->|find calls| CA
    CA -->|positions| P
    E -->|for each call| L
    L -->|query| P
    P -->|returns| D
    D -->|create edge| ED[CodeEdge<br/>CALLS]
```

#### Position Conversion Sequence

```mermaid
sequenceDiagram
    participant Stage as RelationshipExtractionStage
    participant TS as Tree-Sitter
    participant LSP as SolidLspAdapter

    Note over Stage: node.start_line = 10 (1-indexed)
    Note over Stage: node.content = "def login():\\n  validate()"

    Stage->>TS: parse(content)
    TS-->>Stage: call at start_point=(1, 2)
    Note over Stage: Relative: line=1, col=2

    Stage->>Stage: Convert: file_line = 10 + 1 - 1 = 10
    Note over Stage: LSP needs 0-indexed: line=9

    Stage->>LSP: get_definition(file, line=9, col=2)
    LSP-->>Stage: CodeEdge(target=method:other.py:validate)
```

### Test Plan (TDD Approach)

**Unit Tests (test_call_extraction.py)**:

| Test | Purpose | Fixture | Expected Output |
|------|---------|---------|-----------------|
| `test_given_python_code_when_extract_then_finds_call` | Basic Python | `"def f():\n  foo()"` | `[(1, 2)]` |
| `test_given_nested_calls_when_extract_then_finds_all` | Multiple calls | `"foo(bar(baz()))"` | 3 positions |
| `test_given_method_call_when_extract_then_finds_position` | Method call | `"self.helper()"` | 1 position |
| `test_given_chained_calls_when_extract_then_finds_each` | Chain | `"a().b().c()"` | 3 positions |
| `test_given_typescript_when_extract_then_finds_call_expression` | TypeScript | `"foo()"` | 1 position |
| `test_given_go_when_extract_then_finds_call_expression` | Go | `"fmt.Println(x)"` | 1 position |
| `test_given_no_calls_when_extract_then_returns_empty` | No calls | `"x = 1"` | `[]` |
| `test_given_unknown_language_when_extract_then_returns_empty` | Unknown | language="unknown" | `[]` |

**Integration Tests (test_call_extraction_integration.py)**:

| Test | Purpose | Fixture | Expected Output |
|------|---------|---------|-----------------|
| `test_given_python_call_when_scan_then_creates_calls_edge` | E2E Python | python_multi_project | `EdgeType.CALLS` edge exists |
| `test_given_cross_file_call_when_scan_then_resolves_definition` | Cross-file | Caller → Callee | Edge points to correct method |
| `test_given_call_chain_when_scan_then_creates_all_edges` | A→B→C | Chain fixture | 2 CALLS edges |
| `test_given_lsp_unavailable_when_extract_then_graceful_skip` | Degradation | No LSP | No CALLS edges, no error |

### Step-by-Step Implementation Outline

1. **ST001** (✅ Complete): Research documented in `research-dossier-ast-lsp-integration.md`
   - Call types: Python=`call`, TS/JS/Go=`call_expression`
   - Position: `node.start_point` = (row, column) 0-indexed

2. **ST002**: Write failing unit tests
   - Create `/tests/unit/stages/test_call_extraction.py`
   - Test `_extract_call_positions(content, language)` for Python, TS, Go
   - Tests should fail with `AttributeError` or `NotImplementedError`

3. **ST003**: Implement `_extract_call_positions()`
   - Add method to `RelationshipExtractionStage`
   - Use `tree_sitter_language_pack.get_parser(language)`
   - Traverse AST recursively, collect positions for `call`/`call_expression`
   - Return `list[tuple[int, int]]` (line, column both 0-indexed)

4. **ST004**: Write failing integration tests
   - Create `/tests/integration/test_call_extraction_integration.py`
   - Test that `get_definition` creates CALLS edges
   - Use existing python_multi_project fixtures

5. **ST005**: Integrate with `_extract_lsp_relationships()`
   - After existing `get_references` code (line 272)
   - Extract call positions from `node.content`
   - For each position, compute file-level line: `node.start_line + rel_line - 1`
   - Query `lsp.get_definition(file, file_line - 1, col)` (convert to 0-indexed)
   - Upgrade edges to symbol-level

6. **ST006**: Validate with real scan
   - Run `fs2 scan .` on codebase
   - Verify no excessive warnings
   - Run validation script to confirm CALLS edges

### Commands to Run

```bash
# Run unit tests for call extraction
pytest tests/unit/stages/test_call_extraction.py -v

# Run integration tests
pytest tests/integration/test_call_extraction_integration.py -v

# Run all LSP tests
pytest tests/ -k "lsp" -v

# Type check
mypy src/fs2/core/services/stages/relationship_extraction_stage.py --strict

# Lint
ruff check src/fs2/core/services/stages/relationship_extraction_stage.py

# Validation scan (small fixture)
cd tests/fixtures/lsp/python_multi_project && fs2 scan .

# Full codebase scan (use with caution)
fs2 scan . 2>&1 | head -100
```

### Risks & Unknowns

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Tree-sitter parser initialization overhead | Low | Medium | Parser is already initialized in ParsingStage; reuse same language |
| Some languages have different call node types | Medium | Low | Document in code; extend CALL_TYPES set as needed |
| Position conversion off-by-one errors | Medium | High | Comprehensive unit tests with boundary cases |
| LSP server returns None for valid calls | Low | Low | Already handled; log debug, continue |

### Ready Check

- [ ] Research dossier reviewed and understood
- [ ] Call node types confirmed: Python=`call`, TS/JS/Go=`call_expression`
- [ ] Position conversion formula verified: `file_line = node.start_line + rel_line - 1`
- [ ] Test fixtures available (python_multi_project, etc.)
- [ ] LSP servers installed (Pyright, typescript-language-server, gopls)
- [ ] All unit and integration tests discoverable

**When all boxes checked**: Run `/plan-6-implement-phase --subtask 002-subtask-tree-sitter-call-extraction --plan /workspaces/flow_squared/docs/plans/025-lsp-research/lsp-integration-plan.md --phase "Phase 8: Pipeline Integration"`

---

## Phase Footnote Stubs

_Reserved for plan-6 to add implementation footnotes._

| Footnote | Date | Task | Note |
|----------|------|------|------|
| | | | |

---

## Evidence Artifacts

### Execution Log

- **Path**: `002-subtask-tree-sitter-call-extraction.execution.log.md`
- **Purpose**: Detailed narrative of implementation progress
- **Created by**: plan-6 during implementation

### Test Files

- `/workspaces/flow_squared/tests/unit/stages/test_call_extraction.py`
- `/workspaces/flow_squared/tests/integration/test_call_extraction_integration.py`

### Modified Files

- `/workspaces/flow_squared/src/fs2/core/services/stages/relationship_extraction_stage.py`

---

## Discoveries & Learnings

_Populated during implementation by plan-6. Log anything of interest to your future self._

| Date | Task | Type | Discovery | Resolution | References |
|------|------|------|-----------|------------|------------|
| | | | | | |

**Types**: `gotcha` | `research-needed` | `unexpected-behavior` | `workaround` | `decision` | `debt` | `insight`

**What to log**:
- Things that didn't work as expected
- External research that was required
- Implementation troubles and how they were resolved
- Gotchas and edge cases discovered
- Decisions made during implementation
- Technical debt introduced (and why)
- Insights that future phases should know about

_See also: `execution.log.md` for detailed narrative._

---

## After Subtask Completion

**This subtask resolves a blocker for:**
- Parent Task: [T016: Update LSP adapter for symbol-level edges](../tasks.md#task-t016)
- Plan Task: [Task 8.16 in Plan](../../lsp-integration-plan.md#phase-8-pipeline-integration)

**When all ST### tasks complete:**

1. **Record completion** in parent execution log:
   ```
   ### Subtask 002-subtask-tree-sitter-call-extraction Complete

   Resolved: Implemented tree-sitter call expression extraction for accurate LSP get_definition queries
   See detailed log: [subtask execution log](./002-subtask-tree-sitter-call-extraction.execution.log.md)
   ```

2. **Update parent task** (if it was blocked):
   - Open: [`tasks.md`](../tasks.md)
   - Find: T016 (already marked complete but partial)
   - Update Notes: Add "Subtask 002 complete - full bidirectional call graph"

3. **Resume parent phase work:**
   ```bash
   /plan-6-implement-phase --phase "Phase 8: Pipeline Integration" \
     --plan "/workspaces/flow_squared/docs/plans/025-lsp-research/lsp-integration-plan.md"
   ```
   (Note: NO `--subtask` flag to resume main phase)

**Quick Links:**
- 📋 [Parent Dossier](../tasks.md)
- 📄 [Parent Plan](../../lsp-integration-plan.md)
- 📊 [Parent Execution Log](../execution.log.md)
- 📚 [Research Dossier](../../research-dossier-ast-lsp-integration.md)

---

## Directory Structure After Subtask

```
docs/plans/025-lsp-research/tasks/phase-8-pipeline-integration/
├── tasks.md                                          # Parent dossier
├── execution.log.md                                  # Parent execution log
├── 002-subtask-tree-sitter-call-extraction.md        # This file
└── 002-subtask-tree-sitter-call-extraction.execution.log.md  # Created by plan-6
```
