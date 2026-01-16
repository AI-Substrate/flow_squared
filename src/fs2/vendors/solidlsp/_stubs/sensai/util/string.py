"""
Stub for sensai.util.string.

Provides ToStringMixin class for debug string representations.
"""

from __future__ import annotations


class ToStringMixin:
    """
    Mixin that provides __str__ and __repr__ implementations.

    This stub provides a simplified version that just uses the class name
    and id for representation.
    """

    def __str__(self) -> str:
        """Return a string representation of the object."""
        return f"{self.__class__.__name__}[{self._tostring_properties()}]"

    def __repr__(self) -> str:
        """Return a detailed string representation of the object."""
        props = self._tostring_properties()
        return f"{self.__class__.__name__}[id={id(self)}, {props}]"

    def _tostring_properties(self) -> str:
        """Get property string for representation."""
        # Simplified: just return empty string
        # Full implementation would iterate over properties
        return ""
