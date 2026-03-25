"""Tests for GraphStore ABC contract.

Tasks: T001-T003
Purpose: Verify GraphStore ABC defines correct interface.
"""

from abc import ABC

import pytest


@pytest.mark.unit
class TestGraphStoreABC:
    """Tests for GraphStore ABC contract (T001-T003)."""

    def test_graph_store_abc_cannot_be_instantiated(self):
        """
        Purpose: Proves ABC cannot be directly instantiated.
        Quality Contribution: Enforces interface-only contract.
        Acceptance Criteria: TypeError raised on instantiation.

        Task: T001
        """
        from fs2.core.repos.graph_store import GraphStore

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            GraphStore()

    def test_graph_store_abc_defines_add_node_method(self):
        """
        Purpose: Verifies add_node() is an abstract method.
        Quality Contribution: Ensures implementations provide node addition.
        Acceptance Criteria: add_node in __abstractmethods__.

        Task: T002
        """
        from fs2.core.repos.graph_store import GraphStore

        assert "add_node" in GraphStore.__abstractmethods__

    def test_graph_store_abc_defines_add_edge_method(self):
        """
        Purpose: Verifies add_edge() is an abstract method.
        Quality Contribution: Ensures implementations provide edge addition.
        Acceptance Criteria: add_edge in __abstractmethods__.

        Task: T002
        """
        from fs2.core.repos.graph_store import GraphStore

        assert "add_edge" in GraphStore.__abstractmethods__

    def test_graph_store_abc_defines_get_node_method(self):
        """
        Purpose: Verifies get_node() is an abstract method.
        Quality Contribution: Ensures implementations provide node retrieval.
        Acceptance Criteria: get_node in __abstractmethods__.

        Task: T002
        """
        from fs2.core.repos.graph_store import GraphStore

        assert "get_node" in GraphStore.__abstractmethods__

    def test_graph_store_abc_defines_get_children_method(self):
        """
        Purpose: Verifies get_children() is an abstract method.
        Quality Contribution: Ensures implementations provide hierarchy query.
        Acceptance Criteria: get_children in __abstractmethods__.

        Task: T002
        """
        from fs2.core.repos.graph_store import GraphStore

        assert "get_children" in GraphStore.__abstractmethods__

    def test_graph_store_abc_defines_get_parent_method(self):
        """
        Purpose: Verifies get_parent() is an abstract method.
        Quality Contribution: Ensures implementations provide parent query.
        Acceptance Criteria: get_parent in __abstractmethods__.

        Task: T002
        """
        from fs2.core.repos.graph_store import GraphStore

        assert "get_parent" in GraphStore.__abstractmethods__

    def test_graph_store_abc_defines_get_all_nodes_method(self):
        """
        Purpose: Verifies get_all_nodes() is an abstract method.
        Quality Contribution: Ensures implementations provide bulk retrieval.
        Acceptance Criteria: get_all_nodes in __abstractmethods__.

        Task: T002
        """
        from fs2.core.repos.graph_store import GraphStore

        assert "get_all_nodes" in GraphStore.__abstractmethods__

    def test_graph_store_abc_defines_save_method(self):
        """
        Purpose: Verifies save() is an abstract method.
        Quality Contribution: Ensures implementations provide persistence.
        Acceptance Criteria: save in __abstractmethods__.

        Task: T002
        """
        from fs2.core.repos.graph_store import GraphStore

        assert "save" in GraphStore.__abstractmethods__

    def test_graph_store_abc_defines_load_method(self):
        """
        Purpose: Verifies load() is an abstract method.
        Quality Contribution: Ensures implementations provide loading.
        Acceptance Criteria: load in __abstractmethods__.

        Task: T002
        """
        from fs2.core.repos.graph_store import GraphStore

        assert "load" in GraphStore.__abstractmethods__

    def test_graph_store_abc_defines_clear_method(self):
        """
        Purpose: Verifies clear() is an abstract method.
        Quality Contribution: Ensures implementations provide clearing.
        Acceptance Criteria: clear in __abstractmethods__.

        Task: T002
        """
        from fs2.core.repos.graph_store import GraphStore

        assert "clear" in GraphStore.__abstractmethods__

    def test_graph_store_abc_inherits_from_abc(self):
        """
        Purpose: Verifies GraphStore is a proper ABC.
        Quality Contribution: Ensures abc.ABC pattern followed correctly.
        Acceptance Criteria: GraphStore is subclass of ABC.

        Task: T001 (supplementary)
        """
        from fs2.core.repos.graph_store import GraphStore

        assert issubclass(GraphStore, ABC)

    def test_graph_store_abc_receives_configuration_service(self):
        """
        Purpose: Verifies ABC docstring specifies ConfigurationService pattern.
        Quality Contribution: Documents the CF01 requirement in ABC itself.
        Acceptance Criteria: ABC has docstring mentioning ConfigurationService.

        Task: T003
        """
        from fs2.core.repos.graph_store import GraphStore

        assert GraphStore.__doc__ is not None
        assert "ConfigurationService" in GraphStore.__doc__

    def test_graph_store_abc_defines_get_metadata_method(self):
        """
        Purpose: Verifies get_metadata() is an abstract method.
        Quality Contribution: Ensures implementations provide metadata access.
        Acceptance Criteria: get_metadata in __abstractmethods__.

        Task: T003 (tree command)
        """
        from fs2.core.repos.graph_store import GraphStore

        assert "get_metadata" in GraphStore.__abstractmethods__


