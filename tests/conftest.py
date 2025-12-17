"""
Shared pytest configuration and fixtures for fs2.

Per Critical Finding 12: Fixtures mirror domain structure.
- Shared fixtures here (domain types, fakes)
- Test-specific fixtures in test files

Per Insight #2: Warn about singleton pollution.
Per Insight #6: clean_config_env fixture for test isolation.
Per Phase 3: TestContext fixture for pre-wired DI.
"""

import os
import sys
import warnings
from dataclasses import dataclass

import pytest


def pytest_configure(config):
    """Register custom markers and warn about singleton pollution.

    Per Insight #2: Test-time warning for singleton pollution.
    If fs2.config.settings was imported before tests run, it may
    cause test pollution with cached values.
    """
    # Check for singleton pollution
    if "fs2.config" in sys.modules:
        _mod = sys.modules["fs2.config"]
        if hasattr(_mod, "settings") and _mod.settings is not None:
            warnings.warn(
                "fs2.config.settings singleton was imported before tests! "
                "This may cause test pollution. "
                "Use 'from fs2.config.models import FS2Settings' in tests.",
                UserWarning,
                stacklevel=1,
            )


@pytest.fixture
def clean_config_env(monkeypatch):
    """Clear all FS2_* environment variables for test isolation.

    Per Insight #6: Use this fixture in config tests to ensure
    no .env or inherited env var pollution.

    Usage:
        def test_something(clean_config_env, monkeypatch):
            monkeypatch.setenv("FS2_FOO", "value")
            # ... test with known state
    """
    for key in list(os.environ.keys()):
        if key.startswith("FS2_"):
            monkeypatch.delenv(key, raising=False)
    yield


# Phase 3: Pre-wired test dependencies


@dataclass
class TestContext:
    """Pre-wired dependencies for tests.

    Provides a ready-to-use DI container with common test dependencies.
    Tests can use this directly or extract individual components.

    Attributes:
        config: FakeConfigurationService with LogAdapterConfig pre-registered
        logger: FakeLogAdapter for capturing log messages

    Usage:
        def test_something(test_context):
            service = SomeService(config=test_context.config, logger=test_context.logger)
            service.do_work()
            assert len(test_context.logger.messages) == 1
    """

    config: "FakeConfigurationService"  # noqa: F821
    logger: "FakeLogAdapter"  # noqa: F821


@pytest.fixture
def test_context():
    """Pre-configured test context with logger and config.

    Per Phase 3 Insight #2: Reduces boilerplate for tests that need
    a working ConfigurationService + FakeLogAdapter combination.

    The config comes pre-loaded with LogAdapterConfig(min_level="DEBUG")
    so all log levels are captured by default.

    Usage:
        def test_service_logs_on_start(test_context):
            service = MyService(
                config=test_context.config,
                logger=test_context.logger
            )
            service.start()
            assert any("started" in m.message.lower() for m in test_context.logger.messages)
    """
    from fs2.config.objects import LogAdapterConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.log_adapter_fake import FakeLogAdapter

    config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
    logger = FakeLogAdapter(config)
    return TestContext(config=config, logger=logger)


# Phase 3: AST Parser fixtures


@pytest.fixture
def ast_samples_path():
    """Path to the ast_samples fixtures directory.

    Per Phase 3 Task T000k: Provides convenient access to sample source files
    for AST parser tests.

    Usage:
        def test_parse_python(ast_samples_path):
            py_file = ast_samples_path / "python" / "simple_class.py"
            # ... parse the file
    """
    from pathlib import Path

    return Path(__file__).parent / "fixtures" / "ast_samples"


# Tree command fixtures (Phase 1: tree-command)


@dataclass
class ScannedFixturesContext:
    """Context for tests using the scanned fixtures graph.

    Attributes:
        store: NetworkXGraphStore with loaded graph.
        graph_path: Path to the graph pickle file.
        fixtures_path: Path to the ast_samples directory that was scanned.
        project_path: Temporary project directory (with .fs2/config.yaml).
    """

    store: "NetworkXGraphStore"  # noqa: F821
    graph_path: "Path"  # noqa: F821
    fixtures_path: "Path"  # noqa: F821
    project_path: "Path"  # noqa: F821


