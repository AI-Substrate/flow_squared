"""Pytest configuration for web services tests.

Per Critical Insight #4 from tasks.md:
This conftest.py is scoped to tests/unit/web/services/ only.
The autouse=True fixture clears FS2_* env vars before each test
to prevent test pollution, without affecting CLI tests.
"""

import os

import pytest


@pytest.fixture(autouse=True)
def clean_fs2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear all FS2_* environment variables before each test.

    This prevents test pollution from:
    - Environment variables set by previous tests
    - Devcontainer/CI environment variables
    - User's local .env file

    Per Critical Discovery 08 and Insight 4:
    Scoped to services/ only - CLI tests are unaffected.
    """
    # Find all FS2_* env vars
    fs2_vars = [key for key in os.environ if key.startswith("FS2_")]

    # Remove each one
    for var in fs2_vars:
        monkeypatch.delenv(var, raising=False)
