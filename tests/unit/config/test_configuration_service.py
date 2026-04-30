"""Tests for ConfigurationService ABC and implementations.

ST019-ST024: Tests for ConfigurationService, FS2ConfigurationService, FakeConfigurationService.
"""

import pytest


@pytest.mark.unit
class TestConfigurationServiceABC:
    """Tests for ConfigurationService abstract base class."""

    def test_given_abc_when_instantiating_directly_then_raises_type_error(self):
        """
        Purpose: ConfigurationService is abstract.
        Quality Contribution: Enforces implementation.
        """
        # Act & Assert
        from fs2.config.service import ConfigurationService

        with pytest.raises(TypeError) as exc_info:
            ConfigurationService()

        assert "abstract" in str(exc_info.value).lower()

    def test_given_abc_when_checking_methods_then_has_set_get_require(self):
        """
        Purpose: ABC defines set/get/require methods.
        Quality Contribution: Documents the interface.
        """
        # Act
        from fs2.config.service import ConfigurationService

        # Assert
        assert hasattr(ConfigurationService, "set")
        assert hasattr(ConfigurationService, "get")
        assert hasattr(ConfigurationService, "require")


@pytest.mark.unit
class TestFS2ConfigurationService:
    """Tests for FS2ConfigurationService implementation."""

    def test_given_empty_env_when_constructing_then_succeeds(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: Service works with no config files.
        Quality Contribution: Graceful fresh install.
        """
        # Arrange
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)

        # Act
        from fs2.config.service import FS2ConfigurationService

        config = FS2ConfigurationService()

        # Assert: No error, service exists
        assert config is not None

    def test_given_yaml_config_when_constructing_then_loads_typed_object(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: YAML config is loaded into typed objects.
        Quality Contribution: Core loading works.
        """
        # Arrange
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)

        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(
            """
azure:
  openai:
    endpoint: https://test.openai.azure.com
    timeout: 45
"""
        )

        # Act
        from fs2.config.objects import AzureOpenAIConfig
        from fs2.config.service import FS2ConfigurationService

        config = FS2ConfigurationService()
        azure = config.get(AzureOpenAIConfig)

        # Assert
        assert azure is not None
        assert azure.endpoint == "https://test.openai.azure.com"
        assert azure.timeout == 45

    def test_given_env_vars_when_constructing_then_overrides_yaml(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: Env vars override YAML values.
        Quality Contribution: Correct precedence.
        """
        # Arrange
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)

        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(
            """
azure:
  openai:
    endpoint: https://yaml.openai.azure.com
    timeout: 30
"""
        )

        # Env var overrides
        monkeypatch.setenv("FS2_AZURE__OPENAI__TIMEOUT", "90")

        # Act
        from fs2.config.objects import AzureOpenAIConfig
        from fs2.config.service import FS2ConfigurationService

        config = FS2ConfigurationService()
        azure = config.get(AzureOpenAIConfig)

        # Assert: timeout from env, endpoint from yaml
        assert azure is not None
        assert azure.timeout == 90
        assert azure.endpoint == "https://yaml.openai.azure.com"

    def test_given_typed_config_when_set_then_get_retrieves_it(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: set() stores, get() retrieves by type.
        Quality Contribution: Core API works.
        """
        # Arrange
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)

        from fs2.config.objects import SearchQueryConfig
        from fs2.config.service import FS2ConfigurationService

        config = FS2ConfigurationService()
        search = SearchQueryConfig(mode="slim", text="auth", limit=20)

        # Act
        config.set(search)
        retrieved = config.get(SearchQueryConfig)

        # Assert
        assert retrieved is not None
        assert retrieved.mode == "slim"
        assert retrieved.text == "auth"
        assert retrieved.limit == 20

    def test_given_missing_config_when_get_then_returns_none(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: get() returns None for unset configs.
        Quality Contribution: Safe access pattern.
        """
        # Arrange
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)

        from fs2.config.objects import SearchQueryConfig
        from fs2.config.service import FS2ConfigurationService

        config = FS2ConfigurationService()

        # Act
        result = config.get(SearchQueryConfig)

        # Assert
        assert result is None

    def test_given_missing_config_when_require_then_raises_error(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: require() raises actionable error.
        Quality Contribution: Fail-fast with guidance.
        """
        # Arrange
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)

        from fs2.config.exceptions import MissingConfigurationError
        from fs2.config.objects import SearchQueryConfig
        from fs2.config.service import FS2ConfigurationService

        config = FS2ConfigurationService()

        # Act & Assert
        with pytest.raises(MissingConfigurationError) as exc_info:
            config.require(SearchQueryConfig)

        # Check actionable message
        error_str = str(exc_info.value)
        assert "SearchQueryConfig" in error_str
        assert "set" in error_str.lower()  # Mentions how to fix

    def test_given_placeholder_in_yaml_when_constructing_then_expands(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: ${VAR} placeholders are expanded.
        Quality Contribution: Secrets pattern works.
        """
        # Arrange
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)

        # Set secret in env
        monkeypatch.setenv("AZURE_API_KEY", "my-secret-key")

        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text(
            """
azure:
  openai:
    endpoint: https://test.openai.azure.com
    api_key: ${AZURE_API_KEY}
"""
        )

        # Act
        from fs2.config.objects import AzureOpenAIConfig
        from fs2.config.service import FS2ConfigurationService

        config = FS2ConfigurationService()
        azure = config.get(AzureOpenAIConfig)

        # Assert
        assert azure is not None
        assert azure.api_key == "my-secret-key"


@pytest.mark.unit
class TestFakeConfigurationService:
    """Tests for FakeConfigurationService test double."""

    def test_given_configs_in_constructor_when_get_then_returns_them(self):
        """
        Purpose: FakeConfigurationService accepts configs in constructor.
        Quality Contribution: Easy test setup.
        """
        # Arrange
        from fs2.config.objects import AzureOpenAIConfig, SearchQueryConfig
        from fs2.config.service import FakeConfigurationService

        azure = AzureOpenAIConfig(endpoint="https://fake.com")
        search = SearchQueryConfig(mode="slim")

        # Act
        config = FakeConfigurationService(azure, search)

        # Assert
        assert config.get(AzureOpenAIConfig) == azure
        assert config.get(SearchQueryConfig) == search

    def test_given_empty_constructor_when_get_then_returns_none(self):
        """
        Purpose: Empty fake returns None for get().
        Quality Contribution: Clean default.
        """
        # Arrange
        from fs2.config.objects import SearchQueryConfig
        from fs2.config.service import FakeConfigurationService

        config = FakeConfigurationService()

        # Act
        result = config.get(SearchQueryConfig)

        # Assert
        assert result is None

    def test_given_fake_when_set_then_get_retrieves(self):
        """
        Purpose: Fake supports set/get like real service.
        Quality Contribution: Same API contract.
        """
        # Arrange
        from fs2.config.objects import SearchQueryConfig
        from fs2.config.service import FakeConfigurationService

        config = FakeConfigurationService()
        search = SearchQueryConfig(mode="detailed", text="test")

        # Act
        config.set(search)
        retrieved = config.get(SearchQueryConfig)

        # Assert
        assert retrieved is not None
        assert retrieved.mode == "detailed"

    def test_given_missing_config_when_require_then_raises_error(self):
        """
        Purpose: Fake require() raises like real service.
        Quality Contribution: Same error behavior.
        """
        # Arrange
        from fs2.config.exceptions import MissingConfigurationError
        from fs2.config.objects import SearchQueryConfig
        from fs2.config.service import FakeConfigurationService

        config = FakeConfigurationService()

        # Act & Assert
        with pytest.raises(MissingConfigurationError):
            config.require(SearchQueryConfig)


@pytest.mark.unit
class TestGraphConfigAutoRegistration:
    """Tests that FS2ConfigurationService auto-registers GraphConfig() defaults
    when the YAML config has no `graph:` section.

    Closes issue #14: previously, services using `config.require(GraphConfig)`
    would raise `MissingConfigurationError` when the optional `graph:` block
    was absent from `.fs2/config.yaml`, even though every field on GraphConfig
    has a default. The auto-registration mechanism (`_AUTO_DEFAULT_CONFIGS`)
    fixes this at the loader layer so all services keep using the rule-compliant
    `config.require(GraphConfig)` pattern (R3.2 / Constitution P3).
    """

    def test_given_yaml_without_graph_section_when_loading_then_graph_config_uses_defaults(
        self, make_project_config
    ):
        """
        Purpose: Auto-registration provides a default-constructed GraphConfig
            when the YAML has no `graph:` block.
        Quality Contribution: Closes the footgun reported in issue #14 — MCP
            tools (tree, search, get_node) now work out of the box without
            requiring users to add a graph: section by hand.
        Contract: After loading a config that omits `graph:`,
            `config.require(GraphConfig)` MUST return a `GraphConfig` instance
            with `graph_path == ".fs2/graph.pickle"`.
        Worked Example: A user runs `fs2 init` (which produces a config
            without `graph:` in pre-fix versions), then wires fs2 into an MCP
            host. `tree(pattern=".")` should succeed, not raise.
        """
        # Arrange — YAML deliberately omits the `graph:` section
        make_project_config(
            """\
scan:
  scan_paths:
    - "."
"""
        )

        # Act
        from fs2.config.objects import GraphConfig
        from fs2.config.service import FS2ConfigurationService

        config = FS2ConfigurationService()
        graph_config = config.require(GraphConfig)

        # Assert
        assert isinstance(graph_config, GraphConfig)
        assert graph_config.graph_path == ".fs2/graph.pickle"

    def test_given_explicit_graph_section_when_loading_then_explicit_value_wins(
        self, make_project_config
    ):
        """
        Purpose: Explicit YAML graph_path overrides the auto-registered default.
        Quality Contribution: Verifies the auto-registration doesn't mask
            user-provided values — backward compatibility preserved.
        Contract: When YAML provides `graph: { graph_path: X }`, the loader
            MUST register that value, NOT the default. Auto-registration MUST
            be skipped if the type was already registered from YAML.
        Worked Example: An existing project with `graph: { graph_path: "custom/path" }`
            in `.fs2/config.yaml` continues to honor that custom path after
            this fix; the auto-default does not silently overwrite it.
        """
        # Arrange — YAML provides an explicit non-default path
        make_project_config(
            """\
graph:
  graph_path: "custom/path/to/graph.pickle"
"""
        )

        # Act
        from fs2.config.objects import GraphConfig
        from fs2.config.service import FS2ConfigurationService

        config = FS2ConfigurationService()
        graph_config = config.require(GraphConfig)

        # Assert
        assert graph_config.graph_path == "custom/path/to/graph.pickle"

    def test_given_no_yaml_files_at_all_when_loading_then_graph_config_still_available(
        self, isolated_config_env
    ):
        """
        Purpose: Auto-registration works even when there are NO config files —
            no project YAML, no user YAML, no env vars.
        Quality Contribution: Edge case — proves the fall-through works on a
            truly empty load, not just on configs that have other sections.
        Contract: A bare `FS2ConfigurationService()` constructed in a directory
            with no `.fs2/`, no `~/.config/fs2/`, and no `FS2_*` env vars MUST
            still satisfy `require(GraphConfig)`.
        """
        # Arrange — isolated_config_env redirects HOME/XDG/cwd; we write nothing.

        # Act
        from fs2.config.objects import GraphConfig
        from fs2.config.service import FS2ConfigurationService

        config = FS2ConfigurationService()
        graph_config = config.require(GraphConfig)

        # Assert
        assert isinstance(graph_config, GraphConfig)
        assert graph_config.graph_path == ".fs2/graph.pickle"
