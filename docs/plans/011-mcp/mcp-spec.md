# MCP Server for fs2

**Mode**: Full

This specification incorporates findings from `research-dossier.md`

## Research Context

Based on deep codebase research conducted 2025-12-26:

- **Components affected**: New `src/fs2/core/mcp/` module, CLI entry point, pyproject.toml
- **Critical dependencies**: Existing services (TreeService, GetNodeService, SearchService) are MCP-ready with clean interfaces
- **Modification risks**: Low - new module composition, no changes to existing services
- **Key insight**: STDIO transport requires all non-protocol output to stderr (protocol corruption otherwise)

See `research-dossier.md` for full analysis.

---

## Summary

**WHAT**: Expose fs2's code intelligence capabilities (tree navigation, node retrieval, code search) through the Model Context Protocol (MCP), enabling AI coding agents to programmatically explore indexed codebases.

**WHY**: Transform fs2 from a CLI-only tool into an AI-native code intelligence platform. AI agents like Claude currently rely on text-based grep/glob for code exploration. An MCP server enables semantic, structured access to code architecture - understanding files, classes, functions, and their relationships rather than just matching text patterns.

---

## Goals

1. **Enable agent-driven code exploration**: AI agents can discover and understand codebase structure without human CLI intervention
2. **Provide structured code retrieval**: Agents receive typed, structured data (node hierarchies, search results) rather than raw text
3. **Support semantic search**: Agents can find code by concept/meaning, not just string matching
4. **Maintain existing CLI functionality**: MCP server is additive; existing `fs2 tree`, `fs2 get-node`, `fs2 search` continue unchanged
5. **Easy integration**: Single command (`fs2 mcp`) starts the server; works with Claude Desktop and other MCP clients
6. **Agent-optimized documentation**: Tool descriptions guide agents on when/how to use each capability

---

## Non-Goals

1. **Not replacing CLI**: The MCP server supplements, not replaces, the human-facing CLI
2. **Not modifying existing services**: MCP tools compose existing services; no changes to TreeService, GetNodeService, or SearchService internals
3. **Not implementing HTTP transport**: Initial implementation uses STDIO only (standard for local MCP servers)
4. **Not adding authentication**: MCP server runs locally; no auth layer needed
5. **Not exposing scan functionality**: Agents cannot trigger indexing; they consume pre-indexed graphs
6. **Not adding new search capabilities**: MCP exposes existing search modes (text, regex, semantic); no new matching algorithms

---

## Complexity

- **Score**: CS-2 (small)
- **Breakdown**: S=1, I=1, D=0, N=0, F=1, T=1 (Total: 4)
- **Confidence**: 0.85

### Dimension Details

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 1 | New module with 5-6 files, plus CLI entry point; cohesive scope |
| Integration (I) | 1 | One external dependency (MCP framework library) |
| Data/State (D) | 0 | No schema changes; uses existing CodeNode/SearchResult models |
| Novelty (N) | 0 | Well-researched; MCP protocol is specified; patterns documented |
| Non-Functional (F) | 1 | STDIO protocol compliance critical; all output must route correctly |
| Testing/Rollout (T) | 1 | Integration tests needed; no staged rollout required |

### Assumptions

1. Existing services (TreeService, GetNodeService, SearchService) work correctly and have stable interfaces
2. MCP framework library handles JSON-RPC protocol correctly
3. Graph file exists and is valid when MCP server starts
4. STDIO transport is sufficient for initial release (HTTP can come later)

### Dependencies

1. MCP framework library compatible with Python 3.12
2. Pydantic for schema generation (already in fs2)
3. Existing graph infrastructure (NetworkXGraphStore)

### Risks

1. **Protocol compliance**: Any stdout pollution breaks the protocol - requires careful logging setup
2. **Async handling**: SearchService is async; MCP framework must support async tools
3. **Error propagation**: Service errors must translate to agent-friendly messages

### Phases

1. **Phase 1**: Core infrastructure and tree tool
2. **Phase 2**: Get-node and search tools
3. **Phase 3**: CLI integration and testing

---

## Acceptance Criteria

