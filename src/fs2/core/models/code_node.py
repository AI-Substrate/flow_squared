"""CodeNode domain model and classify_node utility.

Provides:
- CodeNode: Universal frozen dataclass representing any structural code element
- classify_node: Language-agnostic classification via pattern matching

Design Principles:
- Language-agnostic: Works for Python, JavaScript, Markdown, Terraform, etc.
- Dual classification: ts_kind (grammar-specific) + category (universal)
- Content-rich: Full source text for embeddings and AI
- No embedded children: Hierarchy via graph edges (child_of), not nested objects
- Dual embedding: Both raw content and smart content embeddings for flexible search

Per Critical Findings: 09 (frozen), 11 (node ID), 12 (truncation)
Per Alignment Brief: Dual classification, position-based anonymous IDs
Per DYK-1: Embeddings as tuple[tuple[float, ...], ...] for chunk-level storage
Per DYK-2: Separate smart_content_embedding field for AI-generated descriptions
"""

from dataclasses import dataclass
from pathlib import Path

from fs2.core.models.content_type import ContentType
from fs2.core.utils.hash import compute_content_hash


def classify_node(ts_kind: str) -> str:
    """Map tree-sitter node type to universal category.

    100% language-agnostic via suffix/substring patterns.
    Works for any language tree-sitter can parse, including new ones.

    Args:
        ts_kind: Tree-sitter node type (e.g., "function_definition", "class_declaration")

    Returns:
        Universal category string:
        - "file": Root containers (module, program, source_file, etc.)
        - "callable": Functions, methods, lambdas
        - "type": Classes, structs, interfaces, enums
        - "section": Markdown/document headings
        - "statement": Control flow statements
        - "expression": Expressions
        - "block": IaC blocks, code blocks
        - "definition": Variable/constant definitions
        - "other": Unrecognized node types
    """
    # Root containers (direct match)
    if ts_kind in (
        "module",
        "program",
        "source_file",
        "document",
        "compilation_unit",
        "translation_unit",
        "config_file",
        "stream",
    ):
        return "file"

    # Suffix patterns first (more specific, prevents false matches)
    # e.g., "FROM_instruction" should not match "struct" substring
    if ts_kind.endswith("_instruction"):  # Dockerfile
        return "block"

    if ts_kind == "block" or ts_kind.endswith("_block"):
        return "block"

    # Substring patterns - tree-sitter grammars follow naming conventions
    if any(x in ts_kind for x in ("function", "method", "lambda", "procedure")):
        return "callable"

    if any(
        x in ts_kind
        for x in ("class", "struct", "interface", "enum", "type_alias", "trait", "impl")
    ):
        return "type"

    if "heading" in ts_kind:
        return "section"

    # More suffix patterns
    if ts_kind.endswith("_statement"):
        return "statement"

    if ts_kind.endswith("_expression"):
        return "expression"

    if ts_kind.endswith(("_definition", "_declaration", "_item", "_specifier")):
        return "definition"

    # Fallback - downstream can still use ts_kind for queries
    return "other"


