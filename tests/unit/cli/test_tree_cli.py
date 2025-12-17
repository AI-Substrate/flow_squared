"""Tests for fs2 tree CLI command.

Full TDD tests for the tree CLI command covering:
- T007: Tree command registration and --help
- T010: Missing graph error (AC7)
- T012: Basic tree display (AC1)
- T014-T016: Pattern filtering (AC2, AC3)
- T018: Empty results (AC8)
- T020: Empty graph edge case
- T022: Exit code 2 (system error)
"""

import pytest
from typer.testing import CliRunner

runner = CliRunner()


# T007: Command registration tests


@pytest.mark.unit
class TestTreeCommandRegistration:
    """T007: Tests for tree command registration."""

    def test_given_cli_app_when_inspected_then_tree_command_registered(self):
        """
        Purpose: Verifies tree command is registered on app.
        Quality Contribution: Ensures command is discoverable.
        Acceptance Criteria: 'tree' in registered commands.

        Task: T007
        """
        from fs2.cli.main import app

        command_names = [cmd.name for cmd in app.registered_commands]
        assert "tree" in command_names, f"Expected 'tree' in {command_names}"


@pytest.mark.unit
class TestTreeHelp:
    """T007: Tests for tree --help output."""

    def test_given_help_flag_when_invoked_then_shows_usage(self):
        """
        Purpose: Verifies tree --help works (AC14).
        Quality Contribution: Ensures CLI is user-friendly.
        Acceptance Criteria: Help output includes command description and options.

        Task: T007
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree", "--help"])

        assert result.exit_code == 0
        assert "tree" in result.stdout.lower()
        # Should show PATTERN argument
        assert "pattern" in result.stdout.lower()

    def test_given_help_when_invoked_then_shows_detail_option(self):
        """
        Purpose: Verifies --detail option is documented.
        Quality Contribution: Ensures option is discoverable.
        Acceptance Criteria: --detail in help output.

        Task: T007
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree", "--help"])

        assert result.exit_code == 0
        assert "--detail" in result.stdout

    def test_given_help_when_invoked_then_shows_depth_option(self):
        """
        Purpose: Verifies --depth option is documented.
        Quality Contribution: Ensures option is discoverable.
        Acceptance Criteria: --depth in help output.

        Task: T007
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree", "--help"])

        assert result.exit_code == 0
        assert "--depth" in result.stdout or "-d" in result.stdout


# Fixtures for tree command tests


@pytest.fixture
def scanned_project(tmp_path, monkeypatch):
    """Create a simple project with scanned graph."""
    # Create config directory
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()

    # Create config file - use relative paths for scan
    config_file = config_dir / "config.yaml"
    config_file.write_text("""scan:
  scan_paths:
    - "."
  respect_gitignore: true
  max_file_size_kb: 500
tree:
  graph_path: ".fs2/graph.pickle"
""")

    # Create source files
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    (src_dir / "calculator.py").write_text("""
class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b
""")

    (src_dir / "utils.py").write_text("""
def helper():
    return "help"

def format_output(value):
    return str(value)
""")

    # Create another subdirectory
    models_dir = src_dir / "models"
    models_dir.mkdir()

    (models_dir / "item.py").write_text("""
class Item:
    def __init__(self, name):
        self.name = name
""")

    # Change to project directory and run scan
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NO_COLOR", "1")

    from fs2.cli.main import app

    result = runner.invoke(app, ["scan"])
    assert result.exit_code == 0, f"Scan failed: {result.stdout}"

    return tmp_path


@pytest.fixture
def config_only_project(tmp_path):
    """Create a project with config but no graph file."""
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()

    config_file = config_dir / "config.yaml"
    config_file.write_text(f"""scan:
  scan_paths:
    - "{tmp_path}"
tree:
  graph_path: ".fs2/graph.pickle"
