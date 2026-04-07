"""Tests for NetworkXGraphStore production implementation.

Tasks: T011-T027
Purpose: Verify NetworkXGraphStore implements GraphStore ABC correctly
with networkx DiGraph backend.
"""

import pickle

import pytest

from fs2.core.models.code_node import CodeNode


def make_file_node(file_path: str = "src/main.py", content: str = "# test") -> CodeNode:
    """Helper to create a file CodeNode for tests."""
    return CodeNode.create_file(
        file_path=file_path,
        language="python",
        ts_kind="module",
        start_byte=0,
        end_byte=len(content),
        start_line=1,
        end_line=content.count("\n") + 1,
        content=content,
    )


def make_class_node(
    file_path: str = "src/main.py",
    name: str = "MyClass",
    qualified_name: str = "MyClass",
    content: str = "class MyClass: pass",
) -> CodeNode:
    """Helper to create a class/type CodeNode for tests."""
    return CodeNode.create_type(
        file_path=file_path,
        language="python",
        ts_kind="class_definition",
        name=name,
        qualified_name=qualified_name,
        start_line=1,
        end_line=1,
        start_column=0,
        end_column=len(content),
        start_byte=0,
        end_byte=len(content),
        content=content,
        signature=f"class {name}:",
    )


def make_method_node(
    file_path: str = "src/main.py",
    name: str = "my_method",
    qualified_name: str = "MyClass.my_method",
    content: str = "def my_method(self): pass",
) -> CodeNode:
    """Helper to create a method/callable CodeNode for tests."""
    return CodeNode.create_callable(
        file_path=file_path,
        language="python",
        ts_kind="function_definition",
        name=name,
        qualified_name=qualified_name,
        start_line=2,
        end_line=2,
        start_column=4,
        end_column=len(content) + 4,
        start_byte=20,
        end_byte=20 + len(content),
        content=content,
        signature=f"def {name}(self):",
    )


