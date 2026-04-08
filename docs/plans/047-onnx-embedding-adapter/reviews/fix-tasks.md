# Fix Tasks: ONNX Embedding Adapter

Apply in order. Re-run review after fixes.

## Critical / High Fixes

### FT-001: Persist the actual ONNX model identifier in graph metadata
- **Severity**: HIGH
- **File(s)**:
  - /Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/core/services/embedding/embedding_service.py
  - /Users/jordanknight/substrate/fs2/045-windows-compat/tests/unit/services/test_embedding_service.py
- **Issue**: `EmbeddingService.get_metadata()` still persists `embedding_model` as the mode name (`"onnx"`) instead of the actual model identifier. Because `EmbeddingStage._detect_metadata_mismatch()` compares `embedding_model`, switching between same-dimension ONNX models can silently preserve stale vectors and mix embedding spaces.
- **Fix**: Persist the actual ONNX model name (for example `self._config.onnx.model`) in metadata for ONNX mode, and add a regression test proving that changing the ONNX model changes metadata and forces re-embed logic to trigger.
- **Patch hint**:
  ```diff
  -        model_name = self._config.mode
  +        model_name = self._config.mode
  +        if self._config.mode == "onnx" and self._config.onnx is not None:
  +            model_name = self._config.onnx.model
           if self._config.mode == "azure" and self._config.azure is not None:
               model_name = self._config.azure.deployment_name
  ```

### FT-002: Preserve actionable ONNX load failures after warmup/retry
- **Severity**: HIGH
- **File(s)**: /Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/core/adapters/embedding_adapter_onnx.py
- **Issue**: `_get_session()` creates actionable `EmbeddingAdapterError` messages for missing runtime/model problems, then replaces them with a generic cached restart-only error at lines 220-224. After warmup or a first failed load, later user-facing calls lose the concrete fix guidance required by AC-7 and the project's actionable-error doctrine.
- **Fix**: Cache the original `EmbeddingAdapterError` instead of replacing it, or wrap it while preserving the original guidance in the raised message.
- **Patch hint**:
  ```diff
  -            except EmbeddingAdapterError:
  -                self._session_error = EmbeddingAdapterError(
  -                    "ONNX session failed to load. "
  -                    "Restart `fs2 mcp` after resolving the issue."
  -                )
  -                raise
  +            except EmbeddingAdapterError as e:
  +                self._session_error = e
  +                raise
  ```

### FT-003: Add durable regression coverage for the core ONNX promises
- **Severity**: HIGH
- **File(s)**:
  - /Users/jordanknight/substrate/fs2/045-windows-compat/tests/unit/adapters/test_embedding_adapter_onnx.py
  - /Users/jordanknight/substrate/fs2/045-windows-compat/docs/plans/047-onnx-embedding-adapter/execution.log.md
- **Issue**: The reviewed phase does not directly verify numeric equivalence (AC-2), config-driven pooling detection (AC-5), or the production load/warmup/scan/search paths (AC-3, AC-4, AC-9, AC-10, AC-11). Those claims are still mostly inferred from workshop prose, summary counts, or manual flag setting.
- **Fix**: Add deterministic commit-local regression tests that exercise production pooling detection and reference-vector comparison, then capture concrete command/output evidence for semantic search, `fs2 scan --embed`, and warmup/preload behavior in `execution.log.md`.
- **Patch hint**:
  ```diff
  +def test_given_pooling_config_when_detected_then_cls_vs_mean_is_selected(...):
  +    ...
  +
  +def test_given_reference_vectors_when_encoding_then_l2_distance_stays_below_threshold(...):
  +    ...
  +
  +def test_given_onnx_mode_when_embedding_service_created_then_scan_path_uses_onnx(...):
  +    ...
  ...
  +## Additional Verification
  +- `fs2 scan --embed ...` => <captured output>
  +- `fs2 search "..." --mode semantic` => <captured output>
  +- preload / warmup transcript => <captured output>
  ```

### FT-004: Make the reviewed commit actually lint-clean
- **Severity**: HIGH
- **File(s)**:
  - /Users/jordanknight/substrate/fs2/045-windows-compat/tests/unit/adapters/test_embedding_adapter_onnx.py
  - /Users/jordanknight/substrate/fs2/045-windows-compat/docs/plans/047-onnx-embedding-adapter/execution.log.md