@dataclass(frozen=True)
class CodeNode:
    """Universal code node representing any structural element from any language.

    Design Principles:
    - Language-agnostic: Works for Python, JavaScript, Markdown, Terraform, etc.
    - Dual classification: ts_kind (grammar-specific) + category (universal)
    - Content-rich: Full source text for embeddings and AI
    - No children field: Hierarchy via graph edges (child_of), NOT embedded children

    Attributes:
        node_id: Unique identifier format {category}:{file_path}:{qualified_name}
                 Anonymous nodes use @line suffix for idempotency
        category: Universal taxonomy ("file", "type", "callable", "section", etc.)
        ts_kind: Original tree-sitter node type from grammar
        name: Simple name (None for anonymous nodes)
        qualified_name: Hierarchical name within file
        start_line: 1-indexed line number (for humans)
        end_line: 1-indexed end line
        start_column: 0-indexed column offset
        end_column: 0-indexed end column
        start_byte: 0-indexed byte offset (for slicing)
        end_byte: 0-indexed end byte
        content: Full source text of this node
        content_hash: SHA-256 hash of content (change detection)
        signature: First line(s) of declaration for quick reference
        language: Source language/grammar name
        is_named: Tree-sitter distinction (True = structural, False = punctuation)
        field_name: Relationship to parent in tree-sitter grammar
        is_error: True if this node is an ERROR node (unparseable chunk)
        content_type: CODE or CONTENT classification (set at scan time, default: CODE)
        parent_node_id: Node ID of parent in hierarchy (None for file nodes)
        truncated: True if content was truncated due to size limits
        truncated_at_line: Line number where truncation occurred
        smart_content: AI-generated summary (defaults to None)
        smart_content_hash: content_hash when smart_content was generated
        embedding: Vector embeddings for raw content chunks.
                   Type: tuple[tuple[float, ...], ...] | None (per DYK-1)
                   Each inner tuple is a 1024-dim embedding for one chunk.
        smart_content_embedding: Vector embeddings for AI-generated descriptions.
                                 Type: tuple[tuple[float, ...], ...] | None (per DYK-2)
                                 Separate from raw embedding for flexible search strategies.
    """

    # === Identity ===
    node_id: str

    # === Classification (DUAL) ===
    category: str
    ts_kind: str

    # === Naming ===
    name: str | None
    qualified_name: str

    # === Location (BOTH formats) ===
    start_line: int
    end_line: int
    start_column: int
    end_column: int
    start_byte: int
    end_byte: int

    # === Content ===
    content: str
    content_hash: str
    signature: str | None

    # === Metadata ===
    language: str
    is_named: bool
    field_name: str | None

    # === Error Flag ===
    is_error: bool = False

    # === Content Type (with default for backwards compatibility) ===
    content_type: ContentType = ContentType.CODE  # CODE or CONTENT, set at scan time

    # === Hierarchy ===
    parent_node_id: str | None = None

    # === Large File Handling ===
    truncated: bool = False
    truncated_at_line: int | None = None

    # === AI-Generated Content ===
    smart_content: str | None = None
    smart_content_hash: str | None = (
        None  # content_hash when smart_content was generated
    )

    # === Embedding Fields (per DYK-1 and DYK-2) ===
    # Type: tuple[tuple[float, ...], ...] | None - chunk-level storage
    embedding: tuple[tuple[float, ...], ...] | None = None
    smart_content_embedding: tuple[tuple[float, ...], ...] | None = None
    embedding_hash: str | None = (
        None  # content_hash when embedding was generated (for staleness detection)
    )

    # === Chunk Offset Tracking (Phase 0) ===
    # Type: tuple[tuple[int, int], ...] | None - (start_line, end_line) per chunk
    # Per DYK-05: Only raw content has offsets; smart_content uses node's full range
    embedding_chunk_offsets: tuple[tuple[int, int], ...] | None = None

    # === Call Site Tracking (Phase 8 LSP Integration) ===
    # Type: tuple[tuple[int, int], ...] | None - (line, column) per call expression
    # Positions are RELATIVE to node content (0-indexed)
    # For method calls (obj.method()), position points to method name, not receiver
    # Used by RelationshipExtractionStage to query LSP get_definition at exact call sites
    call_sites: tuple[tuple[int, int], ...] | None = None

    # === Factory Methods ===

    @classmethod
    def create_file(
        cls,
        file_path: str,
        language: str,
        ts_kind: str,
        start_byte: int,
        end_byte: int,
        start_line: int,
        end_line: int,
        content: str,
        *,
        content_type: ContentType = ContentType.CODE,
        is_named: bool = True,
        field_name: str | None = None,
        is_error: bool = False,
        parent_node_id: str | None = None,
        truncated: bool = False,
        truncated_at_line: int | None = None,
        smart_content: str | None = None,
        smart_content_hash: str | None = None,
        embedding: tuple[tuple[float, ...], ...] | None = None,
        smart_content_embedding: tuple[tuple[float, ...], ...] | None = None,
        embedding_hash: str | None = None,
        embedding_chunk_offsets: tuple[tuple[int, int], ...] | None = None,
    ) -> "CodeNode":
        """Create a file-level CodeNode.

        Args:
            file_path: Relative path to the file
            language: Source language/grammar
            content_type: CODE or CONTENT classification
            ts_kind: Tree-sitter root node type (e.g., "module", "program")
            start_byte: 0-indexed start byte
            end_byte: 0-indexed end byte
            start_line: 1-indexed start line
            end_line: 1-indexed end line
            content: Full file content
            **kwargs: Optional metadata fields

        Returns:
            CodeNode with category="file" and node_id="file:{path}"
        """
        name = Path(file_path).name
        return cls(
            node_id=f"file:{file_path}",
            category="file",
            ts_kind=ts_kind,
            name=name,
            qualified_name=name,
            start_line=start_line,
            end_line=end_line,
            start_column=0,
            end_column=0,
            start_byte=start_byte,
            end_byte=end_byte,
            content=content,
            content_hash=compute_content_hash(content),
            signature=None,
            language=language,
            content_type=content_type,
            is_named=is_named,
            field_name=field_name,
            is_error=is_error,
            parent_node_id=parent_node_id,
            truncated=truncated,
            truncated_at_line=truncated_at_line,
            smart_content=smart_content,
            smart_content_hash=smart_content_hash,
            embedding=embedding,
            smart_content_embedding=smart_content_embedding,
            embedding_hash=embedding_hash,
            embedding_chunk_offsets=embedding_chunk_offsets,
        )

    @classmethod
    def create_type(
        cls,
        file_path: str,
        language: str,
        ts_kind: str,
        name: str,
        qualified_name: str,
        start_line: int,
        end_line: int,
        start_column: int,
        end_column: int,
        start_byte: int,
        end_byte: int,
        content: str,
        signature: str,
        *,
        content_type: ContentType = ContentType.CODE,
        is_named: bool = True,
        field_name: str | None = None,
        is_error: bool = False,
        parent_node_id: str | None = None,
        truncated: bool = False,
        truncated_at_line: int | None = None,
        smart_content: str | None = None,
        smart_content_hash: str | None = None,
        embedding: tuple[tuple[float, ...], ...] | None = None,
        smart_content_embedding: tuple[tuple[float, ...], ...] | None = None,
        embedding_hash: str | None = None,
        embedding_chunk_offsets: tuple[tuple[int, int], ...] | None = None,
    ) -> "CodeNode":
        """Create a type-level CodeNode (class, struct, interface, enum).

        Args:
            file_path: Relative path to the file
            language: Source language/grammar
            ts_kind: Tree-sitter node type (e.g., "class_definition")
            content_type: CODE or CONTENT classification (default: CODE)
            name: Simple type name
            qualified_name: Hierarchical name within file
            start_line: 1-indexed start line
            end_line: 1-indexed end line
            start_column: 0-indexed start column
            end_column: 0-indexed end column
            start_byte: 0-indexed start byte
            end_byte: 0-indexed end byte
            content: Full type definition source
            signature: First line of declaration
            **kwargs: Optional metadata fields

        Returns:
            CodeNode with category="type" and node_id="type:{path}:{qualified_name}"
        """
        return cls(
            node_id=f"type:{file_path}:{qualified_name}",
            category="type",
            ts_kind=ts_kind,
            name=name,
            qualified_name=qualified_name,
            start_line=start_line,
            end_line=end_line,
            start_column=start_column,
            end_column=end_column,
            start_byte=start_byte,
            end_byte=end_byte,
            content=content,
            content_hash=compute_content_hash(content),
            signature=signature,
            language=language,
            content_type=content_type,
            is_named=is_named,
            field_name=field_name,
            is_error=is_error,
            parent_node_id=parent_node_id,
            truncated=truncated,
            truncated_at_line=truncated_at_line,
            smart_content=smart_content,
            smart_content_hash=smart_content_hash,
            embedding=embedding,
            smart_content_embedding=smart_content_embedding,
            embedding_hash=embedding_hash,
            embedding_chunk_offsets=embedding_chunk_offsets,
        )

    @classmethod
    def create_callable(
        cls,
        file_path: str,
        language: str,
        ts_kind: str,
        name: str,
        qualified_name: str,
        start_line: int,
        end_line: int,
        start_column: int,
        end_column: int,
        start_byte: int,
        end_byte: int,
        content: str,
        signature: str,
        *,
        content_type: ContentType = ContentType.CODE,
        is_named: bool = True,
        field_name: str | None = None,
        is_error: bool = False,
        parent_node_id: str | None = None,
        truncated: bool = False,
        truncated_at_line: int | None = None,
        smart_content: str | None = None,
        smart_content_hash: str | None = None,
        embedding: tuple[tuple[float, ...], ...] | None = None,
        smart_content_embedding: tuple[tuple[float, ...], ...] | None = None,
        embedding_hash: str | None = None,
        embedding_chunk_offsets: tuple[tuple[int, int], ...] | None = None,
        call_sites: tuple[tuple[int, int], ...] | None = None,
    ) -> "CodeNode":
        """Create a callable CodeNode (function, method, lambda).

        Args:
            file_path: Relative path to the file
            language: Source language/grammar
            ts_kind: Tree-sitter node type (e.g., "function_definition")
            content_type: CODE or CONTENT classification (default: CODE)
            name: Simple callable name
            qualified_name: Hierarchical name within file
            start_line: 1-indexed start line
            end_line: 1-indexed end line
            start_column: 0-indexed start column
            end_column: 0-indexed end column
            start_byte: 0-indexed start byte
            end_byte: 0-indexed end byte
            content: Full callable source
            signature: First line of declaration
            call_sites: Call expression positions (line, col) relative to content, 0-indexed
            **kwargs: Optional metadata fields

        Returns:
            CodeNode with category="callable" and node_id="callable:{path}:{qualified_name}"
        """
        return cls(
            node_id=f"callable:{file_path}:{qualified_name}",
            category="callable",
            ts_kind=ts_kind,
            name=name,
            qualified_name=qualified_name,
            start_line=start_line,
            end_line=end_line,
            start_column=start_column,
            end_column=end_column,
            start_byte=start_byte,
            end_byte=end_byte,
            content=content,
            content_hash=compute_content_hash(content),
            signature=signature,
            language=language,
            content_type=content_type,
            is_named=is_named,
            field_name=field_name,
            is_error=is_error,
            parent_node_id=parent_node_id,
            truncated=truncated,
            truncated_at_line=truncated_at_line,
            smart_content=smart_content,
            smart_content_hash=smart_content_hash,
            embedding=embedding,
            smart_content_embedding=smart_content_embedding,
            embedding_hash=embedding_hash,
            embedding_chunk_offsets=embedding_chunk_offsets,
            call_sites=call_sites,
        )

    @classmethod
    def create_section(
        cls,
        file_path: str,
        language: str,
        ts_kind: str,
        name: str,
        qualified_name: str,
        start_line: int,
        end_line: int,
        start_column: int,
        end_column: int,
        start_byte: int,
        end_byte: int,
        content: str,
        signature: str,
        *,
        content_type: ContentType = ContentType.CONTENT,
        is_named: bool = True,
        field_name: str | None = None,
        is_error: bool = False,
        parent_node_id: str | None = None,
        truncated: bool = False,
        truncated_at_line: int | None = None,
        smart_content: str | None = None,
        smart_content_hash: str | None = None,
        embedding: tuple[tuple[float, ...], ...] | None = None,
        smart_content_embedding: tuple[tuple[float, ...], ...] | None = None,
        embedding_hash: str | None = None,
        embedding_chunk_offsets: tuple[tuple[int, int], ...] | None = None,
    ) -> "CodeNode":
        """Create a section CodeNode (markdown heading, document section).

        Args:
            file_path: Relative path to the file
            language: Source language/grammar (e.g., "markdown")
            ts_kind: Tree-sitter node type (e.g., "atx_heading")
            content_type: CODE or CONTENT classification (default: CONTENT)
            name: Section title
            qualified_name: Hierarchical name within file
            start_line: 1-indexed start line
            end_line: 1-indexed end line
            start_column: 0-indexed start column
            end_column: 0-indexed end column
            start_byte: 0-indexed start byte
            end_byte: 0-indexed end byte
            content: Full section content
            signature: Heading line
            **kwargs: Optional metadata fields

        Returns:
            CodeNode with category="section" and node_id="section:{path}:{qualified_name}"
        """
        return cls(
            node_id=f"section:{file_path}:{qualified_name}",
            category="section",
            ts_kind=ts_kind,
            name=name,
            qualified_name=qualified_name,
            start_line=start_line,
            end_line=end_line,
            start_column=start_column,
            end_column=end_column,
            start_byte=start_byte,
            end_byte=end_byte,
            content=content,
            content_hash=compute_content_hash(content),
            signature=signature,
            language=language,
            content_type=content_type,
            is_named=is_named,
            field_name=field_name,
            is_error=is_error,
            parent_node_id=parent_node_id,
            truncated=truncated,
            truncated_at_line=truncated_at_line,
            smart_content=smart_content,
            smart_content_hash=smart_content_hash,
            embedding=embedding,
            smart_content_embedding=smart_content_embedding,
            embedding_hash=embedding_hash,
            embedding_chunk_offsets=embedding_chunk_offsets,
        )

    @classmethod
    def create_block(
        cls,
        file_path: str,
        language: str,
        ts_kind: str,
        name: str,
        qualified_name: str,
        start_line: int,
        end_line: int,
        start_column: int,
        end_column: int,
        start_byte: int,
        end_byte: int,
        content: str,
        signature: str,
        *,
        content_type: ContentType = ContentType.CONTENT,
        is_named: bool = True,
        field_name: str | None = None,
        is_error: bool = False,
        parent_node_id: str | None = None,
        truncated: bool = False,
        truncated_at_line: int | None = None,
        smart_content: str | None = None,
        smart_content_hash: str | None = None,
        embedding: tuple[tuple[float, ...], ...] | None = None,
        smart_content_embedding: tuple[tuple[float, ...], ...] | None = None,
        embedding_hash: str | None = None,
        embedding_chunk_offsets: tuple[tuple[int, int], ...] | None = None,
    ) -> "CodeNode":
        """Create a block CodeNode (terraform block, dockerfile instruction).

        Args:
            file_path: Relative path to the file
            language: Source language/grammar (e.g., "hcl")
            ts_kind: Tree-sitter node type (e.g., "block", "FROM_instruction")
            content_type: CODE or CONTENT classification (default: CONTENT)
            name: Block identifier
            qualified_name: Hierarchical name within file
            start_line: 1-indexed start line
            end_line: 1-indexed end line
            start_column: 0-indexed start column
            end_column: 0-indexed end column
            start_byte: 0-indexed start byte
            end_byte: 0-indexed end byte
            content: Full block source
            signature: First line of block
            **kwargs: Optional metadata fields

        Returns:
            CodeNode with category="block" and node_id="block:{path}:{qualified_name}"
        """
        return cls(
            node_id=f"block:{file_path}:{qualified_name}",
            category="block",
            ts_kind=ts_kind,
            name=name,
            qualified_name=qualified_name,
            start_line=start_line,
            end_line=end_line,
            start_column=start_column,
            end_column=end_column,
            start_byte=start_byte,
            end_byte=end_byte,
            content=content,
            content_hash=compute_content_hash(content),
            signature=signature,
            language=language,
            content_type=content_type,
            is_named=is_named,
            field_name=field_name,
            is_error=is_error,
            parent_node_id=parent_node_id,
            truncated=truncated,
            truncated_at_line=truncated_at_line,
            smart_content=smart_content,
            smart_content_hash=smart_content_hash,
            embedding=embedding,
            smart_content_embedding=smart_content_embedding,
            embedding_hash=embedding_hash,
            embedding_chunk_offsets=embedding_chunk_offsets,
        )
