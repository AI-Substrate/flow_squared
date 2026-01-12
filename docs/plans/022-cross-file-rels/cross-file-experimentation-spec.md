# Cross-File Relationship Experimentation

**Plan**: `022-cross-file-rels`
**Type**: Experimentation (not implementation)
**Output**: Experimentation dossier documenting findings
**Mode**: Full (multi-phase)

---

## Testing Strategy

**Approach**: Lightweight
**Rationale**: Experimentation scripts are throwaway; formal tests unnecessary.

**Focus Areas**:
- Scripts run without errors
- Scripts produce expected output types (extracted imports, calls, references)
- Console output demonstrates extraction works

**Excluded**:
- Unit tests for scratch scripts
- Integration tests
- Test coverage requirements

**Mock Usage**: N/A (experimentation uses real fixture files, no mocking needed)

---

## Documentation Strategy

**Location**: None (plan folder only)
**Rationale**: Experimentation dossier in `docs/plans/022-cross-file-rels/` is the sole output. No README or docs/how/ updates needed for scratch experiments.

**Target Audience**: Development team (future implementation reference)
**Maintenance**: Dossier is a one-time research artifact

---

## Research Context

This specification incorporates findings from `research-dossier.md`.

| Aspect | Finding |
|--------|---------|
| **Components affected** | Tree-sitter parsing, fixture files, scratch experiments |
| **Critical dependencies** | `tree-sitter`, `tree-sitter-language-pack` (pip-installable) |
| **Modification risks** | None - experimentation only, no production code changes |
| **Link** | See `research-dossier.md` for full analysis |

**Key Research Finding**: Current test fixtures (21 files across 15 languages) have **zero cross-file relationships**. All imports are to standard libraries only.

---

## Summary

### What

Conduct hands-on experimentation with Tree-sitter-based cross-file relationship detection before committing to an implementation approach. Write experimental scripts in `scratch/` that:

1. Parse various file types and extract potential cross-file references
2. Test the full spectrum of reference types (direct node IDs → fuzzy name matches)
3. Validate confidence scoring heuristics against known relationships
4. Document findings, edge cases, and limitations

### Why

- **Validate assumptions**: Confirm Tree-sitter queries work as expected across languages
- **Discover unknowns**: Find edge cases and limitations before implementation
- **Inform architecture**: Use real data to guide implementation decisions
- **Enrich fixtures**: Create test fixtures with deliberate cross-file relationships
- **De-risk implementation**: Reduce surprises during actual implementation phase

---

## Goals

1. **Validate Tree-sitter parsing** works for import/reference extraction across:
   - Python, TypeScript/JavaScript, Go, Rust, Java, C/C++
   - Non-code files: Markdown, YAML, Dockerfile, JSON

2. **Test the full reference spectrum** with experiments covering:
   - **Confidence 1.0**: Direct fs2 node_id strings in files
   - **Confidence 0.9**: Explicit import statements resolving to files
   - **Confidence 0.7-0.8**: Constructor patterns (`p = Calculator()`, `p.add()`)
   - **Confidence 0.5-0.6**: Method calls with inferred receiver types
   - **Confidence 0.2-0.3**: Name matches (fuzzy, same-package)
   - **Confidence 0.1**: Substring matches in comments/strings

3. **Audit and enrich test fixtures** to include cross-file relationships:
   - Python files that import each other
   - TypeScript modules with import chains
   - Markdown files with node_id references
   - Dockerfile referencing Python entry points
   - README referencing code files and methods
   - YAML/JSON config referencing Python modules

4. **Document findings** in a detailed experimentation dossier including:
   - What worked, what didn't
   - Performance characteristics
   - Edge cases and limitations
   - Recommended approach for implementation

---

## Non-Goals

- **No production code changes** - This is experimentation only
- **No GraphStore modifications** - Test in isolation, don't touch core
- **No new dependencies in pyproject.toml** - Use temporary installs in scratch
- **No test suite additions** - Scratch scripts are throwaway experiments
- **No architecture decisions** - Observe and document, don't commit

---

## Complexity

**Score**: CS-2 (small)

**Breakdown**:
| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 1 | Multiple fixture files + scratch scripts |
| Integration (I) | 1 | Tree-sitter external dependency |
| Data/State (D) | 0 | No schema changes |
| Novelty (N) | 1 | Some exploration needed |
| Non-Functional (F) | 0 | No perf/security requirements |
| Testing/Rollout (T) | 0 | Experimentation, no rollout |
| **Total** | **3** | **CS-2** |

