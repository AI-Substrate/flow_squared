# Multi-Graph Support for fs2

**Mode**: Full

📚 This specification incorporates findings from `research-dossier.md` (70+ findings from 7 research subagents).

---

## Research Context

The research dossier provides comprehensive architectural analysis for this feature:

- **Components affected**: ConfigurationService, GraphStore, CLIContext, MCP dependencies, TreeService, SearchService, GetNodeService
- **Critical dependencies**:
  - Config composition uses deep merge (lists must concatenate, not replace)
  - MCP lazy singletons need extension to cache multiple graphs
  - Services extract GraphConfig from ConfigurationService registry
- **Modification risks**:
  - Thread safety in MCP singleton lifecycle
  - 6+ command composition roots need consistent changes
  - NetworkXGraphStore internals have many test dependencies
- **Key patterns identified**: Typed Object Registry, Dependency Injection, Lazy Singleton, Deep Merge
- **Link**: See `research-dossier.md` for full analysis

---

## Summary

**WHAT**: Enable fs2 to load and query multiple named graph files beyond the default `.fs2/graph.pickle`, configured via YAML with names, paths, descriptions, and source URLs.

**WHY**: Coding agents need access to multiple codebases simultaneously—their local project graph plus external reference graphs (libraries, frameworks, prior projects)—for richer context during development. This allows agents to explore how similar problems were solved elsewhere while working on the current project.

---

## Goals

1. **Multiple graph access**: Users can configure and access multiple named graphs from a single fs2 instance
2. **Transparent discovery**: Agents can list all available graphs with their descriptions and availability status
3. **Seamless switching**: All existing tools (tree, search, get-node) can target any configured graph by name
4. **Performance**: Graphs are cached with staleness detection to avoid redundant loading in MCP sessions
5. **Flexible paths**: Support absolute paths, tilde expansion (~), and relative paths for graph locations
6. **Config composition**: Graphs from user config and project config are merged (not replaced), allowing personal reference graphs alongside project-specific ones
7. **Graceful degradation**: Missing graph files are reported as unavailable rather than causing errors

---

## Non-Goals

1. **Remote graph fetching**: No automatic downloading of graphs from URLs (source_url is informational only)
2. **Scan via MCP**: Scan functionality remains intentionally hidden from MCP (agents consume pre-indexed graphs)
3. **Graph synchronization**: No automatic updating of external graphs when source repositories change
4. **Cross-graph queries**: No unified search across multiple graphs in a single query (each query targets one graph)
5. **Graph aliasing**: No shorthand aliases like "local" for the default graph (may be future extension)
6. **Graph discovery**: No automatic scanning for `.fs2/graph.pickle` in sibling directories

---

## Complexity

**Score**: CS-2 (small)

**Breakdown**:
| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 1 | ~8 files modified across config, CLI, MCP, services |
| Integration (I) | 0 | Internal only; NetworkX, Pydantic, FastMCP already in use |
| Data/State (D) | 1 | New config schema (OtherGraphsConfig) but no data migration |
| Novelty (N) | 0 | Well-specified via research; follows existing patterns |
| Non-Functional (F) | 1 | Thread safety required for graph caching |
| Testing (T) | 1 | Integration tests needed for multi-graph scenarios |

**Total**: P = 1+0+1+0+1+1 = 4 → **CS-2**

**Confidence**: 0.85 (high confidence due to comprehensive research)

**Assumptions**:
- Existing fixture graph (`tests/fixtures/fixture_graph.pkl`) can serve as test data
- No performance regression acceptable for single-graph usage
- Config deep merge behavior remains stable

**Dependencies**:
- None external; all dependencies already present

**Risks**:
- Thread safety in cached graph access under concurrent MCP requests
- Config list concatenation may need custom merge logic

**Phases**:
1. Config model addition (OtherGraph, OtherGraphsConfig)
2. GraphService implementation with caching
3. MCP integration (list_graphs tool, graph_name parameter)
4. CLI integration (--graph-name option)

---

