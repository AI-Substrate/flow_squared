# Research Dossier: Search Capability for fs2

**Generated**: 2025-12-23T23:45:00Z
**Research Query**: Search capability with text, regex, and semantic modes
**Mode**: Plan-Associated
**Location**: `/workspaces/flow_squared/docs/plans/010-search/research-dossier.md`
**FlowSpace**: Available (6282 nodes in flowspace repo, 240 nodes in main repo)
**Findings**: 75 total (10 IA + 10 DC + 10 PS + 10 QT + 10 IC + 10 DE + 15 PL)

---

## Executive Summary

### What It Does
The search system enables finding code nodes by node ID, text content, or semantic meaning. It supports three distinct, non-mixing search modes: **text** (case-insensitive partial match), **regex** (pattern matching), and **semantic** (embedding similarity). Text mode is a simplified regex that auto-transforms queries for partial, case-insensitive matching.

### Business Purpose
Enable developers to quickly locate code by name, content, or concept without knowing exact locations. Text/regex searches work on all text fields (node_id, content, smart_content). Semantic search works only on embedded content (not node_ids). Node ID exact matches score higher and appear first.

### Key Insights
1. **FlowSpace provides a proven reference implementation** with QuerySpec, MatcherRegistry, and three matchers (TextMatcher, RegexMatcher, EmbeddingMatcher)
2. **fs2 already has dual embeddings** (`embedding` for raw code, `smart_content_embedding` for AI summaries) ready for semantic search
3. **Text mode delegates to regex** after transforming patterns for case-insensitivity and partial matching - KISS approach
4. **Node ID exact matches score 1.0**, partial matches score 0.8, enabling predictable ranking
5. **No mixing of search modes** - each query uses exactly one mode, determined by explicit parameter or auto-detection

### Quick Stats
- **Reference Implementation**: FlowSpace (6282 nodes indexed)
- **fs2 Components Ready**: CodeNode, EmbeddingService, GraphStore
- **Search Modes**: 3 (text, regex, semantic)
- **Searchable Fields**: node_id, name, qualified_name, content, smart_content, signature
- **Embedding Fields**: embedding, smart_content_embedding
- **Prior Learnings Applied**: 15 from plans 007-009

---

## How It Currently Works (FlowSpace Reference)

### Entry Points

| Entry Point | Type | Location | Purpose |
|-------------|------|----------|---------|
| `mcp__flowspace__query` | MCP Tool | flowspace/src/mcp/tools.py | Primary search interface |
| `UnifiedQueryService.query()` | Service | flowspace/src/core/query/unified_query_service.py | Orchestrates search |
| `QuerySpec` | Value Object | flowspace/src/core/query/query_spec.py | Validated query parameters |

### Core Execution Flow

1. **Query Specification Creation**
   - File: `query_spec.py:QuerySpec`
   - Input: pattern, method, search_fields, limit, min_similarity
   - Auto-detection: If `method="auto"`, heuristics determine best method
   ```python
   spec = QuerySpec(
       pattern="authentication logic",
       method="auto",  # Auto-detects → "embed" for natural language
       search_fields=["smart_content", "content"],
       top_k=20,
       min_similarity=0.5
   )
   ```

2. **Matcher Selection**
   - File: `matchers.py:MatcherRegistry`
   - Selects appropriate matcher based on `spec.method`
   ```python
   matcher = registry.get_matcher(spec.method)  # TextMatcher, RegexMatcher, or EmbeddingMatcher
   ```

3. **Search Execution**
   - Each matcher implements `match(spec) -> List[QueryResult]`
   - TextMatcher: Substring search with density scoring
   - RegexMatcher: Pattern matching with timeout protection
   - EmbeddingMatcher: Cosine similarity via numpy

4. **Fallback Handling** (Optional)
   - File: `fallback_handler.py`
   - If no results: strip node prefix → retry as text → fallback to embed

5. **Result Ranking**
   - Score normalization and sorting by relevance
   - Node ID exact matches get score=1.0

### Data Flow

