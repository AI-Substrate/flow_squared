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
graph:
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
graph:
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

        assert result.exit_code == 1, (
            f"Expected exit 1, got {result.exit_code}: {result.stdout}"
        )
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

    def test_given_scanned_graph_when_tree_then_exits_zero(self, scanned_project):
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

    def test_given_scanned_graph_when_tree_then_shows_hierarchy(self, scanned_project):
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

    def test_given_scanned_graph_when_tree_then_shows_icons(self, scanned_project):
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

    def test_given_path_pattern_when_tree_then_filters_by_path(self, scanned_project):
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

    def test_given_name_pattern_when_tree_then_filters_by_name(self, scanned_project):
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

    def test_given_glob_pattern_when_tree_then_filters_by_glob(self, scanned_project):
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

    def test_given_no_matches_when_tree_then_shows_message(self, scanned_project):
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
        assert "no" in stdout_lower and (
            "match" in stdout_lower or "found" in stdout_lower
        )

    def test_given_no_matches_when_tree_then_exit_zero(self, scanned_project):
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
graph:
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
graph:
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

        assert result.exit_code == 2, (
            f"Expected exit 2, got {result.exit_code}: {result.stdout}"
        )

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

    def test_given_depth_limit_when_tree_then_shows_hidden_count(self, scanned_project):
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
        assert "hidden" in stdout.lower() or "depth" in stdout.lower(), (
            f"Expected hidden/depth mention in output: {stdout}"
        )


# F6: Verbose flag tests (review fix)


@pytest.mark.unit
class TestTreeVerboseFlag:
    """F6: Tests for --verbose flag behavior."""

    def test_given_verbose_when_tree_then_shows_debug_output(self, scanned_project):
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
        assert has_diagnostic, (
            f"Expected diagnostic output with --verbose: {result.stdout}"
        )

    def test_given_no_verbose_when_tree_then_minimal_output(self, scanned_project):
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


# Phase 2 Tests: Detail Levels and Depth Limiting


# T001: Tests for --detail min output format (AC4)


