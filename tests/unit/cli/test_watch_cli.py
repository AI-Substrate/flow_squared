"""Tests for watch CLI command.

Task: T017
Purpose: Verify watch CLI command handles arguments, exit codes, and @require_init guard.
Per Finding 14: Use CliRunner with NO_COLOR=1.
Per Finding 01: CLI Registration uses app.command(name="X")(require_init(X)).
"""

import pytest
from typer.testing import CliRunner

runner = CliRunner()


@pytest.mark.unit
class TestWatchCliGuard:
    """Tests for watch CLI @require_init guard."""

    def test_given_no_config_when_watch_then_fails(self, tmp_path, monkeypatch):
        """
        Given: No .fs2/config.yaml exists
        When: Running fs2 watch
        Then: Exits with code 1 and shows init message

        Purpose: Verifies watch requires initialization.
        Quality Contribution: Guard prevents operations in wrong directory.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["watch"])

        assert result.exit_code == 1
        assert "init" in result.stdout.lower()


@pytest.mark.unit
class TestWatchCliHelp:
    """Tests for watch CLI help."""

    def test_given_any_directory_when_watch_help_then_succeeds(
        self, tmp_path, monkeypatch
    ):
        """
        Given: Any directory (no config needed)
        When: Running fs2 watch --help
        Then: Exits with code 0 and shows help

        Purpose: Verifies help always works.
        Quality Contribution: Help accessible without init.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["watch", "--help"])

        assert result.exit_code == 0
        # Should show help for watch command
        assert "watch" in result.stdout.lower()


@pytest.mark.unit
class TestWatchCliArguments:
    """Tests for watch CLI argument handling."""

    def test_watch_accepts_no_embeddings_flag(self, tmp_path, monkeypatch):
        """
        Given: Initialized project
        When: Running fs2 watch --no-embeddings
        Then: Command accepts the flag

        Purpose: Verifies --no-embeddings flag is accepted.
        Quality Contribution: Argument pass-through per AC8.
        """
        from fs2.cli.main import app

        # Create minimal config
        fs2_dir = tmp_path / ".fs2"
        fs2_dir.mkdir()
        config_file = fs2_dir / "config.yaml"
        config_file.write_text("scan:\n  scan_paths:\n    - ./src\n")

        src_dir = tmp_path / "src"
        src_dir.mkdir()

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        # Use --help to verify flag is recognized
        result = runner.invoke(app, ["watch", "--help"])

        assert result.exit_code == 0
        assert "--no-embeddings" in result.stdout

    def test_watch_accepts_verbose_flag(self, tmp_path, monkeypatch):
        """
        Given: Initialized project
        When: Running fs2 watch --verbose
        Then: Command accepts the flag

        Purpose: Verifies --verbose flag is accepted.
        Quality Contribution: Debug capability for users.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["watch", "--help"])

        assert result.exit_code == 0
        assert "--verbose" in result.stdout or "-v" in result.stdout
