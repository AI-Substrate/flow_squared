"""Tests for typed config objects.

ST013-ST018: Tests for AzureOpenAIConfig, SearchQueryConfig, and config type registry.
"""

import pytest
from pydantic import ValidationError


@pytest.mark.unit
class TestAzureOpenAIConfig:
    """Tests for AzureOpenAIConfig."""

    def test_given_valid_config_when_constructing_then_succeeds(self):
        """
        Purpose: Valid config constructs successfully.
        Quality Contribution: Basic construction works.
        """
        # Act
        from fs2.config.objects import AzureOpenAIConfig

        config = AzureOpenAIConfig(
            endpoint="https://example.openai.azure.com",
            api_key="test-key",
            timeout=60,
        )

        # Assert
        assert config.endpoint == "https://example.openai.azure.com"
        assert config.api_key == "test-key"
        assert config.timeout == 60

    def test_given_azure_config_when_checking_path_then_returns_azure_openai(self):
        """
        Purpose: __config_path__ is "azure.openai".
        Quality Contribution: Auto-load from correct YAML path.
        """
        # Act
        from fs2.config.objects import AzureOpenAIConfig

        # Assert
        assert AzureOpenAIConfig.__config_path__ == "azure.openai"

    def test_given_defaults_when_constructing_then_has_expected_values(self):
        """
        Purpose: Default values are sensible.
        Quality Contribution: Works out of the box.
        """
        # Act
        from fs2.config.objects import AzureOpenAIConfig

        config = AzureOpenAIConfig()

        # Assert
        assert config.endpoint is None
        assert config.api_key is None
        assert config.api_version == "2024-02-01"
        assert config.deployment_name is None
        assert config.timeout == 30

    def test_given_timeout_too_high_when_constructing_then_validation_error(self):
        """
        Purpose: Timeout > 300 is rejected.
        Quality Contribution: Catches unreasonable timeouts.
        """
        # Act & Assert
        from fs2.config.objects import AzureOpenAIConfig

        with pytest.raises(ValidationError) as exc_info:
            AzureOpenAIConfig(timeout=500)

        # Check error message is actionable
        assert "timeout" in str(exc_info.value).lower()

    def test_given_timeout_too_low_when_constructing_then_validation_error(self):
        """
        Purpose: Timeout < 1 is rejected.
        Quality Contribution: Catches invalid timeouts.
        """
        # Act & Assert
        from fs2.config.objects import AzureOpenAIConfig

        with pytest.raises(ValidationError) as exc_info:
            AzureOpenAIConfig(timeout=0)

        assert "timeout" in str(exc_info.value).lower()


@pytest.mark.unit
class TestSearchQueryConfig:
    """Tests for SearchQueryConfig."""

    def test_given_valid_config_when_constructing_then_succeeds(self):
        """
        Purpose: Valid config constructs successfully.
        Quality Contribution: Basic construction works.
        """
        # Act
        from fs2.config.objects import SearchQueryConfig

        config = SearchQueryConfig(mode="slim", text="authentication")

        # Assert
        assert config.mode == "slim"
        assert config.text == "authentication"

    def test_given_search_config_when_checking_path_then_returns_none(self):
        """
        Purpose: __config_path__ is None (CLI-only, not from YAML).
        Quality Contribution: CLI configs don't auto-load from files.
        """
        # Act
        from fs2.config.objects import SearchQueryConfig

        # Assert
        assert SearchQueryConfig.__config_path__ is None

    def test_given_defaults_when_constructing_then_has_expected_values(self):
        """
        Purpose: Default values are sensible.
        Quality Contribution: Works with minimal input.
        """
        # Act
        from fs2.config.objects import SearchQueryConfig

        config = SearchQueryConfig()

        # Assert
        assert config.mode == "normal"
        assert config.text is None
        assert config.limit == 10

    def test_given_invalid_mode_when_constructing_then_validation_error(self):
        """
        Purpose: Invalid mode is rejected.
        Quality Contribution: Catches typos in mode.
        """
        # Act & Assert
        from fs2.config.objects import SearchQueryConfig

        with pytest.raises(ValidationError) as exc_info:
            SearchQueryConfig(mode="invalid_mode")

        # Check error message mentions valid modes
        error_str = str(exc_info.value).lower()
        assert "mode" in error_str

    def test_given_valid_modes_when_constructing_then_all_succeed(self):
        """
        Purpose: All valid modes work.
        Quality Contribution: Documents valid modes.
        """
        # Act & Assert
        from fs2.config.objects import SearchQueryConfig

        for mode in ("slim", "normal", "detailed"):
            config = SearchQueryConfig(mode=mode)
            assert config.mode == mode


@pytest.mark.unit
class TestConfigTypeRegistry:
    """Tests for YAML_CONFIG_TYPES registry."""

    def test_given_registry_when_checking_then_contains_azure_config(self):
        """
        Purpose: AzureOpenAIConfig is in registry.
        Quality Contribution: Auto-loaded from YAML.
        """
        # Act
        from fs2.config.objects import YAML_CONFIG_TYPES, AzureOpenAIConfig

        # Assert
        assert AzureOpenAIConfig in YAML_CONFIG_TYPES

    def test_given_registry_when_checking_then_excludes_cli_only_configs(self):
        """
        Purpose: CLI-only configs not in registry.
        Quality Contribution: SearchQueryConfig not auto-loaded.
        """
        # Act
        from fs2.config.objects import YAML_CONFIG_TYPES, SearchQueryConfig

        # Assert
        assert SearchQueryConfig not in YAML_CONFIG_TYPES

    def test_given_registry_types_when_checking_then_all_have_config_path(self):
        """
        Purpose: All registry types have __config_path__.
        Quality Contribution: Ensures auto-load works.
        """
        # Act
        from fs2.config.objects import YAML_CONFIG_TYPES

        # Assert
        for config_type in YAML_CONFIG_TYPES:
            assert hasattr(config_type, "__config_path__")
            assert config_type.__config_path__ is not None
