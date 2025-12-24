# Search Capability for fs2

**Mode**: Full

📚 *This specification incorporates findings from `research-dossier.md` and external research*

✅ **External Research Completed** (2025-12-23)
- `research/regex-timeout-protection.md` - ReDoS prevention using `regex` module
- `research/hybrid-search-scoring.md` - BM25, cosine similarity, RRF fusion algorithms

---

## Research Context

**Key Findings from Research Dossier**:
- **Components affected**: New SearchService, QuerySpec, SearchResult models; CLI command
- **Critical dependencies**: GraphStore (node access), numpy (vector math), existing EmbeddingAdapter
- **Ready infrastructure**: CodeNode already has `embedding` and `smart_content_embedding` fields
- **Reference implementation**: FlowSpace provides proven patterns (MatcherRegistry, three matchers)
- **Modification risks**: Low - new feature, no changes to existing CodeNode schema

**Key Findings from External Research**:
- **Regex timeout**: Use `regex` module (drop-in `re` replacement) with `timeout=2.0` and `concurrent=True`
- **Text scoring**: Node ID exact=1.0, partial=0.8, content density-based
- **Semantic scoring**: Cosine similarity with min_similarity threshold (0.5 default)
- **Future hybrid**: RRF with k=60 is the simplest effective fusion method

**Prior Learnings Applied** (from plans 007-009):
- PL-04: Support dual embedding search (code + smart content)
- PL-06: Use FixtureGraph for deterministic testing

**Research Files**:
- `research-dossier.md` - 75 findings from codebase exploration
- `research/regex-timeout-protection.md` - ReDoS prevention techniques
- `research/hybrid-search-scoring.md` - Scoring algorithms and RRF

---

## Summary

**WHAT**: Add search capability to fs2 that enables finding code nodes by node ID, text content, or semantic meaning.

**WHY**: Developers need to quickly locate code by name, content, or concept without knowing exact file locations. A well-designed search system dramatically improves codebase navigation and understanding.

---

## Goals

1. **Enable code discovery by multiple modalities**: Users can search by exact text, regex patterns, or semantic meaning
2. **Provide predictable, non-mixing search modes**: Each query uses exactly one mode (text, regex, OR semantic) with clear behavior
3. **Prioritize node ID matches**: Exact node_id matches appear first (score 1.0), partial matches second (score 0.8)
4. **Keep implementation simple (KISS)**: Text mode delegates to regex after pattern transformation
5. **Leverage existing infrastructure**: Use pre-computed embeddings from EmbeddingService without additional API calls during search
6. **Deliver fast search results**: Text/regex under 1 second, semantic under 2 seconds on typical graphs

---

## Non-Goals

1. **No mode mixing**: Will not combine text and semantic results in a single query (future enhancement)
2. **No fuzzy matching**: Text mode is exact substring (case-insensitive); no typo correction or fuzzy algorithms
3. **No search indexing**: Will iterate over all nodes; no inverted index or specialized search data structures
4. **No query language**: No boolean operators (AND/OR), field-specific syntax, or advanced query parsing
5. **No search history or suggestions**: No tracking of previous queries or auto-complete

---

## Complexity

**Score**: CS-2 (small)

**Breakdown**:
| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 1 | Multiple files: models (2), service (1), matchers (3), config (1), CLI (1) |
| Integration (I) | 1 | numpy for vector ops; GraphStore for node access |
| Data/State (D) | 0 | No schema changes; uses existing CodeNode fields |
| Novelty (N) | 0 | Well-specified; FlowSpace provides reference implementation |
| Non-Functional (F) | 1 | Performance targets: <1s text, <2s semantic |
| Testing/Rollout (T) | 1 | Integration tests with fixture graph needed |

**Total**: P = 4 → **CS-2**

**Confidence**: 0.85

**Assumptions**:
- GraphStore.get_all_nodes() returns all nodes efficiently
- Existing fixture_graph has sufficient diversity for testing
- numpy is already a project dependency (used by embeddings)
- No need for search result caching in initial implementation

**Dependencies**:
- Embeddings must be generated before semantic search works
- GraphStore must be loaded with nodes

