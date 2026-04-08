"""Tests for CrossFileRelsConfig configuration model.

Validates the pydantic model for cross-file relationship extraction config,
including defaults, validation, and YAML_CONFIG_TYPES registry membership.
"""

from fs2.config.objects import YAML_CONFIG_TYPES, CrossFileRelsConfig


class TestCrossFileRelsConfigDefaults:
    """Test default values for CrossFileRelsConfig."""

    def test_enabled_defaults_to_true(self):
        config = CrossFileRelsConfig()
        assert config.enabled is True

    def test_only_enabled_field(self):
        """CrossFileRelsConfig should only have the 'enabled' field (Serena fields removed)."""
        CrossFileRelsConfig()  # validate it constructs
        field_names = set(CrossFileRelsConfig.model_fields.keys())
        assert field_names == {"enabled"}


class TestCrossFileRelsConfigPath:
    """Test __config_path__ for YAML/env loading."""

    def test_config_path_is_cross_file_rels(self):
        assert CrossFileRelsConfig.__config_path__ == "cross_file_rels"


class TestCrossFileRelsConfigRegistry:
    """Test YAML_CONFIG_TYPES registry membership."""

    def test_in_yaml_config_types(self):
        assert CrossFileRelsConfig in YAML_CONFIG_TYPES


class TestCrossFileRelsConfigCustomValues:
    """Test creating config with custom values."""

    def test_disabled(self):
        config = CrossFileRelsConfig(enabled=False)
        assert config.enabled is False
