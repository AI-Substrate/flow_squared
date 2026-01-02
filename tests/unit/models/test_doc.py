"""Tests for documentation domain models (frozen dataclasses).

Tests verify:
- DocMetadata immutability and required fields
- Doc composition of metadata + content
- Factory method for converting registry entries

Per Phase 1 Tasks: Domain Models and Registry
Per Critical Finding 02: path is str, not Path (wheel compatibility)
Per DYK-1: Factory method for DocumentEntry→DocMetadata conversion
Per DYK-2: tags field is tuple for immutability
"""

from dataclasses import FrozenInstanceError

import pytest


@pytest.mark.unit
class TestDocMetadata:
    """Tests for DocMetadata frozen dataclass."""

    def test_given_docmetadata_when_created_then_has_all_six_fields(self):
        """
        Purpose: Proves DocMetadata has id, title, summary, category, tags, path
        Quality Contribution: Documents complete field set per spec AC1
        """
        from fs2.core.models.doc import DocMetadata

        meta = DocMetadata(
            id="test-doc",
            title="Test Document",
            summary="A test document for verification",
            category="how-to",
            tags=("test", "example"),
            path="test.md",
        )

        assert meta.id == "test-doc"
        assert meta.title == "Test Document"
        assert meta.summary == "A test document for verification"
        assert meta.category == "how-to"
        assert meta.tags == ("test", "example")
        assert meta.path == "test.md"

    def test_given_docmetadata_when_assigning_id_then_raises_frozen_error(self):
        """
        Purpose: Proves DocMetadata is immutable (frozen dataclass)
        Quality Contribution: Prevents accidental state mutation
        """
        from fs2.core.models.doc import DocMetadata

        meta = DocMetadata(
            id="test-doc",
            title="Test Document",
            summary="A test document",
            category="how-to",
            tags=("test",),
            path="test.md",
        )

        with pytest.raises(FrozenInstanceError):
            meta.id = "changed"

    def test_given_docmetadata_when_missing_id_then_raises_type_error(self):
        """
        Purpose: Proves id field is required
        Quality Contribution: Catches incomplete model construction
        """
        from fs2.core.models.doc import DocMetadata

        with pytest.raises(TypeError):
            DocMetadata(
                title="Test Document",
                summary="A test document",
                category="how-to",
                tags=("test",),
                path="test.md",
            )

    def test_given_docmetadata_when_missing_title_then_raises_type_error(self):
        """
        Purpose: Proves title field is required
        Quality Contribution: Catches incomplete model construction
        """
        from fs2.core.models.doc import DocMetadata

        with pytest.raises(TypeError):
            DocMetadata(
                id="test-doc",
                summary="A test document",
                category="how-to",
                tags=("test",),
                path="test.md",
            )

    def test_given_docmetadata_when_missing_summary_then_raises_type_error(self):
        """
        Purpose: Proves summary field is required
        Quality Contribution: Catches incomplete model construction
        """
        from fs2.core.models.doc import DocMetadata

        with pytest.raises(TypeError):
            DocMetadata(
                id="test-doc",
                title="Test Document",
                category="how-to",
                tags=("test",),
                path="test.md",
            )

    def test_given_docmetadata_when_missing_category_then_raises_type_error(self):
        """
        Purpose: Proves category field is required
        Quality Contribution: Catches incomplete model construction
        """
        from fs2.core.models.doc import DocMetadata

        with pytest.raises(TypeError):
            DocMetadata(
                id="test-doc",
                title="Test Document",
                summary="A test document",
                tags=("test",),
                path="test.md",
            )

    def test_given_docmetadata_when_missing_tags_then_raises_type_error(self):
        """
        Purpose: Proves tags field is required
        Quality Contribution: Catches incomplete model construction
        """
        from fs2.core.models.doc import DocMetadata

        with pytest.raises(TypeError):
            DocMetadata(
                id="test-doc",
                title="Test Document",
                summary="A test document",
                category="how-to",
                path="test.md",
            )

    def test_given_docmetadata_when_missing_path_then_raises_type_error(self):
        """
        Purpose: Proves path field is required
        Quality Contribution: Catches incomplete model construction
        """
        from fs2.core.models.doc import DocMetadata

        with pytest.raises(TypeError):
            DocMetadata(
                id="test-doc",
                title="Test Document",
                summary="A test document",
                category="how-to",
                tags=("test",),
            )

    def test_given_docmetadata_then_tags_is_tuple(self):
        """
        Purpose: Proves tags field is tuple for immutability (per DYK-2)
        Quality Contribution: Ensures full immutability, not just frozen dataclass
        """
        from fs2.core.models.doc import DocMetadata

        meta = DocMetadata(
            id="test-doc",
            title="Test Document",
            summary="A test document",
            category="how-to",
            tags=("test", "example"),
            path="test.md",
        )

        assert isinstance(meta.tags, tuple)

    def test_given_docmetadata_then_path_is_string(self):
        """
        Purpose: Proves path is str, not Path (per Critical Finding 02)
        Quality Contribution: Ensures wheel compatibility with importlib.resources
        """
        from fs2.core.models.doc import DocMetadata

        meta = DocMetadata(
            id="test-doc",
            title="Test Document",
            summary="A test document",
            category="how-to",
            tags=("test",),
            path="test.md",
        )

        assert isinstance(meta.path, str)