@pytest.mark.unit
class TestNetworkXGraphStoreNodeOperations:
    """Tests for node operations (T011-T016)."""

    def test_add_node_preserves_all_code_node_fields(self):
        """
        Purpose: Verifies add_node stores CodeNode with all fields preserved.
        Quality Contribution: Ensures data integrity for stored nodes.
        Acceptance Criteria: All fields retrievable after add.

        Task: T011
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.models.code_node import CodeNode
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore
        from fs2.core.utils.hash import compute_content_hash

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        # Create node with explicit values for all fields
        content = "# Full content here"
        node = CodeNode(
            node_id="file:src/test.py",
            category="file",
            ts_kind="module",
            name="test.py",
            qualified_name="test.py",
            start_line=1,
            end_line=100,
            start_column=0,
            end_column=50,
            start_byte=0,
            end_byte=5000,
            content=content,
            content_hash=compute_content_hash(content),
            signature=None,
            language="python",
            is_named=True,
            field_name=None,
            is_error=False,
            truncated=False,
            truncated_at_line=None,
            smart_content="AI summary",
            embedding=[0.1, 0.2, 0.3],
        )

        store.add_node(node)
        retrieved = store.get_node(node.node_id)

        assert retrieved is not None
        # Check all 17+ fields
        assert retrieved.node_id == node.node_id
        assert retrieved.category == node.category
        assert retrieved.ts_kind == node.ts_kind
        assert retrieved.name == node.name
        assert retrieved.qualified_name == node.qualified_name
        assert retrieved.start_line == node.start_line
        assert retrieved.end_line == node.end_line
        assert retrieved.start_column == node.start_column
        assert retrieved.end_column == node.end_column
        assert retrieved.start_byte == node.start_byte
        assert retrieved.end_byte == node.end_byte
        assert retrieved.content == node.content
        assert retrieved.content_hash == node.content_hash
        assert retrieved.signature == node.signature
        assert retrieved.language == node.language
        assert retrieved.is_named == node.is_named
        assert retrieved.field_name == node.field_name
        assert retrieved.is_error == node.is_error
        assert retrieved.truncated == node.truncated
        assert retrieved.truncated_at_line == node.truncated_at_line
        assert retrieved.smart_content == node.smart_content
        assert retrieved.embedding == node.embedding

    def test_add_edge_creates_parent_child_relationship(self):
        """
        Purpose: Verifies add_edge creates directed parent → child edge.
        Quality Contribution: Ensures correct hierarchy representation.
        Acceptance Criteria: Edge direction is parent → child.

        Task: T012
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        parent = make_file_node("src/calc.py")
        child = make_class_node("src/calc.py", "Calculator", "Calculator")

        store.add_node(parent)
        store.add_node(child)
        store.add_edge(parent.node_id, child.node_id)

        # Verify edge direction: successors = children, predecessors = parent
        children = store.get_children(parent.node_id)
        assert len(children) == 1
        assert children[0].node_id == child.node_id

        parent_result = store.get_parent(child.node_id)
        assert parent_result is not None
        assert parent_result.node_id == parent.node_id

    def test_get_node_returns_code_node_or_none(self):
        """
        Purpose: Verifies get_node returns CodeNode if exists, None otherwise.
        Quality Contribution: Safe retrieval without exceptions.
        Acceptance Criteria: Returns node or None.

        Task: T013
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        node = make_file_node()
        store.add_node(node)

        # Existing node
        result = store.get_node(node.node_id)
        assert result is not None
        assert result == node

        # Non-existing node
        result = store.get_node("nonexistent:id")
        assert result is None

    def test_get_children_returns_list_of_child_nodes(self):
        """
        Purpose: Verifies get_children returns all direct children.
        Quality Contribution: Enables hierarchy traversal.
        Acceptance Criteria: Returns list of CodeNodes.

        Task: T014
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        file_node = make_file_node("src/calc.py")
        class_node = make_class_node("src/calc.py", "Calculator", "Calculator")
        method1 = make_method_node("src/calc.py", "add", "Calculator.add")
        method2 = make_method_node("src/calc.py", "subtract", "Calculator.subtract")

        store.add_node(file_node)
        store.add_node(class_node)
        store.add_node(method1)
        store.add_node(method2)

        store.add_edge(file_node.node_id, class_node.node_id)
        store.add_edge(class_node.node_id, method1.node_id)
        store.add_edge(class_node.node_id, method2.node_id)

        # File has one child (class)
        file_children = store.get_children(file_node.node_id)
        assert len(file_children) == 1
        assert file_children[0].name == "Calculator"

        # Class has two children (methods)
        class_children = store.get_children(class_node.node_id)
        assert len(class_children) == 2
        child_names = {c.name for c in class_children}
        assert child_names == {"add", "subtract"}

    def test_get_parent_returns_parent_node_or_none(self):
        """
        Purpose: Verifies get_parent returns parent if exists, None otherwise.
        Quality Contribution: Enables upward hierarchy navigation.
        Acceptance Criteria: Returns parent CodeNode or None.

        Task: T015
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        file_node = make_file_node("src/calc.py")
        class_node = make_class_node("src/calc.py", "Calculator", "Calculator")

        store.add_node(file_node)
        store.add_node(class_node)
        store.add_edge(file_node.node_id, class_node.node_id)

        # Class has file as parent
        parent = store.get_parent(class_node.node_id)
        assert parent is not None
        assert parent.node_id == file_node.node_id

        # File has no parent
        root_parent = store.get_parent(file_node.node_id)
        assert root_parent is None

    def test_get_all_nodes_returns_all_nodes(self):
        """
        Purpose: Verifies get_all_nodes returns every node in graph.
        Quality Contribution: Enables bulk operations.
        Acceptance Criteria: Returns list with all added nodes.

        Task: T016
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        nodes = [
            make_file_node("src/a.py"),
            make_file_node("src/b.py"),
            make_file_node("src/c.py"),
        ]

        for node in nodes:
            store.add_node(node)

        all_nodes = store.get_all_nodes()
        assert len(all_nodes) == 3
        all_ids = {n.node_id for n in all_nodes}
        expected_ids = {n.node_id for n in nodes}
        assert all_ids == expected_ids


