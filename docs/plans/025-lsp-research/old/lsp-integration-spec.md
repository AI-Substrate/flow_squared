# LSP Integration for Cross-File Relationship Extraction

📚 This specification incorporates findings from `research-dossier.md`

✅ **External Research Complete**
All external research topics have been addressed - see "Resolved Research" section below.

---

## Research Context

From `research-dossier.md`:

- **Components affected**: ScanPipeline (new stage), adapters (new LSP adapter layer), config (new LspConfig)
- **Critical dependencies**: External LSP servers (Pyright, gopls, OmniSharp, typescript-language-server)
- **Foundation COMPLETE**: CodeEdge, EdgeType, GraphStore extensions (56 tests passing from 024 Phase 1)
- **Modification risks**: ScanPipeline integration must be backward compatible; LSP must remain optional
- **Prior Learnings**: 15 relevant discoveries including stdout isolation (PL-01), lazy initialization (PL-02), protocol-level testing (PL-06)

See `research-dossier.md` for full analysis.

---

## Summary

### What
Enable fs2 to extract high-confidence cross-file relationships (method calls, symbol references, type implementations) by integrating with Language Server Protocol (LSP) servers during the scan workflow. LSP servers provide compiler-level semantic understanding that Tree-sitter alone cannot achieve.

### Why
- **Higher confidence**: LSP provides 0.9-1.0 confidence for relationships vs 0.3-0.5 from heuristics
- **Method call resolution**: `self.auth.validate()` → `AuthHandler.validate()` requires type inference
- **Find all references**: LSP natively supports "what uses this symbol?" queries
- **Agent value**: Agents can answer "what calls this function?" with verified accuracy

---

## Goals

