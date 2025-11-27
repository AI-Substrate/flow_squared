"""Tests for FS2_* environment variable parsing.

ST007: Tests for parse_env_vars() function.

Convention: FS2_X__Y__Z → x.y.z (double underscore = nesting, lowercase)
"""

import pytest


@pytest.mark.unit
class TestParseEnvVars:
    """Tests for parse_env_vars() function."""

    def test_given_simple_fs2_var_when_parsing_then_returns_nested_dict(
        self, monkeypatch
    ):
        """
        Purpose: FS2_X__Y__Z becomes {"x": {"y": {"z": "value"}}}.
        Quality Contribution: Core convention works.
        """
        # Arrange
        monkeypatch.setenv("FS2_AZURE__OPENAI__TIMEOUT", "120")

        # Act
        from fs2.config.loaders import parse_env_vars

        result = parse_env_vars()

        # Assert
        assert result == {"azure": {"openai": {"timeout": "120"}}}

    def test_given_multiple_fs2_vars_when_parsing_then_merges_into_dict(
        self, monkeypatch
    ):
        """
        Purpose: Multiple FS2_* vars are merged into single dict.
        Quality Contribution: Supports complex config via env vars.
        """
        # Arrange
        monkeypatch.setenv("FS2_AZURE__OPENAI__TIMEOUT", "120")
        monkeypatch.setenv("FS2_AZURE__OPENAI__ENDPOINT", "https://example.com")
        monkeypatch.setenv("FS2_LOGGING__LEVEL", "DEBUG")

        # Act
        from fs2.config.loaders import parse_env_vars

        result = parse_env_vars()

        # Assert
        assert result["azure"]["openai"]["timeout"] == "120"
        assert result["azure"]["openai"]["endpoint"] == "https://example.com"
        assert result["logging"]["level"] == "DEBUG"

    def test_given_uppercase_var_when_parsing_then_keys_are_lowercase(
        self, monkeypatch
    ):
        """
        Purpose: Env var keys are converted to lowercase.
        Quality Contribution: Convention compliance.
        """
        # Arrange
        monkeypatch.setenv("FS2_AZURE__OPENAI__API_VERSION", "2024-02-01")

        # Act
        from fs2.config.loaders import parse_env_vars

        result = parse_env_vars()

        # Assert: Keys are lowercase
        assert "azure" in result
        assert "openai" in result["azure"]
        assert "api_version" in result["azure"]["openai"]

    def test_given_no_fs2_vars_when_parsing_then_returns_empty_dict(
        self, monkeypatch
    ):
        """
        Purpose: No FS2_* vars returns empty dict.
        Quality Contribution: Handles no-config case.
        """
        # Arrange: Clear any FS2_ vars that might exist
        import os

        for key in list(os.environ.keys()):
            if key.startswith("FS2_"):
                monkeypatch.delenv(key, raising=False)

        # Act
        from fs2.config.loaders import parse_env_vars

        result = parse_env_vars()

        # Assert
        assert result == {}

    def test_given_single_level_var_when_parsing_then_returns_flat_dict(
        self, monkeypatch
    ):
        """
        Purpose: FS2_KEY (no nesting) becomes {"key": "value"}.
        Quality Contribution: Supports simple top-level config.
        """
        # Arrange
        monkeypatch.setenv("FS2_DEBUG", "true")

        # Act
        from fs2.config.loaders import parse_env_vars

        result = parse_env_vars()

        # Assert
        assert result["debug"] == "true"

    def test_given_non_fs2_vars_when_parsing_then_ignores_them(
        self, monkeypatch
    ):
        """
        Purpose: Non-FS2_* vars are ignored.
        Quality Contribution: Only processes our config vars.
        """
        # Arrange
        monkeypatch.setenv("OTHER_VAR", "should_be_ignored")
        monkeypatch.setenv("FS2_AZURE__TIMEOUT", "30")

        # Act
        from fs2.config.loaders import parse_env_vars

        result = parse_env_vars()

        # Assert
        assert "other_var" not in result
        assert "OTHER_VAR" not in result
        assert result["azure"]["timeout"] == "30"
