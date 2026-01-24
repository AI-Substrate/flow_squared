"""Integration tests for SolidLspAdapter with real gopls server.

TDD Phase: RED - These tests will fail until gopls support is verified.

Tests cover:
- AC12: Go support via gopls with installation instructions
- AC18: Integration tests pass with all 4 real servers
- AC08: get_references() returns CodeEdge list with confidence=1.0
- AC09: get_definition() returns CodeEdge with EdgeType.CALLS

Per Testing Philosophy: Full TDD approach with real LSP server.
Per Mock Usage Policy: Integration tests MUST use real LSP servers.
"""

import shutil
from pathlib import Path

import pytest

from fs2.core.models.code_edge import CodeEdge
from fs2.core.models.edge_type import EdgeType

# Skip entire module if gopls is not available
pytestmark = pytest.mark.skipif(
    not shutil.which("gopls"),
    reason="gopls language server not installed",
)


@pytest.fixture
def go_project() -> Path:
    """Use existing go_project fixture for LSP testing.

    Structure:
    - cmd/server/main.go: calls auth.Validate() from internal/auth
    - internal/auth/auth.go: defines Validate() function
    - go.mod: module declaration
    """
    fixture_path = Path(__file__).parent.parent / "fixtures" / "lsp" / "go_project"
    assert fixture_path.exists(), f"Go project fixture not found at {fixture_path}"
    return fixture_path


@pytest.fixture
def config_service():
    """Create a ConfigurationService with LspConfig."""
    from fs2.config.objects import LspConfig
    from fs2.config.service import FakeConfigurationService

    return FakeConfigurationService(LspConfig(timeout_seconds=30.0))


