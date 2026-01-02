"""Documentation domain models.

Provides:
- DocMetadata: Frozen dataclass for document metadata (catalog entries)
- Doc: Frozen dataclass composing metadata + full content

Design Principles:
- Immutable: All models are frozen dataclasses
- Wheel-safe: path is str, not Path (per Critical Finding 02)
- Tuple for tags: Full immutability (per DYK-2)

Per Phase 1: Domain Models and Registry
Per Critical Finding 02: path is relative string for importlib.resources
Per DYK-1: Factory method for DocumentEntry→DocMetadata conversion
Per DYK-2: tags is tuple for immutability
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fs2.config.docs_registry import DocumentEntry


@dataclass(frozen=True)
class DocMetadata:
    """Document metadata for catalog listings.

    Used by docs_list to return document summaries without loading content.
    All fields are required; tags must be a tuple for immutability.

    Attributes:
        id: Unique document identifier (lowercase, numbers, hyphens only).
        title: Human-readable document title.
        summary: 1-2 sentence description of what the doc covers and when to use it.
        category: Document category (e.g., "how-to", "reference").
        tags: Tuple of tag strings for filtering (immutable).
        path: Relative path to markdown file within fs2.docs package.
    """

    id: str
    title: str
    summary: str
    category: str
    tags: tuple[str, ...]
    path: str

    @classmethod
    def from_registry_entry(cls, entry: DocumentEntry) -> DocMetadata:
        """Create DocMetadata from a registry DocumentEntry.

        Converts the Pydantic model to a frozen dataclass, including
        converting the tags list to a tuple for immutability.

        Args:
            entry: DocumentEntry from the registry YAML.

        Returns:
            Frozen DocMetadata instance.
        """
        return cls(
            id=entry.id,
            title=entry.title,
            summary=entry.summary,
            category=entry.category,
            tags=tuple(entry.tags),
            path=entry.path,
        )


@dataclass(frozen=True)
class Doc:
    """Complete document with metadata and content.

    Used by docs_get to return full document content for agent reading.
    Composes DocMetadata with the full markdown content string.

    Attributes:
        metadata: Document metadata (id, title, summary, category, tags, path).
        content: Full markdown content of the document.
    """

    metadata: DocMetadata
    content: str
