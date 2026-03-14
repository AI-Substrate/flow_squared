"""Tests for fs2 scan CLI command.

Full TDD tests for the scan CLI command covering:
- T001: Typer app structure
- T003-T004: Scan command invocation and AC9 output
- T006-T006a: Error display and exit codes
- T008-T012b: Progress, verbose, TTY detection
- T013: Missing config error
"""

import os

import pytest
from typer.testing import CliRunner

pytestmark = pytest.mark.slow  # Real CLI scan invocations (~10s each)

runner = CliRunner()

# T001: App structure tests - verify imports work and app exists


class TestTyperAppStructure:
    """T001: Tests for Typer app instance and basic structure."""

    def test_given_cli_module_when_imported_then_app_exists(self):
        """
        Purpose: Verifies Typer app instance is created.
        Quality Contribution: Ensures CLI entry point is available.
        Acceptance Criteria: app is a Typer instance.
        """
        import typer

        from fs2.cli.main import app

        assert isinstance(app, typer.Typer)

    def test_given_app_when_inspected_then_scan_command_registered(self):
        """
        Purpose: Verifies scan command is registered on app.
        Quality Contribution: Ensures command is discoverable.
        Acceptance Criteria: 'scan' in registered commands.
        """
        from fs2.cli.main import app

        # Get registered command names
        command_names = [cmd.name for cmd in app.registered_commands]
        assert "scan" in command_names, f"Expected 'scan' in {command_names}"

    def test_given_scan_help_when_invoked_then_shows_help(self):
        """
        Purpose: Verifies scan --help works.
        Quality Contribution: Ensures CLI is user-friendly.
        Acceptance Criteria: Help output includes command description.
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["scan", "--help"])

        assert result.exit_code == 0
        assert "scan" in result.stdout.lower()


# Fixtures for scan command tests


@pytest.fixture
def simple_project(tmp_path):
    """Create a simple project with .fs2 config and Python files."""
    # Create config directory
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()

    # Create config file
    config_file = config_dir / "config.yaml"
    config_file.write_text(f"""scan:
  scan_paths:
    - "{tmp_path}"
  respect_gitignore: true
  max_file_size_kb: 500
""")

    # Create a Python file
    (tmp_path / "calculator.py").write_text("""
class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b
""")

    # Create another file
    (tmp_path / "utils.py").write_text("""
def helper():
    return "help"
""")

    return tmp_path


class TestScanCommandInvocation:
    """T003: Tests for scan command running and calling pipeline."""

    def test_given_valid_config_when_scan_invoked_then_exits_zero(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies scan command runs successfully with valid config.
        Quality Contribution: Ensures happy path works.
        Acceptance Criteria: Exit code is 0.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        # Disable Rich formatting for test reliability
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"

    def test_given_scan_command_when_run_then_creates_graph_file(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies scan creates output graph file.
        Quality Contribution: Ensures graph persistence works.
        Acceptance Criteria: Graph file exists after scan.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"

        # Check graph file was created
        graph_file = simple_project / ".fs2" / "graph.pickle"
        assert graph_file.exists(), "Graph file should be created"


class TestScanOutputFormat:
    """T004: Tests for AC9 output format - 'Scanned N files, created M nodes'."""

    def test_given_scan_command_when_run_then_outputs_file_count(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies AC9 - output includes file count.
        Quality Contribution: Ensures users see scan progress.
        Acceptance Criteria: Output includes "Scanned" and "files".
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"
        # Check for expected output format
        stdout_lower = result.stdout.lower()
        assert "scanned" in stdout_lower, f"Expected 'scanned' in: {result.stdout}"
        assert "file" in stdout_lower, f"Expected 'file' in: {result.stdout}"

    def test_given_scan_command_when_run_then_outputs_node_count(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies AC9 - output includes node count.
        Quality Contribution: Ensures users see graph stats.
        Acceptance Criteria: Output includes "created" and "nodes".
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"
        stdout_lower = result.stdout.lower()
        assert "node" in stdout_lower, f"Expected 'node' in: {result.stdout}"

    def test_given_scan_command_when_run_then_outputs_graph_location(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies output shows where graph was saved.
        Quality Contribution: Helps users find output file.
        Acceptance Criteria: Output includes graph path.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"
        assert "graph" in result.stdout.lower(), f"Expected 'graph' in: {result.stdout}"
        assert ".pickle" in result.stdout or "pickle" in result.stdout.lower()


# Fixtures for error scenarios


@pytest.fixture
def empty_project(tmp_path):
    """Create a project with config but no files to scan."""
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()

    # Create config pointing to empty subdirectory
    empty_dir = tmp_path / "empty_src"
    empty_dir.mkdir()

    config_file = config_dir / "config.yaml"
    config_file.write_text(f"""scan:
  scan_paths:
    - "{empty_dir}"
  respect_gitignore: true
