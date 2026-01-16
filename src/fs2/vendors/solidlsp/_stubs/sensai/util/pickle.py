"""
Stub for sensai.util.pickle.

Provides pickle utilities for caching.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


def dump_pickle(obj: Any, path: str | Path) -> None:
    """
    Dump an object to a pickle file.

    Args:
        obj: Object to pickle
        path: Path to write the pickle file to
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(obj, f)


def load_pickle(path: str | Path) -> Any:
    """
    Load an object from a pickle file.

    Args:
        path: Path to the pickle file

    Returns:
        The unpickled object, or None if the file doesn't exist
    """
    path = Path(path)
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def getstate(
    cls: type[T],
    instance: T,
    transient_properties: list[str] | None = None,
) -> dict[str, Any]:
    """
    Get the state dict for pickling, excluding transient properties.

    Args:
        cls: The class type
        instance: The instance to get state from
        transient_properties: List of property names to exclude from state

    Returns:
        Dict of the object's state for pickling
    """
    transient_properties = transient_properties or []
    state = instance.__dict__.copy()
    for prop in transient_properties:
        state.pop(prop, None)
    return state