**Confidence**: 0.85

**Assumptions**:
- Tree-sitter Python bindings work as documented
- tree-sitter-language-pack includes all needed language grammars
- Fixture enrichment is straightforward

**Dependencies**:
- `tree-sitter` and `tree-sitter-language-pack` pip packages
- Existing fixture files in `tests/fixtures/samples/`

**Risks**:
- Tree-sitter query syntax may be tricky for some languages
- Some language grammars may have quirks

**Phases**:
1. Setup and fixture audit
2. Fixture enrichment (add cross-file relationships)
3. Experimentation scripts
4. Documentation and dossier

---

## Acceptance Criteria

### AC1: Fixture Audit Complete
- [ ] Documented which fixtures currently have cross-file references (expected: none)
- [ ] Identified gaps in fixture coverage per language
- [ ] Created fixture enrichment plan

### AC2: Fixtures Enriched with Cross-File Relationships
- [ ] **Python**: Added `app_service.py` that imports from `auth_handler.py` and `data_parser.py`
- [ ] **TypeScript**: Added `index.ts` that imports from `app.ts`, `utils.js`, `component.tsx`
- [ ] **Markdown**: Added `execution-log.md` with fs2 node_id references
- [ ] **Markdown**: Updated `README.md` to reference specific code files/methods
- [ ] **Dockerfile**: Updated to reference specific Python entry point file
- [ ] **YAML**: Updated `deployment.yaml` to reference Python module paths
- [ ] At least 3 language pairs have deliberate cross-file relationships

### AC3: Experimentation Scripts Written
- [ ] `scratch/cross-file-rels/01_treesitter_setup.py` - Validate Tree-sitter works
- [ ] `scratch/cross-file-rels/02_import_extraction.py` - Extract imports from Python/TS/Go
- [ ] `scratch/cross-file-rels/03_nodeid_detection.py` - Find fs2 node_ids in text files
- [ ] `scratch/cross-file-rels/04_call_extraction.py` - Extract method calls and receivers
- [ ] `scratch/cross-file-rels/05_cross_lang_refs.py` - Dockerfile→Python, YAML→Python
- [ ] `scratch/cross-file-rels/06_confidence_scoring.py` - Test confidence heuristics
- [ ] Each script runs successfully and produces output

### AC4: Reference Type Coverage
Experiments must cover all reference types:

| Type | Example | Experiment |
|------|---------|------------|
| Direct node_id | `callable:path:Class.method` in markdown | 03_nodeid_detection.py |
| File path reference | `./src/auth.py` in README | 03_nodeid_detection.py |
| Explicit import | `from auth_handler import X` | 02_import_extraction.py |
| Constructor pattern | `p = Calculator()` | 04_call_extraction.py |
| Method call | `p.add(1, 2)` | 04_call_extraction.py |
| Type annotation | `handler: AuthHandler` | 04_call_extraction.py |
| **Inheritance** | `class Child(Parent)` | 04_call_extraction.py |
| Cross-language ref | Dockerfile `COPY src/app.py` | 05_cross_lang_refs.py |
| Dockerfile entry | `CMD ["python", "app.py"]` | 05_cross_lang_refs.py |
| Config reference | YAML with Python paths | 05_cross_lang_refs.py |

### AC5: Experimentation Dossier Delivered
- [ ] Written to `docs/plans/022-cross-file-rels/experimentation-dossier.md`
- [ ] Includes findings for each experiment
- [ ] Documents what worked and what didn't
- [ ] Lists edge cases and limitations discovered
- [ ] Provides recommendations for implementation approach
- [ ] Includes confidence scoring validation results

---

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Tree-sitter queries differ per language more than expected | Medium | Medium | Start with Python, document patterns |
| Some languages may not parse well | Low | Low | Focus on top 5 languages, accept gaps |
| Confidence scoring heuristics may be too simplistic | Medium | Medium | Document edge cases, refine in implementation |

### Assumptions

1. Tree-sitter Python bindings are stable and well-documented
2. `tree-sitter-language-pack` includes Python, TypeScript, Go, Rust, Java, C
3. Existing fixtures are representative of real-world code
4. Scratch scripts don't need to be production-quality
5. 2-3 days is sufficient for experimentation

---

## Open Questions

All questions resolved in clarification session 2026-01-12.

