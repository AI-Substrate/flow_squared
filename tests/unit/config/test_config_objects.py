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


@pytest.mark.unit
class TestSearchConfig:
    """Tests for SearchConfig - per plan-018."""

    def test_given_defaults_when_constructing_then_has_expected_values(self):
        """
        Purpose: Default values are sensible (AC06).
        Quality Contribution: Works out of the box with parent_penalty=0.25.
        """
        from fs2.config.objects import SearchConfig

        config = SearchConfig()

        assert config.default_limit == 20
        assert config.min_similarity == 0.25
        assert config.regex_timeout == 2.0
        assert config.parent_penalty == 0.25  # Per AC06: enabled by default

    def test_given_parent_penalty_when_constructing_then_accepts_valid_range(self):
        """
        Purpose: parent_penalty accepts values in [0.0, 1.0] range.
        Quality Contribution: Configuration flexibility (AC07, AC09).
        """
        from fs2.config.objects import SearchConfig

        # Minimum penalty (disabled per AC09)
        config_disabled = SearchConfig(parent_penalty=0.0)
        assert config_disabled.parent_penalty == 0.0

        # Maximum penalty
        config_max = SearchConfig(parent_penalty=1.0)
        assert config_max.parent_penalty == 1.0

        # Middle value
        config_mid = SearchConfig(parent_penalty=0.5)
        assert config_mid.parent_penalty == 0.5

    def test_given_parent_penalty_out_of_range_when_constructing_then_raises(self):
        """
        Purpose: parent_penalty rejects values outside [0.0, 1.0].
        Quality Contribution: Catches invalid configuration.
        """
        from fs2.config.objects import SearchConfig

        with pytest.raises(ValidationError) as exc_info:
            SearchConfig(parent_penalty=-0.1)
        assert "parent_penalty" in str(exc_info.value).lower()

        with pytest.raises(ValidationError) as exc_info:
            SearchConfig(parent_penalty=1.5)
        assert "parent_penalty" in str(exc_info.value).lower()

    def test_given_search_config_when_checking_path_then_returns_search(self):
        """
        Purpose: __config_path__ is "search" for env var prefix.
        Quality Contribution: Supports FS2_SEARCH__PARENT_PENALTY env var (AC08).
        """
        from fs2.config.objects import SearchConfig

        assert SearchConfig.__config_path__ == "search"

    def test_given_search_config_when_checking_registry_then_included(self):
        """
        Purpose: SearchConfig is in YAML_CONFIG_TYPES registry.
        Quality Contribution: Auto-loaded from YAML config files.
        """
        from fs2.config.objects import YAML_CONFIG_TYPES, SearchConfig

        assert SearchConfig in YAML_CONFIG_TYPES


@pytest.mark.unit
class TestSearchConfigEnvOverride:
    """Tests for SearchConfig environment variable override (AC08)."""

    def test_given_env_var_when_loading_then_overrides_parent_penalty(
        self, clean_config_env, monkeypatch, tmp_path
    ):
        """
        Purpose: FS2_SEARCH__PARENT_PENALTY env var overrides config (AC08).
        Quality Contribution: Environment configuration works.

        Per plan-018: Users can set FS2_SEARCH__PARENT_PENALTY=0.5 to override.
        """
        from fs2.config.objects import SearchConfig
        from fs2.config.service import FS2ConfigurationService

        # Set env var
        monkeypatch.setenv("FS2_SEARCH__PARENT_PENALTY", "0.5")

        # Change to temp dir to avoid loading real project config
        monkeypatch.chdir(tmp_path)

        # Create service - it should pick up env var when loading SearchConfig
        service = FS2ConfigurationService()

        search_config = service.require(SearchConfig)

        # Env var should override default
        assert search_config.parent_penalty == 0.5

    def test_given_no_env_var_when_loading_then_uses_default(
        self, clean_config_env, tmp_path, monkeypatch
    ):
        """
        Purpose: Without env var, default 0.25 is used.
        Quality Contribution: Default behavior works.
        """
        from fs2.config.objects import SearchConfig
        from fs2.config.service import FS2ConfigurationService

        # Create minimal .fs2/config.yaml to trigger SearchConfig creation
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("search:\n  default_limit: 20\n")

        # Change to temp dir
        monkeypatch.chdir(tmp_path)

        service = FS2ConfigurationService()

        search_config = service.require(SearchConfig)

        # Should use default for parent_penalty (not in YAML)
        assert search_config.parent_penalty == 0.25