## Acceptance Criteria

### AC1: Configuration of multiple graphs
**Given** a user has an `other_graphs` section in either `~/.config/fs2/config.yaml` (user) or `.fs2/config.yaml` (project)
**When** the configuration is loaded
**Then** all configured graphs are recognized and accessible by name

### AC2: List available graphs via MCP
**Given** three graphs are configured (default + two in other_graphs)
**When** an agent calls the `list_graphs` MCP tool
**Then** all three graphs are returned with name, description, path, and availability status

### AC3: Unavailable graph handling
**Given** a graph is configured but its file does not exist
**When** an agent calls `list_graphs`
**Then** the graph appears with `available: false` status (no error thrown)

### AC4: Graph selection in tree tool
**Given** two graphs are available: "default" and "flowspace-original"
**When** an agent calls `tree(pattern=".", graph_name="flowspace-original")`
**Then** results come from the flowspace-original graph, not the default

### AC5: Graph selection in search tool
**Given** two graphs with different content are available
**When** an agent searches for a term that exists only in graph B
**Then** the search returns results only when `graph_name="B"` is specified

### AC6: Graph selection in get_node tool
**Given** a node_id that exists in graph A but not graph B
**When** an agent calls `get_node(node_id=..., graph_name="A")`
**Then** the node is returned successfully

### AC7: CLI --graph-name option
**Given** the CLI has a configured graph named "shared-lib"
**When** a user runs `fs2 tree --graph-name shared-lib`
**Then** the tree displays content from the shared-lib graph

### AC8: Graph caching with staleness detection
**Given** a graph is loaded and cached
**When** the graph file is modified (mtime or size changes)
**Then** the next access reloads the graph from disk

### AC9: Config composition from multiple sources
**Given** user config has graph "personal-ref" and project config has graph "team-lib"
**When** configuration is loaded
**Then** both graphs are available (lists are concatenated, not replaced)

### AC10: Path resolution
**Given** a graph configured with path `~/projects/other/.fs2/graph.pickle`
**When** the graph is accessed
**Then** the tilde is expanded to the user's home directory

### AC11: Default graph unchanged
**Given** no graph_name parameter is provided
**When** any tool (tree, search, get_node) is called
**Then** the default graph (`.fs2/graph.pickle`) is used (backward compatible)

---

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Thread safety issues in graph cache | Medium | High | Use RLock; follow existing MCP singleton pattern |
| Config merge breaks existing behavior | Low | High | Add specific tests for list concatenation |
| Relative path confusion | Medium | Low | Document that paths resolve from MCP server CWD |
| Memory pressure from multiple large graphs | Low | Medium | Lazy loading; only load graphs when accessed |

### Assumptions

1. Users will pre-scan external repositories before adding them to config
2. Graph files are trusted (RestrictedUnpickler provides security boundary)
3. Most users will have 1-5 additional graphs configured (not hundreds)
4. MCP server CWD is predictable (typically project root)

---

## Open Questions

1. **Mutual exclusivity**: ~~Should `--graph-name` and `--graph-file` be mutually exclusive?~~

   **RESOLVED**: Yes, mutually exclusive. Error if both provided. Clear mental model.

2. **Default graph naming**: ~~Should the default graph have a reserved name?~~

   **RESOLVED**: Yes, reserved name "default". `graph_name="default"` refers to `.fs2/graph.pickle`.

3. **Graph metadata exposure**: ~~Should `list_graphs` include metadata?~~

   **RESOLVED**: No, config info only. No file I/O for listing; keeps `list_graphs` fast.

---

## ADR Seeds (Optional)

### ADR-001: Graph Caching Strategy

**Decision Drivers**:
- MCP tools are stateless but server persists across calls
- Graph loading is expensive (disk I/O, pickle deserialization)
- Graphs may be updated externally between calls

**Candidate Alternatives**:
- A: No caching (reload on every call) — simple but slow
- B: Infinite cache (load once, never refresh) — fast but stale
- C: Staleness detection via mtime/size — balanced approach

