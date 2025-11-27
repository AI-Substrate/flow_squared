"""Tests for XDG path resolution.

ST001: Tests for get_user_config_dir() and get_project_config_dir().
"""

import os
from pathlib import Path

import pytest


@pytest.mark.unit
class TestGetUserConfigDir:
    """Tests for get_user_config_dir() function."""

    def test_given_xdg_config_home_set_when_get_user_config_dir_then_uses_xdg_path(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: XDG_CONFIG_HOME should be respected when set.
        Quality Contribution: Follows XDG Base Directory spec.
        """
        # Arrange
        custom_config = tmp_path / "custom_config"
        custom_config.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(custom_config))

        # Act
        from fs2.config.paths import get_user_config_dir

        result = get_user_config_dir()

        # Assert
        assert result == custom_config / "fs2"

    def test_given_xdg_not_set_when_get_user_config_dir_then_uses_home_config(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: Falls back to ~/.config/fs2 when XDG_CONFIG_HOME not set.
        Quality Contribution: Standard fallback behavior.
        """
        # Arrange
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))

        # Act
        from fs2.config.paths import get_user_config_dir

        result = get_user_config_dir()

        # Assert
        assert result == tmp_path / ".config" / "fs2"

    def test_given_user_config_dir_when_called_then_returns_path_object(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: Return type is Path, not string.
        Quality Contribution: Type safety.
        """
        # Arrange
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        # Act
        from fs2.config.paths import get_user_config_dir

        result = get_user_config_dir()

        # Assert
        assert isinstance(result, Path)


@pytest.mark.unit
class TestGetProjectConfigDir:
    """Tests for get_project_config_dir() function."""

    def test_given_cwd_when_get_project_config_dir_then_returns_dot_fs2(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: Project config dir is .fs2 relative to CWD.
        Quality Contribution: Consistent project-local config location.
        """
        # Arrange
        monkeypatch.chdir(tmp_path)

        # Act
        from fs2.config.paths import get_project_config_dir

        result = get_project_config_dir()

        # Assert
        assert result == tmp_path / ".fs2"

    def test_given_project_config_dir_when_called_then_returns_path_object(
        self, monkeypatch, tmp_path
    ):
        """
        Purpose: Return type is Path, not string.
        Quality Contribution: Type safety.
        """
        # Arrange
        monkeypatch.chdir(tmp_path)

        # Act
        from fs2.config.paths import get_project_config_dir

        result = get_project_config_dir()

        # Assert
        assert isinstance(result, Path)