@pytest.mark.unit
class TestDetailMin:
    """T001: Tests for --detail min output format (AC4).

    AC4: --detail min shows icon, name, type, line range
    """

    def test_given_detail_min_when_tree_then_shows_icon_name_lines(
        self, scanned_project
    ):
        """
        Purpose: Verifies AC4 - min detail shows icon, name, line range.
        Quality Contribution: Ensures default output is complete yet clean.
        Acceptance Criteria: Icon present, name present, line range format [N-M].

        Task: T001
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree", "--detail", "min"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Should have icons
        has_icon = any(icon in stdout for icon in ["📄", "📦", "ƒ", "📁"])
        assert has_icon, f"Expected icons in output: {stdout}"
        # Should have name (calculator or Calculator)
        assert "calculator" in stdout.lower()
        # Should have line range format [N-M]
        import re

        assert re.search(r"\[\d+-\d+\]", stdout), (
            f"Expected line range format [N-M] in output: {stdout}"
        )

    def test_given_detail_min_when_tree_then_no_node_id(self, scanned_project):
        """
        Purpose: Verifies AC4 - min detail excludes node ID.
        Quality Contribution: Clean output without clutter in default mode.
        Acceptance Criteria: No 'file:', 'type:', 'callable:' node ID patterns.

        Task: T001
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree", "--detail", "min"])

        assert result.exit_code == 0
        stdout = result.stdout
        # In min mode, node_id lines should NOT appear
        # Node IDs are like 'file:path' or 'type:path:ClassName'
        # Check that node_id prefixes don't appear on separate lines
        lines = stdout.split("\n")
        for line in lines:
            stripped = line.strip()
            # Skip the summary line which contains "files"
            if "Found" in line and "files" in line:
                continue
            # Node ID lines in max mode start with category:
            # In min mode these shouldn't be visible as standalone info
            if (
                stripped.startswith("file:")
                or stripped.startswith("type:")
                or stripped.startswith("callable:")
            ):
                pytest.fail(f"Found node_id line in min mode: {line}")

    def test_given_detail_min_when_tree_then_no_signature(self, scanned_project):
        """
        Purpose: Verifies AC4 - min detail excludes signature.
        Quality Contribution: Keeps min mode concise.
        Acceptance Criteria: No 'def ' or 'class ' signatures on label lines.

        Task: T001
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree", "--detail", "min"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Check for signature patterns that would appear in max mode
        # Signatures are like 'def add(self, a, b):' appearing on label lines
        # In min mode, we should NOT see these function signatures
        lines = stdout.split("\n")
        for line in lines:
            # Look for ƒ (callable icon) lines
            if "ƒ" in line:
                # In min mode: "ƒ add [10-15]"
                # In max mode: "ƒ add [10-15] def add(self, a, b):"
                # Check that 'def ' doesn't appear on callable lines
                if "def " in line:
                    pytest.fail(
                        f"Found signature 'def ' in min mode callable line: {line}"
                    )


# T003: Tests for --detail max output format (AC5)


@pytest.mark.unit
class TestDetailMax:
    """T003: Tests for --detail max output format (AC5).

    AC5: --detail max shows node ID and signature.
    Format: Main line shows icon, name, [lines], signature inline.
            Second line (dimmed, indented) shows the node ID.
    """

    def test_given_detail_max_when_tree_then_shows_node_id(self, scanned_project):
        """
        Purpose: Verifies AC5 - max detail includes node ID.
        Quality Contribution: Enables copy-paste for FlowSpace tools.
        Acceptance Criteria: Node IDs visible (file:, type:, callable:).

        Task: T003
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree", "--detail", "max"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Should have node_id patterns visible
        # Node IDs are like 'file:path', 'type:path:ClassName', 'callable:path:Class.method'
        has_node_id = any(
            prefix in stdout for prefix in ["file:", "type:", "callable:"]
        )
        assert has_node_id, f"Expected node IDs in max detail output: {stdout}"

    def test_given_detail_max_when_tree_then_shows_signature_inline(
        self, scanned_project
    ):
        """
        Purpose: Verifies AC5 - max detail shows signature inline.
        Quality Contribution: Shows function/class signatures for context.
        Acceptance Criteria: Signatures appear on same line as icon/name.

        Task: T003
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree", "--detail", "max"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Look for signature patterns like 'def add(self, a, b):'
        # These should appear on lines with callable icons
        lines = stdout.split("\n")
        found_signature_on_callable_line = False
        for line in lines:
            if "ƒ" in line and "def " in line:
                found_signature_on_callable_line = True
                break
            # Also check for class signatures
            if "📦" in line and "class " in line:
                found_signature_on_callable_line = True
                break

        assert found_signature_on_callable_line, (
            f"Expected signature inline with callable/type icon: {stdout}"
        )

    def test_given_detail_max_when_tree_then_node_id_on_second_line(
        self, scanned_project
    ):
        """
        Purpose: Verifies AC5 - node_id appears on second line (indented).
        Quality Contribution: Visual separation between main info and node ID.
        Acceptance Criteria: Node ID appears after main label, indented.

        Task: T003
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree", "--detail", "max"])

        assert result.exit_code == 0
        stdout = result.stdout
        # The format is:
        # icon name [lines] signature
        #     node_id
        # So node_id should appear on a line starting with whitespace
        lines = stdout.split("\n")
        found_indented_node_id = False
        for line in lines:
            stripped = line.strip()
            # Node IDs start with category:
            if (
                stripped.startswith("file:")
                or stripped.startswith("type:")
                or stripped.startswith("callable:")
            ):
                # Check it's indented from start of line
                if line.startswith(" ") or line.startswith("\t") or "│" in line:
                    found_indented_node_id = True
                    break

        assert found_indented_node_id, (
            f"Expected indented node ID line in max detail: {stdout}"
        )

    def test_given_detail_max_when_no_signature_then_no_sig_displayed(
        self, scanned_project
    ):
        """
        Purpose: Verifies Discovery 17 - handles missing signatures gracefully.
        Quality Contribution: No empty signature display for file nodes.
        Acceptance Criteria: File nodes don't show 'def ' or 'class ' after line range.

        Task: T003
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree", "--detail", "max"])

        assert result.exit_code == 0
        stdout = result.stdout
        # File nodes (📄) should not have signatures
        lines = stdout.split("\n")
        for line in lines:
            if "📄" in line:
                # File icons shouldn't have def/class after line range
                # Pattern: 📄 name [N-M] - nothing after line range
                # OK: "📄 calculator.py [1-50]"
                # BAD: "📄 calculator.py [1-50] def something"
                if "📄" in line and "[" in line:
                    after_bracket = line.split("]")[-1] if "]" in line else ""
                    # The only thing after ] should be the newline or tree chars
                    # Not a def/class signature
                    if "def " in after_bracket or "class " in after_bracket:
                        pytest.fail(f"File node has signature: {line}")


# T006-T007: Tests for --depth limiting (AC6)


@pytest.mark.unit
class TestDepthLimiting:
    """T006-T007: Tests for --depth limiting (AC6).

    AC6: --depth N limits depth with hidden child indicator.
    Discovery 11: Format: [N children hidden by depth limit]
    """

    def test_given_depth_one_when_tree_then_shows_files_only(self, scanned_project):
        """
        Purpose: Verifies depth=1 shows only root level.
        Quality Contribution: Users can get overview without detail.
        Acceptance Criteria: Only file-level nodes visible, children hidden.

        Task: T006
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree", "--depth", "1"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Should see file icons but not nested methods
        assert "📄" in stdout, f"Expected file icons: {stdout}"
        # With depth 1, we only see root nodes (files in this case)
        # Classes and methods should be hidden
        # The hidden indicator should appear
        assert "hidden" in stdout.lower(), (
            f"Expected hidden indicator for depth=1: {stdout}"
        )

    def test_given_depth_two_when_tree_then_shows_two_levels(self, scanned_project):
        """
        Purpose: Verifies depth=2 shows files and immediate children.
        Quality Contribution: Balance between overview and detail.
        Acceptance Criteria: Files + classes visible, methods hidden.

        Task: T006
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree", "--depth", "2"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Should see files (📄) and classes (📦)
        assert "📄" in stdout, f"Expected file icons: {stdout}"
        # Classes should be visible at depth 2
        assert "Calculator" in stdout or "📦" in stdout, (
            f"Expected classes at depth 2: {stdout}"
        )

    def test_given_depth_zero_when_tree_then_shows_all(self, scanned_project):
        """
        Purpose: Verifies depth=0 means unlimited depth.
        Quality Contribution: Default shows full tree.
        Acceptance Criteria: All nested levels visible, no hidden indicator.

        Task: T006
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree", "--depth", "0"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Should see all levels - including methods
        # Look for callable icon (ƒ) which indicates methods
        assert "ƒ" in stdout or "add" in stdout.lower(), (
            f"Expected methods visible with depth=0: {stdout}"
        )
        # Should NOT have hidden indicator (unless there's nothing to hide)
        # Check output doesn't say "hidden by depth limit"
        lines = [line for line in stdout.split("\n") if "depth limit" in line.lower()]
        assert len(lines) == 0, (
            f"Unexpected depth limit indicator with depth=0: {stdout}"
        )

    def test_given_depth_limit_when_tree_then_shows_hidden_count(self, scanned_project):
        """
        Purpose: Verifies hidden indicator shows child count.
        Quality Contribution: Users know how much is hidden.
        Acceptance Criteria: Format: [N children hidden by depth limit]

        Task: T007
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree", "--depth", "1"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Should have specific format: [N children hidden by depth limit]
        import re

        pattern = r"\[\d+ children? hidden by depth limit\]"
        match = re.search(pattern, stdout, re.IGNORECASE)
        assert match, f"Expected '[N children hidden by depth limit]' format: {stdout}"

    def test_given_depth_three_when_tree_then_shows_three_levels(self, scanned_project):
        """
        Purpose: Verifies depth=3 shows files, classes, and methods.
        Quality Contribution: Full code structure visible.
        Acceptance Criteria: All three levels visible for our test fixture.

        Task: T006
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree", "--depth", "3"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Should see all three levels: files (📄), classes (📦), methods (ƒ)
        assert "📄" in stdout, f"Expected file icons: {stdout}"
        # At depth 3, methods should be visible
        # Our fixture has Calculator with add/subtract methods
        has_methods = (
            "ƒ" in stdout or "add" in stdout.lower() or "subtract" in stdout.lower()
        )
        assert has_methods, f"Expected methods at depth 3: {stdout}"


