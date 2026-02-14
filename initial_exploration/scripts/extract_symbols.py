#!/usr/bin/env python3
"""
Extract symbols from raw tree-sitter AST JSON and output canonical symbols.json format.

Usage:
    python extract_symbols.py <ast_file> [--output <output_path>]
    python extract_symbols.py outputs/sample.py.ast.json
    python extract_symbols.py --all  # Process all .ast.json files
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Script directory for resolving relative paths
SCRIPT_DIR = Path(__file__).parent
EXPLORATION_DIR = SCRIPT_DIR.parent
OUTPUTS_DIR = EXPLORATION_DIR / "outputs"
SAMPLE_REPO = EXPLORATION_DIR / "sample_repo"

# Format family mappings
FORMAT_FAMILIES = {
    'python': 'code_oop',
    'javascript': 'code_oop',
    'typescript': 'code_oop',
    'tsx': 'code_oop',
    'dart': 'code_oop',
    'csharp': 'code_oop',
    'java': 'code_oop',
    'go': 'code_systems',
    'rust': 'code_systems',
    'cpp': 'code_systems',
    'c': 'code_systems',
    'markdown': 'markup',
    'yaml': 'config_kv',
    'json': 'config_kv',
    'toml': 'config_kv',
    'hcl': 'iac',
    'dockerfile': 'iac',
    'sql': 'query',
    'bash': 'shell',
}

# Node types that indicate symbol boundaries for code formats
CODE_SYMBOL_PATTERNS = [
    # Classes and types
    r'class_definition',
    r'class_declaration',
    r'class_specifier',
    r'struct_item',
    r'struct_declaration',
    r'struct_specifier',
    r'interface_declaration',
    r'enum_definition',
    r'enum_declaration',
    r'enum_specifier',
    r'type_declaration',
    r'type_alias_declaration',
    # Functions and methods
    r'function_definition',
    r'function_declaration',
    r'function_item',
    r'method_definition',
    r'method_declaration',
    r'impl_item',
]


def get_category(node_type: str, language: str) -> str | None:
    """Determine the category for a node type."""
    # File-level containers
    if node_type in ('module', 'program', 'source_file', 'translation_unit',
                     'compilation_unit', 'document', 'config_file', 'stream'):
        return 'file'

    # Markdown headings
    if node_type == 'atx_heading':
        return 'section'

    # HCL/Terraform blocks
    if language == 'hcl' and node_type == 'block':
        return 'block'

    # Dockerfile instructions
    if language == 'dockerfile' and node_type == 'from_instruction':
        return 'block'

    # Check code symbol patterns
    for pattern in CODE_SYMBOL_PATTERNS:
        if re.match(pattern, node_type):
            # Determine if it's a type or callable
            if any(x in node_type for x in ('class', 'struct', 'interface', 'enum', 'type')):
                return 'type'
            if any(x in node_type for x in ('function', 'method', 'impl')):
                return 'callable'
            return 'definition'

    return None


def extract_name(node: dict, source_bytes: bytes) -> str | None:
    """Extract the name from a node using various strategies."""
    # Strategy 1: Look for a child with field_name == "name"
    if 'children' in node:
        for child in node['children']:
            if child.get('field_name') == 'name':
                if 'text' in child:
                    return child['text']
                # For identifier nodes, extract from source
                return source_bytes[child['start_byte']:child['end_byte']].decode('utf-8', errors='replace')

    # Strategy 2: Look for type_identifier (Go type declarations)
    if 'children' in node:
        for child in node['children']:
            if child.get('type') == 'type_identifier' and child.get('is_named'):
                if 'text' in child:
                    return child['text']
                return source_bytes[child['start_byte']:child['end_byte']].decode('utf-8', errors='replace')

    # Strategy 3: Look for type_spec or type_alias child (Go)
    if 'children' in node:
        for child in node['children']:
            if child.get('type') in ('type_spec', 'type_alias'):
                result = extract_name(child, source_bytes)
                if result:
                    return result

    # Strategy 4: Look for first identifier child
    if 'children' in node:
        for child in node['children']:
            if child.get('type') == 'identifier' and child.get('is_named'):
                if 'text' in child:
                    return child['text']
                return source_bytes[child['start_byte']:child['end_byte']].decode('utf-8', errors='replace')

    # Strategy 5: For declarators (C/C++), recurse
    if 'children' in node:
        for child in node['children']:
            if child.get('field_name') == 'declarator':
                return extract_name(child, source_bytes)

    # Strategy 4: For Markdown headings, extract heading content
    if node.get('type') == 'atx_heading' and 'children' in node:
        for child in node['children']:
            if child.get('type') == 'heading_content':
                return source_bytes[child['start_byte']:child['end_byte']].decode('utf-8', errors='replace').strip()
            # Fallback: inline content
            if child.get('type') == 'inline':
                return source_bytes[child['start_byte']:child['end_byte']].decode('utf-8', errors='replace').strip()

    # Strategy 5: For HCL blocks, combine type and labels
    if node.get('type') == 'block' and 'children' in node:
        parts = []
        for child in node['children']:
            if child.get('type') == 'identifier':
                text = child.get('text') or source_bytes[child['start_byte']:child['end_byte']].decode('utf-8', errors='replace')
                parts.append(text)
            elif child.get('type') == 'string_lit':
                text = child.get('text') or source_bytes[child['start_byte']:child['end_byte']].decode('utf-8', errors='replace')
                # Remove quotes
                text = text.strip('"\'')
                parts.append(text)
        if parts:
            return '.'.join(parts)

    # Strategy 6: For Dockerfile FROM, extract image name
    if node.get('type') == 'from_instruction' and 'children' in node:
        for child in node['children']:
            if child.get('type') == 'image_spec':
                return source_bytes[child['start_byte']:child['end_byte']].decode('utf-8', errors='replace')

    return None


def extract_signature(node: dict, source_bytes: bytes) -> str | None:
    """Extract the signature (first line(s) of declaration)."""
    start = node['start_byte']
    end = node['end_byte']
    full_text = source_bytes[start:end].decode('utf-8', errors='replace')

    # Get first line or up to opening brace/colon
    lines = full_text.split('\n')
    if not lines:
        return None

    first_line = lines[0].strip()

    # For multi-line signatures, include up to the body start
    # Look for common body markers
    for marker in ['{', ':', 'do', 'then']:
        if marker in first_line:
            # Include up to and including the marker
            idx = first_line.index(marker)
            return first_line[:idx + len(marker)].strip()

    # If first line is short, it's probably the full signature
    if len(first_line) <= 200:
        return first_line

    return first_line[:200] + '...'


def extract_content(node: dict, source_bytes: bytes) -> str:
    """Extract the full source content for a node."""
    start = node['start_byte']
    end = node['end_byte']
    return source_bytes[start:end].decode('utf-8', errors='replace')


def get_heading_level(node: dict, source_bytes: bytes) -> int:
    """Get the heading level for a Markdown atx_heading."""
    if 'children' in node:
        for child in node['children']:
            if child.get('type') == 'atx_h1_marker':
                return 1
            elif child.get('type') == 'atx_h2_marker':
                return 2
            elif child.get('type') == 'atx_h3_marker':
                return 3
            elif child.get('type') == 'atx_h4_marker':
                return 4
            elif child.get('type') == 'atx_h5_marker':
                return 5
            elif child.get('type') == 'atx_h6_marker':
                return 6

    # Fallback: count # characters
    content = source_bytes[node['start_byte']:node['end_byte']].decode('utf-8', errors='replace')
    match = re.match(r'^(#+)', content)
    if match:
        return len(match.group(1))
    return 1


def build_symbol(
    node: dict,
    source_bytes: bytes,
    file_path: str,
    language: str,
    parent_qualified_name: str | None = None,
) -> dict | None:
    """Build a symbol object from an AST node."""
    category = get_category(node['type'], language)
    if category is None:
        return None

    name = extract_name(node, source_bytes)
    if name is None:
        # Use type + position as fallback name
        name = f"{node['type']}_{node['start_point']['row'] + 1}"

    # Build qualified name
    if parent_qualified_name:
        qualified_name = f"{parent_qualified_name}.{name}"
    else:
        qualified_name = name

    # Build the symbol
    symbol = {
        'id': f"{category}:{file_path}:{qualified_name}",
        'category': category,
        'kind': node['type'],
        'name': name,
        'qualified_name': qualified_name,
        'signature': extract_signature(node, source_bytes),
        'doc': None,  # Deferred
        'location': {
            'start_line': node['start_point']['row'] + 1,  # 1-indexed
            'end_line': node['end_point']['row'] + 1,
            'start_byte': node['start_byte'],
            'end_byte': node['end_byte'],
        },
        'content': extract_content(node, source_bytes),
        'children': [],
    }

    return symbol


def walk_ast(
    node: dict,
    source_bytes: bytes,
    file_path: str,
    language: str,
    parent_qualified_name: str | None = None,
    collected_symbols: list | None = None,
    is_root: bool = False,
) -> list[dict]:
    """
    Walk the AST and extract symbols.

    For nested structures, symbols are built hierarchically with children.
    """
    if collected_symbols is None:
        collected_symbols = []

    # Skip the root node (file-level container) - it's handled separately
    category = get_category(node['type'], language)
    if is_root or category == 'file':
        # Just process children, don't create a symbol
        if 'children' in node:
            for child in node['children']:
                walk_ast(
                    child,
                    source_bytes,
                    file_path,
                    language,
                    parent_qualified_name=parent_qualified_name,
                    collected_symbols=collected_symbols,
                    is_root=False,
                )
        return collected_symbols

    # Try to build a symbol for this node
    symbol = build_symbol(node, source_bytes, file_path, language, parent_qualified_name)

    if symbol:
        # This node is a symbol - process its children for nested symbols
        if 'children' in node:
            child_symbols = []
            for child in node['children']:
                nested = walk_ast(
                    child,
                    source_bytes,
                    file_path,
                    language,
                    parent_qualified_name=symbol['qualified_name'],
                    collected_symbols=[],
                    is_root=False,
                )
                child_symbols.extend(nested)

            symbol['children'] = child_symbols

        collected_symbols.append(symbol)
    else:
        # Not a symbol - continue walking children
        if 'children' in node:
            for child in node['children']:
                walk_ast(
                    child,
                    source_bytes,
                    file_path,
                    language,
                    parent_qualified_name=parent_qualified_name,
                    collected_symbols=collected_symbols,
                    is_root=False,
                )

    return collected_symbols


def process_markdown(
    root: dict,
    source_bytes: bytes,
    file_path: str,
) -> dict:
    """
    Special processing for Markdown to create nested section hierarchy.

    Markdown headings are flat in the AST, so we need to build the hierarchy
    based on heading levels.
    """
    # First, collect all headings with their levels and positions
    headings = []

    def find_headings(node: dict):
        if node.get('type') == 'atx_heading':
            level = get_heading_level(node, source_bytes)
            name = extract_name(node, source_bytes) or f"heading_{node['start_point']['row'] + 1}"
            headings.append({
                'node': node,
                'level': level,
                'name': name,
                'start_byte': node['start_byte'],
                'end_byte': node['end_byte'],
            })
        if 'children' in node:
            for child in node['children']:
                find_headings(child)

    find_headings(root)

    if not headings:
        # No headings - return file-level symbol only
        return build_file_symbol(root, source_bytes, file_path, 'markdown', [])

    # Calculate content ranges for each heading (up to next heading of same or higher level)
    for i, heading in enumerate(headings):
        # Find end of this section's content
        if i + 1 < len(headings):
            heading['content_end'] = headings[i + 1]['start_byte']
        else:
            heading['content_end'] = root['end_byte']

    # Build nested structure based on levels
    def build_section_tree(headings: list, start_idx: int, parent_level: int, parent_qname: str) -> tuple[list, int]:
        sections = []
        i = start_idx

        while i < len(headings):
            h = headings[i]
            if h['level'] <= parent_level and parent_level > 0:
                # This heading is at same or higher level than parent - return
                break

            # Build qualified name
            qname = f"{parent_qname}/{h['name']}" if parent_qname else h['name']

            # Get content for this section
            content_start = h['start_byte']
            content_end = h['content_end']
            content = source_bytes[content_start:content_end].decode('utf-8', errors='replace')

            section = {
                'id': f"section:{file_path}:{qname}",
                'category': 'section',
                'kind': 'atx_heading',
                'name': h['name'],
                'qualified_name': qname,
                'signature': source_bytes[h['start_byte']:h['end_byte']].decode('utf-8', errors='replace').split('\n')[0],
                'doc': None,
                'location': {
                    'start_line': h['node']['start_point']['row'] + 1,
                    'end_line': h['node']['end_point']['row'] + 1,
                    'start_byte': content_start,
                    'end_byte': content_end,
                },
                'content': content,
                'children': [],
            }

            # Find child sections (higher level numbers = lower in hierarchy)
            i += 1
            children, i = build_section_tree(headings, i, h['level'], qname)
            section['children'] = children

            sections.append(section)

        return sections, i

    child_sections, _ = build_section_tree(headings, 0, 0, '')

    return build_file_symbol(root, source_bytes, file_path, 'markdown', child_sections)


def build_file_symbol(
    root: dict,
    source_bytes: bytes,
    file_path: str,
    language: str,
    children: list,
) -> dict:
    """Build the root file-level symbol."""
    file_name = Path(file_path).name

    return {
        'id': f"file:{file_path}",
        'category': 'file',
        'kind': root['type'],
        'name': file_name,
        'qualified_name': file_name,
        'signature': None,
        'doc': None,
        'location': {
            'start_line': root['start_point']['row'] + 1,
            'end_line': root['end_point']['row'] + 1,
            'start_byte': root['start_byte'],
            'end_byte': root['end_byte'],
        },
        'content': source_bytes.decode('utf-8', errors='replace'),
        'children': children,
    }


def make_relative_path(file_path: str) -> str:
    """Convert absolute path to relative path from exploration directory."""
    path = Path(file_path)
    try:
        return str(path.relative_to(EXPLORATION_DIR))
    except ValueError:
        # If not under EXPLORATION_DIR, return as-is
        return file_path


def extract_symbols(ast_data: dict, source_bytes: bytes) -> dict:
    """
    Main entry point: extract symbols from raw AST.

    Returns the canonical symbols.json structure.
    """
    file_path = make_relative_path(ast_data['file'])
    language = ast_data['language']
    root = ast_data['root']

    format_family = FORMAT_FAMILIES.get(language, 'unknown')

    # Special handling for Markdown
    if language == 'markdown':
        root_symbol = process_markdown(root, source_bytes, file_path)
    else:
        # Standard processing for code and config files
        child_symbols = walk_ast(root, source_bytes, file_path, language, is_root=True)
        root_symbol = build_file_symbol(root, source_bytes, file_path, language, child_symbols)

    return {
        'version': '1.0',
        'source': {
            'file': file_path,
            'language': language,
            'format_family': format_family,
        },
        'root': root_symbol,
    }


def get_source_file(ast_file: Path) -> Path | None:
    """Find the original source file for an AST file."""
    # ast_file: outputs/sample.py.ast.json -> sample_repo/*/sample.py
    # Extract original filename by removing .ast.json
    original_name = ast_file.name.replace('.ast.json', '')

    # Search in sample_repo
    for subdir in SAMPLE_REPO.iterdir():
        if not subdir.is_dir():
            continue
        candidate = subdir / original_name
        if candidate.exists():
            return candidate

    return None


def clear_symbols_outputs():
    """Remove all *.symbols.json files from outputs directory."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    for f in OUTPUTS_DIR.glob("*.symbols.json"):
        f.unlink()
        print(f"Removed: {f.name}", file=sys.stderr)


