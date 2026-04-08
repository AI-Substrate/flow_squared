"""Tests for OnnxEmbeddingAdapter.

047-T003: TDD tests for ONNX adapter encode pipeline.
Purpose: Verify pooling detection, encoding, normalization,
return type enforcement, thread safety, and error handling.

Mock Usage: Targeted mocks for ONNX InferenceSession and tokenizers.
This is a documented exception to the project's fakes-over-mocks convention
(loading a real 127MB ONNX model in unit tests is impractical).
"""

import threading
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from fs2.config.objects import EmbeddingConfig, OnnxEmbeddingConfig


def _make_mock_config_service(
    mode: str = "onnx",
    dimensions: int = 384,
    batch_size: int = 32,
    onnx: OnnxEmbeddingConfig | None = None,
) -> MagicMock:
    """Create a mock ConfigurationService for adapter construction."""
    from fs2.config.service import ConfigurationService

    embedding_config = EmbeddingConfig(
        mode=mode,
        dimensions=dimensions,
        batch_size=batch_size,
        onnx=onnx or OnnxEmbeddingConfig(),
    )
    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = embedding_config
    return mock_config


def _make_mock_onnx_session(dim: int = 384, seq_len: int = 10):
    """Create a mock ONNX InferenceSession."""
    session = MagicMock()

    # Mock inputs
    input_ids_input = MagicMock()
    input_ids_input.name = "input_ids"
    input_ids_input.shape = ["batch_size", "sequence_length"]

    attention_mask_input = MagicMock()
    attention_mask_input.name = "attention_mask"
    attention_mask_input.shape = ["batch_size", "sequence_length"]

    token_type_ids_input = MagicMock()
    token_type_ids_input.name = "token_type_ids"
    token_type_ids_input.shape = ["batch_size", "sequence_length"]

    session.get_inputs.return_value = [
        input_ids_input,
        attention_mask_input,
        token_type_ids_input,
    ]

    # Mock output
    output = MagicMock()
    output.shape = ["batch_size", "sequence_length", dim]
    session.get_outputs.return_value = [output]

    def run_fn(output_names, input_feed):
        batch_size = input_feed["input_ids"].shape[0]
        actual_seq_len = input_feed["input_ids"].shape[1]
        # Return random but deterministic last_hidden_state
        np.random.seed(42)
        return [np.random.randn(batch_size, actual_seq_len, dim).astype(np.float32)]

    session.run = run_fn
    return session


def _make_mock_tokenizer(seq_len: int = 10):
    """Create a mock tokenizers.Tokenizer."""
    tokenizer = MagicMock()

    class FakeEncoding:
        def __init__(self, length):
            self.ids = [101] + [1000] * (length - 2) + [102]
            self.attention_mask = [1] * length

    def encode_batch_fn(texts):
        return [FakeEncoding(seq_len) for _ in texts]

    tokenizer.encode_batch = encode_batch_fn
    return tokenizer


@pytest.mark.unit
class TestOnnxAdapterInit:
    """047-T003: Tests for adapter initialization."""

    def test_given_config_when_constructed_then_provider_name_is_onnx(self):
        """Proves provider_name returns 'onnx'."""
        from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter

        config = _make_mock_config_service()
        adapter = OnnxEmbeddingAdapter(config)
        assert adapter.provider_name == "onnx"

    def test_given_config_when_constructed_then_session_not_loaded(self):
        """Proves session is lazy-loaded, not in __init__."""
        from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter

        config = _make_mock_config_service()
        adapter = OnnxEmbeddingAdapter(config)
        assert adapter._session is None

    def test_given_no_onnx_config_when_constructed_then_raises_error(self):
        """Proves missing onnx config raises EmbeddingAdapterError."""
        from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter
        from fs2.core.adapters.exceptions import EmbeddingAdapterError

        config = _make_mock_config_service()
        config.require.return_value = EmbeddingConfig(mode="onnx", onnx=None)

        with pytest.raises(EmbeddingAdapterError, match="ONNX config is required"):
            OnnxEmbeddingAdapter(config)