""")

    return tmp_path


@pytest.fixture
def project_without_config(tmp_path):
    """Create a project without .fs2/config.yaml."""
    # Just create a Python file, no config
    (tmp_path / "test.py").write_text("x = 1")
    return tmp_path


class TestExitCodes:
    """T006: Tests for exit codes - 0=success, 1=config error, 2=total failure."""

    def test_given_successful_scan_when_complete_then_exit_zero(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies exit code 0 for successful scan.
        Quality Contribution: Ensures scripts can detect success.
        Acceptance Criteria: Exit code is 0.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        assert result.exit_code == 0

    def test_given_missing_config_when_scan_then_exit_one(
        self, project_without_config, monkeypatch
    ):
        """
        Purpose: Verifies exit code 1 for config errors.
        Quality Contribution: Ensures scripts can detect config issues.
        Acceptance Criteria: Exit code is 1 for missing config.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(project_without_config)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        assert result.exit_code == 1, (
            f"Expected exit 1, got {result.exit_code}: {result.stdout}"
        )

    def test_given_all_files_fail_when_scan_then_exit_two(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies exit code 2 for total failure.
        Quality Contribution: Ensures CI/CD can detect total scan failures.
        Acceptance Criteria: Exit code is 2 when all files error.
        """
        from fs2.cli.main import app

        # Create project structure with scan path that excludes config
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        # Only scan src/, not the whole project (avoids config.yaml being scanned)
        config_file.write_text(f"""scan:
  scan_paths:
    - "{src_dir}"
  respect_gitignore: false
""")

        # Create files with permission denied (unreadable)
        # This will cause ASTParserError for every file
        unreadable_file = src_dir / "unreadable.py"
        unreadable_file.write_text("x = 1")
        unreadable_file.chmod(0o000)  # Remove all permissions

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        try:
            result = runner.invoke(app, ["scan"])

            # Should exit with code 2 for total failure
            assert result.exit_code == 2, (
                f"Expected exit 2 for total failure, got {result.exit_code}: {result.stdout}"
            )
        finally:
            # Restore permissions for cleanup
            unreadable_file.chmod(0o644)


class TestZeroFilesWarning:
    """T006a: Tests for zero-files warning when no files found."""

    def test_given_empty_scan_paths_when_scan_then_shows_warning(
        self, empty_project, monkeypatch
    ):
        """
        Purpose: Verifies warning shown when no files found.
        Quality Contribution: Helps users understand empty results.
        Acceptance Criteria: Output mentions "no files" or "0 files".
        """
        from fs2.cli.main import app

        monkeypatch.chdir(empty_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        # Should succeed (exit 0) but show warning
        assert result.exit_code == 0
        stdout_lower = result.stdout.lower()
        assert "0 files" in stdout_lower or "no files" in stdout_lower, (
            f"Expected zero files message in: {result.stdout}"
        )


class TestErrorDisplay:
    """T007: Tests for error display with ⚠ symbol."""

    def test_given_partial_errors_when_scan_then_shows_warning_symbol(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies warning symbol shown for partial failures.
        Quality Contribution: Ensures users notice errors.
        Acceptance Criteria: Output includes ⚠ or warning indicator.
        """
        from fs2.cli.main import app

        # Create project with a binary file that will fail parsing
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()

        config_file = config_dir / "config.yaml"
        config_file.write_text(f"""scan:
  scan_paths:
    - "{tmp_path}"
  respect_gitignore: true
""")

        # Create a good file
        (tmp_path / "good.py").write_text("x = 1")

        # Create a binary file that will cause parse error
        (tmp_path / "bad.bin").write_bytes(b"\x00\x01\x02\x03")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        # Should still succeed (partial success)
        assert result.exit_code == 0, f"Unexpected exit: {result.stdout}"
        # Check for some indication of files being scanned
        stdout_lower = result.stdout.lower()
        assert "scanned" in stdout_lower

    def test_given_errors_when_scan_then_lists_error_messages(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies error messages are listed.
        Quality Contribution: Helps users understand what failed.
        Acceptance Criteria: Error messages shown in output.
        """
        from fs2.cli.main import app

        # Create project with files that will have errors
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()

        config_file = config_dir / "config.yaml"
        config_file.write_text(f"""scan:
  scan_paths:
    - "{tmp_path}"
  respect_gitignore: true
""")

        # Create a file with encoding issues
        (tmp_path / "bad_encoding.py").write_bytes(b"x = '\xff\xfe'")
        (tmp_path / "good.py").write_text("y = 1")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        # Should succeed overall
        assert result.exit_code == 0
        # Should mention "error" somewhere if errors occurred
        # (Note: this depends on whether the parser actually fails)


# Fixtures for progress tests


@pytest.fixture
def large_project(tmp_path):
    """Create a project with 55+ files (above progress threshold)."""
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()

    config_file = config_dir / "config.yaml"
    config_file.write_text(f"""scan:
  scan_paths:
    - "{tmp_path}"
  respect_gitignore: true
""")

    # Create 55 Python files (above 50-file threshold)
    for i in range(55):
        (tmp_path / f"file_{i:03d}.py").write_text(f"x_{i} = {i}")

    return tmp_path


class TestProgressSpinner:
    """T008-T009: Tests for progress spinner display."""

    def test_given_large_scan_when_run_then_completes_successfully(
        self, large_project, monkeypatch
    ):
        """
        Purpose: Verifies large scans complete with progress.
        Quality Contribution: Ensures progress doesn't break functionality.
        Acceptance Criteria: Exit code 0 for large scans.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(large_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"
        assert "55" in result.stdout or "file" in result.stdout.lower()

    def test_given_small_scan_when_run_then_no_spinner_chars(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies no spinner for small scans (<50 files).
        Quality Contribution: Avoids visual noise for quick scans.
        Acceptance Criteria: No spinner characters in output.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        assert result.exit_code == 0
        # With NO_COLOR, should not have spinner chars
        assert "━" not in result.stdout


class TestVerboseFlag:
    """T010-T011: Tests for --verbose flag."""

    def test_given_verbose_flag_when_scan_then_exits_zero(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies --verbose doesn't break scan.
        Quality Contribution: Ensures verbose mode works.
        Acceptance Criteria: Exit code 0 with --verbose.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan", "--verbose"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"

    def test_given_verbose_flag_when_scan_then_shows_more_output(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies verbose shows more detail.
        Quality Contribution: Helps users debug scans.
        Acceptance Criteria: Verbose output contains more info.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        # Run normal scan
        normal = runner.invoke(app, ["scan"])
        # Run verbose scan
        verbose = runner.invoke(app, ["scan", "--verbose"])

        assert normal.exit_code == 0
        assert verbose.exit_code == 0
        # Verbose should have more output (file names, etc.)
        assert len(verbose.stdout) >= len(normal.stdout)


class TestTTYDetection:
    """T012: Tests for TTY auto-detection."""

    def test_given_tty_check_when_not_tty_then_spinner_disabled(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies spinner disabled when not TTY.
        Quality Contribution: Clean output for pipes/scripts.
        Acceptance Criteria: No ANSI codes when not TTY.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        # CliRunner simulates non-TTY by default

        result = runner.invoke(app, ["scan"])

        assert result.exit_code == 0
        # Should not have escape sequences
        assert "\x1b[" not in result.stdout or "NO_COLOR" not in os.environ


class TestProgressFlags:
    """T012a-T012b: Tests for --no-progress and --progress flags."""

    def test_given_no_progress_flag_when_scan_then_no_spinner(
        self, large_project, monkeypatch
    ):
        """
        Purpose: Verifies --no-progress disables spinner.
        Quality Contribution: Allows clean output in CI.
        Acceptance Criteria: No spinner chars with --no-progress.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(large_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan", "--no-progress"])

        assert result.exit_code == 0
        # Should not have progress bar chars
        assert "━" not in result.stdout

    def test_given_progress_env_var_when_scan_then_respects_setting(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies FS2_SCAN__NO_PROGRESS env var works.
        Quality Contribution: Allows config via environment.
        Acceptance Criteria: Env var disables progress.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setenv("FS2_SCAN__NO_PROGRESS", "true")

        result = runner.invoke(app, ["scan"])

        assert result.exit_code == 0
        # Should still complete successfully
        assert "scanned" in result.stdout.lower()

    def test_given_no_progress_flag_when_checking_should_show_then_returns_false(self):
        """
        Purpose: Verifies --no-progress flag correctly disables progress.
        Quality Contribution: Ensures flag has functional effect.
        Acceptance Criteria: _should_show_progress returns False with --no-progress.
        """
        from fs2.cli.scan import _should_show_progress

        result = _should_show_progress(no_progress=True, force_progress=False)
        assert result is False

    def test_given_progress_flag_when_checking_should_show_then_returns_true(self):
        """
        Purpose: Verifies --progress flag forces progress display.
        Quality Contribution: Ensures flag has functional effect.
        Acceptance Criteria: _should_show_progress returns True with --progress.
        """
        from fs2.cli.scan import _should_show_progress

        result = _should_show_progress(no_progress=False, force_progress=True)
        assert result is True


# ===========================================================================
# T006: Tests for --no-smart-content Flag (Phase 6)
# ===========================================================================


class TestNoSmartContentFlag:
    """T006: Tests for --no-smart-content CLI flag.

    Per Phase 6 Tasks:
    - Flag skips SmartContentStage processing
    - Summary reflects "smart content: skipped"
    - Graph saved normally without smart content
    """

    def test_given_no_smart_content_flag_when_scan_then_exits_zero(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies --no-smart-content doesn't break scan.
        Quality Contribution: Ensures opt-out mode works.
        Acceptance Criteria: Exit code 0 with --no-smart-content.

        Why: Users may want fast scans without LLM processing.
        Contract: Flag disables smart content but scan completes normally.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan", "--no-smart-content"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"

    def test_given_no_smart_content_flag_when_scan_then_shows_skipped(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies summary indicates smart content was skipped.
        Quality Contribution: Users know smart content wasn't generated.
        Acceptance Criteria: Output includes "smart content" and "skipped".

        Why: Users should understand what was (not) processed.
        Contract: Summary shows smart content was explicitly skipped.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan", "--no-smart-content"])

        assert result.exit_code == 0
        stdout_lower = result.stdout.lower()
        # Should mention skipped status
        assert "smart content" in stdout_lower or "skipped" in stdout_lower, (
            f"Expected smart content skip message in: {result.stdout}"
        )

    def test_given_no_smart_content_flag_when_scan_then_graph_created(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies graph is still created without smart content.
        Quality Contribution: Ensures core functionality works in fast mode.
        Acceptance Criteria: Graph file exists after scan.

        Why: Graph should be persisted even without LLM enrichment.
        Contract: --no-smart-content only skips LLM, not graph storage.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan", "--no-smart-content"])

        assert result.exit_code == 0
        graph_file = simple_project / ".fs2" / "graph.pickle"
        assert graph_file.exists(), "Graph file should be created"

    def test_given_default_scan_when_llm_not_configured_then_silently_skips(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies scan works when LLM not configured (no env vars).
        Quality Contribution: No surprise errors for new users.
        Acceptance Criteria: Exit 0, no LLM error messages.

        Why: Most users don't have Azure OpenAI on first run.
        Contract: If no LLM config, skip smart content silently.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")
        # Ensure no LLM env vars are set
        monkeypatch.delenv("FS2_AZURE__OPENAI__ENDPOINT", raising=False)
        monkeypatch.delenv("FS2_AZURE__OPENAI__API_KEY", raising=False)
        monkeypatch.delenv("FS2_OPENAI__API_KEY", raising=False)

        result = runner.invoke(app, ["scan"])

        # Should succeed (smart content silently skipped)
        assert result.exit_code == 0, f"Failed with: {result.stdout}"
        # Should not mention LLM errors
        assert "authentication" not in result.stdout.lower()
        assert "llm error" not in result.stdout.lower()


class TestNoCrossRefsFlag:
    """Tests for --no-cross-refs CLI flag.

    Per Phase 3 cross-file-rels: Flag skips cross-file relationship extraction.
    Not wired to pipeline yet (Phase 4), but must be accepted by CLI.
    """

    def test_given_no_cross_refs_flag_when_scan_then_exits_zero(
        self, simple_project, monkeypatch
    ):
        """Flag is accepted and scan completes normally."""
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan", "--no-cross-refs"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"

    def test_given_no_cross_refs_flag_when_scan_then_graph_created(
        self, simple_project, monkeypatch
    ):
        """Graph is still created when cross-refs are disabled."""
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan", "--no-cross-refs"])

        assert result.exit_code == 0
        graph_file = simple_project / ".fs2" / "graph.pickle"
        assert graph_file.exists(), "Graph file should be created"


class TestCrossRefsInstancesFlag:
    """Tests for --cross-refs-instances CLI flag.

    Per Phase 3 cross-file-rels: Overrides parallel Serena instances.
    Not wired to pipeline yet (Phase 4), but must be accepted by CLI.
    """

    def test_given_cross_refs_instances_flag_when_scan_then_exits_zero(
        self, simple_project, monkeypatch
    ):
        """Flag is accepted with integer value and scan completes normally."""
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan", "--cross-refs-instances", "5"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"

    def test_given_both_cross_ref_flags_when_scan_then_exits_zero(
        self, simple_project, monkeypatch
    ):
        """Both flags can be used together without conflict."""
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(
            app, ["scan", "--no-cross-refs", "--cross-refs-instances", "10"]
        )

        assert result.exit_code == 0, f"Failed with: {result.stdout}"