**Risks**:
- Regex patterns from users could cause catastrophic backtracking (mitigated by simple patterns or timeout)
- Large graphs (>10K nodes) may need optimization in future

**Phases** (suggested):
0. Chunk offset tracking (add start_line/end_line to ChunkItem, store with embeddings)
1. Core models (QuerySpec, SearchResult with detail levels)
2. Search service with text/regex matchers + auto-detection
3. Semantic matcher with embedding support
4. Query embedding fixtures for testing (pre-generate known query embeddings)
5. CLI command integration (JSON output, --detail flag)
6. Documentation and integration testing

---

## Acceptance Criteria

### AC01: Text Search - Case-Insensitive Partial Match
**Given** a graph with nodes containing "EmbeddingAdapter" in various fields
**When** I search with pattern "embedding" in text mode
**Then** I receive results matching "EmbeddingAdapter", "embedding_service", etc.
**And** matches are case-insensitive
**And** results are sorted by score (node_id exact > node_id partial > content matches)

### AC02: Text Search - Node ID Priority
**Given** a graph with node_id "callable:src/adapters/embedding_adapter.py:EmbeddingAdapter.embed"
**When** I search for "EmbeddingAdapter" in text mode
**Then** the node_id exact match scores 1.0
**And** node_id partial matches score 0.8
**And** content-only matches score lower
**And** results are ordered by score descending

### AC03: Regex Search - Pattern Matching
**Given** a graph with various class definitions
**When** I search with pattern "class.*Service" in regex mode
**Then** I receive results matching "class SearchService", "class EmbeddingService", etc.
**And** invalid regex patterns return a clear error message

### AC04: Regex Search - All Text Fields
**Given** a graph with nodes
**When** I search with a regex pattern
**Then** the pattern is matched against node_id, content, and smart_content fields
**And** match_field in results indicates which field matched

### AC05: Semantic Search - Embedding Similarity
**Given** a graph with pre-computed embeddings
**When** I search for "authentication flow" in semantic mode
**Then** I receive results with nodes semantically related to authentication
**And** results include similarity scores (0.0 to 1.0)
**And** results are filtered by min_similarity threshold (default 0.5)

### AC06: Semantic Search - Dual Embedding Support
**Given** a graph with both `embedding` and `smart_content_embedding` fields
**When** I search in semantic mode
**Then** both embedding types are searched
**And** the best match from either field is used for scoring

### AC07: Semantic Search - Missing Embeddings
**Given** a graph without embeddings (or with incomplete embeddings)
**When** I attempt semantic search
**Then** I receive a clear error: "Embeddings not available. Run 'fs2 scan --embed' first."

### AC08: Search Mode Exclusivity
**Given** a search request
**When** I specify a mode (text, regex, or semantic)
**Then** only that mode is used
**And** modes are never mixed or combined in a single query

### AC09: Result Limit
**Given** a search that would return many results
**When** I search with limit=10
**Then** I receive at most 10 results
**And** results are the top 10 by score

### AC10: Empty Pattern Validation
**Given** an empty or whitespace-only search pattern
**When** I attempt to search
**Then** I receive a validation error: "Pattern cannot be empty"

### AC11: CLI Integration
**Given** fs2 CLI is available
**When** I run `fs2 search "pattern"`
**Then** I receive JSON search results
**And** --mode accepts: text, regex, semantic, auto (default: auto)
**And** --limit controls result count (default: 20)
**And** --detail accepts: min (default), max

### AC12: Performance - Text/Regex
**Given** a graph with ~400 nodes (fixture graph size)
**When** I perform text or regex search
**Then** results return in under 1 second

### AC13: Performance - Semantic
**Given** a graph with ~400 nodes with embeddings
**When** I perform semantic search
**Then** results return in under 2 seconds

### AC14: Query Embedding Injection
**Given** SearchService is initialized with an EmbeddingAdapter
**When** I perform semantic search with query "authentication flow"
**Then** the query is embedded via the injected adapter
**And** the resulting embedding is compared against node embeddings

