"""
Language Handler Strategy for AST parsing.

Provides language-specific handling of tree-sitter AST nodes.
Each language may have different container types that should be
traversed but not extracted as code nodes.

Usage:
    from fs2.core.adapters.ast_languages import get_handler
    handler = get_handler("python")
    if ts_kind in handler.container_types:
        # Skip extraction, just recurse

Why explicit registration:
    Per Insight #5 (/didyouknow session), we use a simple explicit dict
    instead of auto-discovery or import magic. This ensures uvx
    compatibility and makes the code easy to debug.
"""

from fs2.core.adapters.ast_languages.handler import DefaultHandler, LanguageHandler
from fs2.core.adapters.ast_languages.python import PythonHandler

__all__ = ["get_handler", "LanguageHandler", "DefaultHandler", "PythonHandler"]


# =============================================================================
# Handler Registry (explicit dict, uvx-safe per Insight #5)
# =============================================================================

# Instantiate handlers once (singleton pattern for efficiency)
_default_handler = DefaultHandler()
_python_handler = PythonHandler()

# Simple dict mapping language names to handler instances
_HANDLERS: dict[str, LanguageHandler] = {
    "python": _python_handler,
}


def get_handler(language: str) -> LanguageHandler:
    """
    Get the handler for a specific language.

    Args:
        language: The language name (e.g., "python", "go").
                  Case-sensitive, should match tree-sitter language names.

    Returns:
        The registered handler for the language, or DefaultHandler
        if no specific handler is registered.

    Example:
        handler = get_handler("python")
        if ts_kind in handler.container_types:
            # Skip this node, just recurse into children
            pass
    """
    return _HANDLERS.get(language, _default_handler)
