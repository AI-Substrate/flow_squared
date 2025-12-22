# Fix Tasks - Phase 3: Embedding Service

Order follows Full TDD: add/adjust tests first, then implementation.

## CRITICAL

1) **Graph integrity sync (plan ↔ dossier)**
- **Issue**: Dossier tasks lack [^13] footnotes and execution log anchors; plan ledger missing some changed files.
- **Fix**:
  - Run `plan-6a --sync-footnotes` to align dossier stubs with plan ledger [^13].
  - Add [^13] footnotes to Phase 3 task Notes column in `/workspaces/flow_squared/docs/plans/009-embeddings/tasks/phase-3-embedding-service/tasks.md` and ensure each completed task links to the correct execution log anchor.
  - Update plan ledger [^13] to include:
    - `/workspaces/flow_squared/src/fs2/core/repos/graph_store_impl.py`
    - `/workspaces/flow_squared/tests/unit/adapters/test_ast_parser_fake.py`
    - `/workspaces/flow_squared/tests/unit/models/test_code_node_embedding.py`

## HIGH

2) **Hash-based skip logic (tests first)**
- **Add tests** in `/workspaces/flow_squared/tests/unit/services/test_embedding_skip.py`:
  - Assert that a node with embeddings but a changed content hash does NOT skip.
  - Assert that hash match DOES skip.
- **Implement** in `/workspaces/flow_squared/src/fs2/core/services/embedding/embedding_service.py`:
  - Persist the hash used at embedding time (new field on CodeNode or embedding metadata).
  - Compare stored hash with `node.content_hash` in `_should_skip()`.

3) **Rate limit coordination + backoff (tests first)**
- **Add/strengthen tests** in `/workspaces/flow_squared/tests/unit/services/test_embedding_rate_limit.py`:
  - Assert that `EmbeddingRateLimitError.retry_after` pauses all concurrent batches.
  - Assert backoff is capped at 60 seconds.
  - Assert successful retry after backoff.
- **Implement** in `/workspaces/flow_squared/src/fs2/core/services/embedding/embedding_service.py`:
  - Catch `EmbeddingRateLimitError` separately.
  - Use asyncio.Event to pause all concurrent batch workers.
  - Apply `retry_after` or exponential backoff with `config.base_delay`/`config.max_delay`.

4) **Concurrent batch processing (tests first)**
- **Add tests** in `/workspaces/flow_squared/tests/unit/services/test_embedding_service.py`:
  - Assert batches are processed concurrently when `max_concurrent_batches > 1` (e.g., timing or call overlap).
- **Implement** in `/workspaces/flow_squared/src/fs2/core/services/embedding/embedding_service.py`:
  - Use `asyncio.Semaphore` + task group to limit concurrency.
  - Ensure rate-limit coordination works with concurrency.

## MEDIUM

5) **Chunk reassembly bound**
- **Issue**: `range(1000)` limits chunk collection.
- **Fix**: Track chunk counts per node during chunking or iterate keys from `chunk_embeddings` instead of fixed range.

6) **Test documentation compliance**
- **Issue**: TDD policy requires Purpose/Quality/Acceptance docstrings.
- **Fix**: Add required docstring fields to tests missing them, especially in `/workspaces/flow_squared/tests/unit/services/test_embedding_rate_limit.py`.

## Re-run
- `uv run pytest tests/unit/services/test_embedding_*.py -v`
- `uv run pytest tests/unit/models/test_content_type.py -v`
- `uv run pytest tests/unit/config/test_embedding_config.py tests/unit/adapters/test_embedding_exceptions.py tests/unit/models/test_code_node_embedding.py tests/unit/adapters/test_embedding_adapter*.py -v`