@pytest.mark.unit
class TestDoc:
    """Tests for Doc frozen dataclass."""

    def test_given_doc_when_created_then_has_metadata_field(self):
        """
        Purpose: Proves Doc has metadata field of type DocMetadata
        Quality Contribution: Validates composition pattern
        """
        from fs2.core.models.doc import Doc, DocMetadata

        meta = DocMetadata(
            id="test-doc",
            title="Test Document",
            summary="A test document",
            category="how-to",
            tags=("test",),
            path="test.md",
        )
        doc = Doc(metadata=meta, content="# Test\n\nContent here.")

        assert doc.metadata == meta
        assert isinstance(doc.metadata, DocMetadata)

    def test_given_doc_when_created_then_has_content_field(self):
        """
        Purpose: Proves Doc has content field of type str
        Quality Contribution: Validates full document content access
        """
        from fs2.core.models.doc import Doc, DocMetadata

        meta = DocMetadata(
            id="test-doc",
            title="Test Document",
            summary="A test document",
            category="how-to",
            tags=("test",),
            path="test.md",
        )
        content = "# Test\n\nContent here."
        doc = Doc(metadata=meta, content=content)

        assert doc.content == content
        assert isinstance(doc.content, str)

    def test_given_doc_when_assigning_content_then_raises_frozen_error(self):
        """
        Purpose: Proves Doc is immutable (frozen dataclass)
        Quality Contribution: Prevents accidental state mutation
        """
        from fs2.core.models.doc import Doc, DocMetadata

        meta = DocMetadata(
            id="test-doc",
            title="Test Document",
            summary="A test document",
            category="how-to",
            tags=("test",),
            path="test.md",
        )
        doc = Doc(metadata=meta, content="# Test")

        with pytest.raises(FrozenInstanceError):
            doc.content = "Changed"

    def test_given_doc_when_missing_metadata_then_raises_type_error(self):
        """
        Purpose: Proves metadata field is required
        Quality Contribution: Catches incomplete model construction
        """
        from fs2.core.models.doc import Doc

        with pytest.raises(TypeError):
            Doc(content="# Test")

    def test_given_doc_when_missing_content_then_raises_type_error(self):
        """
        Purpose: Proves content field is required
        Quality Contribution: Catches incomplete model construction
        """
        from fs2.core.models.doc import Doc, DocMetadata

        meta = DocMetadata(
            id="test-doc",
            title="Test Document",
            summary="A test document",
            category="how-to",
            tags=("test",),
            path="test.md",
        )

        with pytest.raises(TypeError):
            Doc(metadata=meta)


@pytest.mark.unit
class TestDocMetadataFactory:
    """Tests for DocMetadata.from_registry_entry() factory method.

    Per DYK-1: Bridges the gap between Pydantic DocumentEntry and frozen DocMetadata.
    """

    def test_given_document_entry_when_calling_factory_then_returns_docmetadata(self):
        """
        Purpose: Proves factory creates DocMetadata from DocumentEntry
        Quality Contribution: Validates conversion between Pydantic and dataclass
        """
        from fs2.config.docs_registry import DocumentEntry
        from fs2.core.models.doc import DocMetadata

        entry = DocumentEntry(
            id="agents",
            title="AI Agent Guidance",
            summary="Best practices for AI agents",
            category="how-to",
            tags=["agents", "mcp"],
            path="agents.md",
        )

        result = DocMetadata.from_registry_entry(entry)

        assert isinstance(result, DocMetadata)
        assert result.id == "agents"
        assert result.title == "AI Agent Guidance"
        assert result.summary == "Best practices for AI agents"
        assert result.category == "how-to"
        assert result.path == "agents.md"

    def test_given_document_entry_with_list_tags_when_calling_factory_then_converts_to_tuple(
        self,
    ):
        """
        Purpose: Proves factory converts tags list to tuple (per DYK-2)
        Quality Contribution: Ensures full immutability
        """
        from fs2.config.docs_registry import DocumentEntry
        from fs2.core.models.doc import DocMetadata

        entry = DocumentEntry(
            id="config",
            title="Configuration Guide",
            summary="How to configure",
            category="reference",
            tags=["config", "setup", "azure"],
            path="config.md",
        )

        result = DocMetadata.from_registry_entry(entry)

        assert isinstance(result.tags, tuple)
        assert result.tags == ("config", "setup", "azure")

    def test_given_document_entry_with_empty_tags_when_calling_factory_then_returns_empty_tuple(
        self,
    ):
        """
        Purpose: Proves factory handles empty tags list
        Quality Contribution: Edge case coverage
        """
        from fs2.config.docs_registry import DocumentEntry
        from fs2.core.models.doc import DocMetadata

        entry = DocumentEntry(
            id="simple",
            title="Simple Doc",
            summary="A simple document",
            category="how-to",
            tags=[],
            path="simple.md",
        )

        result = DocMetadata.from_registry_entry(entry)

        assert isinstance(result.tags, tuple)
        assert result.tags == ()