1. **Standardized relationship extraction**: LSP service returns language-agnostic `CodeEdge` instances; no language-specific types leak into consuming code
2. **Simple language wrappers**: Adding a new language requires only a configuration entry (~10 lines), not new adapter code
3. **Graceful degradation**: If LSP server not installed, system continues with Tree-sitter-only extraction and clear error messaging
4. **Multi-project support**: Handle repositories with multiple project roots (e.g., `src/project1/` and `src/project2/` for C# solutions)
5. **Lazy initialization**: LSP servers start only when scanning files that need them, not at startup
6. **Real integration tests**: Tests use actual LSP servers (no mocking) for protocol fidelity
7. **Initial languages**: Python (Pyright), C# (OmniSharp), Go (gopls), TypeScript/JS (typescript-language-server)
8. **Extensible design**: Architecture supports adding Java, Rust, C++, Ruby, GDScript later

---

## Non-Goals

1. **Replace Tree-sitter**: LSP enhances but does not replace Tree-sitter baseline (imports, doc references still use Tree-sitter)
2. **Cross-project linkage**: No requirement to link symbols between separate projects (unless explicit node_id match)
3. **IDE features**: Not building hover, completion, diagnostics—only relationship extraction
4. **Bundled LSP servers**: Users install their own LSP servers; fs2 does not ship binaries (may revisit after external research)
5. **Real-time incremental updates**: Focus on full scan, not watch-mode incremental LSP queries
6. **All LSP features**: Only implement `textDocument/references`, `textDocument/definition`, `textDocument/documentSymbol`

---

## Complexity

**Score**: CS-4 (Large)

**Breakdown**:
| Factor | Score | Rationale |
|--------|-------|-----------|
| Surface Area (S) | 2 | Many files: adapters, config, pipeline stage, devcontainer, test fixtures |
| Integration (I) | 2 | Multiple external deps (4 LSP servers), each with own quirks |
| Data/State (D) | 1 | Minor: LspConfig model, project root mapping |
| Novelty (N) | 1 | Some ambiguity: multi-project handling needs research |
| Non-Functional (F) | 0 | Standard performance/reliability expectations |
| Testing/Rollout (T) | 2 | Integration tests with real LSP, staged per-language rollout |

**Total**: S(2) + I(2) + D(1) + N(1) + F(0) + T(2) = **8 → CS-4**

**Confidence**: 0.75 (multi-project handling is uncertain, external research not yet done)

**Assumptions**:
- LSP servers are available in devcontainer (devcontainer.json can be modified)
- JSON-RPC stdio protocol is consistent enough for generic client
- Multi-project detection can be inferred from project files (.csproj, go.mod, tsconfig.json, pyproject.toml)

**Dependencies**:
- External LSP server binaries must be installable in devcontainer
- Foundation models (CodeEdge, EdgeType, GraphStore) are complete (verified)

**Risks**:
- Multi-project LSP initialization complexity may be higher than estimated
- LSP server startup time may impact scan performance
- Server-specific quirks may require per-language handling despite "thin wrapper" goal

**Phases** (high-level):
1. Phase 0: Environment preparation (devcontainer LSP deps)
2. Phase 0b: Multi-project research (scripts/lsp experiments)
3. Phase 1: LSP Adapter ABC and generic client
4. Phase 2: First language integration (Python/Pyright)
5. Phase 3: Remaining languages (Go, C#, TS/JS)
6. Phase 4: Pipeline stage integration
7. Phase 5: Multi-project support
8. Phase 6: Test fixtures and validation

---

## Acceptance Criteria

### Environment & Setup
**AC01**: Devcontainer includes all required LSP servers (Pyright, gopls, OmniSharp, typescript-language-server) verified by `which` command
**AC02**: Test fixtures exist with multi-project layouts for each initial language under `tests/fixtures/samples/`

### Adapter Architecture
**AC03**: `LspAdapter` ABC defines language-agnostic interface; implementations return `CodeEdge` instances only
**AC04**: Adding a new language requires only adding an `LspServerConfig` entry (no new adapter class)
**AC05**: Adapter raises `LspServerNotInstalledError` with actionable installation instructions when server binary not found
**AC06**: Adapter raises `LspInitializationError` with diagnostic info when server fails to start

### Multi-Project Support
**AC07**: `LspConfig` in config system allows specifying project roots per language (e.g., `lsp.csharp.project_roots: ["src/project1", "src/project2"]`)
**AC08**: When scanning a file, system determines correct project root for LSP initialization
**AC09**: Auto-detection of project roots from marker files (.csproj, go.mod, tsconfig.json, pyproject.toml) when not explicitly configured

### Pipeline Integration
**AC10**: New `RelationshipExtractionStage` runs after `ASTExtractionStage`, before `SmartContentStage`
**AC11**: Stage populates `PipelineContext.relationships` with `CodeEdge` instances
**AC12**: LSP servers are initialized lazily on first file requiring that language, not at pipeline start
**AC13**: Pipeline completes successfully even if all LSP servers fail (graceful degradation)

### Standardized Output
**AC14**: All LSP adapters return the same result types regardless of language
**AC15**: LSP results are converted to `CodeEdge` with confidence 0.9 and `resolution_rule="lsp:{method}"`
**AC16**: No language-specific types (pyright, gopls, etc.) appear in service layer or above

### Testing
**AC17**: Integration tests use real LSP servers, not mocks
**AC18**: Tests include multi-project scenarios for each language
**AC19**: Tests verify graceful degradation when LSP server unavailable

### Performance
**AC20**: LSP server startup does not block pipeline for more than 5 seconds per language
**AC21**: Relationship extraction completes within 2x the time of Tree-sitter-only scan for typical projects

---

## Testing Strategy

- **Approach**: Full TDD
- **Rationale**: Comprehensive test-first for all components including LSP communication, ensuring protocol fidelity with real servers
- **Focus Areas**:
  - Adapter ABC contract compliance
  - Error handling (server not installed, initialization failures, timeouts)
  - Multi-project root detection and precedence
  - LSP protocol correctness (JSON-RPC, lifecycle)
  - Pipeline integration and graceful degradation
- **Excluded**: Performance benchmarks (separate Phase 7 validation)
- **Mock Usage**: Targeted fakes only
  - FakeLspAdapter implements ABC for unit testing service layer
  - Real LSP servers required for all integration tests
  - No mocking of LSP protocol communication
- **Test Fixtures**: Multi-project layouts per language under `tests/fixtures/samples/`

---

## Documentation Strategy

- **Location**: Hybrid (README + docs/how/)
- **Rationale**: Quick-start in README, depth in docs/how/ for configuration and troubleshooting
- **Content Split**:
  - **README.md**: LSP server installation commands per language, basic verification steps
  - **docs/how/user/lsp-integration-guide.md**: Multi-project configuration, troubleshooting, supported features
  - **docs/how/dev/lsp-adapter-architecture.md**: Adapter design, adding new languages, testing patterns
- **Target Audience**: fs2 users (installation), contributors (architecture)
- **Maintenance**: Update docs when adding new language support or changing configuration schema

---

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Multi-project LSP initialization is complex | Medium | High | Phase 0b research with real experiments |
| LSP servers have inconsistent behavior | Medium | Medium | Generic client with per-language quirk handling |
| Server startup impacts scan performance | Medium | Medium | Lazy loading, parallel initialization |
| OmniSharp requires .NET runtime | Low | Medium | Document as prerequisite |
| LSP servers consume significant memory | Low | Medium | One server per language, shutdown after scan |

### Assumptions

1. Users can install LSP servers via their package managers (npm, pip, apt, dotnet)
2. JSON-RPC over stdio is the universal LSP transport (not TCP)
3. Project root detection from marker files is reliable
4. LSP servers index workspace within acceptable time (<30s for typical projects)
5. Foundation models (CodeEdge, EdgeType) are sufficient for LSP results

---

## Open Questions

1. **[RESOLVED: Multi-project scope]** Most specific (deepest) project root wins — matches IDE behavior
2. **[RESOLVED: Server lifetime]** Shutdown after each scan — clean slate, may revisit if slow
3. **[RESOLVED: Parallel initialization]** Sequential, lazy — start as needed when scanning files
4. **[RESOLVED: OmniSharp installation]** .NET SDK required as prerequisite for C# support
5. **[DEFERRED: Error verbosity]** How much LSP server diagnostic info to expose — decide during implementation

---

## ADR Seeds (Optional)

### Decision Drivers
- Clean Architecture: adapters must not leak external types
- Extensibility: adding languages should be trivial
- Reliability: LSP failures must not break scans
- Testability: real LSP servers preferred over mocks

### Candidate Alternatives
- **A: Generic client + config registry** — One LspClient class, per-language LspServerConfig entries
- **B: Per-language adapter classes** — Separate adapter per language (PyrightAdapter, GoplsAdapter, etc.)
- **C: External LSP proxy** — Spawn single proxy process that manages all LSP servers

### Stakeholders
- fs2 maintainers (adapter design)
- Users (installation experience, error messages)
- AI agents (relationship query accuracy)

---

## External Research

### Incorporated
- `external-research-1.md`: LSP feature support matrix by language/server
- `external-research-2.md`: Reference LSP client implementation (stdlib-only Python)
- `external-research-3-binary-distribution.md`: LSP server detection, error messaging, cross-platform install guidance
- `external-research-4-session-management.md`: Lifecycle management, batching, throttling, memory management
- `external-research-5-serena-solidlsp.md`: **Production-tested patterns from Serena's 40+ language LSP framework**

### Key Findings

**From external-research-1 & 2:**
- All target languages have mature LSP servers with consistent core features
- Generic stdio JSON-RPC client is feasible (reference implementation provided)
- Per-language config is ~10 lines (thin wrapper pattern validated)

**From external-research-3 (Binary Distribution):**
- Use `shutil.which()` + subprocess version checks for 3-step validation
- Error messages must distinguish: "not installed" vs "not in PATH" vs "wrong version"
- Server-specific version parsing required (gopls uses `gopls version`, not `--version`)
- OmniSharp has two installation paths (dotnet CLI vs pre-built binaries)

**From external-research-4 (Session Management):**
- LSP has no native batching - implement at application layer with semaphores
- Concurrency limits: Pyright (5), gopls (3), TypeScript (4), OmniSharp (3)
- Memory per server: 200MB-2.5GB depending on project/language
- Startup times: 10-30s medium projects, 60-120s for 10k+ files
- Query throughput: simple queries 10-20/s, complex (references) 2-5/s
- Always send proper shutdown sequence to avoid memory leaks

**From external-research-5 (Serena SolidLSP) - HIGH IMPACT:**
- **Thin wrapper pattern**: Most languages need only 100-150 LOC (not 300+)
- **RuntimeDependencyCollection**: Unified binary/npm/download management pattern
- **Two-tier caching**: Separate raw LSP responses from processed symbols
- **Parallel startup with error aggregation**: Start all servers concurrently, rollback on any failure
- **Auto-restart on health check**: Transparent recovery without caller awareness
- **Process tree cleanup**: Use psutil for proper child process termination
- **Language enum as registry**: Single file to edit when adding languages
- **Cross-file reference wait**: Configurable per-language indexing delay (0.5-5s)
- **Estimated total LOC**: ~1500-2000 for 4 languages (vs original ~3000+)

### Applied To
- Goals (standardized output, simple wrappers)
- Architecture (ABC + config registry design)
- Acceptance criteria (specific LSP methods to implement)
- AC05/AC06: Error message formatting and detection strategy (external-research-3)
- AC20/AC21: Performance expectations and throttling approach (external-research-4)
- AC12: Lazy initialization with semaphore-based batching (external-research-4)
- **Phase 1**: Adopt RuntimeDependencyCollection pattern from Serena (external-research-5)
- **Phase 2**: Base generic client on Serena's ls_handler.py queue-based correlation (external-research-5)
- **Phase 3-4**: Use thin wrapper pattern - target ~100 LOC per language (external-research-5)
- **Phase 5**: Add parallel startup and auto-restart to pipeline stage (external-research-5)
- **Phase 7**: Adopt parameterized test fixtures pattern (external-research-5)

---

## Resolved Research

All external research topics have been addressed:

| Topic | Document | Status |
|-------|----------|--------|
| LSP Feature Support | `external-research-1.md` | ✅ Complete |
| Reference Client Implementation | `external-research-2.md` | ✅ Complete |
| Binary Distribution Best Practices | `external-research-3-binary-distribution.md` | ✅ Complete |
| Session Management for Large Codebases | `external-research-4-session-management.md` | ✅ Complete |
| Production Patterns (Serena SolidLSP) | `external-research-5-serena-solidlsp.md` | ✅ Complete |

### Remaining Research
Multi-project research (Phase 0b) should be prioritized as it affects core architecture. This will be conducted via scripts/lsp experiments, not external research.

---

## Phase Outline (High-Level)

| Phase | Name | Key Deliverables |
|-------|------|------------------|
| 0 | Environment Prep | Devcontainer LSP deps, verify installations |
| 0b | Multi-Project Research | scripts/lsp experiments, test fixtures, project root detection strategy |
| 1 | Adapter Foundation | LspAdapter ABC, LspServerConfig, LspAdapterError hierarchy, FakeLspAdapter |
| 2 | Generic Client | JSON-RPC stdio client, server lifecycle, async request/response |
| 3 | Python Integration | Pyright config, integration tests, validation |
| 4 | Multi-Language | Go/gopls, C#/OmniSharp, TS/typescript-language-server |
| 5 | Pipeline Stage | RelationshipExtractionStage, lazy initialization, PipelineContext integration |
| 6 | Multi-Project | LspConfig, project root detection, per-project server instances |
| 7 | Validation | End-to-end tests, performance benchmarks, documentation |

---

**Specification Version**: 1.1
**Created**: 2026-01-14
**Plan Folder**: `docs/plans/025-lsp-research/`
**Mode**: Full

---

## Clarifications

### Session 2026-01-14

**Q1: Workflow Mode**
- **Answer**: Full
- **Rationale**: CS-4 complexity with 8 phases, 4 external LSP server dependencies, and multi-project support requirements warrant comprehensive gates and dossiers.

**Q2: Testing Strategy**
- **Answer**: Full TDD
- **Rationale**: Comprehensive test-first for all components including LSP communication, ensuring protocol fidelity with real servers.

**Q3: Mock/Stub/Fake Usage**
- **Answer**: Targeted fakes
- **Rationale**: FakeLspAdapter for unit tests (follows fs2 "fakes over mocks" convention), real LSP servers for integration tests.

**Q4: Documentation Strategy**
- **Answer**: Hybrid (README + docs/how/)
- **Rationale**: README for LSP server installation commands, docs/how/ for multi-project configuration, troubleshooting, and architecture details.

**Q5: Multi-Project Scope Precedence**
- **Answer**: Most specific (deepest)
- **Rationale**: Closest project root to file wins - matches IDE behavior and user expectations.

**Q6: LSP Server Lifetime**
- **Answer**: Shutdown after scan
- **Rationale**: Clean slate each time with predictable memory usage. May revisit if performance proves problematic.

**Q7: Server Initialization Order**
- **Answer**: Sequential (lazy)
- **Rationale**: Servers start as needed when scanning files requiring that language. Lower peak memory, simpler implementation.

**Q8: OmniSharp/.NET SDK Prerequisite**
- **Answer**: Yes, require .NET SDK
- **Rationale**: Document .NET SDK as prerequisite for C# support. Cleaner detection logic and simpler error messages.

---

### Coverage Summary

| Category | Status | Details |
|----------|--------|---------|
| Workflow Mode | ✅ Resolved | Full mode (CS-4 complexity) |
| Testing Strategy | ✅ Resolved | Full TDD, targeted fakes, real LSP for integration |
| Mock Usage | ✅ Resolved | FakeLspAdapter for unit tests, real servers for integration |
| Documentation Strategy | ✅ Resolved | Hybrid (README + docs/how/) |
| Multi-project scope | ✅ Resolved | Most specific (deepest) wins |
| Server lifetime | ✅ Resolved | Shutdown after scan |
| Initialization order | ✅ Resolved | Sequential, lazy |
| .NET SDK prerequisite | ✅ Resolved | Required for C# |
| Error verbosity | 🔄 Deferred | Decide during implementation |

**Next step**: Run `/plan-3-architect` to generate the phase-based plan.
