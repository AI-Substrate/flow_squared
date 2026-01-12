# Phase 3: Fixture Enrichment & Validation – Tasks & Alignment Brief

**Spec**: [cross-file-experimentation-spec.md](/workspaces/flow_squared/docs/plans/022-cross-file-rels/cross-file-experimentation-spec.md)
**Plan**: [cross-file-experimentation-plan.md](/workspaces/flow_squared/docs/plans/022-cross-file-rels/cross-file-experimentation-plan.md)
**Phase Slug**: `phase-3-fixture-enrichment-validation`
**Date**: 2026-01-12

---

## Executive Briefing

### Purpose
This phase creates test fixtures with deliberate cross-file relationships and validates that the extraction scripts built in Phase 2 can accurately detect them. Without enriched fixtures, we cannot measure precision/recall of our extraction techniques.

### What We're Building
A set of interconnected fixture files that create a realistic dependency graph:
- **Python orchestrator** (`app_service.py`) that imports from and calls existing `auth_handler.py` and `data_parser.py`
- **TypeScript aggregator** (`index.ts`) that imports from existing JS/TS fixtures
- **Markdown fixtures** with explicit fs2 node_id references (confidence 1.0)
- **Ground truth data** mapping all expected relationships with confidence scores
- **Two remaining experiment scripts** (04, 05) for cross-language refs and validation

### User Value
After this phase, we can measure actual precision/recall metrics for each extraction technique. This enables data-driven decisions about which techniques to implement in fs2 production code.

### Example
**Before Phase 3**: Extraction scripts find stdlib imports but can't validate cross-file detection accuracy
**After Phase 3**:
```
Ground Truth: app_service.py IMPORTS auth_handler.py (confidence 0.9)
Extracted:    app_service.py IMPORTS auth_handler.py (confidence 0.9)
Result:       TRUE POSITIVE - Precision/Recall validated
```

---

## Objectives & Scope

### Objective
Create enriched fixtures with known cross-file relationships and validate extraction accuracy against ground truth.

**Acceptance Criteria** (from plan):
- [ ] All 3 new fixture files created and syntactically valid
- [ ] Ground truth contains 10+ expected relationships
- [ ] Node ID detection achieves 100% precision/recall on execution-log.md
- [ ] Import extraction achieves >90% precision on app_service.py
- [ ] Confidence scoring matches expected tiers (±0.1)
- [ ] `pytest tests/` passes after fixture changes

### Goals

- ✅ Create `app_service.py` with cross-file Python imports
- ✅ Create `index.ts` with cross-file TypeScript imports
- ✅ Create markdown fixtures with node_id references
- ✅ Populate `GROUND_TRUTH` with 10+ expected relationships
- ✅ Create `04_cross_lang_refs.py` for Dockerfile/YAML analysis
- ✅ Create `05_confidence_scoring.py` for validation metrics
- ✅ Run all experiments and capture precision/recall
- ✅ Verify no test regressions

### Non-Goals (Scope Boundaries)

