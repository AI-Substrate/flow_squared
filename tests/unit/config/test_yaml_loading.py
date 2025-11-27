"""Tests for YAML config loading.

ST005: Tests for load_yaml_config() function.
"""

import pytest


@pytest.mark.unit
class TestLoadYamlConfig:
    """Tests for load_yaml_config() function."""

    def test_given_valid_yaml_file_when_loading_then_returns_dict(self, tmp_path):
        """
        Purpose: Valid YAML files are parsed correctly.
        Quality Contribution: Basic YAML loading works.
        """
        # Arrange
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            """
azure:
  openai:
    endpoint: https://example.openai.azure.com
    timeout: 60
"""
        )

        # Act
        from fs2.config.loaders import load_yaml_config

        result = load_yaml_config(yaml_file)

        # Assert
        assert result == {
            "azure": {"openai": {"endpoint": "https://example.openai.azure.com", "timeout": 60}}
        }

    def test_given_missing_file_when_loading_then_returns_empty_dict(self, tmp_path):
        """
        Purpose: Missing files return empty dict, not error.
        Quality Contribution: Graceful fallback on fresh install.
        """
        # Arrange
        missing_file = tmp_path / "nonexistent.yaml"

        # Act
        from fs2.config.loaders import load_yaml_config

        result = load_yaml_config(missing_file)

        # Assert
        assert result == {}

    def test_given_invalid_yaml_when_loading_then_returns_empty_dict(self, tmp_path):
        """
        Purpose: Invalid YAML returns empty dict, not error.
        Quality Contribution: Graceful fallback on malformed config.
        """
        # Arrange
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("invalid: yaml: content: [unclosed")

        # Act
        from fs2.config.loaders import load_yaml_config

        result = load_yaml_config(yaml_file)

        # Assert
        assert result == {}

    def test_given_empty_yaml_file_when_loading_then_returns_empty_dict(self, tmp_path):
        """
        Purpose: Empty YAML files return empty dict.
        Quality Contribution: Handles edge case of empty file.
        """
        # Arrange
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        # Act
        from fs2.config.loaders import load_yaml_config

        result = load_yaml_config(yaml_file)

        # Assert
        assert result == {}

    def test_given_nested_yaml_when_loading_then_preserves_structure(self, tmp_path):
        """
        Purpose: Nested YAML structures are preserved.
        Quality Contribution: Supports deep config hierarchies.
        """
        # Arrange
        yaml_file = tmp_path / "nested.yaml"
        yaml_file.write_text(
            """
level1:
  level2:
    level3:
      key: value
      number: 42
      flag: true
"""
        )

        # Act
        from fs2.config.loaders import load_yaml_config

        result = load_yaml_config(yaml_file)

        # Assert
        assert result["level1"]["level2"]["level3"]["key"] == "value"
        assert result["level1"]["level2"]["level3"]["number"] == 42
        assert result["level1"]["level2"]["level3"]["flag"] is True
