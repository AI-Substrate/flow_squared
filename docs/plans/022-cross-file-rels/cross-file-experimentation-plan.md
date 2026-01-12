# Cross-File Relationship Experimentation Plan

**Plan Version**: 1.0.0
**Created**: 2026-01-12
**Spec**: [cross-file-experimentation-spec.md](/workspaces/flow_squared/docs/plans/022-cross-file-rels/cross-file-experimentation-spec.md)
**Status**: READY

> **Research Sources**: R1-xx references point to findings in [research-dossier.md](/workspaces/flow_squared/docs/plans/022-cross-file-rels/research-dossier.md). I1-xx references are implementation insights discovered during plan creation.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Technical Context](#technical-context)
3. [Critical Research Findings](#critical-research-findings)
4. [Testing Philosophy](#testing-philosophy)
5. [Phase 1: Setup & Fixture Audit](#phase-1-setup--fixture-audit)
6. [Phase 2: Core Extraction Scripts](#phase-2-core-extraction-scripts)
7. [Phase 3: Fixture Enrichment & Validation](#phase-3-fixture-enrichment--validation)
8. [Phase 4: Documentation & Dossier](#phase-4-documentation--dossier)
9. [Cross-Cutting Concerns](#cross-cutting-concerns)
10. [Complexity Tracking](#complexity-tracking)
11. [Progress Tracking](#progress-tracking)
12. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

### Problem Statement

Before implementing cross-file relationship detection in fs2, we need to validate that Tree-sitter-based extraction works reliably across multiple languages and reference types. The current test fixtures have zero cross-file relationships, and confidence scoring heuristics are untested.

### Solution Approach

- Create experimental scripts in `scripts/cross-files-rels-research/` to test Tree-sitter parsing
- Enrich test fixtures with deliberate cross-file relationships
- Validate confidence scoring tiers (1.0 → 0.1) against ground truth
- Document findings, edge cases, and recommendations in experimentation dossier

### Expected Outcomes

- Validated Tree-sitter queries for Python, TypeScript, Go
- Enriched fixtures with cross-file imports, calls, and references
- Documented edge cases and language-specific quirks
- Confidence scoring calibration based on real data
- Recommendations for implementation approach

### Success Metrics

- All 5 experiment scripts (01-05) run successfully, plus setup script (00)
- At least 3 language pairs have validated cross-file relationships
- Precision/recall metrics documented for each extraction technique
- Experimentation dossier complete with actionable recommendations

---

## Technical Context

### Current System State

- **Test fixtures**: 21 files across 15 languages in `tests/fixtures/samples/`
- **Cross-file imports**: None (all fixtures import only standard library)
- **Graph infrastructure**: NetworkX DiGraph ready for edge attributes
- **Confidence scoring**: Pattern established in `ChunkMatch` (0.0-1.0)

### Integration Requirements

- `tree-sitter` and `tree-sitter-language-pack` pip packages (scratch only)
- Existing fixture files remain functional
- No production code changes

### Constraints and Limitations

- Experimentation only - no GraphStore modifications
- No new dependencies in `pyproject.toml`
- Scratch scripts are throwaway (not production quality)
- Focus on top 5 languages: Python, TypeScript, Go, Rust, Java

### Assumptions

- Tree-sitter Python bindings work as documented
- `tree-sitter-language-pack` includes all needed grammars
- Fixture enrichment is straightforward
- Scratch scripts don't need formal tests

---

## Critical Research Findings

### Finding 01: Markdown Code Blocks Create False Positives
**Impact**: Critical
**Sources**: [R1-06]
**Problem**: Markdown files contain code examples that are NOT actual imports. Parsing these as real code creates thousands of false edges.
**Example**:
```markdown
<!-- README.md line 116 - this is DOCUMENTATION, not a real import -->
import { useAuth } from '@/hooks/useAuth';
```
**Solution**: Skip markdown code blocks entirely OR assign confidence 0.1 (fuzzy reference only). Test node_id pattern detection separately from code extraction.
**Affects Phases**: Phase 2 (node_id detection), Phase 3 (fixture enrichment)

---

### Finding 02: TypeScript Type-Only Imports Create False Positives
**Impact**: Critical
**Sources**: [R1-02]
**Problem**: React/TypeScript codebases use `import type` statements that don't create runtime dependencies. Tree-sitter may extract these as regular imports.
**Example**:
```typescript
// ❌ WRONG - treating type import as runtime dependency
import type { AppConfig } from "./app";  // Should be confidence 0.5, not 0.9

// ✅ CORRECT - differentiate import types
import { Application } from "./app";     // Runtime import: confidence 0.9
import type { AppConfig } from "./app";  // Type-only: confidence 0.5
```
**Solution**: Differentiate `import type` from regular imports in Tree-sitter query. Create fixtures testing both.
**Affects Phases**: Phase 2 (import extraction), Phase 3 (TypeScript fixture)

---

### Finding 03: Method Call Confidence Is Too Optimistic
**Impact**: Critical
**Sources**: [R1-07, I1-06]
**Problem**: Research dossier shows 0.5-0.6 confidence for method calls, but without type information, resolution is unreliable. Chained calls reduce confidence exponentially.
**Example**:
```python
# Fixture: auth_handler.py line 105
self._validate_credentials(username, password)  # Internal method - confidence 0.8

# Fixture: server.go line 118
json.NewEncoder(w).Encode(...)  # Chained call - each link reduces confidence

# Fixture: UserService.java line 136
cacheManager.get("user:" + id, User.class)  # Injected dependency - confidence 0.3
```
**Solution**: Downgrade confidence estimates: 0.8 for self-calls, 0.6 for typed receiver, 0.3 for inference required. Start with constructor calls only.
**Affects Phases**: Phase 2 (call extraction), Phase 3 (validation)

---

### Finding 04: Python Function-Scoped Imports Are Hidden
**Impact**: High
**Sources**: [R1-01]
**Problem**: Python allows imports inside functions, which Tree-sitter will find but may be missed by naive top-of-file scanning.
**Example**:
```python
# Fixture: auth_handler.py line 174 - HIDDEN inside method
def _create_token(self, user_id: str, role: AuthRole) -> AuthToken:
    import uuid  # Function-scoped import
    token_id = str(uuid.uuid4())
```
**Solution**: Tree-sitter queries find all `import_statement` nodes regardless of nesting. Assign confidence 0.6 for function-scoped (may not be called).
**Affects Phases**: Phase 2 (import extraction)

---

### Finding 05: Go Dot and Blank Imports Need Special Handling
**Impact**: High
**Sources**: [R1-03]
**Problem**: Go's dot imports (`. "fmt"`) import symbols directly into namespace, and blank imports (`_ "driver"`) are for side effects only. Research dossier query handles aliases but not these variants.
**Example**:
```go
// ❌ WRONG - query misses dot import
import . "fmt"  // Imports Printf, Println, etc. directly into namespace

// ❌ WRONG - blank import treated as regular import
import _ "database/sql/driver"  // Side effects only, no symbols used
```
**Solution**: Extend Tree-sitter query to capture dot/blank imports. Confidence: 0.7 for aliases, 0.4 for dot imports, 0.3 for blank imports.
**Affects Phases**: Phase 2 (import extraction)

---

### Finding 06: Phase Execution Order Should Be Revised
**Impact**: High
**Sources**: [I1-01]
**Problem**: Spec defines fixtures first, then scripts. But scripts need to be tested against known-good stdlib imports before validating new fixtures.
**Recommended Order**:
1. Phase 1: Setup + Audit (unchanged)
2. **Phase 2: Core Extraction Scripts** (moved up) - Validate against stdlib imports first
3. **Phase 3: Fixture Enrichment** (moved down) - Use validated scripts to guide fixture creation
4. Phase 4: Documentation (unchanged)
**Solution**: Create extraction scripts that work on stdlib imports first, then use those to validate enriched fixtures.
**Affects Phases**: All phases (reordered)

---

### Finding 07: Modular Script Architecture Enables Reuse
**Impact**: High
**Sources**: [I1-03, I1-05]
**Problem**: Monolithic experiment scripts duplicate code. Query patterns need to be tested independently from extraction logic.
**Solution**: Create shared `lib/` modules:
```
/workspaces/flow_squared/scripts/cross-files-rels-research/
├── lib/
│   ├── __init__.py     # Package marker
│   ├── parser.py       # Tree-sitter initialization (~50 LOC)
│   ├── extractors.py   # Language-specific extractors (~100 LOC)
│   ├── queries.py      # Query registry per language (~80 LOC)
│   └── resolver.py     # Confidence scoring (~60 LOC)
├── experiments/        # Individual experiment scripts
│   ├── 00_verify_setup.py
│   ├── 01_nodeid_detection.py
│   ├── 02_import_extraction.py
│   ├── 03_call_extraction.py
│   ├── 04_cross_lang_refs.py
│   └── 05_confidence_scoring.py
└── results/            # JSON output from experiments
```
**Affects Phases**: Phase 2 (script structure)

---

### Finding 08: Ground Truth Reference Table Enables Validation
**Impact**: High
**Sources**: [I1-04]
**Problem**: Without known expected relationships, can't measure precision/recall.
**Solution**: Define ground truth BEFORE creating fixtures with explicit schema:
```python
from dataclasses import dataclass
from typing import Literal, Optional

@dataclass
class ExpectedRelation:
    source_file: str           # e.g., "app_service.py"
    target_file: str           # e.g., "auth_handler.py"
    target_symbol: Optional[str]  # e.g., "AuthHandler.validate_token" or None for file-level
    rel_type: Literal["IMPORTS", "CALLS", "REFERENCES", "INHERITS"]
    expected_confidence: float  # 0.0-1.0

GROUND_TRUTH: list[ExpectedRelation] = [
    ExpectedRelation("app_service.py", "auth_handler.py", None, "IMPORTS", 0.9),
    ExpectedRelation("app_service.py", "auth_handler.py", "AuthHandler.__init__", "CALLS", 0.8),
    ExpectedRelation("app_service.py", "auth_handler.py", "AuthHandler.validate_token", "CALLS", 0.7),
    ExpectedRelation("execution-log.md", "auth_handler.py", "AuthHandler.authenticate", "REFERENCES", 1.0),
    # ... more entries populated in Phase 1
]
```
**Affects Phases**: Phase 1 (define ground truth), Phase 3 (validation)

---

### Finding 09: Confidence Pyramid Guides Fixture Creation
**Impact**: Medium
**Sources**: [I1-02]
**Problem**: Creating all fixtures at once makes debugging difficult.
**Solution**: Create fixtures in confidence order (highest first):
1. **Confidence 1.0**: Node IDs in markdown (simplest, regex-based)
2. **Confidence 0.9**: Explicit imports (Tree-sitter, well-tested)
3. **Confidence 0.7-0.8**: Constructor patterns (type inference)
4. **Confidence 0.5-0.6**: Method calls (receiver tracking)
5. **Confidence 0.1-0.3**: Fuzzy name matches (hardest)
**Affects Phases**: Phase 3 (fixture creation order)

---

### Finding 10: Node ID Delimiter Ambiguity in Logs
**Impact**: Medium
**Sources**: [R1-08]
**Problem**: Node IDs contain colons that conflict with log timestamps and YAML syntax.
**Example**:
```
2026-01-12 10:30:45: callable:src/calc.py:Calculator.add  # Timestamp colon collision
```
**Solution**: Use strict regex with word boundaries: `\b(file|callable|type):[\w./]+:[\w.]+\b`. Validate captured IDs against graph before creating edges.
**Affects Phases**: Phase 2 (node_id detection)

---

## Testing Philosophy

### Testing Approach

**Selected Approach**: Lightweight
**Rationale**: Experimentation scripts are throwaway; formal tests unnecessary.

**Focus Areas**:
- Scripts run without errors
- Scripts produce expected output types
- Console output demonstrates extraction works

**Excluded**:
- Unit tests for scratch scripts
- Integration tests
- Test coverage requirements

### Validation Strategy

Each experiment script validates against ground truth:
```python
def validate_extraction(extracted, ground_truth):
    tp = len([e for e in extracted if e in ground_truth])
    fp = len([e for e in extracted if e not in ground_truth])
    fn = len([e for e in ground_truth if e not in extracted])
    return {"precision": tp/(tp+fp), "recall": tp/(tp+fn)}
```

### Mock Usage

N/A - Experimentation uses real fixture files, no mocking needed.

---

## Phase 1: Setup & Fixture Audit

**Objective**: Establish scratch environment and document current fixture state.

**Deliverables**:
- `scripts/cross-files-rels-research/` directory structure
- Tree-sitter packages installed in scratch venv
- Fixture audit table documenting current state
- Ground truth reference table (empty, to be populated)

**Dependencies**: None (foundational phase)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Tree-sitter install fails | Low | High | Use pre-built wheels from PyPI |
| Language pack missing grammar | Low | Medium | Document and work around |

### Tasks (Lightweight Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 1.1 | [ ] | Create scratch directory structure | 1 | Directories exist. **Verify**: `ls -la /workspaces/flow_squared/scripts/cross-files-rels-research/{lib,experiments,results}/` | - | Creates `/workspaces/flow_squared/scripts/cross-files-rels-research/` |
| 1.2 | [ ] | Create scratch venv with tree-sitter | 1 | **Commands**: `cd /workspaces/flow_squared/scripts/cross-files-rels-research && python -m venv .venv && source .venv/bin/activate && pip install tree-sitter tree-sitter-language-pack` | - | Isolated from main project |
| 1.3 | [ ] | Verify tree-sitter works | 1 | **Command**: `cd /workspaces/flow_squared/scripts/cross-files-rels-research && source .venv/bin/activate && python experiments/00_verify_setup.py`. Parses Python file, prints AST nodes | - | Creates `experiments/00_verify_setup.py` |
| 1.4 | [ ] | Audit all 21 fixture files | 2 | Table showing: file, language, imports, cross-file refs. **Files**: `find /workspaces/flow_squared/tests/fixtures/samples -type f \| wc -l` = 21. Also audit which tests depend on fixture count/structure. | - | Expect: zero cross-file refs |
| 1.5 | [ ] | Create ground truth template | 1 | `lib/ground_truth.py` with `ExpectedRelation` dataclass and empty `GROUND_TRUTH` list per Finding 08 schema | - | |
| 1.6 | [ ] | Document fixture gaps | 1 | List of missing fixture types per language (e.g., Go needs handlers.go importing server.go) | - | |

### Acceptance Criteria

- [ ] All experiment scripts can `import lib.parser` successfully
- [ ] Tree-sitter can parse Python, TypeScript, Go, Rust, Java, C files
- [ ] Audit table documents all 21 fixtures with import analysis
- [ ] Ground truth template ready for population

---

## Phase 2: Core Extraction Scripts

**Objective**: Create and validate extraction scripts against stdlib imports before enriching fixtures.

**Deliverables**:
- Shared `lib/` modules (parser, queries, extractors, resolver)
- 4 experiment scripts testing different extraction techniques
- Validation output showing extraction works on existing fixtures

**Dependencies**: Phase 1 complete (scratch environment working)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Query syntax differs per language | Medium | Medium | Start with Python, document patterns |
| Tree-sitter API changes | Low | High | Pin version in scratch venv |

### Tasks (Lightweight Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 2.1 | [ ] | Create `lib/parser.py` (~50 LOC) | 2 | Load tree-sitter, parse files, cache trees. File at `/workspaces/flow_squared/scripts/cross-files-rels-research/lib/parser.py` | - | Shared infrastructure |
| 2.2 | [ ] | Create `lib/queries.py` (~80 LOC) | 2 | Query registry for Python, TS, Go imports including dot/blank imports per Finding 05 | - | Include `import type` handling per Finding 02 |
| 2.3 | [ ] | Create `experiments/01_nodeid_detection.py` (~60 LOC) | 2 | Extract fs2 node_ids from text files via regex per Finding 10 | - | Confidence 1.0 tier |
| 2.4 | [ ] | Create `experiments/02_import_extraction.py` (~100 LOC) | 3 | Extract imports from Python, TS, Go using Tree-sitter. Validate against stdlib imports in existing fixtures | - | Handles function-scoped imports per Finding 04 |
| 2.5 | [ ] | Create `lib/extractors.py` (~100 LOC) | 2 | Reusable extractors for imports, calls. Returns `list[dict]` with confidence scores | - | Called by experiments |
| 2.6 | [ ] | Create `experiments/03_call_extraction.py` (~80 LOC) | 3 | Extract function/method calls with receiver tracking. Start with constructor patterns only per Finding 03 | - | Downgraded confidence: 0.8 self-calls, 0.6 typed, 0.3 inferred |
| 2.7 | [ ] | Create `lib/resolver.py` (~60 LOC) | 2 | Confidence scoring logic per Finding 03 tiers | - | Tiered heuristics |
| 2.8 | [ ] | Run all scripts on existing fixtures | 1 | **Commands**: `cd /workspaces/flow_squared/scripts/cross-files-rels-research && source .venv/bin/activate && python experiments/01_nodeid_detection.py /workspaces/flow_squared/tests/fixtures/samples/ && python experiments/02_import_extraction.py /workspaces/flow_squared/tests/fixtures/samples/ && python experiments/03_call_extraction.py /workspaces/flow_squared/tests/fixtures/samples/`. JSON output in `results/` | - | Stdlib imports detected |

### Script Structure Reference

**`/workspaces/flow_squared/scripts/cross-files-rels-research/lib/parser.py`** (~50 LOC):
```python
# /workspaces/flow_squared/scripts/cross-files-rels-research/lib/parser.py
from pathlib import Path
from tree_sitter_language_pack import get_parser, get_language

def parse_file(file_path: Path, language: str) -> "Tree":
    """Parse file and return Tree-sitter AST."""
    parser = get_parser(language)
    return parser.parse(file_path.read_bytes())

def detect_language(file_path: Path) -> str:
    """Detect language from file extension."""
    LANG_MAP = {".py": "python", ".ts": "typescript", ".tsx": "tsx", ".go": "go", ".rs": "rust", ".java": "java"}
    return LANG_MAP.get(file_path.suffix, "unknown")
```

**`/workspaces/flow_squared/scripts/cross-files-rels-research/lib/queries.py`** (~80 LOC):
```python
# /workspaces/flow_squared/scripts/cross-files-rels-research/lib/queries.py
IMPORT_QUERIES = {
    "python": """
        (import_statement name: (dotted_name) @import.module)
        (import_from_statement module_name: (dotted_name) @import.from)
    """,
    "typescript": """
        (import_statement source: (string) @import.source)
        ; Differentiate type-only imports per Finding 02
        (import_statement "type" source: (string) @import.type_only)
    """,
    "go": """
        (import_declaration (import_spec path: (_) @import.path))
        ; Handle dot imports per Finding 05: import . "fmt"
        (import_declaration (import_spec name: (dot) path: (_) @import.dot))
        ; Handle blank imports per Finding 05: import _ "driver"
        (import_declaration (import_spec name: (blank_identifier) path: (_) @import.blank))
    """,
}
```

### Acceptance Criteria

- [ ] All 4 experiment scripts run without errors
- [ ] Node ID detection extracts patterns from README.md code blocks (as examples)
- [ ] Import extraction finds stdlib imports in all Python fixtures
- [ ] Call extraction identifies method calls with receivers
- [ ] Confidence scoring assigns correct tiers

---

## Phase 3: Fixture Enrichment & Validation

**Objective**: Create fixtures with deliberate cross-file relationships and validate extraction accuracy.

**Deliverables**:
- 3 new fixture files with cross-file imports
- Updated markdown fixtures with node_id references
- Ground truth populated with expected relationships
- Precision/recall metrics for each extraction technique

**Dependencies**: Phase 2 complete (extraction scripts validated)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Fixtures break existing tests | Low | High | Run `pytest` after each change |
| Resolution ambiguity | Medium | Medium | Document as edge case |

### Tasks (Lightweight Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 3.1 | [ ] | Create `/workspaces/flow_squared/tests/fixtures/samples/python/app_service.py` | 2 | Imports from `auth_handler.py`, `data_parser.py`. Syntactically valid Python. | - | See spec for content |
| 3.2 | [ ] | Create `/workspaces/flow_squared/tests/fixtures/samples/javascript/index.ts` | 2 | Imports from `app.ts`, `utils.js`, `component.tsx`. Note: verify these files exist or create stubs. | - | TypeScript cross-file |
| 3.3 | [ ] | Create `/workspaces/flow_squared/tests/fixtures/samples/markdown/execution-log.md` | 1 | Contains fs2 node_id patterns in format `callable:path:Symbol.method` | - | Confidence 1.0 test |
| 3.4 | [ ] | Update `/workspaces/flow_squared/tests/fixtures/samples/markdown/README.md` | 2 | References `auth_handler.py`, method names like `AuthHandler.validate_token()` | - | Multiple confidence tiers |
| 3.5 | [ ] | Populate ground truth with expected relationships | 2 | `/workspaces/flow_squared/scripts/cross-files-rels-research/lib/ground_truth.py` complete with 10+ entries | - | Per Finding 08 schema |
| 3.6 | [ ] | Create `experiments/04_cross_lang_refs.py` (~70 LOC) | 2 | Detects cross-language refs in existing YAML/Dockerfile fixtures OR markdown referencing code. Uses regex for `COPY`/`CMD` patterns. | - | Uses existing `/workspaces/flow_squared/tests/fixtures/samples/docker/Dockerfile` and `/workspaces/flow_squared/tests/fixtures/samples/yaml/deployment.yaml` |
| 3.7 | [ ] | Create `experiments/05_confidence_scoring.py` (~80 LOC) | 2 | Validate scoring against ground truth. Outputs precision/recall per confidence tier. | - | Precision/recall output |
| 3.8 | [ ] | Run all experiments on enriched fixtures | 1 | **Commands**: `cd /workspaces/flow_squared/scripts/cross-files-rels-research && source .venv/bin/activate && for exp in experiments/0*.py; do python "$exp" /workspaces/flow_squared/tests/fixtures/samples/ > "results/$(basename $exp .py).json"; done`. All JSON results in `results/` | - | JSON output |
| 3.9 | [ ] | Verify pytest still passes | 1 | **Command**: `cd /workspaces/flow_squared && pytest tests/ -v`. Exit code 0, no failures. | - | No regressions |

### New Fixture Content

**`/workspaces/flow_squared/tests/fixtures/samples/python/app_service.py`**:
```python
"""Application service orchestrating auth and parsing."""
from auth_handler import AuthHandler, AuthToken, AuthRole
from data_parser import JSONParser, ParseResult

class AppService:
    auth: AuthHandler
    parser: JSONParser

    def __init__(self):
        self.auth = AuthHandler()
        self.parser = JSONParser()

    async def process_request(self, token_id: str, data: str) -> ParseResult:
        token = await self.auth.validate_token(token_id)
        if token.is_expired:
            raise ValueError("Token expired")
        return self.parser.parse(data)
```

**`/workspaces/flow_squared/tests/fixtures/samples/markdown/execution-log.md`**:
```markdown
# Execution Log - 2026-01-12

## Nodes Called
- `callable:tests/fixtures/samples/python/auth_handler.py:AuthHandler.authenticate`
- `callable:tests/fixtures/samples/python/auth_handler.py:AuthHandler.validate_token`
- `callable:tests/fixtures/samples/python/data_parser.py:JSONParser.parse`

## Files Modified
- `file:tests/fixtures/samples/python/auth_handler.py`
- `file:tests/fixtures/samples/python/data_parser.py`
```

### Acceptance Criteria

- [ ] All 3 new fixture files created and syntactically valid
- [ ] Ground truth contains 10+ expected relationships
- [ ] Node ID detection achieves 100% precision/recall on execution-log.md
- [ ] Import extraction achieves >90% precision on app_service.py
- [ ] Confidence scoring matches expected tiers (±0.1)
- [ ] `pytest tests/` passes after fixture changes

---

## Phase 4: Documentation & Dossier

**Objective**: Document all findings in experimentation dossier for implementation reference.

**Deliverables**:
- `docs/plans/022-cross-file-rels/experimentation-dossier.md`
- Summary of what worked and what didn't
- Edge cases and limitations
- Recommendations for implementation

**Dependencies**: Phase 3 complete (all experiments run, metrics captured)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Missing edge cases | Medium | Medium | Review all experiment output |

### Tasks (Lightweight Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 4.1 | [ ] | Run all 5 experiments and capture output | 1 | **Commands**: `cd /workspaces/flow_squared/scripts/cross-files-rels-research && source .venv/bin/activate && python experiments/01_nodeid_detection.py /workspaces/flow_squared/tests/fixtures/samples/ > results/01_nodeid.json && python experiments/02_import_extraction.py /workspaces/flow_squared/tests/fixtures/samples/ > results/02_imports.json && python experiments/03_call_extraction.py /workspaces/flow_squared/tests/fixtures/samples/ > results/03_calls.json && python experiments/04_cross_lang_refs.py /workspaces/flow_squared/tests/fixtures/samples/ > results/04_crosslang.json && python experiments/05_confidence_scoring.py /workspaces/flow_squared/tests/fixtures/samples/ > results/05_scoring.json`. All 5 JSON files in `results/` | - | |
| 4.2 | [ ] | Analyze results for patterns | 2 | Document common failures, edge cases in scratch notes | - | |
| 4.3 | [ ] | Write Executive Summary | 1 | Key findings in 2-3 sentences | - | |
| 4.4 | [ ] | Write Experiment Results sections | 2 | One section per experiment (5 total) with precision/recall metrics | - | |
| 4.5 | [ ] | Write Edge Cases & Limitations | 2 | All discovered edge cases documented. Reference research-dossier.md findings R1-01 through R1-08 | - | Link: `/workspaces/flow_squared/docs/plans/022-cross-file-rels/research-dossier.md` |
| 4.6 | [ ] | Write Recommendations section | 2 | Actionable guidance for implementation with priority ranking | - | |
| 4.7 | [ ] | Create experimentation dossier | 1 | Complete markdown document at `/workspaces/flow_squared/docs/plans/022-cross-file-rels/experimentation-dossier.md` | - | Self-contained, no assumed context |

### Dossier Structure

```markdown
# Experimentation Dossier: Cross-File Relationships

## Executive Summary
[2-3 sentences: what we learned, key recommendations]

## Experiment Results

### 1. Tree-sitter Setup
- Languages verified: [Python, TypeScript, Go, ...]
- Installation: [success/issues]

### 2. Node ID Detection
- Pattern: [regex used]
- Precision: [%]
- Recall: [%]
- False positives: [examples]

### 3. Import Extraction
- Python: [precision/recall, edge cases]
- TypeScript: [precision/recall, type-only imports]
- Go: [precision/recall, dot imports]

### 4. Call Extraction
- Constructor patterns: [precision/recall]
- Method calls: [precision/recall, confidence calibration]
- Type inference: [what worked, what didn't]

### 5. Cross-Language References
- Dockerfile → Python: [findings]
- YAML → Python: [findings]
- Markdown → Code: [findings, code block handling]

### 6. Confidence Scoring Validation
- Tier accuracy: [table of expected vs actual]
- Recommended adjustments: [calibration changes]

## Edge Cases & Limitations
[Comprehensive list with examples]

## Recommendations for Implementation
1. [Recommendation 1]
2. [Recommendation 2]
3. [Recommendation 3]

## Next Steps
- [Action items for implementation phase]
```

### Acceptance Criteria

- [ ] All 6 experiment results documented with metrics
- [ ] Edge cases from R1-01 through R1-08 addressed
- [ ] Confidence scoring calibration documented
- [ ] Clear recommendations for implementation
- [ ] Dossier is self-contained (no assumed context)

---

## Cross-Cutting Concerns

### Security Considerations

- Scratch scripts are local-only (no network access)
- No credentials or secrets in fixtures
- Node ID patterns don't expose sensitive paths

### Observability

- Each experiment outputs JSON to `/workspaces/flow_squared/scripts/cross-files-rels-research/results/`
- Console output shows progress and summary
- Errors logged with context for debugging

### Documentation

- **Location**: `/workspaces/flow_squared/docs/plans/022-cross-file-rels/experimentation-dossier.md`
- **Target Audience**: Development team (future implementation reference)
- **Maintenance**: One-time research artifact (no ongoing updates)

---

## Complexity Tracking

| Component | CS | Label | Breakdown (S,I,D,N,F,T) | Justification | Mitigation |
|-----------|-----|-------|-------------------------|---------------|------------|
| Tree-sitter queries | 2 | Small | S=1,I=1,D=0,N=0,F=0,T=0 | Per-language query syntax | Document patterns |
| Method call resolution | 3 | Medium | S=1,I=0,D=0,N=2,F=0,T=0 | Type inference is novel | Start with constructors |
| Cross-language refs | 2 | Small | S=1,I=0,D=0,N=1,F=0,T=0 | Dockerfile parsing new | Regex-based fallback |

**Overall Complexity**: CS-2 (small) - Experimentation with known tools

---

## Progress Tracking

### Phase Completion Checklist

- [ ] Phase 1: Setup & Fixture Audit - NOT STARTED
- [ ] Phase 2: Core Extraction Scripts - NOT STARTED
- [ ] Phase 3: Fixture Enrichment & Validation - NOT STARTED
- [ ] Phase 4: Documentation & Dossier - NOT STARTED

### STOP Rule

**IMPORTANT**: This plan must be complete before creating tasks. After writing this plan:
1. Run `/plan-4-complete-the-plan` to validate readiness
2. Only proceed to `/plan-5-phase-tasks-and-brief` after validation passes

---

## Change Footnotes Ledger

**NOTE**: This section will be populated during implementation by plan-6a-update-progress.

[^1]: [To be added during implementation via plan-6a]
[^2]: [To be added during implementation via plan-6a]

---

**Plan Complete**: 2026-01-12
**Next Step**: Run `/plan-4-complete-the-plan` to validate readiness
