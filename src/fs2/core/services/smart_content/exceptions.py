"""Smart content service-layer exception hierarchy.

Important:
- These exceptions are service-layer concerns.
- Adapter exceptions (e.g., TokenCounterError) remain in the adapter layer and
  may be caught/wrapped by services, but MUST NOT be duplicated or re-exported.
"""

from __future__ import annotations


class SmartContentError(Exception):
    """Base error for smart content service operations."""


class TemplateError(SmartContentError):
    """Template loading or rendering failed."""


class SmartContentProcessingError(SmartContentError):
    """Processing a node (or batch) for smart content failed."""
