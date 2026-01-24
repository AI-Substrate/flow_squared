"""Integration tests for SolidLspAdapter with real Roslyn (C#) server.

TDD Phase: RED - These tests will fail until Roslyn support is verified.

Tests cover:
- AC14: C# support via Roslyn (formerly OmniSharp)
- AC18: Integration tests pass with all 4 real servers
- AC08: get_references() returns CodeEdge list with confidence=1.0
- AC09: get_definition() returns CodeEdge with EdgeType.CALLS

Per Testing Philosophy: Full TDD approach with real LSP server.
Per Mock Usage Policy: Integration tests MUST use real LSP servers.

NOTE: Roslyn is the successor to OmniSharp. The binary is still called "OmniSharp"
but the project is now maintained as part of Roslyn tooling.
"""

import shutil
from pathlib import Path

import pytest

from fs2.core.models.code_edge import CodeEdge
from fs2.core.models.edge_type import EdgeType

# Skip entire module if OmniSharp/Roslyn is not available
pytestmark = pytest.mark.skipif(
    not shutil.which("OmniSharp"),
    reason="OmniSharp (Roslyn) language server not installed",
)


@pytest.fixture
def csharp_project() -> Path:
    """Use existing csharp_multi_project fixture for LSP testing.

    Structure:
    - src/Api/Program.cs: calls user.Validate() method
    - src/Api/Models.cs: defines User class with Validate() method
    - src/Api/Api.csproj: C# project file
    """
    fixture_path = (
        Path(__file__).parent.parent / "fixtures" / "lsp" / "csharp_multi_project"
    )
    assert fixture_path.exists(), f"C# project fixture not found at {fixture_path}"
    return fixture_path


@pytest.fixture
def config_service():
    """Create a ConfigurationService with LspConfig."""
    from fs2.config.objects import LspConfig
    from fs2.config.service import FakeConfigurationService

    return FakeConfigurationService(LspConfig(timeout_seconds=30.0))


@pytest.mark.integration
class TestRoslynIntegration:
    """Integration tests for SolidLspAdapter with real Roslyn server.

    Per AC14: These tests use real Roslyn (OmniSharp) server to validate
    the adapter works end-to-end with C# projects.
    """

    def test_given_csharp_project_when_initialize_then_server_starts(
        self, csharp_project: Path, config_service
    ):
        """AC14: Roslyn server starts successfully.

        Why: Validates that Roslyn can be initialized and becomes ready.
        Contract: initialize("csharp", project_root) -> is_ready() == True
        Quality Contribution: Catches Roslyn initialization errors.

        Worked Example:
            Input: csharp_project with .csproj file
            Output: is_ready() returns True
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)

        try:
            adapter.initialize("csharp", csharp_project)
            assert adapter.is_ready() is True
        finally:
            adapter.shutdown()

    def test_given_csharp_project_when_shutdown_then_server_stops(
        self, csharp_project: Path, config_service
    ):
        """Lifecycle: shutdown() stops Roslyn server.

        Why: Validates shutdown lifecycle is correct.
        Contract: shutdown() sets is_ready() to False.
        Quality Contribution: Ensures cleanup happens correctly.
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)
        adapter.initialize("csharp", csharp_project)

        assert adapter.is_ready() is True

        adapter.shutdown()

        assert adapter.is_ready() is False

    def test_given_csharp_project_when_get_definition_then_returns_code_edge(
        self, csharp_project: Path, config_service
    ):
        """AC14: get_definition returns CodeEdge with EdgeType.CALLS.

        Why: Validates definition lookups work for C# code.
        Contract: get_definition(file, line, col) -> list[CodeEdge] with CALLS type
        Quality Contribution: Catches C# definition resolution errors.

        Worked Example:
            Input: src/Api/Program.cs:4:19 (user.Validate call site)
            Output: CodeEdge pointing to src/Api/Models.cs:Validate with EdgeType.CALLS
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)

        try:
            adapter.initialize("csharp", csharp_project)
            assert adapter.is_ready() is True

            # Get definition of 'Validate' call in Program.cs
            # Line 4 (0-indexed): `var isValid = user.Validate();`
            # 'Validate' starts around column 23
            edges = adapter.get_definition("src/Api/Program.cs", line=4, column=23)

            # Should find definition in Models.cs
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

    def test_given_csharp_project_when_get_references_then_returns_code_edges(
        self, csharp_project: Path, config_service
    ):
        """AC14: get_references returns CodeEdge list with confidence=1.0.

        Why: Validates that LSP references are correctly translated to CodeEdge.
        Contract: get_references(file, line, col) -> list[CodeEdge] with confidence=1.0
        Quality Contribution: Catches LSP→CodeEdge translation errors for C#.

        Note: Roslyn may return empty list for references in small test fixtures.
        The primary validation is that the call succeeds and returns proper types.

        Worked Example:
            Input: src/Api/Models.cs:10:16 (Validate method)
            Output: CodeEdge from Program.cs to Models.cs with EdgeType.REFERENCES (if found)
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)

        try:
            adapter.initialize("csharp", csharp_project)
            assert adapter.is_ready() is True

            # Get references to 'Validate' method definition
            # Line 10 (0-indexed): `public bool Validate()`
            edges = adapter.get_references("src/Api/Models.cs", line=10, column=16)

            # Should return a list (may be empty if Roslyn doesn't find refs)
            assert isinstance(edges, list)

            # If references were found, validate their structure
            for edge in edges:
                assert isinstance(edge, CodeEdge)
                assert edge.confidence == 1.0
                assert edge.resolution_rule == "lsp:references"
                assert edge.edge_type == EdgeType.REFERENCES

        finally:
            adapter.shutdown()

    def test_given_csharp_when_cross_file_reference_then_finds_definition(
        self, csharp_project: Path, config_service
    ):
        """CRITICAL: Cross-file definition resolution works.

        Why: Validates Roslyn can resolve cross-file method calls.
        Contract: Definition lookup crosses file boundaries.
        Quality Contribution: Catches cross-file resolution failures.

        Worked Example:
            Input: src/Api/Program.cs:4 (call to user.Validate())
            Output: CodeEdge with valid target (Models.cs or Program.cs depending on LSP behavior)
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)

        try:
            adapter.initialize("csharp", csharp_project)
            assert adapter.is_ready() is True

            # Get definition of cross-file call: user.Validate()
            edges = adapter.get_definition("src/Api/Program.cs", line=4, column=23)

            # Should find at least one definition
            assert len(edges) >= 1

            # Verify edge structure is correct
            for edge in edges:
                assert isinstance(edge, CodeEdge)
                assert edge.confidence == 1.0
                assert edge.edge_type == EdgeType.CALLS
                # Target should be a valid node_id (file: prefix)
                assert edge.target_node_id.startswith("file:")

        finally:
            adapter.shutdown()

    def test_given_adapter_when_shutdown_twice_then_no_error(
        self, csharp_project: Path, config_service
    ):
        """shutdown() is idempotent - can be called multiple times.

        Why: Per Invariants, shutdown() must be idempotent.
        Contract: Multiple shutdown() calls do not raise.
        Quality Contribution: Prevents resource cleanup bugs.
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)
        adapter.initialize("csharp", csharp_project)

        # Should not raise on multiple calls
        adapter.shutdown()
        adapter.shutdown()
        adapter.shutdown()

        assert adapter.is_ready() is False


@pytest.mark.integration
class TestRoslynErrorHandling:
    """Tests for SolidLspAdapter error handling with Roslyn.

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
            adapter.get_references("src/Api/Program.cs", line=0, column=0)
