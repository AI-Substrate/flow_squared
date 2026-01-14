# LSP Integration via Vendored SolidLSP

**Mode**: Full

📚 This specification incorporates findings from `research-dossier.md` and `external-research-5-serena-solidlsp.md`

---

## Research Context

From `research-dossier.md` and Serena SolidLSP research:

- **Components affected**: New `vendors/solidlsp/` directory, `LspAdapter` ABC, thin wrapper implementation
- **Critical dependencies**: Vendored SolidLSP (~12K lines), psutil for process management
- **Foundation COMPLETE**: CodeEdge, EdgeType, GraphStore extensions (56 tests passing from 024 Phase 1)
- **Key insight**: Serena's SolidLSP is MIT-licensed, production-tested with 40+ languages, and can be directly lifted
- **Modification risks**: Minimal - clean boundary via adapter ABC isolates vendored code

See `research-dossier.md` and `external-research-5-serena-solidlsp.md` for full analysis.

---

## Summary

### What
Enable fs2 to extract high-confidence cross-file relationships (method calls, symbol references, type implementations) by **vendoring Serena's SolidLSP library** and wrapping it with a thin fs2-compliant adapter layer. This approach leverages ~25K lines of production-tested LSP client code (supporting 40+ languages) instead of building from scratch.

### Why
- **Time savings**: ~9-11 days vs 2-3 months building from scratch
- **Production-tested**: SolidLSP supports 40+ languages with mature error handling
- **Higher confidence**: LSP provides 0.9-1.0 confidence vs 0.3-0.5 from Tree-sitter heuristics
- **Method call resolution**: `self.auth.validate()` → `AuthHandler.validate()` requires LSP's type inference
- **Agent value**: Agents can answer "what calls this function?" with verified accuracy
- **Clean license**: MIT license permits copying, modification, and distribution

---

## Goals

1. **Vendor SolidLSP complete**: Copy all SolidLSP files (~25K LOC, 40+ languages) to `src/fs2/vendors/solidlsp/`
2. **Create adapter wrapper**: Thin `LspAdapter` ABC (~150 LOC) with `SolidLspAdapter` implementation (~350 LOC)
3. **Translate types at boundary**: Convert SolidLSP responses to fs2's `CodeEdge` domain model
4. **40+ language support**: All languages supported by SolidLSP work automatically if user has LSP server installed
5. **Tested languages**: Python (Pyright), Go (gopls), TypeScript (typescript-language-server), C# (OmniSharp)
6. **Graceful degradation**: If LSP server unavailable, system continues with Tree-sitter-only extraction
7. **Proper attribution**: Include MIT license notice for Oraios AI and Microsoft in `THIRD_PARTY_LICENSES`

---

## Non-Goals

