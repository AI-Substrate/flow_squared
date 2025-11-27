"""
Shared pytest configuration and fixtures for fs2.

Per Critical Finding 12: Fixtures mirror domain structure.
- Shared fixtures here (domain types, fakes)
- Test-specific fixtures in test files

Per Insight #2: Warn about singleton pollution.
Per Insight #6: clean_config_env fixture for test isolation.
"""

import os
import sys
import warnings

import pytest


def pytest_configure(config):
    """Register custom markers and warn about singleton pollution.

    Per Insight #2: Test-time warning for singleton pollution.
    If fs2.config.settings was imported before tests run, it may
    cause test pollution with cached values.
    """
    # Check for singleton pollution
    if "fs2.config" in sys.modules:
        _mod = sys.modules["fs2.config"]
        if hasattr(_mod, "settings") and _mod.settings is not None:
            warnings.warn(
                "fs2.config.settings singleton was imported before tests! "
                "This may cause test pollution. "
                "Use 'from fs2.config.models import FS2Settings' in tests.",
                UserWarning,
                stacklevel=1,
            )


@pytest.fixture
def clean_config_env(monkeypatch):
    """Clear all FS2_* environment variables for test isolation.

    Per Insight #6: Use this fixture in config tests to ensure
    no .env or inherited env var pollution.

    Usage:
        def test_something(clean_config_env, monkeypatch):
            monkeypatch.setenv("FS2_FOO", "value")
            # ... test with known state
    """
    for key in list(os.environ.keys()):
        if key.startswith("FS2_"):
            monkeypatch.delenv(key, raising=False)
    yield


# Future fixtures (Phase 3+):
# @pytest.fixture
# def fake_log_adapter():
#     from fs2.core.adapters.log_adapter import FakeLogAdapter
#     return FakeLogAdapter()
