# Implementation Strategy: Search Capability for fs2

**Generated**: 2025-12-24
**Based on**: research-dossier.md, search-spec.md, codebase analysis
**Purpose**: Phase breakdown, implementation order, integration approach, testing strategy

---

## Implementation Discoveries

### I1-01: Service Pattern Precedent - EmbeddingService and SmartContentService

**What**: Both EmbeddingService and SmartContentService follow identical Clean Architecture patterns:
- Accept `ConfigurationService` or direct config object in `__init__`
- Use `@classmethod create(config)` factory for production wiring
- StatelessImplementation - no instance state beyond config and adapters
- Return new frozen dataclass instances (CodeNode with updated fields)
- Located in subdirectories: `services/embedding/`, `services/smart_content/`

**Why It Matters**: SearchService must follow the same pattern for consistency. The service will:
- Live in `src/fs2/core/services/search/search_service.py`
- Accept ConfigurationService and GraphStore via constructor
- Provide stateless `search(query_spec) -> List[SearchResult]` method
- Have no batch processing (unlike EmbeddingService) since search is always single-query

**Action Required**:
1. Create `src/fs2/core/services/search/` directory
2. Implement `SearchService` with same initialization pattern as EmbeddingService
3. Create `SearchConfig` in `src/fs2/config/objects.py` (default limit=20, min_similarity=0.5)
4. Add to `YAML_CONFIG_TYPES` for auto-loading

**Affected Phases**: Phase 1 (models), Phase 2 (service structure), Phase 5 (CLI integration)

---

### I1-02: Dual Embedding Fields Already Present - No Schema Changes Needed

**What**: CodeNode already has both `embedding` and `smart_content_embedding` fields as `tuple[tuple[float, ...], ...] | None`. EmbeddingService populates these during scan. GraphStore persists them via pickle.

**Why It Matters**: Semantic search can immediately use existing embeddings without any data migration. No need to modify CodeNode schema or run re-scan. However, chunk offset tracking (Phase 0) requires adding metadata structure.

**Action Required**:
1. Phase 0: Add `embedding_chunks` field to CodeNode as `tuple[EmbeddingChunkMeta, ...] | None`
2. Define `EmbeddingChunkMeta(chunk_index: int, start_line: int, end_line: int, text_hash: str)`
3. Update EmbeddingService to populate chunk metadata alongside embeddings
4. Semantic matcher uses chunk metadata to report match location for `--detail max`

**Affected Phases**: Phase 0 (chunk offsets - NEW), Phase 3 (semantic matcher needs chunk info)

---

### I1-03: GraphStore.get_all_nodes() Extension Point Ready

**What**: GraphStore ABC defines `get_all_nodes() -> list[CodeNode]` for iteration. NetworkXGraphStore implements this by iterating graph nodes. Both fake and real implementations already exist.

**Why It Matters**: SearchService can immediately use `GraphStore.get_all_nodes()` without modification. No new repository methods needed. However, performance consideration: ~400 nodes in fixture graph fit in memory; production may have 10K+ nodes.

**Action Required**:
1. SearchService receives GraphStore via DI (same pattern as ScanPipeline)
2. All matchers operate on `nodes: list[CodeNode]` parameter
3. Future optimization: Add `get_nodes_with_embeddings()` filter method to GraphStore if semantic search becomes slow
4. Integration tests use `scanned_fixtures_graph` fixture (~400 nodes)

**Affected Phases**: Phase 2 (SearchService integration), Phase 6 (integration tests)

---

### I1-04: FakeEmbeddingAdapter Pattern for Query Embeddings

**What**: FakeEmbeddingAdapter already uses `FixtureIndex` to look up embeddings by content hash, falling back to deterministic embeddings for unknown content. Same pattern works for query embeddings.

**Why It Matters**: Test queries can be pre-generated and stored in `tests/fixtures/query_embeddings.pkl`. FakeEmbeddingAdapter loads both node embeddings (from fixture_graph.pkl) and query embeddings. No API calls during tests.

**Action Required**:
1. Phase 4: Create `tests/fixtures/query_embeddings.pkl` with ~20-30 representative queries
2. Update `just generate-fixtures` script to generate query embeddings via real Azure adapter
3. Extend FakeEmbeddingAdapter to accept `query_embeddings: dict[str, list[float]]` parameter
4. SearchService injects EmbeddingAdapter for query embedding (only needed in semantic mode)

