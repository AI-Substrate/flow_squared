"""Tests for placeholder expansion.

ST011: Tests for expand_placeholders() function.

Behavior: ${VAR} is replaced with os.environ value; missing vars are left unexpanded.
Per Insight #5: Missing → leave unexpanded (consumer validates).
"""

import pytest


@pytest.mark.unit
class TestExpandPlaceholders:
    """Tests for expand_placeholders() function."""

    def test_given_placeholder_in_string_when_expanding_then_replaces_with_env_value(
        self, monkeypatch
    ):
        """
        Purpose: ${VAR} is replaced with env var value.
        Quality Contribution: Core expansion works.
        """
        # Arrange
        monkeypatch.setenv("MY_SECRET", "secret_value")
        config = {"api_key": "${MY_SECRET}"}

        # Act
        from fs2.config.loaders import expand_placeholders

        expand_placeholders(config)

        # Assert
        assert config["api_key"] == "secret_value"

    def test_given_missing_env_var_when_expanding_then_leaves_unexpanded(
        self, monkeypatch
    ):
        """
        Purpose: Missing env vars leave placeholder unexpanded.
        Quality Contribution: Consumer validates requirements.
        """
        # Arrange
        monkeypatch.delenv("MISSING_VAR", raising=False)
        config = {"api_key": "${MISSING_VAR}"}

        # Act
        from fs2.config.loaders import expand_placeholders

        expand_placeholders(config)

        # Assert: Left unexpanded
        assert config["api_key"] == "${MISSING_VAR}"

    def test_given_nested_dict_when_expanding_then_recursively_expands(
        self, monkeypatch
    ):
        """
        Purpose: Expansion works in nested dicts.
        Quality Contribution: Supports deep config structures.
        """
        # Arrange
        monkeypatch.setenv("AZURE_KEY", "azure_secret")
        config = {"azure": {"openai": {"api_key": "${AZURE_KEY}"}}}

        # Act
        from fs2.config.loaders import expand_placeholders

        expand_placeholders(config)

        # Assert
        assert config["azure"]["openai"]["api_key"] == "azure_secret"

    def test_given_non_string_values_when_expanding_then_leaves_unchanged(
        self, monkeypatch
    ):
        """
        Purpose: Non-string values (int, bool) are not affected.
        Quality Contribution: Type safety.
        """
        # Arrange
        config = {"timeout": 30, "enabled": True, "names": ["a", "b"]}

        # Act
        from fs2.config.loaders import expand_placeholders

        expand_placeholders(config)

        # Assert
        assert config["timeout"] == 30
        assert config["enabled"] is True
        assert config["names"] == ["a", "b"]

    def test_given_partial_placeholder_when_expanding_then_expands_in_string(
        self, monkeypatch
    ):
        """
        Purpose: Placeholders embedded in strings work.
        Quality Contribution: Supports URL templates.
        """
        # Arrange
        monkeypatch.setenv("HOST", "example.com")
        config = {"endpoint": "https://${HOST}/api/v1"}

        # Act
        from fs2.config.loaders import expand_placeholders

        expand_placeholders(config)

        # Assert
        assert config["endpoint"] == "https://example.com/api/v1"

    def test_given_multiple_placeholders_when_expanding_then_all_replaced(
        self, monkeypatch
    ):
        """
        Purpose: Multiple placeholders in one string work.
        Quality Contribution: Supports complex templates.
        """
        # Arrange
        monkeypatch.setenv("USER", "admin")
        monkeypatch.setenv("PASS", "secret")
        config = {"connection": "${USER}:${PASS}@localhost"}

        # Act
        from fs2.config.loaders import expand_placeholders

        expand_placeholders(config)

        # Assert
        assert config["connection"] == "admin:secret@localhost"
