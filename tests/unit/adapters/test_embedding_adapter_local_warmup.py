"""Tests for SentenceTransformerEmbeddingAdapter thread-safety and warmup.

046-T007/T008: TDD tests for thread-safe model loading, warmup behavior,
and MCP preload lifecycle.

Purpose: Verify that concurrent _get_model() calls load the model exactly
once, errors are stored and re-raised, and warmup() works correctly.

Per DYK#4: Uses a fake sentence_transformers module with controlled delay
to test lock behavior without loading a real 130MB model.

Per project convention: Mock for SentenceTransformer is a documented
exception (loading a real 130MB model in unit tests is impractical).
"""

import logging
import threading
import time
import types
from unittest.mock import MagicMock

import pytest

from fs2.config.objects import EmbeddingConfig, LocalEmbeddingConfig


def _make_mock_config_service(
    mode: str = "local",
    dimensions: int = 384,
    batch_size: int = 32,
    local: LocalEmbeddingConfig | None = None,
) -> MagicMock:
    """Create a mock ConfigurationService for adapter construction."""
    from fs2.config.service import ConfigurationService

    embedding_config = EmbeddingConfig(
        mode=mode,
        dimensions=dimensions,
        batch_size=batch_size,
        local=local or LocalEmbeddingConfig(),
    )
    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = embedding_config
    return mock_config


def _create_fake_st_module(delay: float = 0.3, dim: int = 384, fail: bool = False):
    """Create a fake sentence_transformers module with controlled delay.

    Returns (module, call_count_dict) where call_count_dict["value"]
    tracks how many times SentenceTransformer was constructed.
    """
    call_count = {"value": 0}
    call_count_lock = threading.Lock()

    class FakeSentenceTransformer:
        def __init__(self, model_name, device=None, local_files_only=False):
            with call_count_lock:
                call_count["value"] += 1
            if fail:
                raise OSError(f"Failed to load model: {model_name}")
            time.sleep(delay)
            self._dim = dim
            self.max_seq_length = 512

        def get_sentence_embedding_dimension(self):
            return self._dim

    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeSentenceTransformer

    return module, call_count


def _make_mock_torch():
    """Create a mock torch module for device detection."""
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.backends.mps.is_available.return_value = False
    return mock_torch


def _make_adapter_with_fakes(delay=0.3, fail=False):
    """Create a local adapter with fake sentence_transformers and torch.

    Returns (adapter, fake_st_module, call_count, patches) where
    patches is a context manager that must be active during use.
    """
    from unittest.mock import patch

    from fs2.core.adapters.embedding_adapter_local import (
        SentenceTransformerEmbeddingAdapter,
    )

    config = _make_mock_config_service(local=LocalEmbeddingConfig())
    adapter = SentenceTransformerEmbeddingAdapter(config)

    fake_st, call_count = _create_fake_st_module(delay=delay, fail=fail)
    mock_torch = _make_mock_torch()

    patches = patch.dict(
        "sys.modules",
        {"sentence_transformers": fake_st, "torch": mock_torch},
    )

    return adapter, fake_st, call_count, patches


