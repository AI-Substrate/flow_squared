"""Tests for SearchConfig Pydantic configuration model.

Purpose: Verify SearchConfig defaults and validation behavior
Quality Contribution: Ensures search configuration is valid
Acceptance Criteria: default_limit=20, min_similarity=0.5, regex_timeout=2.0

Per Phase 1 tasks.md: TDD approach - write tests FIRST, then implement
Per objects.py pattern: __config_path__ and field validators
"""

import pytest


class TestSearchConfigDefaults:
    """Tests for SearchConfig default values."""

    def test_default_limit(self):
        """
        Purpose: Proves default limit is 20
        Quality Contribution: Documents expected default
        Acceptance Criteria: default_limit == 20
        """
        from fs2.config.objects import SearchConfig

        config = SearchConfig()
        assert config.default_limit == 20

    def test_default_min_similarity(self):
        """
        Purpose: Proves default min_similarity is 0.25 (per DYK-P3-04)
        Quality Contribution: Documents expected default
        Acceptance Criteria: min_similarity == 0.25
        """
        from fs2.config.objects import SearchConfig

        config = SearchConfig()
        assert config.min_similarity == 0.25

    def test_default_regex_timeout(self):
        """
        Purpose: Proves default regex_timeout is 2.0 seconds
        Quality Contribution: Documents expected default
        Acceptance Criteria: regex_timeout == 2.0
        """
        from fs2.config.objects import SearchConfig

        config = SearchConfig()
        assert config.regex_timeout == 2.0


class TestSearchConfigCustomValues:
    """Tests for SearchConfig with custom values."""

    def test_custom_limit_accepted(self):
        """
        Purpose: Proves custom limit is accepted
        Quality Contribution: Enables configuration flexibility
        Acceptance Criteria: default_limit matches input
        """
        from fs2.config.objects import SearchConfig

        config = SearchConfig(default_limit=50)
        assert config.default_limit == 50

    def test_custom_min_similarity_accepted(self):
        """
        Purpose: Proves custom min_similarity is accepted
        Quality Contribution: Enables threshold tuning
        Acceptance Criteria: min_similarity matches input
        """
        from fs2.config.objects import SearchConfig

        config = SearchConfig(min_similarity=0.8)
        assert config.min_similarity == 0.8

    def test_custom_regex_timeout_accepted(self):
        """
        Purpose: Proves custom regex_timeout is accepted
        Quality Contribution: Enables timeout tuning
        Acceptance Criteria: regex_timeout matches input
        """
        from fs2.config.objects import SearchConfig

        config = SearchConfig(regex_timeout=5.0)
        assert config.regex_timeout == 5.0


class TestSearchConfigValidation:
    """Tests for SearchConfig validation behavior."""

    def test_limit_zero_raises_error(self):
        """
        Purpose: Proves zero limit is rejected
        Quality Contribution: Prevents useless configurations
        Acceptance Criteria: ValueError raised
        """
        from pydantic import ValidationError

        from fs2.config.objects import SearchConfig

        with pytest.raises(ValidationError):
            SearchConfig(default_limit=0)

    def test_negative_limit_raises_error(self):
        """
        Purpose: Proves negative limit is rejected
        Quality Contribution: Prevents invalid configurations
        Acceptance Criteria: ValueError raised
        """
        from pydantic import ValidationError

        from fs2.config.objects import SearchConfig

        with pytest.raises(ValidationError):
            SearchConfig(default_limit=-5)

    def test_min_similarity_below_zero_raises_error(self):
        """
        Purpose: Proves negative similarity rejected
        Quality Contribution: Enforces valid range
        Acceptance Criteria: ValueError raised
        """
        from pydantic import ValidationError

        from fs2.config.objects import SearchConfig

        with pytest.raises(ValidationError):
            SearchConfig(min_similarity=-0.1)

    def test_min_similarity_above_one_raises_error(self):
        """
        Purpose: Proves similarity > 1.0 rejected
        Quality Contribution: Enforces valid range
        Acceptance Criteria: ValueError raised
        """
        from pydantic import ValidationError

        from fs2.config.objects import SearchConfig

        with pytest.raises(ValidationError):
            SearchConfig(min_similarity=1.5)

    def test_regex_timeout_zero_raises_error(self):
        """
        Purpose: Proves zero timeout is rejected
        Quality Contribution: Prevents infinite wait
        Acceptance Criteria: ValueError raised
        """
        from pydantic import ValidationError

        from fs2.config.objects import SearchConfig

        with pytest.raises(ValidationError):
            SearchConfig(regex_timeout=0.0)

    def test_negative_regex_timeout_raises_error(self):
        """
        Purpose: Proves negative timeout is rejected
        Quality Contribution: Prevents invalid configuration
        Acceptance Criteria: ValueError raised
        """
        from pydantic import ValidationError

        from fs2.config.objects import SearchConfig

        with pytest.raises(ValidationError):
            SearchConfig(regex_timeout=-1.0)


class TestSearchConfigBoundaries:
    """Tests for SearchConfig boundary values."""

    def test_limit_one_accepted(self):
        """
        Purpose: Proves limit=1 is valid minimum
        Quality Contribution: Documents valid range
        Acceptance Criteria: SearchConfig created successfully
        """
        from fs2.config.objects import SearchConfig

        config = SearchConfig(default_limit=1)
        assert config.default_limit == 1

    def test_min_similarity_zero_accepted(self):
        """
        Purpose: Proves min_similarity=0.0 is valid
        Quality Contribution: Documents valid range
        Acceptance Criteria: SearchConfig created successfully
        """
        from fs2.config.objects import SearchConfig

        config = SearchConfig(min_similarity=0.0)
        assert config.min_similarity == 0.0

    def test_min_similarity_one_accepted(self):
        """
        Purpose: Proves min_similarity=1.0 is valid
        Quality Contribution: Documents valid range
        Acceptance Criteria: SearchConfig created successfully
        """
        from fs2.config.objects import SearchConfig

        config = SearchConfig(min_similarity=1.0)
        assert config.min_similarity == 1.0


class TestSearchConfigPath:
    """Tests for SearchConfig __config_path__ attribute."""

    def test_has_config_path(self):
        """
        Purpose: Proves __config_path__ is set for YAML loading
        Quality Contribution: Enables configuration from file
        Acceptance Criteria: __config_path__ == "search"
        """
        from fs2.config.objects import SearchConfig

        assert SearchConfig.__config_path__ == "search"