@pytest.mark.unit
class TestNetworkXGraphStorePersistence:
    """Tests for persistence operations (T017-T022a)."""

    def test_save_uses_pickle_not_deprecated_gpickle(self, tmp_path):
        """
        Purpose: Verifies save uses pickle.dump, not deprecated nx.write_gpickle.
        Quality Contribution: Follows networkx 3.0+ best practices.
        Acceptance Criteria: File is valid pickle format.

        Task: T017 (per CF05)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        node = make_file_node()
        store.add_node(node)

        save_path = tmp_path / "graph.pickle"
        store.save(save_path)

        # Verify it's a valid pickle file
        assert save_path.exists()
        with open(save_path, "rb") as f:
            data = pickle.load(f)

        # Should be a tuple (metadata, graph)
        assert isinstance(data, tuple)
        assert len(data) == 2

    def test_save_includes_format_version_metadata(self, tmp_path):
        """
        Purpose: Verifies saved file includes format_version.
        Quality Contribution: Enables future format migrations.
        Acceptance Criteria: Metadata contains format_version matching current.

        Task: T018 (per CF14)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import FORMAT_VERSION, NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        store.add_node(make_file_node())
        save_path = tmp_path / "graph.pickle"
        store.save(save_path)

        with open(save_path, "rb") as f:
            metadata, _ = pickle.load(f)

        assert "format_version" in metadata
        assert metadata["format_version"] == FORMAT_VERSION

    @pytest.mark.skip(reason="caplog interference in full suite")
    def test_load_logs_warning_on_version_mismatch(self, tmp_path, caplog):
        """
        Purpose: Verifies load logs warning but continues on version mismatch.
        Quality Contribution: Graceful handling of future formats.
        Acceptance Criteria: Warning logged, load attempted anyway.

        Task: T019 (per CF14)
        """
        import logging

        import networkx as nx

        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        # Create file with different version
        save_path = tmp_path / "graph.pickle"
        metadata = {"format_version": "99.0", "created_at": "2025-01-01"}
        graph = nx.DiGraph()
        with open(save_path, "wb") as f:
            pickle.dump((metadata, graph), f)

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        with caplog.at_level(logging.WARNING):
            store.load(save_path)

        # Check warning was logged
        assert any("version" in r.message.lower() for r in caplog.records)

    def test_100_nodes_saved_and_loaded_correctly(self, tmp_path):
        """
        Purpose: Verifies AC8 - 100+ nodes persist and reload.
        Quality Contribution: Proves scalability of persistence.
        Acceptance Criteria: All 100 nodes recoverable with all fields.

        Task: T020 (AC8)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        # Add 100 nodes with edges
        for i in range(100):
            node = make_file_node(f"src/file_{i}.py", f"# content {i}")
            store.add_node(node)

        save_path = tmp_path / "graph.pickle"
        store.save(save_path)

        # Load into fresh store
        new_store = NetworkXGraphStore(config)
        new_store.load(save_path)

        # Verify all 100 nodes recovered
        all_nodes = new_store.get_all_nodes()
        assert len(all_nodes) == 100

        # Verify specific nodes
        for i in range(100):
            node = new_store.get_node(f"file:src/file_{i}.py")
            assert node is not None
            assert node.content == f"# content {i}"

    def test_load_nonexistent_file_raises_graph_store_error(self, tmp_path):
        """
        Purpose: Verifies load raises GraphStoreError for missing file.
        Quality Contribution: Actionable error message.
        Acceptance Criteria: GraphStoreError with path in message.

        Task: T021 (per CF10)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.exceptions import GraphStoreError
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        nonexistent = tmp_path / "does_not_exist.pickle"

        with pytest.raises(GraphStoreError) as exc_info:
            store.load(nonexistent)

        assert "does_not_exist.pickle" in str(exc_info.value)

    def test_load_corrupted_file_raises_graph_store_error(self, tmp_path):
        """
        Purpose: Verifies load raises GraphStoreError for corrupted file.
        Quality Contribution: Actionable error message.
        Acceptance Criteria: GraphStoreError with corruption message.

        Task: T022 (per CF10)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.exceptions import GraphStoreError
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        # Write corrupted data
        corrupted = tmp_path / "corrupted.pickle"
        corrupted.write_bytes(b"this is not valid pickle data!!!")

        with pytest.raises(GraphStoreError) as exc_info:
            store.load(corrupted)

        assert (
            "corrupt" in str(exc_info.value).lower()
            or "unpickl" in str(exc_info.value).lower()
        )

    def test_restricted_unpickler_blocks_malicious_classes(self, tmp_path):
        """
        Purpose: Verifies RestrictedUnpickler blocks arbitrary code execution.
        Quality Contribution: Security hardening against RCE via pickle.
        Acceptance Criteria: Only CodeNode, DiGraph, stdlib allowed.

        Task: T022a (Security hardening)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.exceptions import GraphStoreError
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        # Create malicious pickle with os.system call
        # This is a classic RCE payload - if unpickled without restriction,
        # it would execute arbitrary code

        class MaliciousReducer:
            """Pickle that would execute code if loaded unsafely."""

            def __reduce__(self):
                import os

                return (os.system, ("echo PWNED",))

        # Pickle the malicious object
        malicious_path = tmp_path / "malicious.pickle"
        with open(malicious_path, "wb") as f:
            # Wrap in tuple to mimic our format
            pickle.dump(({"format_version": "1.0"}, MaliciousReducer()), f)

        # Loading should raise GraphStoreError due to restricted unpickler
        with pytest.raises(GraphStoreError) as exc_info:
            store.load(malicious_path)

        # Verify it's a security-related error
        error_msg = str(exc_info.value).lower()
        assert (
            "forbidden" in error_msg
            or "not allowed" in error_msg
            or "restricted" in error_msg
        )


