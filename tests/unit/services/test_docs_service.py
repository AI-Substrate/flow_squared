"""Tests for DocsService (MCP Documentation Phase 2).

TDD Phase: RED - Tests written first, DocsService not yet implemented.

Focus:
- DYK-1: Package path parameter for fixture injection
- DYK-2: Registry cached at init, content fresh per-call
- DYK-3: Validate all document paths at init (fail-fast)
- Critical Finding 02: importlib.resources wheel compatibility
- Critical Finding 06: DocsNotFoundError with actionable message
"""

import pytest

from fs2.core.models import DocMetadata

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def docs_service():
    """Create DocsService with test fixture package.

    Per DYK-1: Uses docs_package parameter to inject fixture package
    instead of production fs2.docs package.
    """
    from fs2.core.services.docs_service import DocsService

    return DocsService(docs_package="tests.fixtures.docs")


# ============================================================================
# TestDocsServiceListDocuments - T001
# ============================================================================


class TestDocsServiceListDocuments:
    """Tests for DocsService.list_documents()."""

    @pytest.mark.unit
    def test_given_docs_service_when_list_all_then_returns_all_documents(
        self, docs_service
    ):
        """DocsService.list_documents() returns all registered docs.

        Purpose: Proves basic catalog functionality works
        Quality Contribution: Validates registry loading and conversion
        Acceptance Criteria: Returns list with count matching registry (2 docs)
        """
        result = docs_service.list_documents()

        assert len(result) == 2
        assert all(isinstance(doc, DocMetadata) for doc in result)
        ids = {doc.id for doc in result}
        assert ids == {"sample-doc", "another-doc"}

    @pytest.mark.unit
    def test_given_docs_service_when_filter_by_category_then_returns_matching(
        self, docs_service
    ):
        """DocsService.list_documents(category=...) filters by category.

        Purpose: Proves category filtering works per spec AC2
        Quality Contribution: Enables agent discovery by category
        Acceptance Criteria: Only docs with matching category returned
        """
        result = docs_service.list_documents(category="how-to")

        assert len(result) == 1
        assert result[0].id == "sample-doc"
        assert result[0].category == "how-to"

    @pytest.mark.unit
    def test_given_docs_service_when_filter_by_tags_then_uses_or_logic(
        self, docs_service
    ):
        """DocsService.list_documents(tags=[...]) uses OR logic.

        Purpose: Proves tag filtering with OR semantics per spec AC3
        Quality Contribution: Matches spec behavior for multi-tag queries
        Acceptance Criteria: Docs with ANY matching tag returned
        """
        # "sample" tag only in sample-doc, "config" tag only in another-doc
        result = docs_service.list_documents(tags=["sample", "config"])

        # Should include both docs since each has one matching tag
        assert len(result) == 2

    @pytest.mark.unit
    def test_given_docs_service_when_filter_by_category_and_tags_then_both_applied(
        self, docs_service
    ):
        """DocsService.list_documents(category, tags) applies both filters.

        Purpose: Proves combined filtering works
        Quality Contribution: Supports precise document discovery
        Acceptance Criteria: Only docs matching BOTH category AND any tag
        """
        # sample-doc is how-to with tags [sample, testing]
        result = docs_service.list_documents(category="how-to", tags=["sample"])

        assert len(result) == 1
        assert result[0].id == "sample-doc"

    @pytest.mark.unit
    def test_given_docs_service_when_no_matches_then_returns_empty_list(
        self, docs_service
    ):
        """DocsService.list_documents() returns empty list when no matches.

        Purpose: Proves no error on empty results
        Quality Contribution: Prevents exceptions on valid but empty queries
        Acceptance Criteria: Empty list returned, no error
        """
        result = docs_service.list_documents(category="nonexistent-category")

        assert result == []

    @pytest.mark.unit
    def test_given_docs_service_when_filter_by_multiple_tags_then_or_logic_applied(
        self, docs_service
    ):
        """DocsService.list_documents(tags=[...]) with multiple tags uses OR.

        Purpose: Proves multiple-tag OR filtering
        Quality Contribution: Validates spec AC3 with multiple tags
        Acceptance Criteria: Docs with ANY of the listed tags returned
        """
        # "testing" in sample-doc, "reference" in another-doc
        result = docs_service.list_documents(tags=["testing", "reference"])

        assert len(result) == 2
        ids = {doc.id for doc in result}
        assert ids == {"sample-doc", "another-doc"}


