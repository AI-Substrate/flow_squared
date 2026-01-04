"""Tests for DocsRegistry Pydantic model.

Tests verify:
- YAML parsing for registry structure
- Validation of required fields
- ID pattern enforcement (^[a-z0-9-]+$)
- Actionable error messages

Per Phase 1: Domain Models and Registry
Per Critical Finding 04: Registry Validation
Per DYK-3: DocsRegistry in config/ layer for Pydantic models
"""

import pytest
from pydantic import ValidationError


@pytest.mark.unit
class TestDocumentEntry:
    """Tests for DocumentEntry nested model."""

    def test_given_valid_entry_when_constructing_then_succeeds(self):
        """
        Purpose: Proves DocumentEntry accepts all valid fields
        Quality Contribution: Basic construction works
        """
        from fs2.config.docs_registry import DocumentEntry

        entry = DocumentEntry(
            id="agents",
            title="AI Agent Guidance",
            summary="Best practices for AI agents",
            category="how-to",
            tags=["agents", "mcp"],
            path="agents.md",
        )

        assert entry.id == "agents"
        assert entry.title == "AI Agent Guidance"
        assert entry.summary == "Best practices for AI agents"
        assert entry.category == "how-to"
        assert entry.tags == ["agents", "mcp"]
        assert entry.path == "agents.md"

    def test_given_valid_lowercase_id_when_constructing_then_succeeds(self):
        """
        Purpose: Proves lowercase IDs are accepted
        Quality Contribution: Validates ID pattern
        """
        from fs2.config.docs_registry import DocumentEntry

        entry = DocumentEntry(
            id="configuration-guide",
            title="Config Guide",
            summary="How to configure",
            category="reference",
            tags=["config"],
            path="config.md",
        )

        assert entry.id == "configuration-guide"

    def test_given_id_with_numbers_when_constructing_then_succeeds(self):
        """
        Purpose: Proves numbers in ID are accepted
        Quality Contribution: Validates ID pattern includes digits
        """
        from fs2.config.docs_registry import DocumentEntry

        entry = DocumentEntry(
            id="getting-started-v2",
            title="Getting Started v2",
            summary="Updated guide",
            category="how-to",
            tags=["setup"],
            path="getting-started.md",
        )

        assert entry.id == "getting-started-v2"

    def test_given_uppercase_id_when_constructing_then_raises_validation_error(self):
        """
        Purpose: Proves uppercase IDs are rejected per spec AC6
        Quality Contribution: Enforces ID pattern
        """
        from fs2.config.docs_registry import DocumentEntry

        with pytest.raises(ValidationError) as exc_info:
            DocumentEntry(
                id="Agents",
                title="AI Agent Guidance",
                summary="Best practices",
                category="how-to",
                tags=["agents"],
                path="agents.md",
            )

        error_str = str(exc_info.value)
        assert "id" in error_str.lower()

    def test_given_id_with_spaces_when_constructing_then_raises_validation_error(self):
        """
        Purpose: Proves spaces in ID are rejected
        Quality Contribution: Enforces ID pattern
        """
        from fs2.config.docs_registry import DocumentEntry

        with pytest.raises(ValidationError) as exc_info:
            DocumentEntry(
                id="my agents",
                title="AI Agent Guidance",
                summary="Best practices",
                category="how-to",
                tags=["agents"],
                path="agents.md",
            )

        error_str = str(exc_info.value)
        assert "id" in error_str.lower()

    def test_given_id_with_underscore_when_constructing_then_raises_validation_error(
        self,
    ):
        """
        Purpose: Proves underscores in ID are rejected (only hyphens allowed)
        Quality Contribution: Enforces ID pattern
        """
        from fs2.config.docs_registry import DocumentEntry

        with pytest.raises(ValidationError) as exc_info:
            DocumentEntry(
                id="my_agents",
                title="AI Agent Guidance",
                summary="Best practices",
                category="how-to",
                tags=["agents"],
                path="agents.md",
            )

        error_str = str(exc_info.value)
        assert "id" in error_str.lower()

    def test_given_missing_id_when_constructing_then_raises_validation_error(self):
        """
        Purpose: Proves id field is required
        Quality Contribution: Catches incomplete entries
        """
        from fs2.config.docs_registry import DocumentEntry

        with pytest.raises(ValidationError):
            DocumentEntry(
                title="AI Agent Guidance",
                summary="Best practices",
                category="how-to",
                tags=["agents"],
                path="agents.md",
            )

    def test_given_missing_title_when_constructing_then_raises_validation_error(self):
        """
        Purpose: Proves title field is required
        Quality Contribution: Catches incomplete entries
        """
        from fs2.config.docs_registry import DocumentEntry

        with pytest.raises(ValidationError):
            DocumentEntry(
                id="agents",
                summary="Best practices",
                category="how-to",
                tags=["agents"],
                path="agents.md",
            )


