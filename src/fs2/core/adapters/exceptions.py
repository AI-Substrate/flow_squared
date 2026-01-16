"""Adapter exception hierarchy.

Provides domain exceptions for adapter boundary errors.
Per Finding 07: Exception translation at adapter boundary.

Error Type Guidelines:
| Error Type            | Use For                                          |
|-----------------------|--------------------------------------------------|
| AdapterError          | Base for all adapter errors                      |
| AuthenticationError   | Auth failures (invalid token, expired creds)     |
| AdapterConnectionError| Network/connection issues (timeout, unreachable) |
| GraphNotFoundError    | Graph file not found (user needs to run scan)    |

Pattern for exception translation in adapter implementations:
```python
def _call_sdk(self):
    try:
        return sdk.call()
    except SDKAuthError as e:
        raise AuthenticationError(f"Auth failed: {e}") from e
    except SDKConnectionError as e:
        raise AdapterConnectionError(f"Connection failed: {e}") from e
```
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class AdapterError(Exception):
    """Base adapter error.

    All adapter errors inherit from this class to enable
    catch-all patterns at the service layer.
    """


class TokenCounterError(AdapterError):
    """Token counting failed.

    Raised when the TokenCounter adapter cannot count tokens due to
    tokenizer initialization failures, encoding errors, or other
    underlying library issues.

    Recovery:
    - Verify `tiktoken` is installed (required dependency)
    - Verify LLM model name is configured if model-specific encoding is used
    - Retry with simpler input if content is malformed
    """


class AuthenticationError(AdapterError):
    """Authentication failed.

    Raised when adapter authentication fails due to invalid credentials,
    expired tokens, or permission issues.
    """


class AdapterConnectionError(AdapterError):
    """Connection failed.

    Raised when adapter cannot connect to external service due to
    network issues, timeouts, or service unavailability.

    Note: Named AdapterConnectionError to avoid shadowing built-in ConnectionError.
    """


class FileScannerError(AdapterError):
    """File scanning operation failed.

    Raised when the FileScanner adapter encounters an error during
    directory traversal or file access.

    Common causes:
    - Permission denied on file or directory
    - Path does not exist
    - I/O error during scan
    - Invalid gitignore pattern

    Recovery:
    - Check file/directory permissions
    - Verify scan_paths configuration
    - Check for malformed .gitignore files
    """


class ASTParserError(AdapterError):
    """AST parsing operation failed.

    Raised when the ASTParser adapter encounters an error during
    tree-sitter parsing or language detection.

    Common causes:
    - Unknown or unsupported language
    - Binary file detected (null bytes)
    - Encoding error (non-UTF8 file)
    - Tree-sitter grammar issue

    Recovery:
    - Add language mapping for unknown extensions
    - Exclude binary files from scan
    - Convert files to UTF-8 encoding
    """


class GraphStoreError(AdapterError):
    """Graph storage operation failed.

    Raised when the GraphStore repository encounters an error during
    graph persistence or retrieval.

    Common causes:
    - Disk full during save
    - Corrupted pickle file
    - Permission denied on graph file
    - Incompatible format version

    Recovery:
    - Check disk space
    - Delete corrupted graph file
    - Check file permissions
    - Regenerate graph from scan
    """


class GraphNotFoundError(AdapterError):
    """Graph file does not exist.

    Raised when a service attempts to load a graph that hasn't been created yet.

    Common causes:
    - User hasn't run `fs2 scan` yet
    - Graph path is misconfigured
    - Graph file was deleted

    Recovery:
    - Run `fs2 scan` to create the graph
    - Check graph_path in configuration
    """

    def __init__(self, path: Path, message: str | None = None):
        """Initialize with path to missing graph.

        Args:
            path: Path where graph was expected.
            message: Optional custom message.
        """
        self.path: Path = path if isinstance(path, Path) else Path(path)
        super().__init__(message or f"Graph not found at {path}. Run 'fs2 scan' first.")


# LLM Adapter Exception Hierarchy
# Per Finding 04: Exception translation at adapter boundary
# Per AC7: Status-code-based exception translation (no SDK exception imports)


class LLMAdapterError(AdapterError):
    """Base error for LLM adapter operations.

    All LLM-specific errors inherit from this class to enable
    catch-all patterns for LLM operations at the service layer.

    Note: This error is raised for generic LLM failures that don't
    fit into more specific categories.
    """


class LLMAuthenticationError(LLMAdapterError):
    """LLM authentication failed.

    Raised when the LLM provider rejects the API key or credentials.
    Corresponds to HTTP 401 status code.

    Common causes:
    - Invalid API key
    - Expired credentials
    - Key not authorized for deployment

    Recovery:
    - Check API key is correct
    - Verify ${ENV_VAR} placeholder expanded correctly
    - Ensure key has access to the deployment
    """


class LLMRateLimitError(LLMAdapterError):
    """LLM rate limit exceeded.

    Raised when the LLM provider returns a rate limit error.
    Corresponds to HTTP 429 status code.

    Note: The adapter should have already retried with exponential
    backoff before raising this error.

    Common causes:
    - Too many requests in time window
    - Token quota exceeded
    - Concurrent request limit hit

    Recovery:
    - Wait and retry (automatic via adapter)
    - Reduce request frequency
    - Increase quota with provider
    """


class LLMContentFilterError(LLMAdapterError):
    """LLM content was filtered by provider safety systems.

    Raised when Azure OpenAI or other providers reject content
    due to safety/content filtering policies.
    Corresponds to HTTP 400 with "content_filter" in error.

    Note: The adapter may choose to return a graceful response
    (was_filtered=True) instead of raising this error.

    Common causes:
    - Prompt triggered content policy
    - Response would violate safety guidelines

    Recovery:
    - Rephrase the prompt
    - Review content policy guidelines
    """


# Embedding Adapter Exception Hierarchy
# Per Plan 1.3: Exception hierarchy follows existing pattern
# Per DYK-4: EmbeddingRateLimitError includes retry metadata


class EmbeddingAdapterError(AdapterError):
    """Base error for embedding adapter operations.

    All embedding-specific errors inherit from this class to enable
    catch-all patterns for embedding operations at the service layer.

    Note: This error is raised for generic embedding failures that don't
    fit into more specific categories.
    """


class EmbeddingAuthenticationError(EmbeddingAdapterError):
    """Embedding service authentication failed.

    Raised when the embedding provider rejects the API key or credentials.
    Corresponds to HTTP 401 status code.

    Common causes:
    - Invalid API key
    - Expired credentials
    - Key not authorized for embedding endpoint

    Recovery:
    - Check API key is correct
    - Verify ${ENV_VAR} placeholder expanded correctly
    - Ensure key has access to the embedding deployment
    """


class EmbeddingRateLimitError(EmbeddingAdapterError):
    """Embedding service rate limit exceeded.

    Raised when the embedding provider returns a rate limit error.
    Corresponds to HTTP 429 status code.

    Per DYK-4: Includes retry metadata for intelligent backoff:
    - retry_after: Seconds to wait (from Retry-After header, or None)
    - attempts_made: Number of attempts before this error was raised

    Note: The adapter should have already retried with exponential
    backoff before raising this error.

    Common causes:
    - Too many requests in time window
    - Token quota exceeded
    - Concurrent request limit hit

    Recovery:
    - Wait and retry (automatic via adapter)
    - Reduce request frequency
    - Increase quota with provider

    Attributes:
        retry_after: Seconds to wait before retry, or None if unknown.
        attempts_made: Number of attempts made before giving up.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        attempts_made: int = 0,
    ):
        """Initialize with message and retry metadata.

        Args:
            message: Error description.
            retry_after: Seconds to wait (from Retry-After header), or None.
            attempts_made: Number of retry attempts made.
        """
        super().__init__(message)
        self.retry_after = retry_after
        self.attempts_made = attempts_made


