#!/usr/bin/env python3
"""Extract imports from source files using Tree-sitter.

Uses lib/parser.py, lib/queries.py, and lib/extractors.py to extract
imports from Python, TypeScript, and Go files.

Features per plan:
- Function-scoped import detection (Finding 04)
- Type-only import differentiation (Finding 02)
- Go dot/blank import handling (Finding 05)

Usage:
    python 02_import_extraction.py <directory>
    python 02_import_extraction.py /path/to/fixtures/samples

Output:
    JSON to stdout with imports grouped by file
"""

import json
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.parser import parse_file, detect_language
from lib.extractors import extract_imports
from lib.queries import get_supported_languages

# Code file extensions to scan
CODE_EXTENSIONS = {'.py', '.ts', '.tsx', '.js', '.jsx', '.go', '.java', '.rs', '.c', '.cpp', '.h', '.hpp', '.rb'}


def scan_file(file_path: Path) -> dict | None:
    """Scan a single file for imports.

    Args:
        file_path: Path to source file

    Returns:
        Dict with file info and imports, or None if not parseable
    """
    lang = detect_language(file_path)
    if not lang:
        return None

    if lang not in get_supported_languages():
        return None

    try:
        tree = parse_file(file_path, lang)
        imports = extract_imports(tree, lang)
    except Exception as e:
        return {
            'file': str(file_path),
            'language': lang,
            'error': str(e),
            'imports': [],
        }

    return {
        'file': str(file_path),
        'language': lang,
        'import_count': len(imports),
        'imports': imports,
    }


def scan_directory(directory: Path) -> dict:
    """Scan a directory for imports.

    Args:
        directory: Directory to scan

    Returns:
        Dict with results and metadata
    """
    all_files = []
    files_scanned = 0
    files_with_imports = 0
    total_imports = 0
    by_language = {}

    for file_path in sorted(directory.rglob('*')):
        if not file_path.is_file():
            continue
        if file_path.suffix not in CODE_EXTENSIONS:
            continue

        result = scan_file(file_path)
        if result is None:
            continue

        files_scanned += 1
        import_count = result.get('import_count', 0)

        if import_count > 0:
            files_with_imports += 1
            total_imports += import_count

        lang = result['language']
        if lang not in by_language:
            by_language[lang] = {'files': 0, 'imports': 0}
        by_language[lang]['files'] += 1
        by_language[lang]['imports'] += import_count

        all_files.append(result)

    return {
        'meta': {
            'directory': str(directory.resolve()),
            'files_scanned': files_scanned,
            'files_with_imports': files_with_imports,
            'total_imports': total_imports,
            'by_language': by_language,
        },
        'files': all_files,
    }


def main():
    if len(sys.argv) < 2:
        print('Usage: python 02_import_extraction.py <directory>', file=sys.stderr)
        print('Example: python 02_import_extraction.py /workspaces/flow_squared/tests/fixtures/samples', file=sys.stderr)
        sys.exit(1)

    directory = Path(sys.argv[1])

    if not directory.exists():
        print(f'Error: Directory not found: {directory}', file=sys.stderr)
        sys.exit(1)

    if not directory.is_dir():
        print(f'Error: Not a directory: {directory}', file=sys.stderr)
        sys.exit(1)

    results = scan_directory(directory)

    # Output JSON
    print(json.dumps(results, indent=2))

    return 0


if __name__ == '__main__':
    sys.exit(main())
