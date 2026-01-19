"""SolidLspAdapter - Real LSP adapter wrapping vendored SolidLSP.

This is the production implementation of LspAdapter that wraps
the vendored SolidLSP library for cross-file reference resolution.

Architecture:
- Inherits from LspAdapter ABC
- Receives ConfigurationService (registry) via constructor
- Wraps fs2.vendors.solidlsp.SolidLanguageServer
- Translates LSP Location responses to CodeEdge domain objects
- Translates SolidLSP exceptions to LspAdapterError hierarchy

Per Discovery 05: Named lsp_adapter_solidlsp.py following convention.
Per Discovery 06: Constructor receives ConfigurationService, NOT extracted config.
Per DYK-1: Pre-check server exists before SolidLSP call (fail-fast).
Per DYK-2: Delegate process cleanup to vendored SolidLSP (has full psutil impl).
Per DYK-3: Definition lookups use EdgeType.CALLS with resolution_rule="lsp:definition".
Per DYK-4: Trust SolidLSP internal cross-file wait (no adapter-level delay).
Per DYK-5: Construct node_ids matching tree-sitter format for graph correlation.
"""

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fs2.config.objects import LspConfig
from fs2.core.adapters.exceptions import (
    LspAdapterError,
    LspInitializationError,
    LspServerCrashError,
    LspServerNotFoundError,
    LspTimeoutError,
)
from fs2.core.adapters.lsp_adapter import LspAdapter
from fs2.core.models.code_edge import CodeEdge
from fs2.core.models.edge_type import EdgeType

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService
    from fs2.vendors.solidlsp.ls import SolidLanguageServer
    from fs2.vendors.solidlsp.ls_types import Location

log = logging.getLogger(__name__)

# Server binary names and install commands per language
# Per Discovery 04: Actionable error messages with platform-specific install
_SERVER_CONFIG: dict[str, dict[str, Any]] = {
    "python": {
        "binary": "pyright-langserver",
        "install": {
            "default": "pip install pyright",
            "Darwin": "pip install pyright",
            "Linux": "pip install pyright",
            "Windows": "pip install pyright",
        },
    },
    "typescript": {
        "binary": "typescript-language-server",
        "install": {
            "default": "npm install -g typescript-language-server typescript",
        },
    },
    "go": {
        "binary": "gopls",
        "install": {
            "default": "go install golang.org/x/tools/gopls@latest",
        },
    },
    "csharp": {
        "binary": "OmniSharp",
        "install": {
            "default": "dotnet tool install --global omnisharp",
            "Darwin": "brew install omnisharp/omnisharp-roslyn/omnisharp",
        },
    },
}