- ❌ Modifying extraction logic in `lib/` modules (Phase 2 deliverables are frozen)
- ❌ Adding Go or Rust cross-file fixtures (focus on Python, TypeScript)
- ❌ Creating complex inheritance hierarchies (simple imports/calls only)
- ❌ Handling dynamic imports or lazy loading patterns
- ❌ Parsing non-fixture directories (only `tests/fixtures/samples/`)
- ❌ Full precision/recall for all languages (focus on Python, TypeScript, Go per plan)

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

    style Phase fill:#F5F5F5,stroke:#E0E0E0
    style NewFixtures fill:#E3F2FD,stroke:#1976D2
    style ExistingFixtures fill:#E8F5E9,stroke:#388E3C
    style Experiments fill:#FFF3E0,stroke:#E65100
    style GroundTruth fill:#F3E5F5,stroke:#7B1FA2

    subgraph Phase["Phase 3: Fixture Enrichment & Validation"]
        T001["T001: Create app_service.py"]:::pending
        T002["T002: Create index.ts"]:::pending
        T003["T003: Create execution-log.md"]:::pending
        T004["T004: Update README.md"]:::pending
        T005["T005: Populate ground truth"]:::pending
        T006["T006: Create 04_cross_lang_refs.py"]:::pending
        T007["T007: Create 05_confidence_scoring.py"]:::pending
        T008["T008: Run all experiments"]:::pending
        T009["T009: Verify pytest passes"]:::pending

        T001 --> T005
        T002 --> T005
        T003 --> T005
        T004 --> T005
        T005 --> T007
        T006 --> T008
        T007 --> T008
        T008 --> T009
    end

    subgraph NewFixtures["New Fixtures (Phase 3)"]
        F1["/tests/fixtures/samples/python/app_service.py"]:::pending
        F2["/tests/fixtures/samples/javascript/index.ts"]:::pending
        F3["/tests/fixtures/samples/markdown/execution-log.md"]:::pending
        F4["/tests/fixtures/samples/markdown/README.md"]:::pending
    end

    subgraph ExistingFixtures["Existing Fixtures (Phase 1)"]
        EF1["/tests/fixtures/samples/python/auth_handler.py"]:::completed
        EF2["/tests/fixtures/samples/python/data_parser.py"]:::completed
        EF3["/tests/fixtures/samples/javascript/app.ts"]:::completed
        EF4["/tests/fixtures/samples/javascript/utils.js"]:::completed
        EF5["/tests/fixtures/samples/javascript/component.tsx"]:::completed
    end

    subgraph GroundTruth["Ground Truth"]
        GT["/scripts/.../lib/ground_truth.py"]:::pending
    end

    subgraph Experiments["Experiment Scripts"]
        E4["/scripts/.../experiments/04_cross_lang_refs.py"]:::pending
        E5["/scripts/.../experiments/05_confidence_scoring.py"]:::pending
    end

    T001 -.-> F1
    T002 -.-> F2
    T003 -.-> F3
    T004 -.-> F4
    T005 -.-> GT
    T006 -.-> E4
    T007 -.-> E5

    F1 -.->|imports| EF1
    F1 -.->|imports| EF2
    F2 -.->|imports| EF3
    F2 -.->|imports| EF4
    F2 -.->|imports| EF5
