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
        super().__init__(
            message or f"Graph not found at {path}. Run 'fs2 scan' first."
        )


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
