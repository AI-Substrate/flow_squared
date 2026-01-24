# Fix Tasks: Phase 8 Subtask 001 - Tree-Sitter Call Extraction

**Review**: `reviews/review.001-subtask-tree-sitter-call-extraction.md`
**Verdict**: REQUEST_CHANGES
**Generated**: 2026-01-24

---

## Required Fixes (Blocking)

### FIX-001: Add Footnote to Plan Ledger [HIGH]

**Issue**: LINK-001 - Subtask 001 completed but no footnote entry in plan ledger.

**File**: `/workspaces/flow_squared/docs/plans/025-lsp-research/lsp-integration-plan.md`

**Location**: After line 2053 (after [^20])

**Patch**:
```markdown
[^21]: Phase 8 Subtask 001 - Tree-Sitter Call Extraction (2026-01-24)
  - `function:src/fs2/core/services/stages/relationship_extraction_stage.py:extract_call_positions` - AST call position extraction
  - `function:src/fs2/core/services/stages/relationship_extraction_stage.py:_find_method_identifier` - Method name position helper
  - `function:src/fs2/core/services/stages/relationship_extraction_stage.py:is_stdlib_target` - Stdlib filtering
  - `file:tests/unit/services/stages/test_call_extraction.py` - 17 unit tests
  - `file:tests/integration/test_call_extraction_integration.py` - 3 integration tests
```

### FIX-002: Fix mypy Type Annotations [HIGH]

**Issue**: TYPE-001 through TYPE-004 - Missing type annotations cause mypy --strict to fail.

**File**: `/workspaces/flow_squared/src/fs2/core/services/stages/relationship_extraction_stage.py`

**Patch 1** (Line 118 - add type annotation to inner function):
```python
# Change:
def get_query_position(call_node) -> tuple[int, int]:

# To:
def get_query_position(call_node: "Node") -> tuple[int, int]:  # type: ignore[name-defined]
```

**Patch 2** (Line 148 - add type annotation to visit function):
```python
# Change:
def visit(node):

# To:
def visit(node: "Node") -> None:  # type: ignore[name-defined]
```

**Patch 3** (Line 162 - add return type annotation):
```python
# Change:
def _find_method_identifier(access_node, language: str):

# To:
def _find_method_identifier(access_node: "Node", language: str) -> "Node | None":  # type: ignore[name-defined]
```

**Patch 4** (Line 107 - handle dynamic language string):
```python
# Add type ignore comment to suppress strict type check for dynamic language string:
# Change:
parser = get_parser(language)

# To:
parser = get_parser(language)  # type: ignore[arg-type]
```

**Alternative for Patch 4** (if stricter typing desired):
```python
from typing import cast, Literal
from tree_sitter_language_pack import Language

# Create a type alias for supported languages
SupportedLanguage = Literal["python", "typescript", "javascript", "tsx", "go", "csharp"]

# In function:
if language not in CALL_NODE_TYPES:
    return []
parser = get_parser(cast(Language, language))
```

**Verification**:
```bash
uv run mypy src/fs2/core/services/stages/relationship_extraction_stage.py --strict
```

---

## Optional Fixes (Non-Blocking)

### FIX-003: Populate Phase Footnote Stubs [MEDIUM]

**Issue**: LINK-002 - Phase Footnote Stubs table in subtask dossier is empty.

**File**: `/workspaces/flow_squared/docs/plans/025-lsp-research/tasks/phase-8-pipeline-integration/001-subtask-tree-sitter-call-extraction.md`

**Location**: Around line 566 (Phase Footnote Stubs section)

**Patch**: Add row to table:
```markdown
| [^21] | 2026-01-24 | ST001-ST006 | Tree-Sitter call extraction implementation |
```

### FIX-004: Update ST003 Status in Execution Log [LOW]

**Issue**: TDD-001 - ST003 shows "In Progress" status but has completed timestamp.

**File**: `/workspaces/flow_squared/docs/plans/025-lsp-research/tasks/phase-8-pipeline-integration/001-subtask-tree-sitter-call-extraction.execution.log.md`

**Location**: ST003 section header

**Patch**: Change status emoji from "In Progress" to "Complete":
```markdown
# Change:
**Status**: 🔄 In Progress

# To:
**Status**: ✅ Complete
```

### FIX-005: Add ST001 Log Entry [LOW]

**Issue**: LOG-001 - ST001 has no explicit log entry.

**File**: `/workspaces/flow_squared/docs/plans/025-lsp-research/tasks/phase-8-pipeline-integration/001-subtask-tree-sitter-call-extraction.execution.log.md`

**Location**: Before ST002 section

**Patch**: Add section:
```markdown
## ST001: Document tree-sitter call node types per language

**Status**: ✅ Complete (Pre-existing research)
**Completed**: Prior to subtask execution

### Evidence

Research documented in:
- `/workspaces/flow_squared/docs/plans/025-lsp-research/tasks/phase-8-pipeline-integration/research/tree-sitter-call-nodes.md`

Key node types documented:
- Python: `call` → `attribute` for method access
- TypeScript/JS: `call_expression` → `member_expression`
- Go: `call_expression` → `selector_expression`
- C#: `invocation_expression` → `member_access_expression`
```

---

## Verification Commands

After applying fixes:

```bash
# 1. Verify mypy passes
uv run mypy src/fs2/core/services/stages/relationship_extraction_stage.py --strict

# 2. Verify tests still pass
uv run pytest tests/unit/services/stages/test_call_extraction.py tests/integration/test_call_extraction_integration.py -v --no-cov

# 3. Verify linting still passes
uv run ruff check src/fs2/core/services/stages/relationship_extraction_stage.py

# 4. Re-run code review
/plan-7-code-review --phase "Phase 8: Pipeline Integration" --plan "/workspaces/flow_squared/docs/plans/025-lsp-research/lsp-integration-plan.md" --subtask "001-subtask-tree-sitter-call-extraction"
```

---

## Fix Priority Order

1. **FIX-002** (mypy errors) - Code quality gate
2. **FIX-001** (footnote entry) - Graph integrity
3. **FIX-003** (footnote stubs) - Documentation completeness
4. **FIX-004, FIX-005** (log updates) - Cosmetic documentation
