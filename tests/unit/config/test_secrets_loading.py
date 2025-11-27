"""Tests for secrets loading to os.environ.

ST003: Tests for load_secrets_to_env() function.

Precedence (lowest → highest):
1. OS environment (base layer)
2. User secrets (~/.config/fs2/secrets.env)
3. Project secrets (./.fs2/secrets.env)
4. Working dir .env (./.env wins over everything)
"""

import os

import pytest


@pytest.mark.unit
class TestLoadSecretsToEnv:
    """Tests for load_secrets_to_env() function."""

    def test_given_user_secrets_file_when_loading_then_sets_env_var(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: User secrets file values are loaded into os.environ.
        Quality Contribution: Basic secrets loading works.
        """
        # Arrange
        user_config = tmp_path / ".config" / "fs2"
        user_config.mkdir(parents=True)
        secrets_file = user_config / "secrets.env"
        secrets_file.write_text("TEST_SECRET=from_user_secrets\n")

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)
        # Ensure var doesn't exist
        monkeypatch.delenv("TEST_SECRET", raising=False)

        # Act
        from fs2.config.loaders import load_secrets_to_env

        load_secrets_to_env()

        # Assert
        assert os.environ.get("TEST_SECRET") == "from_user_secrets"

    def test_given_project_secrets_file_when_loading_then_overrides_user_secrets(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: Project secrets override user secrets.
        Quality Contribution: Correct precedence order.
        """
        # Arrange: User secrets
        user_config = tmp_path / ".config" / "fs2"
        user_config.mkdir(parents=True)
        user_secrets = user_config / "secrets.env"
        user_secrets.write_text("TEST_SECRET=from_user\n")

        # Arrange: Project secrets
        project_config = tmp_path / ".fs2"
        project_config.mkdir()
        project_secrets = project_config / "secrets.env"
        project_secrets.write_text("TEST_SECRET=from_project\n")

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("TEST_SECRET", raising=False)

        # Act
        from fs2.config.loaders import load_secrets_to_env

        load_secrets_to_env()

        # Assert: Project wins over user
        assert os.environ.get("TEST_SECRET") == "from_project"

    def test_given_dotenv_file_when_loading_then_dotenv_wins(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: .env file overrides everything (standard dotenv behavior).
        Quality Contribution: Developers expect .env to win.
        """
        # Arrange: User secrets
        user_config = tmp_path / ".config" / "fs2"
        user_config.mkdir(parents=True)
        user_secrets = user_config / "secrets.env"
        user_secrets.write_text("TEST_SECRET=from_user\n")

        # Arrange: Project secrets
        project_config = tmp_path / ".fs2"
        project_config.mkdir()
        project_secrets = project_config / "secrets.env"
        project_secrets.write_text("TEST_SECRET=from_project\n")

        # Arrange: .env file
        dotenv_file = tmp_path / ".env"
        dotenv_file.write_text("TEST_SECRET=from_dotenv\n")

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("TEST_SECRET", raising=False)

        # Act
        from fs2.config.loaders import load_secrets_to_env

        load_secrets_to_env()

        # Assert: .env wins
        assert os.environ.get("TEST_SECRET") == "from_dotenv"

    def test_given_no_secrets_files_when_loading_then_no_error(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: Graceful handling when no secrets files exist.
        Quality Contribution: Doesn't crash on fresh install.
        """
        # Arrange: No secrets files, clean environment
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)

        # Act - should not raise
        from fs2.config.loaders import load_secrets_to_env

        load_secrets_to_env()  # No error expected

    def test_given_multiple_vars_in_file_when_loading_then_all_loaded(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: Multiple variables in a secrets file are all loaded.
        Quality Contribution: Supports multiple secrets.
        """
        # Arrange
        user_config = tmp_path / ".config" / "fs2"
        user_config.mkdir(parents=True)
        secrets_file = user_config / "secrets.env"
        secrets_file.write_text("VAR_ONE=value1\nVAR_TWO=value2\nVAR_THREE=value3\n")

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("VAR_ONE", raising=False)
        monkeypatch.delenv("VAR_TWO", raising=False)
        monkeypatch.delenv("VAR_THREE", raising=False)

        # Act
        from fs2.config.loaders import load_secrets_to_env

        load_secrets_to_env()

        # Assert
        assert os.environ.get("VAR_ONE") == "value1"
        assert os.environ.get("VAR_TWO") == "value2"
        assert os.environ.get("VAR_THREE") == "value3"

    def test_given_xdg_config_home_set_when_loading_then_uses_xdg_path(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: XDG_CONFIG_HOME is respected for user secrets.
        Quality Contribution: XDG compliance.
        """
        # Arrange: XDG config dir
        xdg_config = tmp_path / "xdg_config"
        fs2_config = xdg_config / "fs2"
        fs2_config.mkdir(parents=True)
        secrets_file = fs2_config / "secrets.env"
        secrets_file.write_text("XDG_SECRET=from_xdg\n")

        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("XDG_SECRET", raising=False)

        # Act
        from fs2.config.loaders import load_secrets_to_env

        load_secrets_to_env()

        # Assert
        assert os.environ.get("XDG_SECRET") == "from_xdg"