```

### Task-to-Component Mapping

<!-- Status: ⬜ Pending | 🟧 In Progress | ✅ Complete | 🔴 Blocked -->

| Task | Component(s) | Files | Status | Comment |
|------|-------------|-------|--------|---------|
| T001 | Python Fixtures | `/workspaces/flow_squared/tests/fixtures/samples/python/app_service.py` | ⬜ Pending | Cross-file imports to auth_handler.py, data_parser.py |
| T002 | TypeScript Fixtures | `/workspaces/flow_squared/tests/fixtures/samples/javascript/index.ts` | ⬜ Pending | Cross-file imports to app.ts, utils.js, component.tsx |
| T003 | Markdown Fixtures | `/workspaces/flow_squared/tests/fixtures/samples/markdown/execution-log.md` | ⬜ Pending | Node ID patterns for confidence 1.0 testing |
| T004 | Markdown Fixtures | `/workspaces/flow_squared/tests/fixtures/samples/markdown/README.md` | ⬜ Pending | Method references for multi-tier confidence |
| T005 | Ground Truth | `/workspaces/flow_squared/scripts/cross-files-rels-research/lib/ground_truth.py` | ⬜ Pending | 10+ ExpectedRelation entries |
| T006 | Experiments | `/workspaces/flow_squared/scripts/cross-files-rels-research/experiments/04_cross_lang_refs.py` | ⬜ Pending | Dockerfile/YAML reference detection |
| T007 | Experiments | `/workspaces/flow_squared/scripts/cross-files-rels-research/experiments/05_confidence_scoring.py` | ⬜ Pending | Precision/recall validation |
| T008 | Validation | `/workspaces/flow_squared/scripts/cross-files-rels-research/results/` | ⬜ Pending | Run all 5 experiments, JSON output |
| T009 | Test Suite | `/workspaces/flow_squared/tests/` | ⬜ Pending | Verify no regressions |

---

## Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Subtasks | Notes |
|--------|------|------|-----|------|--------------|------------------|------------|----------|-------|
| [ ] | T001 | Create `app_service.py` with cross-file imports | 2 | Core | – | `/workspaces/flow_squared/tests/fixtures/samples/python/app_service.py` | Python syntax valid (`python -m py_compile`), imports `auth_handler`, `data_parser` | – | Per plan § 3.1 content |
| [ ] | T002 | Create `index.ts` with cross-file imports | 2 | Core | – | `/workspaces/flow_squared/tests/fixtures/samples/javascript/index.ts` | TypeScript syntax valid, imports `app.ts`, `utils.js`, `component.tsx` | – | Verify target files exist first |
| [ ] | T003 | Create `execution-log.md` with node_id patterns | 1 | Core | – | `/workspaces/flow_squared/tests/fixtures/samples/markdown/execution-log.md` | Contains 5+ valid `callable:path:Symbol` patterns | – | Confidence 1.0 tier test |
| [ ] | T004 | Update/Create `README.md` with method references | 2 | Core | – | `/workspaces/flow_squared/tests/fixtures/samples/markdown/README.md` | Contains references to `auth_handler.py` symbols | – | Multi-tier confidence test |
| [ ] | T005 | Populate ground truth with 10+ relationships | 2 | Data | T001, T002, T003, T004 | `/workspaces/flow_squared/scripts/cross-files-rels-research/lib/ground_truth.py` | `len(GROUND_TRUTH) >= 10`, all `ExpectedRelation` valid | – | Per Finding 08 schema |
| [ ] | T006 | Create `04_cross_lang_refs.py` for Dockerfile/YAML | 2 | Experiment | – | `/workspaces/flow_squared/scripts/cross-files-rels-research/experiments/04_cross_lang_refs.py` | Script runs, JSON output in `results/04_crosslang.json` | – | Uses existing docker/yaml fixtures |
| [ ] | T007 | Create `05_confidence_scoring.py` for validation | 2 | Experiment | T005 | `/workspaces/flow_squared/scripts/cross-files-rels-research/experiments/05_confidence_scoring.py` | Outputs precision/recall per confidence tier | – | Compare extracted vs ground truth |
| [ ] | T008 | Run all 5 experiments on enriched fixtures | 1 | Validation | T006, T007 | `/workspaces/flow_squared/scripts/cross-files-rels-research/results/{01_nodeid,02_imports,03_calls,04_crosslang,05_scoring}.json` | All 5 JSON files valid, >90% precision for imports | – | Command in Alignment Brief |
| [ ] | T009 | Verify pytest still passes | 1 | Test | T008 | `/workspaces/flow_squared/tests/` | `pytest tests/ -v` exit code 0 | – | No regressions from fixtures |

---

## Alignment Brief

### Prior Phases Review

#### Phase-by-Phase Summary

**Phase 1: Setup & Fixture Audit** (Complete)
Established the complete scratch environment infrastructure. Created isolated venv with tree-sitter 0.25.2, verified parsing across 6 languages, audited all 21 fixtures finding zero cross-file relationships, and created the `ExpectedRelation` ground truth schema.

**Phase 2: Core Extraction Scripts** (Complete)
Built the extraction library (4 modules: `parser.py`, `queries.py`, `extractors.py`, `resolver.py`) and 3 experiment scripts. Validated against existing fixtures: 45 imports extracted with function-scoped detection working, 212 calls extracted with 36 constructors identified. Discovered tree-sitter 0.25 API changes requiring `Query()` + `QueryCursor()` pattern.

#### Cumulative Deliverables (Available to Phase 3)

**From Phase 1:**
| Deliverable | Path | Usage in Phase 3 |
|-------------|------|------------------|
| Ground truth schema | `/workspaces/flow_squared/scripts/cross-files-rels-research/lib/ground_truth.py` | T005 populates `GROUND_TRUTH` list |
| Fixture audit | Phase 1 execution.log.md | Informed fixture creation targets |
| Venv with dependencies | `/workspaces/flow_squared/scripts/cross-files-rels-research/.venv/` | All experiments run here |

**From Phase 2:**
| Deliverable | Path | Usage in Phase 3 |
|-------------|------|------------------|
| `parse_file()` | `lib/parser.py:53` | Parse enriched fixtures |
| `extract_imports()` | `lib/extractors.py:70` | Validate cross-file imports |
| `extract_calls()` | `lib/extractors.py:327` | Validate method calls |
| `calculate_confidence()` | `lib/resolver.py:32` | Score expected relationships |
| `NODE_ID_PATTERN` | `experiments/01_nodeid_detection.py:25` | Detect node_ids in markdown |
| Confidence tiers | `lib/resolver.py:14-22` | CONF_IMPORT=0.9, CONF_SELF_CALL=0.8, etc. |

#### Pattern Evolution

**Phase 1 → Phase 2**: Established modular architecture (lib/, experiments/, results/) that proved effective. Phase 2 expanded lib/ with 4 modules.

**Phase 2 → Phase 3**: Extraction infrastructure is frozen. Phase 3 focuses on data (fixtures, ground truth) not code changes to lib/.

#### Recurring Issues

1. **Ruby/Rust extraction**: Not implemented in Phase 2. Phase 3 does not need these languages.
2. **TypeScript inline type imports**: Edge case `import { type Foo }` not detected. May affect precision but out of scope.

#### Cross-Phase Learnings

1. **Test data first**: Phase 2's T001a (query validation) and test_data/sample_nodeid.md prevented empty-result confusion. Phase 3 should verify fixture validity before running experiments.
2. **tree-sitter 0.25 API**: Query execution must use `Query()` + `QueryCursor().matches()` pattern. All Phase 3 scripts must follow this.
3. **Confidence constants**: Use named constants from `lib/resolver.py` (CONF_IMPORT, CONF_TYPED, etc.) not magic numbers.

#### Reusable Infrastructure

| Infrastructure | Path | Phase 3 Usage |
|----------------|------|---------------|
| Import extraction | `lib/extractors.py:70` | Validate app_service.py imports |
| Call extraction | `lib/extractors.py:327` | Validate method calls |
| Node ID regex | `experiments/01_nodeid_detection.py:25` | Validate execution-log.md |
| JSON output pattern | `experiments/02_import_extraction.py` | Template for 04, 05 scripts |
| FIXTURE_MAP | `experiments/00_verify_setup.py:15` | Language detection reference |

#### Critical Findings Timeline

| Finding | Phase Applied | How |
|---------|---------------|-----|
| Finding 02 (Type-Only Imports) | Phase 2 | Detection in extractors.py:171-177 |
| Finding 03 (Method Call Confidence) | Phase 2 | Tiered scoring in resolver.py:83-101 |
| Finding 04 (Function-Scoped Imports) | Phase 2 | Parent-traversal in extractors.py:38-50 |
| Finding 05 (Go Dot/Blank Imports) | Phase 2 | Detection in extractors.py:229-266 |
| Finding 08 (Ground Truth Schema) | Phase 1 | ExpectedRelation dataclass |
| Finding 09 (Confidence Pyramid) | Phase 3 | Guides fixture creation order |
| Finding 10 (Node ID Regex) | Phase 2 | Pattern in 01_nodeid_detection.py:25 |

---

### Critical Findings Affecting This Phase

**Finding 01: Markdown Code Blocks Create False Positives**
- **Constrains**: Don't parse markdown code blocks as real imports
- **Requires**: Test node_id detection separately from code extraction
- **Addressed by**: T003, T004 (markdown fixtures test node_id regex, not code blocks)

**Finding 08: Ground Truth Reference Table**
- **Constrains**: Must use `ExpectedRelation` dataclass schema
- **Requires**: Populate with 10+ entries before validation
- **Addressed by**: T005

**Finding 09: Confidence Pyramid Guides Fixture Creation**
- **Constrains**: Create fixtures in confidence order for easier debugging
- **Requires**: Start with confidence 1.0 (node_id), then 0.9 (imports), then lower
- **Addressed by**: T003 (1.0) → T001/T002 (0.9) → T004 (mixed) order flexibility

---

### Invariants & Guardrails

- **No production code changes**: lib/ modules from Phase 2 are frozen
- **Syntactic validity**: All new fixtures must be valid Python/TypeScript/Markdown
- **No test regressions**: `pytest tests/` must pass after fixture changes
- **Confidence bounds**: All `expected_confidence` in [0.0, 1.0]

---

### Inputs to Read

| File | Purpose |
|------|---------|
| `/workspaces/flow_squared/tests/fixtures/samples/python/auth_handler.py` | Import target for app_service.py |
| `/workspaces/flow_squared/tests/fixtures/samples/python/data_parser.py` | Import target for app_service.py |
| `/workspaces/flow_squared/tests/fixtures/samples/javascript/app.ts` | Import target for index.ts |
| `/workspaces/flow_squared/tests/fixtures/samples/javascript/utils.js` | Import target for index.ts |
| `/workspaces/flow_squared/tests/fixtures/samples/javascript/component.tsx` | Import target for index.ts |
| `/workspaces/flow_squared/tests/fixtures/samples/docker/Dockerfile` | Cross-lang refs (04 script) |
| `/workspaces/flow_squared/tests/fixtures/samples/yaml/deployment.yaml` | Cross-lang refs (04 script) |
| `/workspaces/flow_squared/scripts/cross-files-rels-research/lib/ground_truth.py` | Phase 1 schema, T005 updates |

---

### Visual Alignment Aids

#### System State Flow

```mermaid
flowchart LR
    subgraph Before["Before Phase 3"]
        A1[21 Fixtures] --> A2[0 Cross-File Refs]
        A3[Extraction Scripts] --> A4[45 stdlib imports]
    end

    subgraph Phase3["Phase 3 Actions"]
        B1[Create app_service.py] --> B4[Cross-file imports]
        B2[Create index.ts] --> B4
        B3[Create markdown fixtures] --> B5[Node ID patterns]
        B6[Populate ground truth] --> B7[10+ relationships]
        B8[Create validation scripts] --> B9[Precision/Recall]
    end

    subgraph After["After Phase 3"]
        C1[24 Fixtures] --> C2[10+ Cross-File Refs]
        C3[Extraction Scripts] --> C4[Validated metrics]
    end

    Before --> Phase3 --> After
