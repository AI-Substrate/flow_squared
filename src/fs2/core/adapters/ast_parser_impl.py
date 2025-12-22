"""TreeSitterParser - Production implementation of ASTParser ABC.

Provides AST parsing using tree-sitter-language-pack for multi-language support.
Transforms source files into CodeNode hierarchies with language detection.

Architecture:
- Inherits from ASTParser ABC
- Receives ConfigurationService (registry) via constructor
- Uses tree-sitter-language-pack for grammar loading
- Returns flat list of CodeNode (hierarchy via graph edges)

Per Critical Finding 01: Receives ConfigurationService, not extracted config.
Per Critical Finding 02: Adapter ABC with Dual Implementation Pattern.
Per Critical Finding 03: Use .children for O(n) traversal.
Per Critical Finding 07: Binary file detection via null bytes.
Per Critical Finding 08: Named nodes up to depth 4.
Per Critical Finding 10: Translate SDK errors to ASTParserError.
Per Critical Finding 11: Position-based anonymous IDs (@line).
Per Critical Finding 13: Static extension mapping, .h -> cpp.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from tree_sitter_language_pack import get_parser

from fs2.config.objects import ScanConfig
from fs2.core.adapters.ast_parser import ASTParser
from fs2.core.adapters.exceptions import ASTParserError
from fs2.core.models.code_node import CodeNode, classify_node
from fs2.core.models.content_type import ContentType

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


logger = logging.getLogger(__name__)


# Extension to language mapping
# Per CF13: Static mapping with .h -> cpp default
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    # Python
    ".py": "python",
    ".pyi": "python",
    ".pyw": "python",
    # JavaScript/TypeScript
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    # Web
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    # Data formats
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    # Documentation
    ".md": "markdown",
    ".markdown": "markdown",
    ".rst": "rst",
    # Infrastructure
    ".tf": "hcl",
    ".tfvars": "hcl",
    # Systems
    ".c": "c",
    ".h": "cpp",  # Ambiguous, default to cpp per CF13
    ".hpp": "cpp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hh": "cpp",
    ".hxx": "cpp",
    # Modern languages
    ".rs": "rust",
    ".go": "go",
    ".cs": "csharp",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".swift": "swift",
    ".dart": "dart",
    # Scripting
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".fish": "fish",
    ".ps1": "powershell",
    ".rb": "ruby",
    ".lua": "lua",
    ".pl": "perl",
    ".php": "php",
    # Config
    ".ini": "ini",
    ".sql": "sql",
    ".graphql": "graphql",
    ".gql": "graphql",
    # Build
    ".make": "make",
    ".cmake": "cmake",
    # Functional
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hs": "haskell",
    ".ml": "ocaml",
    ".mli": "ocaml_interface",
    ".fs": "fsharp",
    ".fsi": "fsharp_signature",
    ".clj": "clojure",
    ".scm": "scheme",
    ".rkt": "racket",
    # Other
    ".nim": "nim",
    ".zig": "zig",
    ".v": "v",
    ".d": "d",
    ".r": "r",
    ".R": "r",
    ".jl": "julia",
}

# Filename to language mapping (for files without extensions)
FILENAME_TO_LANGUAGE: dict[str, str] = {
    "Dockerfile": "dockerfile",
    "Makefile": "make",
    "CMakeLists.txt": "cmake",
    "Jenkinsfile": "groovy",
    "Vagrantfile": "ruby",
    "Gemfile": "ruby",
    "Rakefile": "ruby",
    ".gitignore": "gitignore",
    ".gitattributes": "gitattributes",
}

# Languages that should be parsed into functions/classes/methods (whitelist)
# These are "real code" languages where extracting callable/type nodes is valuable.
# Used to determine ContentType.CODE vs ContentType.CONTENT.
CODE_LANGUAGES: set[str] = {
    # Systems programming
    "c", "cpp", "rust", "go", "zig", "d", "nim",
    # JVM
    "java", "kotlin", "scala", "groovy",
    # .NET
    "csharp", "fsharp",
    # Web
    "javascript", "typescript", "tsx", "php",
    # Scripting
    "python", "ruby", "perl", "lua",
    # Functional
    "haskell", "ocaml", "elixir", "erlang", "clojure", "scheme", "racket", "commonlisp",
    # Mobile
    "swift", "dart",
    # Scientific
    "r", "julia", "matlab", "fortran",
    # GPU/Shaders
    "cuda", "glsl", "hlsl", "wgsl",
    # Other
    "v",
}

# Languages with extractable structure (includes CODE + structured content).
# These get child node extraction (sections, blocks, callables, types).
EXTRACTABLE_LANGUAGES: set[str] = CODE_LANGUAGES | {
    # Documentation (sections/headings)
    "markdown", "rst",
    # Infrastructure (blocks)
    "hcl", "dockerfile",
}


class TreeSitterParser(ASTParser):
    """Production implementation of ASTParser using tree-sitter.

    Parses source files into CodeNode hierarchies with language detection.
    Uses tree-sitter-language-pack for grammar loading.

    Features:
    - Multi-language support via static extension mapping
    - Binary file detection (null bytes in first 8KB) per CF07
    - Depth-limited traversal (4 levels) per CF08
    - Graceful error handling per CF10

    Usage:
        ```python
        config = FakeConfigurationService(ScanConfig())
        parser = TreeSitterParser(config)

        language = parser.detect_language(Path("src/main.py"))  # "python"
        nodes = parser.parse(Path("src/main.py"))  # [CodeNode, ...]
        ```
    """

    def __init__(self, config: "ConfigurationService"):
        """Initialize with ConfigurationService registry.

        Args:
            config: ConfigurationService registry.
                    Parser will call config.require(ScanConfig) internally.

        Raises:
            MissingConfigurationError: If ScanConfig not in registry.
        """
        # Extract config internally (per Critical Finding 01)
        self._scan_config = config.require(ScanConfig)
        # Cache for loaded parsers by language
        self._parsers: dict[str, object] = {}

    def detect_language(self, file_path: Path) -> str | None:
        """Detect programming language from file extension or name.

        Uses static mapping of extensions to language names.
        Handles ambiguous extensions like .h (defaults to cpp).
        Handles filename matching for Dockerfile, Makefile, etc.

        Args:
            file_path: Path to check for language detection.

        Returns:
            Language name string (e.g., "python", "typescript", "markdown")
            or None if language cannot be determined.
        """
        # First check exact filename match
        filename = file_path.name
        if filename in FILENAME_TO_LANGUAGE:
            return FILENAME_TO_LANGUAGE[filename]

        # Check for Dockerfile variants (Dockerfile.dev, Dockerfile.prod, etc.)
        if filename.startswith("Dockerfile"):
            return "dockerfile"

        # Check extension (case-insensitive)
        suffix = file_path.suffix.lower()
        if suffix in EXTENSION_TO_LANGUAGE:
            return EXTENSION_TO_LANGUAGE[suffix]

        # Unknown
        return None

    def parse(self, file_path: Path) -> list[CodeNode]:
        """Parse a source file and extract CodeNode hierarchy.

        Transforms a source file into structural CodeNode elements
        (file, classes, functions, methods, etc.) using tree-sitter.

        Args:
            file_path: Path to the source file to parse.

        Returns:
            List of CodeNode representing structural elements.
            Returns empty list for binary files or unsupported languages.
            Minimum return is a file-level node for parseable files.

        Raises:
            ASTParserError: If file cannot be read or has encoding issues.
        """
        # Detect language
        language = self.detect_language(file_path)
        if language is None:
            logger.warning(f"Unknown language for {file_path}, skipping")
            return []

        # Read file content
        try:
            content = file_path.read_bytes()
        except PermissionError as e:
            raise ASTParserError(
                f"Permission denied reading {file_path}. "
                f"Check file permissions. Error: {e}"
            ) from e
        except OSError as e:
            raise ASTParserError(
                f"Cannot read {file_path}. Error: {e}"
            ) from e

        # Binary file detection per CF07 - check first 8KB for null bytes
        check_size = min(len(content), 8192)
        if b"\x00" in content[:check_size]:
            logger.warning(f"Binary file detected: {file_path}, skipping")
            return []

        # Decode content
        try:
            content_str = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content_str = content.decode("latin-1")
            except Exception as e:
                raise ASTParserError(
                    f"Cannot decode {file_path}. "
                    f"File encoding not supported. Error: {e}"
                ) from e

        # Get parser for language
        try:
            parser = get_parser(language)
        except Exception as e:
            logger.warning(
                f"No grammar available for {language}: {e}. "
                f"Returning file-only node for {file_path}"
            )
            # Return file-only node
            return self._create_file_only_node(file_path, language, content_str)

        # Parse content
        try:
            tree = parser.parse(content.encode("utf-8") if isinstance(content, str) else content)
        except Exception as e:
            raise ASTParserError(
                f"Failed to parse {file_path} as {language}. Error: {e}"
            ) from e

        # Calculate relative path for node IDs
        # Try to make path relative to current working directory
        try:
            rel_path = file_path.relative_to(Path.cwd())
        except ValueError:
            rel_path = file_path

        # Extract nodes
        nodes: list[CodeNode] = []

        # Determine content type at scan time
        content_type = ContentType.CODE if language in CODE_LANGUAGES else ContentType.CONTENT

        # Add file node
        lines = content_str.split("\n")
        file_node = CodeNode.create_file(
            file_path=str(rel_path),
            language=language,
            content_type=content_type,
            ts_kind=tree.root_node.type,
            start_byte=0,
            end_byte=len(content),
            start_line=1,
            end_line=len(lines),
            content=content_str,
            is_error=tree.root_node.type == "ERROR",
        )
        nodes.append(file_node)

        # Extract child nodes for languages with extractable structure
        # CODE languages get callables/types, structured content gets sections/blocks
        if language in EXTRACTABLE_LANGUAGES:
            self._extract_nodes(
                node=tree.root_node,
                file_path=str(rel_path),
                language=language,
                content_type=content_type,
                content=content_str,
                nodes=nodes,
                depth=1,
                parent_qualified_name=None,
                parent_node_id=file_node.node_id,
            )

        return nodes

    def _create_file_only_node(
        self, file_path: Path, language: str, content: str
    ) -> list[CodeNode]:
        """Create a file-only node when grammar is not available.

        Args:
            file_path: Path to the file.
            language: Detected language name.
            content: File content.

        Returns:
            List containing single file CodeNode.
        """
        try:
            rel_path = file_path.relative_to(Path.cwd())
        except ValueError:
            rel_path = file_path

        # Determine content type (grammar unavailable, but still classify by language)
        content_type = ContentType.CODE if language in CODE_LANGUAGES else ContentType.CONTENT

        lines = content.split("\n")
        return [
            CodeNode.create_file(
                file_path=str(rel_path),
                language=language,
                content_type=content_type,
                ts_kind="source_file",
                start_byte=0,
                end_byte=len(content.encode("utf-8")),
                start_line=1,
                end_line=len(lines),
                content=content,
            )
        ]

    def _extract_nodes(
        self,
        node,
        file_path: str,
        language: str,
        content_type: ContentType,
        content: str,
        nodes: list[CodeNode],
        depth: int,
        parent_qualified_name: str | None,
        parent_node_id: str | None,
    ) -> None:
        """Recursively extract named nodes from AST.

        Per CF03: Uses .children for O(n) traversal.
        Per CF08: Limited to depth 4.

        Args:
            node: Current tree-sitter node.
            file_path: Relative file path for node IDs.
            language: Language name.
            content_type: CODE or CONTENT classification.
            content: Full file content.
            nodes: List to append extracted CodeNodes to.
            depth: Current depth in tree.
            parent_qualified_name: Qualified name of parent node.
            parent_node_id: Node ID of parent for hierarchy edges.
        """
        # Depth limit per CF08
        if depth > 4:
            return

        # Process children (per CF03 - use .children not .child(i))
        for child in node.children:
            if not child.is_named:
                continue

            # Classify the node
            ts_kind = child.type
            category = classify_node(ts_kind)

            # Skip nodes that are too granular (don't create nodes, don't traverse)
            # These are implementation details, not meaningful code structures
            skip_entirely = {
                "lambda",  # Inline lambdas inside functions - not standalone
                "lambda_parameters",  # Just parameter names like 'n', 'x'
                "parameters",  # Function parameter lists
                "argument_list",  # Call arguments
            }
            if ts_kind in skip_entirely:
                continue

            # Skip container nodes that are just structural wrappers
            # These should be traversed but not create CodeNodes
            # Note: Python uses "block" for body wrappers, but HCL uses "block" for actual blocks
            container_types = {
                "module_body",  # Various languages
                "compound_statement",
                "declaration_list",
                "statement_block",
                "body",  # HCL/Python body wrapper
            }
            # Python "block" is a body wrapper, but HCL "block" is an actual block
            is_python_block = ts_kind == "block" and language == "python"
            if ts_kind in container_types or is_python_block:
                # Recurse into container without creating node
                self._extract_nodes(
                    node=child,
                    file_path=file_path,
                    language=language,
                    content_type=content_type,
                    content=content,
                    nodes=nodes,
                    depth=depth,
                    parent_qualified_name=parent_qualified_name,
                    parent_node_id=parent_node_id,
                )
                continue

            # Only extract meaningful structural elements
            if category not in ("type", "callable", "section", "block"):
                # Recurse into non-structural nodes to find nested structures
                self._extract_nodes(
                    node=child,
                    file_path=file_path,
                    language=language,
                    content_type=content_type,
                    content=content,
                    nodes=nodes,
                    depth=depth,
                    parent_qualified_name=parent_qualified_name,
                    parent_node_id=parent_node_id,
                )
                continue

            # Extract name from node
            name = self._extract_name(child, language)
            if name is None:
                # Anonymous node - use position-based ID per CF11
                name = f"@{child.start_point[0] + 1}"

            # Build qualified name
            if parent_qualified_name:
                qualified_name = f"{parent_qualified_name}.{name}"
            else:
                qualified_name = name

            # Extract content
            start_byte = child.start_byte
            end_byte = child.end_byte
            node_content = content[start_byte:end_byte] if start_byte < len(content) else ""

            # Extract signature (first line)
            signature = node_content.split("\n")[0] if node_content else ""

            # Create CodeNode using appropriate factory
            code_node = self._create_node(
                category=category,
                file_path=file_path,
                language=language,
                content_type=content_type,
                ts_kind=ts_kind,
                name=name,
                qualified_name=qualified_name,
                start_line=child.start_point[0] + 1,  # 1-indexed
                end_line=child.end_point[0] + 1,
                start_column=child.start_point[1],
                end_column=child.end_point[1],
                start_byte=start_byte,
                end_byte=end_byte,
                content=node_content,
                signature=signature,
                is_named=child.is_named,
                field_name=None,  # Would need index to use node.field_name_for_child(i)
                is_error=ts_kind == "ERROR",
                parent_node_id=parent_node_id,
            )
            nodes.append(code_node)

            # Recurse with updated qualified name and parent node ID
            self._extract_nodes(
                node=child,
                file_path=file_path,
                language=language,
                content_type=content_type,
                content=content,
                nodes=nodes,
                depth=depth + 1,
                parent_qualified_name=qualified_name,
                parent_node_id=code_node.node_id,
            )

    def _extract_name(self, node, language: str) -> str | None:
        """Extract name from a tree-sitter node.

        Different languages have different naming conventions.
        This method handles common patterns.

        Args:
            node: Tree-sitter node.
            language: Language name.

        Returns:
            Name string or None if name cannot be extracted.
        """
        # First, try to get name via field_name (tree-sitter's child_by_field_name)
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return name_node.text.decode("utf-8") if hasattr(name_node, "text") else None

        # Try common name patterns - look for identifier-like children
        for child in node.children:
            if child.type in ("identifier", "name", "type_identifier", "property_identifier"):
                return child.text.decode("utf-8") if hasattr(child, "text") else None

        # For markdown headings, extract heading content
        if "heading" in node.type.lower():
            # Find heading_content child
            for child in node.children:
                if "content" in child.type.lower() or child.type == "inline":
                    text = child.text.decode("utf-8") if hasattr(child, "text") else ""
                    return text.strip()

        # For HCL blocks (terraform), extract block type and labels
        if language == "hcl" and node.type == "block":
            parts = []
            for child in node.children:
                if child.type in ("identifier", "string_lit"):
                    text = child.text.decode("utf-8").strip('"') if hasattr(child, "text") else ""
                    if text:
                        parts.append(text)
            if parts:
                return ".".join(parts[:3])  # e.g., resource.aws_instance.web

        return None

    def _create_node(
        self,
        category: str,
        file_path: str,
        language: str,
        content_type: ContentType,
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
        is_named: bool,
        field_name: str | None,
        is_error: bool,
        parent_node_id: str | None,
    ) -> CodeNode:
        """Create appropriate CodeNode using factory methods.

        Args:
            category: Node category (type, callable, section, block).
            content_type: CODE or CONTENT classification.
            ... all other CodeNode fields
            parent_node_id: Node ID of parent for hierarchy edges.

        Returns:
            CodeNode created via appropriate factory method.
        """
        if category == "type":
            return CodeNode.create_type(
                file_path=file_path,
                language=language,
                content_type=content_type,
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
                signature=signature,
                is_named=is_named,
                field_name=field_name,
                is_error=is_error,
                parent_node_id=parent_node_id,
            )
        elif category == "callable":
            return CodeNode.create_callable(
                file_path=file_path,
                language=language,
                content_type=content_type,
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
                signature=signature,
                is_named=is_named,
                field_name=field_name,
                is_error=is_error,
                parent_node_id=parent_node_id,
            )
        elif category == "section":
            return CodeNode.create_section(
                file_path=file_path,
                language=language,
                content_type=content_type,
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
                signature=signature,
                is_named=is_named,
                field_name=field_name,
                is_error=is_error,
                parent_node_id=parent_node_id,
            )
        else:  # block
            return CodeNode.create_block(
                file_path=file_path,
                language=language,
                content_type=content_type,
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
                signature=signature,
                is_named=is_named,
                field_name=field_name,
                is_error=is_error,
                parent_node_id=parent_node_id,
            )
