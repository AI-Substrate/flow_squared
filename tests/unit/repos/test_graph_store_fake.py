"""Tests for FakeGraphStore test double.

Tasks: T005-T009
Purpose: Verify FakeGraphStore implements GraphStore ABC correctly.
"""

import pytest
from pathlib import Path


@pytest.mark.unit
class TestFakeGraphStore:
    """Tests for FakeGraphStore test double (T005-T009)."""

    def test_fake_graph_store_accepts_configuration_service(self):
        """
        Purpose: Verifies FakeGraphStore follows ConfigurationService pattern.
        Quality Contribution: Ensures consistent DI across all repositories.
        Acceptance Criteria: Construction with ConfigurationService succeeds.

        Task: T005 (partial)
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.repos.graph_store_fake import FakeGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config)

        assert store is not None

    def test_fake_graph_store_inherits_from_graph_store(self):
        """
        Purpose: Verifies FakeGraphStore is a proper GraphStore implementation.
        Quality Contribution: Ensures polymorphism works correctly.
        Acceptance Criteria: FakeGraphStore is instance of GraphStore.

        Task: T008
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.repos.graph_store import GraphStore
        from fs2.core.repos.graph_store_fake import FakeGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config)

        assert isinstance(store, GraphStore)

    def test_fake_graph_store_configurable_results(self):
        """
        Purpose: Verifies FakeGraphStore returns pre-configured nodes.
        Quality Contribution: Enables deterministic testing of dependent code.
        Acceptance Criteria: get_all_nodes() returns exactly the configured nodes.

        Task: T005
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.repos.graph_store_fake import FakeGraphStore
        from fs2.core.models.code_node import CodeNode

        config = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config)

        # Create test nodes
        node1 = CodeNode.create_file(
            file_path="src/main.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# test",
        )
        node2 = CodeNode.create_file(
            file_path="src/util.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=50,
            start_line=1,
            end_line=5,
            content="# util",
        )

        # Configure with set_nodes
        store.set_nodes([node1, node2])

        result = store.get_all_nodes()

        assert len(result) == 2
        assert node1 in result
        assert node2 in result

    def test_fake_graph_store_records_add_node_calls(self):
        """
        Purpose: Verifies FakeGraphStore tracks add_node calls for verification.
        Quality Contribution: Enables assertions on store usage in tests.
        Acceptance Criteria: call_history contains add_node call after add_node().

        Task: T006
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.repos.graph_store_fake import FakeGraphStore
        from fs2.core.models.code_node import CodeNode

        config = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config)

        node = CodeNode.create_file(
            file_path="src/main.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# test",
        )

        store.add_node(node)

        assert len(store.call_history) >= 1
        add_node_calls = [c for c in store.call_history if c["method"] == "add_node"]
        assert len(add_node_calls) == 1
        assert add_node_calls[0]["args"][0] == node

    def test_fake_graph_store_records_add_edge_calls(self):
        """
        Purpose: Verifies FakeGraphStore tracks add_edge calls for verification.
        Quality Contribution: Enables assertions on edge creation in tests.
        Acceptance Criteria: call_history contains add_edge call after add_edge().

        Task: T006
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.repos.graph_store_fake import FakeGraphStore
        from fs2.core.models.code_node import CodeNode

        config = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config)

        # Add two nodes first
        parent = CodeNode.create_file(
            file_path="src/main.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# test",
        )
        child = CodeNode.create_callable(
            file_path="src/main.py",
            language="python",
            ts_kind="function_definition",
            name="main",
            qualified_name="main",
            start_line=1,
            end_line=5,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=50,
            content="def main(): pass",
            signature="def main():",
        )
        store.add_node(parent)
        store.add_node(child)

        store.add_edge(parent.node_id, child.node_id)

        add_edge_calls = [c for c in store.call_history if c["method"] == "add_edge"]
        assert len(add_edge_calls) == 1
        assert add_edge_calls[0]["args"] == (parent.node_id, child.node_id)

    def test_fake_graph_store_records_save_calls(self):
        """
        Purpose: Verifies FakeGraphStore tracks save calls for verification.
        Quality Contribution: Enables assertions on persistence in tests.
        Acceptance Criteria: call_history contains save call after save().

        Task: T006
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.repos.graph_store_fake import FakeGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config)

        store.save(Path("/fake/path.pickle"))

        save_calls = [c for c in store.call_history if c["method"] == "save"]
        assert len(save_calls) == 1
        assert save_calls[0]["args"][0] == Path("/fake/path.pickle")

    def test_fake_graph_store_error_simulation_for_save(self):
        """
        Purpose: Verifies FakeGraphStore can simulate errors for testing.
        Quality Contribution: Enables error handling tests in dependent code.
        Acceptance Criteria: simulate_error_for causes operation to raise.

        Task: T007
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.repos.graph_store_fake import FakeGraphStore
        from fs2.core.adapters.exceptions import GraphStoreError

        config = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config)

        store.simulate_error_for.add("save")

        with pytest.raises(GraphStoreError):
            store.save(Path("/fake/path.pickle"))

    def test_fake_graph_store_error_simulation_for_load(self):
        """
        Purpose: Verifies FakeGraphStore can simulate load errors.
        Quality Contribution: Enables load error handling tests.
        Acceptance Criteria: simulate_error_for("load") causes load to raise.

        Task: T007
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.repos.graph_store_fake import FakeGraphStore
        from fs2.core.adapters.exceptions import GraphStoreError

        config = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config)

        store.simulate_error_for.add("load")

        with pytest.raises(GraphStoreError):
            store.load(Path("/fake/path.pickle"))

    def test_fake_graph_store_in_memory_storage(self):
        """
        Purpose: Verifies FakeGraphStore stores nodes in memory without persistence.
        Quality Contribution: Enables testing without file I/O.
        Acceptance Criteria: Nodes added via add_node are queryable via get_node.

        Task: T009
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.repos.graph_store_fake import FakeGraphStore
        from fs2.core.models.code_node import CodeNode

        config = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config)

        node = CodeNode.create_file(
            file_path="src/main.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# test",
        )

        store.add_node(node)

        result = store.get_node(node.node_id)
        assert result == node

    def test_fake_graph_store_in_memory_edges(self):
        """
        Purpose: Verifies FakeGraphStore stores edges in memory.
        Quality Contribution: Enables testing of hierarchy without file I/O.
        Acceptance Criteria: get_children returns nodes connected via add_edge.

        Task: T009
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.repos.graph_store_fake import FakeGraphStore
        from fs2.core.models.code_node import CodeNode

        config = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config)

        parent = CodeNode.create_file(
            file_path="src/main.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# test",
        )
        child = CodeNode.create_callable(
            file_path="src/main.py",
            language="python",
            ts_kind="function_definition",
            name="main",
            qualified_name="main",
            start_line=1,
            end_line=5,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=50,
            content="def main(): pass",
            signature="def main():",
        )

        store.add_node(parent)
        store.add_node(child)
        store.add_edge(parent.node_id, child.node_id)

        children = store.get_children(parent.node_id)
        assert len(children) == 1
        assert children[0] == child

    def test_fake_graph_store_get_parent_returns_parent(self):
        """
        Purpose: Verifies get_parent returns the parent node.
        Quality Contribution: Tests hierarchy navigation in fake.
        Acceptance Criteria: get_parent returns node connected as parent.

        Task: T009
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.repos.graph_store_fake import FakeGraphStore
        from fs2.core.models.code_node import CodeNode

        config = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config)

        parent = CodeNode.create_file(
            file_path="src/main.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# test",
        )
        child = CodeNode.create_callable(
            file_path="src/main.py",
            language="python",
            ts_kind="function_definition",
            name="main",
            qualified_name="main",
            start_line=1,
            end_line=5,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=50,
            content="def main(): pass",
            signature="def main():",
        )

        store.add_node(parent)
        store.add_node(child)
        store.add_edge(parent.node_id, child.node_id)

        result = store.get_parent(child.node_id)
        assert result == parent

    def test_fake_graph_store_clear_removes_all(self):
        """
        Purpose: Verifies clear() removes all nodes and edges.
        Quality Contribution: Tests reset functionality.
        Acceptance Criteria: After clear, get_all_nodes returns empty list.

        Task: T009
        """
        from fs2.config.service import FakeConfigurationService
        from fs2.config.objects import ScanConfig
        from fs2.core.repos.graph_store_fake import FakeGraphStore
        from fs2.core.models.code_node import CodeNode

        config = FakeConfigurationService(ScanConfig())
        store = FakeGraphStore(config)

        node = CodeNode.create_file(
            file_path="src/main.py",
            language="python",
            ts_kind="module",
            start_byte=0,
            end_byte=100,
            start_line=1,
            end_line=10,
            content="# test",
        )
        store.add_node(node)
        assert len(store.get_all_nodes()) == 1

        store.clear()

        assert len(store.get_all_nodes()) == 0
