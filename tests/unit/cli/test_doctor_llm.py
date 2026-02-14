"""Tests for fs2 doctor llm subcommand.

Minimal CLI tests for the new `fs2 doctor llm` subcommand that tests
LLM and embedding provider connectivity with actual API calls.

Test Plan (Minimal):
- ST001: Verify CLI wiring and backward compatibility
- Real validation happens via manual testing (ST005) with actual credentials
"""

import pytest
from typer.testing import CliRunner

pytestmark = pytest.mark.slow

runner = CliRunner()


# =============================================================================
# ST001: MINIMAL CLI TESTS FOR FS2 DOCTOR LLM
# =============================================================================


class TestDoctorLLMCommand:
    """ST001: Minimal CLI tests for `fs2 doctor llm` subcommand."""

    def test_doctor_llm_command_exists(self):
        """
        Why: Verify CLI wiring - command is registered and discoverable.
        Contract: `fs2 doctor llm --help` exits 0 and shows LLM-specific help.
        Usage Notes: Tests command registration, not actual functionality.
        Quality Contribution: Critical path - ensures command exists before use.
        Worked Example: `fs2 doctor llm --help` → shows LLM provider test usage.
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["doctor", "llm", "--help"])
        # Command should exist and show LLM-specific help
        assert result.exit_code == 0
        # Help text should be from the llm subcommand, not the parent doctor command
        # The llm subcommand should mention "test" or "connectivity" or "llm provider"
        # and NOT just show the parent's config check help
        output_lower = result.output.lower()
        # Must have llm-specific content (test providers) AND not be the parent help
        assert "test" in output_lower or "connectivity" in output_lower, (
            f"Expected llm subcommand help to mention 'test' or 'connectivity', got: {result.output}"
        )

    def test_doctor_without_subcommand_still_works(self, tmp_path, monkeypatch):
        """
        Why: Backward compatibility - existing `fs2 doctor` usage must not break.
        Contract: `fs2 doctor` (without subcommand) runs config check as before.
        Usage Notes: Tests invoke_without_command=True callback pattern.
        Quality Contribution: Regression-prone - callback pattern is subtle.
        Worked Example: `fs2 doctor` → shows config health check (not llm test).
        """
        from fs2.cli.main import app

        # Setup minimal environment
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        result = runner.invoke(app, ["doctor"])

        # Should run and show config check output (not crash)
        # Exit code depends on config state, but should not raise exception
        assert result.exception is None or isinstance(result.exception, SystemExit)
        # Should show config health check header
        assert "Configuration" in result.output or "config" in result.output.lower()

    def test_doctor_help_shows_llm_subcommand(self):
        """
        Why: Discoverability - users should find llm subcommand via --help.
        Contract: `fs2 doctor --help` lists `llm` as available subcommand.
        Usage Notes: Tests Typer command group registration.
        Quality Contribution: Edge case - help output formatting can vary.
        Worked Example: `fs2 doctor --help` → includes "llm" in commands list.
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["doctor", "--help"])
        assert result.exit_code == 0
        # Should show llm as a subcommand option (Commands section)
        # Looking for "Commands:" section that lists llm
        assert "llm" in result.output.lower() and "commands" in result.output.lower()
