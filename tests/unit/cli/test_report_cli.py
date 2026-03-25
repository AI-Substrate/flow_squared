"""Tests for fs2 report CLI command.

Covers:
- Command and subcommand registration and --help
- Missing graph error handling (exit 1)
- Report generation with a scanned graph
- Custom --output path
- --no-smart-content flag
- --graph-file global option
"""

import re

import pytest
from typer.testing import CliRunner

pytestmark = pytest.mark.slow

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from Rich/Typer output."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


@pytest.mark.unit
class TestReportHelp:
    """Report command registration and help output."""

    def test_report_help_shows_codebase_graph(self):
        from fs2.cli.main import app

        result = runner.invoke(app, ["report", "--help"])
        assert result.exit_code == 0
        assert "codebase-graph" in result.stdout

    def test_codebase_graph_help_shows_flags(self):
        from fs2.cli.main import app

        result = runner.invoke(app, ["report", "codebase-graph", "--help"])
        assert result.exit_code == 0
        text = _strip_ansi(result.stdout)
        assert "--output" in text
        assert "--open" in text
        assert "--no-smart-content" in text


@pytest.mark.unit
class TestReportMissingGraph:
    """Missing graph exits with non-zero."""

    def test_missing_graph_file_exits_nonzero(self, tmp_path, monkeypatch):
        from fs2.cli.main import app

        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(
            app,
            [
                "--graph-file",
                str(tmp_path / "does-not-exist.pickle"),
                "report",
                "codebase-graph",
            ],
        )
        assert result.exit_code != 0

    def test_no_graph_no_config_exits_nonzero(self, tmp_path, monkeypatch):
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["report", "codebase-graph"])
        assert result.exit_code != 0


@pytest.mark.unit
class TestReportGeneration:
    """Report generation with a valid graph."""

    def test_default_output_creates_html(self, scanned_project, monkeypatch):
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["report", "codebase-graph"])
        assert result.exit_code == 0, f"Failed: {result.stdout}"

        output_file = scanned_project / ".fs2" / "reports" / "codebase-graph.html"
        assert output_file.exists()
        html = output_file.read_text(encoding="utf-8")
        assert "GRAPH_DATA" in html

    def test_custom_output_path(self, scanned_project, monkeypatch):
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")
        custom = scanned_project / "my-report.html"

        result = runner.invoke(
            app, ["report", "codebase-graph", "--output", str(custom)]
        )
        assert result.exit_code == 0, f"Failed: {result.stdout}"
        assert custom.exists()

    def test_no_smart_content_excludes_field(self, scanned_project, monkeypatch):
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")
        out = scanned_project / "nosmart.html"

        result = runner.invoke(
            app,
            ["report", "codebase-graph", "--no-smart-content", "--output", str(out)],
        )
        assert result.exit_code == 0, f"Failed: {result.stdout}"
        html = out.read_text(encoding="utf-8")
        assert '"smart_content"' not in html


@pytest.mark.unit
class TestReportWithGraphFile:
    """--graph-file global option support."""

    def test_explicit_graph_file_succeeds(self, scanned_project, monkeypatch):
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")
        graph_path = scanned_project / ".fs2" / "graph.pickle"
        out = scanned_project / "from-explicit.html"

        result = runner.invoke(
            app,
            [
                "--graph-file",
                str(graph_path),
                "report",
                "codebase-graph",
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 0, f"Failed: {result.stdout}"
        assert out.exists()
