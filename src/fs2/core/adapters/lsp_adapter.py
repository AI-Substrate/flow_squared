"""LspAdapter ABC interface.

Defines the contract for Language Server Protocol adapters that provide
cross-file reference resolution for fs2's code graph.

Architecture:
- This file: ABC definition only
- Implementations: lsp_adapter_fake.py (test double), lsp_adapter_solidlsp.py (Phase 3)

Per Discovery 05: Uses naming convention {name}_adapter.py for ABC.
Per Discovery 06: Constructor receives ConfigurationService, not extracted config.
Per Invariants: Returns only CodeEdge domain types, never SolidLSP types.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from fs2.core.models.code_edge import CodeEdge

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


class LspAdapter(ABC):
    """LSP adapter ABC defining language-agnostic interface for cross-file resolution.

    This interface abstracts Language Server Protocol operations for extracting
    cross-file relationships (references, definitions) from source code.

    Per AC04: Returns CodeEdge instances only, never LSP-specific types.
    Per Invariants:
    - All edges have confidence=1.0 (LSP provides definitive answers)
    - All edges have resolution_rule with "lsp:" prefix (e.g., "lsp:references")
    - initialize() and shutdown() are idempotent

    Implementations:
    - FakeLspAdapter: Test double with configurable responses
    - SolidLspAdapter: Real implementation wrapping vendored SolidLSP (Phase 3)

    Usage:
        ```python
        # In composition root
        config = FS2ConfigurationService()
        adapter = SolidLspAdapter(config)  # Or FakeLspAdapter for tests

        # In service layer
        adapter.initialize("python", Path("/project"))
        if adapter.is_ready():
            edges = adapter.get_references("app.py", line=10, column=5)
        adapter.shutdown()
        ```

    Error Handling:
        All methods may raise LspAdapterError subclasses:
        - LspServerNotFoundError: Server binary not found
        - LspServerCrashError: Server process crashed
        - LspTimeoutError: Operation timed out
        - LspInitializationError: Server initialization failed

    Raises:
        LspAdapterError: Base class for all LSP adapter errors.
    """

    @abstractmethod
    def __init__(self, config: "ConfigurationService") -> None:
        """Initialize adapter with ConfigurationService registry.

        Per Discovery 06: Constructor receives ConfigurationService (registry),
        NOT extracted config. Adapter calls config.require(LspConfig) internally.

        Args:
            config: ConfigurationService registry containing LspConfig.

        Raises:
            MissingConfigurationError: If LspConfig not registered in config.
        """
        ...

    @abstractmethod
    def initialize(self, language: str, project_root: Path) -> None:
        """Initialize LSP server for the specified language and project.

        Must be called before get_references() or get_definition().
        Idempotent: Safe to call multiple times.

        Per DYK-4: Language and project_root are initialize() params,
        not adapter config (different projects may use different roots).

        Args:
            language: Programming language identifier (e.g., "python", "typescript", "go").
            project_root: Absolute path to project root directory.

        Raises:
            LspServerNotFoundError: If server binary not found.
            LspInitializationError: If server fails to initialize.
        """
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown LSP server and release resources.

        Idempotent: Safe to call even if not initialized or already shut down.
        After shutdown, is_ready() returns False.
        """
        ...

    @abstractmethod
    def get_references(
        self, file_path: str, line: int, column: int
    ) -> list[CodeEdge]:
        """Find all references to the symbol at the given location.

        Args:
            file_path: Path to file (relative to project_root).
            line: 0-indexed line number.
            column: 0-indexed column number.

        Returns:
            List of CodeEdge instances representing references.
            Each edge has:
            - confidence=1.0
            - resolution_rule="lsp:references"
            - edge_type=EdgeType.REFERENCES

        Raises:
            LspTimeoutError: If request times out.
            LspServerCrashError: If server crashes during request.
            RuntimeError: If not initialized (call initialize() first).
        """
        ...

    @abstractmethod
    def get_definition(
        self, file_path: str, line: int, column: int
    ) -> list[CodeEdge]:
        """Find the definition of the symbol at the given location.

        Args:
            file_path: Path to file (relative to project_root).
            line: 0-indexed line number.
            column: 0-indexed column number.

        Returns:
            List of CodeEdge instances representing definitions.
            Typically returns 1 edge, but may return multiple for overloads.
            Each edge has:
            - confidence=1.0
            - resolution_rule="lsp:definition"
            - edge_type=EdgeType.CALLS (definition implies call relationship)

        Raises:
            LspTimeoutError: If request times out.
            LspServerCrashError: If server crashes during request.
            RuntimeError: If not initialized (call initialize() first).
        """
        ...

    @abstractmethod
    def is_ready(self) -> bool:
        """Check if adapter is initialized and ready for queries.

        Returns:
            True if initialize() succeeded and shutdown() not called.
            False otherwise.
        """
        ...
