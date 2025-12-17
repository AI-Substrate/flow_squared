"""Tests for GraphConfig.

T000: Tests for GraphConfig creation and validation.
Purpose: Verify GraphConfig loads defaults, from YAML, from env vars.

Note: Renamed from test_tree_config.py - GraphConfig was previously named TreeConfig.
"""

import pytest


@pytest.mark.unit
class TestGraphConfigDefaults:
    """T000: Tests for GraphConfig default values."""

    def test_given_no_config_when_created_then_has_default_graph_path(self):
        """
        Purpose: Verifies default graph_path is set.
        Quality Contribution: Ensures command works with defaults.
        Acceptance Criteria: graph_path defaults to ".fs2/graph.pickle".

        Task: T000
        """
        from fs2.config.objects import GraphConfig

        config = GraphConfig()

        assert config.graph_path == ".fs2/graph.pickle"

    def test_given_custom_path_when_created_then_uses_custom_path(self):
        """
        Purpose: Verifies custom graph_path works.
        Quality Contribution: Allows non-standard paths.
        Acceptance Criteria: Custom path is used.

        Task: T000
        """
        from fs2.config.objects import GraphConfig

        config = GraphConfig(graph_path="custom/path.pickle")

        assert config.graph_path == "custom/path.pickle"


@pytest.mark.unit
class TestGraphConfigPath:
    """T000: Tests for GraphConfig __config_path__."""

    def test_given_graph_config_when_checked_then_has_config_path(self):
        """
        Purpose: Verifies __config_path__ is set for YAML loading.
        Quality Contribution: Ensures config can be loaded from YAML.
        Acceptance Criteria: __config_path__ is "graph".

        Task: T000
        """
        from fs2.config.objects import GraphConfig

        assert GraphConfig.__config_path__ == "graph"


@pytest.mark.unit
class TestGraphConfigRegistry:
    """T000: Tests for GraphConfig registration."""

    def test_given_yaml_config_types_when_checked_then_includes_graph_config(self):
        """
        Purpose: Verifies GraphConfig is in YAML_CONFIG_TYPES.
        Quality Contribution: Ensures config can be auto-loaded.
        Acceptance Criteria: GraphConfig in YAML_CONFIG_TYPES.

        Task: T000
        """
        from fs2.config.objects import YAML_CONFIG_TYPES, GraphConfig

        assert GraphConfig in YAML_CONFIG_TYPES


@pytest.mark.unit
class TestGraphConfigYAMLLoading:
    """T000: Tests for GraphConfig YAML loading."""

    def test_given_yaml_with_graph_config_when_loaded_then_uses_yaml_value(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: Verifies GraphConfig loads from YAML.
        Quality Contribution: Ensures YAML config works.
        Acceptance Criteria: YAML value is used.

        Task: T000
        """
        from fs2.config.objects import GraphConfig
        from fs2.config.service import FS2ConfigurationService

        # Create config directory and file
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("""graph:
  graph_path: "custom/from_yaml.pickle"
scan:
  scan_paths:
    - "."
""")

        monkeypatch.chdir(tmp_path)

        service = FS2ConfigurationService()
        config = service.require(GraphConfig)

        assert config.graph_path == "custom/from_yaml.pickle"


@pytest.mark.unit
class TestGraphConfigEnvLoading:
    """T000: Tests for GraphConfig env var loading."""

    def test_given_env_var_when_loaded_then_uses_env_value(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: Verifies GraphConfig loads from env vars.
        Quality Contribution: Ensures env override works.
        Acceptance Criteria: Env var value is used.

        Task: T000
        """
        from fs2.config.objects import GraphConfig
        from fs2.config.service import FS2ConfigurationService

        # Create config directory with basic config
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("""graph:
  graph_path: "default.pickle"
scan:
  scan_paths:
    - "."
""")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("FS2_GRAPH__GRAPH_PATH", "from_env.pickle")

        service = FS2ConfigurationService()
        config = service.require(GraphConfig)

        assert config.graph_path == "from_env.pickle"

    def test_given_env_var_when_yaml_exists_then_env_takes_precedence(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: Verifies env var takes precedence over YAML.
        Quality Contribution: Ensures proper config hierarchy.
        Acceptance Criteria: Env var overrides YAML.

        Task: T000
        """
        from fs2.config.objects import GraphConfig
        from fs2.config.service import FS2ConfigurationService

        # Create config directory with YAML
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("""graph:
  graph_path: "yaml_value.pickle"
scan:
  scan_paths:
    - "."
""")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("FS2_GRAPH__GRAPH_PATH", "env_value.pickle")

        service = FS2ConfigurationService()
        config = service.require(GraphConfig)

        assert config.graph_path == "env_value.pickle"


@pytest.mark.unit
class TestTreeConfigBackwardCompatibility:
    """Tests for backward compatibility alias."""

    def test_given_tree_config_import_when_used_then_same_as_graph_config(self):
        """
        Purpose: Verifies TreeConfig alias works for backward compatibility.
        Quality Contribution: Prevents breaking existing code.
        Acceptance Criteria: TreeConfig is the same as GraphConfig.

        Task: T000
        """
        from fs2.config.objects import GraphConfig, TreeConfig

        # TreeConfig should be an alias to GraphConfig
        assert TreeConfig is GraphConfig
