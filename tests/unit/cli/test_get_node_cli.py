"""Tests for fs2 get-node CLI command.

Full TDD tests for the get-node CLI command covering:
- T001: Command registration and --help (AC8)
- T002: Valid node_id returns JSON, exit 0 (AC1, AC9)
- T003: Stdout is clean JSON only (AC2)
- T004: Pipe to jq works (AC3)
- T005: --file flag writes JSON to file (AC4)
- T006: Node not found returns exit 1 (AC5)
- T007: Missing graph returns exit 1 (AC6)
- T008: Corrupted graph returns exit 2 (AC7)
- T008a: Missing config returns exit 1, mentions "init"

Per plan-005: Full TDD approach - tests written before implementation.
"""

import json

import pytest
from typer.testing import CliRunner

runner = CliRunner()


# T001: Command registration and help tests


@pytest.mark.unit
class TestGetNodeHelp:
    """T001: Tests for get-node command registration and --help (AC8)."""

    def test_given_cli_app_when_inspected_then_get_node_command_registered(self):
        """
        Purpose: Verifies get-node command is registered on app.
        Quality Contribution: Ensures command is discoverable.
        Acceptance Criteria: 'get-node' in registered commands.

        Task: T001
        """
        from fs2.cli.main import app

        command_names = [cmd.name for cmd in app.registered_commands]
        assert "get-node" in command_names, f"Expected 'get-node' in {command_names}"

    def test_given_help_flag_when_get_node_then_shows_usage(self):
        """
        Purpose: Proves command is registered and help is accessible.
        Quality Contribution: Ensures discoverability.
        Acceptance Criteria: Exit 0, shows node_id and --file in output (AC8).

        Task: T001
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["get-node", "--help"])

        assert result.exit_code == 0
        # Should show node_id argument
        assert (
            "node_id" in result.stdout.lower() or "node-id" in result.stdout.lower()
        ), f"Expected 'node_id' in help output: {result.stdout}"
        # Should show --file option
        assert "--file" in result.stdout, f"Expected '--file' in help output: {result.stdout}"


# T002, T003, T004: Success and clean output tests


@pytest.mark.unit
class TestGetNodeSuccess:
    """T002: Tests for successful node retrieval (AC1, AC9)."""

    def test_given_valid_node_id_when_get_node_then_outputs_json(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves core retrieval returns valid JSON with essential fields.
        Quality Contribution: Validates primary use case.
        Acceptance Criteria: Exit 0, JSON contains essential CodeNode fields (AC1, AC9).

        Task: T002
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        # Use a known node_id from the scanned project - file node
        result = runner.invoke(app, ["get-node", "file:src/calculator.py"])

        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.stdout}"
        data = json.loads(result.stdout)

        # Check essential fields (resilient to CodeNode changes - per Insight #2)
        assert "node_id" in data, f"Missing 'node_id' in: {data.keys()}"
        assert "category" in data, f"Missing 'category' in: {data.keys()}"
        assert "content" in data, f"Missing 'content' in: {data.keys()}"
        assert "start_line" in data, f"Missing 'start_line' in: {data.keys()}"
        assert "language" in data, f"Missing 'language' in: {data.keys()}"


@pytest.mark.unit
class TestGetNodePiping:
    """T003, T004: Tests for clean output for piping (AC2, AC3)."""

    def test_given_stdout_when_get_node_then_valid_json_only(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves stdout contains ONLY JSON (no logs, no Rich markup).
        Quality Contribution: Enables piping to jq without parsing errors.
        Acceptance Criteria: json.loads() succeeds on entire stdout (AC2).

        Task: T003
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["get-node", "file:src/calculator.py"])

        assert result.exit_code == 0

        # This MUST succeed - any extra output breaks piping
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"stdout is not valid JSON: {e}\nOutput was: {result.stdout}")

        assert isinstance(data, dict), f"Expected dict, got {type(data)}"

    def test_given_get_node_when_piped_to_jq_then_extracts_field(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves output can be processed by JSON tools like jq.
        Quality Contribution: Validates real-world piping use case.
        Acceptance Criteria: JSON structure supports field extraction (AC3).

        Task: T004
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["get-node", "file:src/calculator.py"])

        assert result.exit_code == 0

        data = json.loads(result.stdout)

        # Simulate jq '.node_id' extraction
        assert "node_id" in data
        node_id = data["node_id"]
        assert node_id == "file:src/calculator.py"

        # Simulate jq '.category' extraction
        assert "category" in data
        assert data["category"] == "file"


# T005: File output tests


@pytest.mark.unit
class TestGetNodeFileOutput:
    """T005: Tests for --file flag (AC4)."""

    def test_given_file_flag_when_get_node_then_writes_to_file(
        self, scanned_project, monkeypatch, tmp_path
    ):
        """
        Purpose: Proves --file writes JSON to specified path.
        Quality Contribution: Enables saving output without shell redirection.
        Acceptance Criteria: File contains valid JSON, exit 0 (AC4).

        Task: T005
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        # Output file in tmp_path (different from scanned_project)
        output_file = tmp_path / "output.json"

        result = runner.invoke(
            app, ["get-node", "file:src/calculator.py", "--file", str(output_file)]
        )

        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.stdout}"
        assert output_file.exists(), "Output file should be created"

        # Verify file contains valid JSON
        data = json.loads(output_file.read_text())
        assert "node_id" in data
        assert data["node_id"] == "file:src/calculator.py"

    def test_given_file_flag_when_get_node_then_stdout_is_empty(
        self, scanned_project, monkeypatch, tmp_path
    ):
        """
        Purpose: Proves stdout is empty with --file (success message goes to stderr).
        Quality Contribution: Keeps stdout clean for piping even with --file (AC4).
        Acceptance Criteria: Exit 0, stdout empty, file contains valid JSON.

        Task: T005
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        output_file = tmp_path / "output.json"

        result = runner.invoke(
            app, ["get-node", "file:src/calculator.py", "--file", str(output_file)]
        )

        assert result.exit_code == 0

        # Stdout should be empty (success message goes to stderr)
        # CliRunner can't capture Rich Console(stderr=True) output
        assert result.stdout == "", (
            f"Expected empty stdout with --file, got: {result.stdout}"
        )

        # File should contain valid JSON
        assert output_file.exists()
        file_content = output_file.read_text()
        data = json.loads(file_content)
        assert "node_id" in data


# T006, T007, T008, T008a: Error handling tests


@pytest.mark.unit
class TestGetNodeErrors:
    """T006-T008a: Tests for error handling (AC5, AC6, AC7)."""

    def test_given_unknown_node_when_get_node_then_exit_one(
        self, scanned_project, monkeypatch
    ):
        """
        Purpose: Proves missing node returns user error.
        Quality Contribution: Prevents silent failures.
        Acceptance Criteria: Exit 1, stdout is empty (errors go to stderr) (AC5).

        Task: T006
        """
        from fs2.cli.main import app

        monkeypatch.chdir(scanned_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["get-node", "nonexistent:node:path"])

        assert result.exit_code == 1, (
            f"Expected exit 1, got {result.exit_code}: {result.stdout}"
        )
        # Stdout should be empty (error message goes to stderr for clean piping)
        # CliRunner can't capture Rich Console(stderr=True) output
        assert result.stdout == "", (
            f"Expected empty stdout for error case, got: {result.stdout}"
        )

    def test_given_missing_graph_when_get_node_then_exit_one(
        self, config_only_project, monkeypatch
    ):
        """
        Purpose: Proves missing graph returns user error with guidance.
        Quality Contribution: Guides user to run fs2 scan first.
        Acceptance Criteria: Exit 1, stdout is empty (guidance goes to stderr) (AC6).

        Task: T007
        """
        from fs2.cli.main import app

        monkeypatch.chdir(config_only_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["get-node", "file:src/main.py"])

        assert result.exit_code == 1, (
            f"Expected exit 1, got {result.exit_code}: {result.stdout}"
        )
        # Stdout should be empty (guidance message goes to stderr for clean piping)
        assert result.stdout == "", (
            f"Expected empty stdout for error case, got: {result.stdout}"
        )

    def test_given_corrupted_graph_when_get_node_then_exit_two(
        self, corrupted_graph_project, monkeypatch
    ):
        """
        Purpose: Proves corrupted graph returns system error.
        Quality Contribution: Distinguishes user vs system errors.
        Acceptance Criteria: Exit 2, stdout is empty (error goes to stderr) (AC7).

        Task: T008
        """
        from fs2.cli.main import app

        monkeypatch.chdir(corrupted_graph_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["get-node", "file:src/main.py"])

        assert result.exit_code == 2, (
            f"Expected exit 2 for corruption, got {result.exit_code}: {result.stdout}"
        )
        # Stdout should be empty (error message goes to stderr for clean piping)
        assert result.stdout == "", (
            f"Expected empty stdout for error case, got: {result.stdout}"
        )

    def test_given_missing_config_when_get_node_then_exit_one(
        self, project_without_config, monkeypatch
    ):
        """
        Purpose: Proves missing config returns user error with guidance.
        Quality Contribution: Guides user to run fs2 init first.
        Acceptance Criteria: Exit 1, stdout contains init suggestion (per CLI guard).

        Task: T008a
        """
        from fs2.cli.main import app

        monkeypatch.chdir(project_without_config)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["get-node", "file:src/main.py"])

        assert result.exit_code == 1, (
            f"Expected exit 1, got {result.exit_code}: {result.stdout}"
        )
        # CLI guard suggests running init
        assert "init" in result.stdout.lower(), (
            f"Expected 'init' in output, got: {result.stdout}"
        )