1. ~~Should experiments also cover inheritance relationships?~~ **RESOLVED**: Yes, include inheritance detection (`class Child(Parent)`) alongside imports/calls.

2. ~~Dockerfile reference detection scope?~~ **RESOLVED**: Detect both `COPY` and `CMD`/`ENTRYPOINT` commands.

3. ~~Include performance benchmarks in dossier?~~ **RESOLVED**: No, functional validation only. Note any obvious slowness but no formal benchmarks.

4. ~~Test specific Flowspace/SCIP edge cases?~~ **RESOLVED**: No, fresh start. Discover edge cases through experimentation rather than porting old patterns.

---

## ADR Seeds (Optional)

### Decision Drivers
- Must remain language-agnostic (no per-language LSP/SCIP)
- Must work with pip-only dependencies
- Must support 15+ languages
- Confidence scoring is required (not binary relationships)

### Candidate Alternatives
- **A**: Pure Tree-sitter with custom queries per language
- **B**: Tree-sitter + stack-graphs for enhanced resolution (limited languages)
- **C**: Tree-sitter + graph-sitter for Python/TypeScript (accelerator)

### Stakeholders
- fs2 development team
- Future users of cross-file relationship features

---

## Unresolved Research

### Topics
From `research-dossier.md` External Research Opportunities:
1. **Stack Graphs evaluation** - Could enhance resolution for supported languages
2. **graph-sitter evaluation** - Could accelerate Python/TS implementation

### Impact
These could inform implementation approach, but are not blockers for experimentation.

### Recommendation
Conduct experimentation with pure Tree-sitter first. If results show significant gaps in resolution accuracy, consider external research before implementation.

---

## Detailed Phase Breakdown

### Phase 1: Setup & Fixture Audit (Day 1 Morning)

**Tasks**:
1. Create `scratch/cross-file-rels/` directory
2. Install tree-sitter packages in scratch environment
3. Audit all 21 fixture files for existing cross-file references
4. Document findings in audit table
5. Create fixture enrichment plan

**Output**: Audit table showing current state of fixtures

### Phase 2: Fixture Enrichment (Day 1 Afternoon)

**Tasks**:
1. Create `tests/fixtures/samples/python/app_service.py`:
   ```python
   from auth_handler import AuthHandler, AuthToken
   from data_parser import JSONParser, ParseResult

   class AppService:
       def __init__(self):
           self.auth = AuthHandler()
           self.parser = JSONParser()

       async def process(self, token_id: str, data: str):
           token = await self.auth.validate_token(token_id)
           result = self.parser.parse(data)
           return result
   ```

2. Create `tests/fixtures/samples/javascript/index.ts`:
   ```typescript
   import { Application, AppConfig } from "./app";
   import { debounce } from "./utils";
   import { Button, ThemeProvider } from "./component";

   const app = new Application({ name: "Test" });
   const debouncedStart = debounce(() => app.start(), 1000);
   ```

3. Create `tests/fixtures/samples/markdown/execution-log.md`:
   ```markdown
   ## Execution Log

   ### Nodes Called
   - `callable:tests/fixtures/samples/python/auth_handler.py:AuthHandler.authenticate`
   - `file:tests/fixtures/samples/python/data_parser.py`

   ### Files Referenced
   - See [auth handler](../python/auth_handler.py) for details
   ```

4. Update `tests/fixtures/samples/markdown/README.md`:
   - Add references to `auth_handler.py`, `data_parser.py`
   - Add method references like "see `AuthHandler.validate_token()`"

5. Update `tests/fixtures/samples/docker/Dockerfile`:
   - Add `COPY src/app_service.py /app/`
   - Add `CMD ["python", "app_service.py"]`

6. Update `tests/fixtures/samples/yaml/deployment.yaml`:
   - Add config referencing Python modules

**Output**: Enriched fixtures with deliberate cross-file relationships

### Phase 3: Experimentation Scripts (Day 2)

**Script 1: `01_treesitter_setup.py`**
- Install and verify tree-sitter works
- Parse a simple Python file
- Print AST structure
- Verify language-pack includes needed languages

**Script 2: `02_import_extraction.py`**
- Extract imports from Python files using queries
- Extract imports from TypeScript files
- Extract imports from Go files
- Map import strings to file paths

**Script 3: `03_nodeid_detection.py`**
- Regex for fs2 node_id pattern: `(file|callable|type):path:name`
- Find node_ids in markdown files
- Find file path references (relative paths)
- Score confidence based on pattern strength