**Stakeholders**: MCP users, CLI users (less affected)

### ADR-002: Config List Merge Behavior

**Decision Drivers**:
- User config provides personal reference graphs
- Project config provides team/project-specific graphs
- Deep merge is already used for other config sections

**Candidate Alternatives**:
- A: Last wins (project replaces user) — simple but loses user graphs
- B: Concatenate lists (both sources included) — additive, no loss
- C: Named deduplication (later source wins per name) — complex

**Stakeholders**: Users with multi-tier config setups

---

## External Research

**Incorporated**: None (no external-research/*.md files present)

**Recommendation**: The research dossier is comprehensive. No external research appears necessary for this well-bounded feature.

---

## Testing Strategy

- **Approach**: Full TDD
- **Rationale**: Thread-safe caching and multi-component integration require comprehensive test coverage
- **Focus Areas**:
  - GraphService thread safety under concurrent access
  - Config list concatenation (user + project configs)
  - Staleness detection (mtime/size changes)
  - MCP tool graph_name parameter routing
  - Path resolution (absolute, tilde, relative)
- **Excluded**: CLI cosmetic output (Rich formatting details)
- **Mock Usage**: Targeted mocks only
  - May reuse existing fakes: FakeGraphStore, FakeConfigurationService
  - New mocks/fakes require human review before implementation
  - Prefer real fixtures (e.g., `tests/fixtures/fixture_graph.pkl`) where practical

---

## Documentation Strategy

- **Location**: Hybrid (README + docs/how/)
- **Rationale**: New user-facing config schema and MCP tool need both quick-start and detailed reference
- **Content Split**:
  - **README.md**: Brief mention of multi-graph capability in features section
  - **docs/how/user/**: Detailed guide for configuring and using multiple graphs
- **MCP Delivery**: New doc must be registered in `docs/how/user/registry.yaml` for MCP `docs_list`/`docs_get` access
- **Target Audience**:
  - Coding agents needing to explore external reference codebases
  - Users configuring fs2 for multi-project workflows
- **New Documentation Files**:
  - `docs/how/user/multi-graphs.md` - Configuration guide with examples
  - Registry entry with `id: multi-graphs`, category: `how-to`, tags: `[config, graphs, mcp]`
- **Maintenance**: Update when config schema changes or new graph-related features added

---

## Clarifications

### Session 2026-01-13

**Q1: Workflow Mode**
- **Answer**: B (Full)
- **Rationale**: User selected full workflow with multi-phase plan and all gates required

**Q2: Testing Strategy**
- **Answer**: A (Full TDD)
- **Rationale**: Thread-safe caching and MCP integration warrant comprehensive test coverage

**Q3: Mock Usage**
- **Answer**: B (Targeted mocks)
- **Rationale**: Reuse existing mock fixtures (FakeGraphStore, FakeConfigurationService); new mocks require human review

**Q4: Documentation Strategy**
- **Answer**: C (Hybrid)
- **Rationale**: User-facing config and MCP tool need quick-start reference plus detailed guide
- **MCP Delivery**: Register in `docs/how/user/registry.yaml` for agent access via `docs_list`/`docs_get`

**Q5: Mutual Exclusivity (--graph-name vs --graph-file)**
- **Answer**: A (Mutually exclusive)
- **Rationale**: Clear error if both provided; simpler mental model for users

**Q6: Default Graph Naming**
- **Answer**: C (Reserved name "default")
- **Rationale**: Explicit naming convention; `graph_name="default"` refers to `.fs2/graph.pickle`

**Q7: Graph Metadata in list_graphs**
- **Answer**: A (Config info only)
- **Rationale**: No file I/O for listing; keeps `list_graphs` fast. Availability check uses file existence only.

---

## Specification Changelog

| Date | Change |
|------|--------|
| 2026-01-13 | Initial specification created from research dossier |
| 2026-01-13 | Clarification session: 7 questions resolved (Mode, Testing, Mocks, Docs, 3 open questions) |