### AC1: Tree Tool Functionality
**Given** an indexed codebase with a valid graph file
**When** an agent calls the tree tool with pattern "."
**Then** the agent receives a hierarchical list of all code elements with node_ids, names, categories, and line locations

### AC2: Tree Tool Filtering
**Given** an indexed codebase
**When** an agent calls the tree tool with pattern "Calculator"
**Then** only nodes containing "Calculator" in their node_id are returned

### AC3: Tree Tool Depth Limiting
**Given** an indexed codebase
**When** an agent calls the tree tool with max_depth=1
**Then** only root-level nodes are returned without their children expanded

### AC4: Get-Node Retrieval
**Given** an indexed codebase and a known node_id
**When** an agent calls get_node with that node_id
**Then** the agent receives the complete CodeNode data including full source content

### AC5: Get-Node Not Found
**Given** an indexed codebase
**When** an agent calls get_node with a non-existent node_id
**Then** the agent receives null/None (not an error)

### AC6: Get-Node Save to File
**Given** an indexed codebase and a valid node_id
**When** an agent calls get_node with save_to_file="output.json"
**Then** the node JSON is written to that file and a confirmation message is returned

### AC7: Search Text Mode
**Given** an indexed codebase
**When** an agent calls search with pattern="config" and mode="text"
**Then** the agent receives nodes containing "config" as substring, sorted by relevance

### AC8: Search Regex Mode
**Given** an indexed codebase
**When** an agent calls search with pattern="def test_.*" and mode="regex"
**Then** the agent receives nodes matching the regex pattern

### AC9: Search Semantic Mode
**Given** an indexed codebase with embeddings
**When** an agent calls search with pattern="error handling logic" and mode="semantic"
**Then** the agent receives conceptually related nodes, sorted by similarity score

### AC10: Search Include/Exclude Filters
**Given** an indexed codebase
**When** an agent calls search with include=["src/"] and exclude=["test"]
**Then** results only include nodes from src/ that don't contain "test" in their path

### AC11: CLI Entry Point
**Given** fs2 is installed
**When** a user runs `fs2 mcp`
**Then** the MCP server starts and listens on STDIO for JSON-RPC messages

### AC12: Config File Support
**Given** fs2 is installed
**When** a user runs `fs2 mcp --config /path/to/config.yaml`
**Then** the server uses the specified config file instead of defaults

### AC13: Protocol Compliance
**Given** the MCP server is running
**When** any tool is called
**Then** only valid JSON-RPC messages appear on stdout; all logging goes to stderr

### AC14: Agent-Friendly Errors
**Given** the MCP server is running and the graph file is missing
**When** any tool is called
**Then** the agent receives a clear error message explaining the issue and suggesting `fs2 scan`

### AC15: Tool Descriptions
**Given** an agent connects to the MCP server
**When** the agent lists available tools
**Then** each tool has a description that explains: what it does, prerequisites, return format, and usage guidance

---

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| STDIO protocol corruption from stray prints | Medium | High | Comprehensive stderr redirection before any imports; code review checklist |
| MCP framework library instability | Low | Medium | Pin to stable version; integration tests catch regressions |
| Async tool handling issues | Low | Medium | Verify framework supports async; test SearchService integration |
| Agent confusion from tool descriptions | Medium | Low | User testing with Claude; iterate on descriptions |

### Assumptions

1. **Graph pre-exists**: Users will have run `fs2 scan` before using MCP server
2. **Local execution**: Server runs locally alongside the codebase; no remote access needed
3. **Single workspace**: Server operates on one graph file at a time
4. **Python 3.12**: Minimum Python version matches fs2 requirements
5. **Stable service interfaces**: TreeService, GetNodeService, SearchService APIs won't change

---

## Open Questions

1. ~~**[RESOLVED: Default working directory]** Default to current directory; `fs2 mcp` works if `.fs2/graph.pickle` exists~~

2. **[DEFERRED: Graph hot-reload]** If the graph file changes while server is running, should changes be detected? (Default: No - restart required)

3. **[DEFERRED: Resource exposure]** Should we expose MCP resources (read-only data URIs) in addition to tools? (Default: Tools only for v1)

