"""FakeLspAdapter - Test double for LSP adapter.

This is the canonical fake implementation of LspAdapter for testing.
Use this to test services that depend on LspAdapter without starting
real language servers.

Architecture:
- Inherits from LspAdapter ABC
- Receives ConfigurationService (registry) via constructor
- Adapter calls config.require(LspConfig) internally
- No external dependencies (it's a fake)

Per Discovery 08: Fakes over mocks; inherits from ABC with call_history.
Per DYK-1: Uses method-specific response setters (set_definition_response,
           set_references_response) instead of single set_response().
Per Discovery 06: Constructor receives ConfigurationService, NOT extracted config.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fs2.config.objects import LspConfig
from fs2.core.adapters.lsp_adapter import LspAdapter
from fs2.core.models.code_edge import CodeEdge

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


class FakeLspAdapter(LspAdapter):
    """Fake implementation of LspAdapter for testing.

    This implementation demonstrates the full adapter fake pattern:
    - Constructor receives ConfigurationService (registry), not specific config
    - Adapter calls config.require(LspConfig) internally (no concept leakage)
    - Domain-only return types (list[CodeEdge])
    - Domain-only exceptions (LspAdapterError hierarchy)
    - Method-specific response setters (DYK-1 pattern)
    - call_history tracking for test assertions

    Usage in tests:
        ```python
        from fs2.config.objects import LspConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.lsp_adapter_fake import FakeLspAdapter
        from fs2.core.models.code_edge import CodeEdge, EdgeType

        # Setup
        config = FakeConfigurationService(LspConfig())
        adapter = FakeLspAdapter(config)

        # Configure responses (DYK-1: method-specific setters)
        adapter.set_references_response([
            CodeEdge(
                source_node_id="file:app.py",
                target_node_id="file:lib.py",
                edge_type=EdgeType.REFERENCES,
                confidence=1.0,
                resolution_rule="lsp:references"
            )
        ])

        # Initialize and use
        adapter.initialize("python", Path("/project"))
        refs = adapter.get_references("app.py", line=10, column=5)

        # Verify
        assert len(refs) == 1
        assert len(adapter.call_history) == 2
        ```
    """

    def __init__(self, config: "ConfigurationService") -> None:
        """Initialize with ConfigurationService registry.

        Args:
            config: ConfigurationService registry (NOT LspConfig).
                    Adapter will call config.require(LspConfig) internally.

        Raises:
            MissingConfigurationError: If LspConfig not in registry.
        """
        # Adapter gets its own config - composition root doesn't extract it
        self._lsp_config = config.require(LspConfig)
        self._call_history: list[dict[str, Any]] = []
        self._is_ready: bool = False
        self._language: str | None = None
        self._project_root: Path | None = None

        # Per DYK-1: Method-specific responses
        self._definition_response: list[CodeEdge] = []
        self._references_response: list[CodeEdge] = []
        self._error: Exception | None = None

    @property
    def call_history(self) -> list[dict[str, Any]]:
        """Access recorded calls for test assertions.

        Returns:
            List of dicts with 'method', 'args', 'kwargs' for each call.
        """
        return self._call_history

    def set_definition_response(self, edges: list[CodeEdge]) -> None:
        """Configure response for get_definition() calls.

        Per DYK-1: Use method-specific setters for independent responses.

        Args:
            edges: List of CodeEdge instances to return.
        """
        self._definition_response = edges

    def set_references_response(self, edges: list[CodeEdge]) -> None:
        """Configure response for get_references() calls.

        Per DYK-1: Use method-specific setters for independent responses.

        Args:
            edges: List of CodeEdge instances to return.
        """
        self._references_response = edges

    def set_error(self, error: Exception) -> None:
        """Configure error to raise on next method call.

        The error will be raised on the next call to get_references() or
        get_definition(), then cleared.

        Args:
            error: Exception to raise (typically LspAdapterError subclass).
        """
        self._error = error

    def initialize(self, language: str, project_root: Path) -> None:
        """Initialize fake adapter for the specified language and project.

        Records the call and sets is_ready() to True.

        Args:
            language: Programming language identifier.
            project_root: Absolute path to project root directory.
        """
        self._call_history.append(
            {
                "method": "initialize",
                "args": (language, project_root),
                "kwargs": {},
            }
        )
        self._language = language
        self._project_root = project_root
        self._is_ready = True

    def shutdown(self) -> None:
        """Shutdown fake adapter.

        Records the call and sets is_ready() to False.
        Idempotent: Safe to call multiple times.
        """
        self._call_history.append(
            {
                "method": "shutdown",
                "args": (),
                "kwargs": {},
            }
        )
        self._is_ready = False

    def get_references(self, file_path: str, line: int, column: int) -> list[CodeEdge]:
        """Return configured references response.

        Args:
            file_path: Path to file (relative to project_root).
            line: 0-indexed line number.
            column: 0-indexed column number.

        Returns:
            Configured list of CodeEdge instances.

        Raises:
            Configured error if set via set_error().
        """
        self._call_history.append(
            {
                "method": "get_references",
                "args": (file_path, line, column),
                "kwargs": {},
            }
        )

        if self._error is not None:
            error = self._error
            self._error = None  # Clear after raising
            raise error

        return self._references_response

    def get_definition(self, file_path: str, line: int, column: int) -> list[CodeEdge]:
        """Return configured definition response.

        Args:
            file_path: Path to file (relative to project_root).
            line: 0-indexed line number.
            column: 0-indexed column number.

        Returns:
            Configured list of CodeEdge instances.

        Raises:
            Configured error if set via set_error().
        """
        self._call_history.append(
            {
                "method": "get_definition",
                "args": (file_path, line, column),
                "kwargs": {},
            }
        )

        if self._error is not None:
            error = self._error
            self._error = None  # Clear after raising
            raise error

        return self._definition_response

    def is_ready(self) -> bool:
        """Check if adapter is initialized and ready for queries.

        Returns:
            True if initialize() called and shutdown() not called.
        """
        return self._is_ready
