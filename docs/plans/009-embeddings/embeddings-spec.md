# Embedding Service for Semantic Code Search

**Mode**: Full (multi-phase planning required)

> This specification incorporates findings from `research-dossier.md` (70 findings across 7 research areas).

---

## Research Context

Based on comprehensive analysis of the original Flowspace embedding system:

- **Components affected**: CodeNode model, scan pipeline, config system, new adapter layer
- **Critical dependencies**: tiktoken (token counting), Azure OpenAI / OpenAI-compatible APIs, numpy (vector operations)
- **Modification risks**: CodeNode is frozen dataclass - adding embedding fields requires careful design
- **Prior art**: SmartContentService provides proven async batch processing pattern

**Key Research Findings**:
1. Original Flowspace uses truncation (single embedding); user requires chunking (multiple embeddings)
2. Dual embedding architecture: both raw content AND smart content get independent embeddings
3. Token limits: 8000 (Azure) / 8191 (OpenAI-compatible) enforced via tiktoken
4. Hash-based skip logic prevents re-embedding unchanged content

See `research-dossier.md` for full analysis.

---

## Summary

**WHAT**: Add an embedding generation service that converts code content and AI-generated smart content into dense vector representations, enabling semantic similarity search across the codebase.

**WHY**: Text-based search (grep, regex) finds exact matches but misses conceptual relationships. Embeddings allow developers to search by meaning ("authentication flow", "error handling patterns") rather than keywords, dramatically improving codebase exploration and AI-assisted development workflows.

---

## Goals

1. **Generate embeddings for all indexed nodes** - Both raw content and smart content should be embedded for maximum search coverage
2. **Handle large content via chunking** - Content exceeding chunk size should be split into overlapping chunks, each embedded separately. Research indicates optimal parameters are:
   - **Code**: 400 tokens, 50 overlap (~12.5%)
   - **Documentation**: 800 tokens, 120 overlap (~15%)
   - **Smart content**: Usually no chunking needed (<500 tokens)
3. **Support multiple embedding providers** - Azure OpenAI, OpenAI-compatible APIs for flexibility and cost control
4. **[DEFERRED] Local transformers** - sentence-transformers provider deferred to post-v1. FakeEmbeddingAdapter with fixture file sufficient for testing
5. **Parallel processing at scale** - Process thousands of nodes efficiently using async worker pools (proven pattern from SmartContentService)
6. **Incremental updates** - Only re-embed content that has changed (hash-based skip logic)
7. **Integrate with scan pipeline** - Embeddings generated as a pipeline stage after smart content enrichment
8. **Persist embeddings with graph** - Store embeddings alongside nodes for efficient retrieval
9. **Graph config node for model tracking** - Store embedding model info in graph metadata; validate at search time to prevent cross-model comparisons

---

## Non-Goals

1. **Semantic search implementation** - This spec covers embedding generation only; search/query is a separate feature
2. **Vector database integration** - Embeddings stored in existing graph pickle; no external vector DB (e.g., Pinecone, Milvus)
3. **Cross-encoder re-ranking** - Advanced retrieval techniques are out of scope for initial implementation
4. **Real-time embedding updates** - Embeddings generated during scan, not on-demand
5. **Multi-language tokenizers** - Using cl100k_base for all content; language-specific tokenizers not supported
6. **Embedding fine-tuning** - Using off-the-shelf models only

---

## Testing Strategy

**Approach**: Full TDD
**Rationale**: CS-4 complexity with external API integrations, chunking algorithms, and pipeline integration requires comprehensive test coverage from the start.

**Mock Usage**: Targeted mocks
- **FakeEmbeddingAdapter**: Returns pre-computed embeddings from fixture file
- **Embedding Fixtures**: Generate once using real API, store as JSON with `{content, embedding_vector}` pairs
- Real implementations for internal components (chunking, token counting, service logic)

**Fixture Generation**:
```python
# One-time script to generate test fixtures
# Run with real API, save results for deterministic testing
fixtures = [
    {"content": "def add(a, b): return a + b", "embedding": [0.1, 0.2, ...]},
    {"smart_content": "Adds two numbers", "embedding": [0.3, 0.4, ...]},
    # ... ~20-50 realistic samples
]
```

**Focus Areas**:
- Chunking logic (token boundaries, overlap handling)
- Hash-based skip logic (content unchanged detection)
- Provider adapter contracts (ABC compliance)
- Batch processing (parallelism, error recovery)
- Graph config node (model mismatch detection)

**Excluded**:
- Actual API integration tests (use fixtures instead)
- Performance benchmarks (defer to validation phase)

---

## Documentation Strategy

**Location**: Hybrid (README.md + docs/how/)

**Content Split**:
- **README.md**: Add section on embedding configuration (3-5 lines showing config.yaml example)
- **docs/how/embeddings-guide.md**: Detailed guide covering providers, chunking, troubleshooting, fixture generation

