#!/usr/bin/env python3
"""Detect fs2 node_id patterns in text files.

Scans text files for fs2 node_id patterns per Finding 10.
Pattern: (file|callable|type|class|method):path:name

Confidence: 1.0 (explicit fs2 references are highest confidence)

Usage:
    python 01_nodeid_detection.py <directory>
    python 01_nodeid_detection.py test_data/

Output:
    JSON to stdout with matches
"""

import json
import re
import sys
from pathlib import Path

# Node ID regex pattern per Finding 10
# Matches: file:path, callable:path:name, type:path:name, class:path:name, method:path:name
# The pattern captures: category:path:symbol (path can have / and .)
NODE_ID_PATTERN = re.compile(
    r'\b(file|callable|type|class|method):[\w./]+(?::[\w.]+)?\b'
)

# Text file extensions to scan
TEXT_EXTENSIONS = {
    '.md', '.txt', '.rst', '.adoc',
    '.py', '.ts', '.tsx', '.js', '.jsx',
    '.go', '.rs', '.java', '.c', '.cpp', '.h', '.hpp',
    '.yaml', '.yml', '.json', '.toml',
    '.sh', '.bash',
}


def scan_file(file_path: Path) -> list[dict]:
    """Scan a single file for node_id patterns.

    Args:
        file_path: Path to file

    Returns:
        List of dicts with match info
    """
    matches = []

    try:
        content = file_path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, PermissionError):
        return []

    for line_num, line in enumerate(content.split('\n'), start=1):
        for match in NODE_ID_PATTERN.finditer(line):
            node_id = match.group(0)
            # Parse the node_id
            parts = node_id.split(':')
            category = parts[0]
            path = parts[1] if len(parts) > 1 else None
            symbol = parts[2] if len(parts) > 2 else None

            matches.append({
                'file': str(file_path),
                'line': line_num,
                'column': match.start() + 1,
                'node_id': node_id,
                'category': category,
                'path': path,
                'symbol': symbol,
                'confidence': 1.0,  # Explicit node_ids have highest confidence
            })

    return matches


def scan_directory(directory: Path) -> dict:
    """Scan a directory for node_id patterns.

    Args:
        directory: Directory to scan

    Returns:
        Dict with results and metadata
    """
    all_matches = []
    files_scanned = 0
    files_with_matches = 0

    for file_path in directory.rglob('*'):
        if not file_path.is_file():
            continue
        if file_path.suffix not in TEXT_EXTENSIONS:
            continue

        files_scanned += 1
        matches = scan_file(file_path)

        if matches:
            files_with_matches += 1
            all_matches.extend(matches)

    return {
        'meta': {
            'directory': str(directory.resolve()),
            'files_scanned': files_scanned,
            'files_with_matches': files_with_matches,
            'total_matches': len(all_matches),
        },
        'matches': all_matches,
    }


def main():
    if len(sys.argv) < 2:
        print('Usage: python 01_nodeid_detection.py <directory>', file=sys.stderr)
        print('Example: python 01_nodeid_detection.py test_data/', file=sys.stderr)
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