- **Issue**: The reviewed commit still fails `ruff` (`types` unused, nested `with`, unused `original_get`, undefined `EmbeddingAdapterError` in dead code), so the execution log's "All changed files pass ruff" claim is false.
- **Fix**: Remove the dead code and unused symbols, collapse the context managers, rerun `ruff`, and record the actual passing command/output in `execution.log.md`.
- **Patch hint**:
  ```diff
  -import types
   from unittest.mock import MagicMock, patch
  ...
  -        with patch.dict("sys.modules", {"onnxruntime": None}):
  -            with pytest.raises(EmbeddingAdapterError, match="onnxruntime"):
  -                adapter._get_session()
  +        with patch.dict("sys.modules", {"onnxruntime": None}), pytest.raises(
  +            EmbeddingAdapterError, match="onnxruntime"
  +        ):
  +            adapter._get_session()
  ...
  -        original_get = adapter._get_session
  ...
  -        adapter._session_error = EmbeddingAdapterError("test error") if False else None
  +        adapter._session_error = None
  ```

## Medium / Low Fixes

### FT-005: Remove ONNX implementation/config knowledge from the service layer
- **Severity**: MEDIUM
- **File(s)**: /Users/jordanknight/substrate/fs2/045-windows-compat/src/fs2/core/services/embedding/embedding_service.py
- **Issue**: The ONNX branch at lines 170-176 imports `OnnxEmbeddingAdapter` directly and materializes `OnnxEmbeddingConfig()` inside `EmbeddingService.create()`, which extends concrete adapter/config awareness in the service layer.
- **Fix**: Move ONNX adapter selection/defaulting behind the adapter factory or composition root so the service continues to depend only on contracts and injected config.
- **Patch hint**:
  ```diff
  -        elif embedding_config.mode == "onnx":
  -            from fs2.config.objects import OnnxEmbeddingConfig
  -            from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter
  -
  -            if embedding_config.onnx is None:
  -                embedding_config.onnx = OnnxEmbeddingConfig()
  -            embedding_adapter = OnnxEmbeddingAdapter(config)
  +        elif embedding_config.mode == "onnx":
  +            from fs2.core.adapters.embedding_adapter import (
  +                create_embedding_adapter_from_config,
  +            )
  +
  +            embedding_adapter = create_embedding_adapter_from_config(config)
  +            if embedding_adapter is None:
  +                raise ValueError(
  +                    "ONNX embeddings require onnxruntime and a valid embedding config"
  +                )
  ```

### FT-006: Align the ONNX test suite with fs2's canonical test doctrine
- **Severity**: MEDIUM
- **File(s)**: /Users/jordanknight/substrate/fs2/045-windows-compat/tests/unit/adapters/test_embedding_adapter_onnx.py
- **Issue**: The suite uses lightweight "Proves..." docstrings, non-canonical test names, `MagicMock` for config/runtime collaborators, and `time.sleep()` for concurrency coordination, which diverges from the repo's documented fake-first, deterministic, executable-doc style.
- **Fix**: Rename tests to the `test_given_<precondition>_when_<action>_then_<outcome>` pattern, expand docstrings to include Purpose and Quality Contribution, prefer fakes where feasible, and replace sleep-based concurrency coordination with `Event`/`Barrier`.
- **Patch hint**:
  ```diff
  -def test_batch_preserves_order(self):
  -    """Proves batch returns one embedding per input, in order."""
  +def test_given_multiple_texts_when_batch_encoding_then_order_is_preserved(self):
  +    """Purpose: verify batch output order is stable.
  +    Quality Contribution: prevents silent reordering bugs in chunk reassembly.
  +    """
  +    # Arrange
  +    ...
  +    # Act
  +    ...
  +    # Assert
  +    ...
  ```

## Re-Review Checklist

- [x] All critical/high fixes applied
- [ ] Re-run `/plan-7-v2-code-review --plan "/Users/jordanknight/substrate/fs2/045-windows-compat/docs/plans/047-onnx-embedding-adapter/onnx-embedding-adapter-plan.md"` and achieve zero HIGH/CRITICAL
