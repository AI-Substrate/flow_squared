"""
SolidLSP - Language Server Protocol wrapper.

Vendored from the Serena project (https://github.com/oraios/serena).
This package provides a unified interface for interacting with various
Language Server Protocol (LSP) servers for cross-file code analysis.

Original authors: Oraios AI
License: MIT (see THIRD_PARTY_LICENSES in project root)

Key components:
- SolidLanguageServer: Main entry point for LSP operations
- LanguageServerConfig: Configuration for specific language servers
- Language: Enum of supported programming languages
"""

from fs2.vendors.solidlsp.ls import SolidLanguageServer
from fs2.vendors.solidlsp.ls_config import Language, LanguageServerConfig

__all__ = ["SolidLanguageServer", "Language", "LanguageServerConfig"]