**Affected Phases**: Phase 4 (fixtures), Phase 3 (semantic matcher setup)

---

### I1-05: CLI Pattern - Typer Commands with Rich Output Abstraction

**What**: `src/fs2/cli/scan.py` demonstrates the pattern:
- Typer command function with annotated parameters
- Creates RichConsoleAdapter for output (abstraction over Rich)
- Uses FS2ConfigurationService for settings
- Creates services via factory methods
- Displays stage banners and results via ConsoleAdapter methods

**Why It Matters**: Search command follows identical pattern but outputs JSON only (no Rich formatting). ConsoleAdapter not needed for search - print raw JSON to stdout.

**Action Required**:
1. Create `src/fs2/cli/search.py` with `search()` typer command
2. Parameters: pattern (positional), --mode (text|regex|semantic|auto), --limit (int), --detail (min|max)
3. Initialize SearchService via factory: `SearchService.create(config)`
4. Convert results to JSON and print with `json.dumps(results, indent=2)`
5. Register command in `src/fs2/cli/main.py`

**Affected Phases**: Phase 5 (CLI command)

---

### I1-06: Test Fixture Pattern - scanned_fixtures_graph Session Scope

**What**: `tests/conftest.py` provides `scanned_fixtures_graph` fixture that:
- Session-scoped (runs once per test session)
- Scans `tests/fixtures/ast_samples/` with real ScanPipeline
- Returns ScannedFixturesContext with loaded NetworkXGraphStore
- Each test gets monkeypatched working directory

**Why It Matters**: Integration tests can use real graph with ~400 nodes. Supports testing with real embeddings if generated. No need to mock GraphStore.

**Action Required**:
1. Phase 6: Integration tests use `scanned_fixtures_graph` fixture
2. Verify fixture graph has embeddings (run `just generate-fixtures` if missing)
3. Test all three search modes (text, regex, semantic) against real graph
4. Verify performance targets: text/regex <1s, semantic <2s

**Affected Phases**: Phase 6 (integration tests)

---

### I1-07: Text Mode Delegation - KISS via Regex Transformation

**What**: FlowSpace TextMatcher delegates to regex after transforming pattern: `re.escape(pattern)` wrapped in `(?i).*{pattern}.*` for case-insensitive partial matching.

**Why It Matters**: No need for separate text matching logic. Single regex engine handles both modes. Reduces code complexity and test surface area.

**Action Required**:
1. Phase 2: Implement `TextMatcher._transform_to_regex(pattern: str) -> str`
2. Transform: `f"(?i).*{re.escape(pattern)}.*"`
3. TextMatcher delegates to RegexMatcher.match() with transformed pattern
4. Tests verify transformation logic separately from matching logic

**Affected Phases**: Phase 2 (text/regex matchers)

---

### I1-08: Frozen Dataclass Pattern - Models Immutable from Day 1

**What**: All fs2 models use `@dataclass(frozen=True)`: CodeNode, ProcessResult, LogEntry. Services return new instances, never mutate.

**Why It Matters**: SearchResult and QuerySpec must follow same pattern. Immutability prevents bugs and enables safe parallelization (future).

**Action Required**:
1. Phase 1: Define `QuerySpec` and `SearchResult` as `@dataclass(frozen=True)`
2. QuerySpec: pattern, mode, limit, min_similarity, search_fields (all read-only)
3. SearchResult: node_id, score, match_field, snippet, matched_chunk_index, etc.
4. Validation in `__post_init__` (not setters)

**Affected Phases**: Phase 1 (models)

---

### I1-09: Regex Timeout Protection - Use `regex` Module Not `re`

**What**: External research (research/regex-timeout-protection.md) recommends `regex` module with `timeout=2.0` parameter for ReDoS protection. Drop-in replacement for `re` with GIL release.

**Why It Matters**: User-provided regex patterns could cause catastrophic backtracking. Timeout prevents hanging searches. Graceful degradation on timeout.

**Action Required**:
1. Add dependency: `uv add regex` (in pyproject.toml)
2. Phase 2: Import `regex` (not `re`) in RegexMatcher
3. Use `regex.search(pattern, text, timeout=2.0, concurrent=True)`
4. Catch `regex.TimeoutError` and return empty results with warning
5. Unit tests verify timeout behavior with pathological patterns

**Affected Phases**: Phase 2 (regex matcher), Phase 6 (timeout testing)

---