def process_all_asts(compact: bool = False):
    """Process all .ast.json files and generate .symbols.json outputs."""
    # Clear existing symbols files
    print("Clearing existing *.symbols.json files...", file=sys.stderr)
    clear_symbols_outputs()

    ast_files = sorted(OUTPUTS_DIR.glob("*.ast.json"))
    print(f"\nProcessing {len(ast_files)} AST files...\n", file=sys.stderr)

    indent = None if compact else 2

    for ast_file in ast_files:
        try:
            # Load AST
            ast_data = json.loads(ast_file.read_text(encoding='utf-8'))

            # Find source file
            source_file = get_source_file(ast_file)
            if source_file is None:
                print(f"  ERROR: {ast_file.name}: Could not find source file", file=sys.stderr)
                continue

            source_bytes = source_file.read_bytes()

            # Extract symbols
            symbols_data = extract_symbols(ast_data, source_bytes)

            # Output filename: sample.py.ast.json -> sample.py.symbols.json
            output_name = ast_file.name.replace('.ast.json', '.symbols.json')
            output_path = OUTPUTS_DIR / output_name

            json_output = json.dumps(symbols_data, indent=indent, ensure_ascii=False)
            output_path.write_text(json_output, encoding='utf-8')

            # Count symbols
            def count_symbols(node):
                count = 1
                for child in node.get('children', []):
                    count += count_symbols(child)
                return count

            symbol_count = count_symbols(symbols_data['root']) - 1  # Exclude root file node

            print(f"  {ast_file.name} -> {output_name} ({symbol_count} symbols)", file=sys.stderr)
        except Exception as e:
            print(f"  ERROR: {ast_file.name}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

    print(f"\nDone. Output written to {OUTPUTS_DIR}/", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description='Extract symbols from raw tree-sitter AST JSON.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s outputs/sample.py.ast.json
    %(prog)s outputs/sample.py.ast.json --output outputs/sample.py.symbols.json
    %(prog)s --all  # Process all .ast.json files
        """,
    )
    parser.add_argument('file', nargs='?', help='AST JSON file to process')
    parser.add_argument('-o', '--output', help='Output file (default: stdout)')
    parser.add_argument('--all', action='store_true',
                       help='Process all .ast.json files in outputs/')
    parser.add_argument('--compact', action='store_true',
                       help='Output compact JSON (no indentation)')

    args = parser.parse_args()

    if args.all:
        process_all_asts(compact=args.compact)
        return

    if not args.file:
        parser.print_help()
        sys.exit(1)

    ast_file = Path(args.file)
    if not ast_file.exists():
        print(f"Error: File not found: {ast_file}", file=sys.stderr)
        sys.exit(1)

    # Load AST
    ast_data = json.loads(ast_file.read_text(encoding='utf-8'))

    # Find source file
    source_file = get_source_file(ast_file)
    if source_file is None:
        # Try to use file path from AST data
        source_path = Path(ast_data['file'])
        if source_path.exists():
            source_file = source_path
        else:
            print(f"Error: Could not find source file for {ast_file}", file=sys.stderr)
            sys.exit(1)

    source_bytes = source_file.read_bytes()

    # Extract symbols
    symbols_data = extract_symbols(ast_data, source_bytes)

    # Output
    indent = None if args.compact else 2
    json_output = json.dumps(symbols_data, indent=indent, ensure_ascii=False)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_output, encoding='utf-8')
        print(f"Output written to {output_path}", file=sys.stderr)
    else:
        print(json_output)


if __name__ == '__main__':
    main()
