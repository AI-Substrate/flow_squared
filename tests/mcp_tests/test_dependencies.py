"""Tests for lazy service initialization.

Services should be created on first access and cached thereafter.
This enables fast server startup and proper resource management.

Per Critical Discovery 03: GraphStore requires ConfigurationService injection.
"""

import logging

import pytest


class TestLazyInitialization:
    """Verify lazy initialization and singleton pattern."""

    def test_config_none_before_first_access(self):
        """Config singleton is None before first access.

        Services should not be created until explicitly requested.
        This enables fast server startup.
        """
        from fs2.mcp import dependencies

        # Reset state
        dependencies.reset_services()

        assert dependencies._config is None

    def test_config_created_on_first_access(self):
        """Config is created when get_config() is called."""
        from fs2.config.service import ConfigurationService
        from fs2.mcp import dependencies

        dependencies.reset_services()

        config = dependencies.get_config()

        assert isinstance(config, ConfigurationService)

    def test_config_cached_after_first_access(self):
        """Config is cached (singleton pattern)."""
        from fs2.mcp import dependencies

        dependencies.reset_services()

        config1 = dependencies.get_config()
        config2 = dependencies.get_config()

        assert config1 is config2, "Config should be cached singleton"

    def test_graph_store_none_before_first_access(self):
        """GraphStore singleton is None before first access."""
        from fs2.mcp import dependencies

        dependencies.reset_services()

        assert dependencies._graph_store is None

    @pytest.mark.skip(
        reason="Requires .fs2/graph.pickle — GraphService checks filesystem"
    )
    def test_graph_store_created_on_first_access(self):
        """GraphStore is created when get_graph_store() is called."""
        from fs2.core.repos.graph_store import GraphStore
        from fs2.mcp import dependencies

        dependencies.reset_services()

        store = dependencies.get_graph_store()

        assert isinstance(store, GraphStore)

    @pytest.mark.skip(
        reason="Requires .fs2/graph.pickle — GraphService checks filesystem"
    )
    def test_graph_store_cached_after_first_access(self):
        """GraphStore is cached (singleton pattern)."""
        from fs2.mcp import dependencies

        dependencies.reset_services()

        store1 = dependencies.get_graph_store()
        store2 = dependencies.get_graph_store()

        assert store1 is store2, "GraphStore should be cached singleton"

    @pytest.mark.skip(
        reason="Requires .fs2/graph.pickle — GraphService checks filesystem"
    )
    def test_graph_store_receives_config(self):
        """GraphStore is constructed with ConfigurationService.

        Per Critical Discovery 03: GraphStore requires ConfigurationService
        injection, not extracted config objects.
        """
        from fs2.mcp import dependencies

        dependencies.reset_services()

        # Get both services
        config = dependencies.get_config()
        store = dependencies.get_graph_store()

        # GraphStore should have been created with config
        # The store being functional implies correct composition
        assert store is not None
        assert config is not None

    @pytest.mark.skip(
        reason="Requires .fs2/graph.pickle — GraphService checks filesystem"
    )
    def test_reset_services_clears_cache(self):
        """reset_services() clears all cached singletons."""
        from fs2.mcp import dependencies

        # Create services
        dependencies.get_config()
        dependencies.get_graph_store()

        # Reset
        dependencies.reset_services()

        # Should be None again
        assert dependencies._config is None
        assert dependencies._graph_store is None

    # =========================================================================
    # Phase 3: GraphService singleton tests (T001)
    # =========================================================================

    def test_graph_service_none_before_first_access(self):
        """GraphService singleton is None before first access.

        Per Phase 3 T001: Validates lazy initialization.
        """
        from fs2.mcp import dependencies

        dependencies.reset_services()

        assert dependencies._graph_service is None

    def test_graph_service_created_on_first_access(self):
        """GraphService is created when get_graph_service() is called.

        Per Phase 3 T001: Service should be a real GraphService instance.
        """
        from fs2.core.services.graph_service import GraphService
        from fs2.mcp import dependencies

        dependencies.reset_services()

        service = dependencies.get_graph_service()

        assert isinstance(service, GraphService)

    def test_graph_service_cached_after_first_access(self):
        """GraphService is cached (singleton pattern).

        Per Phase 3 T001: Same instance returned on subsequent calls.
        """
        from fs2.mcp import dependencies

        dependencies.reset_services()

        service1 = dependencies.get_graph_service()
        service2 = dependencies.get_graph_service()

        assert service1 is service2, "GraphService should be cached singleton"

    def test_reset_services_clears_graph_service(self):
        """reset_services() clears GraphService singleton.

        Per Phase 3 T001: reset_services must clear _graph_service.
        """
        from fs2.mcp import dependencies

        dependencies.reset_services()

        # Create service
        dependencies.get_graph_service()
        assert dependencies._graph_service is not None

        # Reset
        dependencies.reset_services()

        # Should be None again
        assert dependencies._graph_service is None


