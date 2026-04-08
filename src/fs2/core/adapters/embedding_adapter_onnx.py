"""OnnxEmbeddingAdapter implementation.

ONNX Runtime embedding generation using HuggingFace models with ONNX exports.
No PyTorch required — imports in ~0.68s vs 93s for sentence-transformers on Windows.

Architecture:
- This file: Implementation only (ABC in embedding_adapter.py)
- External SDK (onnxruntime) is lazy-imported in _get_session()
- tokenizers lib used directly (not transformers, which imports torch)
- Pooling strategy auto-detected from model's 1_Pooling/config.json

Per 047 Workshop: Produces numerically identical embeddings to sentence-transformers
(L2 < 1e-6 verified experimentally).
Per Critical Finding 05: Returns list[float], not numpy.
"""

import asyncio
import json
import logging
import threading
from typing import TYPE_CHECKING

import numpy as np

from fs2.config.objects import EmbeddingConfig
from fs2.core.adapters.embedding_adapter import EmbeddingAdapter
from fs2.core.adapters.exceptions import EmbeddingAdapterError

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService

logger = logging.getLogger(__name__)


class OnnxEmbeddingAdapter(EmbeddingAdapter):
    """ONNX Runtime embedding adapter for HuggingFace models.

    Provides embedding generation on-device using ONNX Runtime:
    - No PyTorch dependency — imports in ~0.68s on Windows
    - Numerically identical to sentence-transformers (L2 < 1e-6)
    - Auto-detects pooling strategy (CLS vs mean) from model config
    - Thread-safe lazy session loading with double-checked locking
    - Offline-first model download via HuggingFace Hub cache

    Example:
        >>> config_service = FS2ConfigurationService()
        >>> adapter = OnnxEmbeddingAdapter(config_service)
        >>> embedding = await adapter.embed_text("def add(a, b): return a + b")
        >>> len(embedding)  # 384 for BAAI/bge-small-en-v1.5
    """

    def __init__(self, config: "ConfigurationService") -> None:
        self._config_service = config
        self._embedding_config = config.require(EmbeddingConfig)

        if self._embedding_config.onnx is None:
            raise EmbeddingAdapterError(
                "ONNX config is required for mode='onnx'. "
                "Set embedding.onnx.model in .fs2/config.yaml."
            )

        self._onnx_config = self._embedding_config.onnx
        self._session = None  # Lazy loaded
        self._tokenizer = None  # Lazy loaded
        self._use_cls_pooling: bool = True  # Default for BGE models
        self._session_lock = threading.Lock()
        self._session_error: EmbeddingAdapterError | None = None

    @property
    def provider_name(self) -> str:
        """Return 'onnx' as the provider name."""
        return "onnx"

    def _detect_pooling(self, model_name: str) -> bool:
        """Detect pooling strategy from model's 1_Pooling/config.json.

        Returns True for CLS pooling, False for mean pooling.
        Falls back to CLS if config not found (most common for BGE models).
        """
        try:
            from huggingface_hub import hf_hub_download

            pooling_path = hf_hub_download(
                model_name, "1_Pooling/config.json", local_files_only=True
            )
            with open(pooling_path, encoding="utf-8") as f:
                pooling_config = json.load(f)

            if pooling_config.get("pooling_mode_cls_token", False):
                return True
            return not pooling_config.get("pooling_mode_mean_tokens", False)
        except Exception:
            # Config not cached — try with download
            try:
                from huggingface_hub import hf_hub_download

                pooling_path = hf_hub_download(model_name, "1_Pooling/config.json")
                with open(pooling_path, encoding="utf-8") as f:
                    pooling_config = json.load(f)

                if pooling_config.get("pooling_mode_cls_token", False):
                    return True
                return not pooling_config.get("pooling_mode_mean_tokens", False)
            except Exception:
                logger.debug(
                    f"Could not load pooling config for {model_name}, defaulting to CLS"
                )
                return True  # Default to CLS for BGE models

    def _get_session(self):
        """Lazy-load the ONNX session and tokenizer (thread-safe).

        Uses double-checked locking to avoid lock overhead on hot path.
        """
        # Fast path — no lock needed if session already loaded
        if self._session is not None:
            return self._session, self._tokenizer

        # Check for stored error from previous failed load
        if self._session_error is not None:
            raise self._session_error

        # Log waiting message for visibility
        if self._session_lock.locked():
            logger.info(
                "Waiting for ONNX session to load... "
                "(another thread is loading the model)"
            )

        with self._session_lock:
            # Double-check after acquiring lock
            if self._session is not None:
                return self._session, self._tokenizer
            if self._session_error is not None:
                raise self._session_error

            try:
                try:
                    from onnxruntime import InferenceSession
                except ImportError:
                    raise EmbeddingAdapterError(
                        "onnxruntime package is required for ONNX embeddings. "
                        "Install it with: pip install fs2[onnx-embeddings]"
                    ) from None

                try:
                    from tokenizers import Tokenizer
                except ImportError:
                    raise EmbeddingAdapterError(
                        "tokenizers package is required for ONNX embeddings. "
                        "Install it with: pip install tokenizers"
                    ) from None

                from huggingface_hub import hf_hub_download

                model_name = self._onnx_config.model

                # Download ONNX model — offline first
                try:
                    onnx_path = hf_hub_download(
                        model_name, "onnx/model.onnx", local_files_only=True
                    )
                    logger.info(
                        f"Loaded ONNX model: {model_name} (from cache)"
                    )
                except Exception:
                    try:
                        logger.info(
                            f"Downloading ONNX model: {model_name} "
                            f"(first load may download ~130MB)"
                        )
                        onnx_path = hf_hub_download(model_name, "onnx/model.onnx")
                    except Exception as dl_err:
                        raise EmbeddingAdapterError(
                            f"Could not find ONNX export for model '{model_name}'. "
                            f"Ensure the model has an 'onnx/model.onnx' file on HuggingFace Hub. "
                            f"Alternatively, use mode: 'local' for PyTorch inference. "
                            f"Error: {dl_err}"
                        ) from dl_err

                # Download tokenizer
                try:
                    tok_path = hf_hub_download(
                        model_name, "tokenizer.json", local_files_only=True
                    )
                except Exception:
                    tok_path = hf_hub_download(model_name, "tokenizer.json")

                # Load tokenizer
                self._tokenizer = Tokenizer.from_file(tok_path)
                self._tokenizer.enable_truncation(
                    max_length=self._onnx_config.max_seq_length
                )
                self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")

                # Create ONNX session
                self._session = InferenceSession(
                    onnx_path, providers=[self._onnx_config.provider]
                )

                # Detect pooling strategy
                self._use_cls_pooling = self._detect_pooling(model_name)
                pooling_name = "CLS" if self._use_cls_pooling else "mean"
                logger.info(f"ONNX pooling strategy: {pooling_name}")

                # Check output dimensions
                output_shape = self._session.get_outputs()[0].shape
                if len(output_shape) >= 3:
                    actual_dim = output_shape[-1]
                    if (
                        isinstance(actual_dim, int)
                        and actual_dim != self._embedding_config.dimensions
                    ):
                        logger.warning(
                            f"Model dimension ({actual_dim}) differs from configured "
                            f"dimensions ({self._embedding_config.dimensions}). "
                            f"Using model dimension ({actual_dim})."
                        )

            except EmbeddingAdapterError:
                self._session_error = EmbeddingAdapterError(
                    "ONNX session failed to load. "
                    "Restart `fs2 mcp` after resolving the issue."
                )
                raise
            except Exception as e:
                self._session_error = EmbeddingAdapterError(
                    f"ONNX session failed to load: {e}. "
                    f"Restart `fs2 mcp` after resolving the issue."
                )
                raise self._session_error from e

        return self._session, self._tokenizer

    def _encode_sync(self, texts: list[str]) -> list[list[float]]:
        """Synchronous encoding — called via run_in_executor."""
        session, tokenizer = self._get_session()

        # Tokenize
        encoded_batch = tokenizer.encode_batch(texts)
        input_ids = np.array([e.ids for e in encoded_batch], dtype=np.int64)
        attention_mask = np.array(
            [e.attention_mask for e in encoded_batch], dtype=np.int64
        )
        token_type_ids = np.zeros_like(input_ids, dtype=np.int64)

        # Build input feed — only pass what the model expects
        model_input_names = [inp.name for inp in session.get_inputs()]
        input_feed: dict = {}
        if "input_ids" in model_input_names:
            input_feed["input_ids"] = input_ids
        if "attention_mask" in model_input_names:
            input_feed["attention_mask"] = attention_mask
        if "token_type_ids" in model_input_names:
            input_feed["token_type_ids"] = token_type_ids

        # Run inference
        outputs = session.run(None, input_feed)
        last_hidden = outputs[0]  # (batch, seq_len, hidden_dim)

        # Apply pooling
        if self._use_cls_pooling:
            embeddings = last_hidden[:, 0, :]  # CLS token
        else:
            # Mean pooling weighted by attention mask
            mask_expanded = np.expand_dims(attention_mask, -1).astype(np.float32)
            sum_embeddings = np.sum(last_hidden * mask_expanded, axis=1)
            sum_mask = np.maximum(np.sum(mask_expanded, axis=1), 1e-9)
            embeddings = sum_embeddings / sum_mask

        # L2 normalize
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / norms

        # Convert numpy arrays to list[list[float]] per Critical Finding 05
        return [list(float(x) for x in emb) for emb in embeddings]

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text using ONNX Runtime."""
        result = await self.embed_batch([text])
        return result[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts using ONNX Runtime.

        Delegates to synchronous ONNX session.run() via
        run_in_executor to avoid blocking the event loop.
        """
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, self._encode_sync, texts)
        except EmbeddingAdapterError:
            raise
        except Exception as e:
            raise EmbeddingAdapterError(f"ONNX embedding failed: {e}") from e

    def warmup(self) -> None:
        """Pre-load the ONNX session and tokenizer. Safe for background use.

        Called at MCP startup via a daemon thread per 046.
        Catches errors and stores them for re-raise on first search call.
        """
        try:
            self._get_session()
        except EmbeddingAdapterError as e:
            logger.warning(f"ONNX embedding warmup failed: {e}")
