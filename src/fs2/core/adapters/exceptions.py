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