**Script 4: `04_call_extraction.py`**
- Extract function calls from Python
- Extract method calls with receivers
- Attempt to infer receiver types from:
  - Constructor patterns (`p = Calculator()`)
  - Type annotations (`p: Calculator`)
  - Import statements
- Score confidence for each inference

**Script 5: `05_cross_lang_refs.py`**
- Parse Dockerfile for COPY/ENTRYPOINT referencing Python
- Parse YAML for Python module paths
- Parse JSON (package.json) for entry points
- Map to actual files

**Script 6: `06_confidence_scoring.py`**
- Test scoring heuristics against enriched fixtures
- Validate that known relationships get expected confidence
- Document any scoring anomalies

**Output**: Working scripts with console output showing extraction results

### Phase 4: Documentation & Dossier (Day 3)

**Tasks**:
1. Run all scripts and capture output
2. Analyze results for patterns
3. Document edge cases and limitations
4. Write experimentation dossier with:
   - Executive summary
   - Findings per experiment
   - What worked / what didn't
   - Edge cases discovered
   - Performance observations
   - Recommendations for implementation

**Output**: `docs/plans/022-cross-file-rels/experimentation-dossier.md`

---

## Fixture Enrichment Matrix

| Language | Current Files | Enrichment Needed | Cross-File Target |
|----------|---------------|-------------------|-------------------|
| Python | auth_handler.py, data_parser.py | Add app_service.py | app_service → auth_handler, data_parser |
| TypeScript | app.ts, component.tsx, utils.js | Add index.ts | index → app, utils, component |
| Go | server.go | Add handlers.go | handlers → server |
| Rust | lib.rs | Add config.rs | config → lib |
| Java | UserService.java | Split interfaces | Service → Repository, Email, Cache |
| Markdown | README.md | Add execution-log.md | Both → Python files |
| Dockerfile | Dockerfile | Update COPY/CMD | → Python entry point |
| YAML | deployment.yaml | Add Python paths | → Python modules |

---

## Expected Experimentation Dossier Structure

```markdown
# Experimentation Dossier: Cross-File Relationships

## Executive Summary
[What we learned, key findings]

## Experiment Results

### 1. Tree-sitter Setup
- Installation: [success/issues]
- Languages verified: [list]
- Performance: [observations]

### 2. Import Extraction
- Python: [findings]
- TypeScript: [findings]
- Go: [findings]
- Edge cases: [list]

### 3. Node ID Detection
- Pattern: [regex used]
- Success rate: [%]
- False positives: [count/examples]

### 4. Call Extraction
- Constructor pattern detection: [findings]
- Type annotation detection: [findings]
- Inference accuracy: [observations]

### 5. Cross-Language References
- Dockerfile → Python: [findings]
- YAML → Python: [findings]
- Markdown → Code: [findings]

### 6. Confidence Scoring
- Tier validation: [results]
- Anomalies: [list]
- Recommended adjustments: [if any]

## Edge Cases & Limitations
[Detailed list]

## Performance Observations
[If measured]

## Recommendations for Implementation
1. [Recommendation 1]
2. [Recommendation 2]
3. [Recommendation 3]

## Next Steps
- Run /plan-3-architect with these findings
- [Other actions]
```

---

## Clarifications

### Session 2026-01-12

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| Q1 | Workflow mode? | **Full** (multi-phase) | 4 phases with gates |
| Q2 | Testing approach? | **Lightweight** | Scripts run, produce output; no formal tests |
| Q3 | Include inheritance? | **Yes** | Added to reference types (AC4) |
| Q4 | Dockerfile scope? | **Both COPY and CMD/ENTRYPOINT** | Expanded cross-lang refs |
| Q5 | Performance benchmarks? | **No** | Functional validation only |
| Q6 | Test SCIP edge cases? | **No, fresh start** | Discover new edge cases |
| Q7 | Documentation location? | **None** | Dossier in plan folder only |

**Decisions Applied**:
- Added `**Mode**: Full` to header
- Added `## Testing Strategy` section (Lightweight)
- Added `## Documentation Strategy` section (None)
- Updated AC4 reference types table with inheritance and Dockerfile CMD
- Marked all Open Questions as RESOLVED

---

**Specification Complete**: 2026-01-12
**Clarification Complete**: 2026-01-12
**Next Step**: Run `/plan-3-architect` to generate phase-based plan
