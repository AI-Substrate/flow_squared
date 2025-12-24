# External Research: Hybrid Search & Scoring Algorithms

**Research Date**: 2025-12-23
**Research Query**: Code search ranking algorithms, BM25, TF-IDF, cosine similarity, Reciprocal Rank Fusion (RRF), hybrid search scoring
**Sources**: Perplexity deep search

---

## Executive Summary

For fs2 search (which does NOT mix modes in initial implementation), this research informs:
1. **Scoring within each mode** - density-based for text, cosine similarity for semantic
2. **Future extensibility** - RRF provides a proven method for combining rankings if mode mixing is added later
3. **Code search specifics** - BM25 with structural boosting works well for code

---

## 1. BM25: The Standard for Lexical Search

### What It Is

BM25 (Best Matching 25) is the dominant algorithm for keyword-based document ranking, used by Lucene, Elasticsearch, and most search engines.

> "First introduced in 1994, BM25 eventually made its way into popular search engines like Apache Lucene and has been powering search bars across the internet for decades."
> — [Zawanah on Medium](https://medium.com/@zawanah/bm25-explained-the-classic-algorithm-that-still-powers-search-today-865351fce9aa)

### Key Components

| Component | Purpose |
|-----------|---------|
| **Term Frequency (TF)** | Counts how many times search terms appear |
| **Inverse Document Frequency (IDF)** | Gives more weight to rare terms |
| **Document Length Normalization** | Prevents longer documents from unfairly dominating |

### BM25 vs TF-IDF

> "BM25 builds on TF-IDF by taking the Binary Independence Model from the IDF calculation and adding a normalization penalty that weighs a document's length relative to the average length of all documents."
> — [Azure AI Search Documentation](https://learn.microsoft.com/en-us/azure/search/index-similarity-and-scoring)

### BM25 for Code Search

> "After implementing BM25 in Sourcegraph's recent 6.2 release, their internal search quality evaluations showed roughly 20% improvement across all key metrics compared to their baseline ranking."
> — [Sourcegraph Blog](https://sourcegraph.com/blog/keeping-it-boring-and-relevant-with-bm25f)

**Code-specific considerations**:
> "In code search ranking, it's critical to reward matches on certain structural elements. If you search for 'extract tar,' you likely want to see the function definition ExtractTar at the top of results."
> — [Sourcegraph Blog](https://sourcegraph.com/blog/keeping-it-boring-and-relevant-with-bm25f)

---

## 2. Cosine Similarity: The Standard for Semantic Search

### How It Works

Cosine similarity measures the angle between two vectors, producing a value from -1 to 1:
- **1.0**: Identical direction (most similar)
- **0.0**: Orthogonal (unrelated)
- **-1.0**: Opposite direction (opposite meaning)

> "Unlike Euclidean distance, which measures the magnitude of difference between two points, cosine similarity focuses on the direction of vectors. This makes it particularly useful for comparing high-dimensional data like word embeddings."
> — [Memgraph Blog](https://memgraph.com/blog/cosine-similarity-python-scikit-learn)

### Efficient NumPy Implementation

```python
import numpy as np
from numpy.linalg import norm

def cosine_similarity(query_vec: np.ndarray, doc_vec: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    return np.dot(query_vec, doc_vec) / (norm(query_vec) * norm(doc_vec))

def batch_cosine_similarity(query_vec: np.ndarray, doc_matrix: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between query and all documents.

    Args:
        query_vec: Shape (d,) - single query embedding
        doc_matrix: Shape (n, d) - n document embeddings

    Returns:
        Shape (n,) - similarity scores for each document
    """
    # Normalize query
    query_norm = query_vec / norm(query_vec)

    # Normalize all documents (row-wise)
    doc_norms = doc_matrix / norm(doc_matrix, axis=1, keepdims=True)

    # Batch dot product
    return np.dot(doc_norms, query_norm)
```

Source: [DataStax Medium](https://datastax.medium.com/how-to-implement-cosine-similarity-in-python-505e8ec1d823), [GeeksforGeeks](https://www.geeksforgeeks.org/python/how-to-calculate-cosine-similarity-in-python/)

### Performance Optimization

> "If you're going to use Python to directly compute cosine similarity, use optimized libraries like NumPy or scikit-learn. These libraries are optimized for performance and are generally faster than vanilla Python."
> — [DataStax Medium](https://datastax.medium.com/how-to-implement-cosine-similarity-in-python-505e8ec1d823)

For fs2 with ~10K nodes, NumPy is sufficient. For larger scales:
- **Numba**: JIT compilation for scientific computing
- **FAISS**: Facebook's similarity search library
- **scikit-learn**: `sklearn.metrics.pairwise.cosine_similarity` for batch operations

---

## 3. Reciprocal Rank Fusion (RRF): Combining Multiple Rankings

### What It Is

RRF combines rankings from multiple sources (e.g., BM25 + semantic search) into a single unified ranking.

> "Reciprocal Rank Fusion is a rank aggregation method that combines rankings from multiple sources into a single, unified ranking."
> — [ParadeDB Learn](https://www.paradedb.com/learn/search-concepts/reciprocal-rank-fusion)

### The Formula

```
RRF_score(d) = Σ 1 / (k + rank_i(d))
```

Where:
- `d` = document
- `k` = constant (typically 60)
- `rank_i(d)` = position of document d in ranking source i

> "The constant k acts as a smoothing factor. It prevents any single retriever from dominating the results and helps handle ties more gracefully."
> — [Deval Shah on Medium](https://medium.com/@devalshah1619/mathematical-intuition-behind-reciprocal-rank-fusion-rrf-explained-in-2-mins-002df0cc5e2a)

### RRF Implementation

```python
from collections import defaultdict
from dataclasses import dataclass

@dataclass
class RankedResult:
    node_id: str
    score: float

def reciprocal_rank_fusion(
    rankings: list[list[RankedResult]],
    k: int = 60
) -> list[RankedResult]:
    """Combine multiple rankings using RRF.

    Args:
        rankings: List of ranked result lists from different sources
        k: Smoothing constant (default 60, per original RRF paper)

    Returns:
        Combined ranking sorted by RRF score
    """
    rrf_scores: dict[str, float] = defaultdict(float)
    node_data: dict[str, RankedResult] = {}

    for ranking in rankings:
        for rank, result in enumerate(ranking, start=1):
            rrf_scores[result.node_id] += 1.0 / (k + rank)
            node_data[result.node_id] = result

    # Sort by RRF score descending
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    return [
        RankedResult(node_id=nid, score=rrf_scores[nid])
        for nid in sorted_ids
    ]
```

### Why RRF Works Well

> "RRF requires no tuning, and the different relevance indicators do not have to be related to each other to achieve high-quality results."
> — [OpenSearch Blog](https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/)

> "RRF's elegance lies in its simplicity: rather than normalizing scores within each scoring system, it works directly with document positions in the ranked lists."
> — [Elastic Search Labs](https://www.elastic.co/search-labs/blog/weighted-reciprocal-rank-fusion-rrf)

### Weighted RRF

For giving different importance to different sources:

```python
def weighted_rrf(
    rankings: list[tuple[list[RankedResult], float]],  # (ranking, weight)
    k: int = 60
) -> list[RankedResult]:
    """Weighted RRF for asymmetric source importance."""
    rrf_scores: dict[str, float] = defaultdict(float)

    for ranking, weight in rankings:
        for rank, result in enumerate(ranking, start=1):
            rrf_scores[result.node_id] += weight / (k + rank)

    # ... rest same as basic RRF
```

> "Weighted RRF provides a simple but powerful way to assign different importance levels to your retrievers."
> — [Elastic Search Labs](https://www.elastic.co/search-labs/blog/weighted-reciprocal-rank-fusion-rrf)

---

## 4. Score Normalization Techniques

### The Challenge

> "One challenge of hybrid search is that different retrievers produce scores on different scales. This difference makes it tricky to set static optimal weights for combining the results."
> — [OpenSearch Documentation](https://opensearch.org/blog/how-does-the-rank-normalization-work-in-hybrid-search/)

| Score Type | Range | Notes |
|------------|-------|-------|
| Cosine similarity | [-1, 1] or [0, 1] | Unit vectors always [0, 1] |
| BM25 | [0, ∞) | Unbounded, varies by corpus |
| Text density | [0, 1] | Custom metric |

### Min-Max Normalization

```python
def min_max_normalize(scores: list[float]) -> list[float]:
    """Normalize scores to [0, 1] range."""
    min_score = min(scores)
    max_score = max(scores)

    if max_score == min_score:
        return [0.5] * len(scores)  # All equal

    return [(s - min_score) / (max_score - min_score) for s in scores]
```

> "In a benchmark conducted by the OpenSearch team, they concluded that the min_max normalization technique combined with the arithmetic_mean score combination technique provides the best results in hybrid search."
> — [AWS OpenSearch Blog](https://aws.amazon.com/blogs/big-data/hybrid-search-with-amazon-opensearch-service/)

### L2 Normalization

```python
import numpy as np

def l2_normalize(scores: np.ndarray) -> np.ndarray:
    """L2 (Euclidean) normalization."""
    return scores / np.linalg.norm(scores)
```

> "L2 normalization ensures that the magnitude of the scores is normalized, providing a consistent scale for comparing different scores."
> — [OpenSearch Documentation](https://opensearch.org/docs/latest/search-plugins/search-pipelines/normalization-processor/)

### RRF vs Score Normalization Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| **RRF** | No tuning needed, works across scales | Ignores score magnitudes |
| **Min-Max + Mean** | Preserves relative distances | Requires tuning, sensitive to outliers |
| **Weighted Linear** | Fine-grained control | Requires weight optimization |

> "In contrast to a convex combination, a tuned RRF generalizes poorly to out-of-domain datasets. Because RRF is a function of ranks, it disregards the distribution of scores and, as such, discards useful information."
> — [ACM Transactions](https://dl.acm.org/doi/10.1145/3596512)

---

## 5. Hybrid Search Architecture

### How It Works

> "Hybrid search works by combining the results of sparse vector search (e.g., BM25) and dense vector search into a single, ranked list. Weaviate first performs both a vector search and a keyword search in parallel. The results are then handed to a fusion algorithm, such as RRF."
> — [Weaviate Blog](https://weaviate.io/blog/hybrid-search-explained)

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        User Query                           │
└─────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    │                    ▼
┌─────────────────┐           │           ┌─────────────────┐
│  Lexical Search │           │           │ Semantic Search │
│     (BM25)      │           │           │ (Cosine Sim)    │
└─────────────────┘           │           └─────────────────┘
         │                    │                    │
         │              ┌─────┴─────┐              │
         │              │    RRF    │              │
         └──────────────►  Fusion   ◄──────────────┘
                        └─────┬─────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Unified Results │
                    └─────────────────┘
```

---

## 6. Recommendations for fs2

### Current Implementation (No Mode Mixing)

Since fs2 search modes don't mix, each mode should optimize its own scoring:

#### Text Mode (via Regex)

```python
def score_text_match(pattern: str, content: str, node_id: str) -> float:
    """Score a text match with node_id priority."""
    pattern_lower = pattern.lower()

    # Node ID exact match = highest priority
    if pattern_lower == node_id.lower():
        return 1.0

    # Node ID partial match = high priority
    if pattern_lower in node_id.lower():
        return 0.8

    # Content match = density-based scoring
    content_lower = content.lower()
    occurrences = content_lower.count(pattern_lower)

    if occurrences == 0:
        return 0.0

    # Density: occurrences per 1000 chars, capped at 0.7
    density = min(0.7, (occurrences / max(len(content), 1)) * 1000)

    return density
```

#### Semantic Mode

```python
def score_semantic_match(
    query_embedding: np.ndarray,
    node_embedding: np.ndarray,
    min_similarity: float = 0.5
) -> float | None:
    """Score a semantic match using cosine similarity."""
    similarity = cosine_similarity(query_embedding, node_embedding)

    if similarity < min_similarity:
        return None  # Filter out low-similarity results

    return float(similarity)
```

### Future Extension: Hybrid Mode

If mode mixing is added later, use RRF:

```python
def hybrid_search(
    query: str,
    nodes: list[CodeNode],
    text_weight: float = 1.0,
    semantic_weight: float = 0.7,
) -> list[SearchResult]:
    """Combine text and semantic search using weighted RRF."""
    # Run both searches
    text_results = text_search(query, nodes)
    semantic_results = semantic_search(query, nodes)

    # Combine with weighted RRF
    return weighted_rrf([
        (text_results, text_weight),
        (semantic_results, semantic_weight),
    ])
```

### Key Takeaways

1. **For code search**: Node ID/name matches should rank higher than content matches
2. **For semantic search**: Cosine similarity with threshold filtering (0.5 default)
3. **For future hybrid**: RRF is the simplest effective fusion method
4. **Avoid premature optimization**: NumPy cosine similarity is fast enough for <10K nodes

---

## Sources

- [Weaviate: Hybrid Search Explained](https://weaviate.io/blog/hybrid-search-explained)
- [Sourcegraph: BM25 for Code Search](https://sourcegraph.com/blog/keeping-it-boring-and-relevant-with-bm25f)
- [ParadeDB: Reciprocal Rank Fusion](https://www.paradedb.com/learn/search-concepts/reciprocal-rank-fusion)
- [Elastic: Weighted RRF](https://www.elastic.co/search-labs/blog/weighted-reciprocal-rank-fusion-rrf)
- [OpenSearch: Rank Normalization](https://opensearch.org/blog/how-does-the-rank-normalization-work-in-hybrid-search/)
- [Superlinked: Optimizing RAG with Hybrid Search](https://superlinked.com/vectorhub/articles/optimizing-rag-with-hybrid-search-reranking)
- [DataStax: Cosine Similarity in Python](https://datastax.medium.com/how-to-implement-cosine-similarity-in-python-505e8ec1d823)
- [Azure AI Search: BM25 Scoring](https://learn.microsoft.com/en-us/azure/search/index-similarity-and-scoring)