### AC15: Fake Query Embedding for Testing
**Given** a set of pre-generated query embeddings in fixtures
**When** running unit tests with FakeEmbeddingAdapter
**Then** known queries return their pre-computed embeddings
**And** no external API calls are made
**And** tests are deterministic and reproducible

### AC16: Query Embedding Fixture Generation
**Given** a list of representative test queries (e.g., "authentication", "error handling", "database")
**When** running `just generate-fixtures` (or similar)
**Then** real embeddings are generated for each query
**And** stored alongside the fixture graph
**And** FakeEmbeddingAdapter can look them up by query text hash

### AC17: Unknown Query Fallback
**Given** a FakeEmbeddingAdapter with pre-generated query embeddings
**When** a query is submitted that has no pre-generated embedding
**Then** a deterministic fallback embedding is generated (hash-based)
**And** a warning is logged suggesting adding the query to fixtures

### AC18: Auto-Detection Mode
**Given** a search pattern without explicit `--mode`
**When** the pattern contains regex special characters (`.*[]^$+?{}|()\\`)
**Then** regex mode is used
**Otherwise** semantic mode is used
**And** `--mode text` forces text mode explicitly

### AC19: Detail Level - Min Mode
**Given** a search with `--detail min` (or default)
**When** results are returned
**Then** each result includes: node_id, start_line, end_line, match_start_line, match_end_line, smart_content, snippet, score, match_field
**And** snippet is ~50 chars around match (text/regex) or matched chunk excerpt (semantic)

### AC20: Detail Level - Max Mode
**Given** a search with `--detail max`
**When** results are returned
**Then** each result includes all min mode fields plus: content, matched_lines (text/regex), chunk_offset (semantic), embedding_chunk_index (semantic)

### AC21: Chunk Offset Tracking
**Given** an embedding pipeline with chunk offset tracking enabled
**When** content is chunked for embedding
**Then** each ChunkItem includes start_line and end_line
**And** chunk offsets are stored alongside embeddings on CodeNode
**And** semantic search can report which chunk matched

### AC22: JSON Output Format
**Given** `fs2 search` CLI command
**When** results are returned
**Then** output is valid JSON (array of result objects)
**And** no pretty-printing or table formatting is applied
**And** output is suitable for piping to `jq` or other JSON tools

---

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Catastrophic regex backtracking | Low | Medium | Use `regex` module with `timeout=2.0` (see research/regex-timeout-protection.md) |
| Large graphs slow performance | Low | Medium | Defer optimization; current target is <10K nodes |
| Missing embeddings confuse users | Medium | Low | Clear error message with fix instructions |
| Score normalization across modes | N/A | N/A | Not applicable - modes don't mix |

### Assumptions

1. **Pre-computed node embeddings**: Semantic search requires embeddings generated by prior scan
2. **Query embedding at search time**: Search service embeds the query via injected EmbeddingAdapter
3. **In-memory graph**: All nodes fit in memory; no streaming or pagination needed
4. **Single-threaded search**: No parallelization needed for current graph sizes
5. **No persistence of search results**: Results are transient; no caching between queries
6. **numpy available**: Vector operations use numpy (already in project for embeddings)
7. **FakeEmbeddingAdapter for tests**: Tests use pre-generated query embeddings, no API calls

---

## Testing Strategy: Query Embedding Fixtures

### Problem

Semantic search requires embedding the user's query to compare against stored node embeddings. During unit/integration testing, we cannot call real embedding APIs because:
- Tests must be deterministic and reproducible
- CI/CD should not require API credentials
- API calls are slow and costly

### Solution: Pre-Generated Query Embeddings

Extend the existing fixture graph system (see `just generate-fixtures`) to include pre-computed embeddings for known test queries.

```
tests/fixtures/
├── fixture_graph.pkl          # Existing: nodes with embeddings
├── query_embeddings.pkl       # NEW: Dict[query_hash, embedding]
└── samples/                   # Existing: source code samples
```

### Implementation Pattern

