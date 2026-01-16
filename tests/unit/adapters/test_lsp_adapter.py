"""Tests for LspAdapter ABC interface.

TDD Phase: RED - These tests should fail until T005 is implemented.

Tests cover:
- AC04: LspAdapter ABC defines language-agnostic interface returning CodeEdge only
- ABC cannot be instantiated directly
- Required methods exist: initialize, shutdown, get_references, get_definition, is_ready
- Return types are list[CodeEdge]

Per Testing Philosophy: Full TDD approach.
"""

from abc import ABC
from inspect import signature

import pytest


@pytest.mark.unit
class TestLspAdapterABC:
    """Tests for LspAdapter ABC interface contract."""

    def test_given_lsp_adapter_when_checking_inheritance_then_is_abc(self):
        """AC04: LspAdapter is an ABC.

        Purpose: Proves LspAdapter follows ABC pattern
        Quality Contribution: Ensures interface cannot be used directly
        Acceptance Criteria: LspAdapter is subclass of ABC
        """
        from fs2.core.adapters.lsp_adapter import LspAdapter

        assert issubclass(LspAdapter, ABC)

    def test_given_lsp_adapter_when_instantiating_then_raises_type_error(self):
        """LspAdapter ABC cannot be instantiated directly.

        Purpose: Proves ABC enforcement works
        Quality Contribution: Ensures adapters implement required methods
        """
        from fs2.core.adapters.lsp_adapter import LspAdapter

        with pytest.raises(TypeError) as exc_info:
            LspAdapter()  # type: ignore[abstract]

        assert "abstract" in str(exc_info.value).lower()

    def test_given_lsp_adapter_when_checking_methods_then_has_required_interface(self):
        """AC04: LspAdapter defines language-agnostic interface.

        Purpose: Proves all required methods are defined
        Quality Contribution: Ensures consistent interface across implementations
        Acceptance Criteria: has initialize, shutdown, get_references, get_definition, is_ready
        """
        from fs2.core.adapters.lsp_adapter import LspAdapter

        assert hasattr(LspAdapter, "initialize")
        assert hasattr(LspAdapter, "shutdown")
        assert hasattr(LspAdapter, "get_references")
        assert hasattr(LspAdapter, "get_definition")
        assert hasattr(LspAdapter, "is_ready")

    def test_given_lsp_adapter_when_checking_get_references_then_returns_code_edge_list(
        self,
    ):
        """AC04: get_references returns list[CodeEdge].

        Purpose: Proves domain-only return types
        Quality Contribution: Prevents SolidLSP type leakage
        """
        from fs2.core.adapters.lsp_adapter import LspAdapter

        sig = signature(LspAdapter.get_references)
        return_annotation = str(sig.return_annotation)

        assert "CodeEdge" in return_annotation

    def test_given_lsp_adapter_when_checking_get_definition_then_returns_code_edge_list(
        self,
    ):
        """AC04: get_definition returns list[CodeEdge].

        Purpose: Proves domain-only return types
        Quality Contribution: Prevents SolidLSP type leakage
        """
        from fs2.core.adapters.lsp_adapter import LspAdapter

        sig = signature(LspAdapter.get_definition)
        return_annotation = str(sig.return_annotation)

        assert "CodeEdge" in return_annotation

    def test_given_lsp_adapter_when_checking_is_ready_then_returns_bool(self):
        """is_ready() returns boolean.

        Purpose: Proves is_ready method signature
        Quality Contribution: Enables graceful degradation checks
        """
        from fs2.core.adapters.lsp_adapter import LspAdapter

        sig = signature(LspAdapter.is_ready)
        return_annotation = str(sig.return_annotation)

        assert "bool" in return_annotation.lower()

    def test_given_lsp_adapter_when_checking_initialize_params_then_accepts_language_and_root(
        self,
    ):
        """initialize() accepts language and project_root.

        Purpose: Per DYK-4, language and root are initialize() params
        Quality Contribution: Ensures correct initialization signature
        """
        from fs2.core.adapters.lsp_adapter import LspAdapter

        sig = signature(LspAdapter.initialize)
        param_names = list(sig.parameters.keys())

        # Should have self, language, and project_root (order may vary after self)
        assert "language" in param_names
        assert "project_root" in param_names