@pytest.fixture(scope="session")
def _scanned_fixtures_graph_session(tmp_path_factory):
    """Session-scoped fixture that scans ast_samples once.

    Internal fixture - use scanned_fixtures_graph instead.
    Creates a real graph by running ScanPipeline on tests/fixtures/ast_samples/.
    This is expensive, so it's session-scoped to run only once per test session.

    Returns:
        ScannedFixturesContext with store, paths, etc.
    """
    from pathlib import Path

    from fs2.config.objects import GraphConfig, ScanConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters import FileSystemScanner, TreeSitterParser
    from fs2.core.repos import NetworkXGraphStore
    from fs2.core.services import ScanPipeline

    # Get fixtures path
    fixtures_path = Path(__file__).parent / "fixtures" / "ast_samples"

    # Create temp project directory
    project_path = tmp_path_factory.mktemp("scanned_fixtures")
    config_dir = project_path / ".fs2"
    config_dir.mkdir()

    # Create config
    scan_config = ScanConfig(
        scan_paths=[str(fixtures_path)],
        respect_gitignore=False,
        max_file_size_kb=500,
    )
    graph_config = GraphConfig(graph_path=str(config_dir / "graph.pickle"))

    # Create configuration service with both configs
    config = FakeConfigurationService(scan_config, graph_config)

    # Create adapters and pipeline
    file_scanner = FileSystemScanner(config)
    ast_parser = TreeSitterParser(config)
    graph_store = NetworkXGraphStore(config)

    pipeline = ScanPipeline(
        config=config,
        file_scanner=file_scanner,
        ast_parser=ast_parser,
        graph_store=graph_store,
    )

    # Run scan
    summary = pipeline.run()

    # Verify scan succeeded
    assert summary.files_scanned > 0, "Fixture scan should find files"
    assert summary.nodes_created > 0, "Fixture scan should create nodes"

    # Save graph
    graph_path = config_dir / "graph.pickle"
    graph_store.save(graph_path)

    # Create fresh store and load (to test load path)
    loaded_store = NetworkXGraphStore(config)
    loaded_store.load(graph_path)

    # Write config.yaml for CLI tests
    config_yaml = config_dir / "config.yaml"
    config_yaml.write_text(f"""scan:
  scan_paths:
    - "{fixtures_path}"
  respect_gitignore: false
graph:
  graph_path: "{graph_path}"
""")

    return ScannedFixturesContext(
        store=loaded_store,
        graph_path=graph_path,
        fixtures_path=fixtures_path,
        project_path=project_path,
    )


@pytest.fixture
def scanned_fixtures_graph(_scanned_fixtures_graph_session, monkeypatch):
    """Function-scoped fixture providing access to pre-scanned fixtures graph.

    Per Phase 1 Insight #4: High-fidelity real graph from ast_samples.
    Scans tests/fixtures/ast_samples/ once per session using real ScanPipeline.
    Each test gets its own working directory context via monkeypatch.chdir().

    Usage:
        def test_tree_with_real_graph(scanned_fixtures_graph):
            # Working directory is already set to project with graph
            result = runner.invoke(app, ["tree"])
            assert result.exit_code == 0

    Returns:
        ScannedFixturesContext with store, graph_path, fixtures_path, project_path.
    """
    ctx = _scanned_fixtures_graph_session

    # Change to project directory for CLI tests
    monkeypatch.chdir(ctx.project_path)
    monkeypatch.setenv("NO_COLOR", "1")

    return ctx


# Shared CLI Test Fixtures (per plan-005 T000)
# These fixtures are used by multiple CLI test files (scan, tree, get-node)


@pytest.fixture
def scanned_project(tmp_path, monkeypatch):
    """Create a simple project with scanned graph.

    Per plan-005 T000: Shared fixture for CLI tests needing a valid graph.
    Creates source files, runs scan, returns project path.

    Usage:
        def test_command(scanned_project, monkeypatch):
            monkeypatch.chdir(scanned_project)
            result = runner.invoke(app, ["tree"])
            assert result.exit_code == 0

    Returns:
        Path to project root with valid .fs2/graph.pickle.
    """
    from typer.testing import CliRunner

    runner = CliRunner()

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
    """Create a project with config but no graph file.

    Per plan-005 T000: Shared fixture for testing "missing graph" errors.
    Has valid .fs2/config.yaml but no graph.pickle.

    Usage:
        def test_missing_graph(config_only_project, monkeypatch):
            monkeypatch.chdir(config_only_project)
            result = runner.invoke(app, ["tree"])
            assert result.exit_code == 1

    Returns:
        Path to project root with config but no graph.
    """
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


@pytest.fixture
def corrupted_graph_project(tmp_path):
    """Create a project with a corrupted graph file.

    Per plan-005 T000: Shared fixture for testing "corrupted graph" errors.
    Has valid config and a graph.pickle that is not valid pickle data.

    Usage:
        def test_corrupted_graph(corrupted_graph_project, monkeypatch):
            monkeypatch.chdir(corrupted_graph_project)
            result = runner.invoke(app, ["get-node", "file:test.py"])
            assert result.exit_code == 2

    Returns:
        Path to project root with corrupted graph.
    """
    config_dir = tmp_path / ".fs2"
    config_dir.mkdir()

    config_file = config_dir / "config.yaml"
    config_file.write_text(f"""scan:
  scan_paths:
    - "{tmp_path}"
graph:
  graph_path: ".fs2/graph.pickle"
""")

    # Create corrupted graph file (invalid pickle data)
    graph_file = config_dir / "graph.pickle"
    graph_file.write_bytes(b"not valid pickle data - corrupted!")

    return tmp_path


@pytest.fixture
def project_without_config(tmp_path):
    """Create a project without .fs2/config.yaml.

    Per plan-005 T000: Shared fixture for testing "missing config" errors.
    Has Python files but no .fs2/ directory at all.

    Usage:
        def test_missing_config(project_without_config, monkeypatch):
            monkeypatch.chdir(project_without_config)
            result = runner.invoke(app, ["scan"])
            assert result.exit_code == 1
            assert "init" in result.stdout.lower()

    Returns:
        Path to project root with no config.
    """
    # Just create a Python file, no config
    (tmp_path / "test.py").write_text("x = 1")
    return tmp_path
