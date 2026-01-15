#!/usr/bin/env python3
"""
Detection test script for project root validation.

This script validates:
1. "Deepest wins" algorithm for all 4 languages against fixtures
2. Boundary constraint (workspace_root parameter)
3. Language detection via from_filename()
4. Marker file priority at same level

Exit codes:
- 0: All tests pass
- 1: One or more tests failed

Production quality: This validates research scripts before Phase 3 cherry-pick.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.lsp.detect_project_root import (
    detect_project_root_auto,
    find_all_project_roots,
    find_project_root,
)
from scripts.lsp.language import Language, get_typescript_patterns

# Test fixtures base path
FIXTURES_BASE = PROJECT_ROOT / "tests" / "fixtures" / "lsp"


class TestResult:
    """Track test results."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def pass_test(self, name: str) -> None:
        self.passed += 1
        print(f"  ✓ {name}")

    def fail_test(self, name: str, expected: str, got: str) -> None:
        self.failed += 1
        msg = f"  ✗ {name}: expected {expected}, got {got}"
        print(msg)
        self.errors.append(msg)

    def summary(self) -> int:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Results: {self.passed}/{total} passed, {self.failed} failed")
        if self.errors:
            print("\nFailures:")
            for error in self.errors:
                print(f"  {error}")
        return 0 if self.failed == 0 else 1


def test_python_deepest_wins(results: TestResult) -> None:
    """Test Python detection finds nested pyproject.toml (deepest wins)."""
    print("\n[Python: Deepest Wins]")

    fixture = FIXTURES_BASE / "python_multi_project"
    test_file = fixture / "packages" / "auth" / "handler.py"
    expected_root = fixture / "packages" / "auth"  # Has pyproject.toml

    root = find_project_root(test_file, Language.PYTHON)
    if root == expected_root:
        results.pass_test("handler.py → packages/auth/ (deepest)")
    else:
        results.fail_test("handler.py → packages/auth/", str(expected_root), str(root))


def test_typescript_deepest_wins(results: TestResult) -> None:
    """Test TypeScript detection finds nested tsconfig.json (deepest wins)."""
    print("\n[TypeScript: Deepest Wins]")

    fixture = FIXTURES_BASE / "typescript_multi_project"
    test_file = fixture / "packages" / "client" / "index.tsx"
    expected_root = fixture / "packages" / "client"  # Has tsconfig.json

    root = find_project_root(test_file, Language.TYPESCRIPT)
    if root == expected_root:
        results.pass_test("index.tsx → packages/client/ (deepest)")
    else:
        results.fail_test("index.tsx → packages/client/", str(expected_root), str(root))


def test_go_single_root(results: TestResult) -> None:
    """Test Go detection finds single go.mod at root (no nesting)."""
    print("\n[Go: Single Root (no nested go.mod)]")

    fixture = FIXTURES_BASE / "go_project"
    test_file = fixture / "cmd" / "server" / "main.go"
    expected_root = fixture  # Single go.mod at root

    root = find_project_root(test_file, Language.GO)
    if root == expected_root:
        results.pass_test("cmd/server/main.go → go_project/ (single root)")
    else:
        results.fail_test("cmd/server/main.go → go_project/", str(expected_root), str(root))


def test_csharp_deepest_wins(results: TestResult) -> None:
    """Test C# detection finds nested .csproj (deepest wins over .sln)."""
    print("\n[C#: Deepest Wins (.csproj over .sln)]")

    fixture = FIXTURES_BASE / "csharp_multi_project"
    test_file = fixture / "src" / "Api" / "Program.cs"
    expected_root = fixture / "src" / "Api"  # Has Api.csproj

    root = find_project_root(test_file, Language.CSHARP)
    if root == expected_root:
        results.pass_test("Program.cs → src/Api/ (deepest .csproj)")
    else:
        results.fail_test("Program.cs → src/Api/", str(expected_root), str(root))


def test_boundary_constraint(results: TestResult) -> None:
    """Test workspace_root boundary stops search."""
    print("\n[Boundary Constraint]")

    fixture = FIXTURES_BASE / "python_multi_project"
    test_file = fixture / "packages" / "auth" / "handler.py"
    # Set boundary at packages/ - should NOT find root pyproject.toml
    boundary = fixture / "packages"
    expected_root = fixture / "packages" / "auth"  # Still finds nested

    root = find_project_root(test_file, Language.PYTHON, workspace_root=boundary)
    if root == expected_root:
        results.pass_test("Boundary at packages/ → still finds auth/")
    else:
        results.fail_test("Boundary at packages/", str(expected_root), str(root))

    # Set boundary at auth/ - should find auth/
    boundary = fixture / "packages" / "auth"
    root = find_project_root(test_file, Language.PYTHON, workspace_root=boundary)
    if root == expected_root:
        results.pass_test("Boundary at auth/ → finds auth/")
    else:
        results.fail_test("Boundary at auth/", str(expected_root), str(root))


