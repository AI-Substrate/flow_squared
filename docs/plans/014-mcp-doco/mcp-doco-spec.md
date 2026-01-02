# MCP Documentation Tools for fs2

**Mode**: Full

> This specification incorporates findings from `research-dossier.md`

## Research Context

Based on comprehensive research of reference implementations (wormhole, flowspace):

- **Components affected**: `src/fs2/mcp/server.py`, `src/fs2/mcp/dependencies.py`, new service and model files
- **Critical dependencies**: FastMCP tool registration, existing MCP infrastructure
- **Modification risks**: Low - follows established patterns; stdout/stderr logging constraint is critical
- **Link**: See `research-dossier.md` for full analysis

---

## Summary

**WHAT**: Add two MCP tools (`docs_list`, `docs_get`) that allow AI agents to discover and read fs2 documentation directly through the MCP protocol.

**WHY**: AI agents using fs2 MCP tools need contextual help to use the tools effectively. Currently, agents must rely on external knowledge or user intervention to understand fs2 patterns, architecture conventions, and tool usage. By exposing documentation via MCP, agents can:

- Self-serve documentation without human intervention
- Discover available guides relevant to their current task
- Read specific documentation when needed (e.g., "how do I add an adapter?")
- Get actionable guidance aligned with project conventions

---

## Goals

1. **Agent self-service**: Enable AI agents to discover and read documentation without human intervention
2. **Discoverability**: Provide a browsable catalog of available documentation with filtering by category and tags
3. **Complete content access**: Return full markdown content for deep reading when needed
4. **Minimal friction**: No changes required to existing documentation files (use registry approach)
5. **Consistent patterns**: Follow established fs2 MCP tool patterns (FastMCP, Clean Architecture, frozen dataclasses)
6. **Agent-friendly errors**: Provide actionable error messages when documents aren't found

---

## Non-Goals

1. **Documentation editing**: This feature is read-only; no write/update capabilities
2. **Full-text search**: No semantic or keyword search within document content (use existing fs2 search tools for code)
3. **Documentation generation**: Does not auto-generate documentation from code
4. **Frontmatter migration**: Existing docs remain unchanged; metadata lives in registry file
5. **All 196 documents**: Initial scope is 5-10 high-priority documents, not the entire docs folder
6. **Cross-document linking**: No automatic resolution of markdown links between documents
7. **Version history**: No versioning or change tracking of documentation

---

## Complexity

**Score**: CS-2 (small)

**Breakdown**:
| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 1 | Multiple files: models, service, server.py, dependencies.py, registry.yaml, tests |
| Integration (I) | 0 | Internal only; no external dependencies |
| Data/State (D) | 0 | No schema/migrations; YAML registry file only |
| Novelty (N) | 0 | Well-specified with reference implementations (wormhole, flowspace) |
| Non-Functional (F) | 0 | Standard performance; no special security requirements |
| Testing (T) | 1 | Integration tests needed for MCP tools |

**Total**: P = 2 → CS-2

**Confidence**: 0.90 (high confidence due to comprehensive research and clear reference implementations)

**Assumptions**:
- Registry file approach is acceptable (no need for frontmatter)
- 5-10 initial documents is sufficient scope
- Existing FastMCP patterns work for new tools
- No performance concerns with reading markdown files synchronously

**Dependencies**:
- Existing MCP server infrastructure must be stable
- `docs/how/*.md` files exist and are well-formed markdown

**Risks**:
- Low: stdout logging could break MCP protocol (mitigated by existing patterns)
- Low: Large documents could impact response size (mitigated by targeting curated docs)

**Phases**:
1. Domain models and registry
2. DocsService implementation
3. MCP tool integration
4. Testing and documentation

---

## Acceptance Criteria

### AC1: docs_list returns document catalog with actionable summaries
**Given** the MCP server is running
**When** an agent calls `docs_list()` with no parameters
**Then** the response contains a list of all registered documents with:
- `id` (string, slugified)
- `title` (string, human-readable)
- `summary` (string, 1-2 sentences describing WHAT the doc covers and WHEN to use it)
- `category` (string, e.g., "how-to", "reference")
- `tags` (list of strings)
- `count` (total number of documents)

**Summary quality requirement**: Summaries must drive discoverability by clearly stating:
- What problem/question this doc answers
- When an agent should read this doc

### AC2: docs_list supports category filtering
**Given** the MCP server is running
**When** an agent calls `docs_list(category="how-to")`
**Then** the response contains only documents with `category="how-to"`

### AC3: docs_list supports tag filtering
**Given** the MCP server is running
**When** an agent calls `docs_list(tags=["architecture", "mcp"])`
**Then** the response contains documents matching ANY of the specified tags (OR logic)