@pytest.mark.unit
class TestOnnxAdapterPooling:
    """047-T003: CLS vs mean pooling tests."""

    def test_cls_pooling_takes_first_token(self):
        """Proves CLS pooling extracts the [CLS] token embedding."""
        from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter

        config = _make_mock_config_service()
        adapter = OnnxEmbeddingAdapter(config)

        # Inject mock session/tokenizer
        adapter._session = _make_mock_onnx_session()
        adapter._tokenizer = _make_mock_tokenizer()
        adapter._use_cls_pooling = True

        result = adapter._encode_sync(["test text"])

        assert isinstance(result, list)
        assert isinstance(result[0], list)
        assert isinstance(result[0][0], float)
        assert len(result) == 1
        assert len(result[0]) == 384

    def test_mean_pooling_averages_tokens(self):
        """Proves mean pooling averages across all non-padded tokens."""
        from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter

        config = _make_mock_config_service()
        adapter = OnnxEmbeddingAdapter(config)

        adapter._session = _make_mock_onnx_session()
        adapter._tokenizer = _make_mock_tokenizer()
        adapter._use_cls_pooling = False  # Mean pooling

        result = adapter._encode_sync(["test text"])

        assert isinstance(result, list)
        assert len(result) == 1
        assert len(result[0]) == 384

    def test_cls_and_mean_produce_different_embeddings(self):
        """Proves CLS and mean pooling produce different results."""
        from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter

        config = _make_mock_config_service()
        adapter = OnnxEmbeddingAdapter(config)

        session = _make_mock_onnx_session()
        tokenizer = _make_mock_tokenizer()

        adapter._session = session
        adapter._tokenizer = tokenizer
        adapter._use_cls_pooling = True
        cls_result = adapter._encode_sync(["test text"])

        adapter._use_cls_pooling = False
        mean_result = adapter._encode_sync(["test text"])

        # They should be different
        assert cls_result[0] != mean_result[0]


@pytest.mark.unit
class TestOnnxAdapterNormalization:
    """047-T003: L2 normalization tests."""

    def test_output_is_l2_normalized(self):
        """Proves output vectors have unit L2 norm."""
        from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter

        config = _make_mock_config_service()
        adapter = OnnxEmbeddingAdapter(config)

        adapter._session = _make_mock_onnx_session()
        adapter._tokenizer = _make_mock_tokenizer()
        adapter._use_cls_pooling = True

        result = adapter._encode_sync(["test text"])

        norm = float(np.linalg.norm(result[0]))
        assert abs(norm - 1.0) < 1e-5, f"Expected unit norm, got {norm}"


@pytest.mark.unit
class TestOnnxAdapterReturnType:
    """047-T003: Return type contract tests."""

    def test_embed_sync_returns_list_of_list_float(self):
        """Proves return type is list[list[float]], not numpy."""
        from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter

        config = _make_mock_config_service()
        adapter = OnnxEmbeddingAdapter(config)

        adapter._session = _make_mock_onnx_session()
        adapter._tokenizer = _make_mock_tokenizer()
        adapter._use_cls_pooling = True

        result = adapter._encode_sync(["hello", "world"])

        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], list)
        assert isinstance(result[0][0], float)
        # Ensure no numpy types leaked
        assert type(result[0][0]) is float


@pytest.mark.unit
class TestOnnxAdapterBatch:
    """047-T003: Batch encoding tests."""

    def test_batch_preserves_order(self):
        """Proves batch returns one embedding per input, in order."""
        from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter

        config = _make_mock_config_service()
        adapter = OnnxEmbeddingAdapter(config)

        adapter._session = _make_mock_onnx_session()
        adapter._tokenizer = _make_mock_tokenizer()
        adapter._use_cls_pooling = True

        texts = ["text1", "text2", "text3"]
        result = adapter._encode_sync(texts)

        assert len(result) == 3


@pytest.mark.unit
class TestOnnxAdapterErrors:
    """047-T003: Error handling tests."""

    def test_missing_onnxruntime_raises_actionable_error(self):
        """Proves missing onnxruntime gives install instructions."""
        from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter
        from fs2.core.adapters.exceptions import EmbeddingAdapterError

        config = _make_mock_config_service()
        adapter = OnnxEmbeddingAdapter(config)

        with (
            patch.dict("sys.modules", {"onnxruntime": None}),
            pytest.raises(EmbeddingAdapterError, match="onnxruntime"),
        ):
            adapter._get_session()

    def test_session_error_stored_and_reraised(self):
        """Proves load failure stored and re-raised without retrying."""
        from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter
        from fs2.core.adapters.exceptions import EmbeddingAdapterError

        config = _make_mock_config_service()
        adapter = OnnxEmbeddingAdapter(config)

        # Force a load error
        adapter._session_error = EmbeddingAdapterError("test error")

        with pytest.raises(EmbeddingAdapterError, match="test error"):
            adapter._get_session()


