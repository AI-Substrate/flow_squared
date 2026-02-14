"""Tests for fs2 agents-start-here CLI command.

Full TDD tests covering:
- AC-1: Works before init (exit 0, shows status + next step)
- AC-2: Output adapts across 5 project states
- AC-8: Command is unguarded (no require_init)
- AC-10: State 5 (fully configured) points to MCP
"""

import pytest
from typer.testing import CliRunner

pytestmark = pytest.mark.slow
runner = CliRunner()


class TestAgentsStartHereRegistered:
    """AC-8: Command is unguarded and registered."""

    def test_given_app_when_inspected_then_command_registered(self):
        """
        Purpose: Proves agents-start-here is registered in the CLI app.
        Quality Contribution: Command must be discoverable via fs2 --help.
        Acceptance Criteria: "agents-start-here" in registered command names.
        """
        from fs2.cli.main import app

        names = [c.name for c in app.registered_commands]
        assert "agents-start-here" in names

    def test_given_no_config_when_invoked_then_exits_zero(self, tmp_path, monkeypatch):
        """
        Purpose: Proves command works before fs2 init (unguarded).
        Quality Contribution: Agents can orient without any setup.
        Acceptance Criteria: AC-8 - exit code 0 with no .fs2/ directory.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["agents-start-here"])
        assert result.exit_code == 0


class TestAgentsStartHereState1:
    """AC-1: State 1 - Nothing set up, points to fs2 init."""

    def test_given_no_fs2_dir_when_invoked_then_shows_description(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves command describes what fs2 is.
        Quality Contribution: Agents learn what fs2 does.
        Acceptance Criteria: AC-1 - output describes fs2.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["agents-start-here"])
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "fs2" in output_lower
        assert "code" in output_lower or "codebase" in output_lower

    def test_given_no_fs2_dir_when_invoked_then_shows_not_initialized(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves State 1 shows project is not initialized.
        Quality Contribution: Agents know current status.
        Acceptance Criteria: AC-1 - shows "not initialized" or similar.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["agents-start-here"])
        assert result.exit_code == 0
        assert "not initialized" in result.output.lower() or "fs2 init" in result.output

    def test_given_no_fs2_dir_when_invoked_then_next_step_is_init(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves State 1 points to fs2 init as next step.
        Quality Contribution: Agents know exactly what to do next.
        Acceptance Criteria: AC-1 - next step mentions fs2 init.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["agents-start-here"])
        assert result.exit_code == 0
        assert "fs2 init" in result.output


class TestAgentsStartHereState2:
    """AC-2: State 2 - Initialized without providers."""

    def test_given_config_no_providers_when_invoked_then_suggests_config(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves State 2 suggests configuring providers.
        Quality Contribution: Agents know providers are optional but available.
        Acceptance Criteria: AC-2 - points to configuration guide.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        # State 2: config exists, no providers
        fs2_dir = tmp_path / ".fs2"
        fs2_dir.mkdir()
        config = fs2_dir / "config.yaml"
        config.write_text("scan:\n  scan_paths: ['.']\n")

        result = runner.invoke(app, ["agents-start-here"])
        assert result.exit_code == 0
        # Should suggest scanning or configuring providers
        assert (
            "scan" in result.output.lower() or "configuration" in result.output.lower()
        )


class TestAgentsStartHereState3:
    """AC-2: State 3 - Initialized with providers, not scanned."""

    def test_given_config_with_providers_when_invoked_then_suggests_scan(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves State 3 suggests scanning.
        Quality Contribution: Agents know to scan after configuring.
        Acceptance Criteria: AC-2 - points to fs2 scan or fs2 doctor.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        # State 3: config with providers, no graph
        fs2_dir = tmp_path / ".fs2"
        fs2_dir.mkdir()
        config = fs2_dir / "config.yaml"
        config.write_text(
            "scan:\n  scan_paths: ['.']\n"
            "llm:\n  provider: azure\n"
            "embedding:\n  mode: azure\n"
        )

        result = runner.invoke(app, ["agents-start-here"])
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "scan" in output_lower or "doctor" in output_lower


class TestAgentsStartHereState4:
    """AC-2: State 4 - Scanned without providers."""

    def test_given_graph_no_providers_when_invoked_then_points_to_mcp(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves State 4 points to MCP setup.
        Quality Contribution: Scanned project should set up MCP next.
        Acceptance Criteria: AC-2 - mentions MCP.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        # State 4: config + graph, no providers
        fs2_dir = tmp_path / ".fs2"
        fs2_dir.mkdir()
        config = fs2_dir / "config.yaml"
        config.write_text("scan:\n  scan_paths: ['.']\n")
        graph = fs2_dir / "graph.pickle"
        graph.write_bytes(b"fake")

        result = runner.invoke(app, ["agents-start-here"])
        assert result.exit_code == 0
        assert "mcp" in result.output.lower()


class TestAgentsStartHereState5:
    """AC-10: State 5 - Fully configured, points to MCP."""

    def test_given_fully_configured_when_invoked_then_points_to_mcp(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves State 5 points to MCP as next step.
        Quality Contribution: Fully configured agents should connect MCP.
        Acceptance Criteria: AC-10 - mentions MCP and mcp-server-guide.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        # State 5: config + graph + providers
        fs2_dir = tmp_path / ".fs2"
        fs2_dir.mkdir()
        config = fs2_dir / "config.yaml"
        config.write_text(
            "scan:\n  scan_paths: ['.']\n"
            "llm:\n  provider: azure\n"
            "embedding:\n  mode: azure\n"
        )
        graph = fs2_dir / "graph.pickle"
        graph.write_bytes(b"fake")

        result = runner.invoke(app, ["agents-start-here"])
        assert result.exit_code == 0
        assert "mcp" in result.output.lower()

    def test_given_fully_configured_when_invoked_then_mentions_mcp_guide(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves State 5 references the MCP server guide doc.
        Quality Contribution: Agents know where to find MCP setup instructions.
        Acceptance Criteria: AC-10 - output mentions mcp-server-guide.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        # State 5: config + graph + providers
        fs2_dir = tmp_path / ".fs2"
        fs2_dir.mkdir()
        config = fs2_dir / "config.yaml"
        config.write_text(
            "scan:\n  scan_paths: ['.']\n"
            "llm:\n  provider: azure\n"
            "embedding:\n  mode: azure\n"
        )
        graph = fs2_dir / "graph.pickle"
        graph.write_bytes(b"fake")

        result = runner.invoke(app, ["agents-start-here"])
        assert result.exit_code == 0
        assert "mcp-server-guide" in result.output


class TestAgentsStartHereDocsBrowse:
    """Command should include documentation browsing hints."""

    def test_given_any_state_when_invoked_then_mentions_docs_command(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Proves output always tells agents about fs2 docs.
        Quality Contribution: Agents learn to browse docs via CLI.
        Acceptance Criteria: Output includes fs2 docs reference.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["agents-start-here"])
        assert result.exit_code == 0
        assert "fs2 docs" in result.output
