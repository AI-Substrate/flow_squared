"""
Tests for vendored SolidLSP imports.

Purpose: Verify all vendored SolidLSP modules are importable and functional.
Quality Contribution: Catches broken import paths from vendoring.
Acceptance Criteria: All core modules import without error.

TDD Phase: RED - This test is expected to fail initially (ImportError)
           GREEN - Test passes after vendoring is complete (T011)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


class TestSolidLspVendorImports:
    """Tests for vendored SolidLSP core imports."""

    def test_given_vendored_solidlsp_when_importing_core_then_succeeds(self) -> None:
        """
        AC03: Vendored code passes import test.

        Verifies that core SolidLSP modules can be imported from
        the fs2.vendors.solidlsp namespace.
        """
        from fs2.vendors.solidlsp.ls import SolidLanguageServer
        from fs2.vendors.solidlsp.ls_config import Language, LanguageServerConfig
        from fs2.vendors.solidlsp.ls_handler import SolidLanguageServerHandler
        from fs2.vendors.solidlsp.ls_types import Position, Range

        assert SolidLanguageServer is not None
        assert SolidLanguageServerHandler is not None
        assert Language is not None
        assert LanguageServerConfig is not None
        assert Position is not None
        assert Range is not None

    def test_given_vendored_solidlsp_when_importing_language_configs_then_succeeds(
        self,
    ) -> None:
        """
        Verify language server configs are importable.

        Tests that language-specific server configurations can be imported.
        """
        from fs2.vendors.solidlsp.language_servers.csharp_language_server import (
            CSharpLanguageServer,
        )
        from fs2.vendors.solidlsp.language_servers.gopls import Gopls
        from fs2.vendors.solidlsp.language_servers.pyright_server import PyrightServer
        from fs2.vendors.solidlsp.language_servers.typescript_language_server import (
            TypeScriptLanguageServer,
        )

        assert PyrightServer is not None
        assert Gopls is not None
        assert TypeScriptLanguageServer is not None
        assert CSharpLanguageServer is not None

    def test_given_vendored_solidlsp_when_checking_no_serena_imports_then_clean(
        self,
    ) -> None:
        """
        Verify no serena.* imports remain in vendored code.

        The vendored code should have all serena.* imports stubbed out.
        This test uses grep to verify no direct serena imports exist.
        """
        vendor_path = Path(__file__).parents[3] / "src" / "fs2" / "vendors" / "solidlsp"

        if not vendor_path.exists():
            pytest.skip("Vendor path not yet created")

        # Check for direct serena imports (excluding _stubs directory)
        result = subprocess.run(
            [
                "grep",
                "-r",
                "--include=*.py",
                "-l",
                r"from serena\|import serena",
                str(vendor_path),
            ],
            capture_output=True,
            text=True,
        )

        # Filter out _stubs directory from results
        matching_files = [
            f for f in result.stdout.strip().split("\n") if f and "_stubs" not in f
        ]

        assert len(matching_files) == 0, f"Found serena imports in: {matching_files}"

    def test_given_vendored_solidlsp_when_checking_csharp_fixes_then_preserved(
        self,
    ) -> None:
        """
        Verify C# DOTNET_ROOT fix is present.

        Phase 0b research identified that C# LSP needs DOTNET_ROOT
        environment variable passed to subprocess. This fix must be preserved.
        """
        vendor_path = Path(__file__).parents[3] / "src" / "fs2" / "vendors" / "solidlsp"
        csharp_server = vendor_path / "language_servers" / "csharp_language_server.py"

        if not csharp_server.exists():
            pytest.skip("C# language server not yet vendored")

        content = csharp_server.read_text()

        # Verify DOTNET_ROOT env var fix
        assert "DOTNET_ROOT" in content, (
            "C# fix: DOTNET_ROOT environment variable not found"
        )

        # Verify .NET 9+ version check (range(9, 20) or similar)
        assert "range(9," in content or "for major in range(9" in content, (
            "C# fix: .NET 9+ version range not found"
        )

    def test_given_vendored_solidlsp_when_instantiating_then_stubs_compatible(
        self,
    ) -> None:
        """
        Smoke test: verify stubs work at runtime.

        Beyond import success, verify that basic instantiation works.
        This catches stub incompatibilities that would only manifest at runtime.
        """
        from fs2.vendors.solidlsp.ls_config import Language, LanguageServerConfig

        # Create a basic config - this exercises stub compatibility
        # Note: LanguageServerConfig uses code_language, not language
        config = LanguageServerConfig(
            code_language=Language.PYTHON,
        )

        assert config is not None
        assert config.code_language == Language.PYTHON