# Documentation Exception Hierarchy
# Per Critical Finding 06: Error translation with actionable messages
# Per MCP Documentation Plan Phase 2


class DocsNotFoundError(AdapterError):
    """Documentation resource not found.

    Raised when DocsService cannot locate a required documentation resource:
    - Registry file (registry.yaml) missing from package
    - Document file referenced in registry does not exist

    Per Critical Finding 06: Includes actionable recovery message.

    Common causes:
    - Package not properly installed (missing docs/)
    - Registry references a document that doesn't exist
    - docs_package parameter points to non-existent package

    Recovery:
    - Use docs_list() to see available documents
    - Verify the fs2.docs package is installed correctly
    - Check registry.yaml for typos in document paths

    Attributes:
        resource: Name or path of the missing resource.
    """

    def __init__(self, resource: str, message: str | None = None):
        """Initialize with resource identifier and optional message.

        Args:
            resource: Name or path of missing resource (e.g., "registry.yaml").
            message: Optional custom message. Defaults to actionable message.
        """
        self.resource = resource
        default_message = (
            f"Documentation resource not found: {resource}. "
            "Use docs_list() to see available documents."
        )
        super().__init__(message or default_message)


# LSP Adapter Exception Hierarchy
# Per Discovery 04: Actionable error messages with platform-specific install commands
# Per Discovery 12: Exception hierarchy at adapter boundary


