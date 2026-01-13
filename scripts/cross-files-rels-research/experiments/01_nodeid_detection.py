#!/usr/bin/env python3
"""Detect fs2 node_id patterns and raw filenames in text files.

Scans text files for:
1. fs2 node_id patterns per Finding 10: (file|callable|type|class|method):path:name
2. Raw filenames in prose: auth_handler.py, component.tsx, etc.

Confidence tiers:
- 1.0: Explicit node_id patterns (highest)
- 0.5: Raw filename in backticks (`auth_handler.py`)
- 0.4: Raw filename inline (auth_handler.py)

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

# Raw filename pattern - detects filenames like auth_handler.py, component.tsx
# Matches common code file extensions
# Optional backticks, quotes, or bare
RAW_FILENAME_PATTERN = re.compile(
    r'[`"\']?'  # Optional opening quote/backtick
    r'(\w[\w.-]*\.(?:py|ts|tsx|js|jsx|go|rs|java|c|cpp|h|hpp|rb|swift|kt|scala|cs|php|lua|sh|bash|zsh|yaml|yml|json|toml|xml|html|css|scss|sass|sql|graphql|proto|md))'
    r'[`"\']?',  # Optional closing quote/backtick
    re.IGNORECASE
)

# Extensions for code files we want to detect references to
CODE_FILE_EXTENSIONS = {
    '.py', '.ts', '.tsx', '.js', '.jsx',
    '.go', '.rs', '.java', '.c', '.cpp', '.h', '.hpp',
    '.rb', '.swift', '.kt', '.scala', '.cs', '.php', '.lua',
    '.sh', '.bash', '.zsh',
    '.yaml', '.yml', '.json', '.toml', '.xml',
    '.html', '.css', '.scss', '.sass',
    '.sql', '.graphql', '.proto', '.md',
}

# Text file extensions to scan
TEXT_EXTENSIONS = {
    '.md', '.txt', '.rst', '.adoc',
    '.py', '.ts', '.tsx', '.js', '.jsx',
    '.go', '.rs', '.java', '.c', '.cpp', '.h', '.hpp',
    '.yaml', '.yml', '.json', '.toml',
    '.sh', '.bash',
}


def scan_file(file_path: Path) -> list[dict]:
    """Scan a single file for node_id patterns and raw filenames.

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
        # Track positions already matched to avoid duplicates
        matched_positions = set()

        # 1. Explicit node_id patterns (highest priority, confidence 1.0)
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
                'match_type': 'node_id',
            })
            # Mark this range as matched
            matched_positions.update(range(match.start(), match.end()))

        # 2. Raw filename patterns (lower confidence)
        for match in RAW_FILENAME_PATTERN.finditer(line):
            # Skip if this position overlaps with a node_id match
            if any(pos in matched_positions for pos in range(match.start(), match.end())):
                continue

            filename = match.group(1)  # The captured filename without quotes
            full_match = match.group(0)

            # Determine confidence based on quoting
            # Backticks suggest intentional code reference
            if full_match.startswith('`') or full_match.startswith('"') or full_match.startswith("'"):
                confidence = 0.5
            else:
                confidence = 0.4

            matches.append({
                'file': str(file_path),
                'line': line_num,
                'column': match.start() + 1,
                'node_id': f'file:{filename}',  # Synthesize a file node_id
                'category': 'file',
                'path': filename,
                'symbol': None,
                'confidence': confidence,
                'match_type': 'raw_filename',
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
