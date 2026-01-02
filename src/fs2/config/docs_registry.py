"""Documentation registry models for fs2.

Provides Pydantic models for validating registry.yaml structure:
- DocumentEntry: Nested model for individual document metadata
- DocsRegistry: Root model containing list of documents

Design Principles:
- Fail fast: Invalid registry.yaml fails at load time, not tool call time
- Actionable errors: Validation messages guide users to fix issues
- ID pattern: Only lowercase letters, numbers, and hyphens

Per Phase 1: Domain Models and Registry
Per Critical Finding 04: Registry Validation
Per DYK-3: Pydantic models in config/ layer (not core/models/)
"""

from pydantic import BaseModel, Field


class DocumentEntry(BaseModel):
    """Document entry in registry.yaml.

    Represents a single document's metadata in the registry file.
    Used during YAML parsing; converted to DocMetadata for domain use.

    Attributes:
        id: Unique document identifier (lowercase, numbers, hyphens only).
             Must match pattern ^[a-z0-9-]+$ per spec.
        title: Human-readable document title.
        summary: 1-2 sentence description of what the doc covers.
        category: Document category (e.g., "how-to", "reference").
        tags: List of tag strings for filtering.
        path: Relative path to markdown file within fs2.docs package.
    """

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    title: str
    summary: str
    category: str
    tags: list[str]
    path: str


class DocsRegistry(BaseModel):
    """Root model for registry.yaml.

    Validates the complete registry structure when loaded from YAML.
    Ensures all document entries are valid before tool usage.

    Attributes:
        documents: List of document entries in the registry.

    Example YAML:
        ```yaml
        documents:
          - id: agents
            title: "AI Agent Guidance"
            summary: "Best practices for AI agents"
            category: how-to
            tags:
              - agents
              - mcp
            path: agents.md
        ```
    """

    documents: list[DocumentEntry]
