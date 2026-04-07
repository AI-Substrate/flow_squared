"""SentenceTransformerEmbeddingAdapter implementation.

Local embedding generation using HuggingFace SentenceTransformer models.
No API keys required — runs entirely on-device (CPU, MPS, or CUDA).

Architecture:
- This file: Implementation only (ABC in embedding_adapter.py)
- External SDK (sentence_transformers) is lazy-imported in _get_model()
- torch is lazy-imported in _detect_device()

Per Critical Finding 05: Returns list[float], not numpy.
Per DYK-5: Logs download message before first model load.
"""

import asyncio
import logging
import platform
import threading
from typing import TYPE_CHECKING

from fs2.config.objects import EmbeddingConfig
from fs2.core.adapters.embedding_adapter import EmbeddingAdapter
from fs2.core.adapters.exceptions import EmbeddingAdapterError

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddingAdapter(EmbeddingAdapter):
    """Local embedding adapter using SentenceTransformer models.

    Provides embedding generation on-device with:
    - ConfigurationService DI pattern (same as Azure/OpenAI adapters)
    - Auto-detection of best device: CUDA > MPS > CPU
    - Lazy model loading (first call loads model)
    - Thread-pool execution for async compatibility
    - Thread-safe model loading with double-checked locking (046)

    Key differences from API adapters:
    - No retry logic needed (no network)
    - No rate limiting
    - Dimensions fixed by model (not configurable)
    - Sync model.encode() wrapped in run_in_executor()

    Example:
        >>> config_service = FS2ConfigurationService()
        >>> adapter = SentenceTransformerEmbeddingAdapter(config_service)
        >>> embedding = await adapter.embed_text("def add(a, b): return a + b")
        >>> len(embedding)  # 384 for BAAI/bge-small-en-v1.5
    """

    def __init__(self, config: "ConfigurationService") -> None:
        self._config_service = config
        self._embedding_config = config.require(EmbeddingConfig)

        if self._embedding_config.local is None:
            raise EmbeddingAdapterError(
                "Local config is required for mode='local'. "
                "Set embedding.local.model in .fs2/config.yaml."
            )

        self._local_config = self._embedding_config.local
        self._model = None  # Lazy loaded
        self._model_lock = threading.Lock()  # 046: Thread-safe model loading
        self._model_error: EmbeddingAdapterError | None = None  # 046: Stored load failure
        self._device: str | None = None

    @property
    def provider_name(self) -> str:
        """Return 'local' as the provider name."""
        return "local"

    def _detect_device(self) -> str:
        """Auto-detect best available device: CUDA > MPS > CPU."""
        import torch

        requested = self._local_config.device

        if requested != "auto":
            if requested == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA requested but not available, falling back to CPU")
                return "cpu"
            if requested == "mps" and not torch.backends.mps.is_available():
                logger.warning("MPS requested but not available, falling back to CPU")
                return "cpu"
            return requested

        if torch.cuda.is_available():
            logger.info(f"CUDA detected: {torch.cuda.get_device_name(0)}")
            return "cuda"
        if torch.backends.mps.is_available():
            logger.info("MPS detected (Apple Silicon)")
            return "mps"
        logger.info("Using CPU for embeddings")
        return "cpu"

    def _get_model(self):
        """Lazy-load the SentenceTransformer model (thread-safe).

        Uses double-checked locking (DYK#1) to avoid lock overhead
        on the hot path after the model is loaded.
        """
        # DYK#1: Fast path — no lock needed if model already loaded
        if self._model is not None:
            return self._model

        # DYK#5: Check for stored error from previous failed load
        if self._model_error is not None:
            raise self._model_error

        # DYK#3: Log waiting message for visibility during first-time download
        if self._model_lock.locked():
            logger.info(
                "Waiting for embedding model to load... "
                "(another thread is loading the model)"
            )

        with self._model_lock:
            # Double-check after acquiring lock
            if self._model is not None:
                return self._model
            if self._model_error is not None:
                raise self._model_error

            try:
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError:
                    raise EmbeddingAdapterError(
                        "sentence-transformers package is required for local embeddings. "
                        "Install it with: pip install fs2[local-embeddings]"
                    ) from None

                import warnings

                self._device = self._detect_device()

                # Suppress noisy warnings from HuggingFace
                _transformers_logger = logging.getLogger("transformers.modeling_utils")
                prev_level = _transformers_logger.level
                _transformers_logger.setLevel(logging.ERROR)
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message=".*position_ids.*")
                    try:
                        self._model = SentenceTransformer(
                            self._local_config.model,
                            device=self._device,
                            local_files_only=True,
                        )
                        logger.info(
                            f"Loaded embedding model: {self._local_config.model} "
                            f"on device: {self._device} (from cache)"
                        )
                    except OSError:
                        logger.info(
                            f"Downloading embedding model: {self._local_config.model} "
                            f"on device: {self._device} (first load may download ~130MB)"
                        )
                        self._model = SentenceTransformer(
                            self._local_config.model,
                            device=self._device,
                        )
                _transformers_logger.setLevel(prev_level)
                self._model.max_seq_length = self._local_config.max_seq_length

                actual_dim = self._model.get_sentence_embedding_dimension()
                if actual_dim != self._embedding_config.dimensions:
                    logger.warning(
                        f"Model dimension ({actual_dim}) differs from configured "
                        f"dimensions ({self._embedding_config.dimensions}). "
                        f"Using model dimension ({actual_dim})."
                    )

            except EmbeddingAdapterError:
                # Store adapter errors directly (e.g., missing package)
                self._model_error = EmbeddingAdapterError(
                    f"Embedding model failed to load. "
                    f"Restart `fs2 mcp` after resolving the issue. "
                    f"Original error: {self._model_error or 'see above'}"
                )
                raise
            except Exception as e:
                # DYK#5: Store error with actionable restart instruction
                self._model_error = EmbeddingAdapterError(
                    f"Embedding model failed to load: {e}. "
                    f"Restart `fs2 mcp` after resolving the issue."
                )
                raise self._model_error from e

        return self._model

    def warmup(self) -> None:
        """Pre-load the model in current thread. Safe for background use.

        Called at MCP startup via a daemon thread. Catches errors and
        stores them in _model_error for re-raise on first search call.
        """
        try:
            self._get_model()
        except EmbeddingAdapterError as e:
            logger.warning(f"Embedding model warmup failed: {e}")

    def _encode_sync(self, texts: list[str]) -> list[list[float]]:
        """Synchronous encoding — called via run_in_executor."""
        model = self._get_model()

        encode_kwargs: dict = {
            "batch_size": self._embedding_config.batch_size,
            "show_progress_bar": False,
            "normalize_embeddings": True,
            "convert_to_numpy": True,
            "device": self._device,
            "convert_to_tensor": False,
        }

        # Darwin MPS workaround (from FastCode CodeEmbedder)
        if platform.system() == "Darwin":
            encode_kwargs["pool"] = None

        embeddings = model.encode(texts, **encode_kwargs)

        # Convert numpy arrays to list[list[float]] per Critical Finding 05
        return [list(float(x) for x in emb) for emb in embeddings]

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text on-device."""
        result = await self.embed_batch([text])
        return result[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts on-device.

        Delegates to synchronous SentenceTransformer.encode() via
        run_in_executor to avoid blocking the event loop.
        """
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, self._encode_sync, texts)
        except EmbeddingAdapterError:
            raise
        except Exception as e:
            raise EmbeddingAdapterError(f"Local embedding failed: {e}") from e