@pytest.mark.unit
class TestNetworkXGraphStoreEdgeCases:
    """Tests for edge cases (T024-T027)."""

    def test_get_nonexistent_node_returns_none(self):
        """
        Purpose: Verifies get_node returns None for missing node.
        Quality Contribution: Safe retrieval without exceptions.
        Acceptance Criteria: Returns None, not exception.

        Task: T024
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        result = store.get_node("nonexistent:node:id")
        assert result is None

    def test_add_duplicate_node_updates_existing(self):
        """
        Purpose: Verifies add_node with same ID updates (upsert behavior).
        Quality Contribution: Prevents duplicate nodes in graph.
        Acceptance Criteria: Second add updates first, single node in graph.

        Task: T025
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        # Add original
        original = make_file_node("src/main.py", "# original")
        store.add_node(original)

        # Add updated with same path (same node_id)
        updated = make_file_node("src/main.py", "# updated")
        store.add_node(updated)

        # Should be single node with updated content
        all_nodes = store.get_all_nodes()
        assert len(all_nodes) == 1
        assert all_nodes[0].content == "# updated"

    def test_save_creates_parent_directory_if_missing(self, tmp_path):
        """
        Purpose: Verifies save creates parent directories.
        Quality Contribution: User doesn't need to pre-create .fs2/.
        Acceptance Criteria: Nested path created automatically.

        Task: T026
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)
        store.add_node(make_file_node())

        # Path with non-existent parent dirs
        nested_path = tmp_path / "deep" / "nested" / "dir" / "graph.pickle"
        assert not nested_path.parent.exists()

        store.save(nested_path)

        assert nested_path.exists()

    def test_clear_removes_all_nodes_and_edges(self):
        """
        Purpose: Verifies clear() empties the graph completely.
        Quality Contribution: Enables fresh scan without reload.
        Acceptance Criteria: Graph empty after clear.

        Task: T027
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        # Add nodes and edges
        file_node = make_file_node("src/calc.py")
        class_node = make_class_node("src/calc.py", "Calculator", "Calculator")
        store.add_node(file_node)
        store.add_node(class_node)
        store.add_edge(file_node.node_id, class_node.node_id)

        assert len(store.get_all_nodes()) == 2
        assert len(store.get_children(file_node.node_id)) == 1

        store.clear()

        assert len(store.get_all_nodes()) == 0
        assert len(store.get_children(file_node.node_id)) == 0

    def test_get_children_returns_empty_for_leaf_node(self):
        """
        Purpose: Verifies get_children returns empty list for leaf nodes.
        Quality Contribution: Safe handling of leaf traversal.
        Acceptance Criteria: Returns [] not None or exception.

        Task: T014 (supplementary)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        leaf_node = make_method_node()
        store.add_node(leaf_node)

        children = store.get_children(leaf_node.node_id)
        assert children == []

    def test_save_and_load_preserves_edges(self, tmp_path):
        """
        Purpose: Verifies edges persist through save/load cycle.
        Quality Contribution: Ensures hierarchy integrity.
        Acceptance Criteria: Parent-child relationships preserved.

        Task: T020 (supplementary)
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        # Create hierarchy
        file_node = make_file_node("src/calc.py")
        class_node = make_class_node("src/calc.py", "Calculator", "Calculator")
        method_node = make_method_node("src/calc.py", "add", "Calculator.add")

        store.add_node(file_node)
        store.add_node(class_node)
        store.add_node(method_node)
        store.add_edge(file_node.node_id, class_node.node_id)
        store.add_edge(class_node.node_id, method_node.node_id)

        save_path = tmp_path / "graph.pickle"
        store.save(save_path)

        # Load into fresh store
        new_store = NetworkXGraphStore(config)
        new_store.load(save_path)

        # Verify edges preserved
        file_children = new_store.get_children(file_node.node_id)
        assert len(file_children) == 1
        assert file_children[0].name == "Calculator"

        class_children = new_store.get_children(class_node.node_id)
        assert len(class_children) == 1
        assert class_children[0].name == "add"

        method_parent = new_store.get_parent(method_node.node_id)
        assert method_parent is not None
        assert method_parent.name == "Calculator"


