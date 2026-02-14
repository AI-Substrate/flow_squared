#!/usr/bin/env python3
"""
Parse any tree-sitter supported file and output its AST as JSON.

Usage:
    python parse_to_json.py <file_path> [--output <output_path>] [--language <lang>]
    python parse_to_json.py sample_repo/python/sample.py
    python parse_to_json.py sample_repo/python/sample.py --output outputs/sample.py.ast.json
    python parse_to_json.py somefile.txt --language python
    python parse_to_json.py --all  # Process all sample files
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tree_sitter_language_pack import get_parser

# Script directory for resolving relative paths
SCRIPT_DIR = Path(__file__).parent
EXPLORATION_DIR = SCRIPT_DIR.parent
SAMPLE_REPO = EXPLORATION_DIR / "sample_repo"
OUTPUTS_DIR = EXPLORATION_DIR / "outputs"


# Extension to grammar mapping (P1-T18)
EXTENSION_TO_GRAMMAR: dict[str, str] = {
    # Programming languages
    '.py': 'python',
    '.pyw': 'python',
    '.js': 'javascript',
    '.mjs': 'javascript',
    '.cjs': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'tsx',
    '.go': 'go',
    '.rs': 'rust',
    '.cpp': 'cpp',
    '.cc': 'cpp',
    '.cxx': 'cpp',
    '.c++': 'cpp',
    '.hpp': 'cpp',
    '.hxx': 'cpp',
    '.h': 'cpp',  # Ambiguous, defaulting to cpp
    '.c': 'c',
    '.cs': 'csharp',
    '.dart': 'dart',
    '.java': 'java',
    '.kt': 'kotlin',
    '.kts': 'kotlin',
    '.rb': 'ruby',
    '.php': 'php',
    '.swift': 'swift',
    '.scala': 'scala',
    '.lua': 'lua',
    '.r': 'r',
    '.R': 'r',
    '.jl': 'julia',
    '.ex': 'elixir',
    '.exs': 'elixir',
    '.erl': 'erlang',
    '.hrl': 'erlang',
    '.hs': 'haskell',
    '.ml': 'ocaml',
    '.mli': 'ocaml_interface',
    '.fs': 'fsharp',
    '.fsi': 'fsharp_signature',
    '.nim': 'nim',
    '.zig': 'zig',
    '.v': 'v',
    '.odin': 'odin',

    # Markup and documentation
    '.md': 'markdown',
    '.markdown': 'markdown',
    '.rst': 'rst',
    '.tex': 'latex',
    '.html': 'html',
    '.htm': 'html',
    '.xml': 'xml',
    '.svg': 'xml',
    '.css': 'css',
    '.scss': 'scss',

    # Configuration
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.json': 'json',
    '.jsonc': 'json',
    '.toml': 'toml',
    '.ini': 'ini',
    '.cfg': 'ini',
    '.conf': 'ini',
    '.tf': 'hcl',
    '.tfvars': 'hcl',
    '.hcl': 'hcl',
    '.nix': 'nix',

    # Shell and scripting
    '.sh': 'bash',
    '.bash': 'bash',
    '.zsh': 'bash',
    '.fish': 'fish',
    '.ps1': 'powershell',
    '.psm1': 'powershell',

    # Database
    '.sql': 'sql',

    # Build and make
    '.make': 'make',
    '.cmake': 'cmake',

    # Other
    '.proto': 'proto',
    '.graphql': 'graphql',
    '.gql': 'graphql',
    '.vim': 'vim',
    '.el': 'elisp',
}

# Special filename mappings (no extension)
FILENAME_TO_GRAMMAR: dict[str, str] = {
    'Dockerfile': 'dockerfile',
    'dockerfile': 'dockerfile',
    'Makefile': 'make',
    'makefile': 'make',
    'GNUmakefile': 'make',
    'CMakeLists.txt': 'cmake',
    '.gitignore': 'gitignore',
    '.gitattributes': 'gitattributes',
    'requirements.txt': 'requirements',
    'Cargo.toml': 'toml',
    'pyproject.toml': 'toml',
    'package.json': 'json',
    'tsconfig.json': 'json',
}


def detect_language(file_path: Path) -> str | None:
    """Detect the grammar name from file path."""
    # Check special filenames first
    if file_path.name in FILENAME_TO_GRAMMAR:
        return FILENAME_TO_GRAMMAR[file_path.name]

    # Check extension
    suffix = file_path.suffix.lower()
    if suffix in EXTENSION_TO_GRAMMAR:
        return EXTENSION_TO_GRAMMAR[suffix]

    return None


def node_to_dict(node, source: bytes, include_text: bool = True) -> dict[str, Any]:
    """
    Convert a tree-sitter node to a dictionary representation.

    Includes all node metadata for exploration purposes.
    """
    result: dict[str, Any] = {
        'type': node.type,
        'is_named': node.is_named,
        'start_byte': node.start_byte,
        'end_byte': node.end_byte,
        'start_point': {
            'row': node.start_point[0],
            'column': node.start_point[1],
        },
        'end_point': {
            'row': node.end_point[0],
            'column': node.end_point[1],
        },
    }

    # Include error flags for debugging
    if node.has_error:
        result['has_error'] = True
    if node.is_error:
        result['is_error'] = True
    if node.is_missing:
        result['is_missing'] = True

    # Include field name if this node is a field child
    # (This is set by the parent during traversal)

    # Include text for leaf nodes or short nodes
    if include_text:
        text_length = node.end_byte - node.start_byte
        if text_length <= 200:  # Only include text for reasonably short nodes
            import contextlib
            with contextlib.suppress(Exception):
                result['text'] = source[node.start_byte:node.end_byte].decode('utf-8', errors='replace')

    # Include children with field names
    children = []
    for i, child in enumerate(node.children):
        child_dict = node_to_dict(child, source, include_text)

        # Try to get field name for this child
        field_name = node.field_name_for_child(i)
        if field_name:
            child_dict['field_name'] = field_name

        children.append(child_dict)

    if children:
        result['children'] = children
        result['child_count'] = len(children)
        result['named_child_count'] = node.named_child_count

    return result


def make_relative_path(file_path: Path) -> str:
    """Convert absolute path to relative path from exploration directory."""
    try:
        return str(file_path.relative_to(EXPLORATION_DIR))
    except ValueError:
        # If not under EXPLORATION_DIR, return as-is
        return str(file_path)


def parse_file(file_path: Path, language: str | None = None) -> dict[str, Any]:
    """Parse a file and return the AST as a dictionary."""
    # Detect or use provided language
    if language is None:
        language = detect_language(file_path)
        if language is None:
            raise ValueError(f"Could not detect language for {file_path}. Use --language to specify.")

    # Read source
    source = file_path.read_bytes()

    # Get parser
    try:
        parser = get_parser(language)
    except Exception as e:
        raise ValueError(f"Failed to get parser for language '{language}': {e}") from e

    # Parse
    tree = parser.parse(source)

    # Convert to dict
    ast_dict = node_to_dict(tree.root_node, source)

    # Add metadata with relative path
    return {
        'file': make_relative_path(file_path),
        'language': language,
        'source_bytes': len(source),
        'source_lines': source.count(b'\n') + 1,
        'root': ast_dict,
    }


def get_sample_files() -> list[Path]:
    """Get all sample files from sample_repo directory."""
    sample_files = []

    # Walk through sample_repo to find all parseable files
    for subdir in SAMPLE_REPO.iterdir():
        if not subdir.is_dir():
            continue
        for file in subdir.iterdir():
            if file.is_file() and detect_language(file) is not None:
                sample_files.append(file)

    return sorted(sample_files)


def clear_ast_outputs():
    """Remove all *.ast.json files from outputs directory."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    for f in OUTPUTS_DIR.glob("*.ast.json"):
        f.unlink()
        print(f"Removed: {f.name}", file=sys.stderr)


