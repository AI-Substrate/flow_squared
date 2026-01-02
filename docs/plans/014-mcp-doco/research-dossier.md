# Research Report: MCP Documentation System for fs2

**Generated**: 2026-01-02T00:00:00Z
**Research Query**: "Using flowspace MCP server, review how the flowspace repo has a documentation option on its MCP server. Implement similar functionality for fs2 MCP server so agents can check for documentation articles and read them."
**Mode**: Plan-Associated
**Location**: docs/plans/014-mcp-doco/research-dossier.md
**FlowSpace**: Available
**Findings**: 40+

## Executive Summary

### What We're Building
An MCP documentation system for fs2 that allows AI agents to discover and read documentation articles, enabling self-service guidance on using the fs2 code intelligence tools.

### Business Purpose
AI agents using fs2 MCP tools need contextual help to use the tools effectively. By exposing documentation via MCP, agents can:
- Discover available guides without human intervention
- Read specific documentation when needed (e.g., "how do I add an adapter?")
- Get actionable guidance aligned with project conventions

### Key Insights
1. **Wormhole pattern is ideal**: The `docs_list`/`docs_get` pattern from wormhole provides a clean, proven API for documentation discovery and retrieval
2. **Flowspace has a robust loader**: The flowspace repo implements a `DocumentationLoader` ABC with markdown parsing, section extraction, and caching
3. **fs2 already has excellent docs**: 196 markdown files exist, including 14 how-to guides specifically suited for agent consumption
4. **No frontmatter needed initially**: Existing docs use simple markdown format; metadata can be defined in a registry file

### Quick Stats
- **Existing Documentation**: 196 markdown files, 4.1MB total
- **How-To Guides**: 14 files specifically for development guidance
- **Extension Points**: FastMCP tool registration, dependencies.py for DI
- **Reference Implementation**: Wormhole docs_list/docs_get tools

---

## How Reference Implementations Work

### Wormhole MCP Documentation System

The wormhole MCP server (used by this project) provides two documentation tools:

#### Tool: `docs_list`
**Purpose**: Browse available MCP documentation with optional filtering

**Parameters**:
- `category` (optional): Filter by category (exact match)
- `tags` (optional): Filter by tags (OR logic)

**Response Structure**:
```json
{
  "docs": [
    {
      "id": "debugging-guide",
      "summary": "Hypothesis-driven debugging with breakpoint ladders",
      "category": "documentation",
      "tags": ["debugging", "workflows", "best-practices"]
    }
  ],
  "count": 1
}
```

#### Tool: `docs_get`
**Purpose**: Fetch full documentation content and metadata by ID

**Parameters**:
- `id` (required): Document ID from docs_list (lowercase, hyphens, no spaces)

**Response Structure**:
```json
{
  "id": "debugging-guide",
  "summary": "Brief description",
  "content": "# Full Markdown Content\n\n...",
  "metadata": {
    "tool_name": "docs_debugging_guide",
    "description": "Structured debugging workflow",
    "summary": "Brief description",
    "category": "documentation",
    "tags": ["debugging", "workflows"]
  }
}
```

**Key Design Decisions**:
- IDs are slugified (lowercase, hyphens only)
- Content is returned as full markdown
- Metadata includes category and tags for filtering
- Summaries provide quick context without reading full content

---

### Flowspace Documentation Loader Architecture

The flowspace repository implements a sophisticated documentation system:

#### 1. Abstract Base Class Pattern
**Node ID**: `class:src/modules/mcp/docs_loader.py:DocumentationLoader`

```python
class DocumentationLoader(ABC):
    @abstractmethod
    def load_from_file(self, file_path: Path) -> str:
        """Read entire documentation file."""

    @abstractmethod
    def load_section(self, file_path: Path, section: str) -> Optional[str]:
        """Extract named markdown section."""
```

#### 2. Markdown Implementation
**Node ID**: `class:src/modules/mcp/docs_loader.py:MarkdownDocumentationLoader`

Features:
- Absolute and relative path resolution
- UTF-8 file reading with error handling
- Section extraction by heading level
- Case-insensitive section matching

#### 3. Singleton MCP Loader with Caching
**Node ID**: `class:src/modules/mcp/docs_loader.py:MCPDocumentationLoader`

