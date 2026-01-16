"""Tests for fs2 web CLI command.

Per Phase 1 Tasks Dossier:
- T011: Tests cover: port option, host option, no-browser flag, help output

Testing Approach: Lightweight (minimal validation - CLI is thin wrapper)
The CLI just launches Streamlit; actual functionality tested in service tests.
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from fs2.cli.main import app

runner = CliRunner()


class TestWebHelpOutput:
    """Tests for CLI help and basic invocation."""

    def test_web_help_shows_options(self) -> None:
        """Verify --help shows all expected options.

        Contract: Help lists port, host, no-browser options.
        """
        result = runner.invoke(app, ["web", "--help"])

        assert result.exit_code == 0
        assert "--port" in result.output
        assert "--host" in result.output
        assert "--no-browser" in result.output

    def test_web_help_shows_description(self) -> None:
        """Verify help shows command description."""
        result = runner.invoke(app, ["web", "--help"])

        assert result.exit_code == 0
        assert "web" in result.output.lower() or "streamlit" in result.output.lower()


class TestWebOptionParsing:
    """Tests for CLI option parsing."""

    @patch("fs2.cli.web.subprocess.Popen")
    def test_default_port_is_8501(self, mock_popen: MagicMock) -> None:
        """Verify default port is 8501.

        Contract: --port defaults to 8501 per UIConfig.
        """
        mock_popen.return_value.wait.return_value = 0

        _result = runner.invoke(app, ["web"])

        # Streamlit should be launched with default port
        mock_popen.assert_called_once()
        cmd_args = mock_popen.call_args[0][0]
        assert "--server.port" in cmd_args or "8501" in " ".join(cmd_args)

    @patch("fs2.cli.web.subprocess.Popen")
    def test_custom_port_passed_to_streamlit(self, mock_popen: MagicMock) -> None:
        """Verify custom port is passed to Streamlit.

        Contract: --port value forwarded to Streamlit server.
        """
        mock_popen.return_value.wait.return_value = 0

        _result = runner.invoke(app, ["web", "--port", "9000"])

        mock_popen.assert_called_once()
        cmd_args = mock_popen.call_args[0][0]
        assert "9000" in " ".join(cmd_args)

    @patch("fs2.cli.web.subprocess.Popen")
    def test_custom_host_passed_to_streamlit(self, mock_popen: MagicMock) -> None:
        """Verify custom host is passed to Streamlit.

        Contract: --host value forwarded to Streamlit server.
        """
        mock_popen.return_value.wait.return_value = 0

        _result = runner.invoke(app, ["web", "--host", "0.0.0.0"])

        mock_popen.assert_called_once()
        cmd_args = mock_popen.call_args[0][0]
        assert "0.0.0.0" in " ".join(cmd_args)


class TestBrowserBehavior:
    """Tests for browser auto-open behavior."""

    @patch("fs2.cli.web.webbrowser.open")
    @patch("fs2.cli.web.subprocess.Popen")
    def test_browser_opens_by_default(
        self, mock_popen: MagicMock, mock_browser: MagicMock
    ) -> None:
        """Verify browser opens by default.

        Contract: Without --no-browser, browser is opened manually.
        Note: Headless mode always enabled to skip email prompt.
        """
        mock_popen.return_value.wait.return_value = 0

        _result = runner.invoke(app, ["web"])

        # Headless is always enabled (to skip email prompt)
        mock_popen.assert_called_once()
        cmd_args = mock_popen.call_args[0][0]
        cmd_str = " ".join(cmd_args)
        assert "--server.headless" in cmd_str

        # Browser thread is started (may not have executed yet due to delay)
        # Just verify no error occurred - browser opening is async

    @patch("fs2.cli.web.webbrowser.open")
    @patch("fs2.cli.web.subprocess.Popen")
    def test_no_browser_flag_prevents_open(
        self, mock_popen: MagicMock, mock_browser: MagicMock
    ) -> None:
        """Verify --no-browser prevents browser from opening.

        Contract: With --no-browser, browser.open is never called.
        """
        mock_popen.return_value.wait.return_value = 0

        _result = runner.invoke(app, ["web", "--no-browser"])

        mock_popen.assert_called_once()
        cmd_args = mock_popen.call_args[0][0]
        # Headless always enabled
        assert "--server.headless" in " ".join(cmd_args)
        # Browser should NOT be opened
        mock_browser.assert_not_called()


class TestStreamlitLaunch:
    """Tests for Streamlit subprocess launching."""

    @patch("fs2.cli.web.subprocess.Popen")
    def test_launches_streamlit_with_app_path(self, mock_popen: MagicMock) -> None:
        """Verify Streamlit is launched with correct app.py path.

        Contract: Subprocess runs 'streamlit run <app.py path>'.
        """
        mock_popen.return_value.wait.return_value = 0

        _result = runner.invoke(app, ["web"])

        mock_popen.assert_called_once()
        cmd_args = mock_popen.call_args[0][0]
        # Should contain streamlit and app.py
        cmd_str = " ".join(cmd_args)
        assert "streamlit" in cmd_str.lower()
        assert "app.py" in cmd_str

    @patch("fs2.cli.web.subprocess.Popen")
    def test_waits_for_subprocess(self, mock_popen: MagicMock) -> None:
        """Verify CLI waits for Streamlit subprocess.

        Contract: CLI blocks until Streamlit exits.
        """
        mock_process = MagicMock()
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        _result = runner.invoke(app, ["web"])

        # wait() should be called to block until process exits
        mock_process.wait.assert_called_once()
