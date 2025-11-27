"""
Shared pytest configuration and fixtures for fs2.

Per Critical Finding 12: Fixtures mirror domain structure.
- Shared fixtures here (domain types, fakes)
- Test-specific fixtures in test files

Per Insight #2: Warn about singleton pollution.
Per Insight #6: clean_config_env fixture for test isolation.
Per Phase 3: TestContext fixture for pre-wired DI.
"""

import os
import sys
import warnings
from dataclasses import dataclass

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


# Phase 3: Pre-wired test dependencies


@dataclass
class TestContext:
    """Pre-wired dependencies for tests.

    Provides a ready-to-use DI container with common test dependencies.
    Tests can use this directly or extract individual components.

    Attributes:
        config: FakeConfigurationService with LogAdapterConfig pre-registered
        logger: FakeLogAdapter for capturing log messages

    Usage:
        def test_something(test_context):
            service = SomeService(config=test_context.config, logger=test_context.logger)
            service.do_work()
            assert len(test_context.logger.messages) == 1
    """

    config: "FakeConfigurationService"  # noqa: F821
    logger: "FakeLogAdapter"  # noqa: F821


@pytest.fixture
def test_context():
    """Pre-configured test context with logger and config.

    Per Phase 3 Insight #2: Reduces boilerplate for tests that need
    a working ConfigurationService + FakeLogAdapter combination.

    The config comes pre-loaded with LogAdapterConfig(min_level="DEBUG")
    so all log levels are captured by default.

    Usage:
        def test_service_logs_on_start(test_context):
            service = MyService(
                config=test_context.config,
                logger=test_context.logger
            )
            service.start()
            assert any("started" in m.message.lower() for m in test_context.logger.messages)
    """
    from fs2.config.objects import LogAdapterConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.log_adapter_fake import FakeLogAdapter

    config = FakeConfigurationService(LogAdapterConfig(min_level="DEBUG"))
    logger = FakeLogAdapter(config)
    return TestContext(config=config, logger=logger)
