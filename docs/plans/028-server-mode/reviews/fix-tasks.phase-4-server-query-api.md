# Fix Tasks: Phase 4: Server Query API

Apply in order. Re-run review after fixes.

## Critical / High Fixes

### FT-001: Restore tree parity by reusing shared tree orchestration
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py; /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_query_api.py
- **Issue**: The route-layer tree helpers duplicate `TreeService` behavior but never expand symbol children or depth-limited hidden counts, so the remote tree output cannot match local `fs2 tree`.
- **Fix**: Replace `_compute_folder_hierarchy()`, `_build_folder_tree()`, and `_build_pattern_tree()` with a parity-preserving shared service or async wrapper that mirrors local tree semantics for folder mode, pattern mode, and depth handling. Add direct remote-vs-local parity tests.
- **Patch hint**:
  ```diff
  - tree_nodes = _compute_folder_hierarchy(file_nodes, max_depth)
  - tree_nodes = _build_pattern_tree(matched, store, max_depth)
  + tree_nodes = await query_tree_service.build_tree(
  +     store=store,
  +     pattern=pattern,
  +     max_depth=max_depth,
  + )
  ```

### FT-002: Implement real semantic search validation instead of silent fallback
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/app.py; /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_query_api.py
- **Issue**: T006/AC7 require model-aware semantic search with a 422 mismatch path, but the current code has no `model` query parameter, no graph-model comparison, and silently falls back to text when no embedding adapter is configured.
- **Fix**: Wire a real embedding adapter into `create_app()`, add a `model` query parameter for semantic requests, validate it against `graphs.embedding_model`, and return a clear 422 on mismatch. Unsupported semantic requests without an adapter should fail explicitly rather than degrade silently.
- **Patch hint**:
  ```diff
  + model: str | None = Query(default=None)
  ...
  - if embedding_adapter is None:
  -     logger.warning("No embedding adapter configured; falling back to text search")
  -     resolved_mode = "text"
  + if resolved_mode == "semantic" and query_vector is None and embedding_adapter is None:
  +     raise HTTPException(status_code=503, detail="Semantic search requires a configured embedding adapter")
  + _validate_requested_model(graphs, requested_model=model or embedding_adapter.model_name)
  ```

### FT-003: Fix the server → search boundary
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/services/search/__init__.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/services/search/pgvector_matcher.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/repos/protocols.py
- **Issue**: `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py` imports a search-internal implementation file directly, and `PgvectorSemanticMatcher` itself depends on an interface that currently lives in a concrete repo implementation module.
- **Fix**: Either promote `PgvectorSemanticMatcher` to a documented public search contract or hide it behind an existing public search API. If `ConnectionProvider` remains shared, move it into an interface-only module (for example `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/repos/protocols.py`) before cross-domain consumption.
- **Patch hint**:
  ```diff
  - from fs2.core.services.search.pgvector_matcher import PgvectorSemanticMatcher
  + from fs2.core.services.search import PgvectorSemanticMatcher
  ```
  ```diff
  - from fs2.core.repos.graph_store_pg import ConnectionProvider
  + from fs2.core.repos.protocols import ConnectionProvider
  ```

### FT-004: Add the missing Phase 4 core tests and AC10 evidence
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_pgvector_matcher.py; /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_graph_store_pg.py; /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_query_api.py; /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-4-server-query-api/execution.log.md
- **Issue**: The phase doc and execution log claim completed matcher/store/query validation, but the diff adds only `test_query_api.py`. There is no matcher test file, no Phase 4 graph-store test coverage, and no benchmark output for AC10.
- **Fix**: Add unit/integration coverage for `PgvectorSemanticMatcher.search()`, `PostgreSQLGraphStore.get_filtered_nodes_async()`, `search_text_async()`, `search_regex_async()`, `get_children_count_async()`, and `has_embeddings_async()`. Extend query-route tests for regex, semantic, mismatch-422, multi-graph attribution/sorting, and direct remote/local parity. Record actual benchmark and test outputs in the execution log.
- **Patch hint**:
  ```diff
  + async def test_given_query_vector_when_matching_then_returns_best_chunk_per_node(): ...
  + async def test_given_model_mismatch_when_semantic_search_then_returns_422(): ...
  + async def test_given_regex_mode_when_searching_then_results_match_local_shape(): ...
  ```

## Medium / Low Fixes

### FT-005: Align get-node/search serialization with local output
- **Severity**: MEDIUM
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py; /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_query_api.py
- **Issue**: The current get-node/search serializers are bespoke and only partially match the local shapes promised in the phase doc.
- **Fix**: Reuse the local search envelope helpers and documented get-node shape instead of maintaining separate route-local serializers. Add parity tests that compare remote output to local serializers for min/max detail.
- **Patch hint**:
  ```diff
  - folders = _compute_folder_distribution(results)
  + from fs2.core.models.search.search_result_meta import compute_folder_distribution
  + folders = compute_folder_distribution([r["node_id"] for r in results])
  ```

### FT-006: Refresh domain artifacts after the boundary decision
- **Severity**: MEDIUM
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/search/domain.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/graph-storage/domain.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md
- **Issue**: The touched domain docs add Phase 4 history entries but do not fully document the new Contracts/Composition, and the domain map still labels an internal search dependency as a contract edge.
- **Fix**: After the code boundary is corrected, update the domain docs so they describe the final public surface and composition accurately.
- **Patch hint**:
  ```diff
  + ## Composition
  + | Component | Role | Depends On |
  + |-----------|------|------------|
  + | `query.py` | REST query routes | `PostgreSQLGraphStore`, public search contract, `Database` |
  ```

### FT-007: Clean the new query API test file so lint passes
- **Severity**: LOW
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_query_api.py
- **Issue**: Targeted Ruff validation currently fails because of unused imports (`json`, `AsyncMock`, `create_app`) and unsorted import blocks.
- **Fix**: Remove the unused imports, normalize the import order, and rerun the targeted Ruff command before re-review.
- **Patch hint**:
  ```diff
  - import json
  - from unittest.mock import AsyncMock
  - from fs2.server.app import create_app
  + from collections.abc import AsyncGenerator
  ```

## Re-Review Checklist

- [ ] All critical/high fixes applied
- [ ] Re-run `/plan-7-v2-code-review` and achieve zero HIGH/CRITICAL
