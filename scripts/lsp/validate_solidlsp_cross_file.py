#!/usr/bin/env python3
"""
Validate SolidLSP cross-file reference resolution.

This script imports SolidLSP directly from scratch/serena/src/solidlsp/
and validates that it can find cross-file method call references
for Python, TypeScript, Go, and C#.

Uses serena's venv Python to access the SolidLSP dependencies.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

# Add SolidLSP to path
SOLIDLSP_PATH = Path(__file__).parent.parent.parent / "scratch" / "serena" / "src"
sys.path.insert(0, str(SOLIDLSP_PATH))

from solidlsp import SolidLanguageServer
from solidlsp.ls_config import Language, LanguageServerConfig

if TYPE_CHECKING:
    from solidlsp import ls_types

# Fixture base path
FIXTURES_PATH = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "lsp"


@contextmanager
def language_server(language: Language, repo_path: Path) -> Iterator[SolidLanguageServer]:
    """Context manager for SolidLSP lifecycle (start/stop)."""
    config = LanguageServerConfig(code_language=language)
    ls = SolidLanguageServer.create(config, str(repo_path.absolute()))
    ls.start()
    try:
        yield ls
    finally:
        ls.stop()


def validate_python() -> tuple[bool, list[ls_types.Location]]:
    """Validate Python cross-file references via PyrightServer."""
    fixture_path = FIXTURES_PATH / "python_multi_project"
    print(f"\n[Python] Fixture: {fixture_path}")

    with language_server(Language.PYTHON, fixture_path) as ls:
        # Query references for User.validate method
        # Line 10 (0-indexed: 9), column 8 for 'validate' function name
        refs = ls.request_references(
            "packages/auth/models.py",
            line=9,  # 0-indexed
            column=8
        )

        print(f"  References found: {len(refs)}")
        for ref in refs:
            rel_path = ref.get("relativePath") or ""
            print(f"    - {rel_path}: line {ref['range']['start']['line']+1}")

        # Check if handler.py is in the references
        for ref in refs:
            rel_path = ref.get("relativePath") or ""
            if "handler.py" in rel_path:
                print("  [PASS] Python: Found cross-file reference in handler.py")
                return True, refs

        print("  [FAIL] Python: No cross-file reference found")
        return False, refs


def validate_typescript() -> tuple[bool, list[ls_types.Location]]:
    """Validate TypeScript cross-file references via TypeScriptLanguageServer."""
    fixture_path = FIXTURES_PATH / "typescript_multi_project"
    print(f"\n[TypeScript] Fixture: {fixture_path}")

    with language_server(Language.TYPESCRIPT, fixture_path) as ls:
        # TypeScript LSP needs both files opened to index cross-file references
        # Open the referencing file first to trigger indexing
        with ls.open_file("packages/client/index.tsx"):
            pass  # Just opening triggers indexing

        # Line 5 (0-indexed: 4), column 16 for 'formatDate'
        refs = ls.request_references(
            "packages/client/utils.ts",
            line=4,  # 0-indexed
            column=16
        )

        print(f"  References found: {len(refs)}")
        for ref in refs:
            rel_path = ref.get("relativePath") or ""
            print(f"    - {rel_path}: line {ref['range']['start']['line']+1}")

        for ref in refs:
            rel_path = ref.get("relativePath") or ""
            if "index.tsx" in rel_path:
                print("  [PASS] TypeScript: Found cross-file reference in index.tsx")
                return True, refs

        print("  [FAIL] TypeScript: No cross-file reference found")
        return False, refs


def validate_go() -> tuple[bool, list[ls_types.Location]]:
    """Validate Go cross-file references via Gopls."""
    fixture_path = FIXTURES_PATH / "go_project"
    print(f"\n[Go] Fixture: {fixture_path}")

    with language_server(Language.GO, fixture_path) as ls:
        # Line 6 (0-indexed: 5), column 5 for 'Validate'
        refs = ls.request_references(
            "internal/auth/auth.go",
            line=5,  # 0-indexed
            column=5
        )

        print(f"  References found: {len(refs)}")
        for ref in refs:
            rel_path = ref.get("relativePath") or ""
            print(f"    - {rel_path}: line {ref['range']['start']['line']+1}")

        for ref in refs:
            rel_path = ref.get("relativePath") or ""
            if "main.go" in rel_path:
                print("  [PASS] Go: Found cross-file reference in main.go")
                return True, refs

        print("  [FAIL] Go: No cross-file reference found")
        return False, refs


def validate_csharp() -> tuple[bool, list[ls_types.Location]]:
    """Validate C# cross-file references via CSharpLanguageServer."""
    fixture_path = FIXTURES_PATH / "csharp_multi_project"
    print(f"\n[C#] Fixture: {fixture_path}")

    with language_server(Language.CSHARP, fixture_path) as ls:
        # C# LSP may need both files opened like TypeScript
        # Open the referencing file first to trigger indexing
        with ls.open_file("src/Api/Program.cs"):
            pass  # Just opening triggers indexing

        # Line 11 (0-indexed: 10), column 16 for 'Validate'
        refs = ls.request_references(
            "src/Api/Models.cs",
            line=10,  # 0-indexed
            column=16
        )

        print(f"  References found: {len(refs)}")
        for ref in refs:
            rel_path = ref.get("relativePath") or ""
            print(f"    - {rel_path}: line {ref['range']['start']['line']+1}")

        for ref in refs:
            rel_path = ref.get("relativePath") or ""
            if "Program.cs" in rel_path:
                print("  [PASS] C#: Found cross-file reference in Program.cs")
                return True, refs

        print("  [FAIL] C#: No cross-file reference found")
        return False, refs


def main() -> int:
    """Run all validations and return exit code."""
    print("SolidLSP Cross-File Reference Validation")
    print("=" * 50)
    print(f"SolidLSP Path: {SOLIDLSP_PATH}")
    print(f"Fixtures Path: {FIXTURES_PATH}")

    results: dict[str, tuple[bool, list[ls_types.Location]]] = {}

    # Run validations for each language
    # Note: Each language server may take some time to start and index
    try:
        results["Python"] = validate_python()
    except Exception as e:
        print(f"  [ERROR] Python: {e}")
        results["Python"] = (False, [])

    try:
        results["TypeScript"] = validate_typescript()
    except Exception as e:
        print(f"  [ERROR] TypeScript: {e}")
        results["TypeScript"] = (False, [])

    try:
        results["Go"] = validate_go()
    except Exception as e:
        print(f"  [ERROR] Go: {e}")
        results["Go"] = (False, [])

    try:
        results["C#"] = validate_csharp()
    except Exception as e:
        print(f"  [ERROR] C#: {e}")
        results["C#"] = (False, [])

    # Summary
    print()
    print("Summary")
    print("-" * 50)

    all_passed = True
    passed_count = 0
    for lang, (passed, _) in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {lang}: {status}")
        if passed:
            passed_count += 1
        else:
            all_passed = False

    print()
    print(f"Result: {passed_count}/4 languages passed")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