```
User Query
    ↓
QuerySpec (validate, normalize, auto-detect method)
    ↓
MatcherRegistry.get_matcher(method)
    ↓
Matcher.match(spec)
    ├── TextMatcher: substring search → density score
    ├── RegexMatcher: re.search() → binary match
    └── EmbeddingMatcher: cosine similarity → 0-1 score
    ↓
List[QueryResult] (node_id, score, match_field, snippet)
    ↓
Sorted by score (descending)
```

### State Management
- **Stateless**: Each query is independent
- **Graph**: In-memory NetworkX DiGraph loaded once
- **Embeddings**: Pre-computed, stored on nodes as `tuple[tuple[float, ...], ...]`

---

## Architecture & Design

### Component Map

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                            │
│  fs2 search <pattern> --mode text|regex|semantic            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     SearchService                           │
│  - Accepts query parameters                                 │
│  - Selects appropriate matcher                              │
│  - Coordinates search execution                             │
│  - Returns ranked results                                   │
└─────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   TextMatcher   │  │  RegexMatcher   │  │ EmbeddingMatcher│
│  (delegates to  │  │  (re.search)    │  │ (cosine sim)    │
│   RegexMatcher) │  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      GraphStore                             │
│  - get_all_nodes() → List[CodeNode]                         │
│  - Persistence: pickle file                                 │
└─────────────────────────────────────────────────────────────┘
```

#### Core Components (to implement)

- **QuerySpec**: Value object holding validated query parameters
  - File: `src/fs2/core/models/query_spec.py` (NEW)
  - Fields: pattern, method, search_fields, limit, min_similarity

- **SearchService**: Composition layer orchestrating search
  - File: `src/fs2/core/services/search/search_service.py` (NEW)
  - Receives ConfigurationService, uses GraphStore

- **TextMatcher/RegexMatcher/EmbeddingMatcher**: Strategy implementations
  - File: `src/fs2/core/services/search/matchers.py` (NEW)
  - Each implements `match(spec, nodes) -> List[SearchResult]`

- **SearchResult**: Result model
  - File: `src/fs2/core/models/search_result.py` (NEW)
  - Fields: node_id, score, match_field, snippet, node reference

### Design Patterns Identified

1. **Strategy Pattern** (PS-02): Abstract `SearchMatcher` base with concrete implementations
2. **Value Object** (PS-01): `QuerySpec` validates and normalizes query parameters
3. **Delegation** (PS-03): TextMatcher delegates to RegexMatcher after pattern transformation
4. **Pipeline** (PS-05): Pre-filter → Match → Score → Rank stages
5. **Registry** (IA-02): MatcherRegistry manages available search strategies

### System Boundaries

- **Internal**: Search operates on in-memory CodeNode graph
- **External**: No external API calls during search (embeddings pre-computed)
- **Integration**: Results return node_ids for downstream lookup

---

## Dependencies & Integration

### What Search Depends On

#### Internal Dependencies

| Dependency | Type | Purpose | Risk if Changed |
|------------|------|---------|-----------------|
| `CodeNode` | Required | Searchable fields (node_id, content, smart_content, embedding) | High - core data model |
| `GraphStore` | Required | Access to all nodes via `get_all_nodes()` | Medium - interface abstraction |
| `ConfigurationService` | Required | Search configuration (limits, thresholds) | Low - well-isolated |
| `EmbeddingAdapter` | Optional | Only if generating query embeddings at search time | Low - pre-computed preferred |

#### External Dependencies

| Library | Version | Purpose | Criticality |
|---------|---------|---------|-------------|
| `numpy` | >=1.24 | Vector operations for cosine similarity | High (semantic search) |
| `re` | stdlib | Regex pattern matching | High (regex mode) |
| `fnmatch` | stdlib | Glob-to-regex conversion | Low (convenience) |

### What Depends on Search

#### Direct Consumers
- **CLI**: `fs2 search` command
- **MCP Tool**: Future `mcp__fs2__search` tool

### Integration Points

1. **GraphStore**: Load graph, get all nodes
2. **EmbeddingAdapter**: Query embedding generation (if needed)
3. **OutputFormatter**: Result formatting (json, pretty, table)

---

## Quality & Testing

### Test Strategy (from QT findings)

1. **Unit Tests**: Each matcher in isolation
   - TextMatcher: case-insensitive substring
   - RegexMatcher: pattern matching, timeout handling
   - EmbeddingMatcher: cosine similarity, threshold filtering

2. **Integration Tests**: Full search pipeline with fixture graph
   - Use `fixture_graph` pytest fixture (397 nodes with real embeddings)
   - Test all three modes against real multi-language code

3. **Deterministic Testing**: FakeEmbeddingAdapter with FixtureIndex (QT-03)
   - Pre-computed embeddings enable reproducible tests
   - No API calls needed in CI/CD

4. **Performance Baselines** (QT-08):
   - Text search: <1s for fixture graph
   - Semantic search: <2s for fixture graph

### Test Coverage Targets

| Component | Coverage | Priority |
|-----------|----------|----------|
| QuerySpec validation | >95% | High |
| TextMatcher | >90% | High |
| RegexMatcher | >90% | High |
| EmbeddingMatcher | >90% | High |
| SearchService orchestration | >85% | Medium |
| Error handling | >90% | High |

---

## Modification Considerations

### Safe to Modify
1. **Output formatting**: Low risk, well-isolated
2. **Score tuning**: Adjust weights/thresholds
3. **New search fields**: Add fields to search

### Modify with Caution
1. **QuerySpec validation**: Affects all queries
2. **Matcher selection logic**: Changes behavior significantly
3. **Result scoring algorithms**: Impacts ranking

### Danger Zones
1. **CodeNode schema**: Breaking change for all consumers
2. **GraphStore interface**: Persistence compatibility
3. **Embedding storage format**: Existing graphs incompatible

---

## Prior Learnings (From Previous Implementations)

**CRITICAL**: These insights from plans 007-009 prevent repeating past mistakes.

### PL-01: API-Level Batching (CRITICAL)
**Source**: Plan 009-embeddings, Phase 3
**What They Found**: Use batched API calls (ONE call with N items), NOT parallel individual calls.
**Action for Search**: If generating query embeddings, batch multiple queries together.

### PL-02: ChunkItem Pattern for Pipeline Tracking (CRITICAL)
**Source**: Plan 009-embeddings, Phase 3
**What They Found**: Track items through pipeline with explicit dataclass (node_id, chunk_index).
**Action for Search**: Use tracking objects for multi-step search operations.

### PL-03: Hash-Based Skip Logic (COST SAVINGS)
**Source**: Plan 009-embeddings, Phase 3
**What They Found**: Compare hashes to skip unchanged content.
**Action for Search**: Cache query embeddings by query hash.

### PL-04: Dual Embedding Architecture (SEARCH QUALITY)
**Source**: Plan 009-embeddings, Phase 1
**What They Found**: Store both `embedding` (code) and `smart_content_embedding` (AI summary).
**Action for Search**: Support searching against both embedding types.

### PL-05: Content-Type Aware Strategies (PRECISION)
**Source**: Plan 009-embeddings, Phase 3
**What They Found**: Different content types need different handling.
**Action for Search**: Potentially weight code vs documentation results differently.

### PL-06: FakeAdapter Pattern with FixtureGraph (TESTING)
**Source**: Plan 009-embeddings, Phase 2/7
**What They Found**: Build fakes using real fixture data.
**Action for Search**: Use existing FakeEmbeddingAdapter for deterministic tests.

### Prior Learnings Summary

| ID | Type | Key Insight | Action |
|----|------|-------------|--------|
| PL-01 | Pattern | API-level batching, not parallel | Batch query embeddings |
| PL-02 | Pattern | Explicit pipeline tracking | Use tracking dataclasses |
| PL-03 | Optimization | Hash-based skip logic | Cache query embeddings |
| PL-04 | Architecture | Dual embeddings | Support both embedding types |
| PL-05 | Design | Content-type awareness | Consider content-type weighting |
| PL-06 | Testing | Fixture-based fakes | Use FixtureGraph in tests |

---

## Critical Discoveries

### Critical Finding 01: Text Mode = Simplified Regex (KISS)
**Impact**: Critical
**Source**: User requirement, PS-03
**What**: Text mode converts input to regex for case-insensitive partial matching
**Implementation**:
```python
def text_to_regex(pattern: str) -> str:
    """Convert text pattern to case-insensitive partial match regex."""
    escaped = re.escape(pattern)  # Escape special chars
    return f"(?i){escaped}"  # Case-insensitive flag