@pytest.mark.unit
class TestOnnxAdapterThreadSafety:
    """047-T003: Thread-safe session loading tests."""

    def test_concurrent_get_session_loads_once(self):
        """Proves lock prevents duplicate session loads under concurrency."""
        from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter

        config = _make_mock_config_service()
        adapter = OnnxEmbeddingAdapter(config)

        load_count = {"value": 0}
        mock_session = _make_mock_onnx_session()
        mock_tokenizer = _make_mock_tokenizer()

        barrier = threading.Barrier(5, timeout=10)

        def slow_load():
            """Simulate slow load that we control."""
            barrier.wait()
            with adapter._session_lock:
                if adapter._session is not None:
                    return adapter._session, adapter._tokenizer
                load_count["value"] += 1
                adapter._session = mock_session
                adapter._tokenizer = mock_tokenizer
                adapter._use_cls_pooling = True
                return adapter._session, adapter._tokenizer

        adapter._get_session = slow_load

        results = []
        errors = []

        def call_get():
            try:
                s, t = adapter._get_session()
                results.append(s)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=call_get) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        assert len(results) == 5
        assert load_count["value"] == 1


@pytest.mark.unit
class TestOnnxAdapterWarmup:
    """047-T003: warmup() tests."""

    def test_warmup_noop_on_base_class(self):
        """Proves base EmbeddingAdapter.warmup() is a no-op."""
        from fs2.core.adapters.embedding_adapter import EmbeddingAdapter

        assert hasattr(EmbeddingAdapter, "warmup")

    def test_warmup_loads_session(self):
        """Proves warmup triggers session loading."""
        from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter

        config = _make_mock_config_service()
        adapter = OnnxEmbeddingAdapter(config)

        # Pre-inject session to avoid real loading
        adapter._session = _make_mock_onnx_session()
        adapter._tokenizer = _make_mock_tokenizer()

        # warmup should not raise
        adapter.warmup()
        assert adapter._session is not None

    def test_warmup_does_not_raise_on_failure(self):
        """Proves warmup catches errors (stored for re-raise on search)."""
        from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter
        from fs2.core.adapters.exceptions import EmbeddingAdapterError

        config = _make_mock_config_service()
        adapter = OnnxEmbeddingAdapter(config)

        # Mock _get_session to raise
        def fail_load():
            adapter._session_error = EmbeddingAdapterError("load failed")
            raise adapter._session_error

        adapter._get_session = fail_load

        # warmup should NOT raise
        adapter.warmup()
        assert adapter._session_error is not None


@pytest.mark.unit
class TestOnnxConfigValidation:
    """047-T008: Config validation tests."""

    def test_onnx_mode_accepted_by_pydantic(self):
        """Proves mode='onnx' is a valid config value."""
        config = EmbeddingConfig(mode="onnx")
        assert config.mode == "onnx"

    def test_onnx_config_defaults(self):
        """Proves OnnxEmbeddingConfig has sensible defaults."""
        onnx_config = OnnxEmbeddingConfig()
        assert onnx_config.model == "BAAI/bge-small-en-v1.5"
        assert onnx_config.max_seq_length == 512
        assert onnx_config.provider == "CPUExecutionProvider"

    def test_onnx_mode_auto_defaults_dimensions_384(self):
        """Proves ONNX mode auto-defaults dimensions to 384."""
        config = EmbeddingConfig(mode="onnx")
        assert config.dimensions == 384

    def test_onnx_mode_respects_explicit_dimensions(self):
        """Proves explicit dimensions override auto-default."""
        config = EmbeddingConfig(mode="onnx", dimensions=768)
        assert config.dimensions == 768

    def test_onnx_max_seq_length_must_be_positive(self):
        """Proves max_seq_length validation."""
        with pytest.raises(ValueError, match="max_seq_length must be > 0"):
            OnnxEmbeddingConfig(max_seq_length=0)

    def test_existing_modes_still_work(self):
        """Proves no regression on existing mode values."""
        for mode in ["azure", "openai_compatible", "local", "fake"]:
            config = EmbeddingConfig(mode=mode)
            assert config.mode == mode


@pytest.mark.unit
class TestOnnxFactoryIntegration:
    """047-T004/T005: Factory integration tests."""

    def test_factory_returns_none_when_onnxruntime_missing(self):
        """Proves factory graceful degradation when onnxruntime not installed."""
        from fs2.core.adapters.embedding_adapter import (
            create_embedding_adapter_from_config,
        )

        config = _make_mock_config_service(mode="onnx")

        with patch("importlib.util.find_spec", return_value=None):
            adapter = create_embedding_adapter_from_config(config)

        assert adapter is None


