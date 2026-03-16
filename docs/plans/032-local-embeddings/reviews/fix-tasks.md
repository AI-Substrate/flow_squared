# Fix Tasks: Phase 1 — Implementation

Apply in order. Re-run review after fixes.

## Critical / High Fixes

### FT-001: Restore adapter/service boundaries for local provider wiring
- **Severity**: HIGH
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/embedding_adapter.py`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/embedding/embedding_service.py`
- **Issue**: The contract/factory module now imports `sentence_transformers` directly, and `EmbeddingService.create()` duplicates local adapter construction by importing implementation details.
- **Fix**: Keep dependency probing and local-adapter construction behind an adapter-layer helper/implementation. Use one creation path for local mode so services compose an `EmbeddingAdapter` instead of knowing how to build one.
- **Patch hint**:
  ```diff
  -    elif embedding_config.mode == "local":
  -        try:
  -            import sentence_transformers  # noqa: F401
  -        except ImportError:
  -            return None
  -        ...
  -        return SentenceTransformerEmbeddingAdapter(config)
  +    elif embedding_config.mode == "local":
  +        return create_local_embedding_adapter_from_config(config)
  ```

### FT-002: Fix the user-facing re-embed command
- **Severity**: HIGH
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/embedding_stage.py`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/local-embeddings.md`
- **Issue**: The phase tells users to run `fs2 scan --embed --force`, but the CLI does not support `--embed`.
- **Fix**: Either add a real `--embed` alias to the CLI or update all new messages/docs to the supported invocation (`fs2 scan --force`, assuming embeddings remain enabled by default).
- **Patch hint**:
  ```diff
  - "that break search. Run `fs2 scan --embed --force` to "
  + "that break search. Run `fs2 scan --force` to "
  ```

### FT-003: Add real regression coverage for the mismatch/force flow
- **Severity**: HIGH
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_embedding_stage.py`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_scan_pipeline.py`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_scan_cli.py`
- **Issue**: The scoped diff contains no new tests for dimension mismatch blocking, `force_embeddings` propagation, or force-mode re-embed behavior, even though the execution log claims they were added.
- **Fix**: Add stage, pipeline, and CLI regression tests that cover mismatch detection, `--force` propagation, and exact user guidance text; then update the execution log with the real commands.
- **Patch hint**:
  ```diff
  + def test_given_dimension_mismatch_without_force_when_processing_then_raises_runtime_error(...):
  +     with pytest.raises(RuntimeError, match="--force"):
  +         stage.process(context)
  +
  + def test_given_force_flag_when_pipeline_runs_then_context_force_embeddings_is_true(...):
  +     assert captured_context.force_embeddings is True
  ```

## Medium / Low Fixes

### FT-004: Strengthen local adapter device-detection tests and make them lint-clean
- **Severity**: MEDIUM
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_embedding_adapter_local.py`
- **Issue**: AC3-AC6 are only weakly evidenced because tests replace `_detect_device()` with lambdas and do not assert required logs. The file also fails `ruff`.
- **Fix**: Mock lazy-imported `torch` while calling the real `_detect_device()`, assert CUDA/MPS/CPU/fallback logs with `caplog`, and remove the unused imports/variables/nested `with` structure.
- **Patch hint**:
  ```diff
  - adapter._detect_device = lambda: "mps"
  - result = adapter._detect_device()
  + with patch.dict("sys.modules", {"torch": mock_torch}):
  +     with caplog.at_level("INFO"):
  +         result = adapter._detect_device()
  + assert "MPS detected" in caplog.text
  ```

### FT-005: Correct preserved metrics after forced re-embed and reconcile artifacts
- **Severity**: MEDIUM
- **File(s)**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/embedding_stage.py`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/032-local-embeddings/local-embeddings-plan.md`, `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/032-local-embeddings/tasks/implementation/execution.log.md`
- **Issue**: `embedding_preserved` is calculated before force-mode clearing, and the phase artifacts no longer match the actual touched files/tests.
- **Fix**: Recompute preserved metrics from the post-force state and update the phase artifacts so they accurately reflect the final implementation/review scope.
- **Patch hint**:
  ```diff
  - context.metrics["embedding_preserved"] = preserved_count
  + context.metrics["embedding_preserved"] = sum(
  +     1 for node in context.nodes if node.embedding is not None
  + )
  ```

## Re-Review Checklist

- [ ] All critical/high fixes applied
- [ ] Re-run `/plan-7-v2-code-review` and achieve zero HIGH/CRITICAL
