"""Tests for deep merge utility.

ST009: Tests for deep_merge() function.

Behavior: Overlay wins at leaf level, nested dicts are recursively merged.
"""

import pytest


@pytest.mark.unit
class TestDeepMerge:
    """Tests for deep_merge() function."""

    def test_given_flat_dicts_when_merging_then_overlay_wins(self):
        """
        Purpose: Overlay values override base values.
        Quality Contribution: Basic override works.
        """
        # Arrange
        base = {"key": "base_value"}
        overlay = {"key": "overlay_value"}

        # Act
        from fs2.config.loaders import deep_merge

        result = deep_merge(base, overlay)

        # Assert
        assert result["key"] == "overlay_value"

    def test_given_nested_dicts_when_merging_then_recursively_merges(self):
        """
        Purpose: Nested dicts are merged recursively.
        Quality Contribution: Deep merge preserves structure.
        """
        # Arrange
        base = {"azure": {"openai": {"timeout": 30, "endpoint": "base-endpoint"}}}
        overlay = {"azure": {"openai": {"timeout": 60}}}

        # Act
        from fs2.config.loaders import deep_merge

        result = deep_merge(base, overlay)

        # Assert: timeout overridden, endpoint preserved
        assert result["azure"]["openai"]["timeout"] == 60
        assert result["azure"]["openai"]["endpoint"] == "base-endpoint"

    def test_given_non_overlapping_keys_when_merging_then_both_preserved(self):
        """
        Purpose: Non-overlapping keys from both dicts are included.
        Quality Contribution: Merge doesn't lose data.
        """
        # Arrange
        base = {"base_key": "base_value"}
        overlay = {"overlay_key": "overlay_value"}

        # Act
        from fs2.config.loaders import deep_merge

        result = deep_merge(base, overlay)

        # Assert
        assert result["base_key"] == "base_value"
        assert result["overlay_key"] == "overlay_value"

    def test_given_empty_overlay_when_merging_then_returns_base(self):
        """
        Purpose: Empty overlay doesn't change base.
        Quality Contribution: Handles empty config case.
        """
        # Arrange
        base = {"key": "value", "nested": {"inner": "data"}}
        overlay = {}

        # Act
        from fs2.config.loaders import deep_merge

        result = deep_merge(base, overlay)

        # Assert
        assert result == base

    def test_given_empty_base_when_merging_then_returns_overlay(self):
        """
        Purpose: Empty base returns overlay values.
        Quality Contribution: Handles fresh install case.
        """
        # Arrange
        base = {}
        overlay = {"key": "value"}

        # Act
        from fs2.config.loaders import deep_merge

        result = deep_merge(base, overlay)

        # Assert
        assert result == {"key": "value"}

    def test_given_dict_over_scalar_when_merging_then_overlay_wins(self):
        """
        Purpose: Dict overlaying scalar replaces entirely.
        Quality Contribution: Clear override semantics.
        """
        # Arrange
        base = {"key": "scalar_value"}
        overlay = {"key": {"nested": "dict"}}

        # Act
        from fs2.config.loaders import deep_merge

        result = deep_merge(base, overlay)

        # Assert
        assert result["key"] == {"nested": "dict"}

    def test_given_scalar_over_dict_when_merging_then_overlay_wins(self):
        """
        Purpose: Scalar overlaying dict replaces entirely.
        Quality Contribution: Clear override semantics.
        """
        # Arrange
        base = {"key": {"nested": "dict"}}
        overlay = {"key": "scalar_value"}

        # Act
        from fs2.config.loaders import deep_merge

        result = deep_merge(base, overlay)

        # Assert
        assert result["key"] == "scalar_value"

    def test_given_base_dict_when_merging_then_original_unchanged(self):
        """
        Purpose: Merge doesn't mutate original dicts.
        Quality Contribution: No side effects.
        """
        # Arrange
        base = {"key": "original"}
        overlay = {"key": "new"}
        original_base = base.copy()

        # Act
        from fs2.config.loaders import deep_merge

        deep_merge(base, overlay)

        # Assert: original unchanged
        assert base == original_base
