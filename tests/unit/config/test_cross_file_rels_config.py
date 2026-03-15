"""Tests for CrossFileRelsConfig configuration model.

Validates the pydantic model for cross-file relationship extraction config,
including defaults, validation, and YAML_CONFIG_TYPES registry membership.
"""

import pytest
from pydantic import ValidationError

from fs2.config.objects import CrossFileRelsConfig, YAML_CONFIG_TYPES


class TestCrossFileRelsConfigDefaults:
    """Test default values for CrossFileRelsConfig."""

    def test_enabled_defaults_to_true(self):
        config = CrossFileRelsConfig()
        assert config.enabled is True

    def test_parallel_instances_defaults_to_15(self):
        config = CrossFileRelsConfig()
        assert config.parallel_instances == 15

    def test_serena_base_port_defaults_to_8330(self):
        config = CrossFileRelsConfig()
        assert config.serena_base_port == 8330

    def test_timeout_per_node_defaults_to_5(self):
        config = CrossFileRelsConfig()
        assert config.timeout_per_node == 5.0

    def test_languages_defaults_to_python(self):
        config = CrossFileRelsConfig()
        assert config.languages == ["python"]


class TestCrossFileRelsConfigValidation:
    """Test field validation rules."""

    def test_parallel_instances_rejects_zero(self):
        with pytest.raises(ValidationError, match="parallel_instances"):
            CrossFileRelsConfig(parallel_instances=0)

    def test_parallel_instances_rejects_negative(self):
        with pytest.raises(ValidationError, match="parallel_instances"):
            CrossFileRelsConfig(parallel_instances=-1)

    def test_parallel_instances_rejects_over_50(self):
        with pytest.raises(ValidationError, match="parallel_instances"):
            CrossFileRelsConfig(parallel_instances=51)

    def test_parallel_instances_accepts_1(self):
        config = CrossFileRelsConfig(parallel_instances=1)
        assert config.parallel_instances == 1

    def test_parallel_instances_accepts_50(self):
        config = CrossFileRelsConfig(parallel_instances=50)
        assert config.parallel_instances == 50

    def test_timeout_per_node_rejects_zero(self):
        with pytest.raises(ValidationError, match="timeout_per_node"):
            CrossFileRelsConfig(timeout_per_node=0.0)

    def test_timeout_per_node_rejects_negative(self):
        with pytest.raises(ValidationError, match="timeout_per_node"):
            CrossFileRelsConfig(timeout_per_node=-1.0)

    def test_timeout_per_node_accepts_small_positive(self):
        config = CrossFileRelsConfig(timeout_per_node=0.5)
        assert config.timeout_per_node == 0.5


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

    def test_all_custom_values(self):
        config = CrossFileRelsConfig(
            enabled=False,
            parallel_instances=5,
            serena_base_port=9000,
            timeout_per_node=10.0,
            languages=["python", "typescript"],
        )
        assert config.enabled is False
        assert config.parallel_instances == 5
        assert config.serena_base_port == 9000
        assert config.timeout_per_node == 10.0
        assert config.languages == ["python", "typescript"]