```

#### Validation Sequence

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Fix as Fixtures
    participant GT as Ground Truth
    participant Exp as Experiments
    participant Val as Validation

    Dev->>Fix: Create app_service.py (T001)
    Dev->>Fix: Create index.ts (T002)
    Dev->>Fix: Create markdown fixtures (T003, T004)

    Dev->>GT: Populate GROUND_TRUTH (T005)

    Dev->>Exp: Create 04_cross_lang_refs.py (T006)
    Dev->>Exp: Create 05_confidence_scoring.py (T007)

    Dev->>Val: Run all experiments (T008)
    Val->>Fix: Extract imports/calls
    Val->>GT: Compare results
    Val->>Dev: Precision/Recall metrics

    Dev->>Val: Run pytest (T009)
    Val->>Dev: No regressions confirmed
```

---

### Test Plan (Lightweight per Spec)

| Validation | Method | Expected | Fixture/Script |
|------------|--------|----------|----------------|
| app_service.py syntax | `python -m py_compile` | Exit 0 | T001 |
| index.ts syntax | Visual inspection (no tsc in scratch) | Valid TypeScript | T002 |
| Node ID count | `grep -c 'callable:' execution-log.md` | ≥5 | T003 |
| Ground truth entries | `len(GROUND_TRUTH)` | ≥10 | T005 |
| Import precision | 05_confidence_scoring.py | >90% for Python | T007 |
| pytest | `pytest tests/ -v` | Exit 0 | T009 |

