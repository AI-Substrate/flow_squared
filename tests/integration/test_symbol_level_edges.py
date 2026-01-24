"""Integration tests for symbol-level edge detection against EXPECTED_CALLS.md.

Purpose: Validates that LSP-based relationship extraction detects the edges
         documented in each language's EXPECTED_CALLS.md fixture file.

Quality Contribution: Ensures LSP integration detects expected edges accurately.

Per Phase 8 Tasks:
- T021: Write symbol-level edge integration tests validating against EXPECTED_CALLS.md

Why: The EXPECTED_CALLS.md files document what edges SHOULD be detected.
     This test validates our implementation matches those expectations.

Contract: For each language fixture, verify edges in EXPECTED_CALLS.md are found.

Usage Notes:
- Currently validates Python fixtures only (multi-language deferred to Phase 9)
- Uses pytest parametrization for each expected edge
- Requires Pyright LSP server installed
"""

from pathlib import Path
from typing import NamedTuple

import pytest

from fs2.config.objects import GraphConfig, LspConfig, ScanConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.ast_parser_impl import TreeSitterParser
from fs2.core.adapters.file_scanner_impl import FileSystemScanner
from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter
from fs2.core.repos.graph_store_impl import NetworkXGraphStore
from fs2.core.services.scan_pipeline import ScanPipeline


class ExpectedEdge(NamedTuple):
    """Expected edge from EXPECTED_CALLS.md."""

    id: str
    source_file: str
    source_symbol: str
    target_file: str
    target_symbol: str
    edge_type: str


# Python fixture expected edges from EXPECTED_CALLS.md
# Cross-file edges
PYTHON_CROSS_FILE_EDGES = [
    ExpectedEdge(
        "PY-CF-001", "src/app.py", "main", "src/auth.py", "AuthService.create", "calls"
    ),
    ExpectedEdge(
        "PY-CF-002", "src/app.py", "main", "src/auth.py", "AuthService.login", "calls"
    ),
    ExpectedEdge(
        "PY-CF-003", "src/app.py", "main", "src/utils.py", "format_date", "calls"
    ),
    ExpectedEdge(
        "PY-CF-004",
        "src/app.py",
        "process_user",
        "src/auth.py",
        "AuthService.__init__",
        "calls",
    ),
    ExpectedEdge(
        "PY-CF-005",
        "src/app.py",
        "process_user",
        "src/auth.py",
        "AuthService.login",
        "calls",
    ),
    ExpectedEdge(
        "PY-CF-006",
        "src/auth.py",
        "AuthService._validate",
        "src/utils.py",
        "validate_string",
        "calls",
    ),
]

# Same-file edges
PYTHON_SAME_FILE_EDGES = [
    ExpectedEdge(
        "PY-SF-001",
        "src/auth.py",
        "AuthService.__init__",
        "src/auth.py",
        "AuthService._setup",
        "calls",
    ),
    ExpectedEdge(
        "PY-SF-002",
        "src/auth.py",
        "AuthService.login",
        "src/auth.py",
        "AuthService._validate",
        "calls",
    ),
    ExpectedEdge(
        "PY-SF-003",
        "src/auth.py",
        "AuthService._validate",
        "src/auth.py",
        "AuthService._check_token",
        "calls",
    ),
    ExpectedEdge(
        "PY-SF-004",
        "src/auth.py",
        "AuthService.create",
        "src/auth.py",
        "AuthService.__init__",
        "calls",
    ),
]


@pytest.fixture
def python_fixture_path() -> Path:
    """Return path to python_multi_project fixture."""
    fixture_path = (
        Path(__file__).parent.parent / "fixtures" / "lsp" / "python_multi_project"
    )
    assert fixture_path.exists(), f"Fixture not found: {fixture_path}"
    return fixture_path


@pytest.fixture
def scan_python_fixture(python_fixture_path: Path, tmp_path: Path):
    """Scan Python fixture and return (store, edges) tuple."""
    src_path = python_fixture_path / "src"
    test_graph_path = tmp_path / "test_graph.pickle"

    config = FakeConfigurationService(
        ScanConfig(scan_paths=[str(src_path)], respect_gitignore=True),
        GraphConfig(graph_path=str(test_graph_path)),
        LspConfig(),
    )

    scanner = FileSystemScanner(config)
    parser = TreeSitterParser(config)
    store = NetworkXGraphStore(config)

    lsp_adapter = SolidLspAdapter(config)
    # Initialize with cwd as project root since node IDs are relative to cwd
    from pathlib import Path as PathLib

    lsp_adapter.initialize("python", PathLib.cwd())

    pipeline = ScanPipeline(
        config=config,
        file_scanner=scanner,
        ast_parser=parser,
        graph_store=store,
        graph_path=test_graph_path,
        lsp_adapter=lsp_adapter,
    )

    summary = pipeline.run()
    assert summary.success is True

    # Get all relationship edges
    all_edges = []
    for node in store.get_all_nodes():
        outgoing = store.get_relationships(node.node_id, direction="outgoing")
        for rel in outgoing:
            all_edges.append(
                {
                    "source_id": node.node_id,
                    "target_id": rel["node_id"],
                    "edge_type": rel["edge_type"],
                    "confidence": rel.get("confidence"),
                }
            )

    call_edges = [e for e in all_edges if e["edge_type"] == "calls"]

    # Clean up
    lsp_adapter.shutdown()

    return store, call_edges