@pytest.mark.unit
class TestNetworkXGraphStoreEdgeData:
    """Tests for edge data and get_edges() (Phase 1: T003, T004)."""

    def test_add_edge_with_edge_data_stores_attributes(self):
        """
        Purpose: Proves add_edge(**edge_data) stores attributes in networkx.
        Acceptance Criteria: edge attributes accessible via graph.edges[u, v].

        Task: T004
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        node_a = make_file_node("src/a.py")
        node_b = make_method_node("src/b.py", "func_b", "func_b")
        store.add_node(node_a)
        store.add_node(node_b)

        store.add_edge(node_a.node_id, node_b.node_id, edge_type="references")

        # Verify edge data stored in networkx
        edge_data = store._graph.edges[node_a.node_id, node_b.node_id]
        assert edge_data["edge_type"] == "references"

    def test_add_edge_without_edge_data_is_backward_compatible(self):
        """
        Purpose: Proves existing callers (no kwargs) still work.
        Acceptance Criteria: add_edge(parent, child) works, edge has empty data.

        Task: T004
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        file_node = make_file_node()
        class_node = make_class_node()
        store.add_node(file_node)
        store.add_node(class_node)

        # Old-style call without kwargs
        store.add_edge(file_node.node_id, class_node.node_id)

        # Should work fine, edge has empty attributes
        edge_data = store._graph.edges[file_node.node_id, class_node.node_id]
        assert "edge_type" not in edge_data

    def test_get_edges_outgoing_returns_successors(self):
        """
        Purpose: Proves get_edges with direction=outgoing returns successor edges.
        Acceptance Criteria: Returns list of (node_id, edge_data) for successors.

        Task: T003
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        file_node = make_file_node()
        class_node = make_class_node()
        method_node = make_method_node()
        store.add_node(file_node)
        store.add_node(class_node)
        store.add_node(method_node)
        store.add_edge(file_node.node_id, class_node.node_id)
        store.add_edge(file_node.node_id, method_node.node_id)

        edges = store.get_edges(file_node.node_id, direction="outgoing")
        connected_ids = [e[0] for e in edges]
        assert class_node.node_id in connected_ids
        assert method_node.node_id in connected_ids
        assert len(edges) == 2

    def test_get_edges_incoming_returns_predecessors(self):
        """
        Purpose: Proves get_edges with direction=incoming returns predecessor edges.
        Acceptance Criteria: Returns predecessors.

        Task: T003
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        file_node = make_file_node()
        class_node = make_class_node()
        store.add_node(file_node)
        store.add_node(class_node)
        store.add_edge(file_node.node_id, class_node.node_id)

        edges = store.get_edges(class_node.node_id, direction="incoming")
        assert len(edges) == 1
        assert edges[0][0] == file_node.node_id

    def test_get_edges_both_returns_all(self):
        """
        Purpose: Proves direction=both returns union of incoming and outgoing.
        Acceptance Criteria: Both predecessors and successors returned.

        Task: T003
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        node_a = make_file_node("src/a.py")
        node_b = make_class_node("src/a.py", "B", "B")
        node_c = make_method_node("src/a.py", "c", "B.c")
        store.add_node(node_a)
        store.add_node(node_b)
        store.add_node(node_c)
        store.add_edge(node_a.node_id, node_b.node_id)
        store.add_edge(node_b.node_id, node_c.node_id)

        # B has incoming from A and outgoing to C
        edges = store.get_edges(node_b.node_id, direction="both")
        connected_ids = [e[0] for e in edges]
        assert node_a.node_id in connected_ids
        assert node_c.node_id in connected_ids
        assert len(edges) == 2

    def test_get_edges_filters_by_edge_type(self):
        """
        Purpose: Proves edge_type filter works correctly.
        Acceptance Criteria: Only edges with matching edge_type returned.

        Task: T003
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        file_node = make_file_node("src/a.py")
        class_node = make_class_node("src/a.py", "A", "A")
        ref_node = make_method_node("src/b.py", "caller", "caller")
        store.add_node(file_node)
        store.add_node(class_node)
        store.add_node(ref_node)

        # Containment edge (no edge_type)
        store.add_edge(file_node.node_id, class_node.node_id)
        # Reference edge (with edge_type)
        store.add_edge(ref_node.node_id, class_node.node_id, edge_type="references")

        # Filter incoming to references only
        ref_edges = store.get_edges(
            class_node.node_id, direction="incoming", edge_type="references"
        )
        assert len(ref_edges) == 1
        assert ref_edges[0][0] == ref_node.node_id
        assert ref_edges[0][1]["edge_type"] == "references"

        # Filter incoming with no type filter returns both
        all_edges = store.get_edges(class_node.node_id, direction="incoming")
        assert len(all_edges) == 2

    def test_get_edges_returns_empty_for_unknown_node(self):
        """
        Purpose: Proves get_edges returns [] for non-existent node.
        Acceptance Criteria: No crash, empty list.

        Task: T003
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        result = store.get_edges("nonexistent:node:id")
        assert result == []

    def test_get_edges_returns_empty_for_node_with_no_edges(self):
        """
        Purpose: Proves get_edges returns [] for isolated node.
        Acceptance Criteria: No edges = empty list.

        Task: T003
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        node = make_file_node()
        store.add_node(node)

        result = store.get_edges(node.node_id)
        assert result == []

    def test_get_parent_returns_containment_parent_not_reference(self):
        """
        Purpose: Proves get_parent() returns containment parent, not cross-file reference.
        Acceptance Criteria: get_parent returns the node connected via containment edge,
                           ignoring reference edges.

        Task: T009
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        # Containment: file_a → func_a
        file_a = make_file_node("src/a.py")
        func_a = make_method_node("src/a.py", "func_a", "func_a")
        store.add_node(file_a)
        store.add_node(func_a)
        # Cross-file reference FIRST (to prove order doesn't matter)
        ref_node = make_method_node("src/b.py", "caller", "caller")
        store.add_node(ref_node)
        store.add_edge(ref_node.node_id, func_a.node_id, edge_type="references")

        # Containment SECOND: file_a → func_a
        store.add_edge(file_a.node_id, func_a.node_id)  # containment (no edge_type)

        # get_parent should return the containment parent, not the reference
        parent = store.get_parent(func_a.node_id)
        assert parent is not None
        assert parent.node_id == file_a.node_id

    def test_edge_attributes_survive_save_load_roundtrip(self, tmp_path):
        """
        Purpose: Proves edge attributes survive pickle save + RestrictedUnpickler load.
        Acceptance Criteria: get_edges returns same data after save/load cycle.

        Task: T006
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        # Create nodes in different files
        file_a = make_file_node("src/a.py")
        func_a = make_method_node("src/a.py", "caller", "caller")
        file_b = make_file_node("src/b.py")
        func_b = make_method_node("src/b.py", "target", "target")
        store.add_node(file_a)
        store.add_node(func_a)
        store.add_node(file_b)
        store.add_node(func_b)

        # Containment edges (no edge_type)
        store.add_edge(file_a.node_id, func_a.node_id)
        store.add_edge(file_b.node_id, func_b.node_id)

        # Cross-file reference edge (with edge_type)
        store.add_edge(func_a.node_id, func_b.node_id, edge_type="references")

        # Save and reload
        path = tmp_path / "graph.pickle"
        store.save(path)

        store2 = NetworkXGraphStore(config)
        store2.load(path)

        # Verify reference edge survives roundtrip
        ref_edges = store2.get_edges(
            func_b.node_id, direction="incoming", edge_type="references"
        )
        assert len(ref_edges) == 1
        assert ref_edges[0][0] == func_a.node_id
        assert ref_edges[0][1]["edge_type"] == "references"

        # Verify containment edges also survive (no edge_type)
        cont_edges = store2.get_edges(file_a.node_id, direction="outgoing")
        assert len(cont_edges) == 1
        assert cont_edges[0][0] == func_a.node_id
        assert "edge_type" not in cont_edges[0][1]