""")

    return tmp_path


# T010: Missing graph error tests


@pytest.mark.unit
class TestTreeMissingGraph:
    """T010: Tests for missing graph error (AC7)."""

    def test_given_no_graph_when_tree_invoked_then_exit_one(
        self, config_only_project, monkeypatch
    ):
        """
        Purpose: Verifies AC7 - missing graph exits 1.
        Quality Contribution: Ensures user error is reported correctly.
        Acceptance Criteria: Exit code 1, error message shown.

        Task: T010
        """
        from fs2.cli.main import app

        monkeypatch.chdir(config_only_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}: {result.stdout}"
        # Should mention running scan
        stdout_lower = result.stdout.lower()
        assert "scan" in stdout_lower or "graph" in stdout_lower

    def test_given_no_graph_when_tree_invoked_then_shows_helpful_message(
        self, config_only_project, monkeypatch
    ):
        """
        Purpose: Verifies helpful error message for missing graph.
        Quality Contribution: Guides user to fix the issue.
        Acceptance Criteria: Message mentions fs2 scan.

        Task: T010
        """
        from fs2.cli.main import app

        monkeypatch.chdir(config_only_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 1
        # Should suggest running scan
        assert "scan" in result.stdout.lower()


# T012: Basic tree display tests


@pytest.mark.unit
class TestTreeBasicDisplay:
    """T012: Tests for basic tree display (AC1)."""

    def test_given_scanned_graph_when_tree_then_exits_zero(
        self, scanned_project
    ):
        """
        Purpose: Verifies tree command succeeds with valid graph.
        Quality Contribution: Ensures happy path works.
        Acceptance Criteria: Exit code 0.

        Task: T012
        """
        from fs2.cli.main import app

        # scanned_project fixture already changed to tmp_path
        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 0, f"Failed with: {result.stdout}"

    def test_given_scanned_graph_when_tree_then_shows_hierarchy(
        self, scanned_project
    ):
        """
        Purpose: Verifies AC1 - tree displays hierarchy.
        Quality Contribution: Ensures output is useful.
        Acceptance Criteria: Output shows tree structure.

        Task: T012
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 0
        # Should have some tree output
        stdout = result.stdout
        # Should contain file names
        assert "calculator.py" in stdout or "Calculator" in stdout

    def test_given_scanned_graph_when_tree_then_shows_icons(
        self, scanned_project
    ):
        """
        Purpose: Verifies AC1 - tree shows category icons.
        Quality Contribution: Visual clarity.
        Acceptance Criteria: Output includes icons.

        Task: T012
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 0
        # Should have icons (📄 for files, 📦 for types, ƒ for callables)
        stdout = result.stdout
        # At least one icon should be present
        has_icon = any(icon in stdout for icon in ["📄", "📦", "ƒ", "📁"])
        assert has_icon, f"Expected icons in output: {stdout}"


# T014-T016: Pattern filtering tests


@pytest.mark.unit
class TestTreeExactMatch:
    """T014: Tests for exact node_id match."""

    def test_given_exact_node_id_when_tree_then_shows_single_result(
        self, scanned_project
    ):
        """
        Purpose: Verifies exact node_id match returns single result.
        Quality Contribution: Enables precise lookups.
        Acceptance Criteria: Single node + children shown.

        Task: T014
        """
        from fs2.cli.main import app

        # Use a file node_id pattern
        result = runner.invoke(app, ["tree", "file:src/calculator.py"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Should show the calculator file
        assert "calculator" in stdout.lower()


@pytest.mark.unit
class TestTreeSubstringFilter:
    """T015: Tests for substring filtering (AC2)."""

    def test_given_path_pattern_when_tree_then_filters_by_path(
        self, scanned_project
    ):
        """
        Purpose: Verifies AC2 - path filtering works.
        Quality Contribution: Enables focused exploration.
        Acceptance Criteria: Only matching paths shown.

        Task: T015
        """
        from fs2.cli.main import app

        # Filter by src/models path
        result = runner.invoke(app, ["tree", "models"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Should show models content
        assert "item" in stdout.lower() or "Item" in stdout

    def test_given_name_pattern_when_tree_then_filters_by_name(
        self, scanned_project
    ):
        """
        Purpose: Verifies name filtering works via node_id.
        Quality Contribution: Enables name-based search.
        Acceptance Criteria: Nodes containing name shown.

        Task: T015
        """
        from fs2.cli.main import app

        # Filter by Calculator name
        result = runner.invoke(app, ["tree", "Calculator"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Should show Calculator
        assert "calculator" in stdout.lower()


@pytest.mark.unit
class TestTreeGlobFilter:
    """T016: Tests for glob pattern filtering (AC3)."""

    def test_given_glob_pattern_when_tree_then_filters_by_glob(
        self, scanned_project
    ):
        """
        Purpose: Verifies AC3 - glob patterns work.
        Quality Contribution: Enables pattern-based filtering.
        Acceptance Criteria: Only matching nodes shown.

        Task: T016
        """
        from fs2.cli.main import app

        # Use glob pattern to match all .py files
        result = runner.invoke(app, ["tree", "*calculator*"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Should match calculator-related content
        assert "calculator" in stdout.lower()


# T018-T019: Empty results tests


@pytest.mark.unit
class TestTreeEmptyResults:
    """T018: Tests for empty results (AC8)."""

    def test_given_no_matches_when_tree_then_shows_message(
        self, scanned_project
    ):
        """
        Purpose: Verifies AC8 - empty results shows message.
        Quality Contribution: Clear feedback on no matches.
        Acceptance Criteria: "No nodes match" message shown.

        Task: T018
        """
        from fs2.cli.main import app

        # Use pattern that won't match anything
        result = runner.invoke(app, ["tree", "nonexistent_xyz_123"])

        assert result.exit_code == 0
        stdout_lower = result.stdout.lower()
        # Should indicate no matches
        assert "no" in stdout_lower and ("match" in stdout_lower or "found" in stdout_lower)

    def test_given_no_matches_when_tree_then_exit_zero(
        self, scanned_project
    ):
        """
        Purpose: Verifies AC8 - empty results exits 0.
        Quality Contribution: Proper exit code for valid query.
        Acceptance Criteria: Exit code 0.

        Task: T018
        """
        from fs2.cli.main import app

        # Use pattern that won't match anything
        result = runner.invoke(app, ["tree", "nonexistent_xyz_123"])

        assert result.exit_code == 0


# T020-T021: Empty graph tests


@pytest.fixture
def empty_graph_project(tmp_path):
    """Create a project with an empty graph."""
    from fs2.config.objects import ScanConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.repos.graph_store_impl import NetworkXGraphStore

    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()

    config_file = config_dir / "config.yaml"
    config_file.write_text(f"""scan:
  scan_paths:
    - "{tmp_path}"
