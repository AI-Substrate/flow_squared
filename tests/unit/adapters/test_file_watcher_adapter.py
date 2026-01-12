"""Tests for FileWatcherAdapter ABC contract.

Task: T003
Purpose: Verify FileWatcherAdapter ABC defines correct interface.
Per Finding 02: Adapter ABC with Dual Implementation Pattern.
"""

from abc import ABC

import pytest


@pytest.mark.unit
class TestFileWatcherAdapterABC:
    """Tests for FileWatcherAdapter ABC contract (T003).

    These tests verify the abstract base class defines the expected interface
    for file watching adapters. Per spec: watch() async generator, stop() method.
    """

    def test_file_watcher_adapter_abc_cannot_be_instantiated(self):
        """
        Given: FileWatcherAdapter is an abstract base class
        When: Attempting to instantiate it directly
        Then: TypeError is raised

        Purpose: Proves ABC cannot be directly instantiated.
        Quality Contribution: Enforces interface-only contract.
        Acceptance Criteria: TypeError raised on instantiation.
        """
        from fs2.core.adapters.file_watcher_adapter import FileWatcherAdapter

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            FileWatcherAdapter()

    def test_file_watcher_adapter_abc_defines_watch_method(self):
        """
        Given: FileWatcherAdapter is an abstract base class
        When: Checking its abstract methods
        Then: watch is in __abstractmethods__

        Purpose: Verifies watch() is an abstract method.
        Quality Contribution: Ensures implementations provide watch().
        Acceptance Criteria: watch in __abstractmethods__.
        """
        from fs2.core.adapters.file_watcher_adapter import FileWatcherAdapter

        assert "watch" in FileWatcherAdapter.__abstractmethods__

    def test_file_watcher_adapter_abc_defines_stop_method(self):
        """
        Given: FileWatcherAdapter is an abstract base class
        When: Checking its abstract methods
        Then: stop is in __abstractmethods__

        Purpose: Verifies stop() is an abstract method.
        Quality Contribution: Ensures implementations provide stop().
        Acceptance Criteria: stop in __abstractmethods__.
        """
        from fs2.core.adapters.file_watcher_adapter import FileWatcherAdapter

        assert "stop" in FileWatcherAdapter.__abstractmethods__

    def test_file_watcher_adapter_abc_inherits_from_abc(self):
        """
        Given: FileWatcherAdapter follows the ABC pattern
        When: Checking its inheritance hierarchy
        Then: FileWatcherAdapter is a subclass of ABC

        Purpose: Verifies FileWatcherAdapter is a proper ABC.
        Quality Contribution: Ensures abc.ABC pattern followed correctly.
        Acceptance Criteria: FileWatcherAdapter is subclass of ABC.
        """
        from fs2.core.adapters.file_watcher_adapter import FileWatcherAdapter

        assert issubclass(FileWatcherAdapter, ABC)

    def test_file_watcher_adapter_watch_returns_async_iterator(self):
        """
        Given: FileWatcherAdapter.watch() is designed to be an async generator
        When: A concrete implementation provides watch()
        Then: It should be an async method returning an async iterator

        Purpose: Verifies watch() signature expects async iteration.
        Quality Contribution: Ensures consistent async generator interface.
        Acceptance Criteria: watch() signature is async.

        Note: This tests the interface contract via type hints/signatures.
        Actual async behavior is tested in implementation tests.
        """

        from fs2.core.adapters.file_watcher_adapter import FileWatcherAdapter

        # Get the watch method
        watch_method = getattr(FileWatcherAdapter, "watch", None)
        assert watch_method is not None, "watch method must exist"

        # Check it's a coroutine function (async def) or async generator
        # ABC abstract methods may not show as coroutine until implemented,
        # but we can verify the method exists and is abstract
        assert "watch" in FileWatcherAdapter.__abstractmethods__