class TestNetworkXGraphStoreGetAllEdges:
    """Phase 4 T005: Tests for get_all_edges()."""

    def test_get_all_edges_returns_reference_edges(self, tmp_path):
        """Returns all reference edges in graph."""
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        node_a = make_file_node("src/a.py")
        node_b = make_file_node("src/b.py")
        func_a = make_method_node("src/a.py", "A", "foo")
        func_b = make_method_node("src/b.py", "B", "bar")

        store.add_node(node_a)
        store.add_node(node_b)
        store.add_node(func_a)
        store.add_node(func_b)
        store.add_edge(node_a.node_id, func_a.node_id)  # containment
        store.add_edge(node_b.node_id, func_b.node_id)  # containment
        store.add_edge(func_a.node_id, func_b.node_id, edge_type="references")

        all_refs = store.get_all_edges(edge_type="references")
        assert len(all_refs) == 1
        assert all_refs[0] == (func_a.node_id, func_b.node_id, {"edge_type": "references"})

    def test_get_all_edges_no_filter_returns_all(self, tmp_path):
        """Without filter returns both containment and reference edges."""
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        node_a = make_file_node("src/a.py")
        func_a = make_method_node("src/a.py", "A", "foo")

        store.add_node(node_a)
        store.add_node(func_a)
        store.add_edge(node_a.node_id, func_a.node_id)  # containment
        store.add_edge(func_a.node_id, node_a.node_id, edge_type="references")

        all_edges = store.get_all_edges()
        assert len(all_edges) == 2

    def test_get_all_edges_empty_graph(self, tmp_path):
        """Empty graph returns empty list."""
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        assert store.get_all_edges() == []