class SolidLspAdapter(LspAdapter):
    """Production LSP adapter wrapping vendored SolidLSP.

    This implementation demonstrates the full adapter pattern:
    - Constructor receives ConfigurationService (registry), not specific config
    - Adapter calls config.require(LspConfig) internally (no concept leakage)
    - Domain-only return types (list[CodeEdge])
    - Domain-only exceptions (LspAdapterError hierarchy)
    - Translates SolidLSP Location → CodeEdge at adapter boundary

    Usage:
        ```python
        from fs2.config.objects import LspConfig
        from fs2.config.service import FS2ConfigurationService
        from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

        # Setup
        config = FS2ConfigurationService()
        config.register(LspConfig(timeout_seconds=30.0))
        adapter = SolidLspAdapter(config)

        # Initialize and use
        adapter.initialize("python", Path("/project"))
        refs = adapter.get_references("app.py", line=10, column=5)

        # Cleanup
        adapter.shutdown()
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
        self._server: SolidLanguageServer | None = None
        self._is_ready: bool = False
        self._language: str | None = None
        self._project_root: Path | None = None

    def initialize(self, language: str, project_root: Path) -> None:
        """Initialize LSP server for the specified language and project.

        Per DYK-1: Pre-checks server binary exists before calling SolidLSP.
        If binary not found, raises LspServerNotFoundError immediately.

        Args:
            language: Programming language identifier (e.g., "python", "typescript", "go").
            project_root: Absolute path to project root directory.

        Raises:
            LspServerNotFoundError: If server binary not found in PATH.
            LspInitializationError: If server fails to initialize.
        """
        if self._is_ready:
            # Idempotent: already initialized
            log.debug(f"SolidLspAdapter already initialized for {self._language}")
            return

        log.info(f"Initializing SolidLspAdapter for {language} at {project_root}")

        # DYK-1: Pre-check server binary exists (fail-fast)
        server_config = _SERVER_CONFIG.get(language, {})
        binary_name = server_config.get("binary")

        if binary_name and not shutil.which(binary_name):
            install_commands = server_config.get("install", {"default": f"Install {binary_name}"})
            raise LspServerNotFoundError(binary_name, install_commands)

        try:
            # Import vendored SolidLSP
            from fs2.vendors.solidlsp.ls import SolidLanguageServer
            from fs2.vendors.solidlsp.ls_config import Language, LanguageServerConfig

            # Map language string to Language enum
            try:
                lang_enum = Language(language)
            except ValueError as e:
                raise LspInitializationError(
                    f"Unsupported language: '{language}'. "
                    f"Supported languages: {[lang.value for lang in Language]}",
                    root_cause=e,
                ) from e

            # Create LanguageServerConfig (per Phase 1 lesson: use code_language=)
            ls_config = LanguageServerConfig(code_language=lang_enum)

            # Create and start server
            self._server = SolidLanguageServer.create(
                config=ls_config,
                repository_root_path=str(project_root),
                timeout=self._lsp_config.timeout_seconds,
            )
            self._server.start()

            self._language = language
            self._project_root = project_root
            self._is_ready = True

            log.info(f"SolidLspAdapter initialized successfully for {language}")

        except LspServerNotFoundError:
            # Re-raise our domain exceptions
            raise
        except LspInitializationError:
            raise
        except Exception as e:
            # Translate all other errors to LspInitializationError
            log.exception(f"Failed to initialize LSP server for {language}")
            raise LspInitializationError(
                f"Failed to initialize {language} language server: {e}",
                root_cause=e,
            ) from e

    def shutdown(self) -> None:
        """Shutdown LSP server and release resources.

        Per DYK-2: Delegates to SolidLSP's built-in shutdown which has
        full psutil process tree cleanup implementation.

        Idempotent: Safe to call even if not initialized or already shut down.
        After shutdown, is_ready() returns False.
        """
        if self._server is not None:
            try:
                log.info(f"Shutting down SolidLspAdapter for {self._language}")
                # DYK-2: Delegate to SolidLSP - it has full psutil cleanup
                self._server.stop()
            except Exception as e:
                # Per SolidLSP contract: stop() shouldn't raise, but be defensive
                log.warning(f"Exception during LSP shutdown: {e}")
            finally:
                self._server = None

        self._is_ready = False
        self._language = None
        self._project_root = None

    def get_references(
        self, file_path: str, line: int, column: int
    ) -> list[CodeEdge]:
        """Find all references to the symbol at the given location.

        Per DYK-4: No adapter-level wait needed - SolidLSP handles indexing delay.
        Per DYK-5: Translates LSP Location to CodeEdge with tree-sitter node_id format.

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
        self._check_ready()

        try:
            assert self._server is not None
            assert self._project_root is not None

            # DYK-4: SolidLSP handles cross-file wait internally
            locations = self._server.request_references(file_path, line, column)

            return self._translate_references(
                locations=locations,
                source_file=file_path,
                source_line=line,
                project_root=str(self._project_root),
            )

        except RuntimeError:
            raise
        except TimeoutError as e:
            raise LspTimeoutError(
                f"References request timed out for {file_path}:{line}:{column}",
                operation="get_references",
                timeout_seconds=self._lsp_config.timeout_seconds,
            ) from e
        except Exception as e:
            # Check if server crashed
            if self._server is not None and not self._server.server_started:
                raise LspServerCrashError(
                    self._language or "unknown",
                    exit_code=None,
                ) from e
            # Re-raise as generic adapter error
            raise LspAdapterError(f"References request failed: {e}") from e

    def get_definition(
        self, file_path: str, line: int, column: int
    ) -> list[CodeEdge]:
        """Find the definition of the symbol at the given location.

        Per DYK-3: Uses EdgeType.CALLS (semantically correct for call-site → definition).
        Per DYK-5: Translates LSP Location to CodeEdge with tree-sitter node_id format.

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
        self._check_ready()

        try:
            assert self._server is not None
            assert self._project_root is not None

            locations = self._server.request_definition(file_path, line, column)

            return self._translate_definitions(
                locations=locations,
                source_file=file_path,
                source_line=line,
                project_root=str(self._project_root),
            )

        except RuntimeError:
            raise
        except TimeoutError as e:
            raise LspTimeoutError(
                f"Definition request timed out for {file_path}:{line}:{column}",
                operation="get_definition",
                timeout_seconds=self._lsp_config.timeout_seconds,
            ) from e
        except Exception as e:
            if self._server is not None and not self._server.server_started:
                raise LspServerCrashError(
                    self._language or "unknown",
                    exit_code=None,
                ) from e
            raise LspAdapterError(f"Definition request failed: {e}") from e

    def is_ready(self) -> bool:
        """Check if adapter is initialized and ready for queries.

        Returns:
            True if initialize() succeeded and shutdown() not called.
            False otherwise.
        """
        return self._is_ready

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _check_ready(self) -> None:
        """Raise RuntimeError if adapter not initialized."""
        if not self._is_ready:
            raise RuntimeError(
                "SolidLspAdapter not initialized. Call initialize() first."
            )

    # =========================================================================
    # Translation Methods (Static for testability)
    # Per DYK-5: Construct node_ids matching tree-sitter format
    # =========================================================================

    @staticmethod
    def _translate_references(
        locations: list["Location"],
        source_file: str,
        source_line: int,
        project_root: str,
    ) -> list[CodeEdge]:
        """Translate LSP Location list to CodeEdge list for references.

        Args:
            locations: List of LSP Location dicts from SolidLSP.
            source_file: File where the symbol being queried is defined.
            source_line: Line where the symbol is defined.
            project_root: Absolute path to project root.

        Returns:
            List of CodeEdge with EdgeType.REFERENCES.
        """
        if not locations:
            return []

        edges = []
        for loc in locations:
            edge = SolidLspAdapter._translate_reference(
                location=loc,
                source_file=source_file,
                source_line=source_line,
                project_root=project_root,
            )
            edges.append(edge)

        return edges

    @staticmethod
    def _translate_definitions(
        locations: list["Location"],
        source_file: str,
        source_line: int,
        project_root: str,
    ) -> list[CodeEdge]:
        """Translate LSP Location list to CodeEdge list for definitions.

        Args:
            locations: List of LSP Location dicts from SolidLSP.
            source_file: File where the call/reference is located.
            source_line: Line where the call/reference is.
            project_root: Absolute path to project root.

        Returns:
            List of CodeEdge with EdgeType.CALLS.
        """
        if not locations:
            return []

        edges = []
        for loc in locations:
            edge = SolidLspAdapter._translate_definition(
                location=loc,
                source_file=source_file,
                source_line=source_line,
                project_root=project_root,
            )
            edges.append(edge)

        return edges

    @staticmethod
    def _translate_reference(
        location: "Location",
        source_file: str,
        source_line: int,
        project_root: str,
    ) -> CodeEdge:
        """Translate single LSP Location to CodeEdge for reference.

        Per AC08: EdgeType.REFERENCES, confidence=1.0, resolution_rule="lsp:references"

        For references, the semantic is:
        - Source: The file containing the reference (caller)
        - Target: The file being referenced (where symbol is defined - source_file)

        Args:
            location: LSP Location dict with uri, range, absolutePath, relativePath.
            source_file: File where the referenced symbol is defined.
            source_line: Line of the symbol definition (for debugging).
            project_root: Absolute path to project root.

        Returns:
            CodeEdge representing the reference relationship.
        """
        # The location points to WHERE the reference is (the caller)
        ref_file = location.get("relativePath") or SolidLspAdapter._uri_to_relative(
            location["uri"], project_root
        )
        ref_line = location["range"]["start"]["line"]

        # Source is the referencing file, target is the referenced symbol's file
        source_node_id = SolidLspAdapter._source_to_node_id(
            source_file=ref_file,
            source_line=ref_line,
            project_root=project_root,
        )
        target_node_id = SolidLspAdapter._source_to_node_id(
            source_file=source_file,
            source_line=source_line,
            project_root=project_root,
        )

        return CodeEdge(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=EdgeType.REFERENCES,
            confidence=1.0,
            source_line=ref_line,
            resolution_rule="lsp:references",
        )

    @staticmethod
    def _translate_definition(
        location: "Location",
        source_file: str,
        source_line: int,
        project_root: str,
    ) -> CodeEdge:
        """Translate single LSP Location to CodeEdge for definition.

        Per AC09: EdgeType.CALLS, confidence=1.0, resolution_rule="lsp:definition"
        Per DYK-3: CALLS is semantically correct for call-site → definition.

        For definitions, the semantic is:
        - Source: The file making the call (source_file)
        - Target: The file where the symbol is defined (from location)

        Args:
            location: LSP Location dict pointing to the definition.
            source_file: File where the call/reference originates.
            source_line: Line where the call is made.
            project_root: Absolute path to project root.

        Returns:
            CodeEdge representing the call relationship.
        """
        # The location points to WHERE the definition is (unused but kept for clarity)
        _ = location.get("relativePath") or SolidLspAdapter._uri_to_relative(
            location["uri"], project_root
        )

        # Source is the calling file, target is the definition
        source_node_id = SolidLspAdapter._source_to_node_id(
            source_file=source_file,
            source_line=source_line,
            project_root=project_root,
        )
        target_node_id = SolidLspAdapter._location_to_node_id(
            location=location, project_root=project_root
        )

        return CodeEdge(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=EdgeType.CALLS,
            confidence=1.0,
            source_line=source_line,
            resolution_rule="lsp:definition",
        )

    @staticmethod
    def _location_to_node_id(location: "Location", project_root: str) -> str:
        """Convert LSP Location to tree-sitter compatible node_id.

        Per DYK-5: Format is {category}:{rel_path}
        Currently uses file-level granularity; symbol-level would require
        additional documentSymbol calls.

        Args:
            location: LSP Location dict.
            project_root: Absolute path to project root.

        Returns:
            Node ID in format "file:{relative_path}".
        """
        rel_path = location.get("relativePath")
        if not rel_path:
            rel_path = SolidLspAdapter._uri_to_relative(location["uri"], project_root)

        return f"file:{rel_path}"

    @staticmethod
    def _source_to_node_id(
        source_file: str, source_line: int, project_root: str
    ) -> str:
        """Create node_id for source file location.

        Args:
            source_file: Relative file path.
            source_line: Line number (for future symbol-level resolution).
            project_root: Absolute path to project root.

        Returns:
            Node ID in format "file:{relative_path}".
        """
        # Ensure path is relative (remove leading / if present)
        rel_path = source_file
        if rel_path.startswith("/"):
            rel_path = rel_path.lstrip("/")

        return f"file:{rel_path}"

    @staticmethod
    def _uri_to_relative(uri: str, project_root: str) -> str:
        """Convert file URI to relative path.

        Args:
            uri: File URI (e.g., "file:///project/lib.py").
            project_root: Absolute path to project root.

        Returns:
            Relative path (e.g., "lib.py").
        """
        # Handle file:// URIs
        if uri.startswith("file://"):
            abs_path = uri[7:]  # Remove "file://"
            # Handle Windows paths (file:///C:/...)
            if len(abs_path) > 2 and abs_path[2] == ":":
                abs_path = abs_path[1:]  # Remove leading /
        else:
            abs_path = uri

        # Make relative to project root
        try:
            return str(Path(abs_path).relative_to(project_root))
        except ValueError:
            # Path is not relative to project root, return as-is
            return abs_path