---

### Step-by-Step Implementation Outline

1. **T001**: Read `auth_handler.py` and `data_parser.py` to understand exported symbols. Create `app_service.py` importing both.

2. **T002**: Verify `app.ts`, `utils.js`, `component.tsx` exist. Create `index.ts` importing from all three.

3. **T003**: Create `execution-log.md` with at least 5 `callable:path:Symbol` node_id patterns referencing existing fixtures.

4. **T004**: Create/update `README.md` with method references like `AuthHandler.validate_token()`.

5. **T005**: Open `lib/ground_truth.py`, populate `GROUND_TRUTH` list with 10+ `ExpectedRelation` entries covering:
   - app_service.py → auth_handler.py (import, 0.9)
   - app_service.py → data_parser.py (import, 0.9)
   - app_service.py → AuthHandler.__init__ (call, 0.8)
   - execution-log.md → auth_handler.py symbols (reference, 1.0)
   - index.ts → app.ts (import, 0.9)

6. **T006**: Create `04_cross_lang_refs.py` that parses Dockerfile (COPY/FROM) and YAML (configMapRef) for cross-language references.

7. **T007**: Create `05_confidence_scoring.py` that:
   - Runs extraction on enriched fixtures
   - Compares against `GROUND_TRUTH`
   - Outputs precision/recall per confidence tier

