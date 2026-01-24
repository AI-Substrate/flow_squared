"""Tests for fs2 scan --no-lsp CLI flag.

Full TDD tests for Phase 8 Task 8 covering:
- T008: --no-lsp flag disables relationship extraction
- T008: LSP is enabled by default
- T008: Flag appears in --help output
- T008: Scan completes successfully with --no-lsp
"""

import pytest
from typer.testing import CliRunner

runner = CliRunner()


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

    # Create another file with cross-reference pattern
    (tmp_path / "utils.py").write_text("""
def helper():
    # Reference to class:calculator.py:Calculator
    return "help"
""")

    return tmp_path


class TestNoLspFlag:
    """T008: Tests for --no-lsp CLI flag.

    Per Phase 8 Tasks:
    - Flag skips RelationshipExtractionStage LSP processing
    - LSP is enabled by default (opt-out pattern)
    - Summary reflects relationship extraction status
    - Graph saved normally with or without LSP edges
    """

    def test_given_no_lsp_flag_when_scan_help_then_shows_flag(self):
        """
        Purpose: Verifies --no-lsp flag appears in help output.
        Quality Contribution: Ensures flag is discoverable.
        Acceptance Criteria: Help output includes --no-lsp.

        Why: Users need to know the flag exists.
        Contract: Flag is documented in CLI help.
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["scan", "--help"])

        assert result.exit_code == 0
        assert "--no-lsp" in result.stdout, (
            f"Expected '--no-lsp' in help output: {result.stdout}"
        )

    def test_given_no_lsp_flag_when_scan_help_then_shows_description(self):
        """
        Purpose: Verifies --no-lsp flag has a descriptive help message.
        Quality Contribution: Users understand what the flag does.
        Acceptance Criteria: Help mentions LSP or relationship extraction.

        Why: Help text should explain the flag's purpose.
        Contract: Description mentions relationship/LSP/cross-file.
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["scan", "--help"])

        assert result.exit_code == 0
        stdout_lower = result.stdout.lower()
        # Should mention what it disables
        assert any(
            term in stdout_lower
            for term in ["lsp", "relationship", "cross-file", "reference"]
        ), f"Expected LSP-related description in help: {result.stdout}"

    def test_given_no_lsp_flag_when_scan_then_exits_zero(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies --no-lsp doesn't break scan.
        Quality Contribution: Ensures opt-out mode works.
        Acceptance Criteria: Exit code 0 with --no-lsp.

        Why: Users may want fast scans without LSP processing.
        Contract: Flag disables LSP but scan completes normally.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan", "--no-lsp"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"

    def test_given_no_lsp_flag_when_scan_then_graph_created(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies graph is still created without LSP.
        Quality Contribution: Ensures core functionality works in fast mode.
        Acceptance Criteria: Graph file exists after scan.

        Why: Graph should be persisted even without LSP edges.
        Contract: --no-lsp only skips LSP, not graph storage.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan", "--no-lsp"])

        assert result.exit_code == 0
        graph_file = simple_project / ".fs2" / "graph.pickle"
        assert graph_file.exists(), "Graph file should be created"

    def test_given_no_lsp_flag_when_scan_then_nodes_created(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies nodes are created without LSP.
        Quality Contribution: Ensures parsing still works.
        Acceptance Criteria: Output mentions nodes created.

        Why: Node creation is independent of LSP.
        Contract: --no-lsp does not affect node creation.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan", "--no-lsp"])

        assert result.exit_code == 0
        stdout_lower = result.stdout.lower()
        assert "node" in stdout_lower, f"Expected 'node' in: {result.stdout}"

    def test_given_default_scan_when_no_lsp_servers_then_graceful_degradation(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies scan completes when LSP servers unavailable.
        Quality Contribution: Ensures graceful degradation per DYK-4.
        Acceptance Criteria: Exit 0 even without LSP servers.

        Why: Users without LSP servers should still be able to scan.
        Contract: LSP unavailability is WARNING, not ERROR.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan"])

        # Should succeed (LSP gracefully degraded)
        assert result.exit_code == 0, f"Failed with: {result.stdout}"

    def test_given_no_lsp_flag_when_combined_with_no_smart_content_then_both_work(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies --no-lsp works with --no-smart-content.
        Quality Contribution: Ensures flags are composable.
        Acceptance Criteria: Exit 0 with both flags.

        Why: Users may want fastest possible scan.
        Contract: Flags are independent and composable.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan", "--no-lsp", "--no-smart-content"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"

    def test_given_no_lsp_flag_when_combined_with_no_embeddings_then_both_work(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies --no-lsp works with --no-embeddings.
        Quality Contribution: Ensures flags are composable.
        Acceptance Criteria: Exit 0 with both flags.

        Why: Users may want scan without AI features.
        Contract: Flags are independent and composable.
        """
        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["scan", "--no-lsp", "--no-embeddings"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"


class TestNoLspFlagPipelineIntegration:
    """Tests for --no-lsp flag effect on pipeline behavior.

    These tests verify the flag correctly disables LSP processing
    in the RelationshipExtractionStage.
    """

    def test_given_no_lsp_flag_when_scan_then_pipeline_receives_no_lsp_adapter(
        self, simple_project, monkeypatch
    ):
        """
        Purpose: Verifies --no-lsp results in lsp_adapter=None in pipeline.
        Quality Contribution: Ensures flag has functional effect.
        Acceptance Criteria: Pipeline created without LSP adapter.

        Why: Flag should prevent LSP adapter creation.
        Contract: --no-lsp sets lsp_adapter=None in ScanPipeline.
        """
        from unittest.mock import patch

        from fs2.cli.main import app

        monkeypatch.chdir(simple_project)
        monkeypatch.setenv("NO_COLOR", "1")

        # Track pipeline creation
        pipeline_kwargs = {}

        original_init = None
        from fs2.core.services import ScanPipeline as OriginalPipeline

        original_init = OriginalPipeline.__init__

        def capture_init(self, **kwargs):
            pipeline_kwargs.update(kwargs)
            return original_init(self, **kwargs)

        with patch.object(OriginalPipeline, "__init__", capture_init):
            result = runner.invoke(app, ["scan", "--no-lsp"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"
        # Verify lsp_adapter was explicitly None or not passed
        assert pipeline_kwargs.get("lsp_adapter") is None, (
            f"Expected lsp_adapter=None, got: {pipeline_kwargs.get('lsp_adapter')}"
        )
