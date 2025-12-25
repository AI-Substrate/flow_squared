# Search Capability Implementation Plan

**Plan Version**: 1.0.0
**Created**: 2025-12-24
**Spec**: [./search-spec.md](./search-spec.md)
**Status**: READY

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Technical Context](#technical-context)
3. [Critical Research Findings](#critical-research-findings)
4. [Testing Philosophy](#testing-philosophy)
5. [Implementation Phases](#implementation-phases)
   - [Phase 0: Chunk Offset Tracking](#phase-0-chunk-offset-tracking)
   - [Phase 1: Core Models](#phase-1-core-models)
   - [Phase 2: Text/Regex Matchers](#phase-2-textregex-matchers)
   - [Phase 3: Semantic Matcher](#phase-3-semantic-matcher)
   - [Phase 4: Query Embedding Fixtures](#phase-4-query-embedding-fixtures)
   - [Phase 5: CLI Integration](#phase-5-cli-integration)
   - [Phase 6: Documentation and Integration Testing](#phase-6-documentation-and-integration-testing)
6. [Cross-Cutting Concerns](#cross-cutting-concerns)
7. [Complexity Tracking](#complexity-tracking)
8. [Progress Tracking](#progress-tracking)
9. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

**Problem Statement**: Developers need to quickly locate code by name, content, or concept without knowing exact file locations. Currently fs2 indexes code but provides no search capability.

**Solution Approach**:
- Add search capability with three non-mixing modes: text (case-insensitive substring), regex (pattern matching with timeout), semantic (embedding similarity)
- Text mode delegates to regex after pattern transformation (KISS principle)
- Node ID exact matches score 1.0 for predictable ranking
- JSON-only output with min/max detail levels
- Pre-generated query embeddings for deterministic testing
- **CRITICAL**: Embedding fields are arrays of chunk embeddings — semantic search must iterate ALL chunks to find best match (Discovery 05)

**Expected Outcomes**:
- Text/regex search completes in <1 second for typical graphs
- Semantic search completes in <2 seconds
- All 22 acceptance criteria satisfied
- Full TDD coverage for scoring algorithms

**Success Metrics**:
- 100% of ACs pass in integration tests
- Test coverage >80% for new code
- Performance targets met on fixture graph (~400 nodes)

---

## Technical Context

### Current System State
- fs2 indexes codebases via tree-sitter parsing (ScanPipeline)
- CodeNode model has dual embedding fields (`embedding`, `smart_content_embedding`) ready for semantic search
  - **IMPORTANT**: Each field is `tuple[tuple[float, ...], ...] | None` — an **array of chunk embeddings**
  - Content is chunked during embedding (token limit per chunk)
  - Each chunk gets its own 1024-dim embedding vector
  - Semantic search must iterate ALL chunks to find best match
- GraphStore provides `get_all_nodes()` for node access
- EmbeddingService generates embeddings via batch API calls
- FakeEmbeddingAdapter supports fixture-based testing

### Integration Requirements
- SearchService integrates with GraphStore (node access) and EmbeddingAdapter (query embedding)
- CLI command `fs2 search` follows existing Typer patterns
- Tests use existing fixture_graph with real embeddings

### Constraints and Limitations
- No mode mixing: each query uses exactly one search mode
- JSON output only (no pretty-printing)
- In-memory graph iteration (no inverted index)
- Regex timeout protection required (use `regex` module)

### Assumptions
- GraphStore.get_all_nodes() returns nodes efficiently
- numpy available (used by embeddings)
- fixture_graph has embeddings for integration tests
- Query embeddings can be pre-generated for testing

---

## Critical Research Findings

### Discovery 01: ChunkItem Schema Change Risk
**Impact**: Critical
**Sources**: R1-01, R1-02 (risk analysis)
**Problem**: Phase 0 requires adding `start_line`/`end_line` to ChunkItem, which could break existing embedding tests.
**Solution**: Add fields with `None` defaults for backward compatibility.
```python
# ❌ WRONG - Breaking change
@dataclass(frozen=True)
class ChunkItem:
    node_id: str
    chunk_index: int
    text: str
    is_smart_content: bool
    start_line: int  # Required field breaks existing code
    end_line: int

# ✅ CORRECT - Backward compatible
@dataclass(frozen=True)
class ChunkItem:
    node_id: str
    chunk_index: int
    text: str
    is_smart_content: bool
    start_line: int | None = None  # Optional with default
    end_line: int | None = None
```
**Action Required**: Use optional fields with None defaults. Run full embedding test suite before proceeding.
**Affects Phases**: Phase 0

### Discovery 02: Service Pattern Precedent
**Impact**: High
**Sources**: I1-01 (implementation strategy)
**Pattern**: EmbeddingService and SmartContentService follow identical Clean Architecture patterns.
**Solution**: SearchService follows same pattern: accept ConfigurationService, use stateless design, return frozen dataclasses.
```python
# ✅ CORRECT - Follows existing service patterns
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
```
**Action Required**: Create SearchService in `src/fs2/core/services/search/` following established patterns.
**Affects Phases**: Phase 2, Phase 3

### Discovery 03: Text Mode Delegation (KISS)
**Impact**: High
**Sources**: I1-07, R1-09 (implementation + risk)
**Pattern**: FlowSpace TextMatcher delegates to regex after transformation.
**Caution**: Avoid double escaping when delegating.
```python
# ✅ CORRECT - Text transforms pattern once, regex uses as-is
class TextMatcher:
    def _transform_to_regex(self, pattern: str) -> str:
        escaped = re.escape(pattern)  # Escape special chars
        return f"(?i){escaped}"  # Case-insensitive

    def match(self, spec: QuerySpec, nodes: list[CodeNode]) -> list[SearchResult]:
        regex_pattern = self._transform_to_regex(spec.pattern)
        return self._regex_matcher.match_raw(regex_pattern, nodes)
```
**Action Required**: TextMatcher escapes pattern; RegexMatcher receives already-formed regex.
**Affects Phases**: Phase 2

### Discovery 04: Regex Timeout Protection
**Impact**: High
**Sources**: I1-09, R1-06 (implementation + risk)
**Problem**: User regex patterns could cause catastrophic backtracking.
**Solution**: Use `regex` module (drop-in `re` replacement) with timeout parameter.
```python
import regex  # NOT import re

def _search_with_timeout(pattern: str, text: str) -> regex.Match | None:
    try:
        return regex.search(pattern, text, timeout=2.0, concurrent=True)
    except TimeoutError:
        return None  # Graceful degradation
```
**Action Required**: Add dependency `uv add regex` before Phase 2.
**Affects Phases**: Phase 2

### Discovery 05: Dual Embedding Arrays (Chunked)
**Impact**: Critical
**Sources**: I1-02 (implementation), CodeNode model
**Pattern**: CodeNode has `embedding` and `smart_content_embedding` fields, both typed as `tuple[tuple[float, ...], ...] | None`.

**CRITICAL**: Each field is an **array of chunk embeddings**, not a single embedding.
- Content is chunked for embedding (token limit per chunk)
- Each chunk gets its own embedding vector (1024-dim)
- Semantic search must iterate ALL chunks to find best match
- Must track which chunk matched (for line offset reporting via Phase 0)

**Solution**: Iterate all chunks in both fields, find best (chunk_index, field, score):
```python
@dataclass(frozen=True)
class ChunkMatch:
    """Tracks which chunk matched during semantic search."""
    field: str  # "embedding" | "smart_content_embedding"
    chunk_index: int  # Index into the embedding array
    score: float

def _find_best_chunk_match(
    self, query_embedding: np.ndarray, node: CodeNode
) -> ChunkMatch | None:
    """Find best matching chunk across all embeddings."""
    best: ChunkMatch | None = None

    # Search raw content chunks
    if node.embedding:
        for i, chunk_emb in enumerate(node.embedding):
            score = self._cosine_similarity(query_embedding, np.array(chunk_emb))
            if best is None or score > best.score:
                best = ChunkMatch("embedding", i, score)

    # Search smart content chunks
    if node.smart_content_embedding:
        for i, chunk_emb in enumerate(node.smart_content_embedding):
            score = self._cosine_similarity(query_embedding, np.array(chunk_emb))
            if best is None or score > best.score:
                best = ChunkMatch("smart_content_embedding", i, score)

    return best
```
**Action Required**:
1. Iterate ALL chunks in both embedding arrays
2. Track chunk_index of best match (needed for Phase 0 offset lookup)
3. SearchResult includes `embedding_chunk_index` for max detail mode
**Affects Phases**: Phase 0 (chunk offsets), Phase 3 (semantic matcher)

### Discovery 06: Query Embedding Fixtures
**Impact**: High
**Sources**: I1-04, R1-05 (implementation + risk)
**Problem**: Semantic search tests need deterministic query embeddings.
**Solution**: Pre-generate embeddings for ~20-30 test queries, store in `query_embeddings.pkl`.
```python
KNOWN_QUERIES = [
    "authentication flow",
    "error handling",
    "database connection",
    "configuration loading",
    # ... 20-30 representative queries
]
```
**Action Required**: Phase 4 must complete before Phase 3 testing.
**Affects Phases**: Phase 3, Phase 4

### Discovery 07: GraphStore Integration Ready
**Impact**: Medium
**Sources**: I1-03 (implementation)
**Pattern**: GraphStore ABC defines `get_all_nodes() -> list[CodeNode]`. Integration tests use `scanned_fixtures_graph`.
**Action Required**: SearchService receives GraphStore via DI.
**Affects Phases**: Phase 2, Phase 6

### Discovery 08: Frozen Dataclass Pattern with to_dict()
**Impact**: Medium
**Sources**: I1-08 (implementation), get_node.py, tree.py idioms
**Pattern**: All fs2 models use `@dataclass(frozen=True)`. For JSON output, use `to_dict(detail)` method.
```python
@dataclass(frozen=True)
class SearchResult:
    node_id: str
    score: float
    # ... min fields always present ...
    content: str | None = None  # Max-only fields default to None

    def to_dict(self, detail: str = "min") -> dict:
        """Convert to dict with detail level filtering."""
        result = {
            "node_id": self.node_id,
            "score": self.score,
            # ... min fields ...
        }
        if detail == "max":
            result["content"] = self.content
            # ... max fields ...
        return result
```
**Action Required**: SearchResult implements `to_dict(detail)` method for min/max filtering.
**Affects Phases**: Phase 1, Phase 5

### Discovery 09: NumPy Cosine Similarity
**Impact**: Medium
**Sources**: I1-10, R1-07 (implementation + risk)
**Pattern**: NumPy already in project. Vectorized cosine similarity efficient.
```python
import numpy as np
from numpy.linalg import norm

def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
    a_vec = np.array(a)
    b_vec = np.array(b)
    return float(np.dot(a_vec, b_vec) / (norm(a_vec) * norm(b_vec)))
```
**Action Required**: Verify NumPy installed before Phase 3.
**Affects Phases**: Phase 3

### Discovery 10: CLI JSON Output Idiom (from get_node.py)
**Impact**: Medium
**Sources**: I1-05 (implementation), get_node.py idiom
**Pattern**: JSON-only commands use specific idioms for clean piping to jq:
```python
# Console for errors - writes to stderr to keep stdout clean for piping
console = Console(stderr=True)

@app.command()
def search(
    pattern: Annotated[str, typer.Argument(help="Search pattern")],
    mode: Annotated[str, typer.Option("--mode")] = "auto",
    limit: Annotated[int, typer.Option("--limit")] = 20,
    detail: Annotated[str, typer.Option("--detail", help="Detail level: min or max")] = "min",
) -> None:
    # ... service call ...
    results = service.search(spec)

    # Serialize with detail level filtering
    output = [r.to_dict(detail=detail) for r in results]

    # Use raw print() for clean stdout (per get_node.py idiom)
    # default=str handles Path, datetime, etc.
    print(json.dumps(output, indent=2, default=str))
```
**Key idioms**:
- `Console(stderr=True)` for error messages
- `to_dict(detail=detail)` for detail level filtering
- `json.dumps(..., indent=2, default=str)` for serialization
- Raw `print()` for stdout (not console.print)

**Action Required**: Create `src/fs2/cli/search.py` following get_node.py idiom.
**Affects Phases**: Phase 5

---

## Testing Philosophy

### Testing Approach
**Selected Approach**: Full TDD
**Rationale**: Search involves scoring algorithms (cosine similarity, text scoring), regex timeout handling, and integration with GraphStore/EmbeddingAdapter. Comprehensive test coverage ensures correctness.

### Test-Driven Development
- Write tests FIRST (RED)
- Implement minimal code (GREEN)
- Refactor for quality (REFACTOR)

### Focus Areas
- Scoring algorithms (text, regex, semantic) with edge cases
- Mode auto-detection heuristics
- Regex timeout protection
- Integration with fixture graph
- CLI argument parsing and JSON output

### Test Documentation
Every test must include:
```python
"""
Purpose: [what truth this test proves]
Quality Contribution: [how this prevents bugs]
Acceptance Criteria: [measurable assertions]
"""
```

### Mock Usage (Targeted)
- Use FakeEmbeddingAdapter with pre-generated query embeddings
- Use fixture graph for deterministic node data
- No mocking of internal services (SearchService, matchers)
- Only stub truly external calls (network/API)

---

## Implementation Phases

### Phase 0: Chunk Offset Tracking

**Objective**: Add start_line/end_line tracking to ChunkItem and store chunk offsets on CodeNode for semantic search detail mode.

**Deliverables**:
- Extended ChunkItem with optional line offset fields
- Updated `_chunk_by_tokens()` to track line boundaries
- New `embedding_chunk_offsets` field on CodeNode
- Updated EmbeddingService to populate chunk metadata

**Dependencies**:
- Backup fixture_graph.pkl before changes
- Run full embedding test suite first

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ChunkItem schema breaks tests | High | High | Use optional fields with None defaults |
| CodeNode pickle incompatibility | Medium | High | Add field with None default, test load first |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 0.1 | [ ] | Backup fixture_graph.pkl | 1 | Backup exists at tests/fixtures/fixture_graph.pkl.backup | - | Safety first |
| 0.2 | [ ] | Run existing embedding tests | 1 | All tests pass before changes | - | Baseline verification |
| 0.3 | [ ] | Write tests for ChunkItem with line offsets | 2 | Tests verify start_line/end_line fields | - | TDD: write tests first |
| 0.4 | [ ] | Extend ChunkItem with optional line offset fields | 2 | Tests from 0.3 pass, existing tests still pass | - | Backward compatible |
| 0.5 | [ ] | Write tests for line tracking in chunking | 2 | Tests verify line boundaries computed correctly | - | TDD |
| 0.6 | [ ] | Update _chunk_by_tokens() to track line offsets | 3 | Tests from 0.5 pass | - | Track line accumulator |
| 0.7 | [ ] | Write tests for CodeNode.embedding_chunk_offsets | 2 | Tests verify new field serialization | - | TDD |
| 0.8 | [ ] | Add embedding_chunk_offsets field to CodeNode | 2 | Tests from 0.7 pass, pickle load still works | - | Optional with None default |
| 0.9 | [ ] | Update EmbeddingService to populate chunk offsets | 3 | Integration test shows offsets populated | - | Wire it together |
| 0.10 | [ ] | Verify fixture_graph.pkl still loads | 1 | Load succeeds without regeneration | - | Backward compatibility |

### Test Examples (Write First!)

```python
class TestChunkItemLineOffsets:
    def test_chunk_item_accepts_line_offsets(self):
        """
        Purpose: Proves ChunkItem can store line offset metadata
        Quality Contribution: Enables semantic search detail mode
        Acceptance Criteria: ChunkItem with line offsets serializes correctly
        """
        chunk = ChunkItem(
            node_id="test:node",
            chunk_index=0,
            text="line 1\nline 2\nline 3",
            is_smart_content=False,
            start_line=10,
            end_line=12,
        )
        assert chunk.start_line == 10
        assert chunk.end_line == 12

    def test_chunk_item_backward_compatible(self):
        """
        Purpose: Proves existing ChunkItem usage still works
        Quality Contribution: Prevents breaking changes
        Acceptance Criteria: ChunkItem without line offsets has None defaults
        """
        chunk = ChunkItem(
            node_id="test:node",
            chunk_index=0,
            text="content",
            is_smart_content=False,
        )
        assert chunk.start_line is None
        assert chunk.end_line is None
```

### Non-Happy-Path Coverage
- [ ] Large files with many chunks
- [ ] Empty content edge case
- [ ] Single-line content
- [ ] Unicode content with multi-byte chars

### Acceptance Criteria
- [ ] AC21 satisfied: ChunkItem includes start_line and end_line
- [ ] All existing embedding tests pass (no regressions)
- [ ] fixture_graph.pkl loads without regeneration
- [ ] New field serializes/deserializes correctly

---

### Phase 1: Core Models

**Objective**: Create QuerySpec, SearchResult, and ChunkMatch frozen dataclasses with validation and detail level support.

**Deliverables**:
- QuerySpec value object with pattern validation
- SearchResult model with min/max field support
- **ChunkMatch** model for tracking matched chunk during semantic search (Discovery 05)
- SearchMode enum for type safety
- SearchConfig for configuration

**Dependencies**: None (foundational phase)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Validation logic incomplete | Low | Medium | Comprehensive TDD coverage |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 1.1 | [x] | Write comprehensive tests for QuerySpec | 2 | Tests cover: validation, mode enum, limits | [📋](tasks/phase-1-core-models/execution.log.md#task-t001-write-comprehensive-tests-for-queryspec) | TDD first [^6] |
| 1.2 | [x] | Write tests for SearchResult.to_dict(detail) | 2 | Tests cover: min returns 9 fields, max returns 13 fields | [📋](tasks/phase-1-core-models/execution.log.md#task-t002-write-tests-for-searchresultto_dictdetail) | TDD, per get_node.py idiom [^6] |
| 1.3 | [x] | Create SearchMode enum | 1 | TEXT, REGEX, SEMANTIC, AUTO values | [📋](tasks/phase-1-core-models/execution.log.md#task-t003-create-searchmode-enum) | Type safety [^6] |
| 1.4 | [x] | Implement QuerySpec to pass tests | 2 | All tests from 1.1 pass | [📋](tasks/phase-1-core-models/execution.log.md#task-t004-implement-queryspec-to-pass-tests) | Frozen dataclass [^6] |
| 1.5 | [x] | Implement SearchResult to pass tests | 2 | All tests from 1.2 pass | [📋](tasks/phase-1-core-models/execution.log.md#task-t005-implement-searchresult-to-pass-tests) | Detail level support [^6] |
| 1.6 | [x] | Write tests for ChunkMatch | 1 | Tests cover: field, chunk_index, score | [📋](tasks/phase-1-core-models/execution.log.md#task-t006-write-tests-for-chunkmatch) | Discovery 05 [^6] |
| 1.7 | [x] | Implement ChunkMatch | 1 | Frozen dataclass with field/chunk_index/score | [📋](tasks/phase-1-core-models/execution.log.md#task-t007-implement-chunkmatch) | For Phase 3 [^6] |
| 1.8 | [x] | Write tests for SearchConfig | 1 | Tests cover: default_limit, min_similarity | [📋](tasks/phase-1-core-models/execution.log.md#task-t008-write-tests-for-searchconfig) | TDD [^6] |
| 1.9 | [x] | Implement SearchConfig | 1 | Tests from 1.8 pass | [📋](tasks/phase-1-core-models/execution.log.md#task-t009-implement-searchconfig) | Pydantic model [^6] |
| 1.10 | [x] | Create module exports and validate | 1 | Can import from fs2.core.models.search | [📋](tasks/phase-1-core-models/execution.log.md#task-t010-create-module-exports-and-validate) | Clean exports [^6] |

### Test Examples (Write First!)

```python
class TestQuerySpec:
    def test_empty_pattern_raises_validation_error(self):
        """
        Purpose: Proves empty patterns are rejected (AC10)
        Quality Contribution: Prevents meaningless searches
        Acceptance Criteria: ValueError with clear message
        """
        with pytest.raises(ValueError, match="Pattern cannot be empty"):
            QuerySpec(pattern="", mode=SearchMode.TEXT)

    def test_whitespace_pattern_raises_validation_error(self):
        """
        Purpose: Proves whitespace-only patterns rejected
        Quality Contribution: Prevents meaningless searches
        Acceptance Criteria: ValueError raised
        """
        with pytest.raises(ValueError, match="Pattern cannot be empty"):
            QuerySpec(pattern="   ", mode=SearchMode.TEXT)

    def test_valid_spec_with_defaults(self):
        """
        Purpose: Proves default values applied correctly
        Quality Contribution: Documents expected defaults
        Acceptance Criteria: limit=20, min_similarity=0.5
        """
        spec = QuerySpec(pattern="test", mode=SearchMode.TEXT)
        assert spec.limit == 20
        assert spec.min_similarity == 0.5


class TestSearchResultToDict:
    def test_min_detail_returns_required_fields_only(self):
        """
        Purpose: Proves min detail level excludes max-only fields (AC19)
        Quality Contribution: Ensures clean JSON for scanning
        Acceptance Criteria: 9 fields present, content absent
        """
        result = SearchResult(
            node_id="callable:test.py:func",
            score=0.85,
            match_field="content",
            smart_content="A test function",
            snippet="def func():",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=12,
            content="def func():\n    pass",  # Max-only
        )
        d = result.to_dict(detail="min")
        assert "node_id" in d
        assert "score" in d
        assert "smart_content" in d
        assert "content" not in d  # Max-only field excluded

    def test_max_detail_returns_all_fields(self):
        """
        Purpose: Proves max detail level includes all fields (AC20)
        Quality Contribution: Enables deep inspection
        Acceptance Criteria: content, matched_lines, chunk_offset present
        """
        result = SearchResult(
            node_id="callable:test.py:func",
            score=0.85,
            match_field="content",
            smart_content="A test function",
            snippet="def func():",
            start_line=10,
            end_line=20,
            match_start_line=12,
            match_end_line=12,
            content="def func():\n    pass",
            matched_lines=[12],
        )
        d = result.to_dict(detail="max")
        assert "content" in d
        assert d["content"] == "def func():\n    pass"
        assert "matched_lines" in d
```

### Acceptance Criteria
- [ ] AC10 satisfied: Empty pattern validation
- [ ] QuerySpec frozen and immutable
- [ ] SearchResult.to_dict(detail) implements min/max filtering
- [ ] All models have proper __post_init__ validation

---

### Phase 2: Text/Regex Matchers

**Objective**: Implement text and regex search with scoring, timeout protection, and auto-detection.

**Deliverables**:
- RegexMatcher with `regex` module timeout protection
- TextMatcher delegating to RegexMatcher (KISS)
- Node ID priority scoring (1.0 exact, 0.8 partial)
- Auto-detection logic
- SearchService orchestration

**Dependencies**:
- Phase 1 complete (models)
- `regex` module installed (`uv add regex`)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Double escaping bug | Medium | Medium | Careful delegation design, test special chars |
| Regex timeout failure | Low | High | Graceful degradation on TimeoutError |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 2.1 | [x] | Install regex module dependency | 1 | `uv add regex` succeeds, import works | [📋](tasks/phase-2-textregex-matchers/execution.log.md#task-t001-install-regex-module-dependency) | Complete [^7] |
| 2.2 | [x] | Write tests for RegexMatcher basic matching | 2 | Tests cover: simple patterns, field matching | [📋](tasks/phase-2-textregex-matchers/execution.log.md#task-t002-write-tests-for-regexmatcher-basic-matching) | Complete [^7] |
| 2.3 | [x] | Write tests for RegexMatcher timeout | 2 | Tests verify graceful timeout handling | [📋](tasks/phase-2-textregex-matchers/execution.log.md#task-t003-write-tests-for-regexmatcher-timeout-handling) | Complete [^7] |
| 2.4 | [x] | Write tests for invalid regex handling | 1 | Tests verify clear error message | [📋](tasks/phase-2-textregex-matchers/execution.log.md#task-t004-write-tests-for-invalid-regex-handling) | Complete [^7] |
| 2.5 | [x] | Implement RegexMatcher to pass tests | 3 | All tests from 2.2-2.4 pass | [📋](tasks/phase-2-textregex-matchers/execution.log.md#task-t005-implement-regexmatcher-to-pass-tests) | Complete [^7] |
| 2.6 | [x] | Write tests for TextMatcher delegation | 2 | Tests verify text transforms to regex | [📋](tasks/phase-2-textregex-matchers/execution.log.md#task-t006-write-tests-for-textmatcher-delegation) | Complete [^7] |
| 2.7 | [x] | Write tests for TextMatcher special characters | 2 | Tests: "file.py" finds literal dot | [📋](tasks/phase-2-textregex-matchers/execution.log.md#task-t007-write-tests-for-textmatcher-special-char-escaping) | Complete [^7] |
| 2.8 | [x] | Implement TextMatcher to pass tests | 2 | All tests from 2.6-2.7 pass | [📋](tasks/phase-2-textregex-matchers/execution.log.md#task-t008-implement-textmatcher-to-pass-tests) | Complete [^7] |
| 2.9 | [x] | Write tests for node ID scoring priority | 2 | Tests verify: exact=1.0, partial=0.8 | [📋](tasks/phase-2-textregex-matchers/execution.log.md#task-t009-write-tests-for-node-id-scoring-priority) | Complete [^7] |
| 2.10 | [x] | Implement node ID scoring | 2 | Tests from 2.9 pass | [📋](tasks/phase-2-textregex-matchers/execution.log.md#task-t010-implement-node-id-scoring-in-regexmatcher) | Complete [^7] |
| 2.11 | [x] | Write tests for auto-detection heuristics | 2 | Regex chars → regex; else → semantic | [📋](tasks/phase-2-textregex-matchers/execution.log.md#task-t011-t014-searchservice-combined-log) | Complete [^7] |
| 2.12 | [x] | Implement auto-detection | 2 | Tests from 2.11 pass | [📋](tasks/phase-2-textregex-matchers/execution.log.md#task-t011-t014-searchservice-combined-log) | Complete [^7] |
| 2.13 | [x] | Write tests for SearchService orchestration | 2 | Tests verify mode routing | [📋](tasks/phase-2-textregex-matchers/execution.log.md#task-t011-t014-searchservice-combined-log) | Complete [^7] |
| 2.14 | [x] | Implement SearchService | 3 | All text/regex tests pass | [📋](tasks/phase-2-textregex-matchers/execution.log.md#task-t011-t014-searchservice-combined-log) | Complete [^7] |
| 2.15 | [x] | Integration test with fixture graph | 2 | Text search on real nodes works | [📋](tasks/phase-2-textregex-matchers/execution.log.md#task-t015-integration-test-with-fixture_graphpkl) | Complete [^7] |

### Test Examples (Write First!)

```python
class TestRegexMatcher:
    def test_simple_pattern_matches(self):
        """
        Purpose: Proves basic regex matching works (AC03)
        Quality Contribution: Core functionality validation
        Acceptance Criteria: Pattern matches expected nodes
        """
        matcher = RegexMatcher()
        nodes = [create_node("callable:test.py:SearchService.search")]
        results = matcher.match(
            QuerySpec(pattern="class.*Service", mode=SearchMode.REGEX),
            nodes
        )
        assert len(results) > 0

    def test_timeout_returns_empty_not_exception(self):
        """
        Purpose: Proves catastrophic backtracking handled gracefully
        Quality Contribution: Prevents hanging on malicious patterns
        Acceptance Criteria: Returns empty, no exception
        """
        matcher = RegexMatcher()
        evil_pattern = "(a+)+$"  # Known ReDoS pattern
        results = matcher.match(
            QuerySpec(pattern=evil_pattern, mode=SearchMode.REGEX),
            [create_node_with_content("a" * 100)]
        )
        # Should not hang, should return empty or partial results


class TestTextMatcher:
    def test_dot_in_pattern_is_literal(self):
        """
        Purpose: Proves text mode escapes special characters (R1-09)
        Quality Contribution: Prevents surprise regex behavior
        Acceptance Criteria: "file.py" matches literally
        """
        matcher = TextMatcher()
        nodes = [
            create_node("file:src/config.py"),  # Should match
            create_node("file:src/configXpy"),  # Should NOT match (dot is literal)
        ]
        results = matcher.match(
            QuerySpec(pattern="config.py", mode=SearchMode.TEXT),
            nodes
        )
        assert len(results) == 1
        assert "config.py" in results[0].node_id
```

### Acceptance Criteria
- [x] AC01 satisfied: Case-insensitive partial match
- [x] AC02 satisfied: Node ID scoring priority
- [x] AC03 satisfied: Regex pattern matching with error handling
- [x] AC04 satisfied: All text fields searched
- [x] AC08 satisfied: Mode exclusivity
- [x] AC18 satisfied: Auto-detection heuristics

---

### Phase 3: Semantic Matcher

**Objective**: Implement embedding-based semantic search with cosine similarity and chunk iteration.

**CRITICAL**: Embedding fields are **arrays of chunk embeddings** (`tuple[tuple[float, ...], ...]`).
- Must iterate ALL chunks to find best match (see Discovery 05)
- Track chunk_index for matched chunk (needed for line offsets via Phase 0)
- SearchResult includes `embedding_chunk_index` for max detail mode
- **Note (DYK-05)**: `embedding_chunk_offsets` only covers raw content. For smart_content matches, use node's full `(start_line, end_line)` range

**Deliverables**:
- EmbeddingMatcher with cosine similarity
- Chunk iteration for both embedding arrays (raw + smart_content)
- ChunkMatch tracking (field, chunk_index, score)
- Query embedding via injected EmbeddingAdapter
- Similarity threshold filtering
- Missing embeddings error handling

**Dependencies**:
- Phase 0 complete (chunk offset tracking)
- Phase 1 complete (models including ChunkMatch)
- Phase 2 complete (SearchService with temporary AUTO→TEXT fallback)
- Phase 4 complete (query embedding fixtures) OR use FakeEmbeddingAdapter
- NumPy installed (verify)

**✅ DYK-P2-01 RESOLVED**: Phase 3 updated AUTO mode to route to SEMANTIC with TEXT fallback. See [^10] for implementation details.

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Only checking first chunk | High | High | **Review: iterate ALL chunks per Discovery 05** |
| Missing embeddings confuse users | High | Low | Clear error message (AC07) |
| Query embedding fixtures not ready | Medium | Medium | Phase 4 before Phase 3 testing |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 3.1 | [x] | Verify NumPy installed | 1 | `python -c "import numpy"` succeeds | [📋](tasks/phase-3-semantic-matcher/execution.log.md#task-t001) | Prerequisite · NumPy 2.4.0 [^9] |
| 3.2 | [x] | Write tests for cosine similarity function | 2 | Tests verify correct similarity scores | [📋](tasks/phase-3-semantic-matcher/execution.log.md#task-t002-t013) | TDD [^10] |
| 3.3 | [x] | Implement cosine similarity with NumPy | 2 | Tests from 3.2 pass | [📋](tasks/phase-3-semantic-matcher/execution.log.md#task-t002-t013) | Vectorized + clamp negatives [^10] |
| 3.4 | [x] | Write tests for chunk iteration | 2 | Tests verify ALL chunks searched, best found | [📋](tasks/phase-3-semantic-matcher/execution.log.md#task-t002-t013) | **Discovery 05** [^10] |
| 3.5 | [x] | Write tests for EmbeddingMatcher basic matching | 2 | Tests verify nodes ranked by similarity | [📋](tasks/phase-3-semantic-matcher/execution.log.md#task-t002-t013) | TDD [^10] |
| 3.6 | [x] | Write tests for dual embedding search | 2 | Tests verify both fields searched, best used | [📋](tasks/phase-3-semantic-matcher/execution.log.md#task-t002-t013) | AC06 [^10] |
| 3.7 | [x] | Write tests for min_similarity threshold | 2 | Tests verify filtering at 0.25 | [📋](tasks/phase-3-semantic-matcher/execution.log.md#task-t002-t013) | AC05 · DYK-P3-04 [^10] |
| 3.8 | [x] | Implement EmbeddingMatcher with chunk iteration | 3 | All tests from 3.4-3.7 pass | [📋](tasks/phase-3-semantic-matcher/execution.log.md#task-t002-t013) | SemanticMatcher [^10] |
| 3.9 | [x] | Write tests for missing embeddings error | 2 | Tests verify exact error message | [📋](tasks/phase-3-semantic-matcher/execution.log.md#task-t002-t013) | AC07 + fallback [^10] |
| 3.10 | [x] | Implement missing embeddings check | 2 | Tests from 3.9 pass | [📋](tasks/phase-3-semantic-matcher/execution.log.md#task-t002-t013) | AUTO fallback + warning [^10] |
| 3.11 | [x] | Write tests for query embedding injection | 2 | Tests verify adapter called | [📋](tasks/phase-3-semantic-matcher/execution.log.md#task-t002-t013) | AC14 [^10] |
| 3.12 | [x] | Implement query embedding via adapter | 2 | Tests from 3.11 pass | [📋](tasks/phase-3-semantic-matcher/execution.log.md#task-t002-t013) | Native async [^10] |
| 3.13 | [x] | Integration test with fixture graph | 2 | Semantic search on multi-chunk nodes | [📋](tasks/phase-3-semantic-matcher/execution.log.md#task-t002-t013) | 89 tests passing [^10] |

### Test Examples (Write First!)

```python
class TestChunkIteration:
    def test_finds_best_match_across_all_chunks(self):
        """
        Purpose: Proves Discovery 05 - iterate ALL chunks, not just first
        Quality Contribution: Critical for accurate semantic search
        Acceptance Criteria: Best match from any chunk is found
        """
        # Create node with 3 chunks, best match in chunk[2]
        node = create_node_with_embeddings(
            embedding=(
                (0.1,) * 1024,  # chunk 0: low similarity
                (0.2,) * 1024,  # chunk 1: low similarity
                (0.9,) * 1024,  # chunk 2: HIGH similarity
            )
        )
        query_embedding = (0.9,) * 1024  # similar to chunk 2

        match = matcher._find_best_chunk_match(np.array(query_embedding), node)

        assert match.chunk_index == 2  # Must find chunk 2, not chunk 0
        assert match.score > 0.8

    def test_returns_chunk_index_for_line_offset_lookup(self):
        """
        Purpose: Proves chunk_index is tracked for Phase 0 offset lookup
        Quality Contribution: Enables accurate line ranges in max mode
        Acceptance Criteria: ChunkMatch includes chunk_index
        """
        match = matcher._find_best_chunk_match(query_embedding, node)
        assert hasattr(match, 'chunk_index')
        assert isinstance(match.chunk_index, int)


class TestEmbeddingMatcher:
    def test_similar_embeddings_score_high(self):
        """
        Purpose: Proves semantic similarity scoring works
        Quality Contribution: Core semantic search validation
        Acceptance Criteria: Similar content scores >0.8
        """
        matcher = EmbeddingMatcher(embedding_adapter=FakeEmbeddingAdapter())
        # Create nodes with similar content
        results = matcher.match(
            QuerySpec(pattern="authentication flow", mode=SearchMode.SEMANTIC),
            nodes_with_embeddings
        )
        # Top result should be most similar
        assert results[0].score > 0.8

    def test_missing_embeddings_raises_clear_error(self):
        """
        Purpose: Proves AC07 - clear error when no embeddings
        Quality Contribution: User experience
        Acceptance Criteria: Exact error message
        """
        nodes_without_embeddings = [
            create_node_without_embedding("test:node")
        ]
        with pytest.raises(SearchError) as exc:
            matcher.match(spec, nodes_without_embeddings)
        assert "Embeddings not available" in str(exc.value)
        assert "fs2 scan --embed" in str(exc.value)
```

### Acceptance Criteria
- [ ] AC05 satisfied: Embedding similarity with threshold
- [ ] AC06 satisfied: Dual embedding support (both fields, all chunks)
- [ ] AC07 satisfied: Missing embeddings error
- [ ] AC14 satisfied: Query embedding injection
- [ ] Discovery 05: Chunk iteration verified (not just first chunk)

---

### Phase 4: Query Embedding Fixtures

**Objective**: Pre-generate embeddings for known test queries to enable deterministic semantic search testing.

**Deliverables**:
- List of ~20-30 representative test queries
- `query_embeddings.pkl` fixture file
- Extended `just generate-fixtures` command
- Updated FakeEmbeddingAdapter to load query embeddings

**Dependencies**:
- Azure embedding API access (for generation)
- Existing fixture generation infrastructure

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API costs for generation | Low | Low | One-time generation ~$0.10 |
| Query coverage gaps | Medium | Low | Log warning for unknown queries |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 4.1 | [ ] | Define list of known test queries | 1 | 20-30 queries covering search scenarios | - | Documentation |
| 4.2 | [ ] | Write tests for FakeEmbeddingAdapter query lookup | 2 | Tests verify known queries return embeddings | - | TDD |
| 4.3 | [ ] | Write tests for unknown query fallback | 2 | Tests verify deterministic fallback + warning | - | AC17 |
| 4.4 | [ ] | Extend FakeEmbeddingAdapter for query embeddings | 2 | Tests from 4.2-4.3 pass | - | Accept dict param |
| 4.5 | [ ] | Create fixture generation script for queries | 2 | Script generates query_embeddings.pkl | - | Extend justfile |
| 4.6 | [ ] | Generate query embeddings (one-time) | 2 | query_embeddings.pkl exists with ~20-30 entries | - | Run with API |
| 4.7 | [ ] | Add pytest fixture for query embeddings | 1 | Tests can use pre-generated embeddings | - | In conftest.py |
| 4.8 | [ ] | Integration test: semantic search with fixtures | 2 | Deterministic results, no API calls | - | End-to-end |

### Test Examples (Write First!)

```python
class TestFakeEmbeddingAdapterQueries:
    def test_known_query_returns_pregenerated_embedding(self):
        """
        Purpose: Proves AC15 - deterministic test embeddings
        Quality Contribution: Reproducible tests without API
        Acceptance Criteria: Known query returns exact embedding
        """
        adapter = FakeEmbeddingAdapter(
            query_embeddings=load_query_embeddings()
        )
        embedding = await adapter.embed_text("authentication flow")
        assert len(embedding) == 1024
        # Same input always produces same output
        embedding2 = await adapter.embed_text("authentication flow")
        assert embedding == embedding2

    def test_unknown_query_uses_deterministic_fallback(self):
        """
        Purpose: Proves AC17 - fallback for unknown queries
        Quality Contribution: Tests work even with new queries
        Acceptance Criteria: Fallback is deterministic
        """
        adapter = FakeEmbeddingAdapter(query_embeddings={})
        embedding1 = await adapter.embed_text("completely new query")
        embedding2 = await adapter.embed_text("completely new query")
        assert embedding1 == embedding2  # Deterministic
```

### Acceptance Criteria
- [ ] AC15 satisfied: Fake query embeddings for testing
- [ ] AC16 satisfied: Query embedding fixture generation
- [ ] AC17 satisfied: Unknown query fallback with warning
- [ ] No API calls during test runs

---

### Phase 5: CLI Integration

**Objective**: Create `fs2 search` CLI command with JSON output and mode/detail flags.

**Deliverables**:
- `fs2 search` Typer command
- `--mode` flag (text, regex, semantic, auto)
- `--limit` flag (default 20)
- `--detail` flag (min, max)
- JSON output only

**Dependencies**:
- Phase 2 complete (text/regex)
- Phase 3 complete (semantic)
- SearchService fully functional

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Argument parsing edge cases | Low | Low | Comprehensive CLI tests |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 5.1 | [ ] | Write tests for CLI argument parsing | 2 | Tests cover: all flags, defaults | - | TDD |
| 5.2 | [ ] | Write tests for JSON stdout + stderr errors | 2 | Tests verify: valid JSON on stdout, errors on stderr | - | AC22, get_node.py idiom |
| 5.3 | [ ] | Write tests for min detail (content excluded) | 2 | Tests verify to_dict(detail="min") used | - | AC19 |
| 5.4 | [ ] | Write tests for max detail (content included) | 2 | Tests verify to_dict(detail="max") used | - | AC20 |
| 5.5 | [ ] | Create search.py with Console(stderr=True) | 2 | Errors go to stderr, JSON to stdout | - | get_node.py idiom |
| 5.6 | [ ] | Implement argument handling | 2 | Tests from 5.1 pass | - | Typer annotations |
| 5.7 | [ ] | Implement JSON output with raw print() | 2 | json.dumps(..., default=str), print() not console | - | get_node.py idiom |
| 5.8 | [ ] | Implement detail via to_dict(detail) | 2 | Tests from 5.3-5.4 pass | - | SearchResult.to_dict() |
| 5.9 | [ ] | Register command in CLI main | 1 | `fs2 search --help` works | - | Add to app |
| 5.10 | [ ] | Integration test: full CLI workflow | 2 | Search via subprocess works | - | End-to-end |

### Test Examples (Write First!)

```python
class TestSearchCLI:
    def test_json_output_is_valid_and_pipeable(self):
        """
        Purpose: Proves AC22 - JSON output format suitable for jq
        Quality Contribution: Enables piping to jq and other tools
        Acceptance Criteria: stdout is valid JSON, stderr has errors only
        """
        result = runner.invoke(app, ["search", "test"])
        # stdout should be valid JSON
        output = json.loads(result.stdout)
        assert isinstance(output, list)
        # stderr should be empty on success (per get_node.py idiom)
        assert result.stderr == "" or result.stderr is None

    def test_min_detail_excludes_content_field(self):
        """
        Purpose: Proves AC19 - min detail level via to_dict(detail="min")
        Quality Contribution: Documents expected minimal output
        Acceptance Criteria: 9 fields present, content absent
        """
        result = runner.invoke(app, ["search", "test", "--detail", "min"])
        output = json.loads(result.stdout)
        for item in output:
            assert "node_id" in item
            assert "score" in item
            assert "smart_content" in item
            assert "snippet" in item
            assert "content" not in item  # Max-only field excluded

    def test_max_detail_includes_content_field(self):
        """
        Purpose: Proves AC20 - max detail level via to_dict(detail="max")
        Quality Contribution: Documents expected full output
        Acceptance Criteria: content, matched_lines present
        """
        result = runner.invoke(app, ["search", "test", "--detail", "max"])
        output = json.loads(result.stdout)
        for item in output:
            assert "content" in item  # Max-only field included

    def test_errors_go_to_stderr(self):
        """
        Purpose: Proves Console(stderr=True) idiom from get_node.py
        Quality Contribution: Clean stdout for piping even on errors
        Acceptance Criteria: Error message on stderr, empty stdout
        """
        result = runner.invoke(app, ["search", ""])  # Empty pattern
        assert result.exit_code != 0
        assert "Error" in result.stderr or "cannot be empty" in result.stderr
```

### Acceptance Criteria
- [ ] AC11 satisfied: CLI with mode/limit/detail flags
- [ ] AC19 satisfied: Min detail output (via to_dict)
- [ ] AC20 satisfied: Max detail output (via to_dict)
- [ ] AC22 satisfied: JSON output format with stderr for errors

---

### Phase 6: Documentation and Integration Testing

**Objective**: Create documentation (README + docs/how/) and comprehensive integration tests.

**Deliverables**:
- Updated README.md with search usage
- `docs/how/search/` with detailed guides
- Integration tests covering all modes
- Performance verification tests

**Dependencies**:
- All previous phases complete
- Full search functionality working

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Documentation drift | Low | Medium | Include doc updates in phase criteria |

### Discovery & Placement Decision

**Existing docs/how/ structure**: Survey required during task execution.

**Decision**: Create new `docs/how/search/` directory.

**File strategy**: Create numbered files (1-overview.md, 2-usage.md, 3-scoring.md, 4-troubleshooting.md).

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|-----|--------|------|----|------------------|-----|-------|
| 6.1 | [ ] | Survey existing docs/how/ directories | 1 | Documented existing structure | - | Discovery |
| 6.2 | [ ] | Update README.md with search getting-started | 2 | Basic usage, mode flags, examples | - | Hybrid docs |
| 6.3 | [ ] | Create docs/how/search/1-overview.md | 2 | Introduction, modes, quick examples | - | New directory |
| 6.4 | [ ] | Create docs/how/search/2-usage.md | 2 | Detailed usage with all options | - | |
| 6.5 | [ ] | Create docs/how/search/3-scoring.md | 2 | Scoring algorithms explained | - | From research |
| 6.6 | [ ] | Create docs/how/search/4-troubleshooting.md | 2 | Common issues, embedding requirements | - | |
| 6.7 | [ ] | Write integration test: text mode end-to-end | 2 | Search fixture graph with text | - | AC01, AC02 |
| 6.8 | [ ] | Write integration test: regex mode end-to-end | 2 | Search with regex patterns | - | AC03, AC04 |
| 6.9 | [ ] | Write integration test: semantic mode end-to-end | 2 | Search with embeddings | - | AC05, AC06 |
| 6.10 | [ ] | Write integration test: auto-detection | 2 | Verify mode selection | - | AC18 |
| 6.11 | [ ] | Write performance test: text/regex <1s | 2 | Timing assertion | - | AC12 |
| 6.12 | [ ] | Write performance test: semantic <2s | 2 | Timing assertion | - | AC13 |
| 6.13 | [ ] | Review documentation for clarity | 1 | Peer review passed | - | Quality gate |

### Content Outlines

**README.md section** (Hybrid: getting-started):
- What is `fs2 search` (1-2 sentences)
- Installation (already done if fs2 installed)
- Basic usage: `fs2 search "pattern"`
- Mode flags: `--mode text|regex|semantic|auto`
- Link to detailed docs: `docs/how/search/`

**docs/how/search/1-overview.md**:
- Introduction and motivation
- Three search modes explained
- Quick examples for each mode

**docs/how/search/2-usage.md**:
- All CLI flags with descriptions
- Common use cases
- Output format (JSON structure)

**docs/how/search/3-scoring.md**:
- Node ID scoring (1.0 exact, 0.8 partial)
- Text/regex scoring algorithm
- Semantic cosine similarity
- Min similarity threshold

**docs/how/search/4-troubleshooting.md**:
- "Embeddings not available" error
- Regex timeout issues
- Performance optimization tips

### Acceptance Criteria
- [ ] AC12 satisfied: Text/regex <1s
- [ ] AC13 satisfied: Semantic <2s
- [ ] All 22 ACs verified via integration tests
- [ ] Documentation complete and reviewed
- [ ] README updated with search usage

---

## Cross-Cutting Concerns

### CLI Output Idioms (MANDATORY)
**Reference files**: `src/fs2/cli/get_node.py`, `src/fs2/cli/tree.py`

For JSON-only commands, follow the established fs2 idioms:

```python
# 1. Console writes to stderr (keeps stdout clean for piping)
console = Console(stderr=True)

# 2. Detail level via --detail flag (from tree.py)
detail: Annotated[
    str,
    typer.Option("--detail", help="Detail level: min or max"),
] = "min"

# 3. Dataclass to_dict(detail) for filtering (from tree.py pattern)
output = [r.to_dict(detail=detail) for r in results]

# 4. JSON serialization with default=str (from get_node.py)
json_str = json.dumps(output, indent=2, default=str)

# 5. Raw print() for stdout, NOT console.print() (from get_node.py)
print(json_str)
```

**Rationale**: Enables `fs2 search "pattern" | jq '.[] | .node_id'` without pollution.

### Security Considerations
- **Regex injection**: Timeout protection via `regex` module prevents ReDoS
- **Pattern validation**: Empty patterns rejected (AC10)
- **No network calls during search**: Embeddings pre-computed

### Observability
- **Logging**: Log mode selection, match counts, timing
- **Errors**: Clear error messages for missing embeddings (AC07) - to stderr
- **Performance**: Timing targets in tests (AC12, AC13)

### Documentation
- **Location**: Hybrid (README + docs/how/search/)
- **Content**: Getting started, detailed usage, scoring, troubleshooting
- **Maintenance**: Update when adding modes or changing scoring

---

## Complexity Tracking

| Component | CS | Label | Breakdown (S,I,D,N,F,T) | Justification | Mitigation |
|-----------|-----|-------|------------------------|---------------|------------|
| ChunkItem schema change | 3 | Medium | S=1,I=1,D=1,N=0,F=1,T=1 | Modifying existing frozen dataclass | Backward-compatible None defaults |
| SearchService | 3 | Medium | S=1,I=1,D=0,N=0,F=0,T=1 | Multiple matcher strategies | Follow existing service patterns |
| EmbeddingMatcher | 4 | Medium | S=1,I=1,D=1,N=0,F=0,T=1 | **Chunk iteration (Discovery 05)**, dual embedding search | NumPy vectorization, ChunkMatch tracking |

---

## Progress Tracking

### Phase Completion Checklist
- [x] Phase 0: Chunk Offset Tracking - COMPLETE
- [x] Phase 1: Core Models - COMPLETE (69 tests, 10/10 tasks)
- [x] Phase 2: Text/Regex Matchers - COMPLETE (63 tests, 15/15 tasks)
- [x] Phase 3: Semantic Matcher - COMPLETE (89 tests, 13/13 tasks, T014-T017 deferred)
- [-] Phase 4: Query Embedding Fixtures - MERGED INTO PHASE 3 (deferred)
- [ ] Phase 5: CLI Integration - PENDING
- [ ] Phase 6: Documentation and Integration Testing - PENDING

**Overall Progress**: 4/6 phases complete (Phase 4 merged into Phase 3)

### STOP Rule
**IMPORTANT**: This plan must be complete before creating tasks. After writing this plan:
1. Run `/plan-4-complete-the-plan` to validate readiness
2. Only proceed to `/plan-5-phase-tasks-and-brief` after validation passes

---

## Change Footnotes Ledger

[^1]: Subtask 001 ST001-ST005 - Added CLI params for fixture generation
  - `file:src/fs2/cli/main.py` - Added CLIContext and --graph-file global option
  - `file:src/fs2/cli/scan.py` - Added --scan-path repeatable param, context handling
  - `file:src/fs2/cli/tree.py` - Added context handling for --graph-file
  - `file:src/fs2/cli/get_node.py` - Added context handling for --graph-file
  - `file:src/fs2/core/services/scan_pipeline.py` - Added graph_path parameter
  - `file:justfile` - Updated generate-fixtures with two-step recipe
  - `file:scripts/enrich_fixture_smart_content.py` - New script for smart_content enrichment

[^2]: Phase 0 T010-T011 - Fixture regeneration and validation
  - `file:tests/fixtures/fixture_graph.pkl` - Regenerated with 451 nodes, all with chunk offsets
  - `file:tests/scratch/validate_chunk_offsets.py` - Validation script (28 multi-chunk nodes validated)

[^6]: Phase 1 T001-T010 - Core search models (69 tests)
  - `file:src/fs2/core/models/search/__init__.py` - Module exports (SearchMode, QuerySpec, SearchResult, ChunkMatch, EmbeddingField)
  - `class:src/fs2/core/models/search/search_mode.py:SearchMode` - Enum: TEXT, REGEX, SEMANTIC, AUTO
  - `class:src/fs2/core/models/search/query_spec.py:QuerySpec` - Frozen dataclass with pattern, mode, limit, min_similarity
  - `class:src/fs2/core/models/search/search_result.py:SearchResult` - Frozen dataclass with to_dict(detail) for min/max
  - `class:src/fs2/core/models/search/chunk_match.py:ChunkMatch` - Tracks field, chunk_index, score for semantic
  - `class:src/fs2/core/models/search/chunk_match.py:EmbeddingField` - Enum: EMBEDDING, SMART_CONTENT
  - `class:src/fs2/config/objects.py:SearchConfig` - Pydantic config with default_limit, min_similarity, regex_timeout
  - `file:tests/unit/models/test_query_spec.py` - 18 tests for QuerySpec validation
  - `file:tests/unit/models/test_search_result.py` - 19 tests for SearchResult.to_dict()
  - `file:tests/unit/models/test_chunk_match.py` - 16 tests for ChunkMatch validation
  - `file:tests/unit/models/test_search_config.py` - 16 tests for SearchConfig defaults
  - DYK-01: Always include all 13 fields in max mode; null for mode-irrelevant
  - DYK-02: Normative 13-field reference table
  - DYK-03: EmbeddingField enum for type-safe field identification
  - DYK-04: Semantic match lines require chunk offsets (Phase 3 dependency)
  - DYK-05: min_similarity only applies to SEMANTIC mode

[^7]: Phase 2 T001-T015 - Text/Regex Matchers (63 tests)
  - `file:src/fs2/core/services/search/__init__.py` - Module exports (SearchError, RegexMatcher, TextMatcher, SearchService)
  - `class:src/fs2/core/services/search/exceptions.py:SearchError` - Exception for invalid patterns
  - `class:src/fs2/core/services/search/regex_matcher.py:RegexMatcher` - Pattern matching with `regex` module timeout protection
  - `class:src/fs2/core/services/search/regex_matcher.py:FieldMatch` - Internal dataclass for field match results
  - `class:src/fs2/core/services/search/text_matcher.py:TextMatcher` - Case-insensitive substring via delegation to RegexMatcher
  - `class:src/fs2/core/services/search/search_service.py:SearchService` - Orchestration with auto-detection and mode routing
  - `file:tests/unit/services/test_regex_matcher.py` - 24 tests for RegexMatcher (basic, timeout, error, scoring)
  - `file:tests/unit/services/test_text_matcher.py` - 13 tests for TextMatcher (delegation, escaping)
  - `file:tests/unit/services/test_search_service.py` - 17 tests for SearchService (auto-detection, orchestration)
  - `file:tests/integration/test_search_integration.py` - 9 integration tests with fixture_graph.pkl
  - DYK-P2-01: AUTO mode temporarily routes to TEXT (SEMANTIC not yet implemented)
  - DYK-P2-02: Absolute file-level line extraction for `sed -n` accuracy
  - DYK-P2-03: Score hierarchy (node_id exact=1.0, partial=0.8, content=0.5)
  - DYK-P2-04: smart_content matches use node's full (start_line, end_line) range
  - DYK-P2-05: Snippet contains full line at match start
  - DYK-P2-06: Pattern compilation optimization (compile once, search many)

[^8]: Phase 3 T000 - Async conversion + min_similarity 0.25
  - `method:src/fs2/core/services/search/search_service.py:SearchService.search` - Converted to async
  - `method:src/fs2/core/services/search/regex_matcher.py:RegexMatcher.match` - Converted to async
  - `method:src/fs2/core/services/search/regex_matcher.py:RegexMatcher.match_raw` - Converted to async
  - `method:src/fs2/core/services/search/text_matcher.py:TextMatcher.match` - Converted to async
  - `file:src/fs2/config/objects.py` - SearchConfig.min_similarity: 0.5 → 0.25
  - `file:src/fs2/core/models/search/query_spec.py` - QuerySpec.min_similarity: 0.5 → 0.25
  - All test files updated to use async/await with @pytest.mark.asyncio
  - DYK-P3-01: Async throughout for EmbeddingAdapter.embed_text() compatibility

[^9]: Phase 3 T001 - NumPy installation
  - `file:pyproject.toml` - Added numpy>=1.24 to dependencies
  - NumPy 2.4.0 installed via uv sync

[^10]: Phase 3 T002-T013 - Core SemanticMatcher implementation (89 tests)
  - `function:src/fs2/core/services/search/semantic_matcher.py:cosine_similarity` - NumPy vectorized with negative clamping
  - `class:src/fs2/core/services/search/semantic_matcher.py:SemanticMatcher` - Embedding-based search with chunk iteration
  - `method:src/fs2/core/services/search/semantic_matcher.py:SemanticMatcher.match` - Dual embedding search
  - `file:src/fs2/core/services/search/__init__.py` - Updated exports (SemanticMatcher, cosine_similarity)
  - `file:tests/unit/services/test_semantic_matcher.py` - 21 new tests for SemanticMatcher
  - `file:tests/unit/services/test_search_service.py` - 22 tests (updated for semantic fallback)
  - DYK-P3-02: AUTO → SEMANTIC with TEXT fallback if no embeddings
  - DYK-P3-03: Query embedding fixtures deferred (set_response() sufficient)
  - DYK-P3-04: min_similarity 0.25, clamp negative scores to 0
  - DYK-P3-05: Partial embedding coverage warning (proceed + log)
  - Note: T014-T017 (query fixtures) deferred to future iteration

---

**Plan Created**: 2025-12-24
**Next Step**: Run `/plan-4-complete-the-plan` to validate readiness

---

## Subtasks Registry

Mid-implementation detours requiring structured tracking.

| ID | Created | Phase | Parent Task | Reason | Status | Dossier |
|----|---------|-------|-------------|--------|--------|---------|
| 001-subtask-add-cli-graph-file-and-scan-path-params | 2025-12-24 | Phase 0: Chunk Offset Tracking | T010 | Fixture generation requires CLI params for custom input/output paths instead of custom script | [x] Complete | [Link](tasks/phase-0-chunk-offset-tracking/001-subtask-add-cli-graph-file-and-scan-path-params.md) |
