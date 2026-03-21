"""Tests for EmbeddingAdapter ABC.

Phase 2: Embedding Adapters - ABC interface compliance tests.
Purpose: Verify EmbeddingAdapter ABC defines correct interface contract.

Per Plan Task 2.1: Interface compliance tests for EmbeddingAdapter.
Per Critical Finding 05: Embeddings returned as list[float] (not numpy).
Per DYK-3: embed_batch takes array and makes single API call.
"""

import pytest


@pytest.mark.unit
class TestEmbeddingAdapterABC:
    """T002: Tests for EmbeddingAdapter ABC interface compliance."""

    def test_given_abc_when_instantiated_directly_then_raises_typeerror(self):
        """
        Purpose: Proves EmbeddingAdapter cannot be instantiated directly.
        Quality Contribution: Ensures ABC pattern is properly enforced.
        Acceptance Criteria: TypeError raised on direct instantiation.

        Task: T002
        """
        from fs2.core.adapters.embedding_adapter import EmbeddingAdapter

        # Arrange / Act / Assert
        with pytest.raises(TypeError, match="abstract"):
            EmbeddingAdapter()

    def test_given_implementation_missing_embed_text_when_instantiated_then_typeerror(
        self,
    ):
        """
        Purpose: Proves embed_text is required by ABC.
        Quality Contribution: Ensures implementations provide embed_text.
        Acceptance Criteria: TypeError if embed_text not implemented.

        Task: T002
        """
        from fs2.core.adapters.embedding_adapter import EmbeddingAdapter

        # Arrange
        class IncompleteAdapter(EmbeddingAdapter):
            @property
            def provider_name(self) -> str:
                return "incomplete"

            async def embed_batch(self, texts: list[str]) -> list[list[float]]:
                return [[0.1] * 1024 for _ in texts]

        # Act / Assert
        with pytest.raises(TypeError, match="abstract"):
            IncompleteAdapter()

    def test_given_implementation_missing_embed_batch_when_instantiated_then_typeerror(
        self,
    ):
        """
        Purpose: Proves embed_batch is required by ABC.
        Quality Contribution: Ensures implementations provide embed_batch.
        Acceptance Criteria: TypeError if embed_batch not implemented.

        Task: T002
        """
        from fs2.core.adapters.embedding_adapter import EmbeddingAdapter

        # Arrange
        class IncompleteAdapter(EmbeddingAdapter):
            @property
            def provider_name(self) -> str:
                return "incomplete"

            async def embed_text(self, text: str) -> list[float]:
                return [0.1] * 1024

        # Act / Assert
        with pytest.raises(TypeError, match="abstract"):
            IncompleteAdapter()

    def test_given_implementation_missing_provider_name_when_instantiated_then_typeerror(
        self,
    ):
        """
        Purpose: Proves provider_name is required by ABC.
        Quality Contribution: Ensures implementations identify themselves.
        Acceptance Criteria: TypeError if provider_name not implemented.

        Task: T002
        """
        from fs2.core.adapters.embedding_adapter import EmbeddingAdapter

        # Arrange
        class IncompleteAdapter(EmbeddingAdapter):
            async def embed_text(self, text: str) -> list[float]:
                return [0.1] * 1024

            async def embed_batch(self, texts: list[str]) -> list[list[float]]:
                return [[0.1] * 1024 for _ in texts]

        # Act / Assert
        with pytest.raises(TypeError, match="abstract"):
            IncompleteAdapter()

    def test_given_complete_implementation_when_instantiated_then_succeeds(self):
        """
        Purpose: Proves complete implementations can be instantiated.
        Quality Contribution: Validates ABC pattern allows proper subclasses.
        Acceptance Criteria: Complete implementation instantiates without error.

        Task: T002
        """
        from fs2.core.adapters.embedding_adapter import EmbeddingAdapter

        # Arrange
        class CompleteAdapter(EmbeddingAdapter):
            @property
            def provider_name(self) -> str:
                return "test"

            async def embed_text(self, text: str) -> list[float]:
                return [0.1] * 1024

            async def embed_batch(self, texts: list[str]) -> list[list[float]]:
                return [[0.1] * 1024 for _ in texts]

        # Act
        adapter = CompleteAdapter()

        # Assert
        assert adapter.provider_name == "test"


@pytest.mark.unit
class TestEmbeddingAdapterMethodSignatures:
    """T002: Tests for EmbeddingAdapter method signatures."""

    def test_given_embed_text_when_inspected_then_returns_list_float(self):
        """
        Purpose: Per Finding 05: Proves embed_text returns list[float].
        Quality Contribution: Ensures pickle-safe return type.
        Acceptance Criteria: Return type annotation is list[float].

        Task: T002
        """
        import inspect

        from fs2.core.adapters.embedding_adapter import EmbeddingAdapter

        # Arrange / Act
        sig = inspect.signature(EmbeddingAdapter.embed_text)

        # Assert
        assert sig.return_annotation == list[float]

    def test_given_embed_batch_when_inspected_then_returns_list_of_list_float(self):
        """
        Purpose: Per Finding 05: Proves embed_batch returns list[list[float]].
        Quality Contribution: Ensures pickle-safe return type.
        Acceptance Criteria: Return type annotation is list[list[float]].

        Task: T002
        """
        import inspect

        from fs2.core.adapters.embedding_adapter import EmbeddingAdapter

        # Arrange / Act
        sig = inspect.signature(EmbeddingAdapter.embed_batch)

        # Assert
        assert sig.return_annotation == list[list[float]]

    def test_given_embed_text_when_inspected_then_accepts_str(self):
        """
        Purpose: Proves embed_text accepts a single text string.
        Quality Contribution: Documents expected input type.
        Acceptance Criteria: Parameter 'text' is str.

        Task: T002
        """
        import inspect

        from fs2.core.adapters.embedding_adapter import EmbeddingAdapter

        # Arrange / Act
        sig = inspect.signature(EmbeddingAdapter.embed_text)
        params = list(sig.parameters.values())

        # Assert
        text_param = params[1]  # [0] is self
        assert text_param.name == "text"
        assert text_param.annotation is str

    def test_given_embed_batch_when_inspected_then_accepts_list_str(self):
        """
        Purpose: Proves embed_batch accepts a list of strings.
        Quality Contribution: Documents expected input type.
        Acceptance Criteria: Parameter 'texts' is list[str].

        Task: T002
        """
        import inspect

        from fs2.core.adapters.embedding_adapter import EmbeddingAdapter

        # Arrange / Act
        sig = inspect.signature(EmbeddingAdapter.embed_batch)
        params = list(sig.parameters.values())

        # Assert
        texts_param = params[1]  # [0] is self
        assert texts_param.name == "texts"
        assert texts_param.annotation == list[str]


