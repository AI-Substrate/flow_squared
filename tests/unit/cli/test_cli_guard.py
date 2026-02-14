"""Tests for CLI guard (require init).

Full TDD tests for the CLI guard covering:
- T017: scan/search/tree/mcp fail without .fs2/config.yaml
- T017: init/doctor/--help always work
- T017: error shows PWD and .git warning
"""

import pytest
from typer.testing import CliRunner

pytestmark = pytest.mark.slow

runner = CliRunner()


class TestGuardBlocksUninitialized:
    """T017: Tests that commands fail without .fs2/config.yaml."""

    def test_given_no_config_when_scan_then_fails(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies scan fails without init.
        Quality Contribution: Prevents accidental directory creation.
        Acceptance Criteria: AC-23 - Commands fail without .fs2/config.yaml.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        assert result.exit_code == 1
        assert "init" in result.stdout.lower()

    def test_given_no_config_when_tree_then_fails(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies tree fails without init.
        Quality Contribution: Prevents operations in wrong directory.
        Acceptance Criteria: AC-23 - Commands fail without .fs2/config.yaml.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 1
        assert "init" in result.stdout.lower()

    def test_given_no_config_when_search_then_fails(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies search fails without init.
        Quality Contribution: Prevents operations in wrong directory.
        Acceptance Criteria: AC-23 - Commands fail without .fs2/config.yaml.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["search", "test"])

        assert result.exit_code == 1
        assert "init" in result.stdout.lower()

    def test_given_no_config_when_get_node_then_fails(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies get-node fails without init.
        Quality Contribution: Prevents operations in wrong directory.
        Acceptance Criteria: AC-23 - Commands fail without .fs2/config.yaml.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["get-node", "file:test.py"])

        assert result.exit_code == 1
        assert "init" in result.stdout.lower()


class TestGuardShowsPWD:
    """T017: Tests that guard shows current directory in error."""

    def test_given_no_config_when_command_fails_then_shows_cwd(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies error shows current directory.
        Quality Contribution: Helps user identify wrong directory.
        Acceptance Criteria: AC-24 - Error shows current directory path.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        assert result.exit_code == 1
        # Should show current directory or path component
        assert str(tmp_path) in result.stdout or "directory" in result.stdout.lower()

    def test_given_no_git_when_command_fails_then_shows_git_warning(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies error shows .git warning.
        Quality Contribution: Helps identify wrong directory.
        Acceptance Criteria: AC-26 - Shows red .git warning.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        # No .git folder

        result = runner.invoke(app, ["scan"])

        assert result.exit_code == 1
        stdout_lower = result.stdout.lower()
        assert ".git" in stdout_lower or "git" in stdout_lower


class TestGuardAllowsAlwaysWork:
    """T017: Tests that init/doctor/--help always work."""

    def test_given_no_config_when_init_then_succeeds(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies init works without existing config.
        Quality Contribution: Init is the bootstrap command.
        Acceptance Criteria: AC-27 - init always works.
        """
        from fs2.cli.main import app

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0

    def test_given_no_config_when_doctor_then_succeeds(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies doctor works without config.
        Quality Contribution: Doctor diagnoses config issues.
        Acceptance Criteria: AC-27 - doctor always works.
        """
        from fs2.cli.main import app

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        result = runner.invoke(app, ["doctor"])

        # Doctor should succeed (exit 0) even without config
        # It will just report missing configs
        assert result.exit_code == 0

    def test_given_no_config_when_help_then_succeeds(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies --help works without config.
        Quality Contribution: Help must always be accessible.
        Acceptance Criteria: AC-27 - --help always works.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "usage" in result.stdout.lower() or "commands" in result.stdout.lower()

    def test_given_no_config_when_scan_help_then_succeeds(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies scan --help works without config.
        Quality Contribution: Subcommand help must be accessible.
        Acceptance Criteria: AC-27 - subcommand --help works.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan", "--help"])

        assert result.exit_code == 0


class TestGuardNoAutoInit:
    """T017: Tests that commands don't auto-create .fs2/."""

    def test_given_no_config_when_scan_fails_then_no_fs2_created(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies scan doesn't create .fs2/ on failure.
        Quality Contribution: No implicit initialization.
        Acceptance Criteria: AC-28 - No auto-init behavior.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        assert result.exit_code == 1
        # .fs2/ should NOT be created
        assert not (tmp_path / ".fs2").exists()
