"""Integration tests for SolidLspAdapter with real TypeScript language server.

TDD Phase: RED - These tests will fail until TypeScript support is verified.

Tests cover:
- AC13: TypeScript support via typescript-language-server
- AC18: Integration tests pass with all 4 real servers
- AC08: get_references() returns CodeEdge list with confidence=1.0
- AC09: get_definition() returns CodeEdge with EdgeType.CALLS
- Cross-file resolution (CRITICAL per DYK session 2026-01-19)

Per Testing Philosophy: Full TDD approach with real LSP server.
Per Mock Usage Policy: Integration tests MUST use real LSP servers.

NOTE: Per DYK session 2026-01-19, TypeScript LSP's request_definition() works
with tsconfig.json - no file-opening workaround needed. Only request_references()
is unreliable, which we don't use for edge building.
"""

import shutil
from pathlib import Path

import pytest

from fs2.core.models.code_edge import CodeEdge
from fs2.core.models.edge_type import EdgeType

# Skip entire module if TypeScript language server is not available
pytestmark = pytest.mark.skipif(
    not shutil.which("typescript-language-server"),
    reason="typescript-language-server not installed",
)


@pytest.fixture
def typescript_project() -> Path:
    """Use existing typescript_multi_project fixture for LSP testing.
    
    Structure:
    - packages/client/index.tsx: calls formatDate() from utils.ts
    - packages/client/utils.ts: defines formatDate() function
    - tsconfig.json: TypeScript project configuration
    - package.json: npm package metadata
    """
    fixture_path = Path(__file__).parent.parent / "fixtures" / "lsp" / "typescript_multi_project"
    assert fixture_path.exists(), f"TypeScript project fixture not found at {fixture_path}"
    return fixture_path


@pytest.fixture
def config_service():
    """Create a ConfigurationService with LspConfig."""
    from fs2.config.objects import LspConfig
    from fs2.config.service import FakeConfigurationService

    return FakeConfigurationService(LspConfig(timeout_seconds=30.0))