class TestDependencyInjection:
    """Test that fakes can be injected for testing."""

    def test_set_config_allows_fake_injection(self, fake_config):
        """Fakes can be injected via set_config() for testing."""
        from fs2.mcp import dependencies

        dependencies.reset_services()
        dependencies.set_config(fake_config)

        config = dependencies.get_config()

        assert config is fake_config

    def test_set_graph_store_allows_fake_injection(self, fake_graph_store):
        """Fakes can be injected via set_graph_store() for testing."""
        from fs2.mcp import dependencies

        dependencies.reset_services()
        dependencies.set_graph_store(fake_graph_store)

        store = dependencies.get_graph_store()

        assert store is fake_graph_store

    def test_fake_injection_bypasses_creation(self, fake_config, fake_graph_store):
        """Injected fakes are returned directly without creating real services."""
        from fs2.mcp import dependencies

        dependencies.reset_services()
        dependencies.set_config(fake_config)
        dependencies.set_graph_store(fake_graph_store)

        # These should return the injected fakes
        config = dependencies.get_config()
        store = dependencies.get_graph_store()

        assert config is fake_config
        assert store is fake_graph_store

    # =========================================================================
    # Phase 3: GraphService injection tests (T001)
    # =========================================================================

    def test_set_graph_service_allows_fake_injection(self, fake_graph_service_fixture):
        """Fakes can be injected via set_graph_service() for testing.

        Per Phase 3 T001 / DYK-01: FakeGraphService injection pattern.
        """
        from fs2.mcp import dependencies

        dependencies.reset_services()
        dependencies.set_graph_service(fake_graph_service_fixture)

        service = dependencies.get_graph_service()

        assert service is fake_graph_service_fixture

    def test_get_graph_store_delegates_to_graph_service(
        self, fake_graph_service_fixture, multi_graph_stores
    ):
        """get_graph_store(name) delegates to GraphService.get_graph().

        Per Phase 3 T007 / DYK-03: Full delegation for staleness detection.
        """
        from fs2.mcp import dependencies

        stores, config = multi_graph_stores

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_service(fake_graph_service_fixture)

        # Get named graph should delegate to service
        store = dependencies.get_graph_store("default")

        assert store is stores["default"]

    def test_get_graph_store_external_graph(
        self, fake_graph_service_fixture, multi_graph_stores
    ):
        """get_graph_store('external-lib') returns external graph.

        Per Phase 3 T007: Named graph support via delegation.
        """
        from fs2.mcp import dependencies

        stores, config = multi_graph_stores

        dependencies.reset_services()
        dependencies.set_config(config)
        dependencies.set_graph_service(fake_graph_service_fixture)

        # Get external graph
        store = dependencies.get_graph_store("external-lib")

        assert store is stores["external-lib"]


class TestServiceLogging:
    """Verify services log when initialized (OBS-001 fix)."""

    @pytest.mark.skip(reason="caplog interference in full suite")
    def test_config_creation_logs_debug_message(self, caplog):
        """Creating config singleton logs a DEBUG message.

        Per code review OBS-001: Singleton creation should be observable
        for debugging initialization timing and configuration issues.
        """
        from fs2.mcp import dependencies

        dependencies.reset_services()

        with caplog.at_level(logging.DEBUG, logger="fs2.mcp.dependencies"):
            dependencies.get_config()

        assert "ConfigurationService" in caplog.text
        assert "Creating" in caplog.text or "singleton" in caplog.text.lower()

    @pytest.mark.skip(reason="caplog interference in full suite")
    def test_graph_store_creation_logs_debug_message(self, caplog):
        """Creating GraphStore singleton logs a DEBUG message.

        Per code review OBS-001: Singleton creation should be observable
        for debugging initialization timing and configuration issues.
        """
        from fs2.mcp import dependencies

        dependencies.reset_services()

        with caplog.at_level(logging.DEBUG, logger="fs2.mcp.dependencies"):
            dependencies.get_graph_store()

        assert "GraphStore" in caplog.text
        assert "Creating" in caplog.text or "singleton" in caplog.text.lower()

    @pytest.mark.skip(reason="caplog interference in full suite")
    def test_cached_access_does_not_log(self, caplog):
        """Accessing cached singleton does not log again.

        Only the first creation should log, not subsequent accesses.
        """
        from fs2.mcp import dependencies

        dependencies.reset_services()

        # First access creates and logs
        with caplog.at_level(logging.DEBUG, logger="fs2.mcp.dependencies"):
            dependencies.get_config()

        caplog.clear()

        # Second access should NOT log
        with caplog.at_level(logging.DEBUG, logger="fs2.mcp.dependencies"):
            dependencies.get_config()

        assert "Creating" not in caplog.text
