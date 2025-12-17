# CLI Architecture Alignment - Extract Services

**Version**: 1.0.0
**Created**: 2025-12-17
**Status**: Draft
**Mode**: Simple

📚 This specification incorporates findings from `research-dossier.md`

---

## Research Context

The research dossier identified critical architectural violations in the CLI layer:

- **Components Affected**: `tree.py` (372 lines), `get_node.py` (110 lines), `scan.py` (176 lines)
- **Critical Dependencies**: GraphStore ABC, TreeConfig, existing service patterns (ScanPipeline, SampleService)
- **Modification Risks**: Low - clear function boundaries, existing patterns to follow
- **Key Finding**: 210+ lines of business logic in `tree.py` that belong in a service layer

See `research-dossier.md` for full analysis.

---

## Summary

**WHAT**: Extract business logic from CLI commands (`tree`, `get-node`) into dedicated service classes (`TreeService`, `GetNodeService`) following the established Clean Architecture patterns.

**WHY**:
1. CLI layer currently violates Clean Architecture principle P1: "CLI → Services → {Adapters, Repos}"
2. Business logic in CLI is untestable without file I/O and real graph fixtures
3. Services enable code reuse across interfaces (CLI, API, SDK, tests)
4. Aligns codebase with documented constitution and prevents future violations

---

## Goals

1. **Extract TreeService** - Move node filtering, tree building, and root bucket algorithms from `tree.py` into a dedicated service
2. **Extract GetNodeService** - Move node retrieval and JSON serialization logic from `get_node.py` into a dedicated service
3. **Enable Unit Testing** - New services must be testable with `FakeGraphStore` without file I/O
4. **Preserve CLI Behavior** - All existing CLI functionality and output must remain unchanged
5. **Follow Established Patterns** - Use `ScanPipeline` and `SampleService` as reference implementations
6. **Update Constitution** - Add explicit rule prohibiting business logic in CLI layer
7. **Add Service-Focused Fixtures** - Extend `conftest.py` with fixtures for testing new services

---

## Non-Goals

1. **Refactor scan.py** - Already correctly uses ScanPipeline; display logic cleanup is optional
2. **Refactor init.py** - Simple template writing; service extraction adds no value
3. **Change CLI Interface** - No changes to command arguments, options, or output format
4. **Create API/SDK** - Services enable this future work but not in scope
5. **Rename/Move CLI Tests** - Existing tests remain in `tests/unit/cli/`
6. **Add New CLI Features** - Pure refactoring; no new functionality

---

## Complexity

**Score**: CS-3 (Medium)

**Breakdown**:
| Factor | Score | Rationale |
|--------|-------|-----------|
| Surface Area (S) | 2 | 6+ files touched: 2 CLI, 2 new services, 2 test files, constitution |
| Integration (I) | 0 | Internal only; no external dependencies |
| Data/State (D) | 0 | No schema changes; uses existing models |
| Novelty (N) | 0 | Well-specified; patterns exist in codebase |
| Non-Functional (F) | 0 | Standard requirements |
| Testing (T) | 1 | Unit + integration tests required |

**Total**: 3 → CS-3 (Medium)

**Confidence**: 0.90 - Research confirmed patterns exist; mechanical refactoring

**Assumptions**:
- Existing service patterns (ScanPipeline, SampleService) are correct and should be followed
- FakeGraphStore is sufficient for service testing
- CLI tests can remain integration-style while services get unit tests

**Dependencies**:
- GraphStore ABC (exists)
- FakeGraphStore (exists)
- TreeConfig (exists)
- ConfigurationService pattern (exists)

**Risks**:
- CLI behavior regression if extraction is incomplete
- Mitigation: Run existing CLI tests before/after each change

**Phases**:
1. Create GetNodeService + tests (simpler, validates pattern)
2. Create TreeService + tests (complex, more logic)
3. Update CLI commands to use services
4. Update constitution with CLI scope rule

---

## Acceptance Criteria

### AC1: TreeService Exists and Is Unit Testable
**Given** a `FakeGraphStore` with mock nodes
**When** `TreeService.filter_nodes(pattern)` is called
**Then** matching nodes are returned without file I/O
**And** tests complete in <100ms

### AC2: TreeService Implements All Business Logic
**Given** the existing `tree.py` functions `_filter_nodes()`, `_build_root_bucket()`, and `_add_node_to_tree()`
**When** TreeService is complete
**Then** all logic is moved to service methods
**And** `tree.py` contains only argument parsing and Rich presentation

### AC3: GetNodeService Exists and Is Unit Testable
**Given** a `FakeGraphStore` with mock nodes
**When** `GetNodeService.get_node(node_id)` is called
**Then** the correct node or error is returned without file I/O
**And** tests complete in <100ms

### AC4: GetNodeService Implements All Business Logic
**Given** the existing `get_node.py` logic for graph loading and node retrieval
**When** GetNodeService is complete
**Then** all logic is moved to service methods
**And** `get_node.py` contains only argument parsing and output handling

### AC5: CLI Behavior Is Preserved
**Given** the existing CLI test suites (`test_tree_cli.py`, `test_get_node_cli.py`)
**When** all tests are run after refactoring
**Then** all tests pass
**And** exit codes, output format, and error messages are unchanged