**Target Audience**: Developers configuring fs2 for their projects
**Maintenance**: Update when adding new providers or changing config schema

---

## Complexity

**Score**: CS-4 (large)

**Breakdown**:
| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 2 | Multiple modules: adapters (4 files), service, stage, config, models |
| Integration (I) | 2 | External APIs (Azure, OpenAI), tiktoken library |
| Data/State (D) | 1 | New fields on CodeNode, storage format extension |
| Novelty (N) | 1 | Well-specified from research; chunking is new design |
| Non-Functional (F) | 1 | Performance (batching, parallelism), rate limiting required |
| Testing/Rollout (T) | 2 | Unit + integration tests, CLI flag for opt-out |

**Total**: P = 2+2+1+1+1+2 = **9** → **CS-4**

**Confidence**: 0.85 (high confidence due to comprehensive research and existing SmartContentService pattern)

**Assumptions**:
- tiktoken library available and works with Azure/OpenAI models
- SmartContentService pattern directly applicable
- CodeNode can be extended with embedding fields without breaking existing code
- Azure OpenAI quota sufficient for batch embedding

**Dependencies**:
- tiktoken package (token counting)
- openai package (Azure/OpenAI API client)
- numpy (vector operations)
- sentence-transformers (deferred to post-v1, for local provider)

**Risks**:
- API rate limiting may require careful backoff tuning
- Large codebases may have significant embedding costs
- Chunking strategy affects search quality (requires experimentation)

**Phases** (suggested):
1. Core infrastructure: Adapter ABC, config models, token counter, graph config node
2. Embedding service: Batch processing, chunking, hash-based skip
3. Provider implementations: Azure, OpenAI-compatible, Fake (with fixture file)
4. Pipeline integration: EmbeddingStage, CLI flag, progress reporting
5. Testing and validation: Full TDD tests, fixture generation, manual verification
6. Documentation: README section + docs/how/embeddings-guide.md
7. [DEFERRED] Local provider: sentence-transformers for offline use (post-v1)

---

## Acceptance Criteria

### AC1: Embedding Generation
**Given** a scanned codebase with nodes containing content and smart_content
**When** the embedding stage executes
**Then** each node receives embedding vectors for both content and smart_content (if present)

### AC2: Content-Type Aware Chunking
**Given** content exceeding chunk size threshold
**When** embedding is generated
**Then** content is split into overlapping chunks based on content type:
- Code (Python/TypeScript): 400 tokens, 50 overlap
- Documentation (Markdown): 800 tokens, 120 overlap
- Smart content: Single chunk (typically <500 tokens)
Each chunk is embedded separately and stored as array of vectors

### AC3: Hash-Based Skip Logic
**Given** a node whose content has not changed since last scan
**When** embedding stage runs
**Then** existing embeddings are preserved (not re-generated), reducing API calls and cost

### AC4: Provider Configuration
**Given** embedding configuration specifying `mode: azure`
**When** EmbeddingService is initialized
**Then** Azure OpenAI provider is used with configured endpoint, API key, model, and dimensions

### AC5: Parallel Processing
**Given** 1000 nodes requiring embedding
**When** `process_batch()` is called with `max_workers: 50`
**Then** embeddings are generated using 50 concurrent workers with rate limiting and exponential backoff

### AC6: Progress Reporting
**Given** embedding generation in progress
**When** progress callback is provided
**Then** callback receives `EmbeddingProgress` with processed, total, skipped, and error counts

### AC7: CLI Integration
**Given** user runs `fs2 scan`
**When** `--no-embeddings` flag is NOT provided
**Then** embedding stage executes after smart content stage

### AC8: Error Recovery
**Given** API error during embedding generation for a single node
**When** error occurs
**Then** error is logged, node is marked as failed, but processing continues for remaining nodes

### AC9: Graph Config Node
**Given** embeddings are generated during scan
**When** graph is persisted
**Then** a config node stores embedding metadata:
- `embedding_model`: "text-embedding-3-small"
- `embedding_dimensions`: 1024
- `chunk_params`: {"code": 400, "docs": 800}

### AC10: Model Mismatch Detection
**Given** a graph embedded with model "text-embedding-3-small"
**When** search is attempted with a different model configured
**Then** an `EmbeddingModelMismatchError` is raised with clear message about the conflict

### AC11: Storage Format
**Given** embeddings are generated
**When** graph is persisted
**Then** embeddings are stored as `tuple[tuple[float, ...], ...]` in CodeNode (frozen, hashable)

---

## Risks & Assumptions

### Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| API rate limiting causes batch failures | High | Exponential backoff with jitter; batch fallback to single-item |
| Large codebase embedding costs | Medium | Hash-based skip logic; configurable batch size; local provider option |
| Chunking strategy suboptimal | Medium | Configurable chunk_size and overlap; can tune based on search quality |
| tiktoken encoder mismatch | Low | Use cl100k_base (standard for text-embedding-3-*) |
| CodeNode frozen dataclass conflicts | Medium | Use replace() for updates; ensure hashable tuple storage |