# ============================================================================
# TestDocsServiceGetDocument - T002
# ============================================================================


class TestDocsServiceGetDocument:
    """Tests for DocsService.get_document()."""

    @pytest.mark.unit
    def test_given_docs_service_when_get_existing_doc_then_returns_doc(
        self, docs_service
    ):
        """DocsService.get_document(id) returns Doc for existing document.

        Purpose: Proves document retrieval works
        Quality Contribution: Core functionality for agent reading
        Acceptance Criteria: Returns Doc with metadata and content
        """
        from fs2.core.models import Doc

        result = docs_service.get_document("sample-doc")

        assert result is not None
        assert isinstance(result, Doc)
        assert result.metadata.id == "sample-doc"

    @pytest.mark.unit
    def test_given_docs_service_when_get_nonexistent_doc_then_returns_none(
        self, docs_service
    ):
        """DocsService.get_document(id) returns None for unknown ID.

        Purpose: Proves non-existent doc returns None (not error) per spec AC5
        Quality Contribution: Graceful handling of unknown IDs
        Acceptance Criteria: Returns None, no exception
        """
        result = docs_service.get_document("nonexistent-doc-id")

        assert result is None

    @pytest.mark.unit
    def test_given_docs_service_when_get_doc_then_content_matches_file(
        self, docs_service
    ):
        """DocsService.get_document(id) returns content matching file.

        Purpose: Proves content is correctly loaded from markdown file
        Quality Contribution: Validates importlib.resources loading
        Acceptance Criteria: content field equals file contents
        """
        result = docs_service.get_document("sample-doc")

        assert result is not None
        assert "# Sample Documentation" in result.content
        assert "testing the DocsService" in result.content

    @pytest.mark.unit
    def test_given_docs_service_when_get_doc_then_metadata_populated(
        self, docs_service
    ):
        """DocsService.get_document(id) returns fully populated metadata.

        Purpose: Proves all metadata fields are populated from registry
        Quality Contribution: Validates registry-to-model conversion
        Acceptance Criteria: All 6 metadata fields populated correctly
        """
        result = docs_service.get_document("sample-doc")

        assert result is not None
        assert result.metadata.id == "sample-doc"
        assert result.metadata.title == "Sample Documentation"
        assert result.metadata.category == "how-to"
        assert result.metadata.tags == ("sample", "testing")
        assert result.metadata.path == "sample-doc.md"
        assert "sample document for testing" in result.metadata.summary.lower()


# ============================================================================
# TestDocsServiceInitValidation - T003 validation tests (DYK-3)
# ============================================================================


class TestDocsServiceInitValidation:
    """Tests for DocsService initialization validation."""

    @pytest.mark.unit
    def test_given_missing_registry_when_init_then_raises_docs_not_found_error(self):
        """DocsService raises DocsNotFoundError if registry missing.

        Purpose: Proves fail-fast validation per DYK-3
        Quality Contribution: Catches config errors at startup
        Acceptance Criteria: DocsNotFoundError with actionable message
        """
        from fs2.core.adapters.exceptions import DocsNotFoundError
        from fs2.core.services.docs_service import DocsService

        # Nonexistent package raises DocsNotFoundError with package name
        with pytest.raises(DocsNotFoundError, match=r"not found"):
            DocsService(docs_package="nonexistent.package")

    @pytest.mark.unit
    def test_given_missing_doc_file_when_init_then_raises_docs_not_found_error(self):
        """DocsService raises DocsNotFoundError if document file missing.

        Purpose: Proves all paths validated at init per DYK-3
        Quality Contribution: Catches broken registry references at startup
        Acceptance Criteria: DocsNotFoundError with actionable message
        """
        from fs2.core.adapters.exceptions import DocsNotFoundError
        from fs2.core.services.docs_service import DocsService

        # docs_broken package has registry referencing non-existent file
        with pytest.raises(DocsNotFoundError, match=r"missing|not found"):
            DocsService(docs_package="tests.fixtures.docs_broken")