### I1-10: NumPy Cosine Similarity - Existing Dependency, Batch Operations

**What**: NumPy is already a project dependency (used by embeddings). Cosine similarity via vectorized operations: `dot(a, b) / (norm(a) * norm(b))`.

**Why It Matters**: No new dependencies. Efficient batch similarity computation for semantic search. Can compute similarities for all nodes at once.

**Action Required**:
1. Phase 3: Implement `_cosine_similarity(query_emb, node_emb) -> float` using NumPy
2. Batch compute: `np.dot(node_embeddings, query_embedding) / norms`
3. Filter by `min_similarity` threshold (default 0.5)
4. Sort by similarity descending, limit results
5. Handle both `embedding` and `smart_content_embedding` fields (take max)

**Affected Phases**: Phase 3 (semantic matcher)

---

## Phase Breakdown and Dependencies

### Phase Dependency Graph

```
Phase 0 (Chunk Offsets)
    ↓
Phase 1 (Models) ──→ Phase 2 (Text/Regex) ──→ Phase 5 (CLI)
    ↓                       ↓                        ↓
    └──→ Phase 3 (Semantic) ──→ Phase 4 (Fixtures) ──→ Phase 6 (Tests)
```

### Parallelization Opportunities

**Can Run in Parallel**:
- Phase 1 (models) + Phase 0 (chunk offsets) - independent data structures
- Phase 2 (text/regex) + Phase 3 (semantic) - after Phase 1 completes

**Must Run Sequentially**:
- Phase 0 → Phase 3 (semantic needs chunk metadata)
- Phase 1 → Phase 2/3 (matchers need models)
- Phase 4 → Phase 6 (tests need fixtures)
- Phase 5 needs Phase 2+3 (CLI needs all matchers)

---

## Detailed Phase Plans

### Phase 0: Chunk Offset Tracking (NEW - Prerequisite)

**Goal**: Enable `--detail max` to show which embedding chunk matched in semantic search

**Deliverables**:
1. `EmbeddingChunkMeta` frozen dataclass in `src/fs2/core/models/embedding_chunk.py`
2. Add `embedding_chunks: tuple[EmbeddingChunkMeta, ...] | None` to CodeNode
3. Update EmbeddingService to populate chunk metadata
4. Update GraphStore to persist/load chunk metadata
5. Unit tests for chunk metadata generation

**Files**:
- NEW: `src/fs2/core/models/embedding_chunk.py`
- MODIFY: `src/fs2/core/models/code_node.py` (add field)
- MODIFY: `src/fs2/core/services/embedding/embedding_service.py` (populate metadata)
- NEW: `tests/unit/models/test_embedding_chunk.py`
- MODIFY: `tests/unit/services/test_embedding_service.py` (verify metadata)

**Acceptance Criteria**:
- AC21: ChunkItem includes start_line/end_line
- Chunk offsets stored alongside embeddings
- Semantic search can report matched chunk

**Testing**: Unit tests only (no integration yet)

**Estimated Complexity**: Low (data structure only)

---

### Phase 1: Core Models (QuerySpec, SearchResult)

**Goal**: Define validated query parameters and search result data structures

**Deliverables**:
1. `QuerySpec` frozen dataclass with validation in `src/fs2/core/models/query_spec.py`
2. `SearchResult` frozen dataclass in `src/fs2/core/models/search_result.py`
3. `SearchMode` enum (TEXT, REGEX, SEMANTIC, AUTO)
4. `SearchConfig` in `src/fs2/config/objects.py`
5. Unit tests for validation logic (empty pattern, invalid mode, etc.)

**Files**:
- NEW: `src/fs2/core/models/query_spec.py`
- NEW: `src/fs2/core/models/search_result.py`
- NEW: `src/fs2/core/models/search_mode.py` (enum)
- MODIFY: `src/fs2/config/objects.py` (add SearchConfig)
- MODIFY: `src/fs2/config/objects.py` (add to YAML_CONFIG_TYPES)
- NEW: `tests/unit/models/test_query_spec.py`
- NEW: `tests/unit/models/test_search_result.py`

**Acceptance Criteria**:
- AC10: Empty pattern validation
- AC08: Mode exclusivity enforced by enum
- AC19/AC20: Result fields defined for min/max detail

**Testing**: Full TDD - validation edge cases

**Estimated Complexity**: Low (models only, no logic)

---

### Phase 2: Text and Regex Matchers

**Goal**: Implement text and regex search with node ID priority and timeout protection

