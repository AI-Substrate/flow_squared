#!/usr/bin/env python3
"""Extract function/method calls from source files using Tree-sitter.

Uses lib/parser.py, lib/queries.py, and lib/extractors.py to extract
calls from Python, TypeScript, and Go files.

Features per plan:
- Constructor detection with language-specific confidence (didyouknow #3)
- Self/this method call detection (Finding 03)
- Receiver tracking for method calls

Usage:
    python 03_call_extraction.py <directory>
    python 03_call_extraction.py /path/to/fixtures/samples

Output:
    JSON to stdout with calls grouped by file
"""

import json
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.parser import parse_file, detect_language
from lib.extractors import extract_calls
from lib.queries import get_supported_languages

# Code file extensions to scan
CODE_EXTENSIONS = {'.py', '.ts', '.tsx', '.js', '.jsx', '.go', '.java', '.rs', '.c', '.cpp', '.h', '.hpp', '.rb'}


def scan_file(file_path: Path) -> dict | None:
    """Scan a single file for function calls.

    Args:
        file_path: Path to source file

    Returns:
        Dict with file info and calls, or None if not parseable
    """
    lang = detect_language(file_path)
    if not lang:
        return None

    if lang not in get_supported_languages():
        return None

    try:
        tree = parse_file(file_path, lang)
        calls = extract_calls(tree, lang)
    except Exception as e:
        return {
            'file': str(file_path),
            'language': lang,
            'error': str(e),
            'calls': [],
        }

    # Count constructors
    constructor_count = sum(1 for c in calls if c.get('is_constructor'))
    self_call_count = sum(1 for c in calls if c.get('is_self_call'))

    return {
        'file': str(file_path),
        'language': lang,
        'call_count': len(calls),
        'constructor_count': constructor_count,
        'self_call_count': self_call_count,
        'calls': calls,
    }


def scan_directory(directory: Path) -> dict:
    """Scan a directory for function calls.

    Args:
        directory: Directory to scan

    Returns:
        Dict with results and metadata
    """
    all_files = []
    files_scanned = 0
    files_with_calls = 0
    total_calls = 0
    total_constructors = 0
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
        call_count = result.get('call_count', 0)
        constructor_count = result.get('constructor_count', 0)

        if call_count > 0:
            files_with_calls += 1
            total_calls += call_count
            total_constructors += constructor_count

        lang = result['language']
        if lang not in by_language:
            by_language[lang] = {'files': 0, 'calls': 0, 'constructors': 0}
        by_language[lang]['files'] += 1
        by_language[lang]['calls'] += call_count
        by_language[lang]['constructors'] += constructor_count

        all_files.append(result)

    return {
        'meta': {
            'directory': str(directory.resolve()),
            'files_scanned': files_scanned,
            'files_with_calls': files_with_calls,
            'total_calls': total_calls,
            'total_constructors': total_constructors,
            'by_language': by_language,
        },
        'files': all_files,
    }


def main():
    if len(sys.argv) < 2:
        print('Usage: python 03_call_extraction.py <directory>', file=sys.stderr)
        print('Example: python 03_call_extraction.py /workspaces/flow_squared/tests/fixtures/samples', file=sys.stderr)
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