```
**Why It Matters**: Simpler codebase - TextMatcher delegates to RegexMatcher

### Critical Finding 02: No Mode Mixing
**Impact**: Critical
**Source**: User requirement
**What**: Each search uses exactly ONE mode (text, regex, OR semantic)
**Why It Matters**: Simpler mental model, predictable behavior, easier testing

### Critical Finding 03: Node ID Scoring Priority
**Impact**: Critical
**Source**: User requirement, PS-04
**What**: Node ID exact matches score 1.0 (highest), partial 0.8
**Implementation**:
```python
def score_node_id_match(pattern: str, node_id: str) -> float:
    if pattern.lower() == node_id.lower():
        return 1.0  # Exact match
    elif pattern.lower() in node_id.lower():
        return 0.8  # Partial match
    return 0.0  # No match
```
**Why It Matters**: Users searching by node ID get exact matches first

### Critical Finding 04: fs2 Embeddings Ready for Semantic Search
**Impact**: High
**Source**: IA-05, IA-06, DC-02
**What**: CodeNode already has `embedding` and `smart_content_embedding` fields
**Why It Matters**: Semantic search can leverage existing infrastructure

### Critical Finding 05: FlowSpace Provides Complete Reference
**Impact**: High
**Source**: All IA findings
**What**: FlowSpace implements all three search modes with proven patterns
**Why It Matters**: Can adapt FlowSpace patterns rather than designing from scratch

---

## Proposed fs2 Search Architecture

### Search Modes Contract

| Mode | Input | Searches | Scoring | Example |
|------|-------|----------|---------|---------|
| `text` | Plain string | node_id, content, smart_content | Density-based (0-1) | `"EmbeddingAdapter"` |
| `regex` | Regex pattern | node_id, content, smart_content | Binary (1.0 if match) | `"class.*Service"` |
| `semantic` | Natural language | embedding, smart_content_embedding | Cosine similarity (0-1) | `"authentication flow"` |

### QuerySpec Model

```python
@dataclass(frozen=True)
class QuerySpec:
    """Validated search query specification."""
    pattern: str
    mode: Literal["text", "regex", "semantic"]
    limit: int = 20
    min_similarity: float = 0.5  # For semantic only
    search_fields: tuple[str, ...] = ("node_id", "content", "smart_content")

    def __post_init__(self):
        if not self.pattern:
            raise ValueError("Pattern cannot be empty")
        if self.mode not in ("text", "regex", "semantic"):
            raise ValueError(f"Invalid mode: {self.mode}")