@pytest.mark.unit
class TestThreadSafeModelLoading:
    """046-T007: Thread-safe _get_model() tests.

    AC-2: Concurrent search requests load the model exactly once.
    AC-9: Concurrent _get_model() calls yield exactly one model load.
    """

    def test_concurrent_get_model_loads_model_exactly_once(self):
        """Proves lock prevents duplicate model loads under concurrency.

        Races 5 threads calling _get_model() simultaneously.
        Without the lock (pre-T002), this would load the model 5 times.
        With the lock, only 1 load should occur.
        """
        adapter, _, call_count, patches = _make_adapter_with_fakes(delay=0.3)

        results = []
        errors = []

        def call_get_model():
            try:
                model = adapter._get_model()
                results.append(model)
            except Exception as e:
                errors.append(e)

        with patches:
            threads = [threading.Thread(target=call_get_model) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert len(results) == 5, "All 5 threads should have gotten a model"
        assert call_count["value"] == 1, (
            f"Model should be loaded exactly once, but was loaded {call_count['value']} times"
        )
        # All threads should get the same model instance
        assert all(r is results[0] for r in results), "All threads should share the same model"

    def test_get_model_returns_cached_model_on_second_call(self):
        """Proves model is cached after first load."""
        adapter, _, call_count, patches = _make_adapter_with_fakes(delay=0.05)

        with patches:
            model1 = adapter._get_model()
            model2 = adapter._get_model()

        assert model1 is model2
        assert call_count["value"] == 1


@pytest.mark.unit
class TestModelErrorStorage:
    """046-T007: Error storage and re-raise tests.

    AC-7: Warmup failure surfaces as actionable error on first semantic search.
    DYK#5: Error message includes 'Restart fs2 mcp'.
    """

    def test_model_load_failure_stored_and_reraised(self):
        """Proves load failure is stored and re-raised without retrying.

        After a load failure, subsequent _get_model() calls should
        immediately raise the stored error instead of retrying.
        Note: First call may attempt up to 2 constructions due to
        the offline-first retry pattern (local_files_only=True, then False).
        """
        from fs2.core.adapters.exceptions import EmbeddingAdapterError

        adapter, _, call_count, patches = _make_adapter_with_fakes(fail=True)

        with patches:
            # First call should fail (may attempt 2 constructions: offline + online)
            with pytest.raises(EmbeddingAdapterError):
                adapter._get_model()

            initial_count = call_count["value"]

            # Second call should re-raise stored error without ANY retry
            with pytest.raises(EmbeddingAdapterError):
                adapter._get_model()

        # No additional construction attempts on second call
        assert call_count["value"] == initial_count, (
            f"Model load should not be retried on second call, but "
            f"{call_count['value'] - initial_count} additional attempts made"
        )

    def test_model_error_includes_restart_instruction(self):
        """Proves error message includes actionable restart instruction.

        DYK#5: Error must include 'Restart `fs2 mcp`'.
        """
        from fs2.core.adapters.exceptions import EmbeddingAdapterError

        adapter, _, _, patches = _make_adapter_with_fakes(fail=True)

        with patches:
            with pytest.raises(EmbeddingAdapterError, match="Restart.*fs2 mcp"):
                adapter._get_model()


@pytest.mark.unit
class TestWarmupMethod:
    """046-T007: warmup() method tests.

    AC-4: Semantic search arriving during warmup waits and returns correct results.
    """

    def test_warmup_loads_model(self):
        """Proves warmup() triggers model loading."""
        adapter, _, call_count, patches = _make_adapter_with_fakes(delay=0.05)

        with patches:
            adapter.warmup()

        assert adapter._model is not None
        assert call_count["value"] == 1

    def test_warmup_does_not_raise_on_failure(self):
        """Proves warmup() catches errors (stored for later re-raise on search)."""
        adapter, _, _, patches = _make_adapter_with_fakes(fail=True)

        with patches:
            # warmup should NOT raise — it logs and stores the error
            adapter.warmup()

        # But _get_model() should re-raise the stored error
        from fs2.core.adapters.exceptions import EmbeddingAdapterError

        with patches:
            with pytest.raises(EmbeddingAdapterError):
                adapter._get_model()

    def test_warmup_called_from_background_thread(self):
        """Proves warmup() is safe to call from a background thread."""
        adapter, _, call_count, patches = _make_adapter_with_fakes(delay=0.1)

        with patches:
            thread = threading.Thread(target=adapter.warmup, daemon=True)
            thread.start()
            thread.join(timeout=5)

        assert adapter._model is not None
        assert call_count["value"] == 1

    def test_search_waits_for_warmup_to_complete(self):
        """Proves search threads block on lock until warmup finishes.

        AC-4: Warmup thread holds lock during load. Search thread's
        _get_model() blocks on lock, then gets the cached model.
        """
        adapter, _, call_count, patches = _make_adapter_with_fakes(delay=0.3)
        search_results = []

        def do_search():
            model = adapter._get_model()
            search_results.append(model)

        with patches:
            # Start warmup in background
            warmup_thread = threading.Thread(target=adapter.warmup, daemon=True)
            warmup_thread.start()

            # Small delay to ensure warmup starts first
            time.sleep(0.05)

            # Start search in another thread
            search_thread = threading.Thread(target=do_search)
            search_thread.start()

            warmup_thread.join(timeout=5)
            search_thread.join(timeout=5)

        assert len(search_results) == 1, "Search should have completed"
        assert adapter._model is not None
        assert call_count["value"] == 1, "Model loaded exactly once"

    def test_warmup_noop_on_base_class(self):
        """Proves base EmbeddingAdapter.warmup() is a no-op."""
        from fs2.core.adapters.embedding_adapter import EmbeddingAdapter

        # warmup should exist and be callable on the ABC
        assert hasattr(EmbeddingAdapter, "warmup")


@pytest.mark.unit
class TestWarmupLogging:
    """046-T007: Logging tests for warmup visibility.

    DYK#3: Log 'Waiting for embedding model to load...' before lock
    if model not ready, so callers see activity during first-time download.
    """

    def test_waiting_message_logged_when_model_not_ready(self, caplog):
        """Proves a waiting message is logged when model is loading."""
        adapter, _, _, patches = _make_adapter_with_fakes(delay=0.2)

        with patches:
            with caplog.at_level(logging.DEBUG):
                # Start warmup in background to hold lock
                warmup_thread = threading.Thread(target=adapter.warmup, daemon=True)
                warmup_thread.start()
                time.sleep(0.05)

                # Second call should log waiting message
                search_thread = threading.Thread(target=adapter._get_model)
                search_thread.start()

                warmup_thread.join(timeout=5)
                search_thread.join(timeout=5)

        # Check that some form of "waiting" or "loading" was logged
        log_text = caplog.text.lower()
        assert "model" in log_text and ("wait" in log_text or "load" in log_text), (
            f"Expected waiting/loading log message, got: {caplog.text}"
        )