@pytest.mark.unit
class TestEmbeddingAdapterAsyncMethods:
    """T002: Tests for EmbeddingAdapter async method signatures."""

    def test_given_embed_text_when_inspected_then_is_coroutine(self):
        """
        Purpose: Proves embed_text is async for I/O-bound operations.
        Quality Contribution: Ensures non-blocking API calls.
        Acceptance Criteria: embed_text is a coroutine function.

        Task: T002
        """
        import inspect

        from fs2.core.adapters.embedding_adapter import EmbeddingAdapter

        # Arrange / Act / Assert
        assert inspect.iscoroutinefunction(EmbeddingAdapter.embed_text)

    def test_given_embed_batch_when_inspected_then_is_coroutine(self):
        """
        Purpose: Proves embed_batch is async for I/O-bound operations.
        Quality Contribution: Ensures non-blocking API calls.
        Acceptance Criteria: embed_batch is a coroutine function.

        Task: T002
        """
        import inspect

        from fs2.core.adapters.embedding_adapter import EmbeddingAdapter

        # Arrange / Act / Assert
        assert inspect.iscoroutinefunction(EmbeddingAdapter.embed_batch)


@pytest.mark.unit
class TestEmbeddingAdapterFactoryLocal:
    """032-T006: Tests for create_embedding_adapter_from_config with mode=local."""

    def test_given_mode_local_with_deps_when_creating_then_returns_local_adapter(self):
        """
        Purpose: Proves factory returns SentenceTransformerEmbeddingAdapter.
        Acceptance Criteria: Correct adapter type returned.

        Task: 032-T006 (DYK-1: probes importability)
        """
        from unittest.mock import MagicMock, patch

        from fs2.config.objects import EmbeddingConfig, LocalEmbeddingConfig
        from fs2.core.adapters.embedding_adapter import (
            create_embedding_adapter_from_config,
        )
        from fs2.core.adapters.embedding_adapter_local import (
            SentenceTransformerEmbeddingAdapter,
        )

        mock_config = MagicMock()
        mock_config.require.return_value = EmbeddingConfig(
            mode="local",
            local=LocalEmbeddingConfig(),
        )

        # Mock sentence_transformers as importable via find_spec
        mock_st = MagicMock()
        with patch.dict("sys.modules", {"sentence_transformers": mock_st}), \
             patch("importlib.util.find_spec", return_value=MagicMock()):
            adapter = create_embedding_adapter_from_config(mock_config)

        assert isinstance(adapter, SentenceTransformerEmbeddingAdapter)

    def test_given_mode_local_no_local_section_when_creating_then_uses_defaults(self):
        """
        Purpose: Proves factory creates default LocalEmbeddingConfig when missing.
        Acceptance Criteria: Adapter created with default config.

        Task: 032-T006
        """
        from unittest.mock import MagicMock, patch

        from fs2.config.objects import EmbeddingConfig
        from fs2.core.adapters.embedding_adapter import (
            create_embedding_adapter_from_config,
        )
        from fs2.core.adapters.embedding_adapter_local import (
            SentenceTransformerEmbeddingAdapter,
        )

        mock_config = MagicMock()
        mock_config.require.return_value = EmbeddingConfig(
            mode="local",
            local=None,
        )

        mock_st = MagicMock()
        with patch.dict("sys.modules", {"sentence_transformers": mock_st}), \
             patch("importlib.util.find_spec", return_value=MagicMock()):
            adapter = create_embedding_adapter_from_config(mock_config)

        assert isinstance(adapter, SentenceTransformerEmbeddingAdapter)

    def test_given_mode_local_no_deps_when_creating_then_returns_none(self):
        """
        Purpose: DYK-1 — Proves factory returns None when sentence-transformers missing.
        Quality Contribution: Graceful degradation for search fallback.
        Acceptance Criteria: Returns None, not a broken adapter.

        Task: 032-T006 (DYK-1)
        """
        from unittest.mock import MagicMock, patch

        from fs2.config.objects import EmbeddingConfig, LocalEmbeddingConfig
        from fs2.core.adapters.embedding_adapter import (
            create_embedding_adapter_from_config,
        )

        mock_config = MagicMock()
        mock_config.require.return_value = EmbeddingConfig(
            mode="local",
            local=LocalEmbeddingConfig(),
        )

        # Simulate sentence_transformers not installed
        with patch("importlib.util.find_spec", return_value=None):
            adapter = create_embedding_adapter_from_config(mock_config)

        assert adapter is None