```

### SearchResult Model

```python
@dataclass(frozen=True)
class SearchResult:
    """Single search result with scoring."""
    node_id: str
    score: float  # 0.0 to 1.0
    match_field: str  # Which field matched
    snippet: str  # Matched content excerpt
    node: CodeNode  # Full node reference
```

### SearchService Interface

```python
class SearchService:
    def __init__(
        self,
        config: ConfigurationService,
        graph_store: GraphStore,
        embedding_adapter: EmbeddingAdapter | None = None,
    ) -> None:
        self._config = config.require(SearchConfig)
        self._graph_store = graph_store
        self._embedding_adapter = embedding_adapter

    def search(self, spec: QuerySpec) -> list[SearchResult]:
        """Execute search and return ranked results."""
        nodes = self._graph_store.get_all_nodes()

        if spec.mode == "text":
            return self._text_search(spec, nodes)
        elif spec.mode == "regex":
            return self._regex_search(spec, nodes)
        elif spec.mode == "semantic":
            return self._semantic_search(spec, nodes)
```

---

## External Research Opportunities

### Research Opportunity 1: Hybrid Search Scoring Algorithms

**Why Needed**: The user specified no mode mixing, but future enhancement might want to combine text and semantic results. Understanding industry practices now informs clean extension points.

**Impact on Plan**: Low for initial implementation, high for future extensibility.

**Source Findings**: IA-07 (RRF fusion), PS-08 (result combining)

**Ready-to-use prompt**:
```
/deepresearch "Code search ranking algorithms 2024: Compare BM25, TF-IDF, cosine similarity, and Reciprocal Rank Fusion (RRF) for combining lexical and semantic search results. Focus on: (1) Score normalization techniques when combining text match scores with embedding similarity scores, (2) Optimal weighting strategies for code vs documentation, (3) Performance benchmarks for codebases under 10K nodes. Context: Building search for Python codebase analysis tool with pre-computed embeddings."
```

**Results location**: `docs/plans/010-search/external-research/hybrid-search-scoring.md`

### Research Opportunity 2: Regex Timeout Protection

**Why Needed**: FlowSpace implements timeout protection for catastrophic backtracking. Need to understand best practices.

**Impact on Plan**: Medium - affects regex mode reliability.

**Source Findings**: DC-05, PS-05

**Ready-to-use prompt**:
```
/deepresearch "Regex timeout protection in Python 2024: Techniques for preventing catastrophic backtracking in user-provided regex patterns. Compare: (1) signal.alarm approach (Unix only), (2) threading with timeout, (3) regex module with timeout parameter, (4) pattern complexity analysis before execution. Focus on cross-platform solutions that work in asyncio contexts."
```

**Results location**: `docs/plans/010-search/external-research/regex-timeout.md`

---

## Appendix: File Inventory

### Core Files (Existing)

| File | Purpose | Lines | Relevance |
|------|---------|-------|-----------|
| `src/fs2/core/models/code_node.py` | Domain model | ~200 | Searchable fields |
| `src/fs2/core/repos/graph_store.py` | Storage ABC | ~50 | Node access |
| `src/fs2/core/repos/graph_store_impl.py` | Pickle storage | ~150 | Implementation |
| `src/fs2/core/adapters/embedding_adapter.py` | Embedding ABC | ~60 | Query embedding |
| `src/fs2/core/services/embedding/embedding_service.py` | Embedding generation | ~300 | Reference patterns |

### New Files (To Create)

| File | Purpose |
|------|---------|
| `src/fs2/core/models/query_spec.py` | Query specification value object |
| `src/fs2/core/models/search_result.py` | Search result model |
| `src/fs2/core/services/search/search_service.py` | Search orchestration |
| `src/fs2/core/services/search/matchers.py` | Text, Regex, Embedding matchers |
| `src/fs2/config/objects/search_config.py` | Search configuration |
| `src/fs2/cli/commands/search.py` | CLI command |
| `tests/unit/services/search/test_*.py` | Unit tests |
| `tests/integration/test_search_*.py` | Integration tests |

### Test Files

| File | Purpose |
|------|---------|
| `tests/fixtures/fixture_graph.pkl` | Pre-computed graph with embeddings (397 nodes) |
| `tests/conftest.py` | Fixture definitions (fixture_graph, fake adapters) |

---

## Next Steps

**Research Phase Complete**. Recommended next actions:

1. **Optional External Research**: Run `/deepresearch` prompts above for:
   - Hybrid search scoring (for future extensibility)
   - Regex timeout protection (for reliability)

2. **Proceed to Specification**: Run `/plan-1b-specify "search capability"` to create formal specification

3. **Key Decisions Needed**:
   - Should query embedding be computed at search time or require pre-indexed queries?
   - Should regex mode have timeout protection (complexity vs simplicity)?
   - Should results include highlighted snippets?

---

**Research Complete**: 2025-12-23T23:45:00Z
**Report Location**: `/workspaces/flow_squared/docs/plans/010-search/research-dossier.md`