# T008-T009: Tests for summary line format (AC9 counts)


@pytest.mark.unit
class TestSummaryLine:
    """T008-T009: Tests for summary line format (AC9 partial).

    AC9 (partial): Summary shows counts: "Found N nodes in M files"
    Note: Freshness timestamp is deferred to Phase 3.
    """

    def test_given_tree_when_complete_then_shows_checkmark(self, scanned_project):
        """
        Purpose: Verifies summary line starts with checkmark.
        Quality Contribution: Visual confirmation of success.
        Acceptance Criteria: ✓ present in summary.

        Task: T008
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Should have checkmark in summary
        assert "✓" in stdout, f"Expected ✓ in summary: {stdout}"

    def test_given_tree_when_complete_then_shows_found_format(self, scanned_project):
        """
        Purpose: Verifies summary uses "Found N nodes in M files" format.
        Quality Contribution: Clear count reporting.
        Acceptance Criteria: Exact format matches AC9.

        Task: T008
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Should have "Found N nodes in M files" format
        import re

        pattern = r"Found \d+ nodes? in \d+ files?"
        match = re.search(pattern, stdout)
        assert match, f"Expected 'Found N nodes in M files' format: {stdout}"

    def test_given_tree_when_complete_then_node_count_accurate(self, scanned_project):
        """
        Purpose: Verifies node count includes all displayed nodes.
        Quality Contribution: Accurate reporting for users.
        Acceptance Criteria: Count >= 6 for our fixture (3 files, 3+ classes/functions).

        Task: T009
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Extract node count
        import re

        match = re.search(r"Found (\d+) nodes?", stdout)
        assert match, f"Could not find node count: {stdout}"
        node_count = int(match.group(1))
        # Our fixture has:
        # - calculator.py (1) + Calculator class (1) + add/subtract methods (2)
        # - utils.py (1) + helper/format_output functions (2)
        # - models/item.py (1) + Item class (1) + __init__ method (1)
        # Total: at least 10 nodes
        assert node_count >= 6, f"Expected at least 6 nodes, got {node_count}"

    def test_given_tree_when_complete_then_file_count_accurate(self, scanned_project):
        """
        Purpose: Verifies file count is accurate.
        Quality Contribution: Accurate reporting for users.
        Acceptance Criteria: Count >= 3 for our fixture (3 .py files).

        Task: T009
        """
        from fs2.cli.main import app

        result = runner.invoke(app, ["tree"])

        assert result.exit_code == 0
        stdout = result.stdout
        # Extract file count
        import re

        match = re.search(r"in (\d+) files?", stdout)
        assert match, f"Could not find file count: {stdout}"
        file_count = int(match.group(1))
        # Our fixture has 3 Python files
        assert file_count >= 3, f"Expected at least 3 files, got {file_count}"

    def test_given_depth_limit_when_tree_then_summary_counts_visible_only(
        self, scanned_project
    ):
        """
        Purpose: Verifies summary counts only visible nodes, not hidden.
        Quality Contribution: Accurate count reflects what user sees.
        Acceptance Criteria: Count with --depth 1 < count with no limit.

        Task: T009
        """
        import re

        from fs2.cli.main import app

        # Get full count
        result_full = runner.invoke(app, ["tree"])
        match_full = re.search(r"Found (\d+) nodes?", result_full.stdout)
        full_count = int(match_full.group(1)) if match_full else 0

        # Get limited count
        result_limited = runner.invoke(app, ["tree", "--depth", "1"])
        match_limited = re.search(r"Found (\d+) nodes?", result_limited.stdout)
        limited_count = int(match_limited.group(1)) if match_limited else 0

        # Limited should be less than full
        assert limited_count < full_count, (
            f"Expected depth-limited count ({limited_count}) < full count ({full_count})"
        )
