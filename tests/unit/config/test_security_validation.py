"""Tests for literal secret detection (sk-*, 64+ char rejection).

TDD Phase: RED - These tests should fail until T016 is implemented.

Tests cover:
- Literal secrets rejected (sk-* prefix, 64+ characters) per Insight #4
- Placeholders allowed in field validators per Finding 02
- Two-stage validation (field + model validator) per Insight #5
- Security validation only on api_key field per Insight #4
"""

import pytest


@pytest.mark.unit
def test_given_literal_sk_key_when_loading_then_raises_error():
    """
    Purpose: Proves sk-* prefix secrets are rejected in config
    Quality Contribution: Prevents secrets from being committed to config files
    Acceptance Criteria:
    - api_key: sk-1234567890 in config raises LiteralSecretError
    - Error message suggests using placeholder
    """
    # Arrange
    from fs2.config.exceptions import LiteralSecretError
    from fs2.config.models import FS2Settings

    # Act & Assert
    with pytest.raises(LiteralSecretError) as exc_info:
        FS2Settings(azure={"openai": {"api_key": "sk-1234567890abcdef"}})

    assert "placeholder" in str(exc_info.value).lower()
    assert "${" in str(exc_info.value)


@pytest.mark.unit
def test_given_long_literal_key_when_loading_then_raises_error():
    """
    Purpose: Proves long secrets (64+ chars) are rejected
    Quality Contribution: Catches API keys that are unusually long
    Acceptance Criteria:
    - api_key with 65+ characters raises LiteralSecretError
    """
    # Arrange
    from fs2.config.exceptions import LiteralSecretError
    from fs2.config.models import FS2Settings

    long_key = "a" * 65  # 65 characters

    # Act & Assert
    with pytest.raises(LiteralSecretError):
        FS2Settings(azure={"openai": {"api_key": long_key}})


@pytest.mark.unit
def test_given_placeholder_when_loading_then_allowed():
    """
    Purpose: Proves ${ENV_VAR} placeholders pass field validation
    Quality Contribution: Validates two-stage validation per Finding 02
    Acceptance Criteria:
    - api_key: ${MY_API_KEY} does NOT raise (placeholder allowed)
    - Expansion happens later in model_validator
    """
    # Arrange - note: placeholder will fail expansion if var not set
    # We're testing field validator allows placeholders through
    from fs2.config.models import FS2Settings

    # This should not raise at field validation stage
    # The model_validator will expand it (and fail if var not set)
    # For this test, set the env var to allow full creation
    import os

    os.environ["MY_API_KEY"] = "test-value"
    try:
        config = FS2Settings(azure={"openai": {"api_key": "${MY_API_KEY}"}})
        # If we get here, placeholder was allowed through field validator
        # and expanded by model validator
        assert config.azure.openai.api_key == "test-value"
    finally:
        del os.environ["MY_API_KEY"]


@pytest.mark.unit
def test_given_short_normal_key_when_loading_then_allowed():
    """
    Purpose: Proves short, non-sk keys are allowed
    Quality Contribution: Ensures we don't over-reject valid tokens
    Acceptance Criteria:
    - api_key: abc123 (short, no sk- prefix) is allowed
    """
    # Arrange
    from fs2.config.models import FS2Settings

    # Act - should not raise
    config = FS2Settings(azure={"openai": {"api_key": "abc123"}})

    # Assert
    assert config.azure.openai.api_key == "abc123"


@pytest.mark.unit
def test_given_64_char_key_when_loading_then_allowed():
    """
    Purpose: Proves exactly 64 char keys are allowed (boundary condition)
    Quality Contribution: Validates boundary condition
    Acceptance Criteria:
    - api_key with exactly 64 characters is allowed
    - Only 65+ triggers rejection
    """
    # Arrange
    from fs2.config.models import FS2Settings

    key_64_chars = "a" * 64  # Exactly 64 characters

    # Act - should not raise
    config = FS2Settings(azure={"openai": {"api_key": key_64_chars}})

    # Assert
    assert config.azure.openai.api_key == key_64_chars


@pytest.mark.unit
def test_given_long_endpoint_when_loading_then_allowed():
    """
    Purpose: Proves long strings in non-secret fields are allowed
    Quality Contribution: Per Insight #4 - 64+ char check is field-scoped
    Acceptance Criteria:
    - endpoint with 100+ characters is allowed (not a secret field)
    """
    # Arrange
    from fs2.config.models import FS2Settings

    long_endpoint = "https://" + "a" * 100 + ".openai.azure.com"

    # Act - should not raise (endpoint is not a secret field)
    config = FS2Settings(azure={"openai": {"endpoint": long_endpoint}})

    # Assert
    assert config.azure.openai.endpoint == long_endpoint


@pytest.mark.unit
def test_given_none_api_key_when_loading_then_allowed():
    """
    Purpose: Proves None/missing api_key is valid (optional field)
    Quality Contribution: Validates optional config pattern
    Acceptance Criteria:
    - api_key: null/None is allowed
    """
    # Arrange
    from fs2.config.models import FS2Settings

    # Act - should not raise
    config = FS2Settings(azure={"openai": {"api_key": None}})

    # Assert
    assert config.azure.openai.api_key is None
