# MCP Documentation Tools Implementation Plan

**Plan Version**: 1.0.0
**Created**: 2026-01-02
**Spec**: [./mcp-doco-spec.md](./mcp-doco-spec.md)
**Status**: DRAFT

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Technical Context](#technical-context)
3. [Critical Research Findings](#critical-research-findings)
4. [Testing Philosophy](#testing-philosophy)
5. [Implementation Phases](#implementation-phases)
   - [Phase 1: Domain Models and Registry](#phase-1-domain-models-and-registry)
   - [Phase 2: DocsService Implementation](#phase-2-docsservice-implementation)
   - [Phase 3: MCP Tool Integration](#phase-3-mcp-tool-integration)
   - [Phase 4: Curated Documentation](#phase-4-curated-documentation)
   - [Phase 5: Testing and Documentation](#phase-5-testing-and-documentation)
6. [Cross-Cutting Concerns](#cross-cutting-concerns)
7. [Complexity Tracking](#complexity-tracking)
8. [Progress Tracking](#progress-tracking)
9. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

**Problem**: AI agents using fs2 MCP tools need contextual help to use the tools effectively. Currently, agents must rely on external knowledge or user intervention to understand fs2 patterns, tool usage, and configuration options.

**Solution**:
- Add two MCP tools (`docs_list`, `docs_get`) for documentation discovery and retrieval
- Bundle curated documentation in `src/fs2/docs/` for uvx distribution
- Use registry.yaml for centralized metadata (no frontmatter changes needed)
- Follow established fs2 MCP patterns (FastMCP, Clean Architecture, TDD)

**Expected Outcomes**:
- Agents can self-serve documentation without human intervention
- Discoverability via category and tag filtering
- Full markdown content access for deep reading
- Works with `uvx fs2 mcp` distribution

**Success Metrics**:
- `docs_list()` returns catalog with actionable summaries
- `docs_get(id)` returns full document content
- All 9 acceptance criteria from spec pass
- 100% test coverage for new code

---

## Technical Context

### Current System State

The fs2 MCP server (`src/fs2/mcp/server.py`) provides three tools:
- `tree` - Explore codebase structure
- `get_node` - Retrieve complete source code
- `search` - Find code by content or meaning

**Extension points identified**:
| Extension Point | Location | Purpose |
|-----------------|----------|---------|
| Tool Registration | `server.py` after line 706 | Add `docs_list`, `docs_get` |
| Service Creation | `src/fs2/core/services/` | Create `DocsService` |
| Dependency Injection | `dependencies.py` | Add `get_docs_service()` |
| Package Resources | `src/fs2/docs/` | Bundled documentation |

### Integration Requirements

- **importlib.resources**: Use `importlib.resources.files("fs2.docs")` for package resource access
- **pyproject.toml**: Add docs to wheel include patterns
- **FastMCP**: Register tools with `@mcp.tool()` decorator and annotations
- **Dependency Injection**: Follow thread-safe singleton pattern in `dependencies.py`

### Constraints and Limitations

- **stdout reserved**: All logging must go to stderr (MCP JSON-RPC protocol)
- **No caching**: Read from importlib.resources each call (docs are small)
- **Full document only**: No section extraction in initial version
- **Curated docs only**: 2 initial docs (agents.md, configuration-guide.md)

### Assumptions

1. Registry file approach is acceptable (no frontmatter)
2. importlib.resources works for both editable and wheel installs
3. Curated docs are small enough that sync reads are acceptable
4. UTF-8 encoding for all documentation files

---

## Critical Research Findings

### 🚨 Critical Finding 01: MCP Protocol Integrity (stdout/stderr)

**Impact**: Critical
**Sources**: [Research Dossier, R1-01]

**Problem**: stdout is 100% reserved for MCP JSON-RPC protocol. Any print statements or unrouted logging corrupts the protocol stream.

**Solution**:
- Use `logging.debug()` routed to stderr
- Defer resource loading to first tool call (not import time)
- Follow `MCPLoggingConfig` pattern

**Example**:
```python
# ❌ WRONG - breaks MCP protocol
print("Loading registry...")

# ✅ CORRECT - stderr only
logger.debug("Loading registry...")
```

**Affects Phases**: 2, 3

---

### 🚨 Critical Finding 02: importlib.resources Wheel Compatibility

**Impact**: Critical
**Sources**: [I1-03, R1-02, R1-07]

**Problem**: Package resources must work both in development (editable install) and production (wheel). The `importlib.resources.files()` API returns a Traversable, not a filesystem Path.

**Solution**:
- Never call `.resolve()` or assume filesystem paths
- Use only: `.is_file()`, `.read_text()`, `.joinpath()`
- Add docs to pyproject.toml wheel includes
- Follow `TemplateService` pattern exactly

**Example**:
```python
# ❌ WRONG - assumes filesystem
path = importlib_resources.files("fs2.docs").resolve() / "registry.yaml"

# ✅ CORRECT - Traversable API
registry_file = importlib_resources.files("fs2.docs") / "registry.yaml"
content = registry_file.read_text(encoding="utf-8")
```

**Affects Phases**: 1, 2

---

### 🔴 High Finding 03: Tool Annotation Requirements

**Impact**: High
**Sources**: [Research Dossier Discovery 02, R1-05]

**Problem**: MCP tools require proper annotations for agent behavior hints. Incorrect annotations cause agents to misclassify tool behavior.

**Solution**: Both `docs_list` and `docs_get` must have:
- `readOnlyHint=True` (no side effects)
- `destructiveHint=False`
- `idempotentHint=True` (same inputs = same outputs)
- `openWorldHint=False` (no external network calls)

**Affects Phases**: 3

---

### 🔴 High Finding 04: Registry Validation

**Impact**: High
**Sources**: [R1-03]

**Problem**: Invalid registry.yaml (typos, missing fields) causes cryptic errors at tool call time instead of failing fast.

**Solution**:
- Create Pydantic model for registry schema
- Validate eagerly on first tool call
- Provide actionable error messages

**Affects Phases**: 1, 2

---

### 🟡 Medium Finding 05: Dependency Injection Pattern

**Impact**: Medium
**Sources**: [I1-02, R1-06]

**Problem**: MCP server uses module-level singletons. DocsService must follow same pattern for consistency and testability.

**Solution**: Add to `dependencies.py`:
- `get_docs_service()` - lazy singleton getter
- `set_docs_service()` - test injection
- `reset_docs_service()` - cleanup

**Affects Phases**: 2

---

### 🟡 Medium Finding 06: Error Translation

**Impact**: Medium
**Sources**: [R1-04]

**Problem**: Resource loading failures return generic "Unexpected error" instead of actionable messages.

**Solution**:
- Create `DocsNotFoundError` domain exception
- Add handler in `translate_error()`
- Provide actionable "Use docs_list() to see available documents"

**Affects Phases**: 2, 3

---

### 🟡 Medium Finding 07: JSON Serialization Safety

**Impact**: Medium
**Sources**: [R1-08]

**Problem**: Pydantic models are not JSON-serializable by default. Tool responses must be plain dicts.

**Solution**: Always use `.model_dump()` before returning from tools.

**Affects Phases**: 3

---

### 🟢 Low Finding 08: Test Fixture Architecture

**Impact**: Low
**Sources**: [I1-06]

**Problem**: Tests need isolated registry and docs without affecting other tests.

**Solution**:
- Add `reset_mcp_dependencies` call for docs
- Create sample registry fixture
- Use real fixture files (no mocks)

**Affects Phases**: 5

---

## Testing Philosophy

### Testing Approach

**Selected Approach**: Full TDD
**Rationale**: Feature adds MCP tools with filtering logic and error handling; comprehensive tests ensure reliability
**Focus Areas**:
- DocsService registry loading and document retrieval
- Filtering logic (category, tags with OR semantics)
- Error handling (missing documents, invalid IDs)
- MCP tool integration (response format, annotations)

### Test-Driven Development

All code follows RED-GREEN-REFACTOR:
1. Write failing test first (RED)
2. Implement minimal code to pass (GREEN)
3. Refactor for quality (REFACTOR)

### Mock Usage

**Policy**: Avoid mocks entirely
- Use real fixtures (sample markdown files, test registry.yaml)
- Follow fs2 "Fakes over mocks" pattern
- If ABC needed, implement FakeDocsService with in-memory data

### Dual Testing Strategy

1. **Direct function call** (unit): `result = docs_list(category="how-to")`
2. **MCP protocol** (integration): `await mcp_client.call_tool("docs_list", {...})`

Both must pass to ensure tool function works AND FastMCP serialization works.

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

### Phase 1: Domain Models and Registry

**Objective**: Create domain models for documentation and registry structure with TDD.

**Deliverables**:
- `DocMetadata` frozen dataclass
- `Doc` frozen dataclass
- `DocsRegistry` Pydantic model for validation
- Registry schema with validation

**Dependencies**: None (foundational phase)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Schema too restrictive | Low | Low | Start minimal, extend as needed |
| Pydantic version issues | Low | Medium | Use v2 patterns only |

#### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 1.1 | [ ] | Write tests for DocMetadata frozen dataclass | 1 | Tests verify: immutability, required fields (id, title, summary, category, tags, path), type validation | - | Create `tests/unit/models/test_doc.py` |
| 1.2 | [ ] | Implement DocMetadata in `src/fs2/core/models/doc.py` | 1 | All tests from 1.1 pass | - | Frozen dataclass with tuple for tags |
| 1.3 | [ ] | Write tests for Doc frozen dataclass | 1 | Tests verify: metadata field, content field, immutability | - | Extends test_doc.py |
| 1.4 | [ ] | Implement Doc dataclass | 1 | All tests from 1.3 pass | - | Simple composition |
| 1.5 | [ ] | Write tests for DocsRegistry Pydantic model | 2 | Tests verify: YAML parsing, validation errors, field constraints (id pattern) | - | Create `tests/unit/models/test_docs_registry.py` |
| 1.6 | [ ] | Implement DocsRegistry Pydantic model | 2 | All tests from 1.5 pass, validates registry.yaml structure | - | Pattern `^[a-z0-9-]+$` for IDs |
| 1.7 | [ ] | Export models from `src/fs2/core/models/__init__.py` | 1 | Can import `from fs2.core.models import DocMetadata, Doc` | - | |

#### Test Examples (Write First!)

```python
# tests/unit/models/test_doc.py
import pytest
from fs2.core.models.doc import DocMetadata, Doc

class TestDocMetadata:
    """Tests for DocMetadata frozen dataclass."""

    def test_docmetadata_is_frozen(self):
        """
        Purpose: Proves DocMetadata is immutable
        Quality Contribution: Prevents accidental state mutation
        Acceptance Criteria: AttributeError on assignment
        """
        meta = DocMetadata(
            id="test-doc",
            title="Test Document",
            summary="A test document",
            category="how-to",
            tags=("test",),
            path="test.md"
        )
        with pytest.raises(AttributeError):
            meta.id = "changed"

    def test_docmetadata_requires_all_fields(self):
        """
        Purpose: Proves all fields are required
        Quality Contribution: Catches incomplete registry entries
        Acceptance Criteria: TypeError on missing fields
        """
        with pytest.raises(TypeError):
            DocMetadata(id="test")  # Missing required fields
```

#### Non-Happy-Path Coverage
- [ ] Empty string for id/title/summary
- [ ] Invalid characters in id (spaces, uppercase)
- [ ] Empty tags tuple
- [ ] Non-existent path (validated later, not here)

#### Acceptance Criteria
- [ ] DocMetadata is frozen dataclass with 6 fields
- [ ] Doc is frozen dataclass with metadata + content
- [ ] DocsRegistry validates YAML structure
- [ ] All tests passing (8+ tests)
- [ ] Models exported from `__init__.py`

---

### Phase 2: DocsService Implementation

**Objective**: Create DocsService with registry loading and document retrieval using importlib.resources.

**Deliverables**:
- `DocsService` class with `list_documents()` and `get_document()` methods
- Dependency injection in `dependencies.py`
- Domain exception `DocsNotFoundError`

**Dependencies**: Phase 1 complete (models exist)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| importlib.resources edge cases | Medium | High | Follow TemplateService pattern exactly |
| Thread safety issues | Low | Medium | Use RLock pattern from dependencies.py |

#### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 2.1 | [ ] | Write tests for DocsService.list_documents() | 2 | Tests cover: all docs, category filter, tags filter (OR logic), empty results | - | Create `tests/unit/services/test_docs_service.py` |
| 2.2 | [ ] | Write tests for DocsService.get_document() | 2 | Tests cover: existing doc, non-existent doc (returns None), invalid id format | - | Extend test_docs_service.py |
| 2.3 | [ ] | Create test fixtures in `tests/fixtures/docs/` | 1 | Sample registry.yaml + 2 sample .md files | - | Real files, no mocks |
| 2.4 | [ ] | Implement DocsService with importlib.resources | 3 | All tests from 2.1, 2.2 pass | - | Follow TemplateService pattern |
| 2.5 | [ ] | Create DocsNotFoundError exception | 1 | Exception with actionable message | - | Add to `src/fs2/core/adapters/exceptions.py` |
| 2.6 | [ ] | Add get_docs_service() to dependencies.py | 1 | Thread-safe singleton pattern | - | Include set_ and reset_ functions |
| 2.7 | [ ] | Write integration test with real package resources | 2 | Test loads from fs2.docs package | - | Requires Phase 4 docs exist |

#### Test Examples (Write First!)

```python
# tests/unit/services/test_docs_service.py
import pytest
from fs2.core.services.docs_service import DocsService
from fs2.core.models.doc import DocMetadata

class TestDocsServiceListDocuments:
    """Tests for DocsService.list_documents()."""

    def test_list_all_documents(self, docs_service_with_fixtures):
        """
        Purpose: Proves list_documents returns all registered docs
        Quality Contribution: Validates basic catalog functionality
        Acceptance Criteria: Returns list with count matching registry
        """
        result = docs_service_with_fixtures.list_documents()

        assert len(result) == 2  # From fixture
        assert all(isinstance(doc, DocMetadata) for doc in result)

    def test_filter_by_category(self, docs_service_with_fixtures):
        """
        Purpose: Proves category filtering works
        Quality Contribution: Enables agent discovery
        Acceptance Criteria: Only matching category returned
        """
        result = docs_service_with_fixtures.list_documents(category="how-to")

        assert all(doc.category == "how-to" for doc in result)

    def test_filter_by_tags_or_logic(self, docs_service_with_fixtures):
        """
        Purpose: Proves tag filtering uses OR logic
        Quality Contribution: Matches spec AC3
        Acceptance Criteria: Doc with ANY matching tag returned
        """
        result = docs_service_with_fixtures.list_documents(tags=["agents", "config"])

        # Should include docs with either tag
        assert len(result) >= 1
```

#### Non-Happy-Path Coverage
- [ ] Registry file not found (DocsNotFoundError)
- [ ] Document file not found (returns None, logs warning)
- [ ] Invalid YAML in registry (validation error)
- [ ] Empty registry (returns empty list)
- [ ] Non-UTF8 document (encoding error)

#### Acceptance Criteria
- [ ] DocsService loads registry via importlib.resources
- [ ] list_documents() returns all, filters by category/tags
- [ ] get_document() returns Doc or None
- [ ] Thread-safe singleton in dependencies.py
- [ ] All tests passing (12+ tests)
- [ ] No stdout output (stderr only)

---

### Phase 3: MCP Tool Integration

**Objective**: Add `docs_list` and `docs_get` tools to MCP server with proper annotations.

**Deliverables**:
- `docs_list` async tool function
- `docs_get` async tool function
- Tool annotations (readOnlyHint, etc.)
- Error translation for DocsNotFoundError

**Dependencies**: Phase 2 complete (DocsService exists)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| JSON serialization issues | Low | Medium | Use model_dump() explicitly |
| Annotation mistakes | Low | Medium | Add validation test |

#### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 3.1 | [ ] | Write tests for docs_list tool | 2 | Tests cover: no params, category filter, tags filter, response format | - | Create `tests/mcp_tests/test_docs_tools.py` |
| 3.2 | [ ] | Write tests for docs_get tool | 2 | Tests cover: valid id, invalid id, response format with content | - | Extend test_docs_tools.py |
| 3.3 | [ ] | Write tests for tool annotations | 1 | Both tools have correct annotations | - | Verify via mcp_client.list_tools() |
| 3.4 | [ ] | Implement docs_list tool in server.py | 2 | All tests from 3.1 pass | - | Async function, proper docstring |
| 3.5 | [ ] | Implement docs_get tool in server.py | 2 | All tests from 3.2 pass | - | Returns None for not found |
| 3.6 | [ ] | Add tool annotations | 1 | All tests from 3.3 pass | - | readOnlyHint=True, etc. |
| 3.7 | [ ] | Add DocsNotFoundError to translate_error() | 1 | Actionable error message returned | - | "Use docs_list() to see available documents" |
| 3.8 | [ ] | Write MCP protocol integration tests | 2 | Tools work via mcp_client.call_tool() | - | JSON response validation |

#### Test Examples (Write First!)

```python
# tests/mcp_tests/test_docs_tools.py
import json
import pytest
from fs2.mcp.server import docs_list, docs_get

class TestDocsListTool:
    """Tests for docs_list MCP tool."""

    @pytest.mark.asyncio
    async def test_docs_list_returns_catalog(self, docs_mcp_client):
        """
        Purpose: Proves docs_list returns document catalog via MCP
        Quality Contribution: Validates MCP integration
        Acceptance Criteria: Response has docs array and count
        """
        result = await docs_mcp_client.call_tool("docs_list", {})
        data = json.loads(result.content[0].text)

        assert "docs" in data
        assert "count" in data
        assert isinstance(data["docs"], list)
        assert data["count"] == len(data["docs"])

    @pytest.mark.asyncio
    async def test_docs_list_with_category_filter(self, docs_mcp_client):
        """
        Purpose: Proves category filtering works via MCP
        Quality Contribution: Matches spec AC2
        Acceptance Criteria: Only how-to docs returned
        """
        result = await docs_mcp_client.call_tool(
            "docs_list",
            {"category": "how-to"}
        )
        data = json.loads(result.content[0].text)

        for doc in data["docs"]:
            assert doc["category"] == "how-to"


class TestDocsGetTool:
    """Tests for docs_get MCP tool."""

    @pytest.mark.asyncio
    async def test_docs_get_returns_content(self, docs_mcp_client):
        """
        Purpose: Proves docs_get returns full document content
        Quality Contribution: Validates content retrieval
        Acceptance Criteria: Response has id, title, content, metadata
        """
        result = await docs_mcp_client.call_tool(
            "docs_get",
            {"id": "agents"}
        )
        data = json.loads(result.content[0].text)

        assert data["id"] == "agents"
        assert "title" in data
        assert "content" in data
        assert "metadata" in data
        assert len(data["content"]) > 0  # Not empty
```

#### Non-Happy-Path Coverage
- [ ] docs_list with no registered docs (empty array)
- [ ] docs_get with non-existent id (returns None)
- [ ] docs_get with invalid id format (error with action)
- [ ] JSON serialization of all response fields

#### Acceptance Criteria
- [ ] docs_list tool registered with FastMCP
- [ ] docs_get tool registered with FastMCP
- [ ] Both tools have correct annotations
- [ ] Error translation for DocsNotFoundError
- [ ] All tests passing (12+ tests)
- [ ] Response format matches spec examples

---

### Phase 4: Curated Documentation

**Objective**: Create the bundled documentation package with initial curated docs.

**Deliverables**:
- `src/fs2/docs/` package directory
- `registry.yaml` with 2 document entries
- `agents.md` (copied/curated from docs/how/AGENTS.md)
- `configuration-guide.md` (comprehensive configuration reference)
- pyproject.toml update for wheel inclusion

**Dependencies**: Phase 1 complete (models for validation)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Missing __init__.py | Low | High | Create empty __init__.py |
| Wheel doesn't include docs | Medium | High | Verify pyproject.toml includes |

#### Tasks

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 4.1 | [ ] | Create `src/fs2/docs/` package directory | 1 | Directory exists with `__init__.py` | - | Empty __init__.py is sufficient |
| 4.2 | [ ] | Create `registry.yaml` with 2 entries | 1 | Valid YAML matching DocsRegistry schema | - | agents, configuration-guide entries |
| 4.3 | [ ] | Copy and curate agents.md from docs/how/AGENTS.md | 2 | Content matches source, summary is actionable | - | Keep user-focused, remove dev-only content |
| 4.4 | [ ] | Create configuration-guide.md (comprehensive) | 3 | Complete configuration reference covering all topics below | - | See Configuration Guide Content section |
| 4.5 | [ ] | Update pyproject.toml for wheel inclusion | 1 | Docs included when building wheel | - | Add to hatch.build includes |
| 4.6 | [ ] | Verify importlib.resources access works | 1 | Test confirms files accessible | - | Create quick verification test |

#### Registry Content (registry.yaml)

```yaml
# fs2 Documentation Registry
# This file maps document IDs to their metadata for MCP discovery

documents:
  - id: agents
    title: "AI Agent Guidance"
    summary: "Best practices for AI agents using fs2 tools. Read this FIRST when starting to use fs2 MCP server to understand tool selection, search strategies, and common workflows."
    category: how-to
    tags:
      - agents
      - mcp
      - getting-started
    path: agents.md

  - id: configuration-guide
    title: "Complete Configuration Guide"
    summary: "Comprehensive reference for all fs2 configuration options. Covers file locations (user vs project), secrets management, LLM/embedding provider setup (Azure/OpenAI), and environment variable patterns. Read when setting up fs2 for the first time or troubleshooting configuration."
    category: reference
    tags:
      - config
      - setup
      - azure
      - openai
      - llm
      - embedding
      - secrets
    path: configuration-guide.md
```

#### Configuration Guide Content (configuration-guide.md)

The configuration guide must be a comprehensive markdown document covering:

**1. Configuration File Locations**
- User configuration: `~/.config/fs2/config.yaml` (XDG spec)
- Project configuration: `.fs2/config.yaml`
- Precedence: project overrides user

**2. Environment Files for Secrets** (CRITICAL SECTION)

Three locations, loaded in order (later overrides earlier):
1. **User secrets**: `~/.config/fs2/secrets.env` (note: named `secrets.env`, not `.env`)
2. **Project secrets**: `.fs2/secrets.env` (also named `secrets.env`)
3. **Working directory**: `.env` (standard dotenv, highest priority)

**Naming convention**:
- In `~/.config/fs2/` and `.fs2/` directories → use `secrets.env`
- In project root (working directory) → use `.env`

**Example `.fs2/.env` or `.env`**:
```bash
# API keys for LLM and embedding services
AZURE_OPENAI_API_KEY=your-azure-openai-key-here
AZURE_EMBEDDING_API_KEY=your-azure-embedding-key-here

# OpenAI alternative
OPENAI_API_KEY=sk-your-openai-key-here
```

**How it works**:
- All env files are loaded into `os.environ` BEFORE config.yaml is parsed
- This enables `${VAR}` placeholder expansion at runtime
- Never commit secrets to config.yaml - always use placeholders

**3. Configuration Merging and Precedence**
- Deep merge behavior (nested objects merged, not replaced)
- Full precedence order (lowest to highest):
  1. Default values in code
  2. User config.yaml (`~/.config/fs2/config.yaml`)
  3. Project config.yaml (`.fs2/config.yaml`)
  4. `FS2_*` environment variables (highest priority)
- Environment variable override prefix: `FS2_`
- Double underscore for nesting: `FS2_LLM__PROVIDER=azure`

**4. Environment Variable Substitution (${VAR} Expansion)**
- Placeholder syntax: `${VAR_NAME}` in config.yaml
- Expansion happens AFTER all config sources merged
- Variables come from: secrets.env files, .env file, shell environment
- Missing variables left unexpanded (consumer validates)
- Security: literal secrets rejected (sk-* prefix check prevents accidental commits)

**Example flow**:
```yaml
# .fs2/config.yaml
llm:
  api_key: ${AZURE_OPENAI_API_KEY}  # Placeholder, not literal
```
```bash
# .env (loaded first)
AZURE_OPENAI_API_KEY=actual-key-here
```
→ At runtime, `api_key` becomes `actual-key-here`

**5. LLM Configuration**
- Provider selection: `azure`, `openai`, `fake`
- Azure OpenAI setup (full example with all fields)
- OpenAI setup (full example)
- Parameters: temperature, max_tokens, timeout, max_retries
- Environment variable mapping

**6. Embedding Configuration**
- Mode selection: `azure`, `openai_compatible`, `fake`
- Azure embedding setup (full example)
- Dimensions, batch_size, retry configuration
- Chunking configuration (code, documentation, smart_content)

**7. Scan Configuration**
- scan_paths (relative/absolute)
- respect_gitignore
- max_file_size_kb
- follow_symlinks

**8. Smart Content Configuration**
- max_workers
- max_input_tokens
- token_limits per category

**9. Search Configuration**
- default_limit, min_similarity, regex_timeout

**10. Complete Examples**
- Minimal testing config (with `provider: fake`)
- Azure production config (full config.yaml + .env pair)
- OpenAI production config (full config.yaml + .env pair)

**11. Troubleshooting**
- Common errors and fixes
- "Literal secret detected" - use ${VAR} placeholder instead
- "Missing configuration" - check env file loaded correctly
- Validation behavior (two-stage: pre-expansion and post-expansion)

#### Acceptance Criteria
- [ ] `src/fs2/docs/__init__.py` exists
- [ ] registry.yaml valid and passes DocsRegistry validation
- [ ] agents.md has actionable summary
- [ ] configuration-guide.md covers all 11 sections above
- [ ] pyproject.toml includes docs in wheel
- [ ] `importlib.resources.files("fs2.docs")` works

---

### Phase 5: Testing and Documentation

**Objective**: Complete test coverage and update project documentation.

**Deliverables**:
- Comprehensive test suite
- Updated README.md with docs tool usage
- Updated idioms.md with in-app docs pattern

**Dependencies**: Phases 1-4 complete

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Test isolation issues | Low | Medium | Use autouse reset fixture |

#### Tasks

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 5.1 | [ ] | Add mcp_client fixture for docs tests | 1 | Fixture injects DocsService | - | Add to `tests/mcp_tests/conftest.py` |
| 5.2 | [ ] | Add reset fixture for docs dependencies | 1 | Autouse fixture resets docs singleton | - | Extend reset_mcp_dependencies |
| 5.3 | [ ] | Run full test suite, fix any failures | 2 | All tests pass, no regressions | - | `just test` succeeds |
| 5.4 | [ ] | Verify test coverage > 80% | 1 | Coverage report shows > 80% for new code | - | |
| 5.5 | [ ] | Update README.md with docs tool section | 2 | Examples for docs_list, docs_get | - | Per Documentation Strategy |
| 5.6 | [ ] | Update idioms.md with in-app docs pattern | 2 | Documents src/fs2/docs/ mechanism | - | Per AC9 |
| 5.7 | [ ] | Run lint and fix issues | 1 | `just lint` passes | - | |

#### README.md Section (to add)

```markdown
## Documentation Tools

The fs2 MCP server includes documentation tools for agent self-service:

### Browse Available Documentation

```python
# List all documents
docs_list()

# Filter by category
docs_list(category="how-to")

# Filter by tags (OR logic)
docs_list(tags=["config", "setup"])
```

### Get Full Document Content

```python
# Retrieve complete document
docs_get(id="agents")
# Returns: {id, title, content, metadata}
```

See [MCP Server Guide](docs/how/mcp-server-guide.md) for setup details.
```

#### Acceptance Criteria
- [ ] Test fixtures for docs tools exist
- [ ] All 50+ tests passing
- [ ] Test coverage > 80% for new code
- [ ] README.md updated
- [ ] idioms.md updated with pattern
- [ ] Lint passes

---

## Cross-Cutting Concerns

### Security Considerations

- **No secrets in sample-config.yaml**: Use placeholders like `${API_KEY}`
- **Path traversal prevention**: Registry paths are relative to fs2.docs package only
- **Input validation**: Document IDs must match `^[a-z0-9-]+$` pattern

### Observability

- **Logging**: All logging to stderr via `logging.getLogger("fs2.mcp.docs")`
- **Error tracking**: DocsNotFoundError includes path for debugging
- **Metrics**: None required (simple read-only operations)

### Documentation

- **Location**: README.md only (per spec)
- **Content**: Tool usage examples with filtering
- **Target audience**: AI agents and developers using fs2 MCP
- **Maintenance**: Update README when adding new documents to registry

---

## Complexity Tracking

| Component | CS | Label | Breakdown (S,I,D,N,F,T) | Justification | Mitigation |
|-----------|-----|-------|-------------------------|---------------|------------|
| Overall Feature | 2 | Small | S=1,I=0,D=0,N=0,F=0,T=1 | Multiple files but follows existing patterns | - |
| DocsService | 2 | Small | S=1,I=0,D=0,N=0,F=0,T=1 | New service with importlib.resources | Follow TemplateService pattern |
| MCP Tools | 2 | Small | S=1,I=0,D=0,N=0,F=0,T=1 | Two new tools following existing patterns | Copy tree/search patterns |

---

## Progress Tracking

### Phase Completion Checklist

- [ ] Phase 1: Domain Models and Registry - NOT STARTED
- [ ] Phase 2: DocsService Implementation - NOT STARTED
- [ ] Phase 3: MCP Tool Integration - NOT STARTED
- [ ] Phase 4: Curated Documentation - NOT STARTED
- [ ] Phase 5: Testing and Documentation - NOT STARTED

### STOP Rule

**IMPORTANT**: This plan must be validated before creating tasks. After writing this plan:
1. Run `/plan-4-complete-the-plan` to validate readiness
2. Only proceed to `/plan-5-phase-tasks-and-brief` after validation passes

---

## Change Footnotes Ledger

[^1]: [To be added during implementation via plan-6a]
[^2]: [To be added during implementation via plan-6a]
[^3]: [To be added during implementation via plan-6a]
[^4]: [To be added during implementation via plan-6a]
[^5]: [To be added during implementation via plan-6a]

---

**Next Step**: Run `/plan-4-complete-the-plan` to validate readiness