@pytest.mark.unit
class TestGraphStoreGetMetadataContract:
    """T003: Tests for GraphStore.get_metadata() contract."""

    def test_given_loaded_graph_when_get_metadata_then_returns_dict(self, tmp_path):
        """
        Purpose: Verifies metadata access after load.
        Quality Contribution: Ensures freshness info available.
        Acceptance Criteria: Returns dict with expected keys.

        Task: T003
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.models.code_node import CodeNode
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        # Add a node and save
        node = CodeNode.create_file(
            "test.py", "python", "module", 0, 100, 1, 10, "# test"
        )
        store.add_node(node)
        graph_path = tmp_path / "test_graph.pickle"
        store.save(graph_path)

        # Create fresh store and load
        store2 = NetworkXGraphStore(config)
        store2.load(graph_path)

        metadata = store2.get_metadata()

        assert isinstance(metadata, dict)
        assert "format_version" in metadata
        assert "created_at" in metadata
        assert "node_count" in metadata
        assert "edge_count" in metadata

    def test_given_no_load_when_get_metadata_then_raises_error(self):
        """
        Purpose: Verifies error when metadata accessed before load.
        Quality Contribution: Prevents silent failures.
        Acceptance Criteria: GraphStoreError raised.

        Task: T003
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.adapters.exceptions import GraphStoreError
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        with pytest.raises(GraphStoreError, match="not loaded"):
            store.get_metadata()

    def test_given_loaded_graph_when_get_metadata_then_node_count_matches(
        self, tmp_path
    ):
        """
        Purpose: Verifies node_count in metadata is accurate.
        Quality Contribution: Ensures correct statistics.
        Acceptance Criteria: node_count matches actual nodes.

        Task: T003
        """
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.models.code_node import CodeNode
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        # Add 3 nodes
        for i in range(3):
            node = CodeNode.create_file(
                f"test{i}.py", "python", "module", 0, 100, 1, 10, f"# test {i}"
            )
            store.add_node(node)

        graph_path = tmp_path / "test_graph.pickle"
        store.save(graph_path)

        # Load and check
        store2 = NetworkXGraphStore(config)
        store2.load(graph_path)

        metadata = store2.get_metadata()
        assert metadata["node_count"] == 3


@pytest.mark.unit
class TestGraphStoreEdgeContract:
    """Tests for GraphStore edge infrastructure (Phase 1: T001, T002)."""

    def test_add_edge_accepts_edge_data_kwargs(self):
        """
        Purpose: Proves add_edge() signature accepts **edge_data.
        Acceptance Criteria: add_edge with edge_type kwarg doesn't raise TypeError.

        Task: T001
        """
        import inspect

        from fs2.core.repos.graph_store import GraphStore

        sig = inspect.signature(GraphStore.add_edge)
        params = list(sig.parameters.values())
        # Should have self, parent_id, child_id, and **edge_data
        param_names = [p.name for p in params]
        assert "parent_id" in param_names
        assert "child_id" in param_names
        # Check that there's a VAR_KEYWORD parameter (**kwargs)
        var_kw = [p for p in params if p.kind == inspect.Parameter.VAR_KEYWORD]
        assert len(var_kw) == 1, "add_edge should accept **edge_data"
        assert var_kw[0].name == "edge_data"

    def test_get_edges_is_abstract_method(self):
        """
        Purpose: Proves get_edges() is defined as abstract on GraphStore.
        Acceptance Criteria: get_edges in __abstractmethods__.

        Task: T002
        """
        from fs2.core.repos.graph_store import GraphStore

        assert "get_edges" in GraphStore.__abstractmethods__

    def test_get_edges_signature_has_correct_params(self):
        """
        Purpose: Proves get_edges() has node_id, direction, edge_type params.
        Acceptance Criteria: Signature matches contract.

        Task: T002
        """
        import inspect

        from fs2.core.repos.graph_store import GraphStore

        sig = inspect.signature(GraphStore.get_edges)
        param_names = list(sig.parameters.keys())
        assert "node_id" in param_names
        assert "direction" in param_names
        assert "edge_type" in param_names

    def test_graph_store_abc_defines_get_all_edges_method(self):
        """
        Purpose: Proves get_all_edges exists on ABC.
        Quality Contribution: Enables extracting all reference edges.
        Acceptance Criteria: Method exists with edge_type parameter.

        Task: Phase 4 T005
        """
        import inspect

        from fs2.core.repos.graph_store import GraphStore

        assert hasattr(GraphStore, "get_all_edges")
        sig = inspect.signature(GraphStore.get_all_edges)
        param_names = list(sig.parameters.keys())
        assert "edge_type" in param_names