### AC4: docs_get returns full document content
**Given** the MCP server is running and document "agents" exists in registry
**When** an agent calls `docs_get(id="agents")`
**Then** the response contains:
- `id` (matching the request)
- `title` (human-readable)
- `content` (full markdown content of the file)
- `metadata` (category, tags, summary)

### AC5: docs_get returns agent-friendly error for unknown document
**Given** the MCP server is running
**When** an agent calls `docs_get(id="nonexistent-doc")`
**Then** the response contains:
- `type`: error type identifier
- `message`: human-readable error description
- `action`: suggested remediation (e.g., "Use docs_list() to see available documents")

### AC6: Initial document set includes two curated docs
**Given** the registry is configured in `src/fs2/docs/registry.yaml`
**When** an agent calls `docs_list()`
**Then** the response includes:
- `agents` → `src/fs2/docs/agents.md` (copied from `docs/how/AGENTS.md`)
- `sample-config` → `src/fs2/docs/sample-config.yaml` (annotated YAML based on `.fs2/config.yaml`, identifiable info removed)

### AC9: In-app documentation mechanism documented in idioms
**Given** the feature is complete
**When** a future agent reads `docs/rules-idioms-architecture/idioms.md`
**Then** they find documentation explaining:
- The `src/fs2/docs/` pattern for distributable in-app documentation
- How to add new curated docs (create file + add to registry.yaml)
- The separation between `docs/how/` (developer) and `src/fs2/docs/` (user)

### AC7: Tools have correct MCP annotations
**Given** the tools are registered
**When** inspecting tool definitions
**Then** both `docs_list` and `docs_get` have:
- `readOnlyHint=True`
- `destructiveHint=False`
- `idempotentHint=True`
- `openWorldHint=False`

### AC8: Documents loaded via importlib.resources
**Given** the MCP server is running (installed via uvx or local)
**When** an agent calls `docs_get(id="agents")`
**Then** the document is loaded from the bundled `fs2.docs` package resources

---

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| stdout logging breaks MCP | Low | High | Follow existing MCPLoggingConfig pattern; all logging to stderr |
| Large document overwhelms response | Low | Medium | Curate initial document set; consider pagination for future |
| Registry out of sync with docs | Medium | Low | Keep registry minimal; validate paths at startup |
| Breaking existing tools | Low | High | Add tools without modifying existing code paths |

### Assumptions

1. **Registry approach is acceptable**: Metadata lives in YAML file, not in document frontmatter
2. **Sync loading is fine**: Documents are small enough that sync file reads won't block
3. **UTF-8 encoding**: All documentation files are UTF-8 encoded
4. **Relative paths work**: Registry paths are relative to project root
5. **No circular dependencies**: DocsService doesn't depend on other fs2 services

---

## Open Questions

1. **[RESOLVED by research]** Should we use frontmatter or registry? → Registry approach recommended
2. **[RESOLVED by research]** What documents to include initially? → Tier 1 high-priority docs (5 minimum)
3. **[RESOLVED]** Cache invalidation → No caching; read from `importlib.resources` each time (docs are small, bundled)
4. **[RESOLVED]** Registry & docs location → `src/fs2/docs/` (bundled with package for uvx distribution)
5. **[RESOLVED]** Section extraction → Full document only; curated docs are concise enough
6. **[RESOLVED]** Doc source strategy → Curated in-app docs (separate from `docs/how/`; user-focused, not developer-focused)

---

## ADR Seeds (Optional)

### ADR-001: Registry vs Frontmatter for Document Metadata

**Decision Drivers**:
- Existing docs have no frontmatter (pure markdown)
- Centralized metadata is easier to maintain
- Frontmatter would require modifying 196 files

**Candidate Alternatives**:
- A: YAML registry file (centralized metadata, no doc changes)
- B: Add YAML frontmatter to each document (metadata in-place)
- C: Auto-generate metadata from markdown headers (least accurate)

**Stakeholders**: Project maintainers, AI agents using fs2

---

## Appendix: Example API Responses

### docs_list() response
```json
{
  "docs": [
    {
      "id": "agents",
      "title": "AI Agent Guidance",
      "summary": "Best practices for AI agents using fs2 tools. Read this FIRST when starting to use fs2 MCP server to understand tool selection, search strategies, and common workflows.",
      "category": "how-to",
      "tags": ["agents", "mcp", "getting-started"]
    },
    {
      "id": "sample-config",
      "title": "Sample Configuration",
      "summary": "Annotated example of .fs2/config.yaml with all options explained. Use when setting up fs2 for the first time or troubleshooting configuration issues.",
      "category": "reference",
      "tags": ["config", "setup", "yaml"]
    }
  ],
  "count": 2
}
```

### docs_get(id="agents") response
```json
{
  "id": "agents",
  "title": "AI Agent Guidance",
  "content": "# AI Agent Guidance\n\nThis document describes...",
  "metadata": {
    "summary": "Best practices for AI agents using fs2 tools. Read this FIRST when starting to use fs2 MCP server to understand tool selection, search strategies, and common workflows.",
    "category": "how-to",
    "tags": ["agents", "mcp", "getting-started"]
  }
}
```

