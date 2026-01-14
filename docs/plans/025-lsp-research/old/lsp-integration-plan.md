# LSP Integration for Cross-File Relationship Extraction - Implementation Plan

**Plan Version**: 1.1.0
**Created**: 2026-01-14
**Spec**: [./lsp-integration-spec.md](./lsp-integration-spec.md)
**Status**: DRAFT
**Mode**: Full

> **v1.1.0**: Added "Commands to Run" sections to all 9 phases for agent handover readiness.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Technical Context](#technical-context)
3. [Critical Research Findings](#critical-research-findings)
4. [Testing Philosophy](#testing-philosophy)
5. [Implementation Phases](#implementation-phases)
   - [Phase 0: Environment Preparation](#phase-0-environment-preparation)
   - [Phase 0b: Multi-Project Research](#phase-0b-multi-project-research)
   - [Phase 1: LSP Adapter Foundation](#phase-1-lsp-adapter-foundation)
   - [Phase 2: Generic LSP Client](#phase-2-generic-lsp-client)
   - [Phase 3: Python/Pyright Integration](#phase-3-pythonpyright-integration)
   - [Phase 4: Multi-Language Expansion](#phase-4-multi-language-expansion)
   - [Phase 5: Pipeline Stage Integration](#phase-5-pipeline-stage-integration)
   - [Phase 6: Multi-Project Support](#phase-6-multi-project-support)
   - [Phase 7: Validation & Documentation](#phase-7-validation--documentation)
6. [Cross-Cutting Concerns](#cross-cutting-concerns)
7. [Complexity Tracking](#complexity-tracking)
8. [Progress Tracking](#progress-tracking)
9. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

### Problem Statement

fs2's current Tree-sitter-based relationship extraction achieves 100% accuracy for imports but cannot resolve method calls on typed receivers (e.g., `self.auth.validate()`) or find all references to a symbol. This limits the code graph's utility for cross-file navigation queries like "what calls this function?"

### Solution Approach

- Integrate Language Server Protocol (LSP) servers (Pyright, gopls, OmniSharp, typescript-language-server) as optional relationship extraction enhancers
- Create an `LspAdapter` ABC with thin per-language configuration wrappers (~10 lines each)
- Add a new `RelationshipExtractionStage` to the scan pipeline after parsing
- Leverage the existing CodeEdge/EdgeType/GraphStore foundation (56 tests passing from 024 Phase 1)

### Expected Outcomes

- High-confidence cross-file relationships (0.9-1.0 confidence from LSP vs 0.3-0.5 from heuristics)
- Method call resolution across files
- "Find all references" queries with verified accuracy
- Graceful degradation when LSP servers unavailable

### Success Metrics

- AC01-AC21 acceptance criteria met
- Integration tests pass with real LSP servers
- Pipeline completes successfully with/without LSP servers
- Adding a new language requires only configuration entry

---

## Technical Context

### Current System State

```
ScanPipeline (existing)
├── DiscoveryStage     → File enumeration
├── ParsingStage       → Tree-sitter AST extraction
├── SmartContentStage  → Content summarization
├── EmbeddingStage     → Vector embeddings
└── StorageStage       → GraphStore persistence
```

**Foundation Already Complete** (from 024 Phase 1):
- `EdgeType` enum: IMPORTS, CALLS, REFERENCES, DOCUMENTS
- `CodeEdge` frozen dataclass with validation
- `GraphStore.add_relationship_edge()` and `get_relationships()`
- `PipelineContext.relationships` field
- FakeGraphStore with call_history (56 tests passing)

### Integration Requirements

1. **New Pipeline Stage**: `RelationshipExtractionStage` between Parsing and SmartContent
2. **New Adapter Layer**: `LspAdapter` ABC + GenericLspAdapter + FakeLspAdapter
3. **New Configuration**: `LspConfig` pydantic model in config system
4. **Devcontainer Update**: Install 4 LSP servers for dev/CI

### Constraints and Limitations

- LSP servers are external binaries (not pip packages)
- JSON-RPC over stdio requires clean stdout (no debug output)
- Sequential lazy initialization (one server at a time, as needed)
- Shutdown after each scan (clean memory slate)
- LSP must remain optional (graceful degradation)

### Assumptions

1. LSP servers can be installed in devcontainer via npm/go/dotnet
2. JSON-RPC stdio protocol is consistent across servers
3. Project root detection from marker files is reliable
4. LSP servers index typical projects in <30 seconds

---

## Critical Research Findings

### Prior Research

Research dossier contains 75 findings including 15 Prior Learnings from previous implementations. Key findings incorporated into this plan:

### 🚨 Critical Discovery 01: stdout Isolation Requirement

**Impact**: Critical
**Sources**: [PL-01, R1-02]
**Problem**: Any stdout during LSP communication breaks JSON-RPC message framing
**Solution**: Configure stderr-only logging BEFORE importing LSP libraries; use MCP logging pattern from `logging_config.py`
**Example**:
```python
# ❌ WRONG - Debug print corrupts JSON-RPC
print(f"Sending request: {request}")
process.stdin.write(message)

# ✅ CORRECT - Use stderr for all logging
import sys
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stderr))
logger.debug(f"Sending request: {request}")
```
**Action Required**: GenericLspAdapter must redirect all logging to stderr
**Affects Phases**: Phase 1, Phase 2, Phase 3

### 🚨 Critical Discovery 02: ABC Structure with @abstractmethod

**Impact**: Critical
**Sources**: [I1-05, DC-01]
**Problem**: Runtime enforcement requires explicit ABC pattern
**Solution**: LspAdapter must use `abc.ABC` with `@abstractmethod` decorators following EmbeddingAdapter pattern
**Example**:
```python
# ❌ WRONG - Protocol doesn't enforce at instantiation
class LspAdapter(Protocol):
    def get_references(self, ...): ...

# ✅ CORRECT - ABC enforces on instantiation
class LspAdapter(ABC):
    @abstractmethod
    async def get_references(self, ...) -> list[dict]: ...
```
**Action Required**: Create LspAdapter ABC in `lsp_adapter.py`
**Affects Phases**: Phase 1

### 🚨 Critical Discovery 03: No LSP Type Leakage

**Impact**: Critical
**Sources**: [R1-03, PS-04, AC14-AC16]
**Problem**: LSP server response types vary; service layer must see only domain types
**Solution**: All translation happens in adapter layer; return only `CodeEdge` instances
**Example**:
```python
# ❌ WRONG - Pyright types leak into service
def get_relationships(self) -> list[PyrightLocation]:
    return pyright_client.get_references()

# ✅ CORRECT - Domain types only
def get_relationships(self, ...) -> list[CodeEdge]:
    raw = self._client.get_references()
    return [self._to_code_edge(loc) for loc in raw]
```
**Action Required**: LspAdapter.get_references() returns list[CodeEdge]
**Affects Phases**: Phase 1, Phase 3, Phase 4

### ⚠️ High Discovery 04: 3-Step Binary Validation

**Impact**: High
**Sources**: [R1-01, external-research-3]
**Problem**: LSP servers may be missing, not in PATH, or wrong version
**Solution**: Implement 3-step validation: (1) shutil.which(), (2) version check with server-specific command, (3) version comparison
**Example**:
```python
# ❌ WRONG - Single check misses version issues
if shutil.which("pyright-langserver"):
    return True

# ✅ CORRECT - 3-step validation
def validate_server(config: LspServerConfig) -> ServerStatus:
    path = shutil.which(config.command[0])
    if not path:
        return ServerStatus.MISSING

    version = get_version(config)  # Server-specific command
    if not version:
        return ServerStatus.MISCONFIGURED

    if version < config.min_version:
        return ServerStatus.WRONG_VERSION

    return ServerStatus.READY
```
**Action Required**: Create LspServerValidator with 3-step validation
**Affects Phases**: Phase 1, Phase 2

### ⚠️ High Discovery 05: Graceful Degradation Pattern

**Impact**: High
**Sources**: [R1-04, AC13]
**Problem**: Pipeline must complete even if all LSP servers fail
**Solution**: Follow `smart_content_service=None` pattern; LSP is optional enhancement
**Example**:
```python
# ❌ WRONG - LSP failure breaks pipeline
if not lsp_adapter:
    raise RuntimeError("LSP required")

# ✅ CORRECT - Continue with metrics
if lsp_adapter is None:
    context.metrics["lsp_skipped"] = True
    return  # Skip stage, pipeline continues
```
**Action Required**: RelationshipExtractionStage handles None adapter
**Affects Phases**: Phase 5

### ⚠️ High Discovery 06: File Naming Convention

**Impact**: High
**Sources**: [I1-02]
**Problem**: fs2 has strict naming conventions for adapters
**Solution**: Follow pattern: ABC in `{name}_adapter.py`, fake in `{name}_adapter_fake.py`, impl in `{name}_adapter_{impl}.py`
**Action Required**:
```
src/fs2/core/adapters/
├── lsp_adapter.py           # ABC
├── lsp_adapter_fake.py      # FakeLspAdapter
├── lsp_adapter_generic.py   # GenericLspAdapter (stdio JSON-RPC)
└── lsp_server_configs.py    # LspServerConfig registry
```
**Affects Phases**: Phase 1, Phase 2

### ⚠️ High Discovery 07: Exception Hierarchy Pattern

**Impact**: High
**Sources**: [I1-03, R1-07]
**Problem**: LSP errors need domain exception translation with actionable messages
**Solution**: Add `LspAdapterError` hierarchy following `LLMAdapterError` pattern
**Example**:
```python
class LspAdapterError(AdapterError):
    """Base error for LSP adapter operations."""

class LspServerNotInstalledError(LspAdapterError):
    """Server binary not found.

    Common causes:
    - Server not installed
    - Server not in PATH

    Recovery:
    - Install with: npm install -g pyright
    - Verify with: which pyright-langserver
    """
```
**Affects Phases**: Phase 1

### ⚠️ High Discovery 08: Fake Adapter Pattern

**Impact**: High
**Sources**: [I1-06, PL-11]
**Problem**: Unit tests need controllable LSP behavior without real servers
**Solution**: FakeLspAdapter inherits from ABC, tracks calls in `call_history`, supports `set_response()` and `set_error()`
**Action Required**: Create FakeLspAdapter following FakeEmbeddingAdapter pattern
**Affects Phases**: Phase 1

### ⚠️ High Discovery 09: Pipeline Stage Protocol

**Impact**: High
**Sources**: [I1-07]
**Problem**: New stage must integrate with existing pipeline architecture
**Solution**: Implement `PipelineStage` Protocol with `name` property and `process(context)` method
**Action Required**: Create RelationshipExtractionStage, insert after ParsingStage
**Affects Phases**: Phase 5

### ⚠️ High Discovery 10: Integration Test Reliability

**Impact**: High
**Sources**: [R1-06, PL-06]
**Problem**: Real LSP servers need startup time; tests may be flaky
**Solution**: Session-scoped fixtures, readiness checks, realistic timeouts
**Action Required**: Session-scoped LSP adapter fixtures with initialization wait
**Affects Phases**: Phase 3, Phase 4, Phase 6

### Medium Discovery 11: Configuration Model Pattern

**Impact**: Medium
**Sources**: [I1-04]
**Problem**: LspConfig must follow pydantic conventions
**Solution**: Follow `EmbeddingConfig` pattern with `__config_path__` and validators
**Affects Phases**: Phase 1

### Medium Discovery 12: Multi-Project Root Detection

**Impact**: Medium
**Sources**: [R1-08]
**Problem**: Complex repos may have multiple valid roots
**Solution**: "Most specific (deepest) wins" rule with explicit config override
**Affects Phases**: Phase 0b, Phase 6

---

## Testing Philosophy

### Testing Approach

**Selected Approach**: Full TDD
**Rationale**: Comprehensive test-first for all components including LSP communication, ensuring protocol fidelity with real servers
**Focus Areas**:
- Adapter ABC contract compliance
- Error handling (server not installed, initialization failures, timeouts)
- Multi-project root detection and precedence
- LSP protocol correctness (JSON-RPC, lifecycle)
- Pipeline integration and graceful degradation

### Test-Driven Development

For each component:
1. **RED**: Write tests that fail (describe expected behavior)
2. **GREEN**: Implement minimal code to pass tests
3. **REFACTOR**: Improve quality while maintaining green tests

### Mock Usage Policy

**Policy**: Targeted fakes only (per spec clarification Q3)
- FakeLspAdapter implements ABC for unit testing service layer
- Real LSP servers required for all integration tests
- No mocking of LSP protocol communication

### Test Documentation

Every test includes:
```python
"""
Purpose: [what truth this test proves]
Quality Contribution: [how this prevents bugs]
Acceptance Criteria: [measurable assertions]
"""
```

### Test Structure

```
tests/
├── unit/adapters/
│   ├── test_lsp_adapter.py         # ABC contract tests
│   ├── test_lsp_adapter_fake.py    # Fake behavior tests
│   └── test_lsp_adapter_generic.py # Generic client unit tests
├── integration/
│   ├── test_lsp_pyright.py         # Real Pyright tests
│   ├── test_lsp_gopls.py           # Real gopls tests
│   └── test_lsp_pipeline.py        # Pipeline integration
└── fixtures/samples/
    ├── python_multi_project/       # Multi-project fixture
    ├── typescript_project/         # TS fixture
    └── go_project/                 # Go fixture
```

---

## Implementation Phases

### Phase 0: Environment Preparation

**Objective**: Install and verify all LSP servers in devcontainer for development and CI.

**Deliverables**:
- Updated `.devcontainer/devcontainer.json` with LSP server installations
- Post-install verification script
- CI workflow validates server availability

**Dependencies**: None (foundational phase)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OmniSharp requires .NET SDK | Medium | Low | Document as prerequisite, use feature |
| Server versions incompatible | Low | Medium | Pin specific versions |

### Tasks (Full TDD Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 0.1 | [ ] | Add Pyright to devcontainer | 1 | `which pyright-langserver` returns path | - | npm global install |
| 0.2 | [ ] | Add gopls to devcontainer | 1 | `which gopls` returns path | - | Go feature includes gopls |
| 0.3 | [ ] | Add typescript-language-server | 1 | `which typescript-language-server` returns path | - | npm global install |
| 0.4 | [ ] | Add OmniSharp to devcontainer | 2 | `which OmniSharp` or `dotnet tool list` shows omnisharp | - | .NET SDK required |
| 0.5 | [ ] | Create verification script | 1 | Script exits 0 when all servers found | - | scripts/verify-lsp-servers.sh |
| 0.6 | [ ] | Add to postCreateCommand | 1 | Servers installed on container rebuild | - | |

### Acceptance Criteria
- [ ] All 4 LSP servers available via `which` command (AC01)
- [ ] Verification script passes in devcontainer
- [ ] Servers persist across container rebuilds

### Commands to Run

```bash
# Verify all LSP servers are installed
which pyright-langserver && echo "✓ Pyright"
which gopls && echo "✓ gopls"
which typescript-language-server && echo "✓ typescript-language-server"
dotnet tool list -g | grep -i omnisharp && echo "✓ OmniSharp"

# Run verification script (after task 0.5)
./scripts/verify-lsp-servers.sh

# Expected: All commands return paths, script exits 0
```

---

### Phase 0b: Multi-Project Research

**Objective**: Research and validate multi-project root detection strategy via scripts/lsp experiments.

**Deliverables**:
- Research scripts in `scripts/lsp/`
- Multi-project test fixtures
- Documented project root detection algorithm

**Dependencies**: Phase 0 (servers installed)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Detection algorithm too complex | Medium | High | Start simple, iterate |
| Marker file patterns vary | Medium | Medium | Document known patterns |

### Tasks (Full TDD Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 0b.1 | [ ] | Create scripts/lsp/ directory | 1 | Directory exists | - | |
| 0b.2 | [ ] | Create multi-project test fixtures | 2 | Fixtures have nested project roots | - | Python, TS, Go, C# |
| 0b.3 | [ ] | Write project root detection script | 2 | Script finds marker files | - | .csproj, go.mod, tsconfig.json, pyproject.toml |
| 0b.4 | [ ] | Test "deepest wins" algorithm | 2 | Correct root for nested projects | - | Per Q5 clarification |
| 0b.5 | [ ] | Document detection algorithm | 1 | README in scripts/lsp/ | - | |

### Acceptance Criteria
- [ ] Detection algorithm documented
- [ ] Test fixtures validate detection for all 4 languages
- [ ] "Most specific (deepest) wins" rule implemented

### Commands to Run

```bash
# Verify research directory and fixtures exist
ls -la scripts/lsp/
ls -la tests/fixtures/samples/python_multi_project/
ls -la tests/fixtures/samples/go_project/

# Run detection algorithm tests
python scripts/lsp/detect_project_root.py tests/fixtures/samples/python_multi_project/

# Expected: Script outputs correct project root for nested structures
```

---

### Phase 1: LSP Adapter Foundation

**Objective**: Create the LspAdapter ABC, LspServerConfig, exception hierarchy, and FakeLspAdapter.

**Deliverables**:
- `src/fs2/core/adapters/lsp_adapter.py` (ABC)
- `src/fs2/core/adapters/lsp_adapter_fake.py` (Fake)
- `src/fs2/core/adapters/lsp_server_configs.py` (Config dataclass)
- Exception hierarchy in `exceptions.py`
- Comprehensive test coverage

**Dependencies**: Phase 0b (research complete)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ABC design doesn't fit all servers | Low | High | Research before design |
| Exception hierarchy incomplete | Low | Medium | Add exceptions as discovered |

### Tasks (Full TDD Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 1.1 | [ ] | Write ABC contract tests | 2 | Tests: ABC non-instantiable, methods required | - | test_lsp_adapter.py |
| 1.2 | [ ] | Create LspAdapter ABC | 2 | Tests from 1.1 pass | - | lsp_adapter.py |
| 1.3 | [ ] | Write LspServerConfig tests | 1 | Tests: frozen, validation | - | |
| 1.4 | [ ] | Create LspServerConfig dataclass | 1 | Tests from 1.3 pass | - | lsp_server_configs.py |
| 1.5 | [ ] | Write exception hierarchy tests | 2 | Tests: inheritance, messages | - | |
| 1.6 | [ ] | Add LspAdapterError hierarchy | 2 | Tests from 1.5 pass | - | exceptions.py |
| 1.7 | [ ] | Write FakeLspAdapter tests | 2 | Tests: call_history, set_response, set_error | - | test_lsp_adapter_fake.py |
| 1.8 | [ ] | Create FakeLspAdapter | 2 | Tests from 1.7 pass | - | lsp_adapter_fake.py |
| 1.9 | [ ] | Verify ABC inheritance | 1 | FakeLspAdapter inherits from LspAdapter | - | |

### Test Examples (Write First!)

```python
@pytest.mark.unit
class TestLspAdapterABC:
    """Tests for LspAdapter abstract base class contract."""

    def test_given_abc_when_instantiate_directly_then_raises_type_error(self):
        """
        Purpose: Proves LspAdapter cannot be instantiated directly
        Quality Contribution: Enforces ABC pattern at runtime
        Acceptance Criteria: TypeError raised on direct instantiation
        """
        with pytest.raises(TypeError, match="abstract"):
            LspAdapter()

    def test_given_missing_get_references_when_instantiate_then_raises_type_error(self):
        """
        Purpose: Proves get_references is a required abstract method
        Quality Contribution: Ensures all implementations provide relationship extraction
        Acceptance Criteria: TypeError mentions 'get_references'
        """
        class IncompleteLspAdapter(LspAdapter):
            @property
            def provider_name(self) -> str:
                return "incomplete"
            # Missing: get_references, get_definition, initialize, shutdown

        with pytest.raises(TypeError, match="get_references"):
            IncompleteLspAdapter()
```

### Non-Happy-Path Coverage
- [ ] ABC instantiation rejection
- [ ] Missing method detection
- [ ] Invalid config values rejected
- [ ] Exception message formatting

### Acceptance Criteria
- [ ] LspAdapter ABC defines language-agnostic interface (AC03)
- [ ] FakeLspAdapter inherits from ABC with call_history
- [ ] Exception hierarchy includes server-not-found and initialization errors (AC05, AC06)
- [ ] All tests passing (100% of phase tests)
- [ ] Test coverage > 80% for new code

### Commands to Run

```bash
# Run Phase 1 unit tests
pytest tests/unit/adapters/test_lsp_adapter.py tests/unit/adapters/test_lsp_adapter_fake.py -v --tb=short

# Run linter on new files
ruff check src/fs2/core/adapters/lsp_adapter.py src/fs2/core/adapters/lsp_adapter_fake.py src/fs2/core/adapters/lsp_server_configs.py

# Check test coverage
pytest tests/unit/adapters/test_lsp_adapter*.py --cov=src/fs2/core/adapters --cov-report=term-missing --cov-fail-under=80

# Verify ABC inheritance
python -c "from fs2.core.adapters.lsp_adapter_fake import FakeLspAdapter; from fs2.core.adapters.lsp_adapter import LspAdapter; assert issubclass(FakeLspAdapter, LspAdapter); print('✓ ABC inheritance verified')"

# Expected: All tests pass (exit 0), coverage > 80%, no ruff errors
```

---

### Phase 2: Generic LSP Client

**Objective**: Implement the GenericLspAdapter with stdio JSON-RPC communication.

**Deliverables**:
- `src/fs2/core/adapters/lsp_adapter_generic.py`
- Server lifecycle management (initialize, shutdown)
- Async request/response handling
- Error translation

**Dependencies**: Phase 1 (ABC and Fake complete)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| JSON-RPC framing issues | Medium | High | Use reference implementation from research |
| Stdout pollution | Medium | High | stderr-only logging (Critical Discovery 01) |
| Deadlocks | Low | High | Timeouts on all I/O |

### Tasks (Full TDD Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 2.1 | [ ] | Write JSON-RPC message framing tests | 2 | Tests: Content-Length header, message parsing | - | |
| 2.2 | [ ] | Implement message framing | 2 | Tests from 2.1 pass | - | |
| 2.3 | [ ] | Write request/response correlation tests | 2 | Tests: ID matching, async handling | - | |
| 2.4 | [ ] | Implement request/response handler | 3 | Tests from 2.3 pass | - | |
| 2.5 | [ ] | Write server lifecycle tests | 2 | Tests: initialize, shutdown sequence | - | |
| 2.6 | [ ] | Implement server lifecycle | 2 | Tests from 2.5 pass | - | |
| 2.7 | [ ] | Write error translation tests | 2 | Tests: SDK errors → domain exceptions | - | |
| 2.8 | [ ] | Implement error translation | 2 | Tests from 2.7 pass | - | |
| 2.9 | [ ] | Write timeout handling tests | 2 | Tests: request timeout, graceful failure | - | |
| 2.10 | [ ] | Implement timeout handling | 2 | Tests from 2.9 pass | - | 30s default per research |

### Acceptance Criteria
- [ ] GenericLspAdapter inherits from LspAdapter ABC
- [ ] Server starts via subprocess with stdio
- [ ] JSON-RPC messages framed correctly
- [ ] Proper shutdown sequence (exit notification)
- [ ] All SDK errors translated to domain exceptions

### Commands to Run

```bash
# Run Phase 2 unit tests
pytest tests/unit/adapters/test_lsp_adapter_generic.py -v --tb=short

# Run linter
ruff check src/fs2/core/adapters/lsp_adapter_generic.py

# Check test coverage for generic client
pytest tests/unit/adapters/test_lsp_adapter_generic.py --cov=src/fs2/core/adapters/lsp_adapter_generic --cov-report=term-missing --cov-fail-under=80

# Verify ABC inheritance
python -c "from fs2.core.adapters.lsp_adapter_generic import GenericLspAdapter; from fs2.core.adapters.lsp_adapter import LspAdapter; assert issubclass(GenericLspAdapter, LspAdapter); print('✓ ABC inheritance verified')"

# Expected: All tests pass (exit 0), coverage > 80%, no ruff errors
```

---

### Phase 3: Python/Pyright Integration

**Objective**: Add Pyright configuration and validate with integration tests.

**Deliverables**:
- Pyright config in `LSP_CONFIGS`
- Integration tests with real Pyright server
- Test fixtures with Python cross-file imports

**Dependencies**: Phase 2 (Generic client complete)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Pyright initialization slow | Medium | Low | Reasonable timeout (60s) |
| Pyright quirks | Low | Medium | Document any workarounds |

### Tasks (Full TDD Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 3.1 | [ ] | Write Pyright config tests | 1 | Tests: command, language_id, extensions | - | |
| 3.2 | [ ] | Add Pyright to LSP_CONFIGS | 1 | Tests from 3.1 pass | - | |
| 3.3 | [ ] | Create Python test fixtures | 2 | Fixtures have cross-file imports, method calls | - | tests/fixtures/samples/ |
| 3.4 | [ ] | Write Pyright integration tests | 3 | Tests: get_references, get_definition | - | Real Pyright server |
| 3.5 | [ ] | Run integration tests, fix issues | 2 | All integration tests pass | - | |
| 3.6 | [ ] | Validate CodeEdge conversion | 2 | LSP results → CodeEdge with confidence 0.9 | - | AC15 |

### Acceptance Criteria
- [ ] Pyright config requires only ~10 lines (AC04)
- [ ] Integration tests use real Pyright server (AC17)
- [ ] LSP results converted to CodeEdge with confidence 0.9 (AC15)
- [ ] Graceful failure when Pyright not installed (AC05)

### Commands to Run

```bash
# Verify Pyright is available
which pyright-langserver || echo "ERROR: Pyright not installed"

# Run Pyright config unit tests
pytest tests/unit/adapters/test_lsp_server_configs.py -k pyright -v

# Run Pyright integration tests (requires real server)
pytest tests/integration/test_lsp_pyright.py -v --timeout=120

# Verify CodeEdge conversion
pytest tests/integration/test_lsp_pyright.py -k "code_edge" -v

# Expected: All tests pass, integration tests complete within 120s
```

---

### Phase 4: Multi-Language Expansion

**Objective**: Add gopls, OmniSharp, and typescript-language-server configurations.

**Deliverables**:
- Go (gopls), C# (OmniSharp), TypeScript (typescript-language-server) configs
- Integration tests for each language
- Language-specific test fixtures

**Dependencies**: Phase 3 (Python validated)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Server-specific quirks | Medium | Medium | Per-server testing |
| OmniSharp .NET dependency | Low | Low | Document prerequisite |

### Tasks (Full TDD Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 4.1 | [ ] | Write gopls config tests | 1 | Tests: command, language_id | - | gopls version not --version |
| 4.2 | [ ] | Add gopls to LSP_CONFIGS | 1 | Tests from 4.1 pass | - | |
| 4.3 | [ ] | Create Go test fixtures | 2 | Fixtures have cross-file calls | - | |
| 4.4 | [ ] | Write gopls integration tests | 2 | Tests: get_references, get_definition | - | |
| 4.5 | [ ] | Write OmniSharp config tests | 1 | Tests: command, .NET requirement | - | |
| 4.6 | [ ] | Add OmniSharp to LSP_CONFIGS | 1 | Tests from 4.5 pass | - | Requires .NET SDK (Q8) |
| 4.7 | [ ] | Create C# test fixtures | 2 | Fixtures have cross-file calls | - | |
| 4.8 | [ ] | Write OmniSharp integration tests | 2 | Tests: get_references, get_definition | - | |
| 4.9 | [ ] | Write TS language server config tests | 1 | Tests: command, extensions | - | .ts, .tsx, .js, .jsx |
| 4.10 | [ ] | Add typescript-language-server to LSP_CONFIGS | 1 | Tests from 4.9 pass | - | |
| 4.11 | [ ] | Create TypeScript test fixtures | 2 | Fixtures have cross-file calls | - | |
| 4.12 | [ ] | Write TS integration tests | 2 | Tests: get_references, get_definition | - | |

### Acceptance Criteria
- [ ] All 4 languages configured with ~10 lines each (AC04)
- [ ] Integration tests pass for each language (AC17)
- [ ] All return same result types (AC14)

### Commands to Run

```bash
# Verify all LSP servers are available
which gopls && which typescript-language-server && dotnet tool list -g | grep -i omnisharp

# Run config unit tests for all languages
pytest tests/unit/adapters/test_lsp_server_configs.py -v

# Run gopls integration tests
pytest tests/integration/test_lsp_gopls.py -v --timeout=120

# Run OmniSharp integration tests
pytest tests/integration/test_lsp_omnisharp.py -v --timeout=120

# Run TypeScript integration tests
pytest tests/integration/test_lsp_typescript.py -v --timeout=120

# Run all multi-language integration tests
pytest tests/integration/test_lsp_*.py -v --timeout=300

# Expected: All tests pass, each language returns CodeEdge with same schema
```

---

### Phase 5: Pipeline Stage Integration

**Objective**: Create RelationshipExtractionStage and integrate with ScanPipeline.

**Deliverables**:
- `RelationshipExtractionStage` implementing `PipelineStage` Protocol
- Integration with `ScanPipeline`
- Lazy LSP initialization
- CLI `--with-lsp` flag

**Dependencies**: Phase 4 (All languages working)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Pipeline timing issues | Low | Medium | Insert at correct position |
| Graceful degradation failure | Low | High | Test with servers unavailable |

### Tasks (Full TDD Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 5.1 | [ ] | Write RelationshipExtractionStage tests | 3 | Tests: process(), graceful degradation | - | |
| 5.2 | [ ] | Create RelationshipExtractionStage | 3 | Tests from 5.1 pass | - | After ParsingStage |
| 5.3 | [ ] | Write lazy initialization tests | 2 | Tests: server starts on first file | - | AC12 |
| 5.4 | [ ] | Implement lazy initialization | 2 | Tests from 5.3 pass | - | |
| 5.5 | [ ] | Write pipeline integration tests | 3 | Tests: full scan with LSP | - | |
| 5.6 | [ ] | Integrate stage into ScanPipeline | 2 | Tests from 5.5 pass | - | |
| 5.7 | [ ] | Write graceful degradation tests | 2 | Tests: pipeline completes without LSP | - | AC13 |
| 5.8 | [ ] | Add CLI `--with-lsp` flag | 2 | Flag enables LSP stage | - | |
| 5.9 | [ ] | Test shutdown after scan | 1 | Servers shutdown cleanly | - | Q6 decision |

### Acceptance Criteria
- [ ] New stage runs after ParsingStage, before SmartContentStage (AC10)
- [ ] Stage populates `context.relationships` with CodeEdge instances (AC11)
- [ ] Lazy initialization on first file (AC12)
- [ ] Pipeline completes even if all LSP servers fail (AC13)

### Commands to Run

```bash
# Run pipeline stage unit tests
pytest tests/unit/services/test_relationship_extraction_stage.py -v --tb=short

# Run pipeline integration tests
pytest tests/integration/test_lsp_pipeline.py -v --timeout=180

# Test graceful degradation (with servers unavailable)
FS2_LSP__ENABLED=false pytest tests/integration/test_lsp_pipeline.py -k "graceful_degradation" -v

# Test CLI flag
fs2 scan --with-lsp tests/fixtures/samples/python_multi_project/ --dry-run

# Verify lazy initialization
pytest tests/integration/test_lsp_pipeline.py -k "lazy_init" -v

# Expected: All tests pass, pipeline completes with/without LSP servers
```

---

### Phase 6: Multi-Project Support

**Objective**: Implement project root detection and per-project LSP server instances.

**Deliverables**:
- `LspConfig` pydantic model with project roots
- Project root detection algorithm
- Per-project server instances

**Dependencies**: Phase 5 (Pipeline working)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Detection algorithm incorrect | Medium | High | "Deepest wins" + explicit override |
| Multiple server instances memory | Low | Medium | One server per language max |

### Tasks (Full TDD Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 6.1 | [ ] | Write LspConfig tests | 2 | Tests: project_roots, validation | - | AC07 |
| 6.2 | [ ] | Create LspConfig pydantic model | 2 | Tests from 6.1 pass | - | |
| 6.3 | [ ] | Write project root detection tests | 2 | Tests: marker files, deepest wins | - | AC08, AC09 |
| 6.4 | [ ] | Implement project root detection | 2 | Tests from 6.3 pass | - | |
| 6.5 | [ ] | Write multi-project fixture tests | 2 | Tests: correct root per file | - | |
| 6.6 | [ ] | Create multi-project test fixtures | 2 | Nested projects per language | - | AC02 |
| 6.7 | [ ] | Write per-project server tests | 2 | Tests: separate servers per root | - | |
| 6.8 | [ ] | Implement per-project servers | 2 | Tests from 6.7 pass | - | |

### Acceptance Criteria
- [ ] LspConfig allows specifying project roots (AC07)
- [ ] System determines correct project root for each file (AC08)
- [ ] Auto-detection from marker files works (AC09)
- [ ] Multi-project tests pass for each language (AC18)

### Commands to Run

```bash
# Run LspConfig unit tests
pytest tests/unit/config/test_lsp_config.py -v --tb=short

# Run project root detection unit tests
pytest tests/unit/adapters/test_project_root_detection.py -v

# Run multi-project integration tests
pytest tests/integration/test_multi_project.py -v --timeout=180

# Test with nested fixtures (deepest wins)
pytest tests/integration/test_multi_project.py -k "nested" -v

# Verify fixtures have correct structure
ls -laR tests/fixtures/samples/python_multi_project/

# Expected: All tests pass, correct project root detected for nested structures
```

---

### Phase 7: Validation & Documentation

**Objective**: End-to-end validation, performance benchmarks, and documentation.

**Deliverables**:
- End-to-end integration tests
- Performance benchmarks
- README.md LSP section
- docs/how/ guides

**Dependencies**: Phase 6 (All features complete)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Performance not meeting AC20/AC21 | Medium | Medium | Profile and optimize |

### Tasks (Full TDD Approach)

| #   | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 7.1 | [ ] | Write end-to-end integration tests | 3 | Tests: full scan with all languages | - | |
| 7.2 | [ ] | Run full integration suite | 2 | All tests pass | - | |
| 7.3 | [ ] | Write performance benchmarks | 2 | Measure startup time, query time | - | |
| 7.4 | [ ] | Validate AC20 (5s startup) | 1 | Each server starts <5s | - | |
| 7.5 | [ ] | Validate AC21 (2x scan time) | 1 | LSP scan <2x Tree-sitter scan | - | |
| 7.6 | [ ] | Write graceful degradation tests | 2 | Pipeline works without servers | - | AC19 |
| 7.7 | [ ] | Update README.md with LSP section | 2 | Install commands, verification | - | Per Doc Strategy |
| 7.8 | [ ] | Create docs/how/user/lsp-integration-guide.md | 2 | Configuration, troubleshooting | - | |
| 7.9 | [ ] | Create docs/how/dev/lsp-adapter-architecture.md | 2 | Adapter design, adding languages | - | |

### Acceptance Criteria
- [ ] All 21 acceptance criteria verified
- [ ] Performance meets AC20/AC21
- [ ] README.md updated with LSP installation
- [ ] User and developer guides complete

### Commands to Run

```bash
# Run full end-to-end integration suite
pytest tests/integration/test_lsp_*.py -v --timeout=300

# Run all unit tests
pytest tests/unit/adapters/test_lsp_*.py tests/unit/services/test_relationship_extraction_stage.py tests/unit/config/test_lsp_config.py -v

# Run performance benchmarks (AC20: startup <5s, AC21: scan <2x baseline)
pytest tests/benchmarks/test_lsp_performance.py -v --benchmark-json=lsp_benchmark_results.json

# Validate AC20: Server startup time
python -c "
import time
from fs2.core.adapters.lsp_adapter_generic import GenericLspAdapter
from fs2.core.adapters.lsp_server_configs import LSP_CONFIGS
import asyncio

async def test_startup():
    for lang, config in LSP_CONFIGS.items():
        start = time.perf_counter()
        adapter = GenericLspAdapter(config)
        await adapter.initialize('/tmp/test')
        elapsed = time.perf_counter() - start
        await adapter.shutdown()
        assert elapsed < 5.0, f'{lang} startup took {elapsed:.2f}s (>5s)'
        print(f'✓ {lang}: {elapsed:.2f}s')

asyncio.run(test_startup())
"

# Run graceful degradation tests (AC19)
pytest tests/integration/test_lsp_pipeline.py -k "graceful" -v

# Run full test suite with coverage
pytest --cov=src/fs2/core/adapters --cov=src/fs2/core/services --cov-report=html --cov-fail-under=80

# Run linter on all LSP code
ruff check src/fs2/core/adapters/lsp_*.py src/fs2/core/services/*relationship*.py src/fs2/config/lsp_config.py

# Verify documentation files exist
ls -la README.md docs/how/user/lsp-integration-guide.md docs/how/dev/lsp-adapter-architecture.md

# Expected: All tests pass, coverage > 80%, benchmarks meet AC20/AC21, docs exist
```

---

## Cross-Cutting Concerns

### Security Considerations

- **Input Validation**: LSP server responses validated before processing
- **Binary Execution**: Only execute binaries from PATH, never arbitrary paths
- **Subprocess Isolation**: LSP servers run in isolated subprocesses

### Observability

- **Logging Strategy**: stderr-only for stdio protocol compliance
- **Metrics**: Track server startup time, query count, success rate
- **Error Tracking**: Domain exceptions with actionable messages

### Documentation

- **Location**: Hybrid (README + docs/how/) per Documentation Strategy
- **README.md**: LSP server installation commands, basic verification
- **docs/how/user/**: Multi-project configuration, troubleshooting, features
- **docs/how/dev/**: Adapter architecture, adding new languages, testing

---

## Complexity Tracking

| Component | CS | Label | Breakdown (S,I,D,N,F,T) | Justification | Mitigation |
|-----------|-----|-------|------------------------|---------------|------------|
| GenericLspAdapter | 3 | Medium | S=1,I=2,D=0,N=0,F=0,T=0 | JSON-RPC protocol, subprocess mgmt | Reference impl from research |
| RelationshipExtractionStage | 3 | Medium | S=1,I=1,D=1,N=0,F=0,T=0 | Pipeline integration, lazy init | Follow existing stage patterns |
| Multi-project detection | 3 | Medium | S=1,I=0,D=1,N=1,F=0,T=0 | Complex repos, nested roots | "Deepest wins" + explicit override |
| Full feature (overall) | 4 | Large | S=2,I=2,D=1,N=1,F=0,T=2 | External deps, multi-phase rollout | Staged per-language rollout |

---

## Progress Tracking

### Phase Completion Checklist

- [ ] Phase 0: Environment Preparation - NOT STARTED
- [ ] Phase 0b: Multi-Project Research - NOT STARTED
- [ ] Phase 1: LSP Adapter Foundation - NOT STARTED
- [ ] Phase 2: Generic LSP Client - NOT STARTED
- [ ] Phase 3: Python/Pyright Integration - NOT STARTED
- [ ] Phase 4: Multi-Language Expansion - NOT STARTED
- [ ] Phase 5: Pipeline Stage Integration - NOT STARTED
- [ ] Phase 6: Multi-Project Support - NOT STARTED
- [ ] Phase 7: Validation & Documentation - NOT STARTED

### STOP Rule

**IMPORTANT**: This plan must be complete before creating tasks. After writing this plan:
1. Run `/plan-4-complete-the-plan` to validate readiness
2. Only proceed to `/plan-5-phase-tasks-and-brief` after validation passes

---

## Change Footnotes Ledger

**NOTE**: This section will be populated during implementation by plan-6a-update-progress.

**Footnote Numbering Authority**: plan-6a-update-progress is the **single source of truth** for footnote numbering across the entire plan.

[^1]: [To be added during implementation via plan-6a]
[^2]: [To be added during implementation via plan-6a]
[^3]: [To be added during implementation via plan-6a]

---

**Plan Version**: 1.0.0
**Created**: 2026-01-14
**Spec**: [./lsp-integration-spec.md](./lsp-integration-spec.md)

---

**Next step**: Run `/plan-4-complete-the-plan` to validate readiness.