@pytest.mark.integration
class TestGoplsIntegration:
    """Integration tests for SolidLspAdapter with real gopls server.

    Per AC12: These tests use real gopls server to validate
    the adapter works end-to-end with Go projects.
    """

    def test_given_go_project_when_initialize_then_server_starts(
        self, go_project: Path, config_service
    ):
        """AC12: gopls server starts successfully.

        Why: Validates that gopls can be initialized and becomes ready.
        Contract: initialize("go", project_root) -> is_ready() == True
        Quality Contribution: Catches gopls initialization errors.

        Worked Example:
            Input: go_project with go.mod
            Output: is_ready() returns True
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)

        try:
            adapter.initialize("go", go_project)
            assert adapter.is_ready() is True
        finally:
            adapter.shutdown()

    def test_given_go_project_when_shutdown_then_server_stops(
        self, go_project: Path, config_service
    ):
        """Lifecycle: shutdown() stops gopls server.

        Why: Validates shutdown lifecycle is correct.
        Contract: shutdown() sets is_ready() to False.
        Quality Contribution: Ensures cleanup happens correctly.
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)
        adapter.initialize("go", go_project)

        assert adapter.is_ready() is True

        adapter.shutdown()

        assert adapter.is_ready() is False

    def test_given_go_project_when_get_definition_then_returns_code_edge(
        self, go_project: Path, config_service
    ):
        """AC12: get_definition returns CodeEdge with EdgeType.CALLS.

        Why: Validates definition lookups work for Go code.
        Contract: get_definition(file, line, col) -> list[CodeEdge] with CALLS type
        Quality Contribution: Catches Go definition resolution errors.

        Worked Example:
            Input: cmd/server/main.go:9:12 (auth.Validate call site)
            Output: CodeEdge pointing to internal/auth/auth.go:Validate with EdgeType.CALLS
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)

        try:
            adapter.initialize("go", go_project)
            assert adapter.is_ready() is True

            # Get definition of 'Validate' call in main.go
            # Line 9 (0-indexed): `isValid := auth.Validate("testuser")`
            # 'Validate' starts around column 20
            edges = adapter.get_definition("cmd/server/main.go", line=9, column=20)

            # Should find definition in internal/auth/auth.go
            assert isinstance(edges, list)
            assert len(edges) >= 1

            # Definition edges should have CALLS type per DYK-3
            for edge in edges:
                assert isinstance(edge, CodeEdge)
                assert edge.confidence == 1.0
                assert edge.resolution_rule == "lsp:definition"
                assert edge.edge_type == EdgeType.CALLS

        finally:
            adapter.shutdown()

    def test_given_go_project_when_get_references_then_returns_code_edges(
        self, go_project: Path, config_service
    ):
        """AC12: get_references returns CodeEdge list with confidence=1.0.

        Why: Validates that LSP references are correctly translated to CodeEdge.
        Contract: get_references(file, line, col) -> list[CodeEdge] with confidence=1.0
        Quality Contribution: Catches LSP→CodeEdge translation errors for Go.

        Note: gopls may return empty list for references in small test fixtures.
        The primary validation is that the call succeeds and returns proper types.

        Worked Example:
            Input: internal/auth/auth.go:5:5 (Validate function)
            Output: CodeEdge from main.go to auth.go with EdgeType.REFERENCES (if found)
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)

        try:
            adapter.initialize("go", go_project)
            assert adapter.is_ready() is True

            # Get references to 'Validate' function definition
            # Line 5 (0-indexed): `func Validate(username string) bool {`
            edges = adapter.get_references("internal/auth/auth.go", line=5, column=5)

            # Should return a list (may be empty if gopls doesn't find refs)
            assert isinstance(edges, list)

            # If references were found, validate their structure
            for edge in edges:
                assert isinstance(edge, CodeEdge)
                assert edge.confidence == 1.0
                assert edge.resolution_rule == "lsp:references"
                assert edge.edge_type == EdgeType.REFERENCES

        finally:
            adapter.shutdown()

    def test_given_go_when_cross_file_reference_then_finds_other_file(
        self, go_project: Path, config_service
    ):
        """CRITICAL: Cross-file definition resolution works.

        Why: Validates gopls can resolve cross-file function calls.
        Contract: Definition lookup crosses file boundaries.
        Quality Contribution: Catches cross-file resolution failures.

        Worked Example:
            Input: cmd/server/main.go:9 (call to auth.Validate)
            Output: CodeEdge pointing to internal/auth/auth.go
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)

        try:
            adapter.initialize("go", go_project)
            assert adapter.is_ready() is True

            # Get definition of cross-file call: auth.Validate
            edges = adapter.get_definition("cmd/server/main.go", line=9, column=20)

            assert len(edges) >= 1

            # Verify the edge points to a different file
            for edge in edges:
                # The target should reference auth.go, not main.go
                assert "auth" in edge.target_node_id.lower()
                assert edge.confidence == 1.0

        finally:
            adapter.shutdown()

    def test_given_adapter_when_shutdown_twice_then_no_error(
        self, go_project: Path, config_service
    ):
        """shutdown() is idempotent - can be called multiple times.

        Why: Per Invariants, shutdown() must be idempotent.
        Contract: Multiple shutdown() calls do not raise.
        Quality Contribution: Prevents resource cleanup bugs.
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)
        adapter.initialize("go", go_project)

        # Should not raise on multiple calls
        adapter.shutdown()
        adapter.shutdown()
        adapter.shutdown()

        assert adapter.is_ready() is False


@pytest.mark.integration
class TestGoplsErrorHandling:
    """Tests for SolidLspAdapter error handling with gopls.

    Per AC05: SolidLspAdapter wraps SolidLSP with exception translation.
    """

    def test_given_uninitialized_adapter_when_get_references_then_raises_error(
        self, config_service
    ):
        """RuntimeError raised when calling methods before initialize().

        Why: Validates adapter enforces initialization lifecycle.
        Contract: get_references() on uninitialized adapter -> RuntimeError
        Quality Contribution: Catches lifecycle bugs early.
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)

        # Should not be ready before initialize
        assert adapter.is_ready() is False

        with pytest.raises(RuntimeError, match="not initialized"):
            adapter.get_references("cmd/server/main.go", line=0, column=0)