def edge_matches(edge: dict, expected: ExpectedEdge) -> bool:
    """Check if a detected edge matches an expected edge.

    Matching criteria:
    - Source contains expected source symbol name
    - Target contains expected target symbol name OR class name (for class.method patterns)
    - Source file path matches
    - Target file path matches (for cross-file) or same file (for same-file)

    Note: LSP may return class-level instead of method-level resolution,
    e.g., `AuthService` instead of `AuthService.create`. We accept both.
    """
    source_id = edge["source_id"]
    target_id = edge["target_id"]

    # Extract file paths from node IDs (format: category:path:symbol)
    source_parts = source_id.split(":")
    target_parts = target_id.split(":")

    # Handle different node ID formats
    if len(source_parts) >= 2:
        source_path = source_parts[1]
        source_parts[-1] if len(source_parts) >= 3 else ""
    else:
        source_path = ""

    if len(target_parts) >= 2:
        target_path = target_parts[1]
        target_parts[-1] if len(target_parts) >= 3 else ""
    else:
        target_path = ""

    # Check source matches
    source_file_match = expected.source_file.replace(
        "src/", ""
    ) in source_path or source_path.endswith(expected.source_file.split("/")[-1])
    source_symbol_match = expected.source_symbol.split(".")[-1] in source_id

    # Check target matches - allow class-level when method expected
    # e.g., expected="AuthService.create" should match detected="AuthService"
    target_file_match = expected.target_file.replace(
        "src/", ""
    ) in target_path or target_path.endswith(expected.target_file.split("/")[-1])

    # Target symbol matching: accept method name OR class name
    target_parts_expected = expected.target_symbol.split(".")
    target_symbol_match = any(part in target_id for part in target_parts_expected)

    return (
        source_file_match
        and source_symbol_match
        and target_file_match
        and target_symbol_match
    )