### Assumptions
1. Azure OpenAI text-embedding-3-small model is available and performs well for code
2. 8000 token limit (Azure) is firm and requires chunking for large files
3. SmartContentService async pattern is proven and can be reused directly
4. Embedding dimensions (1024 for small, 3072 for large) are sufficient for code similarity
5. Graph pickle format can handle additional embedding fields without migration

---

## Open Questions

1. ~~**[RESOLVED: Chunk size and overlap]**~~ - External research completed. Optimal values are:
   - Code: 400 tokens, 50 overlap (not 7500/500)
   - Docs: 800 tokens, 120 overlap
   - See `external-research/chunk-size-research.md` for full analysis

2. ~~**[RESOLVED: Smart content embedding]**~~ - Embed everything regardless of length. Consistent behavior, no edge cases.

3. ~~**[RESOLVED: Local provider priority]**~~ - Deferred to post-v1. FakeEmbeddingAdapter with pre-computed fixture file sufficient for unit testing.

4. ~~**[RESOLVED: Embedding storage granularity]**~~ - Vectors only per-node. Model info stored once in graph config node. Validation at search time prevents cross-model comparisons.

---

## ADR Seeds (Optional)

### ADR-001: Chunking vs Truncation Strategy
**Decision Drivers**:
- Original Flowspace uses truncation (loses information for large files)
- User requirement explicitly requests chunking with array storage
- Search quality depends on capturing full content semantics

**Candidate Alternatives**:
- A: Truncation (simple, matches original Flowspace)
- B: Fixed-size chunking with overlap (user requirement)
- C: Semantic chunking (split at logical boundaries like functions)

**Stakeholders**: Product owner, users performing semantic search

### ADR-002: Embedding Provider Architecture
**Decision Drivers**:
- Need to support multiple providers (Azure, OpenAI, local)
- fs2 uses ABC + impl pattern for adapters
- Provider selection via configuration

**Candidate Alternatives**:
- A: Single provider class with conditional logic
- B: ABC interface with provider implementations (fs2 pattern)
- C: Plugin architecture with dynamic loading

**Stakeholders**: Maintainers, users with different infrastructure

---

## External Research

**Incorporated**:
- `external-research/chunk-size-research.md` - Comprehensive analysis of optimal chunking parameters

**Key Findings**:
1. **Smaller chunks are better**: 400-800 tokens optimal, not 7500 (original plan)
2. **Content-type matters**: Code needs smaller chunks (400) than docs (800)
3. **Overlap sweet spot**: 10-20% overlap balances context vs redundancy
4. **Code-aware splitting**: Prefer logical boundaries (functions/classes) over pure token splits
5. **Precision vs recall tradeoff**: Smaller chunks improve precision, overlap helps recall

**Applied To**:
- Goal #2: Updated chunk parameters
- AC2: Content-type aware chunking strategy
- Open Question #1: Resolved

---

## Unresolved Research

**Topics** (from research-dossier.md External Research Opportunities):
1. ~~**Optimal Chunk Size and Overlap**~~ - RESOLVED via external research
2. **Embedding Model Selection** - text-embedding-3-small assumed but code-specific models may perform better (deferred - can evaluate post-implementation)

**Impact**: Model selection could improve search quality but is lower priority than chunking strategy.

**Recommendation**: Proceed with text-embedding-3-small. Model is configurable, can evaluate alternatives later.

---

## Clarifications

### Session 2025-12-19

| # | Question | Answer | Updated Section |
|---|----------|--------|-----------------|
| Q1 | Workflow Mode | Full (confirmed) | Mode header |
| Q2 | Testing Strategy | Full TDD | New Testing Strategy section |
| Q3 | Mock Usage | Targeted mocks with pre-computed embedding fixtures | Testing Strategy |
| Q4 | Documentation Strategy | Hybrid (README + docs/how/) | New Documentation Strategy section |
| Q5 | Smart content threshold | Embed everything regardless of length | Open Question #2 resolved |
| Q6 | Local provider priority | Deferred to post-v1 | Goal #4 updated, Open Question #3 resolved |
| Q7 | Provenance storage | Vectors only per-node; model info in graph config node | AC9, AC10 added, Open Question #4 resolved |
| Q8 | Graph config scope | Embedding only (minimal scope) | AC9 |

**Coverage Summary**:
- **Resolved**: 8/8 questions answered
- **Deferred**: Local transformers provider (post-v1)
- **Outstanding**: None

---

**Specification Complete**: 2025-12-19 (Clarifications incorporated)
**Plan Directory**: docs/plans/009-embeddings/
**Next Step**: Run `/plan-3-architect` to generate phase-based plan