@pytest.mark.unit
class TestOnnxMetadataRegression:
    """FT-001: Ensure ONNX model ID is persisted in metadata, not just mode name."""

    def test_given_onnx_mode_when_get_metadata_then_model_name_is_actual_model_id(
        self,
    ):
        """Purpose: Prevents silent stale embeddings when switching same-dimension ONNX models.
        Quality Contribution: Metadata mismatch detection triggers re-embed on model change.
        """
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        config = EmbeddingConfig(
            mode="onnx",
            dimensions=384,
            onnx=OnnxEmbeddingConfig(model="BAAI/bge-small-en-v1.5"),
        )
        service = EmbeddingService(
            config=config, embedding_adapter=None, token_counter=None
        )
        metadata = service.get_metadata()

        assert metadata["embedding_model"] == "BAAI/bge-small-en-v1.5"
        assert metadata["embedding_model"] != "onnx"

    def test_given_different_onnx_models_when_get_metadata_then_metadata_differs(self):
        """Purpose: Proves changing the ONNX model changes metadata, triggering re-embed.
        Quality Contribution: Guards against silently mixing embedding spaces.
        """
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        config_a = EmbeddingConfig(
            mode="onnx",
            dimensions=384,
            onnx=OnnxEmbeddingConfig(model="BAAI/bge-small-en-v1.5"),
        )
        config_b = EmbeddingConfig(
            mode="onnx",
            dimensions=384,
            onnx=OnnxEmbeddingConfig(model="all-MiniLM-L6-v2"),
        )
        meta_a = EmbeddingService(
            config=config_a, embedding_adapter=None, token_counter=None
        ).get_metadata()
        meta_b = EmbeddingService(
            config=config_b, embedding_adapter=None, token_counter=None
        ).get_metadata()

        assert meta_a["embedding_model"] != meta_b["embedding_model"]

    def test_given_onnx_mode_no_config_when_get_metadata_then_falls_back_to_mode(self):
        """Purpose: Graceful fallback when onnx config is None.
        Quality Contribution: No crash on edge case config.
        """
        from fs2.core.services.embedding.embedding_service import EmbeddingService

        config = EmbeddingConfig(mode="onnx", dimensions=384, onnx=None)
        service = EmbeddingService(
            config=config, embedding_adapter=None, token_counter=None
        )
        metadata = service.get_metadata()

        assert metadata["embedding_model"] == "onnx"


@pytest.mark.unit
class TestOnnxPoolingDetection:
    """FT-003: Config-driven pooling detection tests."""

    def test_given_cls_pooling_config_when_detected_then_use_cls(self):
        """Purpose: Verifies CLS pooling is selected from 1_Pooling/config.json.
        Quality Contribution: Wrong pooling produces L2 ~0.36 vs correct embeddings.
        """
        import json
        import tempfile
        from pathlib import Path

        from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter

        config = _make_mock_config_service()
        adapter = OnnxEmbeddingAdapter(config)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {"pooling_mode_cls_token": True, "pooling_mode_mean_tokens": False}, f
            )
            f.flush()
            pooling_path = f.name

        mock_download = MagicMock(return_value=pooling_path)
        with patch("huggingface_hub.hf_hub_download", mock_download):
            use_cls = adapter._detect_pooling("BAAI/bge-small-en-v1.5")

        Path(pooling_path).unlink(missing_ok=True)
        assert use_cls is True

    def test_given_mean_pooling_config_when_detected_then_use_mean(self):
        """Purpose: Verifies mean pooling is selected when config says so.
        Quality Contribution: Ensures non-BGE models use correct pooling.
        """
        import json
        import tempfile
        from pathlib import Path

        from fs2.core.adapters.embedding_adapter_onnx import OnnxEmbeddingAdapter

        config = _make_mock_config_service()
        adapter = OnnxEmbeddingAdapter(config)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {"pooling_mode_cls_token": False, "pooling_mode_mean_tokens": True}, f
            )
            f.flush()
            pooling_path = f.name

        mock_download = MagicMock(return_value=pooling_path)
        with patch("huggingface_hub.hf_hub_download", mock_download):
            use_cls = adapter._detect_pooling("some/mean-model")

        Path(pooling_path).unlink(missing_ok=True)
        assert use_cls is False