8. **T008**: Run all 5 experiments and save JSON to `results/`.

9. **T009**: Run `pytest tests/` to confirm no regressions.

---

### Commands to Run (Copy/Paste)

```bash
# Environment setup
cd /workspaces/flow_squared/scripts/cross-files-rels-research
source .venv/bin/activate

# Validate Python syntax (T001)
python -m py_compile /workspaces/flow_squared/tests/fixtures/samples/python/app_service.py

# Run all experiments (T008)
for exp in experiments/0*.py; do
  python "$exp" /workspaces/flow_squared/tests/fixtures/samples/ > "results/$(basename $exp .py).json" 2>&1
done

# Validate JSON output
for json in results/*.json; do python -c "import json; json.load(open('$json'))"; done

# Run pytest (T009)
cd /workspaces/flow_squared
pytest tests/ -v

# Ground truth count check
cd /workspaces/flow_squared/scripts/cross-files-rels-research
python -c "from lib.ground_truth import GROUND_TRUTH; print(f'Ground truth entries: {len(GROUND_TRUTH)}')"
```

---

### Risks & Unknowns

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| New fixtures break existing tests | High | Low | Run pytest after each fixture creation |
| TypeScript imports fail parsing | Medium | Low | Verify target files exist before T002 |
| Ground truth schema mismatch | Medium | Low | Use exact `ExpectedRelation` dataclass |
| Precision below 90% | Medium | Medium | Investigate false positives, adjust expectations |
| Dockerfile/YAML regex unreliable | Low | Medium | Document limitations in dossier |

---

### Ready Check

- [ ] Prior phases reviewed (Phase 1 & 2 complete)
- [ ] Critical findings mapped to tasks (Finding 01→T003/T004, Finding 08→T005, Finding 09→task order)
- [ ] ADR constraints mapped to tasks (N/A - no ADRs for this feature)
- [ ] Inputs to read identified (8 files listed)
- [ ] Commands to run documented
- [ ] Non-goals explicitly stated
- [ ] Mermaid diagrams render correctly

**Await explicit GO/NO-GO before implementation.**

---

## Phase Footnote Stubs

_Footnotes will be added by plan-6 during implementation._

| Footnote | Task | Description | File:Line |
|----------|------|-------------|-----------|
| | | | |

---

## Evidence Artifacts

- **Execution Log**: `/workspaces/flow_squared/docs/plans/022-cross-file-rels/tasks/phase-3-fixture-enrichment-validation/execution.log.md`
- **JSON Results**: `/workspaces/flow_squared/scripts/cross-files-rels-research/results/{01_nodeid,02_imports,03_calls,04_crosslang,05_scoring}.json`
- **Ground Truth**: `/workspaces/flow_squared/scripts/cross-files-rels-research/lib/ground_truth.py`

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

## Directory Layout

```
docs/plans/022-cross-file-rels/
├── cross-file-experimentation-spec.md
├── cross-file-experimentation-plan.md
├── research-dossier.md
├── external-research.md
└── tasks/
    ├── phase-1-setup-fixture-audit/
    │   ├── tasks.md
    │   └── execution.log.md
    ├── phase-2-core-extraction-scripts/
    │   ├── tasks.md
    │   └── execution.log.md
    └── phase-3-fixture-enrichment-validation/
        ├── tasks.md                    # This file
        └── execution.log.md            # Created by plan-6
```