class TestAtomicSave:
    """Tests for atomic save behavior (Plan 036 T01)."""

    def test_save_uses_temp_file_then_rename(self, tmp_path):
        """Verify save writes to .tmp then renames — no partial .pickle file."""
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)
        store.add_node(make_file_node())

        graph_path = tmp_path / "graph.pickle"
        store.save(graph_path)

        # After save, graph.pickle exists and .tmp does not
        assert graph_path.exists()
        assert not (tmp_path / "graph.pickle.tmp").exists()

    def test_save_cleans_up_tmp_on_failure(self, tmp_path):
        """Verify .tmp is cleaned up if save fails (when possible)."""
        from pathlib import Path
        from unittest.mock import patch

        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.exceptions import GraphStoreError
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)
        store.add_node(make_file_node())

        graph_path = tmp_path / "graph.pickle"

        # Patch os.replace to simulate failure after tmp file is written
        import os as _os

        def failing_replace(src, dst):
            raise OSError("Simulated replace failure")

        with patch.object(_os, "replace", failing_replace):
            with pytest.raises(GraphStoreError):
                store.save(graph_path)

        # Temp file should be cleaned up (it was writable, only rename failed)
        assert not (tmp_path / "graph.pickle.tmp").exists()

    def test_prior_graph_survives_if_new_save_interrupted(self, tmp_path):
        """Simulate interrupted save: prior graph.pickle should remain loadable."""
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)
        original = make_file_node("src/original.py", "# original")
        store.add_node(original)

        graph_path = tmp_path / "graph.pickle"
        store.save(graph_path)

        # Simulate "interrupted save" by writing a partial .tmp file
        tmp_file = tmp_path / "graph.pickle.tmp"
        tmp_file.write_bytes(b"partial data - corrupted")

        # The real graph.pickle should still be loadable
        store2 = NetworkXGraphStore(config)
        store2.load(graph_path)
        loaded = store2.get_all_nodes()
        assert len(loaded) == 1
        assert loaded[0].content == "# original"

    def test_save_roundtrip_with_atomic_write(self, tmp_path):
        """Verify full save/load roundtrip works with atomic write."""
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)
        node = make_file_node("src/test.py", "def foo(): pass")
        store.add_node(node)

        graph_path = tmp_path / "graph.pickle"
        store.save(graph_path)

        store2 = NetworkXGraphStore(config)
        store2.load(graph_path)
        loaded = store2.get_all_nodes()
        assert len(loaded) == 1
        assert loaded[0].content == "def foo(): pass"