```python
class MCPDocumentationLoader:
    _docs_cache: Dict[str, str] = {}

    def get_server_docs(self) -> str:
        """Load server.md (cached)"""

    def get_tool_docs(self, tool_name: str) -> str:
        """Load tools/{tool_name}.md (cached)"""
```

#### 4. Documentation File Organization
```
src/modules/mcp/docs/
├── server.md           # Main server documentation
└── tools/
    ├── search_nodes.md # Per-tool documentation
    ├── query.md
    └── ...
```

---

## Current fs2 MCP Server Architecture

### Entry Point and CLI
**File**: `src/fs2/cli/mcp.py`

```python
@app.command()
def mcp():
    """Start the fs2 MCP server."""
    MCPLoggingConfig().configure()  # CRITICAL: Before any fs2 imports
    from fs2.mcp.server import mcp as mcp_server
    mcp_server.run(transport="stdio")
```

### Server and Tool Registration
**File**: `src/fs2/mcp/server.py`

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("fs2")

# Tool registration pattern
@mcp.tool()
async def tree(pattern: str = ".", max_depth: int = 0, detail: str = "min") -> list[dict]:
    """Explore codebase structure as a hierarchical tree."""
    ...

_tree_tool = mcp.tool(
    annotations={
        "title": "Explore Code Tree",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)(tree)
```

### Dependency Injection
**File**: `src/fs2/mcp/dependencies.py`

Thread-safe singleton pattern with lazy initialization:
```python
_lock = RLock()
_config: FS2ConfigurationService | None = None

def get_config() -> FS2ConfigurationService:
    global _config
    with _lock:
        if _config is None:
            _config = FS2ConfigurationService()
        return _config
```

### Error Translation
**File**: `src/fs2/mcp/server.py` (lines 76-125)

```python
def translate_error(exc: Exception) -> dict[str, Any]:
    """Convert domain exceptions to agent-friendly responses."""
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "action": "Suggested fix..."  # Actionable guidance
    }
```

### Extension Points Identified

| Extension Point | Location | Purpose |
|-----------------|----------|---------|
| New Tool Registration | `server.py` after line 706 | Add `docs_list`, `docs_get` tools |
| Service Creation | `src/fs2/core/services/` | Create `DocsService` |
| Dependency Injection | `dependencies.py` | Add `get_docs_service()` |
| Data Conversion | `server.py` | Add `_doc_to_dict()` helper |
| Error Handling | `translate_error()` | Add doc-specific errors |

---

## Existing fs2 Documentation Inventory

### Documentation Structure
```
docs/
├── how/                          # 14 how-to guides (PRIMARY TARGET)
│   ├── adding-services-adapters.md   # 406 lines - Adapter/service patterns
│   ├── mcp-server-guide.md           # 387 lines - MCP setup
│   ├── wormhole-mcp-guide.md         # 292 lines - VS Code integration
│   ├── llm-adapter-extension.md      # 259 lines - LLM extension
│   ├── scanning.md                   # 252 lines - Graph scanning
│   ├── llm-service-setup.md          # 192 lines - LLM configuration
│   ├── AGENTS.md                     # 182 lines - AI agent guidance
│   ├── tdd.md                        # 72 lines - TDD patterns
│   ├── di.md                         # 67 lines - DI patterns
│   ├── configuration.md              # 56 lines - Config system
│   ├── architecture.md               # 52 lines - Clean Architecture
│   └── embeddings/
│       ├── 1-overview.md             # Embedding architecture
│       ├── 2-configuration.md        # Config schema
│       └── 3-providers.md            # Provider adapters
├── rules-idioms-architecture/    # 4 governance documents
│   ├── constitution.md               # 14.4 KB - Principles
│   ├── rules.md                      # 12.7 KB - Normative rules
│   ├── idioms.md                     # 18.6 KB - Code patterns
│   └── architecture.md               # 16.6 KB - Boundaries
└── plans/                        # ~140+ plan documents
```

### Document Characteristics
- **Format**: Pure markdown (no YAML frontmatter)
- **Headers**: Start with `# Title`
- **Cross-links**: Reference other docs via relative paths
- **Code examples**: Extensive working code patterns
- **Versioning**: Some include version/date in body text

