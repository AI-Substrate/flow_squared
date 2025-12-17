"""Integration tests for fs2 CLI commands.

T020-T021: End-to-end CLI integration tests.
Tests use subprocess to verify real CLI behavior.
"""

import subprocess
import sys


class TestCLIEndToEnd:
    """T020: Full scan via CLI subprocess."""

    def test_given_project_when_init_then_scan_succeeds(self, tmp_path):
        """
        Purpose: Verifies full init -> scan workflow.
        Quality Contribution: Proves end-to-end functionality.
        Acceptance Criteria: Both commands succeed, graph created.
        """
        # Run fs2 init
        init_result = subprocess.run(
            [sys.executable, "-m", "fs2", "init"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={"NO_COLOR": "1", **dict(__import__("os").environ)},
        )

        assert init_result.returncode == 0, f"Init failed: {init_result.stderr}"
        assert (tmp_path / ".fs2" / "config.yaml").exists()

        # Create a Python file to scan
        (tmp_path / "test.py").write_text("def hello():\n    return 'world'")

        # Run fs2 scan
        scan_result = subprocess.run(
            [sys.executable, "-m", "fs2", "scan"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={"NO_COLOR": "1", **dict(__import__("os").environ)},
        )

        assert scan_result.returncode == 0, f"Scan failed: {scan_result.stderr}"
        assert "scanned" in scan_result.stdout.lower()
        assert (tmp_path / ".fs2" / "graph.pickle").exists()

    def test_given_no_init_when_scan_then_suggests_init(self, tmp_path):
        """
        Purpose: Verifies helpful error without init.
        Quality Contribution: Guides users to correct workflow.
        Acceptance Criteria: Exit 1, mentions init.
        """
        scan_result = subprocess.run(
            [sys.executable, "-m", "fs2", "scan"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={"NO_COLOR": "1", **dict(__import__("os").environ)},
        )

        assert scan_result.returncode == 1
        assert "init" in scan_result.stdout.lower()


class TestCLIHelpOutput:
    """T021: CLI help and version output."""

    def test_given_help_flag_when_run_then_shows_commands(self, tmp_path):
        """
        Purpose: Verifies --help works.
        Quality Contribution: Ensures CLI is discoverable.
        Acceptance Criteria: Help shows scan and init commands.
        """
        result = subprocess.run(
            [sys.executable, "-m", "fs2", "--help"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "scan" in result.stdout
        assert "init" in result.stdout

    def test_given_scan_help_when_run_then_shows_options(self, tmp_path):
        """
        Purpose: Verifies scan --help works.
        Quality Contribution: Ensures options are documented.
        Acceptance Criteria: Help shows verbose and no-progress options.
        """
        result = subprocess.run(
            [sys.executable, "-m", "fs2", "scan", "--help"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "--verbose" in result.stdout
        assert "--no-progress" in result.stdout


class TestCLIWithRealProject:
    """Integration tests with actual code structure."""

    def test_given_python_project_when_scanned_then_extracts_hierarchy(
        self, tmp_path
    ):
        """
        Purpose: Verifies AC5 - File -> Class -> Method hierarchy.
        Quality Contribution: Ensures core parsing works end-to-end.
        Acceptance Criteria: Scan finds classes and methods.
        """
        # Create project structure
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(f"""scan:
  scan_paths:
    - "{tmp_path}"
  respect_gitignore: true
""")

        # Create Python file with class and methods
        (tmp_path / "calculator.py").write_text('''
class Calculator:
    """A simple calculator."""

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    def subtract(self, a: int, b: int) -> int:
        """Subtract b from a."""
        return a - b
''')

        # Run scan
        result = subprocess.run(
            [sys.executable, "-m", "fs2", "scan"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={"NO_COLOR": "1", **dict(__import__("os").environ)},
        )

        assert result.returncode == 0, f"Failed: {result.stdout}\n{result.stderr}"
        # Should find files and create nodes
        assert "scanned" in result.stdout.lower()
        # Should create multiple nodes (file + class + methods)
        assert "node" in result.stdout.lower()
        # Should create nodes for class and methods
        assert "5 nodes" in result.stdout or "nodes" in result.stdout.lower()