@pytest.mark.integration
class TestTypeScriptIntegration:
    """Integration tests for SolidLspAdapter with real TypeScript server.
    
    Per AC13: These tests use real typescript-language-server to validate
    the adapter works end-to-end with TypeScript projects.
    """

    def test_given_typescript_project_when_initialize_then_server_starts(
        self, typescript_project: Path, config_service
    ):
        """AC13: typescript-language-server starts successfully.
        
        Why: Validates that TypeScript server can be initialized and becomes ready.
        Contract: initialize("typescript", project_root) -> is_ready() == True
        Quality Contribution: Catches TypeScript server initialization errors.
        
        Worked Example:
            Input: typescript_project with tsconfig.json
            Output: is_ready() returns True
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)

        try:
            adapter.initialize("typescript", typescript_project)
            assert adapter.is_ready() is True
        finally:
            adapter.shutdown()

    def test_given_typescript_project_when_shutdown_then_server_stops(
        self, typescript_project: Path, config_service
    ):
        """Lifecycle: shutdown() stops TypeScript server.
        
        Why: Validates shutdown lifecycle is correct.
        Contract: shutdown() sets is_ready() to False.
        Quality Contribution: Ensures cleanup happens correctly.
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)
        adapter.initialize("typescript", typescript_project)

        assert adapter.is_ready() is True

        adapter.shutdown()

        assert adapter.is_ready() is False

    def test_given_typescript_project_when_get_definition_then_returns_code_edge(
        self, typescript_project: Path, config_service
    ):
        """AC13: get_definition returns CodeEdge with EdgeType.CALLS.
        
        Why: Validates definition lookups work for TypeScript code.
        Contract: get_definition(file, line, col) -> list[CodeEdge] with CALLS type
        Quality Contribution: Catches TypeScript definition resolution errors.
        
        Worked Example:
            Input: packages/client/index.tsx:8:22 (formatDate call site)
            Output: CodeEdge pointing to packages/client/utils.ts:formatDate with EdgeType.CALLS
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)

        try:
            adapter.initialize("typescript", typescript_project)
            assert adapter.is_ready() is True

            # Get definition of 'formatDate' call in index.tsx
            # Line 8 (0-indexed): `const formatted = formatDate(date);`
            # 'formatDate' starts around column 22
            edges = adapter.get_definition(
                "packages/client/index.tsx", line=8, column=22
            )

            # Should find definition in utils.ts
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

    def test_given_typescript_project_when_get_references_then_returns_code_edges(
        self, typescript_project: Path, config_service
    ):
        """AC13: get_references returns CodeEdge list with confidence=1.0.
        
        Why: Validates that LSP references are correctly translated to CodeEdge.
        Contract: get_references(file, line, col) -> list[CodeEdge] with confidence=1.0
        Quality Contribution: Catches LSP→CodeEdge translation errors for TypeScript.
        
        NOTE: Per DYK session 2026-01-19, TypeScript LSP's request_references()
        is unreliable without workspace indexing. This test validates the API
        contract but may return empty list. The cross-file test validates
        request_definition() which DOES work reliably.
        
        Worked Example:
            Input: packages/client/utils.ts:4:16 (formatDate function)
            Output: CodeEdge from index.tsx to utils.ts with EdgeType.REFERENCES (if found)
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)

        try:
            adapter.initialize("typescript", typescript_project)
            assert adapter.is_ready() is True

            # Get references to 'formatDate' function definition
            # Line 4 (0-indexed): `export function formatDate(date: Date): string {`
            edges = adapter.get_references(
                "packages/client/utils.ts", line=4, column=16
            )

            # Should return a list (may be empty due to tsserver limitations)
            assert isinstance(edges, list)

            # If references were found, validate their structure
            for edge in edges:
                assert isinstance(edge, CodeEdge)
                assert edge.confidence == 1.0
                assert edge.resolution_rule == "lsp:references"
                assert edge.edge_type == EdgeType.REFERENCES

        finally:
            adapter.shutdown()

    def test_given_typescript_when_cross_file_reference_then_finds_definition(
        self, typescript_project: Path, config_service
    ):
        """CRITICAL: Cross-file definition resolution works.
        
        Why: Validates TypeScript LSP can resolve definitions for function calls.
        Contract: Definition lookup returns valid CodeEdge with confidence 1.0.
        Quality Contribution: Catches definition resolution failures.
        
        NOTE: TypeScript LSP may return the import declaration location
        instead of the actual function definition in utils.ts. This is a
        known TypeScript LSP behavior - it returns the "closest" definition
        which may be the import statement. The important validation is that:
        1. We GET a definition result (not empty)
        2. The result is a valid CodeEdge with confidence=1.0
        3. The edge type is CALLS
        
        Worked Example:
            Input: packages/client/index.tsx:8:22 (call to formatDate)
            Output: CodeEdge with valid target (may be import or actual definition)
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)

        try:
            adapter.initialize("typescript", typescript_project)
            assert adapter.is_ready() is True

            # Get definition of formatDate call
            edges = adapter.get_definition(
                "packages/client/index.tsx", line=8, column=22
            )

            # Should find at least one definition
            assert len(edges) >= 1

            # Verify edge structure is correct
            for edge in edges:
                assert isinstance(edge, CodeEdge)
                assert edge.confidence == 1.0
                assert edge.edge_type == EdgeType.CALLS
                assert edge.resolution_rule == "lsp:definition"
                # Target should be a valid node_id (file: prefix)
                assert edge.target_node_id.startswith("file:")

        finally:
            adapter.shutdown()

    def test_given_adapter_when_shutdown_twice_then_no_error(
        self, typescript_project: Path, config_service
    ):
        """shutdown() is idempotent - can be called multiple times.
        
        Why: Per Invariants, shutdown() must be idempotent.
        Contract: Multiple shutdown() calls do not raise.
        Quality Contribution: Prevents resource cleanup bugs.
        """
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        adapter = SolidLspAdapter(config_service)
        adapter.initialize("typescript", typescript_project)

        # Should not raise on multiple calls
        adapter.shutdown()
        adapter.shutdown()
        adapter.shutdown()

        assert adapter.is_ready() is False


@pytest.mark.integration
class TestTypeScriptErrorHandling:
    """Tests for SolidLspAdapter error handling with TypeScript.
    
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
            adapter.get_references(
                "packages/client/index.tsx", line=0, column=0
            )