**Deliverables**:
1. `SearchMatcher` ABC in `src/fs2/core/services/search/matchers.py`
2. `TextMatcher` (delegates to RegexMatcher)
3. `RegexMatcher` (uses `regex` module with timeout)
4. Node ID scoring logic (exact=1.0, partial=0.8, content=density)
5. Unit tests for all matchers

**Files**:
- NEW: `src/fs2/core/services/search/matchers.py` (ABC + all matchers)
- NEW: `tests/unit/services/search/test_text_matcher.py`
- NEW: `tests/unit/services/search/test_regex_matcher.py`
- MODIFY: `pyproject.toml` (add `regex` dependency)

**Acceptance Criteria**:
- AC01: Text search case-insensitive partial match
- AC02: Node ID priority scoring
- AC03: Regex pattern matching
- AC04: All text fields matched
- Regex timeout protection (research finding)

**Testing**: Full TDD
- Valid patterns, invalid patterns
- Node ID exact/partial/content matches
- Scoring verification
- Timeout behavior (pathological patterns)

**Estimated Complexity**: Medium (scoring logic, timeout handling)

---

### Phase 3: Semantic Matcher with Dual Embedding Support

**Goal**: Implement cosine similarity search using pre-computed node embeddings

**Deliverables**:
1. `SemanticMatcher` in same file as other matchers
2. Cosine similarity via NumPy (vectorized)
3. Dual embedding support (embedding + smart_content_embedding, take max)
4. Query embedding via injected EmbeddingAdapter
5. Missing embeddings error handling
6. Chunk offset reporting for `--detail max`

**Files**:
- MODIFY: `src/fs2/core/services/search/matchers.py` (add SemanticMatcher)
- NEW: `tests/unit/services/search/test_semantic_matcher.py`

**Acceptance Criteria**:
- AC05: Embedding similarity scoring
- AC06: Dual embedding support
- AC07: Missing embeddings error
- AC14: Query embedding injection
- AC20: Chunk offset in max mode

**Testing**: Full TDD
- Similarity computation accuracy
- Threshold filtering (min_similarity)
- Dual embedding (prefer smart_content_embedding if available)
- Missing embeddings graceful failure
- Chunk offset lookup

**Dependencies**: Phase 0 (chunk metadata), Phase 1 (models)

**Estimated Complexity**: Medium (NumPy operations, dual embedding logic)

---

### Phase 4: Query Embedding Fixtures

**Goal**: Enable deterministic semantic search testing without API calls

**Deliverables**:
1. `KNOWN_QUERIES` list (~20-30 representative queries)
2. `just generate-query-embeddings` script (or extend existing generate-fixtures)
3. `tests/fixtures/query_embeddings.pkl` file
4. Update FakeEmbeddingAdapter to load query embeddings
5. Fallback to deterministic embedding for unknown queries

**Files**:
- NEW: `scripts/generate_query_embeddings.py`
- MODIFY: `tests/fixtures/` (add query_embeddings.pkl)
- MODIFY: `src/fs2/core/adapters/embedding_adapter_fake.py` (query support)
- NEW: `tests/unit/adapters/test_fake_embedding_query_lookup.py`

**Acceptance Criteria**:
- AC15: Fake query embedding for testing
- AC16: Query embedding fixture generation
- AC17: Unknown query fallback

**Testing**: Unit tests for fixture lookup

**Dependencies**: Phase 3 (needs SemanticMatcher to test against)

**Estimated Complexity**: Low (extend existing fixture pattern)

---

### Phase 5: CLI Command and SearchService

**Goal**: Integrate all matchers into SearchService and expose via CLI

**Deliverables**:
1. `SearchService` in `src/fs2/core/services/search/search_service.py`
2. Mode auto-detection (regex chars → REGEX, else → SEMANTIC)
3. Matcher selection and result ranking
4. CLI command `fs2 search` in `src/fs2/cli/search.py`
5. JSON output only (no pretty-printing)
6. Detail level handling (min/max)

**Files**:
- NEW: `src/fs2/core/services/search/search_service.py`
- NEW: `src/fs2/cli/search.py`
- MODIFY: `src/fs2/cli/main.py` (register command)
- NEW: `tests/unit/services/search/test_search_service.py`
- NEW: `tests/integration/test_search_cli.py`

