"""Hash utilities for fs2.

Provides stable hashing primitives used for change detection.
"""

from __future__ import annotations

import hashlib


def compute_content_hash(content: str) -> str:
    """Compute a stable SHA-256 hexdigest for content.

    Args:
        content: Text content to hash.

    Returns:
        SHA-256 hexdigest of UTF-8 encoded content.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