### Tier 1 - High Priority for Agents
| ID | File | Description |
|----|------|-------------|
| `agents` | `docs/how/AGENTS.md` | Agent-specific guidance for using fs2 |
| `adding-services-adapters` | `docs/how/adding-services-adapters.md` | Clean Architecture patterns |
| `architecture` | `docs/how/architecture.md` | Layer boundaries and rules |
| `mcp-server-guide` | `docs/how/mcp-server-guide.md` | MCP server setup |
| `constitution` | `docs/rules-idioms-architecture/constitution.md` | Guiding principles |

### Tier 2 - Workflow-Specific
| ID | File | Description |
|----|------|-------------|
| `scanning` | `docs/how/scanning.md` | Graph scanning |
| `tdd` | `docs/how/tdd.md` | Test patterns |
| `configuration` | `docs/how/configuration.md` | Config system |
| `di` | `docs/how/di.md` | Dependency injection |

---

## Recommended Implementation Design

### API Design

#### Tool: `docs_list`
```python
@mcp.tool()
async def docs_list(
    category: str | None = None,
    tags: list[str] | None = None
) -> dict:
    """
    Browse available fs2 documentation.

    Args:
        category: Filter by category ("how-to", "rules", "reference")
        tags: Filter by tags (OR logic)

    Returns:
        List of documents with id, title, summary, category, tags
    """
```

#### Tool: `docs_get`
```python
@mcp.tool()
async def docs_get(id: str) -> dict:
    """
    Fetch full documentation content by ID.

    Args:
        id: Document ID from docs_list (e.g., "adding-services-adapters")

    Returns:
        Document with id, title, content (markdown), metadata
    """
```

### Data Model

```python
@dataclass(frozen=True)
class DocMetadata:
    id: str              # Slugified identifier
    title: str           # Human-readable title
    summary: str         # 1-2 sentence description
    category: str        # "how-to" | "rules" | "reference"
    tags: tuple[str, ...]  # Filterable tags
    path: str            # Relative path to markdown file

@dataclass(frozen=True)
class Doc:
    metadata: DocMetadata
    content: str         # Full markdown content
```

### Registry Approach (Recommended)

Rather than parsing frontmatter, use a registry file to define document metadata:

**File**: `src/fs2/mcp/docs/registry.yaml`
```yaml
documents:
  - id: agents
    title: AI Agent Guidance
    summary: How AI agents should use fs2 MCP tools effectively
    category: how-to
    tags: [agents, mcp, tools]
    path: docs/how/AGENTS.md

  - id: adding-services-adapters
    title: Adding Services and Adapters
    summary: Step-by-step guide for implementing new adapters, services, and config types
    category: how-to
    tags: [architecture, adapters, services, clean-architecture]
    path: docs/how/adding-services-adapters.md

  # ... more documents
```

### Architecture

```
src/fs2/
├── core/
│   ├── models/
│   │   └── doc.py                # Doc, DocMetadata dataclasses
│   ├── services/
│   │   └── docs_service.py       # DocsService (loads registry, reads files)
│   └── repos/
│       └── docs_repo.py          # DocsRepository ABC + implementation
└── mcp/
    ├── docs/
    │   └── registry.yaml         # Document metadata registry
    └── server.py                 # Add docs_list, docs_get tools
```

### Clean Architecture Compliance

Following fs2 patterns:
1. **ABC Interface**: `DocsRepository` protocol for loading docs
2. **Service Composition**: `DocsService` composes repository + config
3. **Frozen Dataclasses**: `Doc`, `DocMetadata` as immutable domain models
4. **Dependency Injection**: Via `dependencies.py` with lazy initialization
5. **Error Translation**: Doc-specific errors in `translate_error()`

---

## Modification Considerations

### Safe to Modify
- `src/fs2/mcp/server.py` - Add new tools (follows existing patterns)
- `src/fs2/mcp/dependencies.py` - Add docs service getter
- `src/fs2/core/services/` - Add new service

### Modify with Caution
- Tool annotations must be correct (readOnlyHint=True for docs tools)
- Logging must go to stderr (stdout reserved for MCP protocol)