**Acceptance Criteria**:
- AC08: Mode exclusivity
- AC09: Result limit
- AC11: CLI integration
- AC18: Auto-detection mode
- AC22: JSON output format

**Testing**: Full TDD
- Service unit tests (mode selection, ranking)
- CLI integration tests (argument parsing, JSON format)

**Dependencies**: Phase 2 (text/regex), Phase 3 (semantic)

**Estimated Complexity**: Medium (integration logic, CLI wiring)

---

### Phase 6: Integration Testing and Documentation

**Goal**: End-to-end testing with real graph and comprehensive docs

**Deliverables**:
1. Integration tests using `scanned_fixtures_graph` fixture
2. Performance verification (AC12, AC13)
3. All search modes tested against real graph
4. Documentation in `docs/how/search.md`
5. README.md updates with basic usage

**Files**:
- NEW: `tests/integration/test_search_integration.py`
- NEW: `docs/how/search.md`
- MODIFY: `README.md` (search command section)

**Acceptance Criteria**:
- AC12: Performance - text/regex <1s
- AC13: Performance - semantic <2s
- All 22 acceptance criteria verified

**Testing**: Integration tests
- All modes against fixture graph (~400 nodes)
- Performance benchmarks
- Error scenarios (missing embeddings, invalid patterns)

**Dependencies**: Phase 5 (needs complete SearchService)

**Estimated Complexity**: Medium (comprehensive testing, docs)

---

## Key Files Summary

### New Files to Create (17 total)

**Models**:
1. `src/fs2/core/models/query_spec.py` - QuerySpec dataclass
2. `src/fs2/core/models/search_result.py` - SearchResult dataclass
3. `src/fs2/core/models/search_mode.py` - SearchMode enum
4. `src/fs2/core/models/embedding_chunk.py` - EmbeddingChunkMeta dataclass

**Services**:
5. `src/fs2/core/services/search/search_service.py` - Main search service
6. `src/fs2/core/services/search/matchers.py` - All matcher implementations
7. `src/fs2/core/services/search/__init__.py` - Package init

**CLI**:
8. `src/fs2/cli/search.py` - CLI command

**Tests** (9 files):
9. `tests/unit/models/test_query_spec.py`
10. `tests/unit/models/test_search_result.py`
11. `tests/unit/models/test_embedding_chunk.py`
12. `tests/unit/services/search/test_text_matcher.py`
13. `tests/unit/services/search/test_regex_matcher.py`
14. `tests/unit/services/search/test_semantic_matcher.py`
15. `tests/unit/services/search/test_search_service.py`
16. `tests/integration/test_search_cli.py`
17. `tests/integration/test_search_integration.py`

**Documentation**:
18. `docs/how/search.md`

### Files to Modify (6 total)

1. `src/fs2/core/models/code_node.py` - Add embedding_chunks field
2. `src/fs2/core/services/embedding/embedding_service.py` - Populate chunk metadata
3. `src/fs2/config/objects.py` - Add SearchConfig, register in YAML_CONFIG_TYPES
4. `src/fs2/core/adapters/embedding_adapter_fake.py` - Query embedding support
5. `src/fs2/cli/main.py` - Register search command
6. `README.md` - Basic search usage

---

## Testing Strategy Details

### Test Coverage by Phase

| Phase | Unit Tests | Integration Tests | Coverage Target |
|-------|-----------|-------------------|-----------------|
| 0 | Chunk metadata generation | None | 100% (data structure) |
| 1 | Model validation | None | 100% (validation logic) |
| 2 | Matcher logic, scoring | None | 95% (timeout edge cases) |
| 3 | Similarity computation | None | 95% (NumPy operations) |
| 4 | Fixture lookup | None | 100% (fallback logic) |
| 5 | Service integration | CLI parsing, JSON output | 90% (CLI formatting) |
| 6 | None | End-to-end, performance | 100% (all ACs) |

### Mock Usage

**Use Fakes (Preferred)**:
- FakeEmbeddingAdapter (with query embeddings)
- FakeConfigurationService
- Fixture graph (scanned_fixtures_graph)

**Avoid Mocking**:
- SearchService (test real composition)
- Matchers (test real algorithms)
- GraphStore (use FakeGraphStore or fixture)

**Targeted Mocks Only**:
- None needed - all dependencies have fakes

### Test Data Strategy

**Unit Tests**:
- Minimal CodeNode instances (just required fields)
- Known embeddings (simple vectors like [0.5] * 1024)
- Edge cases (empty content, no embeddings, etc.)

