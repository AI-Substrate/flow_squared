# LSP Integration via Vendored SolidLSP - Implementation Plan

**Plan Version**: 1.0.0
**Created**: 2026-01-14
**Spec**: [./lsp-integration-spec.md](./lsp-integration-spec.md)
**Status**: DRAFT

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Technical Context](#technical-context)
3. [Critical Research Findings](#critical-research-findings)
4. [Testing Philosophy](#testing-philosophy)
5. [Implementation Phases](#implementation-phases)
   - [Phase 0: Environment Preparation](#phase-0-environment-preparation)
   - [Phase 0b: Multi-Project Research](#phase-0b-multi-project-research)
   - [Phase 1: Vendor SolidLSP Core](#phase-1-vendor-solidlsp-core)
   - [Phase 2: LspAdapter ABC and Exceptions](#phase-2-lspadapter-abc-and-exceptions)
   - [Phase 3: SolidLspAdapter Implementation](#phase-3-solidlspadapter-implementation)
   - [Phase 4: Multi-Language LSP Support](#phase-4-multi-language-lsp-support)
   - [Phase 5: Python Import Extraction](#phase-5-python-import-extraction)
   - [Phase 6: Node ID and Filename Detection](#phase-6-node-id-and-filename-detection)
   - [Phase 7: TypeScript and Go Imports](#phase-7-typescript-and-go-imports)
   - [Phase 8: Pipeline Integration](#phase-8-pipeline-integration)
   - [Phase 9: Documentation](#phase-9-documentation)
6. [Cross-Cutting Concerns](#cross-cutting-concerns)
7. [Complexity Tracking](#complexity-tracking)
8. [Progress Tracking](#progress-tracking)
9. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

### Problem Statement
fs2 currently extracts cross-file relationships using Tree-sitter heuristics, which cannot resolve method calls through type inference (e.g., `self.auth.validate()` → `AuthHandler.validate()`). This limits agent accuracy when answering "what calls this function?" queries.

### Solution Approach
- **Vendor Serena's SolidLSP** (~25K LOC) to `src/fs2/vendors/solidlsp/`
- **Create thin adapter wrapper** (`LspAdapter` ABC ~150 LOC, `SolidLspAdapter` ~350 LOC)
- **Translate LSP responses** to fs2's existing `CodeEdge` domain model at the adapter boundary
- **Support 40+ languages** automatically via SolidLSP's language server configurations
- **Test with 4 languages**: Python (Pyright), Go (gopls), TypeScript, C# (OmniSharp)

### Expected Outcomes
- Cross-file method call resolution with 0.9-1.0 confidence (vs 0.3-0.5 from heuristics)
- Graceful degradation when LSP servers unavailable
- Actionable error messages guiding users to install missing servers

### Success Metrics
- All 19 acceptance criteria from spec satisfied
- Integration tests passing with real LSP servers
- No Tree-sitter regression (baseline extraction unchanged)

---

## Technical Context

### Current System State
- **Foundation complete**: CodeEdge, EdgeType, GraphStore from 024 Phase 1 (56 tests passing)
- **Tree-sitter extraction**: Working for imports, doc references at 100% accuracy
- **Missing capability**: Type-aware method call resolution

### Integration Requirements
- Adapters must follow fs2 Clean Architecture patterns (R2.1, R3.1)
- Exception translation at adapter boundary (R3.3)
- ConfigurationService injection (R3.2)
- Domain-only types in ABC signatures

### Constraints and Limitations
- Users must install LSP servers (no auto-install)
- LSP servers are external binaries (not pip packages)
- Some servers spawn child processes requiring psutil for cleanup

### Assumptions
1. SolidLSP's core functionality is independent of Serena-specific features
2. Import path changes (`solidlsp.*` → `fs2.vendors.solidlsp.*`) are sufficient
3. Users can follow installation instructions for LSP servers
4. Foundation models (CodeEdge, EdgeType) handle all LSP result types

---

## Critical Research Findings

### Reference Key

The discovery codes reference source documents from the research phase:

| Code Prefix | Source Document |
|-------------|-----------------|
| R1-* | Risk analysis from `/docs/plans/025-lsp-research/research-dossier.md` |
| PL-* | Prior learnings from research dossier |
| I1-* | Implementation strategy discoveries |
| P1-* | Pattern discoveries from fs2 codebase exploration |
| external-research-* | External research documents in plan folder |

### 🚨 Critical Discovery 01: Stdout Isolation Required
**Impact**: Critical
**Sources**: [R1-07, PL-01]
**Problem**: Any stdout output during LSP import/initialization breaks JSON-RPC communication
**Root Cause**: JSON-RPC uses Content-Length headers over stdout
**Solution**: Configure stderr-only logging BEFORE any LSP imports
```python
# In adapter implementation
import sys, os
_orig_stdout = sys.stdout
sys.stdout = open(os.devnull, 'w')
try:
    from fs2.vendors.solidlsp.ls import SolidLanguageServer
finally:
    sys.stdout = _orig_stdout
```
**Action Required**: All LSP imports must be wrapped with stdout suppression
**Affects Phases**: Phase 1, Phase 3

### 🚨 Critical Discovery 02: Process Tree Cleanup
**Impact**: Critical
**Sources**: [R1-02, external-research-5 Section 7]
**Problem**: Some LSP servers spawn child processes; standard terminate() leaves orphans
**Root Cause**: OmniSharp, Vue server, etc. spawn helper processes
**Solution**: Use psutil for recursive child process termination with fallback
```python
def _signal_process_tree(self, process, terminate: bool = True):
    try:
        import psutil
        parent = psutil.Process(process.pid)
        for child in parent.children(recursive=True):
            getattr(child, "terminate" if terminate else "kill")()
        getattr(parent, "terminate" if terminate else "kill")()
    except ImportError:
        process.terminate() if terminate else process.kill()
```
**Action Required**: Add psutil as optional dependency; implement two-tier shutdown
**Affects Phases**: Phase 3, Phase 4

### 🚨 Critical Discovery 03: Graceful Degradation
**Impact**: Critical
**Sources**: [R1-05, spec AC15]
**Problem**: Scan must complete even if LSP initialization fails
**Solution**: Wrap all LSP operations in try/except, fall back to Tree-sitter
```python
def extract_relationships(self, file: Path) -> list[CodeEdge]:
    edges = []
    edges.extend(self._treesitter_extract_imports(file))  # Always
    try:
        if self.lsp_adapter and self.lsp_adapter.is_ready():
            edges.extend(self._lsp_extract_references(file))
    except LspAdapterError as e:
        logger.warning(f"LSP extraction failed: {e}")
    return edges
```
**Action Required**: All LSP calls must be non-fatal to scan completion
**Affects Phases**: Phase 3, Phase 5

### High Discovery 04: Actionable Error Messages
**Impact**: High
**Sources**: [R1-06, spec Q5 clarification]
**Problem**: Generic errors provide no recovery path
**Solution**: Create LspAdapterError hierarchy with platform-specific install commands
```python
class LspServerNotFoundError(LspAdapterError):
    def __init__(self, server_name: str, install_commands: dict[str, str]):
        system = platform.system()
        cmd = install_commands.get(system, install_commands.get('default'))
        super().__init__(f"'{server_name}' not found. Install with:\n  {cmd}")
```
**Action Required**: Each error type includes exact install/fix command
**Affects Phases**: Phase 2, Phase 4

### High Discovery 05: Adapter Naming Convention
**Impact**: High
**Sources**: [P1-01, R2.2]
**Pattern**: fs2 uses specific naming convention for adapter files
- ABC: `{name}_adapter.py`
- Implementation: `{name}_adapter_{impl}.py`
- Fake: `{name}_adapter_fake.py`
**Action Required**: Follow convention exactly
```
/src/fs2/core/adapters/lsp_adapter.py          # ABC
/src/fs2/core/adapters/lsp_adapter_fake.py     # Test double
/src/fs2/core/adapters/lsp_adapter_solidlsp.py # SolidLSP wrapper
```
**Affects Phases**: Phase 2, Phase 3

### High Discovery 06: ConfigurationService Injection
**Impact**: High
**Sources**: [P1-03, R3.2]
**Pattern**: Adapters receive ConfigurationService registry, call require() internally
```python
class SolidLspAdapter(LspAdapter):
    def __init__(self, config: "ConfigurationService"):
        self._lsp_config = config.require(LspConfig)
```
**Action Required**: No concept leakage - composition root doesn't know adapter configs
**Affects Phases**: Phase 2, Phase 3

### High Discovery 07: CodeEdge Mapping
**Impact**: High
**Sources**: [I1-03, P1-05]
**Mapping**: LSP responses map cleanly to existing CodeEdge model

| LSP Request | EdgeType | Confidence | resolution_rule |
|-------------|----------|------------|-----------------|
| `textDocument/references` | REFERENCES | 1.0 | `lsp:references` |
| `textDocument/definition` | REFERENCES | 1.0 | `lsp:definition` |

**Action Required**: Adapter must return CodeEdge instances with these values
**Affects Phases**: Phase 3

### High Discovery 08: Test Double Pattern
**Impact**: High
**Sources**: [P1-06, spec Q3 clarification]
**Pattern**: Fakes over mocks; fakes inherit from ABC with call_history
```python
class FakeLspAdapter(LspAdapter):
    def __init__(self, config: "ConfigurationService"):
        self.call_history: list[dict[str, Any]] = []
        self._response: list[CodeEdge] | None = None
        self._error: Exception | None = None

    def set_response(self, edges: list[CodeEdge]) -> None:
        self._response = edges
```
**Action Required**: Create FakeLspAdapter following this pattern
**Affects Phases**: Phase 2

### Medium Discovery 09: Import Path Changes
**Impact**: Medium
**Sources**: [R1-03]
**Problem**: Vendored SolidLSP needs import path modifications
**Solution**: Systematic sed/awk transformation + verification test
```bash
# Transform imports
sed -i 's/from solidlsp\./from fs2.vendors.solidlsp./g' *.py
sed -i 's/import solidlsp\./import fs2.vendors.solidlsp./g' *.py
```
**Action Required**: Create import verification test after vendoring
**Affects Phases**: Phase 1

### Medium Discovery 10: Initialization Wait
**Impact**: Medium
**Sources**: [R1-09, external-research-5 Section 11]
**Problem**: LSP servers need time to index before cross-file refs work
**Solution**: Configurable per-language initialization wait
```python
@dataclass(frozen=True)
class LspServerConfig:
    name: str
    command: list[str]
    cross_file_wait_seconds: float = 2.0
```
**Action Required**: Wait only once per session before first cross-file query
**Affects Phases**: Phase 3, Phase 4

### Medium Discovery 11: Project Root Detection
**Impact**: Medium
**Sources**: [Phase 0b research, external-research-4]
**Problem**: LSP servers need correct rootUri for workspace boundary
**Solution**: "Deepest wins" algorithm with marker file detection
- Python: `pyproject.toml`, `setup.py`
- Go: `go.mod`
- TypeScript: `tsconfig.json`, `package.json`
- C#: `.csproj`, `.sln`
**Action Required**: Research and validate algorithm before adapter implementation
**Affects Phases**: Phase 0b, Phase 3

### Medium Discovery 12: Exception Hierarchy
**Impact**: Medium
**Sources**: [P1-02, R3.3]
**Pattern**: Domain exceptions in exceptions.py with recovery instructions
```python
class LspAdapterError(AdapterError):
    """Base LSP error."""

class LspServerNotFoundError(LspAdapterError):
    """Server binary not found."""

class LspServerCrashError(LspAdapterError):
    """Server process crashed."""

class LspTimeoutError(LspAdapterError):
    """Operation timed out."""

class LspInitializationError(LspAdapterError):
    """Server initialization failed."""
```
**Action Required**: Add to existing exceptions.py following pattern
**Affects Phases**: Phase 2

### Low Discovery 13: Parallel Server Startup
**Impact**: Low
**Sources**: [R1-10]
**Optimization**: Start all language servers in parallel with ThreadPoolExecutor
**Rollback**: Fall back to sequential if issues arise
**Affects Phases**: Phase 4

### Low Discovery 14: Memory Monitoring
**Impact**: Low
**Sources**: [R1-08, external-research-4]
**Optimization**: Optional psutil-based memory monitoring with auto-restart
**Rollback**: Disable monitoring if psutil causes issues
**Affects Phases**: Phase 3 (optional enhancement)

---

## Testing Philosophy

### Testing Approach
**Selected Approach**: Full TDD
**Rationale**: Adapter boundary is critical for type translation correctness and Clean Architecture compliance
**Focus Areas**:
- Adapter ABC contract compliance
- Exception translation (SolidLSP → domain errors)
- LSP response → CodeEdge conversion
- Graceful degradation when servers unavailable
- Vendored code import path correctness

### Test-Driven Development
- Write tests FIRST (RED)
- Implement minimal code (GREEN)
- Refactor for quality (REFACTOR)

### Mock Usage Policy
**From Spec**: Targeted fakes with **strong preference for real servers**
- Devcontainer guarantees Pyright, gopls, typescript-language-server, OmniSharp availability
- Use `FakeLspAdapter` **only** for service-layer unit test isolation
- Integration tests **MUST** use real LSP servers
- No mocking of LSP protocol communication or SolidLSP internals

### Test Documentation
Every test must include:
```python
"""
Purpose: [what truth this test proves]
Quality Contribution: [how this prevents bugs]
Acceptance Criteria: [measurable assertions]
"""
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

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 0.1 | [ ] | Add Pyright to devcontainer | 1 | `which pyright-langserver` returns path | - | npm global install |
| 0.2 | [ ] | Add gopls to devcontainer | 1 | `which gopls` returns path | - | Go feature includes gopls |
| 0.3 | [ ] | Add typescript-language-server | 1 | `which typescript-language-server` returns path | - | npm global install |
| 0.4 | [ ] | Add OmniSharp to devcontainer | 2 | `dotnet tool list -g` shows omnisharp | - | .NET SDK required |
| 0.5 | [ ] | Create verification script | 1 | Script exits 0 when all servers found | - | scripts/verify-lsp-servers.sh |
| 0.6 | [ ] | Add to postCreateCommand | 1 | Servers installed on container rebuild | - | |

### Test Examples

```bash
#!/bin/bash
# scripts/verify-lsp-servers.sh
"""
Purpose: Verify all LSP servers are installed and accessible
Quality Contribution: Prevents CI failures from missing servers
Acceptance Criteria: All 4 servers respond to --version
"""

set -e

echo "Verifying LSP servers..."

which pyright-langserver && pyright-langserver --version && echo "✓ Pyright"
which gopls && gopls version && echo "✓ gopls"
which typescript-language-server && typescript-language-server --version && echo "✓ TypeScript"
dotnet tool list -g | grep -i omnisharp && echo "✓ OmniSharp"

echo "All LSP servers verified!"
```

### Acceptance Criteria
- [ ] All 4 LSP servers available via `which` command
- [ ] Verification script passes in devcontainer
- [ ] Servers persist across container rebuilds
- [ ] CI workflow can validate server availability

### Commands to Run
```bash
# Verify all LSP servers are installed
which pyright && pyright --version && echo "✓ Pyright"
which gopls && gopls version && echo "✓ gopls"
which typescript-language-server && typescript-language-server --version && echo "✓ TypeScript"
dotnet tool list -g | grep -i omnisharp && echo "✓ OmniSharp"

# Run verification script
bash scripts/verify-lsp-servers.sh

# Expected: All commands exit 0, script outputs "All LSP servers verified!"
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

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 0b.1 | [x] | Create scripts/lsp/ directory | 1 | Directory exists | [📋](tasks/phase-0b-multi-project-research/execution.log.md) | Complete |
| 0b.2 | [x] | Create multi-project test fixtures | 2 | Fixtures have nested project roots | [📋](tasks/phase-0b-multi-project-research/execution.log.md) | Python, TS, Go, C# |
| 0b.3 | [x] | Write project root detection script | 2 | Script finds marker files | [📋](tasks/phase-0b-multi-project-research/execution.log.md) | .csproj, go.mod, tsconfig.json, pyproject.toml |
| 0b.4 | [x] | Test "deepest wins" algorithm | 2 | Correct root for nested projects | [📋](tasks/phase-0b-multi-project-research/execution.log.md) | |
| 0b.5 | [x] | Document detection algorithm | 1 | README in scripts/lsp/ | [📋](tasks/phase-0b-multi-project-research/execution.log.md) | |
| 0b.6 | [x] | **Subtask 001**: Validate SolidLSP cross-file refs | 3 | 4/4 languages pass | [📋](tasks/phase-0b-multi-project-research/001-subtask-validate-lsp-cross-file.execution.log.md) | [^3][^4][^5][^6] |

### Test Examples

```python
# scripts/lsp/detect_project_root.py
"""
Purpose: Research script for project root detection algorithm
Quality Contribution: Validates "deepest wins" rule before production implementation
Acceptance Criteria: Correctly identifies project root for nested structures
"""

MARKER_FILES = {
    'python': ['pyproject.toml', 'setup.py', 'setup.cfg'],
    'go': ['go.mod'],
    'typescript': ['tsconfig.json', 'package.json'],
    'csharp': ['.csproj', '.sln'],
}

def find_project_root(file_path: Path, language: str) -> Path | None:
    """Find deepest project root containing file."""
    markers = MARKER_FILES.get(language, [])
    current = file_path.parent
    deepest_root = None

    while current != current.parent:
        for marker in markers:
            if (current / marker).exists():
                deepest_root = current  # Keep searching for deeper
        current = current.parent

    return deepest_root
```

### Acceptance Criteria
- [ ] Detection algorithm documented in README
- [ ] Test fixtures validate detection for all 4 languages
- [ ] "Most specific (deepest) wins" rule implemented
- [ ] Edge cases documented (no marker found, multiple markers)

### Commands to Run
```bash
# Verify research directory exists
ls -la scripts/lsp/

# Verify test fixtures exist
ls -la tests/fixtures/samples/python_multi_project/ 2>/dev/null || echo "Create Python fixtures"
ls -la tests/fixtures/samples/go_project/ 2>/dev/null || echo "Create Go fixtures"

# Run detection algorithm validation
python scripts/lsp/detect_project_root.py tests/fixtures/samples/python_multi_project/nested/app.py
# Expected: Outputs correct project root path

# Verify README documentation
cat scripts/lsp/README.md | head -20
```

---

### Phase 1: Vendor SolidLSP Core

**Objective**: Copy SolidLSP files (~25K LOC) to `src/fs2/vendors/solidlsp/` with import paths updated.

**Deliverables**:
- Vendored SolidLSP code in `src/fs2/vendors/solidlsp/`
- Updated import paths throughout vendored code
- `THIRD_PARTY_LICENSES` file with MIT attribution
- Import verification test

**Dependencies**: None (can run parallel with Phase 0/0b)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SolidLSP has Serena-specific code | Medium | Medium | Stub out non-essential imports |
| Import path changes break code | Medium | Low | Systematic find/replace, test coverage |
| Hidden dependencies | Low | Medium | Review imports before vendoring |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 1.1 | [ ] | Write import verification test | 1 | Test fails (code not yet vendored) | - | TDD: test first |
| 1.2 | [ ] | Create vendors/solidlsp/ directory structure | 1 | Directory exists with __init__.py | - | |
| 1.3 | [ ] | Copy SolidLSP core files | 2 | ls.py, ls_handler.py, ls_types.py, etc. present | - | ~12K LOC core |
| 1.4 | [ ] | Copy language server configs | 2 | All 40+ language configs present | - | ~13K LOC configs |
| 1.5 | [ ] | Update import paths systematically | 2 | sed/awk transformation complete | - | solidlsp.* → fs2.vendors.solidlsp.* |
| 1.6 | [ ] | Stub out Serena-specific imports | 2 | No references to serena.* modules | - | |
| 1.7 | [ ] | Run import verification test | 1 | Test passes | - | TDD: green |
| 1.8 | [ ] | Create THIRD_PARTY_LICENSES | 1 | MIT license with Oraios AI, Microsoft attribution | - | AC02 |
| 1.9 | [ ] | Create VENDOR_VERSION file | 1 | Records upstream commit SHA and date | - | Upstream tracking |

### Test Examples

```python
# tests/unit/vendors/test_solidlsp_imports.py
"""
Purpose: Verify all vendored SolidLSP modules are importable
Quality Contribution: Catches broken import paths from vendoring
Acceptance Criteria: All core modules import without error
"""

import pytest

class TestSolidLspVendorImports:
    def test_given_vendored_solidlsp_when_importing_core_then_succeeds(self):
        """AC03: Vendored code passes import test."""
        from fs2.vendors.solidlsp.ls import SolidLanguageServer
        from fs2.vendors.solidlsp.ls_handler import LspHandler
        from fs2.vendors.solidlsp.ls_types import LspServerConfig
        from fs2.vendors.solidlsp.ls_exceptions import LspException

        assert SolidLanguageServer is not None
        assert LspHandler is not None

    def test_given_vendored_solidlsp_when_importing_language_configs_then_succeeds(self):
        """Verify language server configs are importable."""
        from fs2.vendors.solidlsp.language_servers.pyright_server import PyrightServer
        from fs2.vendors.solidlsp.language_servers.gopls import GoplsServer

        assert PyrightServer is not None
        assert GoplsServer is not None
```

### Acceptance Criteria
- [ ] AC01: All SolidLSP files (~25K LOC) copied to `src/fs2/vendors/solidlsp/`
- [ ] AC02: `THIRD_PARTY_LICENSES` includes MIT license with Oraios AI and Microsoft
- [ ] AC03: `python -c "from fs2.vendors.solidlsp.ls import SolidLanguageServer"` succeeds
- [ ] No Serena-specific imports remain
- [ ] All import paths updated to fs2.vendors.solidlsp.*
- [ ] `VENDOR_VERSION` file exists with upstream commit SHA and vendoring date

### Commands to Run
```bash
# Verify vendored code structure
ls -la src/fs2/vendors/solidlsp/
ls -la src/fs2/vendors/solidlsp/language_servers/

# Test imports (AC03)
python -c "from fs2.vendors.solidlsp.ls import SolidLanguageServer; print('✓ Core import')"
python -c "from fs2.vendors.solidlsp.language_servers.pyright_server import PyrightServer; print('✓ Pyright')"

# Run unit tests
pytest tests/unit/vendors/test_solidlsp_imports.py -v

# Verify no Serena-specific imports remain
grep -r "from serena" src/fs2/vendors/solidlsp/ && echo "ERROR: Serena imports found" || echo "✓ No Serena imports"

# Verify THIRD_PARTY_LICENSES exists
cat THIRD_PARTY_LICENSES | head -30

# Verify VENDOR_VERSION exists with commit SHA
cat src/fs2/vendors/solidlsp/VENDOR_VERSION
# Expected format:
# upstream_repo: https://github.com/oraios/serena
# commit_sha: <40-char-sha>
# vendored_date: YYYY-MM-DD

# Lint vendored code
ruff check src/fs2/vendors/solidlsp/ --select=E,F
```

---

### Phase 2: LspAdapter ABC and Exceptions

**Objective**: Create the `LspAdapter` ABC interface and exception hierarchy following fs2 patterns.

**Deliverables**:
- `LspAdapter` ABC in `src/fs2/core/adapters/lsp_adapter.py`
- `FakeLspAdapter` test double in `src/fs2/core/adapters/lsp_adapter_fake.py`
- `LspAdapterError` hierarchy in `src/fs2/core/adapters/exceptions.py`
- `LspConfig` in `src/fs2/config/objects.py`
- ABC contract tests

**Dependencies**: None (can run parallel with Phase 1)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Interface design wrong | Medium | High | Review against SolidLSP capabilities |
| Exception messages not actionable | Low | Medium | Test each message includes fix command |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 2.1 | [ ] | Write ABC contract tests | 2 | Tests define expected interface | - | TDD: test first |
| 2.2 | [ ] | Write FakeLspAdapter tests | 2 | Tests for call_history, set_response, set_error | - | TDD: test first |
| 2.3 | [ ] | Add LspAdapterError hierarchy to exceptions.py | 2 | NotFound, Crash, Timeout, Initialization errors | - | AC07 |
| 2.4 | [ ] | Create LspAdapter ABC | 2 | Interface with initialize, shutdown, get_references | - | AC04 |
| 2.5 | [ ] | Create FakeLspAdapter | 2 | Inherits ABC, has call_history | - | AC06 |
| 2.6 | [ ] | Add LspConfig to config/objects.py | 1 | Config type for server settings | - | |
| 2.7 | [ ] | Run all tests green | 1 | All Phase 2 tests pass | - | TDD: green |

### Test Examples

```python
# tests/unit/adapters/test_lsp_adapter.py
"""
Purpose: Verify LspAdapter ABC contract is correct
Quality Contribution: Ensures adapter interface matches spec requirements
Acceptance Criteria: ABC defines all required methods
"""

import pytest
from abc import ABC
from fs2.core.adapters.lsp_adapter import LspAdapter

class TestLspAdapterABC:
    def test_given_lsp_adapter_when_checking_inheritance_then_is_abc(self):
        """AC04: LspAdapter is an ABC."""
        assert issubclass(LspAdapter, ABC)

    def test_given_lsp_adapter_when_checking_methods_then_has_required_interface(self):
        """AC04: LspAdapter defines language-agnostic interface."""
        assert hasattr(LspAdapter, 'initialize')
        assert hasattr(LspAdapter, 'shutdown')
        assert hasattr(LspAdapter, 'get_references')
        assert hasattr(LspAdapter, 'get_definition')
        assert hasattr(LspAdapter, 'is_ready')

    def test_given_lsp_adapter_when_get_references_then_returns_code_edges(self):
        """AC04: Interface returns CodeEdge instances only."""
        from inspect import signature
        sig = signature(LspAdapter.get_references)
        # Return type should be list[CodeEdge]
        assert 'CodeEdge' in str(sig.return_annotation)


# tests/unit/adapters/test_lsp_adapter_fake.py
"""
Purpose: Verify FakeLspAdapter behaves correctly for testing
Quality Contribution: Enables isolated service layer testing
Acceptance Criteria: Fake supports set_response, set_error, call_history
"""

class TestFakeLspAdapter:
    def test_given_fake_adapter_when_set_response_then_returns_configured_edges(self):
        """AC06: FakeLspAdapter has call_history tracking."""
        from fs2.core.adapters.lsp_adapter_fake import FakeLspAdapter
        from fs2.core.models.code_edge import CodeEdge, EdgeType
        from tests.helpers.fake_config import FakeConfigurationService

        config = FakeConfigurationService()
        adapter = FakeLspAdapter(config)

        expected = [CodeEdge(
            source_node_id="file:a.py",
            target_node_id="file:b.py",
            edge_type=EdgeType.REFERENCES,
            confidence=1.0,
            resolution_rule="lsp:references"
        )]
        adapter.set_response(expected)

        result = adapter.get_references("a.py", 10, 5)

        assert result == expected
        assert len(adapter.call_history) == 1
        assert adapter.call_history[0]['method'] == 'get_references'
```

### Non-Happy-Path Coverage
- [ ] LspServerNotFoundError includes install command
- [ ] LspServerCrashError includes server name and exit code
- [ ] LspTimeoutError includes operation and timeout value
- [ ] LspInitializationError includes root cause

### Acceptance Criteria
- [ ] AC04: `LspAdapter` ABC defines language-agnostic interface returning `CodeEdge` only
- [ ] AC06: `FakeLspAdapter` inherits from ABC with `call_history` tracking
- [ ] AC07: Adapter raises `LspAdapterError` hierarchy (NotFound, StartError, Timeout, NotSupported)
- [ ] All error messages include actionable fix instructions
- [ ] Tests pass with FakeLspAdapter

### Commands to Run
```bash
# Run ABC contract tests
pytest tests/unit/adapters/test_lsp_adapter.py -v

# Run FakeLspAdapter tests
pytest tests/unit/adapters/test_lsp_adapter_fake.py -v

# Run all Phase 2 tests together
pytest tests/unit/adapters/test_lsp_adapter*.py -v

# Verify exception hierarchy
python -c "from fs2.core.adapters.exceptions import LspAdapterError, LspServerNotFoundError; print('✓ Exceptions')"

# Verify LspConfig registered
python -c "from fs2.config.objects import LspConfig; print('✓ LspConfig')"

# Lint new adapter code
ruff check src/fs2/core/adapters/lsp_adapter*.py
mypy src/fs2/core/adapters/lsp_adapter*.py --strict
```

---

### Phase 3: SolidLspAdapter Implementation

**Objective**: Implement `SolidLspAdapter` wrapping vendored SolidLSP with Pyright integration.

**Deliverables**:
- `SolidLspAdapter` in `src/fs2/core/adapters/lsp_adapter_solidlsp.py`
- LSP response → CodeEdge translation
- Pyright integration tests with real server
- Exception translation at boundary

**Dependencies**: Phase 1 (vendored code), Phase 2 (ABC interface)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SolidLSP API differs from expected | Medium | Medium | Review SolidLSP source first |
| Pyright not available in test | Low | High | Phase 0 ensures availability |
| Type translation errors | Medium | Medium | Comprehensive test coverage |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 3.1 | [ ] | Write integration tests for Pyright | 2 | Tests use real Pyright server | - | TDD: test first |
| 3.2 | [ ] | Write unit tests for type translation | 2 | Tests for LSP → CodeEdge conversion | - | TDD: test first |
| 3.3 | [ ] | Implement SolidLspAdapter skeleton | 2 | Class inherits LspAdapter, receives ConfigurationService | - | AC05 |
| 3.4 | [ ] | Implement initialize() with stdout isolation | 2 | Server starts, stdout captured | - | Discovery 01 |
| 3.5 | [ ] | Implement shutdown() with process tree cleanup | 2 | All child processes terminated | - | Discovery 02 |
| 3.6 | [ ] | Implement get_references() | 3 | Returns CodeEdge list with confidence=1.0 | - | AC08 |
| 3.7 | [ ] | Implement get_definition() | 2 | Returns CodeEdge with appropriate EdgeType | - | AC09 |
| 3.8 | [ ] | Implement exception translation | 2 | SolidLSP errors → domain exceptions | - | AC05 |
| 3.9 | [ ] | Add psutil optional dependency | 1 | pyproject.toml updated | - | |
| 3.10 | [ ] | Run all tests green | 1 | Integration + unit tests pass | - | TDD: green |

### Test Examples

```python
# tests/integration/test_lsp_pyright.py
"""
Purpose: Verify SolidLspAdapter works with real Pyright server
Quality Contribution: Validates end-to-end LSP communication
Acceptance Criteria: Real LSP server returns valid references
"""

import shutil
import pytest
from pathlib import Path
from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter
from fs2.core.models.code_edge import EdgeType

# Skip if Pyright not installed
pytestmark = pytest.mark.skipif(
    not shutil.which('pyright'),
    reason="Pyright not installed"
)

class TestPyrightIntegration:
    @pytest.fixture
    def python_project(self, tmp_path):
        """Create minimal Python project with known references."""
        # lib.py
        (tmp_path / "lib.py").write_text("def helper(): pass")
        # app.py
        (tmp_path / "app.py").write_text("""
from lib import helper

def main():
    helper()
""")
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        return tmp_path

    def test_given_python_project_when_get_references_then_returns_code_edges(
        self, python_project, config_service
    ):
        """AC17: Integration tests with real Pyright server."""
        adapter = SolidLspAdapter(config_service)
        adapter.initialize("python", python_project)

        try:
            # Get references to helper function in lib.py line 1
            edges = adapter.get_references(
                python_project / "lib.py", line=1, column=5
            )

            assert len(edges) >= 1
            assert all(e.edge_type == EdgeType.REFERENCES for e in edges)
            assert all(e.confidence == 1.0 for e in edges)
            assert all(e.resolution_rule == "lsp:references" for e in edges)
        finally:
            adapter.shutdown()


# tests/unit/adapters/test_lsp_type_translation.py
"""
Purpose: Verify LSP responses correctly translate to CodeEdge
Quality Contribution: Ensures type boundary is correct
Acceptance Criteria: All LSP location types map to CodeEdge
"""

class TestLspTypeTranslation:
    def test_given_lsp_location_when_translating_then_creates_code_edge(self):
        """AC08: textDocument/references → CodeEdge with REFERENCES."""
        from fs2.core.adapters.lsp_adapter_solidlsp import _translate_reference

        lsp_location = {
            "uri": "file:///project/lib.py",
            "range": {"start": {"line": 10, "character": 5}}
        }

        edge = _translate_reference(
            source_file="app.py",
            source_line=15,
            target_location=lsp_location
        )

        assert edge.source_node_id == "file:app.py"
        assert edge.target_node_id == "file:lib.py"
        assert edge.edge_type == EdgeType.REFERENCES
        assert edge.confidence == 1.0
        assert edge.resolution_rule == "lsp:references"
```

### Non-Happy-Path Coverage
- [ ] Server not found → LspServerNotFoundError with install command
- [ ] Server crashes → LspServerCrashError with exit code
- [ ] Timeout → LspTimeoutError with operation name
- [ ] Invalid response → graceful handling, return empty list

### Acceptance Criteria
- [ ] AC05: `SolidLspAdapter` wraps SolidLSP with exception translation
- [ ] AC08: LSP `textDocument/references` → `CodeEdge` with `EdgeType.REFERENCES`
- [ ] AC09: LSP `textDocument/definition` → `CodeEdge` with appropriate EdgeType
- [ ] AC10: All LSP-derived edges have `confidence=1.0` and `resolution_rule="lsp:{method}"`
- [ ] AC17: Integration tests pass with real Pyright server
- [ ] Stdout isolation prevents JSON-RPC corruption
- [ ] Process tree cleanup prevents orphaned processes

### Commands to Run
```bash
# Run unit tests for type translation
pytest tests/unit/adapters/test_lsp_type_translation.py -v

# Run Pyright integration tests (requires Pyright installed)
pytest tests/integration/test_lsp_pyright.py -v

# Run all Phase 3 tests
pytest tests/unit/adapters/test_lsp_*.py tests/integration/test_lsp_pyright.py -v

# Verify psutil optional dependency
python -c "import psutil; print(f'✓ psutil {psutil.__version__}')" || echo "psutil not installed (optional)"

# Lint SolidLspAdapter implementation
ruff check src/fs2/core/adapters/lsp_adapter_solidlsp.py
mypy src/fs2/core/adapters/lsp_adapter_solidlsp.py --strict

# Verify no orphaned processes after test
ps aux | grep -E "pyright|gopls" | grep -v grep || echo "✓ No orphaned LSP processes"
```

---

### Phase 4: Multi-Language LSP Support

**Objective**: Extend SolidLspAdapter to support gopls, TypeScript, and OmniSharp.

**Deliverables**:
- gopls integration tests
- TypeScript language server integration tests
- OmniSharp integration tests
- Per-language configuration in LspConfig

**Dependencies**: Phase 3 (SolidLspAdapter working with Pyright)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Server-specific quirks | Medium | Medium | Test each server independently |
| OmniSharp requires .NET | Low | Low | Phase 0 ensures availability |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 4.1 | [ ] | Write gopls integration tests | 2 | Tests with real gopls server | - | AC12 |
| 4.2 | [ ] | Verify gopls support works | 2 | Tests pass | - | |
| 4.3 | [ ] | Write TypeScript integration tests | 2 | Tests with real TS server | - | AC13 |
| 4.4 | [ ] | Verify TypeScript support works | 2 | Tests pass | - | |
| 4.5 | [ ] | Write OmniSharp integration tests | 2 | Tests with real OmniSharp | - | AC14 |
| 4.6 | [ ] | Verify OmniSharp support works | 2 | Tests pass | - | |
| 4.7 | [ ] | Add per-language wait configuration | 1 | LspConfig has per-language settings | - | Discovery 10 |
| 4.8 | [ ] | Document any per-language code needed | 1 | Report to user if any | - | User request |

### Test Examples

```python
# tests/integration/test_lsp_gopls.py
"""
Purpose: Verify SolidLspAdapter works with gopls
Quality Contribution: Validates Go language support
Acceptance Criteria: gopls returns valid references
"""

import shutil
import pytest
from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

pytestmark = pytest.mark.skipif(
    not shutil.which('gopls'),
    reason="gopls not installed"
)

class TestGoplsIntegration:
    @pytest.fixture
    def go_project(self, tmp_path):
        """Create minimal Go project."""
        (tmp_path / "go.mod").write_text("module test\ngo 1.21")
        (tmp_path / "lib.go").write_text("package main\nfunc Helper() {}")
        (tmp_path / "main.go").write_text("""package main

func main() {
    Helper()
}
""")
        return tmp_path

    def test_given_go_project_when_get_references_then_returns_code_edges(
        self, go_project, config_service
    ):
        """AC12: Go support via gopls."""
        adapter = SolidLspAdapter(config_service)
        adapter.initialize("go", go_project)

        try:
            edges = adapter.get_references(
                go_project / "lib.go", line=2, column=6
            )

            assert len(edges) >= 1
            assert all(e.confidence == 1.0 for e in edges)
        finally:
            adapter.shutdown()
```

### Acceptance Criteria
- [ ] AC11: Python support via Pyright (from Phase 3)
- [ ] AC12: Go support via gopls with installation instructions
- [ ] AC13: TypeScript support via typescript-language-server
- [ ] AC14: C# support via OmniSharp
- [ ] AC18: Integration tests pass with all 4 real servers
- [ ] Any per-language code documented and reported

### Commands to Run
```bash
# Run gopls integration tests
pytest tests/integration/test_lsp_gopls.py -v

# Run TypeScript integration tests
pytest tests/integration/test_lsp_typescript.py -v

# Run OmniSharp integration tests
pytest tests/integration/test_lsp_omnisharp.py -v

# Run ALL integration tests (all 4 languages)
pytest tests/integration/test_lsp_*.py -v

# Verify all servers are available
which pyright && which gopls && which typescript-language-server && dotnet tool list -g | grep -i omnisharp

# Report any per-language code needed
echo "Check implementation for per-language code outside SolidLSP configs"
grep -r "if.*language.*==" src/fs2/core/adapters/lsp_adapter_solidlsp.py || echo "✓ No per-language branching"
```

---

### Phase 5: Python Import Extraction

**Objective**: Implement Python import extraction with high accuracy using Tree-sitter queries.

**Deliverables**:
- RelationshipExtractionService (core service)
- PythonImportExtractor (language-specific)
- Confidence scoring for Python imports
- Integration with existing fixtures

**Dependencies**: Phase 1 complete (024 foundation models)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Tree-sitter API changes | Low | Medium | Pin tree-sitter-language-pack version |
| Import resolution ambiguity | Medium | Low | Use 0.9 confidence for unambiguous, lower for relative |
| Namespace package handling | Medium | Low | Document as known limitation initially |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 5.1 | [ ] | Write tests for Python import extraction | 2 | Tests cover: from X import Y, import X, import X as Y, relative imports | - | Use fixtures from 022 |
| 5.2 | [ ] | Create RelationshipExtractionService ABC | 1 | ABC defined with extract() method signature | - | `src/fs2/core/services/relationship_extraction/` |
| 5.3 | [ ] | Implement PythonImportExtractor | 3 | All tests from 5.1 pass | - | Use tree-sitter queries from 022 |
| 5.4 | [ ] | Write tests for import-to-file resolution | 2 | Tests cover: same-directory, relative path, absolute path, not found | - | |
| 5.5 | [ ] | Implement import path resolver | 2 | Tests from 5.4 pass; resolves import names to file node_ids | - | |
| 5.6 | [ ] | Write confidence scoring tests | 2 | Tests cover: top-level (0.9), function-scoped (0.6), relative (0.7) | - | |
| 5.7 | [ ] | Implement confidence calculator | 2 | Tests from 5.6 pass | - | |
| 5.8 | [ ] | Integration test with real Python fixtures | 2 | app_service.py imports detected with correct targets | - | Use 022 fixtures |

### Test Examples

```python
# File: tests/unit/services/test_python_import_extractor.py

class TestPythonImportExtractor:
    def test_given_from_import_when_extract_then_finds_module(self):
        """
        Purpose: Proves from X import Y creates edge to X
        Quality Contribution: Core import detection for Python
        Acceptance Criteria: Edge from source to target with confidence >= 0.85
        """
        # Arrange
        source_content = "from auth_handler import AuthHandler"
        node = create_code_node(content=source_content, language="python")
        all_nodes = [
            node,
            create_code_node(node_id="file:auth_handler.py"),
        ]

        # Act
        extractor = PythonImportExtractor()
        edges = extractor.extract(node, all_nodes)

        # Assert
        assert len(edges) == 1
        assert edges[0].target_node_id == "file:auth_handler.py"
        assert edges[0].edge_type == EdgeType.IMPORTS
        assert edges[0].confidence >= 0.85
```

### Non-Happy-Path Coverage
- [ ] Import of non-existent module returns edge with lower confidence
- [ ] Circular import detection (A imports B imports A)
- [ ] Star import handling (from X import *)
- [ ] Type-only imports (TYPE_CHECKING blocks)

### Acceptance Criteria
- [ ] Python file with `from auth_handler import AuthHandler` creates edge with confidence >= 0.85
- [ ] Import extraction accuracy matches 022 validation (100% for Python)
- [ ] All tests passing
- [ ] Test coverage > 80%

### Commands to Run
```bash
# Run Python import extraction tests
pytest tests/unit/services/test_python_import_extractor.py -v

# Run confidence scoring tests
pytest tests/unit/services/test_confidence_scoring.py -v

# Run all Phase 5 tests
pytest tests/unit/services/test_python_import*.py -v

# Verify with real fixtures
pytest tests/integration/test_python_import_integration.py -v

# Lint new service code
ruff check src/fs2/core/services/relationship_extraction/
mypy src/fs2/core/services/relationship_extraction/ --strict
```

---

### Phase 6: Node ID and Filename Detection

**Objective**: Detect explicit fs2 node_id patterns and raw filenames in text files.

**Deliverables**:
- NodeIdDetector for explicit node_id patterns (confidence 1.0)
- RawFilenameDetector for heuristic filename detection (confidence 0.4-0.5)
- Integration with text/markdown file types

**Dependencies**: Phase 1 complete (024 foundation models), can run parallel with Phase 5

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| False positives in raw filename | High | Low | Use low confidence (0.4-0.5) to signal uncertainty |
| Node ID pattern conflicts with URLs | Low | Low | Require exact pattern match with word boundaries |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 6.1 | [ ] | Write tests for node_id pattern detection | 2 | Tests cover: file:, callable:, class:, method:, type: patterns | - | |
| 6.2 | [ ] | Implement NodeIdDetector | 2 | All tests from 6.1 pass; uses regex from 022 experiments | - | Port from `01_nodeid_detection.py` |
| 6.3 | [ ] | Write tests for raw filename detection | 2 | Tests cover: backtick quoted (0.5), bare inline (0.4), extension filtering | - | |
| 6.4 | [ ] | Implement RawFilenameDetector | 2 | All tests from 6.3 pass | - | Port from 022 experiments |
| 6.5 | [ ] | Write integration tests with markdown fixtures | 2 | execution-log.md references detected | - | Use 022 fixtures |
| 6.6 | [ ] | Combine detectors in TextReferenceExtractor | 1 | Single extractor handles both patterns | - | |

### Test Examples

```python
# File: tests/unit/services/test_nodeid_detector.py

class TestNodeIdDetector:
    def test_given_explicit_nodeid_when_detect_then_confidence_1_0(self):
        """
        Purpose: Proves explicit node_id patterns have highest confidence
        Quality Contribution: Exact node_id detection
        Acceptance Criteria: Confidence = 1.0 for explicit patterns
        """
        content = "See callable:src/calc.py:Calculator.add for details"
        detector = NodeIdDetector()

        matches = detector.detect(content)

        assert len(matches) == 1
        assert matches[0].target_node_id == "callable:src/calc.py:Calculator.add"
        assert matches[0].confidence == 1.0

class TestRawFilenameDetector:
    def test_given_backtick_quoted_filename_when_detect_then_confidence_0_5(self):
        """
        Purpose: Proves quoted filenames get higher confidence than bare
        Quality Contribution: Raw filename detection with appropriate confidence
        """
        content = "See `auth_handler.py` for authentication logic"
        detector = RawFilenameDetector()

        matches = detector.detect(content)

        assert len(matches) == 1
        assert "auth_handler.py" in matches[0].target_node_id
        assert matches[0].confidence == 0.5
```

### Non-Happy-Path Coverage
- [ ] URL that looks like filename (github.com) filtered appropriately
- [ ] Node ID with missing parts handled gracefully
- [ ] Binary file content skipped

### Acceptance Criteria
- [ ] Markdown with `callable:src/calc.py:Calculator.add` creates edge with confidence = 1.0
- [ ] README with `auth_handler.py` creates edge with confidence 0.4-0.5
- [ ] All tests passing
- [ ] Test coverage > 80%

### Commands to Run
```bash
# Run node_id detection tests
pytest tests/unit/services/test_nodeid_detector.py -v

# Run raw filename detection tests
pytest tests/unit/services/test_raw_filename_detector.py -v

# Run all Phase 6 tests
pytest tests/unit/services/test_nodeid*.py tests/unit/services/test_raw_filename*.py -v

# Run integration tests with markdown
pytest tests/integration/test_text_reference_integration.py -v

# Lint detector code
ruff check src/fs2/core/services/relationship_extraction/
mypy src/fs2/core/services/relationship_extraction/ --strict
```

---

### Phase 7: TypeScript and Go Imports

**Objective**: Extend import extraction to TypeScript and Go languages.

**Deliverables**:
- TypeScriptImportExtractor
- GoImportExtractor
- Language registry for extractor selection

**Dependencies**: Phase 5 complete (uses same patterns)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| TypeScript type-only imports | Medium | Low | Lower confidence for type-only (0.5) |
| Go dot imports | Low | Low | Handle with 0.4 confidence |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 7.1 | [ ] | Write tests for TypeScript import extraction | 2 | Tests cover: ES modules, type-only imports, re-exports | - | |
| 7.2 | [ ] | Implement TypeScriptImportExtractor | 2 | All tests from 7.1 pass | - | Tree-sitter queries from 022 |
| 7.3 | [ ] | Write tests for Go import extraction | 2 | Tests cover: single import, grouped imports, dot imports, blank imports | - | |
| 7.4 | [ ] | Implement GoImportExtractor | 2 | All tests from 7.3 pass | - | |
| 7.5 | [ ] | Create language extractor registry | 1 | Registry returns correct extractor for language | - | |
| 7.6 | [ ] | Integration test with index.ts and Go fixtures | 2 | Imports detected correctly | - | |

### Test Examples

```python
# File: tests/unit/services/test_typescript_import_extractor.py

class TestTypeScriptImportExtractor:
    def test_given_es_module_import_when_extract_then_finds_module(self):
        """
        Purpose: Proves ES module imports create edges
        Quality Contribution: TypeScript import detection
        """
        source_content = "import { AuthService } from './auth-service';"
        node = create_code_node(content=source_content, language="typescript")

        extractor = TypeScriptImportExtractor()
        edges = extractor.extract(node, [])

        assert len(edges) >= 1
        assert edges[0].edge_type == EdgeType.IMPORTS
        assert edges[0].confidence >= 0.85
```

### Non-Happy-Path Coverage
- [ ] Dynamic imports (import()) handled or skipped
- [ ] Namespace imports (import * as X)
- [ ] Go underscore imports (import _ "pkg")

### Acceptance Criteria
- [ ] TypeScript imports extracted with same accuracy as 022 validation
- [ ] Go imports extracted with same accuracy as 022 validation
- [ ] All tests passing
- [ ] Test coverage > 80%

### Commands to Run
```bash
# Run TypeScript import tests
pytest tests/unit/services/test_typescript_import_extractor.py -v

# Run Go import tests
pytest tests/unit/services/test_go_import_extractor.py -v

# Run all Phase 7 tests
pytest tests/unit/services/test_typescript*.py tests/unit/services/test_go*.py -v

# Run integration tests
pytest tests/integration/test_import_integration.py -v

# Lint extractor code
ruff check src/fs2/core/services/relationship_extraction/
mypy src/fs2/core/services/relationship_extraction/ --strict
```

---

### Phase 8: Pipeline Integration

**Objective**: Wire all relationship extraction components into the scan pipeline. Integrate LSP adapter, import extractors, node ID detection, and filename detection into a unified RelationshipExtractionStage. LSP enabled by default with `--no-lsp` flag to disable.

**Deliverables**:
- RelationshipExtractionStage (pipeline stage orchestrating all extractors)
- ScanPipeline modifications for stage injection
- StorageStage extension for relationship persistence
- `--no-lsp` CLI flag to disable LSP extraction
- Metrics and progress reporting
- Graceful degradation when LSP servers unavailable
- Edge deduplication (highest confidence wins)

**Dependencies**: Phases 3-4 (LSP adapter), Phases 5-7 (all extractors complete)

#### Pipeline Architecture

**Current Scan Pipeline (5 stages):**
```
┌─────────────┐   ┌──────────────┐   ┌──────────────────┐   ┌────────────────┐   ┌──────────────┐
│ Discovery   │ → │ Parsing      │ → │ SmartContent     │ → │ Embedding      │ → │ Storage      │
│ (files)     │   │ (AST/nodes)  │   │ (AI summaries)   │   │ (vectors)      │   │ (persist)    │
└─────────────┘   └──────────────┘   └──────────────────┘   └────────────────┘   └──────────────┘
```

**New Pipeline with Relationship Extraction (6 stages):**
```
┌─────────────┐   ┌──────────────┐   ┌──────────────────────┐   ┌──────────────────┐   ┌────────────────┐   ┌──────────────┐
│ Discovery   │ → │ Parsing      │ → │ Relationship         │ → │ SmartContent     │ → │ Embedding      │ → │ Storage      │
│ (files)     │   │ (AST/nodes)  │   │ Extraction           │   │ (AI summaries)   │   │ (vectors)      │   │ (persist)    │
└─────────────┘   └──────────────┘   └──────────────────────┘   └──────────────────┘   └────────────────┘   └──────────────┘
                                              ↓
                                     Multiple extraction sources
                                     (see below)
                                              ↓
                                     Outputs: list[CodeEdge]
                                     with varying confidence
```

#### Relationship Extraction Sources

The `RelationshipExtractionStage` extracts edges from **multiple sources**:

| Source | Method | Confidence | EdgeType | Example |
|--------|--------|------------|----------|---------|
| **Node ID References** | Regex detection | **1.0** | REFERENCES/DOCUMENTS | `method:src/auth.py:Auth.login` in README |
| **LSP References** | LspAdapter queries | **1.0** | REFERENCES/CALLS | `textDocument/references` response |
| **Import Statements** | Tree-sitter AST | **0.9** | IMPORTS | `from auth import Auth` |
| **Cross-Language Refs** | Line scanning | **0.7** | REFERENCES | Dockerfile `COPY src/app.py` |
| **Raw Filename (quoted)** | Regex heuristic | **0.5** | REFERENCES/DOCUMENTS | `` `auth_handler.py` `` in docs |
| **Raw Filename (bare)** | Regex heuristic | **0.4** | REFERENCES/DOCUMENTS | `auth_handler.py` in prose |

**Critical: Node ID detection is highest confidence (1.0)** - enables README/docs to explicitly link to code.

#### Extractor Components

```
RelationshipExtractionStage
├── NodeIdDetector          # Regex: callable:, method:, file:, class:, type:
│   └── confidence: 1.0
│   └── EdgeType: REFERENCES or DOCUMENTS (for docs→code)
│
├── LspAdapter              # LSP server queries (optional, controlled by --no-lsp)
│   └── confidence: 1.0
│   └── EdgeType: REFERENCES, CALLS
│
├── ImportExtractors        # Tree-sitter per language
│   ├── PythonImportExtractor
│   ├── TypeScriptImportExtractor
│   └── GoImportExtractor
│   └── confidence: 0.9 (top-level), 0.6 (function-scoped)
│   └── EdgeType: IMPORTS
│
└── RawFilenameDetector     # Heuristic filename matching
    └── confidence: 0.5 (quoted), 0.4 (bare)
    └── EdgeType: REFERENCES or DOCUMENTS
```

**Why Stage Position 3 (after Parsing)?**
1. **Has nodes**: ParsingStage output available (prerequisite for querying symbols)
2. **Before storage**: StorageStage can persist edges alongside nodes
3. **Logical flow**: Structure -> Relationships -> Enrichment -> Persistence
4. **Error isolation**: Follows SmartContent/Embedding pattern (optional, collects errors)

**Key Files to Modify:**
| File | Change |
|------|--------|
| `src/fs2/core/services/scan_pipeline.py` | Add `RelationshipExtractionStage` to stage list |
| `src/fs2/core/services/pipeline_context.py` | Add `lsp_adapter`, `no_lsp`, `relationship_extraction_service` injection points |
| `src/fs2/core/services/stages/relationship_extraction_stage.py` | **NEW** - orchestrates all extractors |
| `src/fs2/core/services/stages/storage_stage.py` | Persist `context.relationships` via `graph_store.add_relationship_edge()` |
| `src/fs2/cli/scan.py` | Add `--no-lsp` flag (other extractors always run) |

**Stage Protocol Contract:**
```python
class RelationshipExtractionStage:
    """Extracts cross-file relationships from multiple sources."""

    def __init__(
        self,
        node_id_detector: NodeIdDetector,
        import_extractors: dict[str, ImportExtractor],  # keyed by language
        filename_detector: RawFilenameDetector,
        lsp_adapter: LspAdapter | None = None,  # Optional - controlled by --no-lsp
    ):
        self._node_id_detector = node_id_detector
        self._import_extractors = import_extractors
        self._filename_detector = filename_detector
        self._lsp_adapter = lsp_adapter

    @property
    def name(self) -> str:
        return "relationship_extraction"

    def process(self, context: PipelineContext) -> PipelineContext:
        if context.relationship_extraction_service is None:
            return context  # Skip if no service

        all_edges: list[CodeEdge] = []

        for node in context.nodes:
            try:
                # 1. Node ID detection (always, highest confidence)
                all_edges.extend(self._node_id_detector.extract(node))

                # 2. Import extraction (always, per language)
                extractor = self._import_extractors.get(node.language)
                if extractor:
                    all_edges.extend(extractor.extract(node, context.nodes))

                # 3. Raw filename detection (always, for docs/markdown)
                if node.language in ("markdown", "text"):
                    all_edges.extend(self._filename_detector.extract(node, context.nodes))

                # 4. LSP references (optional, controlled by --no-lsp)
                if self._lsp_adapter and not context.no_lsp:
                    try:
                        all_edges.extend(self._extract_lsp_refs(node))
                    except LspAdapterError as e:
                        context.errors.append(f"LSP: {e}")  # Collect, don't fail

            except Exception as e:
                context.errors.append(str(e))

        # Deduplicate: same source+target keeps highest confidence
        seen: dict[tuple[str, str], CodeEdge] = {}
        for edge in all_edges:
            key = (edge.source_node_id, edge.target_node_id)
            if key not in seen or edge.confidence > seen[key].confidence:
                seen[key] = edge

        # Validate targets exist (filter out edges to non-existent nodes)
        node_ids = {node.node_id for node in context.nodes}
        valid_edges = [
            edge for edge in seen.values()
            if edge.target_node_id in node_ids
        ]

        context.relationships = valid_edges
        context.metrics["relationship_extraction_count"] = len(valid_edges)
        context.metrics["relationship_extraction_before_dedup"] = len(all_edges)
        context.metrics["relationship_extraction_invalid_targets"] = len(seen) - len(valid_edges)
        return context
```

#### EdgeType Usage

| EdgeType | When to Use | Example |
|----------|-------------|---------|
| `IMPORTS` | Code file imports another | `from auth import Auth` -> edge from app.py to auth.py |
| `CALLS` | Code calls function/method | LSP finds `Auth.login()` call -> edge to auth.py |
| `REFERENCES` | General reference to code | Config file mentions `app.py` |
| `DOCUMENTS` | Documentation explicitly documents code | README explains `Auth` class via node_id |

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Performance regression on large codebases | Medium | Medium | Profile early; batch processing if needed |
| Stage ordering issues | Low | High | Follow existing stage pattern exactly |
| Performance impact from LSP | Medium | Medium | Lazy initialization, parallel queries |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 8.1 | [ ] | Write tests for RelationshipExtractionStage | 2 | Tests cover: process with nodes, empty nodes, error handling | - | |
| 8.2 | [ ] | Implement RelationshipExtractionStage | 2 | All tests from 8.1 pass | - | Follow stage pattern |
| 8.3 | [ ] | Write tests for StorageStage relationship persistence | 2 | Tests cover: relationships added to graph, metrics recorded | - | |
| 8.4 | [ ] | Extend StorageStage for relationships | 1 | Tests from 8.3 pass | - | ~10 LOC addition |
| 8.5 | [ ] | Write tests for ScanPipeline with relationship stage | 2 | Full pipeline test with relationships enabled | - | |
| 8.6 | [ ] | Modify ScanPipeline to include relationship stage | 2 | Stage runs by default; relationships populated | - | |
| 8.7 | [ ] | Write CLI flag tests for --no-lsp | 2 | Tests verify flag parsing and behavior | - | |
| 8.8 | [ ] | Add --no-lsp flag to CLI | 1 | Flag sets `context.no_lsp = True` | - | `cli/scan.py` |
| 8.9 | [ ] | Write graceful degradation tests | 2 | Tests verify scan completes without LSP | - | AC15, AC16 |
| 8.10 | [ ] | Implement LSP status reporting | 2 | Shows available/missing servers at startup | - | |
| 8.11 | [ ] | Write edge deduplication tests | 2 | Tests verify highest-confidence wins | - | Dedup logic |
| 8.12 | [ ] | Write target validation tests | 2 | Tests verify edges to non-existent nodes filtered | - | Graph integrity |
| 8.13 | [ ] | Integration test with ground truth | 2 | 10/15 ground truth entries detected (67%+ pass) | - | Use 022 ground truth |
| 8.14 | [ ] | Integration test: full scan with LSP | 2 | End-to-end scan extracts all edge types | - | |

### Test Examples

```python
# File: tests/unit/services/test_relationship_extraction_stage.py

class TestRelationshipExtractionStage:
    def test_given_nodes_with_imports_when_process_then_relationships_populated(self):
        """
        Purpose: Proves stage populates context.relationships
        Quality Contribution: Pipeline integration verification
        """
        # Arrange
        context = PipelineContext(
            nodes=[create_python_node_with_imports()],
            graph_store=FakeGraphStore(),
            relationship_extraction_service=FakeRelationshipExtractionService(),
        )
        stage = RelationshipExtractionStage()

        # Act
        result = stage.process(context)

        # Assert
        assert result.relationships is not None
        assert len(result.relationships) > 0
        assert result.metrics["relationship_extraction_count"] > 0

    def test_given_no_service_when_process_then_skips_gracefully(self):
        """Stage skipped if no relationship_extraction_service."""
        context = PipelineContext(
            nodes=[create_python_node()],
            graph_store=FakeGraphStore(),
            relationship_extraction_service=None,  # No service
        )
        stage = RelationshipExtractionStage()

        result = stage.process(context)

        assert result.relationships is None or len(result.relationships) == 0


# tests/unit/cli/test_scan_lsp_flag.py
"""
Purpose: Verify LSP is enabled by default and --no-lsp disables it
Quality Contribution: Ensures CLI interface matches spec (LSP on by default)
Acceptance Criteria: LSP runs by default, --no-lsp disables it
"""

from typer.testing import CliRunner
from fs2.cli.main import app

runner = CliRunner()

class TestScanLspFlag:
    def test_given_default_scan_when_lsp_servers_available_then_lsp_enabled(self, tmp_path):
        """LSP extraction is enabled by default."""
        result = runner.invoke(app, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        # LSP status should be shown

    def test_given_no_lsp_flag_when_scanning_then_lsp_disabled(self, tmp_path):
        """--no-lsp flag disables LSP extraction."""
        result = runner.invoke(app, ["scan", str(tmp_path), "--no-lsp"])

        assert result.exit_code == 0
        # LSP should not be mentioned or should show as disabled


# tests/unit/stages/test_edge_deduplication.py
"""
Purpose: Verify edge deduplication keeps highest confidence
Quality Contribution: Prevents duplicate edges in graph
Acceptance Criteria: Same source+target deduplicated, highest confidence wins
"""

class TestEdgeDeduplication:
    def test_given_duplicate_edges_when_processing_then_keeps_highest_confidence(self):
        """Deduplication keeps edge with highest confidence."""
        from fs2.core.models.code_edge import CodeEdge, EdgeType

        edges = [
            CodeEdge("file:a.py", "file:b.py", EdgeType.REFERENCES, 0.4, resolution_rule="filename"),
            CodeEdge("file:a.py", "file:b.py", EdgeType.IMPORTS, 0.9, resolution_rule="import:python"),
            CodeEdge("file:a.py", "file:b.py", EdgeType.REFERENCES, 1.0, resolution_rule="lsp:references"),
        ]

        # Dedup logic
        seen: dict[tuple[str, str], CodeEdge] = {}
        for edge in edges:
            key = (edge.source_node_id, edge.target_node_id)
            if key not in seen or edge.confidence > seen[key].confidence:
                seen[key] = edge

        result = list(seen.values())

        assert len(result) == 1
        assert result[0].confidence == 1.0
        assert result[0].resolution_rule == "lsp:references"


# tests/unit/stages/test_target_validation.py
"""
Purpose: Verify edges to non-existent nodes are filtered out
Quality Contribution: Ensures graph integrity - no broken references
Acceptance Criteria: Edges with invalid targets removed, metric tracks count
"""

class TestTargetValidation:
    def test_given_edge_to_nonexistent_node_when_validating_then_filtered_out(self):
        """Edges pointing to non-existent nodes are removed."""
        from fs2.core.models.code_edge import CodeEdge, EdgeType

        # Nodes that exist in graph
        existing_node_ids = {"file:a.py", "file:b.py"}

        # Edges - one valid, one to non-existent target
        edges = [
            CodeEdge("file:a.py", "file:b.py", EdgeType.IMPORTS, 0.9, "import:python"),
            CodeEdge("file:a.py", "file:deleted.py", EdgeType.REFERENCES, 1.0, "nodeid"),
        ]

        # Validation logic
        valid_edges = [e for e in edges if e.target_node_id in existing_node_ids]
        invalid_count = len(edges) - len(valid_edges)

        assert len(valid_edges) == 1
        assert valid_edges[0].target_node_id == "file:b.py"
        assert invalid_count == 1  # Track dropped edges


# tests/integration/test_scan_graceful_degradation.py
"""
Purpose: Verify scan completes even when LSP fails
Quality Contribution: Prevents scan failures from optional enhancement
Acceptance Criteria: Tree-sitter extraction continues regardless of LSP
"""

class TestGracefulDegradation:
    def test_given_lsp_init_fails_when_scanning_then_scan_completes(
        self, python_project, config_service
    ):
        """AC16: Scan completes successfully even if LSP fails."""
        from fs2.core.adapters.lsp_adapter_fake import FakeLspAdapter
        from fs2.core.adapters.exceptions import LspInitializationError

        # Configure FakeLspAdapter to fail on initialization
        fake_adapter = FakeLspAdapter(config_service)
        fake_adapter.set_error(LspInitializationError("Simulated failure for test"))

        # Scan with the failing adapter (LSP is on by default)
        result = scan_project(python_project, lsp_adapter=fake_adapter)

        # Scan should complete with Tree-sitter results
        assert result.success is True
        assert len(result.edges) > 0  # Tree-sitter imports found
        assert any("warning" in log.lower() for log in result.logs)
```

### Non-Happy-Path Coverage
- [ ] Stage skipped if no relationship_extraction_service
- [ ] Errors logged but don't stop pipeline
- [ ] Empty nodes list handled gracefully
- [ ] LSP failure doesn't break scan
- [ ] Invalid confidence values rejected

### Acceptance Criteria
- [ ] 10/15 ground truth entries detected (67%+ pass rate)
- [ ] Relationships persisted to graph on save
- [ ] Old graphs still load (backward compatibility)
- [ ] LSP enabled by default (no flag needed)
- [ ] `--no-lsp` flag disables LSP extraction
- [ ] AC15: If LSP server not installed, raises `LspServerNotFoundError` with actionable message
- [ ] AC16: Scan completes successfully even if LSP initialization fails
- [ ] LSP status shown at scan startup
- [ ] Edge deduplication: same source+target keeps highest confidence only
- [ ] Target validation: edges to non-existent nodes filtered out
- [ ] All tests passing
- [ ] Test coverage > 80%

### Commands to Run
```bash
# Run stage unit tests
pytest tests/unit/stages/test_relationship_extraction_stage.py -v

# Run CLI flag tests
pytest tests/unit/cli/test_scan_lsp_flag.py -v

# Run deduplication tests
pytest tests/unit/stages/test_edge_deduplication.py -v

# Run target validation tests
pytest tests/unit/stages/test_target_validation.py -v

# Run graceful degradation tests
pytest tests/integration/test_scan_graceful_degradation.py -v

# Run ground truth validation
pytest tests/integration/test_relationship_pipeline.py -v

# Run all Phase 8 tests
pytest tests/unit/stages/test_relationship*.py tests/unit/cli/test_scan*.py tests/integration/test_relationship*.py tests/integration/test_scan*.py -v

# Verify --no-lsp flag in help
fs2 scan --help | grep -A2 "no-lsp"

# Test scan with LSP (enabled by default)
fs2 scan . --verbose 2>&1 | head -30

# Test scan without LSP
fs2 scan . --no-lsp --verbose 2>&1 | head -30

# Lint pipeline and CLI code
ruff check src/fs2/cli/ src/fs2/core/services/
mypy src/fs2/cli/ src/fs2/core/services/ --strict
```

---

### Phase 9: Documentation

**Objective**: Document LSP integration for users and contributors.

**Deliverables**:
- Updated README.md with LSP quick-start
- User guide in `docs/how/user/lsp-guide.md`
- Developer guide in `docs/how/dev/lsp-adapter-architecture.md`

**Dependencies**: All implementation phases complete

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Documentation drift | Medium | Low | Include in PR reviews |

### Tasks (Lightweight Approach for Documentation)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 9.1 | [ ] | Survey existing docs/how/ directories | 1 | Structure documented | - | Discovery step |
| 9.2 | [ ] | Update README.md with LSP quick-start | 2 | Install, enable, verify sections | - | |
| 9.3 | [ ] | Create docs/how/user/lsp-guide.md | 2 | Troubleshooting, supported languages | - | |
| 9.4 | [ ] | Create docs/how/dev/lsp-adapter-architecture.md | 2 | Adding new languages, adapter design | - | |
| 9.5 | [ ] | Review documentation for completeness | 1 | All install commands tested | - | |

### Content Outlines

**README.md section** (Quick-start):
```markdown
## LSP Integration (Optional)

Enable high-confidence cross-file analysis with Language Server Protocol:

### Install LSP Servers
```bash
# Python
pip install pyright

# Go
go install golang.org/x/tools/gopls@latest

# TypeScript
npm install -g typescript typescript-language-server

# C#
dotnet tool install -g omnisharp
```

### Scan (LSP enabled by default)
```bash
fs2 scan ./project
# LSP is automatically enabled if servers are installed
```

### Disable LSP (if needed)
```bash
fs2 scan ./project --no-lsp
```

### Verify LSP Status
```bash
fs2 scan ./project --verbose
# Should show: "LSP Server Status: [OK] pyright ..."
```

See [docs/how/user/lsp-guide.md](docs/how/user/lsp-guide.md) for troubleshooting.
```

### Acceptance Criteria
- [ ] README.md updated with getting-started section
- [ ] All docs created and complete
- [ ] Install commands tested and working
- [ ] Target audience can follow guides successfully

### Commands to Run
```bash
# Verify docs exist
ls -la docs/how/user/lsp-guide.md
ls -la docs/how/dev/lsp-adapter-architecture.md

# Check README.md has LSP section
grep -A5 "LSP Integration" README.md

# Validate markdown formatting
markdownlint README.md docs/how/user/lsp-guide.md docs/how/dev/lsp-adapter-architecture.md 2>/dev/null || echo "markdownlint not installed - manual review required"

# Verify install commands in docs work
pip install pyright --dry-run 2>/dev/null && echo "✓ Pyright install command valid"
go install golang.org/x/tools/gopls@latest --help 2>/dev/null | head -1 || echo "Verify Go install command"

# Check for broken links (if link checker available)
lychee README.md docs/how/user/lsp-guide.md 2>/dev/null || echo "Link checker not installed - manual review required"
```

---

## Cross-Cutting Concerns

### Security Considerations
- No credentials stored in LSP configurations
- LSP servers run in sandboxed subprocess
- No network access from LSP servers (local analysis only)

### Observability
- Logging: LSP operations logged at DEBUG level
- Metrics: Track LSP query latency, cache hits
- Error tracking: All LspAdapterError exceptions logged

### Documentation
- Location: Hybrid (README + docs/how/)
- Target audience: Users (installation), Contributors (extending)
- Maintenance: Update when adding new language support

---

## Complexity Tracking

| Component | CS | Label | Breakdown (S,I,D,N,F,T) | Justification | Mitigation |
|-----------|-----|-------|------------------------|---------------|------------|
| SolidLspAdapter | 3 | Medium | S=1,I=1,D=0,N=1,F=0,T=1 | Wraps vendored code, type translation | Comprehensive tests, TDD |
| Vendoring | 2 | Small | S=2,I=0,D=0,N=0,F=0,T=0 | Large surface area but mechanical | Systematic find/replace |
| Python Import Extraction | 3 | Medium | S=1,I=1,D=0,N=1,F=0,T=0 | Tree-sitter queries validated; resolution logic new | Use 022 queries; TDD |
| Node ID/Filename Detection | 2 | Small | S=1,I=0,D=0,N=1,F=0,T=0 | Regex patterns from 022 experiments | Port existing regex patterns |
| TypeScript/Go Imports | 2 | Small | S=1,I=0,D=0,N=1,F=0,T=0 | Similar to Python extractor | Follow Python extractor pattern |
| Pipeline Integration | 3 | Medium | S=2,I=0,D=1,N=0,F=0,T=0 | Multiple files; stage ordering critical; merges LSP + extractors | Follow existing stage pattern exactly |

**Overall Feature**: CS-3 (Medium) - Combines LSP integration with comprehensive relationship extraction

---

## Progress Tracking

### Phase Completion Checklist
- [x] Phase 0: Environment Preparation - COMPLETE (2026-01-14)
- [x] Phase 0b: Multi-Project Research - COMPLETE (2026-01-15) - includes Subtask 001: SolidLSP validation (4/4 languages)
- [ ] Phase 1: Vendor SolidLSP Core - NOT STARTED
- [ ] Phase 2: LspAdapter ABC and Exceptions - NOT STARTED
- [ ] Phase 3: SolidLspAdapter Implementation - NOT STARTED
- [ ] Phase 4: Multi-Language LSP Support - NOT STARTED
- [ ] Phase 5: Python Import Extraction - NOT STARTED (ported from 024 Phase 2)
- [ ] Phase 6: Node ID and Filename Detection - NOT STARTED (ported from 024 Phase 3)
- [ ] Phase 7: TypeScript and Go Imports - NOT STARTED (ported from 024 Phase 4)
- [ ] Phase 8: Pipeline Integration - NOT STARTED (merged from 024 Phase 5 + 025 Phase 5)
- [ ] Phase 9: Documentation - NOT STARTED

**Overall Progress**: 2/11 phases complete (18%) - Phase 0 + Phase 0b

**Note**: 024 Phase 1 (Core Models & GraphStore Extension) is COMPLETE - foundation models (EdgeType, CodeEdge, GraphStore extensions) are already implemented and available for use.

### STOP Rule
**IMPORTANT**: This plan must be complete before creating tasks. After writing this plan:
1. Run `/plan-4-complete-the-plan` to validate readiness
2. Only proceed to `/plan-5-phase-tasks-and-brief` after validation passes

---

## Change Footnotes Ledger

**NOTE**: This section is populated during implementation by plan-6a-update-progress.

[^1]: Phase 0 - Environment preparation scripts created
[^2]: Phase 0 - LSP installation scripts at scripts/lsp_install/

[^3]: Subtask 001 ST005 - Created SolidLSP validation script
  - `function:scripts/lsp/validate_solidlsp_cross_file.py:validate_python`
  - `function:scripts/lsp/validate_solidlsp_cross_file.py:validate_typescript`
  - `function:scripts/lsp/validate_solidlsp_cross_file.py:validate_go`
  - `function:scripts/lsp/validate_solidlsp_cross_file.py:validate_csharp`

[^4]: Subtask 001 ST006 - Validation discoveries
  - TypeScript LSP requires opening both files before query
  - Added `pyright>=1.1.400` to fs2 pyproject.toml

[^5]: Subtask 001 ST007 - Research document
  - `file:docs/plans/025-lsp-research/tasks/phase-0b-multi-project-research/cross-file-lsp-validation.md`

[^6]: Subtask 001 ST008 - C# MSBuild fix
  - `method:scratch/serena/src/solidlsp/language_servers/csharp_language_server.py:CSharpLanguageServer._ensure_dotnet_runtime` - Accept .NET 9+
  - `method:scratch/serena/src/solidlsp/language_servers/csharp_language_server.py:CSharpLanguageServer.__init__` - Pass DOTNET_ROOT env vars

---

## Deviation Ledger

No deviations from constitution or architecture required. Plan follows:
- R2.1: Import rules (ABCs don't import SDKs)
- R2.2: Naming conventions (lsp_adapter.py, lsp_adapter_solidlsp.py, lsp_adapter_fake.py)
- R3.1: ABC requirements (inherits ABC, @abstractmethod, domain types)
- R3.2: Dependency injection (ConfigurationService registry)
- R3.3: Exception handling (translate to domain exceptions with actionable messages)

---

## ADR Ledger

| ADR | Status | Affects Phases | Notes |
|-----|--------|----------------|-------|
| None | - | - | No existing ADRs reference this feature |

**Recommendation**: Consider creating ADR for "Vendor vs Build vs Dependency" decision documenting why vendoring was chosen over pip dependency or building from scratch.

---

## Critical Insights Discussion

**Session**: 2026-01-14
**Context**: LSP Integration Implementation Plan v1.0 + 024 Plan Integration
**Analyst**: AI Clarity Agent
**Reviewer**: Development Team
**Format**: Water Cooler Conversation (5 Critical Insights)

### Insight 1: Vendoring Creates Permanent Maintenance Burden

**Did you know**: Once we vendor SolidLSP's ~25K LOC, it becomes our code to maintain forever with no automatic upstream security patches.

**Implications**:
- Serena is actively maintained; we won't get their fixes automatically
- Security vulnerabilities require manual patching
- Code will drift from upstream over time

**Options Considered**:
- Option A: Vendor and Accept - Simple but no visibility
- Option B: Vendor with Upstream Tracking - Add VENDOR_VERSION file
- Option C: Pin to Specific Commit + Automation - CI alerts
- Option D: Use as Pip Dependency - External dependency risk

**AI Recommendation**: Option B (Vendor with Upstream Tracking)
- Reasoning: Minimal effort, provides visibility, manual check before releases is sufficient

**Decision**: Add `VENDOR_VERSION` file recording upstream commit SHA, no diff script

**Action Items**:
- [x] Add Task 1.9: Create VENDOR_VERSION file
- [x] Add acceptance criterion for VENDOR_VERSION

**Affects**: Phase 1 (vendoring tasks)

---

### Insight 2: Edge Deduplication Not Addressed

**Did you know**: The same cross-file relationship can be discovered by multiple extraction sources (LSP, imports, node IDs), potentially creating duplicate edges.

**Implications**:
- Graph could have duplicate edges for same relationship
- Storage bloat
- Confusing query results

**Options Considered**:
- Option A: No Deduplication - Accept duplicates
- Option B: Deduplicate by Source+Target - Highest confidence wins
- Option C: Deduplication with Merged Metadata - Keep all resolution_rules
- Option D: No Deduplication but Add Source Tracking - New field

**AI Recommendation**: Option B (Highest Confidence Wins)
- Reasoning: Simple dict-based dedup, clean graph, confidence is meaningful

**Decision**: Deduplicate edges by (source_node_id, target_node_id), keep highest confidence

**Action Items**:
- [x] Add deduplication logic to Stage Protocol Contract
- [x] Add Task 8.11: Write edge deduplication tests
- [x] Add test example and acceptance criterion

**Affects**: Phase 8 (pipeline integration)

---

### Insight 3: Import Extractors Are Hidden Prerequisites

**Did you know**: Phase 8's RelationshipExtractionStage depends on import extractors (Python, TypeScript, Go) that were planned in 024, not this plan.

**Implications**:
- 024 Phases 2-5 are prerequisites to 025 Phase 8
- Cross-plan coordination required if kept separate
- Risk of blocking implementation

**Options Considered**:
- Option A: Add Explicit Dependency Note - Clear but separate plans
- Option B: Port 024 Phases 2-5 Into 025 - Single unified plan
- Option C: Merge Into New Combined Plan - Fresh start but rework

**AI Recommendation**: Option A initially, then Option B after research
- Reasoning: Subagent analysis showed plans are compatible; porting creates single source of truth

**Decision**: Port 024 Phases 2-5 into 025 as unified implementation

**Action Items**:
- [x] Port Phase 5: Python Import Extraction (from 024 Phase 2)
- [x] Port Phase 6: Node ID and Filename Detection (from 024 Phase 3)
- [x] Port Phase 7: TypeScript and Go Imports (from 024 Phase 4)
- [x] Merge Phase 8: Pipeline Integration (024 Phase 5 + 025 Phase 5)
- [x] Renumber Phase 9: Documentation
- [x] Update Table of Contents and Progress Tracking

**Affects**: Entire plan structure (now 11 phases: 0, 0b, 1-9)

---

### Insight 4: CI/CD Test Infrastructure Not Addressed

**Did you know**: Integration tests require real LSP servers, but there's no plan for CI/CD setup (GitHub Actions, etc.).

**Implications**:
- Tests would skip in CI without servers installed
- Zero LSP integration tests actually run in CI
- Regressions could slip through

**Options Considered**:
- Option A: Add CI Setup to Phase 0 - Install servers in CI
- Option B: Use Devcontainer in CI - Reuse local setup
- Option C: Accept Skipped Tests in CI - Local-only testing
- Option D: Mock-Based CI Tests - FakeLspAdapter in CI

**AI Recommendation**: Option A (Add CI Setup)
- Reasoning: Ensures integration tests actually run

**Decision**: Out of scope - CI will be addressed separately with Docker

**Action Items**: None for this plan

**Affects**: N/A (deferred)

---

### Insight 5: Node ID References Can Create Edges to Non-Existent Nodes

**Did you know**: When a README contains `method:src/auth.py:Auth.login`, the NodeIdDetector creates a 1.0 confidence edge even if that node doesn't exist in the graph.

**Implications**:
- High confidence edges to non-existent targets
- Graph has broken references
- Agents follow edges to 404 not found

**Options Considered**:
- Option A: Validate Target Exists - Filter invalid edges
- Option B: Lower Confidence for Unvalidated - Signal uncertainty
- Option C: Add `validated` Field - Explicit boolean
- Option D: Accept Broken Edges - Document limitation

**AI Recommendation**: Option A (Validate Target Exists)
- Reasoning: Simple filter, clean graph, metric tracks dropped edges

**Decision**: Validate target exists, filter out edges with non-existent targets

**Action Items**:
- [x] Add target validation logic to Stage Protocol Contract
- [x] Add Task 8.12: Write target validation tests
- [x] Add test example and acceptance criterion

**Affects**: Phase 8 (pipeline integration)

---

## Session Summary

**Insights Surfaced**: 5 critical insights identified and discussed
**Decisions Made**: 5 decisions reached through collaborative discussion
**Action Items Created**: 15+ follow-up tasks/updates
**Areas Updated**:
- Phase 1: Added VENDOR_VERSION task
- Phase 8: Added deduplication, target validation, merged with 024
- Plan Structure: Expanded from 8 to 11 phases (ported 024)

**Shared Understanding Achieved**: ✓

**Confidence Level**: High - Key risks identified and mitigated, plan is comprehensive and self-contained.

**Next Steps**: Run `/plan-4-complete-the-plan` to validate readiness, then proceed to implementation.

---

## Subtasks Registry

Mid-implementation detours requiring structured tracking.

| ID | Created | Phase | Parent Task | Reason | Status | Dossier |
|----|---------|-------|-------------|--------|--------|---------|
| 001-subtask-validate-lsp-cross-file | 2026-01-15 | Phase 0b: Multi-Project Research | T007 | Validate that LSP servers can resolve cross-file method calls before vendoring 25K LOC of SolidLSP. | [ ] Pending | [Link](tasks/phase-0b-multi-project-research/001-subtask-validate-lsp-cross-file.md) |

---

**Plan Version**: 1.1.0
**Created**: 2026-01-14
**Updated**: 2026-01-15 (Subtask 001 added)
**Spec**: [./lsp-integration-spec.md](./lsp-integration-spec.md)
