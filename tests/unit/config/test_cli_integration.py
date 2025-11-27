"""Tests for CLI integration pattern.

ST026: Tests demonstrating CLI → ConfigurationService → Service flow.
"""

import pytest


@pytest.mark.unit
class TestCLIIntegration:
    """Tests for CLI integration pattern."""

    def test_given_cli_flow_when_set_then_service_can_get(self, monkeypatch, tmp_path):
        """
        Purpose: Full CLI integration: construct → set() → service get().
        Quality Contribution: Documents the intended usage pattern.
        """
        # Arrange: Simulate CLI flow
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)

        from fs2.config.objects import SearchQueryConfig
        from fs2.config.service import FS2ConfigurationService

        # Simulate CLI command like: fs2 query "authentication" --mode slim
        config = FS2ConfigurationService()
        config.set(SearchQueryConfig(mode="slim", text="authentication"))

        # Act: Service consumes config
        class MockSearchService:
            def __init__(self, config):
                self._search = config.require(SearchQueryConfig)

            def execute(self) -> str:
                return (
                    f"Searching for '{self._search.text}' in {self._search.mode} mode"
                )

        service = MockSearchService(config)

        # Assert
        assert service.execute() == "Searching for 'authentication' in slim mode"

    def test_given_yaml_and_cli_when_service_gets_both_then_both_available(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: YAML config and CLI config coexist.
        Quality Contribution: Shows combined usage.
        """
        # Arrange: YAML for Azure config
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
    timeout: 60
"""
        )

        from fs2.config.objects import AzureOpenAIConfig, SearchQueryConfig
        from fs2.config.service import FS2ConfigurationService

        # CLI sets search config
        config = FS2ConfigurationService()
        config.set(SearchQueryConfig(mode="detailed", text="error handling"))

        # Act: Service uses both
        class MockService:
            def __init__(self, config):
                self._azure = config.get(AzureOpenAIConfig)
                self._search = config.require(SearchQueryConfig)

            def describe(self) -> str:
                endpoint = self._azure.endpoint if self._azure else "none"
                return f"Search: {self._search.text}, Azure: {endpoint}"

        service = MockService(config)

        # Assert
        assert (
            service.describe()
            == "Search: error handling, Azure: https://test.openai.azure.com"
        )

    def test_given_fake_service_when_testing_then_no_file_access(self):
        """
        Purpose: FakeConfigurationService enables isolated testing.
        Quality Contribution: Fast, deterministic tests.
        """
        # Arrange: Use fake - no file system access needed
        from fs2.config.objects import AzureOpenAIConfig, SearchQueryConfig
        from fs2.config.service import FakeConfigurationService

        fake_azure = AzureOpenAIConfig(
            endpoint="https://fake.openai.azure.com",
            api_key="fake-key",
        )
        fake_search = SearchQueryConfig(mode="slim", text="test query")

        config = FakeConfigurationService(fake_azure, fake_search)

        # Act: Service uses fake config
        class MockLLMService:
            def __init__(self, config):
                self._azure = config.require(AzureOpenAIConfig)
                self._search = config.require(SearchQueryConfig)

            def call(self) -> str:
                return f"Calling {self._azure.endpoint} with '{self._search.text}'"

        service = MockLLMService(config)

        # Assert
        assert (
            service.call() == "Calling https://fake.openai.azure.com with 'test query'"
        )

    def test_given_env_override_when_cli_runs_then_env_wins(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: CLI can use FS2_* env vars for overrides.
        Quality Contribution: Documents CLI override pattern.
        """
        # Arrange: YAML has timeout=30
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
    timeout: 30
"""
        )

        # Simulate: FS2_AZURE__OPENAI__TIMEOUT=120 fs2 query ...
        monkeypatch.setenv("FS2_AZURE__OPENAI__TIMEOUT", "120")

        from fs2.config.objects import AzureOpenAIConfig
        from fs2.config.service import FS2ConfigurationService

        # Act
        config = FS2ConfigurationService()
        azure = config.get(AzureOpenAIConfig)

        # Assert: env var overrode YAML
        assert azure is not None
        assert azure.timeout == 120
        assert azure.endpoint == "https://test.openai.azure.com"