def test_auto_detection(results: TestResult) -> None:
    """Test detect_project_root_auto() language detection."""
    print("\n[Auto-Detection]")

    fixture = FIXTURES_BASE / "python_multi_project"
    test_file = fixture / "packages" / "auth" / "handler.py"
    expected_root = fixture / "packages" / "auth"
    expected_lang = Language.PYTHON

    root, lang = detect_project_root_auto(test_file)
    if root == expected_root and lang == expected_lang:
        results.pass_test("handler.py auto-detects Python + auth/")
    else:
        results.fail_test(
            "handler.py auto-detect",
            f"({expected_root}, {expected_lang})",
            f"({root}, {lang})",
        )

    # Test TypeScript with .tsx extension
    fixture = FIXTURES_BASE / "typescript_multi_project"
    test_file = fixture / "packages" / "client" / "index.tsx"
    expected_root = fixture / "packages" / "client"
    expected_lang = Language.TYPESCRIPT

    root, lang = detect_project_root_auto(test_file)
    if root == expected_root and lang == expected_lang:
        results.pass_test("index.tsx auto-detects TypeScript + client/")
    else:
        results.fail_test(
            "index.tsx auto-detect",
            f"({expected_root}, {expected_lang})",
            f"({root}, {lang})",
        )

    # Test unknown extension returns None language
    unknown_file = fixture / "packages" / "client" / "readme.md"
    root, lang = detect_project_root_auto(unknown_file)
    if lang is None:
        results.pass_test("readme.md returns None language")
    else:
        results.fail_test("readme.md lang", "None", str(lang))


def test_typescript_pattern_generation(results: TestResult) -> None:
    """Test TypeScript algorithmic pattern generation (12 patterns)."""
    print("\n[TypeScript Pattern Generation]")

    patterns = get_typescript_patterns()
    expected_count = 12  # prefix(3) × postfix(2) × base(2) = 12

    if len(patterns) == expected_count:
        results.pass_test(f"Generated {expected_count} patterns")
    else:
        results.fail_test("Pattern count", str(expected_count), str(len(patterns)))

    # Verify key patterns exist
    key_patterns = ["*.ts", "*.tsx", "*.js", "*.jsx", "*.mts", "*.mjs", "*.cts", "*.cjs"]
    for pattern in key_patterns:
        if pattern in patterns:
            results.pass_test(f"Contains {pattern}")
        else:
            results.fail_test(f"Contains {pattern}", "present", "missing")


def test_language_from_filename(results: TestResult) -> None:
    """Test Language.from_filename() detection."""
    print("\n[Language Detection]")

    test_cases = [
        ("main.py", Language.PYTHON),
        ("types.pyi", Language.PYTHON),
        ("app.ts", Language.TYPESCRIPT),
        ("app.tsx", Language.TYPESCRIPT),
        ("utils.mjs", Language.TYPESCRIPT),
        ("config.cjs", Language.TYPESCRIPT),
        ("handler.go", Language.GO),
        ("Program.cs", Language.CSHARP),
        ("readme.md", None),
        ("config.json", None),
    ]

    for filename, expected in test_cases:
        result = Language.from_filename(filename)
        if result == expected:
            results.pass_test(f"{filename} → {expected}")
        else:
            results.fail_test(f"{filename}", str(expected), str(result))


def test_fallback_to_file_directory(results: TestResult) -> None:
    """Test fallback when no marker found."""
    print("\n[Fallback to File Directory]")

    # Create a path that won't have any markers
    fake_file = Path("/tmp/no_markers/deep/nested/file.py")
    expected_dir = Path("/tmp/no_markers/deep/nested")

    # Should fall back to file's directory when no marker found
    root = find_project_root(fake_file, Language.PYTHON)
    if root == expected_dir:
        results.pass_test("No marker → falls back to file's directory")
    else:
        results.fail_test("No marker fallback", str(expected_dir), str(root))


def test_find_all_project_roots(results: TestResult) -> None:
    """Test find_all_project_roots() finds multiple roots."""
    print("\n[Find All Project Roots]")

    fixture = FIXTURES_BASE / "python_multi_project"

    roots = find_all_project_roots(fixture, Language.PYTHON)

    # Should find both pyproject.toml locations
    expected_roots = {
        fixture,  # Root pyproject.toml
        fixture / "packages" / "auth",  # Nested pyproject.toml
    }

    found_set = set(roots)
    if found_set == expected_roots:
        results.pass_test(f"Found {len(roots)} project roots (deepest first)")
    else:
        results.fail_test(
            "Find all roots",
            str(expected_roots),
            str(found_set),
        )

    # Verify order: deepest first
    if len(roots) >= 2 and len(roots[0].parts) > len(roots[1].parts):
        results.pass_test("Sorted deepest first")
    else:
        results.fail_test("Sort order", "deepest first", "incorrect order")


def main() -> int:
    """Run all tests and return exit code."""
    print("=" * 60)
    print("LSP Project Root Detection - Validation Tests")
    print("=" * 60)

    results = TestResult()

    # Core algorithm tests
    test_python_deepest_wins(results)
    test_typescript_deepest_wins(results)
    test_go_single_root(results)
    test_csharp_deepest_wins(results)

    # Edge cases and features
    test_boundary_constraint(results)
    test_auto_detection(results)
    test_typescript_pattern_generation(results)
    test_language_from_filename(results)
    test_fallback_to_file_directory(results)
    test_find_all_project_roots(results)

    return results.summary()


if __name__ == "__main__":
    sys.exit(main())