class TestPythonSymbolLevelEdges:
    """T021: Symbol-level edge validation for Python fixtures."""

    @pytest.mark.slow
    @pytest.mark.lsp
    def test_given_python_fixtures_when_scanned_then_detects_cross_file_edges(
        self, scan_python_fixture
    ):
        """
        Purpose: Validates cross-file edges from EXPECTED_CALLS.md.
        Quality Contribution: Ensures LSP detects cross-file relationships.
        Acceptance Criteria: ≥50% of cross-file edges detected.

        Why: Cross-file detection is the primary value of LSP integration.
        Contract: Edges documented in EXPECTED_CALLS.md should be found.
        """
        store, call_edges = scan_python_fixture

        print("\n=== Python Cross-File Edge Validation ===")
        print(f"Total call edges detected: {len(call_edges)}")

        # Check each expected edge
        detected = []
        missing = []

        for expected in PYTHON_CROSS_FILE_EDGES:
            found = False
            for edge in call_edges:
                if edge_matches(edge, expected):
                    detected.append(expected)
                    found = True
                    break
            if not found:
                missing.append(expected)

        print(
            f"\nDetected cross-file edges ({len(detected)}/{len(PYTHON_CROSS_FILE_EDGES)}):"
        )
        for e in detected:
            print(f"  ✓ {e.id}: {e.source_symbol} -> {e.target_symbol}")

        print(
            f"\nMissing cross-file edges ({len(missing)}/{len(PYTHON_CROSS_FILE_EDGES)}):"
        )
        for e in missing:
            print(f"  ✗ {e.id}: {e.source_symbol} -> {e.target_symbol}")

        # Show all detected edges for debugging
        print("\nAll detected call edges:")
        for edge in call_edges[:20]:
            print(f"  {edge['source_id']} -> {edge['target_id']}")

        # Acceptance: ≥50% (3 of 6) cross-file edges
        detection_rate = len(detected) / len(PYTHON_CROSS_FILE_EDGES)
        assert detection_rate >= 0.5, (
            f"Cross-file detection rate {detection_rate:.0%} < 50%. "
            f"Missing: {[e.id for e in missing]}"
        )

    @pytest.mark.slow
    @pytest.mark.lsp
    def test_given_python_fixtures_when_scanned_then_detects_same_file_edges(
        self, scan_python_fixture
    ):
        """
        Purpose: Validates same-file edges from EXPECTED_CALLS.md.
        Quality Contribution: Ensures LSP detects intra-file method calls.
        Acceptance Criteria: ≥50% of same-file edges detected.

        Why: Same-file resolution validates method chain detection.
        Contract: Method calls within auth.py should be found.
        """
        store, call_edges = scan_python_fixture

        print("\n=== Python Same-File Edge Validation ===")
        print(f"Total call edges detected: {len(call_edges)}")

        detected = []
        missing = []

        for expected in PYTHON_SAME_FILE_EDGES:
            found = False
            for edge in call_edges:
                if edge_matches(edge, expected):
                    detected.append(expected)
                    found = True
                    break
            if not found:
                missing.append(expected)

        print(
            f"\nDetected same-file edges ({len(detected)}/{len(PYTHON_SAME_FILE_EDGES)}):"
        )
        for e in detected:
            print(f"  ✓ {e.id}: {e.source_symbol} -> {e.target_symbol}")

        print(
            f"\nMissing same-file edges ({len(missing)}/{len(PYTHON_SAME_FILE_EDGES)}):"
        )
        for e in missing:
            print(f"  ✗ {e.id}: {e.source_symbol} -> {e.target_symbol}")

        # Acceptance: ≥50% (2 of 4) same-file edges
        detection_rate = len(detected) / len(PYTHON_SAME_FILE_EDGES)
        assert detection_rate >= 0.5, (
            f"Same-file detection rate {detection_rate:.0%} < 50%. "
            f"Missing: {[e.id for e in missing]}"
        )

    @pytest.mark.slow
    @pytest.mark.lsp
    def test_given_python_fixtures_when_scanned_then_total_detection_rate_meets_threshold(
        self, scan_python_fixture
    ):
        """
        Purpose: Validates overall detection rate meets minimum threshold.
        Quality Contribution: End-to-end detection quality gate.
        Acceptance Criteria: ≥67% total detection rate.

        Why: Combined metric ensures LSP integration is production-ready.
        Contract: 10 expected edges → ≥7 detected.
        """
        store, call_edges = scan_python_fixture

        all_expected = PYTHON_CROSS_FILE_EDGES + PYTHON_SAME_FILE_EDGES

        detected = []
        for expected in all_expected:
            for edge in call_edges:
                if edge_matches(edge, expected):
                    detected.append(expected)
                    break

        detection_rate = len(detected) / len(all_expected)

        print("\n=== Total Detection Rate ===")
        print(f"Expected edges: {len(all_expected)}")
        print(f"Detected edges: {len(detected)}")
        print(f"Detection rate: {detection_rate:.0%}")

        # Minimum threshold: 67% (7 of 10)
        MIN_DETECTION_RATE = 0.67

        assert detection_rate >= MIN_DETECTION_RATE, (
            f"Total detection rate {detection_rate:.0%} < {MIN_DETECTION_RATE:.0%}. "
            f"Detected {len(detected)}/{len(all_expected)} edges."
        )


class TestEdgeValidationUtilities:
    """Unit tests for edge matching utilities."""

    def test_edge_matches_returns_true_for_matching_edge(self):
        """Verify edge_matches correctly identifies matching edges."""
        # Create edge dict
        edge = {
            "source_id": "callable:src/app.py:main",
            "target_id": "callable:src/auth.py:AuthService.login",
            "edge_type": "calls",
        }

        expected = ExpectedEdge(
            id="PY-CF-002",
            source_file="src/app.py",
            source_symbol="main",
            target_file="src/auth.py",
            target_symbol="AuthService.login",
            edge_type="calls",
        )

        assert edge_matches(edge, expected) is True

    def test_edge_matches_returns_false_for_non_matching_edge(self):
        """Verify edge_matches correctly rejects non-matching edges."""
        edge = {
            "source_id": "callable:src/utils.py:format_date",
            "target_id": "callable:src/utils.py:helper",
            "edge_type": "calls",
        }

        expected = ExpectedEdge(
            id="PY-CF-002",
            source_file="src/app.py",
            source_symbol="main",
            target_file="src/auth.py",
            target_symbol="AuthService.login",
            edge_type="calls",
        )

        assert edge_matches(edge, expected) is False