tree:
  graph_path: ".fs2/graph.pickle"
""")

    # Create an empty graph
    config = FakeConfigurationService(ScanConfig())
    store = NetworkXGraphStore(config)
    # Don't add any nodes - empty graph
    store.save(config_dir / "graph.pickle")

    return tmp_path


@pytest.mark.unit
class TestTreeEmptyGraph:
    """T020: Tests for empty graph edge case."""

    def test_given_empty_graph_when_tree_then_shows_zero_nodes(
        self, empty_graph_project, monkeypatch
    ):
        """
        Purpose: Verifies empty graph is handled.
        Quality Contribution: No crash on empty graph.
        Acceptance Criteria: Shows "0 nodes" or similar message.

        Task: T020
        """
        from fs2.cli.main import app

        monkeypatch.chdir(empty_graph_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 0
        stdout_lower = result.stdout.lower()
        # Should indicate empty/zero
        assert "0" in stdout_lower or "empty" in stdout_lower or "no" in stdout_lower


# T022-T023: Exit code 2 (system error) tests


@pytest.fixture
def corrupted_graph_project(tmp_path):
    """Create a project with a corrupted graph file."""
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()

    config_file = config_dir / "config.yaml"
    config_file.write_text(f"""scan:
  scan_paths:
    - "{tmp_path}"
tree:
  graph_path: ".fs2/graph.pickle"