**Integration Tests**:
- Real fixture graph (~400 nodes)
- Pre-generated query embeddings (20-30 queries)
- Performance validation with realistic data

---

## Integration Approach

### Composition Root Changes

**In CLI (`src/fs2/cli/search.py`)**:
```python
config = FS2ConfigurationService()
graph_store = NetworkXGraphStore(config)
graph_store.load(config.require(GraphConfig).graph_path)

# Optional: only if semantic mode
embedding_adapter = None
if mode == SearchMode.SEMANTIC:
    embedding_adapter = EmbeddingAdapter.create(config)

service = SearchService(
    config=config,
    graph_store=graph_store,
    embedding_adapter=embedding_adapter,
)

results = service.search(query_spec)
print(json.dumps([r.to_dict() for r in results], indent=2))
```

**No Changes to Existing Services**: SearchService is additive

### GraphStore Integration

**Already Available**:
- `get_all_nodes() -> list[CodeNode]` - iterate all nodes
- `load(path)` - load graph from pickle

**No New Methods Needed**: Search operates on full node list

### Configuration

**New Config Section** in `.fs2/config.yaml`:
```yaml
search:
  default_limit: 20
  min_similarity: 0.5
  regex_timeout_seconds: 2.0
  auto_mode_enabled: true
```

**Env Vars**:
- `FS2_SEARCH__DEFAULT_LIMIT`
- `FS2_SEARCH__MIN_SIMILARITY`

---

## Risk Mitigation

### Performance Risks

**Risk**: Large graphs (>10K nodes) slow semantic search
**Mitigation**:
1. Start with in-memory iteration (simple, works for current graphs)
2. Measure performance in Phase 6
3. Future: Add `get_nodes_with_embeddings()` to GraphStore if needed
4. Future: Implement result streaming for huge graphs

**Risk**: Regex timeout doesn't prevent all hangs
**Mitigation**:
1. Use `regex` module with `concurrent=True` (releases GIL)
2. Set conservative timeout (2 seconds)
3. Document known limitations
4. Log warning for timeout events

### Testing Risks

**Risk**: Query embeddings drift from real embeddings over time
**Mitigation**:
1. Include embedding model version in fixtures
2. Re-generate fixtures when upgrading embedding API
3. Unit tests verify fixture compatibility

**Risk**: Fixture graph too small for realistic testing
**Mitigation**:
1. Current fixture: ~400 nodes (sufficient for functional tests)
2. Document performance targets based on fixture size
3. Future: Add performance test suite with larger synthetic graphs

---

## Success Criteria

### Phase Completion Checklist

**Phase 0**: ✅ Chunk metadata on CodeNode, unit tests pass
**Phase 1**: ✅ Models created, validation tests pass
**Phase 2**: ✅ Text/regex matchers work, timeout protection verified
**Phase 3**: ✅ Semantic matcher works, dual embedding supported
**Phase 4**: ✅ Query embeddings generated, FakeEmbeddingAdapter extended
**Phase 5**: ✅ CLI command works, JSON output correct
**Phase 6**: ✅ All 22 ACs pass, performance targets met, docs complete

### Acceptance Criteria Map

| Phase | ACs Addressed |
|-------|---------------|
| 0 | AC21 (chunk offsets) |
| 1 | AC10 (validation), AC19-20 (detail levels) |
| 2 | AC01-04 (text/regex), AC12 (performance) |
| 3 | AC05-07 (semantic), AC14 (query embedding) |
| 4 | AC15-17 (query fixtures) |
| 5 | AC08-09, AC11, AC18, AC22 (CLI, modes, output) |
| 6 | AC12-13 (performance verification), all ACs |

---

## Next Steps

1. **Review this strategy** with spec and research dossier
2. **Confirm phase order** and parallelization opportunities
3. **Generate Phase 0 tasks** (chunk offset tracking)
4. **Generate Phase 1 tasks** (models)
5. **Implement in order** with TDD discipline

---

## References

- **Spec**: `search-spec.md` (22 ACs, 7 phases suggested)
- **Research**: `research-dossier.md` (75 findings)
- **External Research**: `research/regex-timeout-protection.md`, `research/hybrid-search-scoring.md`
- **Codebase Patterns**: EmbeddingService, SmartContentService, CLI scan command
- **Test Patterns**: scanned_fixtures_graph, FakeEmbeddingAdapter, fixture_graph.pkl
