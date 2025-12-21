# Fix Tasks — Phase 2: Embedding Adapters

## CRITICAL
1) Sync plan↔dossier task tables and logs.
- Files: /workspaces/flow_squared/docs/plans/009-embeddings/embeddings-plan.md, /workspaces/flow_squared/docs/plans/009-embeddings/tasks/phase-2-embedding-adapters/tasks.md, /workspaces/flow_squared/docs/plans/009-embeddings/tasks/phase-2-embedding-adapters/execution.log.md
- Fix: Update Phase 2 tasks in plan to [x] with [📋] links to execution log anchors; add any missing tasks (e.g., AzureEmbeddingConfig) or record a plan deviation.
- Patch hint:
  ```diff
  -| 2.1 | [ ] | Write tests for EmbeddingAdapter ABC | ... | - |
  +| 2.1 | [x] | Write tests for EmbeddingAdapter ABC | ... | [📋](./tasks/phase-2-embedding-adapters/execution.log.md#task-t002-t003) |
  ```

## HIGH
2) Populate Phase 2 footnotes and ledger entries.
- Files: /workspaces/flow_squared/docs/plans/009-embeddings/tasks/phase-2-embedding-adapters/tasks.md, /workspaces/flow_squared/docs/plans/009-embeddings/embeddings-plan.md
- Fix: Add footnote tags (e.g., [^12]) in task Notes for changed files; add matching footnote stubs in Phase Footnote Stubs; add Phase 2 entries in Change Footnotes Ledger with FlowSpace node IDs.
- Patch hint:
  ```diff
  -| [x] | T005 | Implement AzureEmbeddingAdapter | ... | Per Plan 2.6 ... |
  +| [x] | T005 | Implement AzureEmbeddingAdapter | ... | Per Plan 2.6 ... [^12] |
  ```

3) Implement global rate-limit coordination for Azure adapter per plan.
- File: /workspaces/flow_squared/src/fs2/core/adapters/embedding_adapter_azure.py
- Fix: Add shared `asyncio.Event` (module-level or injected) to coordinate backoff across concurrent calls; update tests to assert the event pauses other workers.
- Patch hint:
  ```diff
  +RATE_LIMIT_EVENT = asyncio.Event()
  ...
  +if RATE_LIMIT_EVENT.is_set():
  +    await asyncio.sleep(delay)
  +    RATE_LIMIT_EVENT.clear()
  ```

4) Implement fixture-backed FakeEmbeddingAdapter per plan.
- Files: /workspaces/flow_squared/src/fs2/core/adapters/embedding_adapter_fake.py, /workspaces/flow_squared/tests/unit/adapters/test_embedding_adapter_fake.py, /workspaces/flow_squared/tests/fixtures/embedding_fixtures.json
- Fix: Load fixture embeddings (or fixture graph index) and add tests validating fixture lookup; keep deterministic fallback for unknown content.
- Patch hint:
  ```diff
  +def _load_fixture(self, fixture_path: str) -> dict[str, list[float]]:
  +    ...
  +def _lookup_fixture_embedding(self, text: str) -> list[float] | None:
  +    ...
  ```

## MEDIUM
5) Re-run Phase 1 regression tests and record evidence.
- Evidence commands (from Phase 1 log):
  - `uv run pytest tests/unit/config/test_embedding_config.py -v`
  - `uv run pytest tests/unit/adapters/test_embedding_exceptions.py -v`
  - `uv run pytest tests/unit/models/test_code_node_embedding.py -v`
- Record results in the review report and/or execution log.