```python
# During fixture generation (one-time, with real API)
KNOWN_QUERIES = [
    "authentication flow",
    "error handling",
    "database connection",
    "API endpoint",
    "configuration loading",
    # ... ~20-30 representative queries
]

for query in KNOWN_QUERIES:
    embedding = real_adapter.embed_text(query)
    query_embeddings[hash(query)] = embedding

# During testing (FakeEmbeddingAdapter)
class FakeEmbeddingAdapter(EmbeddingAdapter):
    def __init__(self, fixture_index: FixtureIndex, query_embeddings: dict):
        self._fixture_index = fixture_index
        self._query_embeddings = query_embeddings

    async def embed_text(self, text: str) -> list[float]:
        query_hash = compute_hash(text)
        if query_hash in self._query_embeddings:
            return self._query_embeddings[query_hash]
        # Fallback: deterministic hash-based embedding
        logger.warning(f"Unknown query '{text}' - using fallback embedding")
        return self._generate_deterministic_embedding(query_hash)
```

### Integration with Existing Fixtures

The fixture system already handles:
- **Node embeddings**: Stored on CodeNode via `fixture_graph.pkl`
- **Smart content**: Pre-generated via `FakeLLMAdapter`

Query embeddings extend this pattern:
- Add `query_embeddings.pkl` alongside `fixture_graph.pkl`
- Update `just generate-fixtures` to include query embedding generation
- `FakeEmbeddingAdapter` loads both for testing

---

## Open Questions

1. **[RESOLVED: Snippet generation]** Yes - two detail levels (min/max). Min shows smart_content + snippet; max shows full node + chunk offsets.

2. **[RESOLVED: Timeout protection]** Use `regex` module with `timeout=2.0` parameter - drop-in replacement for `re` with built-in timeout (see research/regex-timeout-protection.md)

3. **[RESOLVED: Auto-detection mode]** Yes - auto mode with simple heuristics: if pattern contains regex special characters (`.*[]^$+?{}|()\\`) → regex mode; otherwise → semantic mode. Text mode is explicit only.

4. **[RESOLVED: Output formats]** JSON only. Simple, scriptable, no pretty-printing complexity.

---

## ADR Seeds (Optional)

### ADR-001: Text Mode Delegation to Regex

**Decision Drivers**:
- User requirement: Text mode is "simplified regex"
- KISS principle: Minimize separate code paths
- Maintainability: One regex engine, not two search implementations

**Candidate Alternatives**:
- A) Text delegates to Regex after escaping + case-insensitive flag (recommended)
- B) Separate TextMatcher implementation with string.find()
- C) Use a third-party fuzzy matching library

**Stakeholders**: Core maintainers

### ADR-002: Search Mode Parameter

**Decision Drivers**:
- User requirement: No mixing of search modes
- Explicit is better than implicit
- Testability: Clear mode = predictable behavior

**Candidate Alternatives**:
- A) Explicit `--mode` parameter required (recommended)
- B) Auto-detection based on pattern characteristics
- C) Default to text, special prefix for others (`/regex:`, `/semantic:`)

**Stakeholders**: CLI users, API consumers

### ADR-003: Query Embedding Testing Strategy

**Decision Drivers**:
- Tests must be deterministic without API calls
- Existing fixture graph pattern works well (plan 009)
- FakeEmbeddingAdapter already supports FixtureIndex lookup
- CI/CD should not require embedding API credentials

**Candidate Alternatives**:
- A) Pre-generated query embeddings in fixtures, extend FakeEmbeddingAdapter (recommended)
- B) Mock embedding adapter that returns random vectors (non-deterministic)
- C) Use local embedding model (e.g., sentence-transformers) in tests (slow, adds dependency)
- D) Skip semantic search tests entirely (unacceptable coverage gap)

**Stakeholders**: Test infrastructure, CI/CD

---

## Completed External Research

**Research Files** (in `research/` directory):

### 1. Regex Timeout Protection ✅
**File**: `research/regex-timeout-protection.md`
**Key Findings**:
- Use `regex` module (drop-in replacement for `re`) with `timeout` parameter
- Add dependency: `uv add regex`
- Implementation: `regex.search(pattern, text, timeout=2.0, concurrent=True)`
- GIL is released during matching, enabling other threads to run
- Graceful degradation: return `None` on timeout, don't raise

