"""Tests for TokenCounter adapter family.

T003: TokenCounterAdapter ABC + FakeTokenCounterAdapter contract tests.
Purpose: Establish the adapter interface and fake behavior for token counting.
"""

from __future__ import annotations

from abc import ABC

import pytest


@pytest.mark.unit
class TestTokenCounterAdapterContract:
    """T003: Tests for the TokenCounterAdapter ABC contract."""

    def test_given_token_counter_adapter_when_checked_then_is_abc(self):
        """
        Purpose: Proves TokenCounterAdapter is an ABC.
        Quality Contribution: Prevents accidental concrete implementations without contract.
        Acceptance Criteria: TokenCounterAdapter subclasses abc.ABC.

        Task: T003
        """
        from fs2.core.adapters.token_counter_adapter import TokenCounterAdapter

        assert issubclass(TokenCounterAdapter, ABC)

    def test_given_token_counter_adapter_when_instantiating_then_type_error(self):
        """
        Purpose: Proves TokenCounterAdapter cannot be instantiated (abstract).
        Quality Contribution: Enforces implementation completeness.
        Acceptance Criteria: Instantiation raises TypeError.

        Task: T003
        """
        from fs2.config.objects import LLMConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.token_counter_adapter import TokenCounterAdapter

        config = FakeConfigurationService(
            LLMConfig(provider="fake", model="gpt-4o-mini")
        )

        with pytest.raises(TypeError):
            TokenCounterAdapter(config)  # type: ignore[abstract]


@pytest.mark.unit
class TestFakeTokenCounterAdapter:
    """T003: Tests for FakeTokenCounterAdapter configurability + call history."""

    def test_given_fake_adapter_when_counting_then_records_call_history(self):
        """
        Purpose: Proves fake records calls for assertions (fakes over mocks).
        Quality Contribution: Enables deterministic behavioral tests in services.
        Acceptance Criteria: call_history captures inputs.

        Task: T003
        """
        from fs2.config.objects import LLMConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.token_counter_adapter_fake import (
            FakeTokenCounterAdapter,
        )

        config = FakeConfigurationService(
            LLMConfig(provider="fake", model="gpt-4o-mini")
        )
        counter = FakeTokenCounterAdapter(config)

        counter.count_tokens("hello world")

        assert counter.call_history == [
            {"method": "count_tokens", "args": {"text": "hello world"}}
        ]

    def test_given_no_configuration_when_counting_then_returns_default(self):
        """
        Purpose: Defines the fake's default behavior.
        Quality Contribution: Prevents accidental reliance on real tokenizer in tests.
        Acceptance Criteria: Default count is deterministic.

        Task: T003
        """
        from fs2.config.objects import LLMConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.token_counter_adapter_fake import (
            FakeTokenCounterAdapter,
        )

        config = FakeConfigurationService(
            LLMConfig(provider="fake", model="gpt-4o-mini")
        )
        counter = FakeTokenCounterAdapter(config)

        assert counter.count_tokens("any text") == 0

    def test_given_default_count_configured_when_counting_then_returns_configured_value(
        self,
    ):
        """
        Purpose: Proves fake can be configured to return a fixed token count.
        Quality Contribution: Enables precise truncation tests without tiktoken.
        Acceptance Criteria: set_default_count controls output.

        Task: T003
        """
        from fs2.config.objects import LLMConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.token_counter_adapter_fake import (
            FakeTokenCounterAdapter,
        )

        config = FakeConfigurationService(
            LLMConfig(provider="fake", model="gpt-4o-mini")
        )
        counter = FakeTokenCounterAdapter(config)

        counter.set_default_count(123)

        assert counter.count_tokens("any text") == 123

    def test_given_text_specific_count_when_counting_then_returns_specific_value(self):
        """
        Purpose: Proves fake supports per-text overrides.
        Quality Contribution: Enables edge-case tests (empty, unicode, large input).
        Acceptance Criteria: set_count_for_text overrides default count.

        Task: T003
        """
        from fs2.config.objects import LLMConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.token_counter_adapter_fake import (
            FakeTokenCounterAdapter,
        )

        config = FakeConfigurationService(
            LLMConfig(provider="fake", model="gpt-4o-mini")
        )
        counter = FakeTokenCounterAdapter(config)

        counter.set_default_count(10)
        counter.set_count_for_text("special", 999)

        assert counter.count_tokens("special") == 999
        assert counter.count_tokens("other") == 10


@pytest.mark.unit
class TestTokenCounterErrorTranslation:
    """T004: Tests for TokenCounterError existence and exception translation."""

    def test_given_adapter_exceptions_when_importing_then_token_counter_error_exists(
        self,
    ):
        """
        Purpose: Proves token counting failures have a domain exception at the adapter boundary.
        Quality Contribution: Prevents SDK/library exceptions from leaking into services.
        Acceptance Criteria: TokenCounterError is importable from adapters.exceptions.

        Task: T004
        """
        from fs2.core.adapters.exceptions import TokenCounterError

        assert issubclass(TokenCounterError, Exception)

    def test_given_tiktoken_failure_when_counting_then_raises_token_counter_error(
        self, monkeypatch
    ):
        """
        Purpose: Proves exception translation at adapter boundary for tiktoken failures.
        Quality Contribution: Ensures services catch only domain exceptions.
        Acceptance Criteria: Any underlying exception is translated to TokenCounterError.

        Task: T004
        """
        from fs2.config.objects import LLMConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.exceptions import TokenCounterError
        from fs2.core.adapters.token_counter_adapter_tiktoken import (
            TiktokenTokenCounterAdapter,
        )

        class FakeEncoder:
            def encode(self, _text: str) -> list[int]:
                raise RuntimeError("boom")

        class FakeTiktokenModule:
            @staticmethod
            def encoding_for_model(_model: str) -> FakeEncoder:
                return FakeEncoder()

            @staticmethod
            def get_encoding(_name: str) -> FakeEncoder:
                return FakeEncoder()

        # Prevent network calls in tests by replacing tiktoken with a fake module.
        monkeypatch.setitem(__import__("sys").modules, "tiktoken", FakeTiktokenModule)

        config = FakeConfigurationService(
            LLMConfig(provider="fake", model="gpt-4o-mini")
        )
        counter = TiktokenTokenCounterAdapter(config)

        with pytest.raises(TokenCounterError) as exc_info:
            counter.count_tokens("hello")

        assert "token" in str(exc_info.value).lower()

    def test_given_multiple_counts_when_used_then_encoder_is_cached(self, monkeypatch):
        """
        Purpose: Proves encoder is created once per adapter instance (cached).
        Quality Contribution: Prevents repeated expensive encoder creation.
        Acceptance Criteria: encoding_for_model called once during init.

        Task: T005
        """
        from fs2.config.objects import LLMConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.token_counter_adapter_tiktoken import (
            TiktokenTokenCounterAdapter,
        )

        calls = {"count": 0}

        class FakeEncoder:
            def encode(self, _text: str) -> list[int]:
                return [1, 2, 3]

        class FakeTiktokenModule:
            @staticmethod
            def encoding_for_model(_model: str) -> FakeEncoder:
                calls["count"] += 1
                return FakeEncoder()

        monkeypatch.setitem(__import__("sys").modules, "tiktoken", FakeTiktokenModule)

        config = FakeConfigurationService(
            LLMConfig(provider="fake", model="gpt-4o-mini")
        )
        counter = TiktokenTokenCounterAdapter(config)

        assert counter.count_tokens("a") == 3
        assert counter.count_tokens("b") == 3
        assert calls["count"] == 1