def process_all_samples(compact: bool = False):
    """Process all sample files and generate .ast.json outputs."""
    # Clear existing AST files
    print("Clearing existing *.ast.json files...", file=sys.stderr)
    clear_ast_outputs()

    sample_files = get_sample_files()
    print(f"\nProcessing {len(sample_files)} sample files...\n", file=sys.stderr)

    indent = None if compact else 2

    for file_path in sample_files:
        try:
            result = parse_file(file_path)

            # Output filename: sample.py -> sample.py.ast.json
            output_name = f"{file_path.name}.ast.json"
            output_path = OUTPUTS_DIR / output_name

            json_output = json.dumps(result, indent=indent, ensure_ascii=False)
            output_path.write_text(json_output, encoding='utf-8')

            print(f"  {file_path.name} -> {output_name}", file=sys.stderr)
        except Exception as e:
            print(f"  ERROR: {file_path.name}: {e}", file=sys.stderr)

    print(f"\nDone. Output written to {OUTPUTS_DIR}/", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description='Parse a file using tree-sitter and output AST as JSON.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s sample_repo/python/sample.py
    %(prog)s sample_repo/python/sample.py --output outputs/sample.py.ast.json
    %(prog)s myfile.txt --language python
    %(prog)s --all  # Process all sample files
    %(prog)s --list-languages
        """,
    )
    parser.add_argument('file', nargs='?', help='File to parse')
    parser.add_argument('-o', '--output', help='Output file (default: stdout)')
    parser.add_argument('-l', '--language', help='Override language detection')
    parser.add_argument('--all', action='store_true',
                       help='Process all sample files in sample_repo/')
    parser.add_argument('--list-languages', action='store_true',
                       help='List supported file extensions')
    parser.add_argument('--compact', action='store_true',
                       help='Output compact JSON (no indentation)')

    args = parser.parse_args()

    if args.list_languages:
        print("Supported extensions:")
        for ext, lang in sorted(EXTENSION_TO_GRAMMAR.items()):
            print(f"  {ext:12} -> {lang}")
        print("\nSpecial filenames:")
        for name, lang in sorted(FILENAME_TO_GRAMMAR.items()):
            print(f"  {name:20} -> {lang}")
        return

    if args.all:
        process_all_samples(compact=args.compact)
        return

    if not args.file:
        parser.print_help()
        sys.exit(1)

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    try:
        result = parse_file(file_path, args.language)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Output
    indent = None if args.compact else 2
    json_output = json.dumps(result, indent=indent, ensure_ascii=False)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_output, encoding='utf-8')
        print(f"Output written to {output_path}", file=sys.stderr)
    else:
        print(json_output)


if __name__ == '__main__':
    main()