### 2. Hybrid Search Scoring ✅
**File**: `research/hybrid-search-scoring.md`
**Key Findings**:
- **Text scoring**: Node ID exact=1.0, partial=0.8, content density-based (occurrences/length)
- **Semantic scoring**: Cosine similarity with NumPy, threshold at 0.5
- **Future hybrid mode**: Use Reciprocal Rank Fusion (RRF) with k=60
- NumPy batch cosine similarity is efficient for <10K nodes

**Impact on Implementation**:
- Regex timeout is resolved - use `regex` module
- Scoring algorithms are defined - implement as specified
- Future extensibility path is clear (RRF for hybrid mode)

---

## Clarifications

### Session 2025-12-24

| # | Question | Answer | Rationale |
|---|----------|--------|-----------|
| Q1 | Workflow mode? | **Full** | CS-2 but 6+ phases, comprehensive gates |
| Q2 | Testing approach? | **Full TDD** | Scoring algorithms and integrations need comprehensive coverage |
| Q3 | Mock usage? | **Targeted mocks** | Use fakes wisely - FakeEmbeddingAdapter, fixture graphs |
| Q4 | Documentation location? | **Hybrid** | README: basic usage; docs/how/: scoring, troubleshooting |
| Q5 | Snippet/detail levels? | **Two levels: min/max** | Min: smart_content + extract; Max: full node + offsets |
| Q6 | Chunk offset tracking? | **Yes - Phase 0** | Required for max mode to show matched embedding segment offsets |
| Q7 | Auto-detection mode? | **Yes** | Regex chars → regex mode; otherwise → semantic |
| Q8 | Output formats? | **JSON only** | Simple, scriptable output |

---

## Testing Strategy

**Approach**: Full TDD

**Rationale**: Search involves scoring algorithms (cosine similarity, text scoring), regex timeout handling, and integration with GraphStore/EmbeddingAdapter. Comprehensive test coverage ensures correctness.

**Focus Areas**:
- Scoring algorithms (text, regex, semantic) with edge cases
- Mode auto-detection heuristics
- Regex timeout protection
- Integration with fixture graph
- CLI argument parsing and JSON output

**Excluded**:
- UI/visual formatting (JSON only)
- Performance benchmarking (verify targets, not micro-optimize)

**Mock Usage**: Targeted mocks only
- Use FakeEmbeddingAdapter with pre-generated query embeddings
- Use fixture graph for deterministic node data
- No mocking of internal services (SearchService, matchers)

---

## Documentation Strategy

**Location**: Hybrid (README.md + docs/how/)

**Content Split**:
| README.md | docs/how/search.md |
|-----------|-------------------|
| Basic `fs2 search` usage | Scoring algorithm details |
| Mode flags (`--mode`, auto-detection) | Semantic search requirements |
| Common examples | Advanced regex patterns |
| Output format (JSON) | Troubleshooting embedding issues |

**Target Audience**: fs2 CLI users, developers integrating search

**Maintenance**: Update when adding new modes or changing scoring

---

## Result Detail Levels

Search results support two detail levels controlled by `--detail min|max`:

### Min Mode (Default)
Efficient output for scanning results:
- `node_id`: Full node identifier
- `start_line` / `end_line`: Node boundaries
- `match_start_line` / `match_end_line`: Where match occurred
- `smart_content`: AI-generated summary (always included)
- `snippet`: Short extract of matched content (text/regex) or matched embedding segment (semantic)
- `score`: Match score (0.0-1.0)
- `match_field`: Which field matched (node_id, content, smart_content)

### Max Mode
Full context for deep inspection:
- All min mode fields, plus:
- `content`: Entire node content
- `matched_lines`: Specific lines containing matches (text/regex)
- `chunk_offset`: Start/end line of matched embedding chunk (semantic)
- `embedding_chunk_index`: Which chunk matched best (semantic)

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2025-12-23 | Claude | Initial specification from research dossier |
| 2025-12-23 | Claude | Added external research: regex timeout, hybrid scoring |
| 2025-12-24 | Claude | Added query embedding fixtures phase and testing strategy (AC14-17, ADR-003) |
| 2025-12-24 | Claude | Clarification session: Full mode, TDD, detail levels, auto-detection, JSON output, Phase 0 |