---

## Testing Strategy

- **Approach**: Full TDD
- **Rationale**: Feature adds MCP tools with filtering logic and error handling; comprehensive tests ensure reliability
- **Focus Areas**:
  - DocsService registry loading and document retrieval
  - Filtering logic (category, tags with OR semantics)
  - Error handling (missing documents, invalid IDs)
  - MCP tool integration (response format, annotations)
- **Excluded**: Manual testing of MCP protocol transport (covered by FastMCP)
- **Mock Usage**: Avoid mocks entirely
  - Use real fixtures (sample markdown files, test registry.yaml in `tests/fixtures/`)
  - Follows fs2 "Fakes over mocks" pattern from CLAUDE.md
  - If ABC needed for DocsRepository, implement FakeDocsRepository with in-memory data

### MCP Test Patterns (from codebase research)

**Fixture Architecture**:
```python
# Inject fakes before creating client
dependencies.reset_services()
dependencies.set_config(config)
dependencies.set_graph_store(store)

async with Client(mcp) as client:
    yield client
```

**Dual Testing**:
1. **Direct function call** (unit): `result = docs_list(category="how-to")`
2. **MCP protocol** (integration): `await mcp_client.call_tool("docs_list", {"category": "how-to"})`

**Response Parsing**:
```python
result = await mcp_client.call_tool("docs_list", {})
data = json.loads(result.content[0].text)
```

**Autouse Cleanup**: `reset_mcp_dependencies` fixture resets singletons after each test

---

## Documentation Strategy

- **Location**: README.md only
- **Rationale**: Quick-start documentation for MCP tools; detailed MCP info already in docs/how/mcp-server-guide.md
- **Content**:
  - Add section to README showing `docs_list` and `docs_get` tool usage
  - Brief examples of filtering by category/tags
  - Link to existing mcp-server-guide.md for setup details
- **Target Audience**: AI agents and developers using fs2 MCP server
- **Maintenance**: Update README when new documents are added to registry

---

## Clarifications

### Session 2026-01-02

**Q1: Workflow Mode**
- **Selected**: Full
- **Rationale**: User preference for comprehensive gates and multi-phase planning

**Q2: Testing Strategy**
- **Selected**: Full TDD
- **Rationale**: Comprehensive coverage for MCP tools with filtering, caching, and error handling

**Q3: Mock Usage**
- **Selected**: Avoid mocks entirely
- **Rationale**: Aligns with fs2 "Fakes over mocks" pattern; use real fixtures and FakeDocsRepository if needed

**Q4: Documentation Strategy**
- **Selected**: README.md only
- **Rationale**: Quick-start docs; detailed MCP setup already in docs/how/mcp-server-guide.md

**Q5: Registry & Docs Location**
- **Selected**: `src/fs2/docs/` (registry.yaml + curated markdown files)
- **Rationale**: Must be bundled with package for uvx distribution; use `importlib.resources` at runtime

**Q6: Doc Source Strategy**
- **Selected**: Curated in-app docs (Option B)
- **Rationale**:
  - `docs/how/` = Developer docs for repo contributors
  - `src/fs2/docs/` = Curated user help, distributable via uvx
  - No build step; manually maintained; agent/user-optimized

**Q7: Cache Invalidation**
- **Selected**: No caching
- **Rationale**: Read from `importlib.resources` each time; docs are small and bundled, minimal perf impact

**Q8: Section Extraction**
- **Selected**: Full document only
- **Rationale**: Curated docs are concise; no need for section parsing complexity

**Q9: Initial Documentation Set**
- **Selected**: Two docs created during plan execution
- **Documents**:
  1. `agents.md` - Copy of `docs/how/AGENTS.md`
  2. `sample-config.yaml` - Annotated YAML from `.fs2/config.yaml` (identifiable info removed, detailed comments)
- **Additional**: Update `idioms.md` to document this mechanism for future agents

---

## Clarification Summary

| Topic | Resolution |
|-------|------------|
| Workflow Mode | Full |
| Testing Strategy | Full TDD |
| Mock Usage | Avoid mocks; use fixtures and fakes |
| Documentation | README.md only |
| Registry Location | `src/fs2/docs/registry.yaml` |
| Doc Source | Curated in-app docs (separate from `docs/how/`) |
| Cache Strategy | No caching |
| Section Extraction | Full document only |
| Initial Docs | `agents.md` (copy) + `sample-config.yaml` (annotated) |

**Resolved**: 9/9 questions
**Deferred**: 0
**Outstanding**: 0

---

**Specification Status**: Ready for architecture
**Next Step**: Run `/plan-3-architect` to generate phase-based plan
