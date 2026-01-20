"""Relationship extraction services for detecting cross-file references.

This package contains detectors for finding relationships between code elements:
- NodeIdDetector: Detects explicit fs2 node_id patterns (confidence 1.0)
- RawFilenameDetector: Detects raw filename mentions (confidence 0.4-0.5)
- TextReferenceExtractor: Combines both detectors for complete extraction
"""

from fs2.core.services.relationship_extraction.nodeid_detector import NodeIdDetector
from fs2.core.services.relationship_extraction.raw_filename_detector import (
    RawFilenameDetector,
)
from fs2.core.services.relationship_extraction.text_reference_extractor import (
    TextReferenceExtractor,
)

__all__ = [
    "NodeIdDetector",
    "RawFilenameDetector",
    "TextReferenceExtractor",
]
