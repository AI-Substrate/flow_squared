#!/usr/bin/env python3
"""Verify tree-sitter setup by parsing fixture files in 6 target languages.

Per insight #2: Uses explicit FIXTURE_MAP to map language names to specific files.
"""

import sys
from pathlib import Path
from tree_sitter_language_pack import get_parser

# Fixture root directory
FIXTURES_ROOT = Path("/workspaces/flow_squared/tests/fixtures/samples")

# Explicit mapping of language to fixture file (per insight #2)
FIXTURE_MAP = {
    "python": "python/auth_handler.py",
    "typescript": "javascript/app.ts",
    "go": "go/server.go",
    "rust": "rust/lib.rs",
    "java": "java/UserService.java",
    "c": "c/algorithm.c",
}


def count_nodes(node) -> int:
    """Recursively count all nodes in AST tree."""
    count = 1  # Count current node
    for child in node.children:
        count += count_nodes(child)
    return count


def verify_language(lang: str, fixture_path: str) -> tuple[bool, int, str]:
    """Parse a fixture file and return (success, node_count, message)."""
    file_path = FIXTURES_ROOT / fixture_path

    if not file_path.exists():
        return False, 0, f"File not found: {file_path}"

    try:
        parser = get_parser(lang)
        content = file_path.read_bytes()
        tree = parser.parse(content)
        node_count = count_nodes(tree.root_node)
        return True, node_count, f"Parsed successfully"
    except Exception as e:
        return False, 0, f"Parse error: {e}"


def main() -> int:
    """Verify tree-sitter works for all target languages."""
    print("=" * 60)
    print("Tree-sitter Setup Verification")
    print("=" * 60)

    all_passed = True
    results = []

    for lang, fixture_path in FIXTURE_MAP.items():
        success, node_count, msg = verify_language(lang, fixture_path)
        status = "OK" if success else "FAIL"
        results.append((lang, fixture_path, status, node_count, msg))

        if not success:
            all_passed = False

    # Print results table
    print(f"\n{'Language':<12} {'Fixture':<30} {'Status':<6} {'Nodes':<8}")
    print("-" * 60)

    for lang, path, status, nodes, msg in results:
        print(f"{lang:<12} {path:<30} {status:<6} {nodes:<8}")

    print("-" * 60)

    if all_passed:
        print(f"\nSUCCESS: All {len(FIXTURE_MAP)} languages verified!")
        return 0
    else:
        print(f"\nFAILED: Some languages could not be parsed")
        for lang, path, status, nodes, msg in results:
            if status == "FAIL":
                print(f"  - {lang}: {msg}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