### Extension Pattern to Follow
Look at existing tools (`tree`, `get_node`, `search`) for:
- Tool registration with `@mcp.tool()` decorator
- Annotation patterns for readOnlyHint, etc.
- Error handling with translate_error()
- Data conversion helpers (`_tree_node_to_dict`, etc.)

---

## Critical Discoveries

### Discovery 01: MCP Logging Constraint
**Impact**: Critical
**Source**: fs2 MCP implementation research
**Description**: stdout is 100% reserved for MCP JSON-RPC protocol. All logging must go to stderr via `MCPLoggingConfig().configure()` called BEFORE any fs2 imports.
**Required Action**: Any new code must not print to stdout.

### Discovery 02: Tool Annotation Requirements
**Impact**: High
**Source**: fs2 MCP server.py analysis
**Description**: MCP tools should have proper annotations:
- `readOnlyHint=True` for docs tools (they only read)
- `destructiveHint=False`
- `idempotentHint=True` (same inputs = same outputs)
- `openWorldHint=False` (no external network calls)

### Discovery 03: Registry vs Frontmatter Trade-off
**Impact**: Medium
**Source**: Documentation analysis
**Description**: Existing docs don't use YAML frontmatter. Two options:
1. **Registry file** (recommended): Centralized metadata, no doc changes needed
2. **Add frontmatter**: More work, requires updating all docs
**Recommendation**: Use registry approach initially; can migrate to frontmatter later.

### Discovery 04: Existing AGENTS.md is Perfect Starting Point
**Impact**: Medium
**Source**: Documentation inventory
**Description**: `docs/how/AGENTS.md` already contains agent-specific guidance. This should be the first document exposed via MCP.

---

## Prior Learnings

No directly relevant prior learnings found for MCP documentation systems. However, the following patterns from prior phases apply:

1. **Clean Architecture enforcement** (from 003-fs2-base): Services compose adapters/repos via injection
2. **Lazy initialization pattern** (from MCP implementation): Use `_ensure_loaded()` for deferred work
3. **Registry pattern** (from FlowSpace): YAML registry files work well for metadata

---

## Recommendations

### If Implementing This Feature

1. **Start with registry approach**: Define metadata in YAML, don't modify existing docs
2. **Expose 5-10 docs initially**: Focus on Tier 1 high-priority docs
3. **Follow existing tool patterns**: Copy `tree` tool structure for `docs_list`/`docs_get`
4. **Use frozen dataclasses**: `Doc`, `DocMetadata` following fs2 patterns
5. **Add caching**: Cache loaded documents like flowspace's `MCPDocumentationLoader`

### Implementation Order

1. Create `DocMetadata` and `Doc` domain models
2. Create `docs/registry.yaml` with initial 5 documents
3. Create `DocsService` to load registry and read files
4. Add `docs_list` tool to server.py
5. Add `docs_get` tool to server.py
6. Add tests following TDD pattern

### Success Criteria

- [ ] `docs_list` returns list of available documents
- [ ] `docs_list` supports category/tag filtering
- [ ] `docs_get` returns full document content
- [ ] Documents are cached after first load
- [ ] Error messages are agent-friendly
- [ ] All tests pass
- [ ] Documentation updated

---

## External Research Opportunities

No external research gaps identified. The reference implementations (wormhole, flowspace) provide sufficient guidance for implementation.

---

## Appendix: Key File References

| Purpose | File |
|---------|------|
| MCP CLI Entry | `src/fs2/cli/mcp.py` |
| MCP Server | `src/fs2/mcp/server.py` |
| Dependencies | `src/fs2/mcp/dependencies.py` |
| Example Service | `src/fs2/core/services/tree_service.py` |
| Example Model | `src/fs2/core/models/code_node.py` |
| Primary Docs | `docs/how/*.md` |
| Governance Docs | `docs/rules-idioms-architecture/*.md` |

---

## Next Steps

1. Run `/plan-1b-specify` to create feature specification
2. Or proceed directly to `/plan-3-architect` if requirements are clear

---

**Research Complete**: 2026-01-02
**Report Location**: docs/plans/014-mcp-doco/research-dossier.md
