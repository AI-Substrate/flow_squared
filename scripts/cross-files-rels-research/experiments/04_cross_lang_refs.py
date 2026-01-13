#!/usr/bin/env python3
"""Detect cross-language file references in Dockerfiles and YAML files.

Scans Dockerfiles for COPY/ADD commands and YAML files for file path references.
These represent cross-language relationships where configuration files reference
code files.

Confidence: 0.7 (cross-language references are lower confidence than imports)

Usage:
    python 04_cross_lang_refs.py <directory>
    python 04_cross_lang_refs.py /workspaces/flow_squared/tests/fixtures/samples/

Output:
    JSON to stdout with detected cross-file references
"""

import json
import re
import sys
from pathlib import Path

# Patterns for Dockerfile commands that reference files
DOCKERFILE_PATTERNS = [
    # COPY source dest (may include --from or --chown flags)
    re.compile(r'COPY\s+(?:--\w+(?:=\S+)?\s+)*(\S+)\s+\S+'),
    # ADD source dest
    re.compile(r'ADD\s+(?:--\w+(?:=\S+)?\s+)*(\S+)\s+\S+'),
]

# File extensions that indicate a Python file reference
PYTHON_FILE_PATTERN = re.compile(r'[\w./]+\.py\b')

# Confidence for cross-language references
CONF_CROSS_LANG = 0.7


def scan_dockerfile(file_path: Path) -> list[dict]:
    """Scan a Dockerfile for file references.

    Args:
        file_path: Path to Dockerfile

    Returns:
        List of dicts with reference info
    """
    refs = []

    try:
        content = file_path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, PermissionError):
        return []

    for line_num, line in enumerate(content.split('\n'), start=1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith('#'):
            continue

        # Check for COPY/ADD commands
        for pattern in DOCKERFILE_PATTERNS:
            match = pattern.search(line)
            if match:
                source_path = match.group(1)

                # Check if it references a Python file
                py_match = PYTHON_FILE_PATTERN.search(source_path)
                if py_match:
                    refs.append({
                        'source_file': str(file_path),
                        'line': line_num,
                        'command': line.strip().split()[0],
                        'target_path': source_path,
                        'ref_type': 'copy',
                        'confidence': CONF_CROSS_LANG,
                    })

    return refs


def scan_yaml_file(file_path: Path) -> list[dict]:
    """Scan a YAML file for Python file references.

    Args:
        file_path: Path to YAML file

    Returns:
        List of dicts with reference info
    """
    refs = []

    try:
        content = file_path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, PermissionError):
        return []

    for line_num, line in enumerate(content.split('\n'), start=1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith('#'):
            continue

        # Check for Python file references
        for match in PYTHON_FILE_PATTERN.finditer(line):
            py_path = match.group(0)
            # Skip if it's in a URL or common non-file context
            if '://' in line or py_path.startswith('pip'):
                continue

            refs.append({
                'source_file': str(file_path),
                'line': line_num,
                'target_path': py_path,
                'ref_type': 'yaml_ref',
                'confidence': CONF_CROSS_LANG,
            })

    return refs


def scan_directory(directory: Path) -> dict:
    """Scan a directory for cross-language file references.

    Args:
        directory: Directory to scan

    Returns:
        Dict with results and metadata
    """
    all_refs = []
    files_scanned = 0
    files_with_refs = 0

    # Scan Dockerfiles
    for file_path in directory.rglob('*'):
        if not file_path.is_file():
            continue

        # Check for Dockerfile (various naming conventions)
        if file_path.name == 'Dockerfile' or file_path.name.startswith('Dockerfile.'):
            files_scanned += 1
            refs = scan_dockerfile(file_path)
            if refs:
                files_with_refs += 1
                all_refs.extend(refs)
            continue

        # Check for YAML files
        if file_path.suffix in {'.yaml', '.yml'}:
            files_scanned += 1
            refs = scan_yaml_file(file_path)
            if refs:
                files_with_refs += 1
                all_refs.extend(refs)

    return {
        'meta': {
            'directory': str(directory.resolve()),
            'files_scanned': files_scanned,
            'files_with_refs': files_with_refs,
            'total_refs': len(all_refs),
        },
        'refs': all_refs,
    }


def main():
    if len(sys.argv) < 2:
        print('Usage: python 04_cross_lang_refs.py <directory>', file=sys.stderr)
        print('Example: python 04_cross_lang_refs.py tests/fixtures/samples/', file=sys.stderr)
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
