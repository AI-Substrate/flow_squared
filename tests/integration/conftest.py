"""Shared fixtures for integration tests."""

import pytest


@pytest.fixture(autouse=True)
def reset_dependencies():
    """Reset global dependency singletons between tests.

    Per Phase 4: CLI commands use shared dependencies module.
    Tests must start with clean state to avoid cross-contamination.
    """
    from fs2.core import dependencies

    dependencies.reset_services()
    yield
    dependencies.reset_services()