### AC6: Services Follow DI Pattern
**Given** the `SampleService` and `ScanPipeline` patterns
**When** new services are implemented
**Then** constructor receives `ConfigurationService` (registry) and `GraphStore` (ABC)
**And** config extraction happens inside service via `config.require()`

### AC7: Domain Result Types Are Used
**Given** the `ScanSummary` and `ProcessResult` patterns
**When** services return results
**Then** they return frozen dataclass types (e.g., `TreeResult`, `GetNodeResult`)
**And** CLI handles presentation of these types

### AC8: Constitution Is Updated
**Given** the existing constitution at `docs/rules-idioms-architecture/constitution.md`
**When** the refactoring is complete
**Then** a new rule is added: "CLI layer MUST NOT contain business logic"
**And** the code review checklist includes this verification

### AC9: Service Tests Use Fakes
**Given** the `FakeGraphStore` pattern
**When** service tests are written
**Then** no mocks (`unittest.mock`) are used for adapters/repos
**And** fakes inherit from ABC

---

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CLI behavior regression | Medium | High | Run CLI tests after each change; preserve exact output format |
| Incomplete logic extraction | Low | Medium | Compare line counts; verify CLI only has imports + presentation |
| Service pattern misapplied | Low | Medium | Code review against ScanPipeline reference |
| Test fixture complexity | Low | Low | Reuse existing FakeGraphStore; add minimal new fixtures |

### Assumptions

1. **Pattern Correctness**: ScanPipeline and SampleService are authoritative examples
2. **Test Coverage**: Existing CLI tests adequately cover behavior to verify
3. **Scope Stability**: No new CLI features will be added during refactoring
4. **GraphStore Sufficiency**: The GraphStore ABC provides all methods needed by services

---

## Open Questions

All questions resolved in clarification session 2025-12-17.

---

## Testing Strategy

**Approach**: Lightweight
**Rationale**: Pure refactoring with no new functionality. Existing CLI tests verify behavior preservation. New service tests validate extraction correctness.

**Focus Areas**:
- Service unit tests with FakeGraphStore (validate extracted logic works)
- Existing CLI tests (verify behavior unchanged after refactor)

**Excluded**:
- Full TDD cycle (code exists, just moving it)
- E2E tests (CLI tests already cover this)
- Performance benchmarks

**Mock Usage**: Avoid mocks entirely (per constitution P4: "Fakes over Mocks")
- Use FakeGraphStore for service tests
- Use real fixtures for CLI integration tests

---

## Documentation Strategy

**Location**: None (D)
**Rationale**: Internal refactoring - no new features, no external API changes. Constitution update is the only documentation change.

**Target Audience**: Developers maintaining fs2 codebase
**Maintenance**: N/A - patterns are documented in SampleService and ScanPipeline

---

## ADR Seeds (Optional)

### Decision Drivers
- Constitution mandates Clean Architecture layer separation
- Testability requires pure logic extraction
- Existing patterns (ScanPipeline) establish precedent

### Candidate Alternatives
- **A**: Full extraction to services (recommended) - aligns with architecture
- **B**: Partial extraction - move only filtering to service, keep tree building in CLI
- **C**: No extraction - document as technical debt, fix later

### Stakeholders
- Development team (implementing)
- Future maintainers (understanding patterns)
- LLM agents (following constitution rules)

---

## External Research

No external research was required. All patterns exist in the codebase:
- `ScanPipeline` demonstrates service composition
- `SampleService` demonstrates DI pattern
- `FakeGraphStore` demonstrates test fakes

---

## Clarifications

### Session 2025-12-17

**Q1: Workflow Mode**
- **Answer**: Simple (A)
- **Rationale**: Pure refactoring with established patterns. Single-phase execution, inline tasks.

**Q2: Testing Strategy**
- **Answer**: Lightweight (C)
- **Rationale**: No TDD - just a refactor. Tests will be updated to cover new services. Existing CLI tests verify behavior preservation.

**Q3: Documentation Strategy**
- **Answer**: None (D)
- **Rationale**: Internal refactoring; no new external documentation needed. Constitution update is in-scope.

**Q4: TreeResult Model** (from Open Questions)
- **Resolution**: Use `list[CodeNode]` initially. Services can return simple types; CLI handles Rich rendering. Domain result types are optional for this refactor.
- **Rationale**: YAGNI - keep it simple for a refactor. Can add `TreeResult` later if needed.

**Q5: Error Handling** (from Open Questions)
- **Resolution**: Follow ScanPipeline pattern - raise domain exceptions (`GraphStoreError`, etc.)
- **Rationale**: Consistency with existing services. CLI catches and renders errors.

**Q6: Test Location** (from Open Questions)
- **Resolution**: Yes, `tests/unit/services/` alongside `test_scan_pipeline.py`
- **Rationale**: Follows existing test organization.

---

## Coverage Summary

| Category | Status | Count |
|----------|--------|-------|
| Resolved | Complete | 6 |
| Deferred | N/A | 0 |
| Outstanding | N/A | 0 |

---

**Next Step**: Run `/plan-3-architect` to generate the single-phase plan with inline tasks