1. **Replace Tree-sitter**: LSP enhances but does not replace Tree-sitter baseline (imports, doc references)
2. **Modify SolidLSP internals**: Keep vendored code as close to upstream as possible for easier updates
3. **Test all 40+ languages**: Vendor all, but integration-test only 4 (Python, TS/JS, Go, C#)
4. **Real-time incremental updates**: Focus on full scan, not watch-mode LSP queries
5. **Bundled LSP servers**: Users install their own (Pyright via pip/npm, gopls via go install, etc.)
6. **Custom LSP features**: Only use standard LSP methods (references, definition, documentSymbol)

---

## Complexity

**Score**: CS-3 (Medium)

**Breakdown**:
| Factor | Score | Rationale |
|--------|-------|-----------|
| Surface Area (S) | 2 | New vendors dir (~25K LOC), adapter files, tests, attribution |
| Integration (I) | 1 | Single vendored dependency (SolidLSP), well-documented |
| Data/State (D) | 0 | Uses existing CodeEdge/EdgeType models, no new schemas |
| Novelty (N) | 1 | Adapter pattern clear, some import path adjustments needed |
| Non-Functional (F) | 0 | Standard performance expectations |
| Testing/Rollout (T) | 1 | Integration tests with real LSP servers |

**Total**: S(2) + I(1) + D(0) + N(1) + F(0) + T(1) = **5 → CS-3**

**Confidence**: 0.85 (high - detailed design from subagent research, clear precedent from Serena)

**Assumptions**:
- SolidLSP code can be copied with minimal modifications (import path changes only)
- MIT license permits vendoring (verified ✅)
- Existing CodeEdge/EdgeType models sufficient for LSP results (verified ✅)
- Users can install language servers (pip, npm, go install)

**Dependencies**:
- Foundation models (CodeEdge, EdgeType, GraphStore) - **COMPLETE** from 024 Phase 1
- psutil package for process tree cleanup
- External LSP servers installed by users

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SolidLSP has hidden dependencies | Low | Medium | Review imports before vendoring |
| Import path changes break code | Medium | Low | Systematic find/replace, test coverage |
| Upstream SolidLSP diverges | Low | Low | Pin to specific commit, selective merge |

**Phases** (high-level):
1. Phase 1: Vendor SolidLSP core files
2. Phase 2: Create LspAdapter ABC and wrapper
3. Phase 3: Integration tests with real servers
4. Phase 4: Pipeline integration and CLI flag

---

## Acceptance Criteria

### Vendoring
**AC01**: All SolidLSP files (~25K LOC, 40+ languages) copied to `src/fs2/vendors/solidlsp/` with import paths updated
**AC02**: `THIRD_PARTY_LICENSES` file includes MIT license text with Oraios AI and Microsoft attribution
**AC03**: Vendored code passes import test: `python -c "from fs2.vendors.solidlsp.ls import SolidLanguageServer"`

### Adapter Interface
**AC04**: `LspAdapter` ABC defines language-agnostic interface returning `CodeEdge` instances only
**AC05**: `SolidLspAdapter` implementation wraps SolidLSP with exception translation at boundary
**AC06**: `FakeLspAdapter` test double inherits from ABC with `call_history` tracking
**AC07**: Adapter raises `LspAdapterError` hierarchy (NotFound, StartError, Timeout, NotSupported)

### Type Translation
**AC08**: LSP `textDocument/references` results converted to `CodeEdge` with `EdgeType.REFERENCES`
**AC09**: LSP `textDocument/definition` results converted to `CodeEdge` with appropriate EdgeType
**AC10**: All LSP-derived edges have `confidence=1.0` and `resolution_rule="lsp:{method}"`

### Language Support (Tested)
**AC11**: Python support via Pyright with installation instructions in README
**AC12**: Go support via gopls with installation instructions
**AC13**: TypeScript support via typescript-language-server with installation instructions
**AC14**: C# support via OmniSharp with installation instructions

### Graceful Degradation
**AC15**: If LSP server not installed, adapter raises `LspServerNotFoundError` with actionable message
**AC16**: Scan completes successfully even if LSP initialization fails (graceful fallback)

### Testing
**AC17**: Unit tests for adapter ABC contract compliance
**AC18**: Integration tests with real servers (Pyright, gopls, typescript-language-server, OmniSharp) on test fixtures
**AC19**: FakeLspAdapter passes same contract tests as real implementation

---

## Testing Strategy

- **Approach**: Full TDD
- **Rationale**: Adapter boundary is critical for type translation correctness and Clean Architecture compliance
- **Focus Areas**:
  - Adapter ABC contract compliance
  - Exception translation (SolidLSP → domain errors)
  - LSP response → CodeEdge conversion
  - Graceful degradation when servers unavailable
  - Vendored code import path correctness
- **Excluded**: SolidLSP internals (already tested upstream), LSP protocol details
- **Mock Usage**: Targeted fakes with strong preference for real servers
  - `FakeLspAdapter` implements ABC for unit testing service layer isolation only
  - **Prefer real LSP servers** (Pyright, gopls, etc.) - devcontainer guarantees availability
  - Only use fakes when testing service-layer behavior that shouldn't trigger real LSP
  - No mocking of LSP protocol communication or SolidLSP internals
  - Rationale: Docker/devcontainer provides deterministic environment; use it

---

## Documentation Strategy

- **Location**: Hybrid (README + docs/how/)
- **Rationale**: Users need quick-start for enabling LSP; contributors need depth for extending
- **Content Split**:
  - **README.md**: Quick-start (install LSP servers, `--no-lsp` flag, verification)
  - **docs/how/user/lsp-guide.md**: Troubleshooting, supported languages, error messages
  - **docs/how/dev/lsp-adapter-architecture.md**: Adding new languages, adapter design
- **Target Audience**: fs2 users (installation), contributors (extending languages)
- **Maintenance**: Update when adding new language support or changing CLI interface

---

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SolidLSP has Serena-specific code | Medium | Medium | Stub out non-essential imports |
| Users don't have LSP servers installed | Medium | Low | Clear error messages with install commands |
| Process cleanup issues on Windows | Low | Medium | Test on Windows, fallback to simple kill |

### Assumptions

1. SolidLSP's core functionality is independent of Serena-specific features
2. Import path changes (`solidlsp.*` → `fs2.vendors.solidlsp.*`) are sufficient
3. Users can follow installation instructions for LSP servers
4. Foundation models (CodeEdge, EdgeType) handle all LSP result types

---

## Open Questions

1. **[RESOLVED: Yes]** Can we vendor SolidLSP? → MIT license permits copying/modification
2. **[RESOLVED: ~25K]** How much code to copy? → All language configs (~25K LOC total)
3. **[RESOLVED: No]** Should we auto-install LSP servers? → User responsibility; actionable error messages
4. **[RESOLVED: All 40+]** Which languages for initial support? → Vendor all, test 4 (Python, TS/JS, Go, C#)

---

## ADR Seeds (Optional)

### Decision Drivers
- Time to market (weeks vs months)
- Maintenance burden of vendored code
- Clean Architecture boundary preservation
- License compatibility

### Candidate Alternatives
- **A: Vendor SolidLSP** — Copy ~25K lines (all 40+ languages), wrap with adapter (RECOMMENDED)
- **B: Build from scratch** — Write custom LSP client (~3K LOC, 2-3 months)
- **C: Use SolidLSP as pip dependency** — External package dependency (version coupling risk)

### Stakeholders
- fs2 maintainers (vendoring decision)
- Users (LSP server installation)
- AI agents (cross-file relationship accuracy)

---

## External Research

### Incorporated
- `external-research-1.md`: LSP feature support matrix by language/server
- `external-research-2.md`: Reference LSP client implementation (stdlib-only Python)
- `external-research-3-binary-distribution.md`: Server detection, error messaging, install guidance
- `external-research-4-session-management.md`: Lifecycle management, throttling, memory management
- `external-research-5-serena-solidlsp.md`: **Production patterns from Serena's 40+ language framework**

### Key Findings

**From external-research-5 (Serena SolidLSP) - HIGH IMPACT:**
- **MIT License**: Clear to copy, modify, distribute with attribution
- **Thin wrapper pattern**: Most languages need only 100-150 LOC
- **RuntimeDependencyCollection**: Unified binary/npm/download management
- **Two-tier caching**: Separate raw LSP responses from processed symbols
- **Parallel startup**: Multiple servers start concurrently with error aggregation
- **Auto-restart**: Transparent recovery on health check failure
- **Process tree cleanup**: psutil for proper child process termination
- **Estimated wrapper effort**: ~1K LOC to wrap ~25K vendored code (1:25 ratio)

### Applied To
- Goals: Vendor + wrap approach (from Serena research)
- Complexity: Reduced from CS-4 to CS-3 due to mature vendored code
- Acceptance criteria: Specific to adapter boundary, not LSP protocol
- Testing strategy: Follow Serena's parameterized fixture pattern

---

## File Structure (Proposed)

```
src/fs2/
├── vendors/
│   └── solidlsp/                       # Vendored (~12K LOC)
│       ├── __init__.py
│       ├── ls.py                       # Main ABC
│       ├── ls_handler.py               # JSON-RPC client
│       ├── ls_config.py                # Language registry
│       ├── ls_types.py                 # Types
│       ├── ls_request.py               # Request wrappers
│       ├── ls_exceptions.py            # Exceptions
│       ├── ls_utils.py                 # Utilities
│       ├── settings.py                 # Settings
│       ├── lsp_protocol_handler/       # Protocol types
│       └── language_servers/           # Per-language configs
│           ├── common.py               # RuntimeDependencyCollection
│           ├── pyright_server.py       # Python
│           ├── gopls.py                # Go
│           └── typescript_language_server.py  # TypeScript
├── core/
│   └── adapters/
│       ├── lsp_adapter.py              # ABC (~150 LOC)
│       ├── lsp_adapter_solidlsp.py     # Wrapper (~350 LOC)
│       ├── lsp_adapter_fake.py         # Test double (~200 LOC)
│       └── exceptions.py               # Add LspAdapterError hierarchy

THIRD_PARTY_LICENSES                    # MIT attribution

tests/
├── unit/adapters/
│   ├── test_lsp_adapter.py             # ABC contract
│   └── test_lsp_adapter_fake.py        # Fake behavior
└── integration/
    └── test_lsp_integration.py         # Real Pyright tests
```

---

**Specification Version**: 1.0
**Created**: 2026-01-14
**Plan Folder**: `docs/plans/025-lsp-research/`

---

## Clarifications

### Session 2026-01-14

**Q1: Workflow Mode**
- **Answer**: Full
- **Rationale**: CS-3 complexity with vendoring ~12K LOC, adapter boundary testing, and multi-phase rollout warrants comprehensive gates and dossiers.

**Q2: Testing Strategy**
- **Answer**: Full TDD
- **Rationale**: Adapter boundary is critical; comprehensive tests ensure type translation and exception handling correctness.

**Q3: Mock Usage**
- **Answer**: Targeted fakes (B), with strong preference for real servers
- **Rationale**: Devcontainer guarantees Pyright/gopls availability. Use real LSP servers whenever possible; fakes only for service-layer unit test isolation.

**Q4: Documentation Strategy**
- **Answer**: Hybrid (C)
- **Content Split**:
  - **README.md**: Quick-start (install LSP servers, disable with `--no-lsp` flag, verify it works)
  - **docs/how/user/**: LSP troubleshooting guide, supported languages reference
  - **docs/how/dev/**: Adding new language support, adapter architecture
- **Target Audience**: fs2 users (installation), contributors (extending languages)
- **Maintenance**: Update when adding new language support or changing CLI flags

**Q5: Auto-Install LSP Servers**
- **Answer**: No auto-install (A)
- **Rationale**: Simpler, respects user environment, avoids "magic" downloads. May revisit auto-install for popular languages (Python) later.
- **Requirement**: Error messages MUST be actionable with exact install commands (e.g., "pyright not found. Install with: pip install pyright")

**Q6: Language Support Scope**
- **Answer**: Vendor all 40+ languages, test 4
- **Rationale**: Adapter wrapper is language-agnostic; SolidLSP handles all per-language details. No reason to artificially limit.
- **Vendoring**: Copy ALL language server configs from SolidLSP (~25K LOC total)
- **Testing**: Install and test with 4 languages in devcontainer:
  - Python (Pyright)
  - TypeScript/JavaScript (typescript-language-server)
  - Go (gopls)
  - C# (OmniSharp)
- **Reporting**: Flag any per-language code required outside SolidLSP during implementation
- **User Experience**: All 40+ languages work automatically if user has LSP server installed
