"""Tests for discover-projects and add-project CLI commands.

Uses typer test runner for CLI output assertions.
"""

import pytest
from typer.testing import CliRunner

from fs2.cli.main import app

runner = CliRunner()


@pytest.fixture()
def project_dir(tmp_path):
    """Create a temp directory with Python and TypeScript markers."""
    (tmp_path / "pyproject.toml").write_text("[build-system]")
    sub = tmp_path / "frontend"
    sub.mkdir()
    (sub / "tsconfig.json").write_text("{}")
    return tmp_path


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    import re

    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestDiscoverProjects:
    """Tests for fs2 discover-projects command."""

    def test_discovers_python_project(self, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        result = runner.invoke(app, ["discover-projects"])
        assert result.exit_code == 0
        assert "python" in result.stdout

    def test_discovers_typescript_project(self, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        result = runner.invoke(app, ["discover-projects"])
        assert result.exit_code == 0
        assert "typescript" in result.stdout

    def test_shows_project_count(self, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        result = runner.invoke(app, ["discover-projects"])
        assert "2 project(s)" in _strip_ansi(result.stdout)

    def test_json_output(self, project_dir, monkeypatch):
        import json

        monkeypatch.chdir(project_dir)
        result = runner.invoke(app, ["discover-projects", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "projects" in data
        assert data["count"] == 2

    def test_empty_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["discover-projects"])
        assert result.exit_code == 0
        assert "No language projects detected" in result.stdout

    def test_scan_path_option(self, project_dir):
        result = runner.invoke(
            app, ["discover-projects", "--scan-path", str(project_dir)]
        )
        assert result.exit_code == 0
        assert "python" in result.stdout


class TestAddProject:
    """Tests for fs2 add-project command."""

    def test_adds_project_by_number(self, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        (project_dir / ".fs2").mkdir()
        (project_dir / ".fs2" / "config.yaml").write_text("")

        # Discover first, then add
        runner.invoke(app, ["discover-projects"])
        result = runner.invoke(app, ["add-project", "1"])
        assert result.exit_code == 0
        assert "Added" in result.stdout

        # Verify config was written
        config = (project_dir / ".fs2" / "config.yaml").read_text()
        assert "python" in config
        assert "entries" in config

    def test_adds_all_projects(self, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        (project_dir / ".fs2").mkdir()
        (project_dir / ".fs2" / "config.yaml").write_text("")

        runner.invoke(app, ["discover-projects"])
        result = runner.invoke(app, ["add-project", "--all"])
        assert result.exit_code == 0
        assert "Wrote 2 project(s)" in _strip_ansi(result.stdout)

    def test_idempotent(self, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        (project_dir / ".fs2").mkdir()
        (project_dir / ".fs2" / "config.yaml").write_text("")

        runner.invoke(app, ["discover-projects"])
        runner.invoke(app, ["add-project", "--all"])
        # Run again — should skip all
        result = runner.invoke(app, ["add-project", "--all"])
        assert "already in config" in _strip_ansi(result.stdout)
        assert "No new projects to add" in _strip_ansi(result.stdout)

    def test_invalid_number(self, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        runner.invoke(app, ["discover-projects"])
        result = runner.invoke(app, ["add-project", "99"])
        assert result.exit_code == 1
        assert "Invalid project number" in result.stderr

    def test_no_args_shows_error(self, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        runner.invoke(app, ["discover-projects"])
        result = runner.invoke(app, ["add-project"])
        assert result.exit_code == 1

    def test_creates_config_dir_if_missing(self, project_dir, monkeypatch):
        monkeypatch.chdir(project_dir)
        # No .fs2 dir exists
        runner.invoke(app, ["discover-projects"])
        result = runner.invoke(app, ["add-project", "1"])
        assert result.exit_code == 0
        assert (project_dir / ".fs2" / "config.yaml").exists()
