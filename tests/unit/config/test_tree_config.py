"""Tests for TreeConfig.

T001: Tests for TreeConfig creation and validation.
Purpose: Verify TreeConfig loads defaults, from YAML, from env vars.
"""

import pytest


@pytest.mark.unit
class TestTreeConfigDefaults:
    """T001: Tests for TreeConfig default values."""

    def test_given_no_config_when_created_then_has_default_graph_path(self):
        """
        Purpose: Verifies default graph_path is set.
        Quality Contribution: Ensures command works with defaults.
        Acceptance Criteria: graph_path defaults to ".fs2/graph.pickle".

        Task: T001
        """
        from fs2.config.objects import TreeConfig

        config = TreeConfig()

        assert config.graph_path == ".fs2/graph.pickle"

    def test_given_custom_path_when_created_then_uses_custom_path(self):
        """
        Purpose: Verifies custom graph_path works.
        Quality Contribution: Allows non-standard paths.
        Acceptance Criteria: Custom path is used.

        Task: T001
        """
        from fs2.config.objects import TreeConfig

        config = TreeConfig(graph_path="custom/path.pickle")

        assert config.graph_path == "custom/path.pickle"


@pytest.mark.unit
class TestTreeConfigPath:
    """T001: Tests for TreeConfig __config_path__."""

    def test_given_tree_config_when_checked_then_has_config_path(self):
        """
        Purpose: Verifies __config_path__ is set for YAML loading.
        Quality Contribution: Ensures config can be loaded from YAML.
        Acceptance Criteria: __config_path__ is "tree".

        Task: T001
        """
        from fs2.config.objects import TreeConfig

        assert TreeConfig.__config_path__ == "tree"


@pytest.mark.unit
class TestTreeConfigRegistry:
    """T001: Tests for TreeConfig registration."""

    def test_given_yaml_config_types_when_checked_then_includes_tree_config(self):
        """
        Purpose: Verifies TreeConfig is in YAML_CONFIG_TYPES.
        Quality Contribution: Ensures config can be auto-loaded.
        Acceptance Criteria: TreeConfig in YAML_CONFIG_TYPES.

        Task: T001
        """
        from fs2.config.objects import YAML_CONFIG_TYPES, TreeConfig

        assert TreeConfig in YAML_CONFIG_TYPES


@pytest.mark.unit
class TestTreeConfigYAMLLoading:
    """T001: Tests for TreeConfig YAML loading."""

    def test_given_yaml_with_tree_config_when_loaded_then_uses_yaml_value(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: Verifies TreeConfig loads from YAML.
        Quality Contribution: Ensures YAML config works.
        Acceptance Criteria: YAML value is used.

        Task: T001
        """
        from fs2.config.service import FS2ConfigurationService
        from fs2.config.objects import TreeConfig

        # Create config directory and file
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("""tree:
  graph_path: "custom/from_yaml.pickle"
scan:
  scan_paths:
    - "."
""")

        monkeypatch.chdir(tmp_path)

        service = FS2ConfigurationService()
        config = service.require(TreeConfig)

        assert config.graph_path == "custom/from_yaml.pickle"


@pytest.mark.unit
class TestTreeConfigEnvLoading:
    """T001: Tests for TreeConfig env var loading."""

    def test_given_env_var_when_loaded_then_uses_env_value(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: Verifies TreeConfig loads from env vars.
        Quality Contribution: Ensures env override works.
        Acceptance Criteria: Env var value is used.

        Task: T001
        """
        from fs2.config.service import FS2ConfigurationService
        from fs2.config.objects import TreeConfig

        # Create config directory with basic config
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("""tree:
  graph_path: "default.pickle"
scan:
  scan_paths:
    - "."
""")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("FS2_TREE__GRAPH_PATH", "from_env.pickle")

        service = FS2ConfigurationService()
        config = service.require(TreeConfig)

        assert config.graph_path == "from_env.pickle"

    def test_given_env_var_when_yaml_exists_then_env_takes_precedence(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: Verifies env var takes precedence over YAML.
        Quality Contribution: Ensures proper config hierarchy.
        Acceptance Criteria: Env var overrides YAML.

        Task: T001
        """
        from fs2.config.service import FS2ConfigurationService
        from fs2.config.objects import TreeConfig

        # Create config directory with YAML
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("""tree:
  graph_path: "yaml_value.pickle"
scan:
  scan_paths:
    - "."
""")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("FS2_TREE__GRAPH_PATH", "env_value.pickle")

        service = FS2ConfigurationService()
        config = service.require(TreeConfig)

        assert config.graph_path == "env_value.pickle"