""")

    # Create corrupted graph file
    graph_file = config_dir / "graph.pickle"
    graph_file.write_bytes(b"not a valid pickle file content\x00\x01\x02")

    return tmp_path


@pytest.mark.unit
class TestTreeSystemError:
    """T022: Tests for exit code 2 (system error)."""

    def test_given_corrupted_graph_when_tree_then_exit_two(
        self, corrupted_graph_project, monkeypatch
    ):
        """
        Purpose: Verifies corrupted graph exits 2.
        Quality Contribution: Distinguishes user vs system errors.
        Acceptance Criteria: Exit code 2 for corruption.

        Task: T022
        """
        from fs2.cli.main import app

        monkeypatch.chdir(corrupted_graph_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}: {result.stdout}"

    def test_given_corrupted_graph_when_tree_then_shows_error_message(
        self, corrupted_graph_project, monkeypatch
    ):
        """
        Purpose: Verifies error message for corrupted graph.
        Quality Contribution: Helps diagnose the issue.
        Acceptance Criteria: Error message shown.

        Task: T022
        """
        from fs2.cli.main import app

        monkeypatch.chdir(corrupted_graph_project)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 2
        stdout_lower = result.stdout.lower()
        # Should indicate error
        assert "error" in stdout_lower


# F5: Summary counts tests (review fix)


@pytest.mark.unit
class TestTreeSummaryCounts:
    """F5: Tests for accurate summary counts including children."""

    def test_given_tree_with_children_when_displayed_then_counts_all_nodes(
        self, scanned_project
    ):
        """
        Purpose: Verifies summary counts all displayed nodes, not just roots.
        Quality Contribution: Ensures accurate user feedback.
        Acceptance Criteria: Node count includes children in subtree.

        Task: F5 review fix
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 0
        # Should show accurate counts - at minimum:
        # - calculator.py has Calculator class with 2 methods = 4 nodes (file, class, 2 methods)
        # - utils.py has 2 functions = 3 nodes (file, 2 functions)
        # - models/item.py has Item class with __init__ = 3 nodes
        # Total should be > 3 (more than just root files)
        stdout = result.stdout
        # Look for the summary line pattern: "Found X nodes in Y files"
        import re

        match = re.search(r"Found (\d+) nodes? in (\d+) files?", stdout)
        assert match, f"Summary line not found in output: {stdout}"
        node_count = int(match.group(1))
        file_count = int(match.group(2))
        # We have 3 files with multiple classes/functions each
        assert node_count >= 6, f"Expected at least 6 nodes, got {node_count}"
        assert file_count >= 3, f"Expected at least 3 files, got {file_count}"

    def test_given_depth_limit_when_tree_then_shows_hidden_count(
        self, scanned_project
    ):
        """
        Purpose: Verifies depth-limited output shows hidden children count.
        Quality Contribution: User knows content is hidden.
        Acceptance Criteria: "[N children hidden]" message present.

        Task: F5 review fix
        """
        from fs2.cli.main import app

        # Limit depth to 1 - should hide children of files
        result = runner.invoke(app, ["tree", "--depth", "1"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Should mention hidden children
        assert "hidden" in stdout.lower() or "depth" in stdout.lower(), \
            f"Expected hidden/depth mention in output: {stdout}"


# F6: Verbose flag tests (review fix)


@pytest.mark.unit
class TestTreeVerboseFlag:
    """F6: Tests for --verbose flag behavior."""

    def test_given_verbose_when_tree_then_shows_debug_output(
        self, scanned_project
    ):
        """
        Purpose: Verifies --verbose enables debug logging.
        Quality Contribution: Users can diagnose issues.
        Acceptance Criteria: Debug output visible with --verbose.

        Task: F6 review fix
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree", "--verbose"])

        assert result.exit_code == 0
        stdout_lower = result.stdout.lower()
        # With verbose, should show some diagnostic info
        # (e.g., "loading", "filtering", "nodes found", etc.)
        has_diagnostic = any(
            term in stdout_lower
            for term in ["loading", "filtering", "debug", "pattern", "nodes"]
        )
        assert has_diagnostic, f"Expected diagnostic output with --verbose: {result.stdout}"

    def test_given_no_verbose_when_tree_then_minimal_output(
        self, scanned_project
    ):
        """
        Purpose: Verifies normal mode doesn't show debug info.
        Quality Contribution: Clean output for normal use.
        Acceptance Criteria: No DEBUG: prefix in output.

        Task: F6 review fix
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Should NOT have DEBUG prefix in normal mode
        assert "DEBUG:" not in stdout