@pytest.mark.unit
class TestDocsRegistry:
    """Tests for DocsRegistry Pydantic model."""

    def test_given_valid_registry_when_constructing_then_succeeds(self):
        """
        Purpose: Proves DocsRegistry parses valid structure
        Quality Contribution: Basic construction works
        """
        from fs2.config.docs_registry import DocsRegistry, DocumentEntry

        registry = DocsRegistry(
            documents=[
                DocumentEntry(
                    id="agents",
                    title="AI Agent Guidance",
                    summary="Best practices for AI agents",
                    category="how-to",
                    tags=["agents", "mcp"],
                    path="agents.md",
                ),
            ]
        )

        assert len(registry.documents) == 1
        assert registry.documents[0].id == "agents"

    def test_given_empty_documents_when_constructing_then_succeeds(self):
        """
        Purpose: Proves empty documents list is valid
        Quality Contribution: Supports initial empty registry
        """
        from fs2.config.docs_registry import DocsRegistry

        registry = DocsRegistry(documents=[])

        assert len(registry.documents) == 0
        assert isinstance(registry.documents, list)

    def test_given_multiple_documents_when_constructing_then_succeeds(self):
        """
        Purpose: Proves registry can hold multiple documents
        Quality Contribution: Supports real-world usage
        """
        from fs2.config.docs_registry import DocsRegistry, DocumentEntry

        registry = DocsRegistry(
            documents=[
                DocumentEntry(
                    id="agents",
                    title="AI Agent Guidance",
                    summary="Best practices",
                    category="how-to",
                    tags=["agents"],
                    path="agents.md",
                ),
                DocumentEntry(
                    id="configuration-guide",
                    title="Configuration Guide",
                    summary="How to configure",
                    category="reference",
                    tags=["config"],
                    path="configuration-guide.md",
                ),
            ]
        )

        assert len(registry.documents) == 2
        assert registry.documents[0].id == "agents"
        assert registry.documents[1].id == "configuration-guide"

    def test_given_yaml_dict_when_constructing_then_succeeds(self):
        """
        Purpose: Proves registry parses YAML-like dict structure
        Quality Contribution: Validates YAML parsing workflow
        """
        from fs2.config.docs_registry import DocsRegistry

        # Simulate YAML parsed as dict
        yaml_data = {
            "documents": [
                {
                    "id": "agents",
                    "title": "AI Agent Guidance",
                    "summary": "Best practices",
                    "category": "how-to",
                    "tags": ["agents", "mcp"],
                    "path": "agents.md",
                }
            ]
        }

        registry = DocsRegistry(**yaml_data)

        assert len(registry.documents) == 1
        assert registry.documents[0].id == "agents"

    def test_given_missing_documents_field_when_constructing_then_raises_validation_error(
        self,
    ):
        """
        Purpose: Proves documents field is required
        Quality Contribution: Catches malformed registry
        """
        from fs2.config.docs_registry import DocsRegistry

        with pytest.raises(ValidationError):
            DocsRegistry()
