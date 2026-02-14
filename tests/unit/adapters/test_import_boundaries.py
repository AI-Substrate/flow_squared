"""Tests for import boundary rules.

Tests verify:
- Adapter ABC files contain no external SDK imports
- Models have no imports from services/adapters/repos

Architecture: Each adapter ABC is in its own file:
- log_adapter.py, console_adapter.py, sample_adapter.py

Per Finding 03: Repository/Adapter Pattern with SDK Isolation
Per AC3: Services → ABCs only; no SDK imports in ABC files
"""

import ast
from pathlib import Path

import pytest

# Dynamic project root resolution (works in devcontainer and local)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Allowed imports for ABC files: stdlib + fs2 internal
ALLOWED_MODULES = {
    "abc",
    "typing",
    "dataclasses",
    "datetime",
    "enum",
    "fs2",
}

# Forbidden patterns for domain models
FORBIDDEN_MODEL_PATTERNS = {
    "fs2.core.services",
    "fs2.core.adapters",
    "fs2.core.repos",
}


def check_no_sdk_imports(file_path: Path) -> list[str]:
    """Check that a file has no external SDK imports."""
    source = file_path.read_text()
    tree = ast.parse(source)

    forbidden_imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_root = alias.name.split(".")[0]
                if module_root not in ALLOWED_MODULES:
                    forbidden_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module_root = node.module.split(".")[0]
                if module_root not in ALLOWED_MODULES:
                    forbidden_imports.append(node.module)

    return forbidden_imports


def check_no_forbidden_model_imports(file_path: Path) -> list[str]:
    """Check that a model file doesn't import from services/adapters/repos."""
    source = file_path.read_text()
    tree = ast.parse(source)

    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                for pattern in FORBIDDEN_MODEL_PATTERNS:
                    if node.module.startswith(pattern):
                        violations.append(node.module)

    return violations


@pytest.mark.unit
class TestImportBoundaries:
    """Tests for Clean Architecture import boundaries."""

    def test_given_log_adapter_abc_when_imported_then_no_sdk_types(self):
        """
        Purpose: Proves log_adapter.py contains no external SDK imports
        Quality Contribution: Enforces Clean Architecture boundaries
        """
        file_path = (
            _PROJECT_ROOT / "src" / "fs2" / "core" / "adapters" / "log_adapter.py"
        )
        forbidden = check_no_sdk_imports(file_path)
        assert forbidden == [], f"Forbidden imports in log_adapter.py: {forbidden}"

    def test_given_console_adapter_abc_when_imported_then_no_sdk_types(self):
        """
        Purpose: Proves console_adapter.py contains no external SDK imports
        Quality Contribution: Enforces Clean Architecture boundaries
        """
        file_path = (
            _PROJECT_ROOT / "src" / "fs2" / "core" / "adapters" / "console_adapter.py"
        )
        forbidden = check_no_sdk_imports(file_path)
        assert forbidden == [], f"Forbidden imports in console_adapter.py: {forbidden}"

    def test_given_sample_adapter_abc_when_imported_then_no_sdk_types(self):
        """
        Purpose: Proves sample_adapter.py contains no external SDK imports
        Quality Contribution: Enforces Clean Architecture boundaries
        """
        file_path = (
            _PROJECT_ROOT / "src" / "fs2" / "core" / "adapters" / "sample_adapter.py"
        )
        forbidden = check_no_sdk_imports(file_path)
        assert forbidden == [], f"Forbidden imports in sample_adapter.py: {forbidden}"

    def test_given_repos_protocols_when_imported_then_no_sdk_types(self):
        """
        Purpose: Proves repos protocols.py contains no external SDK imports
        Quality Contribution: Enforces Clean Architecture boundaries
        """
        file_path = _PROJECT_ROOT / "src" / "fs2" / "core" / "repos" / "protocols.py"
        forbidden = check_no_sdk_imports(file_path)
        assert forbidden == [], f"Forbidden imports in repos/protocols.py: {forbidden}"

    def test_given_models_log_level_when_imported_then_no_core_imports(self):
        """
        Purpose: Proves domain models don't import from services/adapters/repos
        Quality Contribution: Enforces dependency flow rules
        """
        file_path = _PROJECT_ROOT / "src" / "fs2" / "core" / "models" / "log_level.py"
        violations = check_no_forbidden_model_imports(file_path)
        assert violations == [], f"Forbidden imports in log_level.py: {violations}"

    def test_given_models_log_entry_when_imported_then_no_core_imports(self):
        """
        Purpose: Proves LogEntry doesn't import from services/adapters/repos
        Quality Contribution: Enforces dependency flow rules
        """
        file_path = _PROJECT_ROOT / "src" / "fs2" / "core" / "models" / "log_entry.py"
        violations = check_no_forbidden_model_imports(file_path)
        assert violations == [], f"Forbidden imports in log_entry.py: {violations}"
