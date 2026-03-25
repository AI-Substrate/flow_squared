"""Tests for ReportsConfig model.

Validates config loading, field defaults, and validation rules.
Uses fakes over mocks per doctrine.
"""

import pytest

from fs2.config.objects import ReportsConfig


@pytest.mark.unit
class TestReportsConfig:
    """Tests for ReportsConfig model."""

    def test_defaults(self):
        """Proves default values are sensible."""
        config = ReportsConfig()
        assert config.output_dir == ".fs2/reports"
        assert config.include_smart_content is True
        assert config.max_nodes == 10000

    def test_custom_values(self):
        """Proves custom values override defaults."""
        config = ReportsConfig(
            output_dir="custom/reports",
            include_smart_content=False,
            max_nodes=50000,
        )
        assert config.output_dir == "custom/reports"
        assert config.include_smart_content is False
        assert config.max_nodes == 50000

    def test_max_nodes_too_low(self):
        """Proves max_nodes < 100 is rejected."""
        with pytest.raises(ValueError, match="max_nodes must be between"):
            ReportsConfig(max_nodes=50)

    def test_max_nodes_too_high(self):
        """Proves max_nodes > 500000 is rejected."""
        with pytest.raises(ValueError, match="max_nodes must be between"):
            ReportsConfig(max_nodes=1000000)

    def test_max_nodes_boundary_low(self):
        """Proves max_nodes = 100 is accepted."""
        config = ReportsConfig(max_nodes=100)
        assert config.max_nodes == 100

    def test_max_nodes_boundary_high(self):
        """Proves max_nodes = 500000 is accepted."""
        config = ReportsConfig(max_nodes=500000)
        assert config.max_nodes == 500000

    def test_config_path(self):
        """Proves __config_path__ is 'reports' for YAML registry."""
        assert ReportsConfig.__config_path__ == "reports"
