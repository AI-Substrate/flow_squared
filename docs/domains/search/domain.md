# Domain: Search

**Slug**: search
**Type**: business
**Created**: 2026-03-05
**Created By**: extracted from existing codebase
**Status**: active

## Purpose

Owns code search across indexed graphs — text matching, regex pattern matching, and semantic vector similarity. This domain provides the query engine that CLI `search` commands and MCP `search` tools depend on. It routes queries to the appropriate matcher strategy and applies post-processing (parent penalization, pagination, filtering).

## Concepts

| Concept | Entry Point | What It Does |
|---------|-------------|-------------|
| Search code by any mode | `SearchService.search(spec)` | Routes to text/regex/semantic matcher based on QuerySpec.mode |
| Build a search query | `QuerySpec(pattern, mode)` | Validated, frozen query specification with filters and limits |
| Consume search results | `SearchResult.to_dict(detail)` | Scored results with detail-level field filtering (min/max) |

### Search code by any mode

SearchService is the single entry point. It detects the appropriate matcher (AUTO mode uses heuristics), applies include/exclude filters, runs the matcher, then applies parent penalization and pagination.

```python
from fs2.core.services.search import SearchService
from fs2.core.models.search import QuerySpec, SearchMode

spec = QuerySpec(pattern="GraphStore", mode=SearchMode.AUTO)
results = await search_service.search(spec)  # list[SearchResult]
```

### Build a search query

QuerySpec validates all inputs at construction (frozen dataclass). Supports text, regex, semantic, and auto modes with configurable similarity threshold, filters, and pagination.

```python
spec = QuerySpec(
    pattern="error handling",
    mode=SearchMode.SEMANTIC,
    limit=10, offset=0,
    min_similarity=0.3,
    include=("src/**",), exclude=("tests/**",)
)
```

### Consume search results

SearchResult provides detail-level serialization: min mode (9 fields for quick display) and max mode (13 fields including full content and chunk offsets).

```python
for result in results:
    d = result.to_dict(detail="min")
    # {"node_id": "...", "score": 0.58, "snippet": "...", ...}
```

## Boundary

### Owns
- Search routing and orchestration (SearchService)
- Text matching (TextMatcher → delegates to RegexMatcher)
- Regex matching (RegexMatcher with timeout protection)
- Semantic matching (SemanticMatcher with cosine similarity)
- AUTO mode detection (regex metacharacter heuristic + SEMANTIC fallback)
- Parent penalization (plan-018 hierarchy-aware scoring)
- Search models (QuerySpec, SearchResult, SearchMode, SearchResultMeta, ChunkMatch)
- Include/exclude filtering
- Search configuration (SearchConfig: regex_timeout, parent_penalty)
- Search exceptions (SearchError)

### Does NOT Own
- Graph data access (graph-storage domain — consumed via GraphStoreProtocol)
- Embedding generation (embedding adapters — consumed via EmbeddingAdapter ABC)
- CLI presentation of results (cli-presentation)
- MCP tool interface (cli-presentation)
- Configuration system (configuration domain)

## Contracts (Public Interface)

| Contract | Type | Consumers | Description |
|----------|------|-----------|-------------|
| `SearchService` | Service | CLI search command, MCP search tool | Async search orchestrator |
| `QuerySpec` | Frozen Dataclass | CLI, MCP (construct queries) | Validated search specification |
| `SearchResult` | Frozen Dataclass | CLI, MCP (format output) | Scored result with to_dict(detail) |
| `SearchMode` | Enum | CLI, MCP (mode parameter) | TEXT / REGEX / SEMANTIC / AUTO |
| `SearchResultMeta` | Dataclass | MCP (envelope metadata) | Total count, folder distribution |
| `SearchConfig` | Pydantic Model | SearchService | regex_timeout, parent_penalty |

## Composition (Internal)

| Component | Role | Depends On |
|-----------|------|------------|
| `SearchService` | Orchestrator | GraphStoreProtocol, EmbeddingAdapter (optional), ConfigurationService |
| `TextMatcher` | Strategy | RegexMatcher (delegates with escaped pattern) |
| `RegexMatcher` | Strategy | `regex` module with timeout |
| `SemanticMatcher` | Strategy | EmbeddingAdapter (for query embedding), cosine_similarity |
| `QuerySpec` | Input model | SearchMode enum |
| `SearchResult` | Output model | ChunkMatch, EmbeddingField |
| `SearchResultMeta` | Output envelope | extract_folder(), compute_folder_distribution() |

## Source Location

Primary: `src/fs2/core/services/search/` + `src/fs2/core/models/search/`

| File | Role | Notes |
|------|------|-------|
| `src/fs2/core/services/search/search_service.py` | Orchestrator | Routing, parent penalty, filtering |
| `src/fs2/core/services/search/text_matcher.py` | Matcher | Delegates to RegexMatcher |
| `src/fs2/core/services/search/regex_matcher.py` | Matcher | Timeout-protected regex |
| `src/fs2/core/services/search/semantic_matcher.py` | Matcher | Cosine similarity + embedding |
| `src/fs2/core/services/search/exceptions.py` | Exceptions | SearchError |
| `src/fs2/core/services/search/__init__.py` | Exports | |
| `src/fs2/core/models/search/query_spec.py` | Input model | Frozen, validated |
| `src/fs2/core/models/search/search_mode.py` | Enum | 4 modes |
| `src/fs2/core/models/search/search_result.py` | Output model | 13 fields, to_dict() |
| `src/fs2/core/models/search/search_result_meta.py` | Envelope | Folder distribution |
| `src/fs2/core/models/search/chunk_match.py` | Internal | Semantic chunk tracking |
| `src/fs2/core/models/search/__init__.py` | Exports | |
| `src/fs2/config/objects.py` | Config | SearchConfig section |
| `tests/unit/services/test_search_service.py` | Tests | |
| `tests/unit/services/test_text_matcher.py` | Tests | |
| `tests/unit/services/test_regex_matcher.py` | Tests | |
| `tests/unit/services/test_semantic_matcher.py` | Tests | |

## Dependencies

### This Domain Depends On
- **graph-storage** — GraphStoreProtocol (get_all_nodes, get_parent) for node data
- **configuration** — ConfigurationService for SearchConfig
- **EmbeddingAdapter** (informal embedding domain) — for semantic query embedding
- **regex** (external) — timeout-protected pattern matching

### Domains That Depend On This
- **cli-presentation** (informal) — CLI search command, MCP search tool

## History

| Plan | What Changed | Date |
|------|-------------|------|
| 010-search | Initial SearchService + 3 matchers + models | 2024 |
| 015-search-fix | Bug fixes | 2025 |
| 018-search-trimming | Parent penalization | 2025 |
| *(extracted)* | Domain extracted from existing codebase | 2026-03-05 |
