"""DocsService for MCP documentation access.

Provides document discovery and retrieval from bundled package resources.
Used by MCP tools (docs_list, docs_get) to serve documentation to AI agents.

Design Principles:
- Wheel-safe: Uses importlib.resources Traversable API only (CF-02)
- Fail-fast: Validates all document paths at init (DYK-3)
- Package injection: Accepts docs_package parameter for testing (DYK-1)
- No caching of content: Fresh read per get_document call (DYK-2)
- No stdout: All logging via stderr (CF-01)

Per MCP Documentation Plan Phase 2.
"""

from __future__ import annotations

import importlib.resources as importlib_resources
import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

import yaml

from fs2.config.docs_registry import DocsRegistry
from fs2.core.adapters.exceptions import DocsNotFoundError
from fs2.core.models import Doc, DocMetadata

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

DEFAULT_DOCS_PACKAGE = "fs2.docs"


class DocsService:
    """Service for loading and retrieving bundled documentation.

    Provides two main operations:
    - list_documents(): Get catalog of available documents with filtering
    - get_document(): Get full document content by ID

    Attributes:
        docs_package: Package name for importlib.resources loading.
    """

    def __init__(self, docs_package: str = DEFAULT_DOCS_PACKAGE) -> None:
        """Initialize DocsService with package resource loading.

        Per DYK-1: Accepts docs_package parameter for fixture injection.
        Per DYK-2: Caches registry at init, validates all paths.
        Per DYK-3: Validates all document paths exist (fail-fast).

        Args:
            docs_package: Package name containing docs (default: fs2.docs).

        Raises:
            DocsNotFoundError: If registry or any document file is missing.
        """
        self._docs_package = docs_package
        self._registry_entries: dict[str, DocMetadata] = {}

        # Load and validate registry at init (DYK-2, DYK-3)
        self._load_registry()

    def _load_registry(self) -> None:
        """Load registry.yaml and validate all document paths exist.

        Raises:
            DocsNotFoundError: If registry or any referenced document is missing.
        """
        try:
            base = importlib_resources.files(self._docs_package)
        except ModuleNotFoundError as e:
            logger.debug("Package not found: %s", self._docs_package)
            raise DocsNotFoundError(
                self._docs_package,
                f"Documentation package not found: {self._docs_package}. "
                "Verify the package is installed correctly.",
            ) from e

        # Load registry.yaml
        registry_file = base.joinpath("registry.yaml")
        try:
            if not registry_file.is_file():
                raise DocsNotFoundError(
                    "registry.yaml",
                    f"Registry file not found in {self._docs_package}. "
                    "Use docs_list() to see available documents.",
                )
            registry_content = registry_file.read_text(encoding="utf-8")
        except FileNotFoundError as e:
            raise DocsNotFoundError(
                "registry.yaml",
                f"Registry file not found in {self._docs_package}. "
                "Use docs_list() to see available documents.",
            ) from e

        # Parse and validate registry
        try:
            registry_data = yaml.safe_load(registry_content)
            registry = DocsRegistry.model_validate(registry_data)
        except Exception as e:
            logger.debug("Registry validation failed: %s", e)
            raise DocsNotFoundError(
                "registry.yaml",
                f"Invalid registry.yaml in {self._docs_package}: {e}",
            ) from e

        # Validate all document paths exist and build lookup (DYK-3)
        missing_docs: list[str] = []
        for entry in registry.documents:
            doc_file = base.joinpath(entry.path)
            try:
                if not doc_file.is_file():
                    missing_docs.append(entry.path)
                    continue
            except FileNotFoundError:
                missing_docs.append(entry.path)
                continue

            # Convert to DocMetadata and cache
            metadata = DocMetadata.from_registry_entry(entry)
            self._registry_entries[entry.id] = metadata

        if missing_docs:
            missing_str = ", ".join(missing_docs)
            raise DocsNotFoundError(
                missing_str,
                f"Document files not found in {self._docs_package}: {missing_str}. "
                "Check registry.yaml for path typos.",
            )

        logger.debug(
            "DocsService loaded %d documents from %s",
            len(self._registry_entries),
            self._docs_package,
        )

    def list_documents(
        self,
        *,
        category: str | None = None,
        tags: Sequence[str] | None = None,
    ) -> list[DocMetadata]:
        """List available documents with optional filtering.

        Args:
            category: Filter by category (exact match). None = no filter.
            tags: Filter by tags (OR logic - docs with ANY matching tag).
                  None = no filter.

        Returns:
            List of DocMetadata for matching documents.
            Empty list if no matches (not an error).
        """
        results: list[DocMetadata] = []

        for metadata in self._registry_entries.values():
            # Apply category filter
            if category is not None and metadata.category != category:
                continue

            # Apply tags filter (OR logic per spec AC3)
            if tags is not None:
                tag_set = set(tags)
                if not tag_set.intersection(metadata.tags):
                    continue

            results.append(metadata)

        return results

    def get_document(self, doc_id: str) -> Doc | None:
        """Get full document content by ID.

        Per DYK-2: Loads content fresh each call (no caching).

        Args:
            doc_id: Document identifier from registry.

        Returns:
            Doc with metadata and full content, or None if not found.
        """
        metadata = self._registry_entries.get(doc_id)
        if metadata is None:
            return None

        # Load content fresh (DYK-2)
        try:
            base = importlib_resources.files(self._docs_package)
            doc_file = base.joinpath(metadata.path)
            content = doc_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to load document %s: %s", doc_id, e)
            return None

        return Doc(metadata=metadata, content=content)