class LspAdapterError(AdapterError):
    """Base error for LSP adapter operations.

    All LSP-specific errors inherit from this class to enable
    catch-all patterns for LSP operations at the service layer.

    Note: This error is raised for generic LSP failures that don't
    fit into more specific categories.
    """


class LspServerNotFoundError(LspAdapterError):
    """LSP server binary not found.

    Raised when the adapter cannot locate the LSP server binary
    required for the specified language.

    Per Discovery 04: Includes platform-specific install commands.

    Common causes:
    - Server not installed
    - Server not in PATH
    - Wrong server name configured

    Recovery:
    - Install the appropriate server for your platform
    - Ensure server binary is in PATH
    - Check configuration for correct server name

    Attributes:
        server_name: Name of the missing server binary.
        install_commands: Dict of platform -> install command.
    """

    def __init__(self, server_name: str, install_commands: dict[str, str]):
        """Initialize with server name and platform-specific install commands.

        Args:
            server_name: Name of the missing server (e.g., "pyright").
            install_commands: Mapping of platform.system() values to install commands.
                             Include "default" key as fallback.
        """
        import platform

        self.server_name = server_name
        self.install_commands = install_commands

        system = platform.system()
        cmd = install_commands.get(system, install_commands.get("default", ""))

        message = f"LSP server '{server_name}' not found. Install with:\n  {cmd}"
        super().__init__(message)


class LspServerCrashError(LspAdapterError):
    """LSP server process crashed unexpectedly.

    Raised when the language server process terminates abnormally
    during operation (not during initialization).

    Common causes:
    - Server bug triggered by input
    - Out of memory
    - Unhandled exception in server

    Recovery:
    - Check server logs for error details
    - Try restarting the adapter
    - Report issue to server maintainers if reproducible

    Attributes:
        server_name: Name of the crashed server.
        exit_code: Exit code of the crashed process, if known.
    """

    def __init__(self, server_name: str, exit_code: int | None = None):
        """Initialize with server name and optional exit code.

        Args:
            server_name: Name of the crashed server.
            exit_code: Exit code of the crashed process, or None if unknown.
        """
        self.server_name = server_name
        self.exit_code = exit_code

        if exit_code is not None:
            message = (
                f"LSP server '{server_name}' crashed with exit code {exit_code}. "
                "Check server logs and try restarting."
            )
        else:
            message = (
                f"LSP server '{server_name}' crashed unexpectedly. "
                "Check server logs and try restarting."
            )
        super().__init__(message)


class LspTimeoutError(LspAdapterError):
    """LSP operation timed out.

    Raised when an LSP request doesn't complete within the configured
    timeout period.

    Common causes:
    - Large codebase with many files
    - Server still indexing
    - Server hung on complex operation

    Recovery:
    - Wait for server indexing to complete
    - Increase timeout in configuration
    - Check if server is responsive

    Attributes:
        operation: Name of the operation that timed out.
        timeout_seconds: Configured timeout value in seconds.
    """

    def __init__(self, message: str, operation: str | None = None, timeout_seconds: float | None = None):
        """Initialize with message and optional operation details.

        Args:
            message: Error description.
            operation: Name of the operation that timed out (e.g., "get_references").
            timeout_seconds: Configured timeout value.
        """
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        super().__init__(message)


class LspInitializationError(LspAdapterError):
    """LSP server initialization failed.

    Raised when the language server fails to initialize properly.
    This typically occurs during the LSP initialize/initialized handshake.

    Common causes:
    - Invalid project root path
    - Server doesn't support the language/file type
    - Missing project configuration files
    - Server binary exists but is incompatible

    Recovery:
    - Check project root path is valid
    - Verify language is supported by the server
    - Check for required project configuration files
    - Update server to compatible version

    Attributes:
        root_cause: Underlying error that caused initialization failure.
    """

    def __init__(self, message: str, root_cause: Exception | None = None):
        """Initialize with message and optional root cause.

        Args:
            message: Error description.
            root_cause: Underlying exception that caused the failure.
        """
        self.root_cause = root_cause
        super().__init__(message)