4. ~~**[RESOLVED: Tool naming]** Short names: `tree`, `get_node`, `search` (server name provides context)~~

---

## ADR Seeds (Optional)

### Decision: MCP Framework Selection
- **Decision Drivers**: Python-native, decorator-based API, STDIO transport support, async tool support, Pydantic integration, active maintenance
- **Candidate Alternatives**:
  - A: FastMCP (Python-native, decorator-based)
  - B: Raw MCP SDK (lower-level, more control)
  - C: Custom implementation (full control, high effort)
- **Stakeholders**: fs2 maintainers, AI agent users

### Decision: Tool vs Resource for Code Access
- **Decision Drivers**: Agent interaction patterns, caching behavior, read-only nature of code data
- **Candidate Alternatives**:
  - A: Tools only (simpler, explicit invocation)
  - B: Resources for browsing + Tools for search (richer model)
  - C: Resources only (no tool overhead)
- **Stakeholders**: AI agent developers, fs2 users

---

## Unresolved Research

### Topics

From `research-dossier.md` External Research Opportunities not yet addressed:

1. **FastMCP Advanced Patterns**: Error handling, progress reporting, resource vs tool tradeoffs
2. **Claude Desktop MCP Integration**: Exact JSON config format, environment variable passing, debugging

### Impact

- These gaps don't block specification or initial architecture
- May affect implementation details in Phase 2-3
- Progress reporting (opportunity 1) could improve agent UX for large searches

### Recommendation

Consider addressing before Phase 2 implementation to inform error handling and client configuration patterns.

---

## Clarifications

### Session 2025-12-26

**Q1: Workflow Mode**
- **Answer**: B (Full)
- **Rationale**: User preference for comprehensive gates and multi-phase plan structure

**Q2: Testing Strategy**
- **Answer**: A (Full TDD)
- **Rationale**: Comprehensive test coverage for new MCP server module

**Q3: Mock Usage**
- **Answer**: B (Allow targeted mocks)
- **Rationale**: Use existing Fakes for services; targeted mocks for MCP framework/transport testing

**Q4: Documentation Strategy**
- **Answer**: C (Hybrid)
- **Content Split**:
  - README.md: Quick-start (`fs2 mcp` command), Claude Desktop config snippet, link to detailed docs
  - docs/how/: Detailed tool descriptions, troubleshooting guide, architecture overview

**Q5: Default Working Directory**
- **Answer**: A (Default to current directory)
- **Rationale**: `fs2 mcp` just works if `.fs2/graph.pickle` exists in cwd

**Q6: Tool Naming**
- **Answer**: A (Short names: `tree`, `get_node`, `search`)
- **Rationale**: Clean, concise; fs2 server name provides sufficient context

---

## Testing Strategy

- **Approach**: Full TDD
- **Rationale**: New module with protocol compliance requirements; tests verify correct behavior before implementation
- **Focus Areas**:
  - Protocol compliance (stdout/stderr separation)
  - Tool schema generation and validation
  - Service composition (TreeService, GetNodeService, SearchService integration)
  - Error handling and agent-friendly messages
  - CLI entry point functionality
- **Excluded**: Internal service logic (already tested in existing service tests)
- **Mock Usage**: Targeted mocks
  - Use existing Fakes: FakeGraphStore, FakeEmbeddingAdapter, FakeConfigurationService
  - Targeted mocks allowed for: MCP framework transport, STDIO capture, external system boundaries
  - Avoid mocking: Service internals, domain models

---

## Documentation Strategy

- **Location**: Hybrid (README.md + docs/how/)
- **Rationale**: User-facing feature needs both quick-start and detailed reference
- **Content Split**:
  - **README.md**: Quick-start section with `fs2 mcp` command, Claude Desktop JSON config snippet, link to detailed docs
  - **docs/how/mcp-server-guide.md**: Detailed tool descriptions, all parameters, troubleshooting, architecture overview
- **Target Audience**: AI agent developers, Claude Desktop users, fs2 power users
- **Maintenance**: Update docs when tools change; keep Claude Desktop config current

---

**Spec Status**: Clarification complete
**Next Step**: Run `/plan-3-architect` to generate the phase-based plan
