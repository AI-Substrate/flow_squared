# Subtask 002: Language Handler Strategy for Unique Node IDs

**Parent Plan:** [View Plan](../../smart-content-plan.md)
**Parent Phase:** Phase 6: Scan Pipeline Integration
**Parent Task(s):** [T003](./tasks.md#t003), [T005](./tasks.md#t005)
**Plan Task Reference:** [Task 6.3, 6.5 in Plan](../../smart-content-plan.md#phase-6-scan-pipeline-integration)

**Why This Subtask:**
Investigation revealed smart content re-processes ~13-15 nodes every scan despite graph loading (Subtask 001). Root cause: **duplicate node_ids** from languages where tree-sitter produces non-unique names. For example, Python's `"block"` type is a body wrapper, while other languages use `"block"` for actual code blocks. C++ has multiple methods with identical signatures (`ListenerId`). The current parser has inline language checks (`language == "python"`) violating Clean Architecture principles. This subtask implements a **Language Handler Strategy** pattern to isolate language-specific logic into testable, pluggable adapters.

**Created:** 2025-12-25
**Requested By:** Development Team (via smart content re-scanning investigation)

---

## Executive Briefing

### Purpose
This subtask eliminates duplicate node_ids by implementing a clean, extensible **Language Handler Strategy** pattern. This ensures each node has a unique, stable identifier across parses—enabling the hash-based skip logic (AC5/AC6) to work correctly and preventing unnecessary LLM re-processing.

### What We're Building
A pluggable language handler architecture:

1. **LanguageHandler ABC** - Base class defining override points for language-specific behavior
2. **Handler Registry** - Auto-discovery mechanism for language handlers
3. **PythonHandler** - Handles Python's `"block"` as container type
4. **Handler Integration** - TreeSitterParser delegates to handlers for language-specific logic
5. **Diagnostic Scripts** - Tools to identify remaining duplicate node_ids

### Unblocks
- **Smart Content Hash Skip Logic**: Stable node_ids mean `content_hash` comparisons work correctly
- **T003**: SmartContentStage merge logic depends on stable node_id matching
- **Future Languages**: Easy addition of Go, Rust, C++ handlers without modifying core parser

### Example

**Before (language-specific code in parser):**
```python
# ast_parser_impl.py - VIOLATION: hardcoded language checks
is_python_block = ts_kind == "block" and language == "python"
if language == "hcl" and node.type == "block":
    # HCL-specific extraction...
```

**After (clean handler delegation):**
```python
# ast_parser_impl.py - CLEAN: delegates to handlers
handler = self._get_handler(language)
if handler.is_container(ts_kind):
    # Recurse without creating node
    ...
```

```python
# ast_languages/python.py - ISOLATED: language-specific logic
class PythonHandler(LanguageHandler):
    def is_container(self, ts_kind: str) -> bool:
        return ts_kind == "block"  # Python's block is a body wrapper
```

---

## Objectives & Scope

### Objective
Implement Language Handler Strategy pattern to isolate language-specific AST parsing logic, enabling unique node_id generation and eliminating the root cause of smart content re-processing.

### Goals

- ✅ Create `LanguageHandler` ABC with extension points (`is_container`, `extract_name`, `classify_node`)
- ✅ Create `ast_languages/` directory for language-specific handlers
- ✅ Implement `PythonHandler` to handle `"block"` as container type
- ✅ Implement handler registry with auto-discovery
- ✅ Refactor `TreeSitterParser._extract_nodes()` to delegate to handlers
- ✅ Remove inline language checks from `ast_parser_impl.py`
- ✅ Create diagnostic script to verify no duplicate node_ids remain
- ✅ Write comprehensive tests for handler pattern (TDD)
- ✅ Document pattern for adding new language handlers

### Non-Goals

- ❌ Implement handlers for all 100+ languages (only Python needed now)
- ❌ Add Go/Rust/C++ handlers (future work when issues arise)
- ❌ Re-add HCL/Dockerfile to EXTRACTABLE_LANGUAGES (remain as content blobs)
- ❌ Change node_id format (keep `{category}:{path}:{qualified_name}`)
- ❌ Performance optimization of handler lookup (dict lookup is O(1))

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

    subgraph Parent["Parent Context (Phase 6)"]
        T003["T003: SmartContentStage"]:::pending
        T005["T005: ScanPipeline constructor"]:::pending
    end

    subgraph Subtask["Subtask 002: Language Handler Strategy"]
        ST001["ST001: LanguageHandler ABC tests"]:::pending
        ST002["ST002: Implement LanguageHandler ABC"]:::pending
        ST003["ST003: Handler registry tests"]:::pending
        ST004["ST004: Implement handler registry"]:::pending
        ST005["ST005: PythonHandler tests"]:::pending
        ST006["ST006: Implement PythonHandler"]:::pending
        ST007["ST007: Parser integration tests"]:::pending
        ST008["ST008: Refactor parser to use handlers"]:::pending
        ST009["ST009: Verify no duplicate node_ids"]:::pending

        ST001 --> ST002
        ST003 --> ST004
        ST002 --> ST004
        ST005 --> ST006
        ST004 --> ST006
        ST007 --> ST008
        ST006 --> ST008
        ST008 --> ST009
    end

    subgraph Files["Files"]
        F1["ast_languages/__init__.py"]:::pending
        F2["ast_languages/handler.py"]:::pending
        F3["ast_languages/python.py"]:::pending
        F4["ast_parser_impl.py"]:::pending
        F5["test_language_handler.py"]:::pending
        F6["test_python_handler.py"]:::pending
        F7["diagnose_duplicate_nodeids.py"]:::pending
    end

    ST001 -.-> F5
    ST002 -.-> F2
    ST003 -.-> F5
    ST004 -.-> F1
    ST005 -.-> F6
    ST006 -.-> F3
    ST007 -.-> F5
    ST008 -.-> F4
    ST009 -.-> F7
    ST009 -.->|stabilizes| T003
    ST009 -.->|stabilizes| T005
```

### Task-to-Component Mapping

<!-- Status: ⬜ Pending | 🟧 In Progress | ✅ Complete | 🔴 Blocked -->

| Task | Component(s) | Files | Status | Comment |
|------|-------------|-------|--------|---------|
| ST001 | LanguageHandler ABC Tests | `test_language_handler.py` | ⬜ Pending | TDD: Test ABC interface and default behavior |
| ST002 | LanguageHandler ABC | `ast_languages/handler.py` | ⬜ Pending | Base class with `is_container`, `extract_name`, `classify_node` |
| ST003 | Handler Registry Tests | `test_language_handler.py` | ⬜ Pending | TDD: Test registration and lookup |
| ST004 | Handler Registry | `ast_languages/__init__.py` | ⬜ Pending | Dict-based registry with default handler |
| ST005 | PythonHandler Tests | `test_python_handler.py` | ⬜ Pending | TDD: Test Python-specific behavior |
| ST006 | PythonHandler | `ast_languages/python.py` | ⬜ Pending | `is_container("block") -> True` |
| ST007 | Parser Integration Tests | `test_language_handler.py` | ⬜ Pending | TDD: Test parser uses handlers correctly |
| ST008 | Parser Refactor | `ast_parser_impl.py` | ⬜ Pending | Remove inline checks, delegate to handlers |
| ST009 | Verification | `diagnose_duplicate_nodeids.py` | ⬜ Pending | Confirm zero duplicates in fixture files |

---

## Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Subtasks | Notes |
|--------|------|------|-----|------|--------------|------------------|------------|----------|-------|
| [ ] | ST001 | Write tests for LanguageHandler ABC interface | 2 | Test | – | `/workspaces/flow_squared/tests/unit/adapters/test_language_handler.py` | Tests cover: ABC cannot be instantiated, default methods return None/False, language property | – | TDD RED |
| [ ] | ST002 | Implement LanguageHandler ABC with extension points | 2 | Core | ST001 | `/workspaces/flow_squared/src/fs2/core/adapters/ast_languages/handler.py` | All ST001 tests pass; ABC has `language`, `is_container`, `extract_name`, `classify_node` | – | Base class |
| [ ] | ST003 | Write tests for handler registry | 2 | Test | ST002 | `/workspaces/flow_squared/tests/unit/adapters/test_language_handler.py` | Tests cover: get handler by language, default handler for unknown, register custom | – | TDD RED |
| [ ] | ST004 | Implement handler registry with auto-discovery | 2 | Core | ST003 | `/workspaces/flow_squared/src/fs2/core/adapters/ast_languages/__init__.py` | All ST003 tests pass; `get_handler(lang)` returns handler or default | – | Dict-based |
| [ ] | ST005 | Write tests for PythonHandler | 1 | Test | ST004 | `/workspaces/flow_squared/tests/unit/adapters/test_python_handler.py` | Tests cover: `is_container("block") -> True`, other types -> False | – | TDD RED |
| [ ] | ST006 | Implement PythonHandler | 1 | Core | ST005 | `/workspaces/flow_squared/src/fs2/core/adapters/ast_languages/python.py` | All ST005 tests pass; handles Python block container | – | First handler |
| [ ] | ST007 | Write tests for parser handler integration | 2 | Test | ST006 | `/workspaces/flow_squared/tests/unit/adapters/test_language_handler.py` | Tests cover: parser uses handler for container detection, parser fallback for unknown | – | TDD RED |
| [ ] | ST008 | Refactor TreeSitterParser to use handlers | 3 | Core | ST007 | `/workspaces/flow_squared/src/fs2/core/adapters/ast_parser_impl.py` | All ST007 tests pass; no inline `language ==` checks; handler delegation works | – | Remove violations |
| [ ] | ST009 | Verify no duplicate node_ids in codebase | 1 | Validation | ST008 | `/workspaces/flow_squared/scripts/scratch/diagnose_duplicate_nodeids.py` | Script reports 0 duplicates for src/ and tests/ | – | Final check |

---

## Alignment Brief

### Objective Recap
Implement Language Handler Strategy to produce unique node_ids, enabling hash-based smart content preservation (AC5/AC6) to work correctly across scans.

### Prior Phase Dependencies
- **Subtask 001**: Graph loading infrastructure is complete; node_id matching depends on stable IDs
- **Phase 6 T003**: SmartContentStage merge logic uses `prior_nodes[node.node_id]` lookup
- **001-universal-ast-parser**: Research findings on tree-sitter behavior

### Critical Findings Affecting This Subtask

| Finding | Constraint/Requirement | Tasks Affected |
|---------|------------------------|----------------|
| **CF08**: Tree-sitter `"block"` differs by language | Python: body wrapper; HCL: actual block | ST006 |
| **CF03**: Frozen Dataclass Immutability | Handlers return values, don't mutate | ST002 |
| **Clean Architecture**: No language-specific code in core | Use handler pattern, not inline checks | ST008 |
| **Investigation Finding**: ~13-15 nodes re-process each scan | Root cause is duplicate node_ids | ST009 |

### Invariants & Guardrails

- **Handler isolation**: Each handler in separate file under `ast_languages/`
- **Default behavior**: Unknown languages use `DefaultHandler` (all methods return None/False)
- **No breaking changes**: Existing node_id format preserved (`{category}:{path}:{qualified_name}`)
- **Test coverage**: Each handler has dedicated test file

### Inputs to Read

| File | Purpose |
|------|---------|
| `/workspaces/flow_squared/src/fs2/core/adapters/ast_parser_impl.py` | Current parser with inline language checks |
| `/workspaces/flow_squared/scripts/scratch/diagnose_reprocessing.py` | Diagnostic script from investigation |
| `/workspaces/flow_squared/scripts/scratch/find_all_duplicates.py` | Duplicate node_id finder |
| `/workspaces/flow_squared/initial_exploration/FINDINGS.md` | Tree-sitter research on node types |

### Visual Alignment Aids

#### Handler Pattern Architecture

```mermaid
flowchart TD
    subgraph Parser["TreeSitterParser"]
        Parse[parse method]
        Extract[_extract_nodes]
    end

    subgraph Registry["Handler Registry"]
        GetHandler[get_handler]
        Handlers[(handlers dict)]
    end

    subgraph Handlers["Language Handlers"]
        Default[DefaultHandler]
        Python[PythonHandler]
        Future[GoHandler...]
    end

    Parse --> Extract
    Extract --> GetHandler
    GetHandler --> Handlers
    Handlers --> Default
    Handlers --> Python
    Handlers -.-> Future

    style Python fill:#4CAF50,stroke:#388E3C,color:#fff
    style Default fill:#9E9E9E,stroke:#757575,color:#fff
    style Future fill:#F5F5F5,stroke:#E0E0E0,color:#757575
```

#### Handler Interface

```mermaid
classDiagram
    class LanguageHandler {
        <<abstract>>
        +language: str
        +is_container(ts_kind: str) bool
        +extract_name(node, content) str | None
        +classify_node(ts_kind: str) str | None
    }

    class DefaultHandler {
        +language = "default"
        +is_container() False
        +extract_name() None
        +classify_node() None
    }

    class PythonHandler {
        +language = "python"
        +is_container("block") True
    }

    LanguageHandler <|-- DefaultHandler
    LanguageHandler <|-- PythonHandler
```

### Test Plan (TDD)

#### ST001: LanguageHandler ABC Tests

| Test Name | Purpose | Expected Outcome |
|-----------|---------|------------------|
| `test_language_handler_abc_cannot_be_instantiated` | ABC enforcement | `TypeError` on instantiation |
| `test_language_handler_has_language_property` | Interface contract | `language` property defined |
| `test_language_handler_has_is_container_method` | Interface contract | `is_container(ts_kind)` method defined |
| `test_language_handler_has_extract_name_method` | Interface contract | `extract_name(node, content)` method defined |

#### ST003: Handler Registry Tests

| Test Name | Purpose | Expected Outcome |
|-----------|---------|------------------|
| `test_get_handler_returns_python_for_python` | Registration works | `PythonHandler` returned |
| `test_get_handler_returns_default_for_unknown` | Fallback works | `DefaultHandler` returned |
| `test_register_handler_adds_to_registry` | Custom registration | Handler accessible after registration |

#### ST005: PythonHandler Tests

| Test Name | Purpose | Expected Outcome |
|-----------|---------|------------------|
| `test_python_handler_is_container_block_true` | Python behavior | `is_container("block") -> True` |
| `test_python_handler_is_container_other_false` | Non-container | `is_container("function_definition") -> False` |

#### ST007: Parser Integration Tests

| Test Name | Purpose | Expected Outcome |
|-----------|---------|------------------|
| `test_parser_uses_handler_for_container_detection` | Integration | Handler's `is_container` called |
| `test_parser_python_block_not_extracted` | Behavior correct | Python `block` nodes skipped |
| `test_parser_other_language_block_extracted` | No regression | Non-Python `block` nodes extracted (if applicable) |

### Step-by-Step Implementation Outline

1. **ST001** (RED): Write failing tests for LanguageHandler ABC
2. **ST002** (GREEN): Implement LanguageHandler ABC with abstract methods
3. **ST003** (RED): Write failing tests for handler registry
4. **ST004** (GREEN): Implement registry with `get_handler()` function
5. **ST005** (RED): Write failing tests for PythonHandler
6. **ST006** (GREEN): Implement PythonHandler with `is_container("block") -> True`
7. **ST007** (RED): Write failing tests for parser integration
8. **ST008** (GREEN): Refactor parser to use handlers, remove inline checks
9. **ST009** (VERIFY): Run diagnostic script, confirm 0 duplicates

### Commands to Run

```bash
# Environment setup
cd /workspaces/flow_squared
uv sync

# Run subtask tests
uv run pytest tests/unit/adapters/test_language_handler.py -v
uv run pytest tests/unit/adapters/test_python_handler.py -v

# Run all parser tests (regression check)
uv run pytest tests/unit/adapters/test_ast_parser_impl.py -v

# Run diagnostic
python3 scripts/scratch/find_all_duplicates.py

# Verify smart content stability
uv run fs2 scan -v > /tmp/scan1.log 2>&1
uv run fs2 scan -v > /tmp/scan2.log 2>&1
diff <(grep "Smart content:" /tmp/scan1.log) <(grep "Smart content:" /tmp/scan2.log)
# Should show minimal/no differences

# Linting
uv run ruff check src/fs2/core/adapters/ast_languages/
```

### Risks/Unknowns

| Risk | Severity | Mitigation |
|------|----------|------------|
| Regression in other languages from handler refactor | Medium | Comprehensive test suite, run all parser tests |
| Handler overhead slows parsing | Low | Dict lookup is O(1); profile if concerns arise |
| More languages need handlers | Low | Pattern makes adding handlers easy; address as discovered |
| Some duplicates are legitimate (e.g., overloaded methods) | Medium | Accept some duplicates; document known cases |

### Ready Check

- [x] Current inline language checks identified (`language == "python"`, removed HCL)
- [x] Duplicate node_id diagnostic scripts exist
- [x] Clean Architecture principles understood (no language-specific code in core)
- [x] Tree-sitter research findings reviewed (FINDINGS.md)
- [x] Subtask 001 complete (graph loading infrastructure ready)
- [ ] Tests written (ST001, ST003, ST005, ST007)

**Awaiting GO/NO-GO from human sponsor before implementation.**

---

## Phase Footnote Stubs

_Populated by plan-6 after implementation. Each footnote links implementation evidence to tasks._

| Footnote | Node ID | Type | Tasks | Description |
|----------|---------|------|-------|-------------|
| | | | | |

_Reserved footnotes: [^36]-[^42] per plan ledger._

---

## Evidence Artifacts

| Artifact | Location | Purpose |
|----------|----------|---------|
| Execution Log | `./002-subtask-language-handler-strategy.execution.log.md` | Narrative record of implementation |
| Test Results | Console output | pytest results proving coverage |
| Duplicate Check | Scripts output | Verification of 0 duplicates |

---

## Discoveries & Learnings

_Populated during implementation by plan-6. Log anything of interest to your future self._

| Date | Task | Type | Discovery | Resolution | References |
|------|------|------|-----------|------------|------------|
| 2025-12-25 | Pre-work | insight | HCL blocks lack unique identifiers; removed from EXTRACTABLE_LANGUAGES | Treat HCL/Dockerfile as content blobs | ast_parser_impl.py:173-178 |
| 2025-12-25 | Pre-work | insight | Python `"block"` is body wrapper; other languages use it differently | Need handler strategy for language-specific behavior | ast_parser_impl.py:467 |
| 2025-12-25 | Pre-work | gotcha | C++ has 3x `EventEmitter.ListenerId` methods with same name | Legitimate overloading; accept some duplicates | find_all_duplicates.py output |

**Types**: `gotcha` | `research-needed` | `unexpected-behavior` | `workaround` | `decision` | `debt` | `insight`

_See also: `execution.log.md` for detailed narrative._

---

## After Subtask Completion

**This subtask resolves a blocker for:**
- Parent Tasks: [T003: SmartContentStage](./tasks.md#t003), [T005: ScanPipeline](./tasks.md#t005)
- Plan Tasks: [6.3, 6.5 in Plan](../../smart-content-plan.md#phase-6-scan-pipeline-integration)

**When all ST### tasks complete:**

1. **Record completion** in parent execution log:
   ```
   ### Subtask 002-subtask-language-handler-strategy Complete

   Resolved: Language Handler Strategy implemented. Python block handling
   isolated. Duplicate node_ids eliminated (except legitimate overloads).
   Smart content re-scanning reduced from ~35 to ~5 nodes per scan.
   See detailed log: [subtask execution log](./002-subtask-language-handler-strategy.execution.log.md)
   ```

2. **Update parent tasks** (if affected):
   - Open: [`tasks.md`](./tasks.md)
   - Find: T003, T005
   - Update Notes: Add "Subtask 002 complete - stable node_ids"

3. **Resume parent phase work:**
   ```bash
   /plan-6-implement-phase --phase "Phase 6: Scan Pipeline Integration" \
     --plan "/workspaces/flow_squared/docs/plans/008-smart-content/smart-content-plan.md"
   ```
   (Note: NO `--subtask` flag to resume main phase)

**Quick Links:**
- 📋 [Parent Dossier](./tasks.md)
- 📄 [Parent Plan](../../smart-content-plan.md)
- 📊 [Parent Execution Log](./execution.log.md)

---

## Directory Layout

```
docs/plans/008-smart-content/
├── smart-content-spec.md
├── smart-content-plan.md
└── tasks/
    └── phase-6-scan-pipeline-integration/
        ├── tasks.md
        ├── execution.log.md
        ├── 001-subtask-graph-loading-for-smart-content-preservation.md      # Complete
        ├── 001-subtask-graph-loading-for-smart-content-preservation.execution.log.md
        ├── 002-subtask-language-handler-strategy.md                          # This file
        └── 002-subtask-language-handler-strategy.execution.log.md            # Created by /plan-6

src/fs2/core/adapters/
├── ast_parser.py
├── ast_parser_impl.py
└── ast_languages/                    # NEW directory
    ├── __init__.py                   # Handler registry
    ├── handler.py                    # LanguageHandler ABC
    └── python.py                     # PythonHandler
```

---

**Subtask Status**: READY FOR IMPLEMENTATION
**Next Step**: Await GO from human sponsor, then run `/plan-6-implement-phase --subtask 002-subtask-language-handler-strategy`
