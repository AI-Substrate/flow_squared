"""Tests for GraphStore ABC contract.

Tasks: T001-T003, T006-T011 (Phase 1 Cross-File Relationships)
Purpose: Verify GraphStore ABC defines correct interface and relationship edge support.
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


# =============================================================================
# Phase 1 Cross-File Relationships: T006-T011
# =============================================================================


@pytest.mark.unit
class TestGraphStoreRelationshipEdgeABC:
    """T006: Tests for GraphStore relationship edge ABC extension."""

    def test_graph_store_abc_defines_add_relationship_edge_method(self):
        """
        Purpose: Verifies add_relationship_edge() is an abstract method.
        Quality Contribution: Ensures implementations provide relationship edge addition.
        Acceptance Criteria: add_relationship_edge in __abstractmethods__.

        Task: T006
        """
        from fs2.core.repos.graph_store import GraphStore

        assert "add_relationship_edge" in GraphStore.__abstractmethods__

    def test_graph_store_abc_defines_get_relationships_method(self):
        """
        Purpose: Verifies get_relationships() is an abstract method.
        Quality Contribution: Ensures implementations provide relationship queries.
        Acceptance Criteria: get_relationships in __abstractmethods__.

        Task: T006
        """
        from fs2.core.repos.graph_store import GraphStore

        assert "get_relationships" in GraphStore.__abstractmethods__


@pytest.mark.unit
class TestNetworkXGraphStoreAddRelationshipEdge:
    """T008: Tests for NetworkXGraphStore.add_relationship_edge()."""

    @pytest.fixture
    def store(self):
        """Create a NetworkXGraphStore instance with test nodes."""
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.models.code_node import CodeNode
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        # Add source and target nodes
        source = CodeNode.create_file(
            "src/app.py", "python", "module", 0, 100, 1, 10, "import auth"
        )
        target = CodeNode.create_file(
            "src/auth.py", "python", "module", 0, 200, 1, 20, "class Auth: pass"
        )
        store.add_node(source)
        store.add_node(target)
        return store

    def test_add_relationship_edge_stores_edge_type(self, store):
        """
        Purpose: Proves relationship edge stores edge_type attribute.
        Quality Contribution: Enables type-based edge filtering.
        Acceptance Criteria: Edge attribute contains edge_type (AC3).

        Task: T008
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        edge = CodeEdge(
            source_node_id="file:src/app.py",
            target_node_id="file:src/auth.py",
            edge_type=EdgeType.IMPORTS,
            confidence=0.9,
        )
        store.add_relationship_edge(edge)

        # Verify edge exists and has correct type
        rels = store.get_relationships("file:src/app.py", direction="outgoing")
        assert len(rels) == 1
        assert rels[0]["edge_type"] == "imports"

    def test_add_relationship_edge_stores_confidence(self, store):
        """
        Purpose: Proves relationship edge stores confidence attribute.
        Quality Contribution: Enables confidence-based filtering.
        Acceptance Criteria: Edge attribute contains confidence (AC3).

        Task: T008
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        edge = CodeEdge(
            source_node_id="file:src/app.py",
            target_node_id="file:src/auth.py",
            edge_type=EdgeType.IMPORTS,
            confidence=0.85,
        )
        store.add_relationship_edge(edge)

        rels = store.get_relationships("file:src/app.py", direction="outgoing")
        assert len(rels) == 1
        assert rels[0]["confidence"] == 0.85

    def test_add_relationship_edge_stores_source_line(self, store):
        """
        Purpose: Proves relationship edge stores source_line attribute.
        Quality Contribution: Enables documentation discovery navigation.
        Acceptance Criteria: Edge attribute contains source_line (per user clarification).

        Task: T008
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        edge = CodeEdge(
            source_node_id="file:src/app.py",
            target_node_id="file:src/auth.py",
            edge_type=EdgeType.IMPORTS,
            confidence=0.9,
            source_line=5,
        )
        store.add_relationship_edge(edge)

        rels = store.get_relationships("file:src/app.py", direction="outgoing")
        assert len(rels) == 1
        assert rels[0]["source_line"] == 5

    def test_add_relationship_edge_source_line_none_when_not_provided(self, store):
        """
        Purpose: Proves source_line is None when not provided.
        Quality Contribution: Backward compatibility for edges without line info.
        Acceptance Criteria: source_line can be None.

        Task: T008
        """
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.edge_type import EdgeType

        edge = CodeEdge(
            source_node_id="file:src/app.py",
            target_node_id="file:src/auth.py",
            edge_type=EdgeType.IMPORTS,
            confidence=0.9,
        )
        store.add_relationship_edge(edge)

        rels = store.get_relationships("file:src/app.py", direction="outgoing")
        assert len(rels) == 1
        assert rels[0]["source_line"] is None


@pytest.mark.unit
class TestNetworkXGraphStoreGetRelationships:
    """T009-T010: Tests for NetworkXGraphStore.get_relationships()."""

    @pytest.fixture
    def store_with_edges(self):
        """Create a store with multiple relationship edges."""
        from fs2.config.objects import ScanConfig
        from fs2.config.service import FakeConfigurationService
        from fs2.core.models.code_edge import CodeEdge
        from fs2.core.models.code_node import CodeNode
        from fs2.core.models.edge_type import EdgeType
        from fs2.core.repos.graph_store_impl import NetworkXGraphStore

        config = FakeConfigurationService(ScanConfig())
        store = NetworkXGraphStore(config)

        # Create nodes: A imports B, B imports C
        node_a = CodeNode.create_file(
            "src/a.py", "python", "module", 0, 100, 1, 10, "import b"
        )
        node_b = CodeNode.create_file(
            "src/b.py", "python", "module", 0, 100, 1, 10, "import c"
        )
        node_c = CodeNode.create_file(
            "src/c.py", "python", "module", 0, 100, 1, 10, "# base"
        )
        store.add_node(node_a)
        store.add_node(node_b)
        store.add_node(node_c)

        # Add edges: A→B, B→C
        store.add_relationship_edge(
            CodeEdge(
                source_node_id="file:src/a.py",
                target_node_id="file:src/b.py",
                edge_type=EdgeType.IMPORTS,
                confidence=0.9,
                source_line=1,
            )
        )
        store.add_relationship_edge(
            CodeEdge(
                source_node_id="file:src/b.py",
                target_node_id="file:src/c.py",
                edge_type=EdgeType.IMPORTS,
                confidence=0.9,
                source_line=1,
            )
        )

        return store

    def test_get_relationships_outgoing_returns_targets(self, store_with_edges):
        """
        Purpose: Proves outgoing direction returns what a node depends on.
        Quality Contribution: "What does this file import?"
        Acceptance Criteria: Returns correct target node_ids (AC7).

        Task: T010
        """
        rels = store_with_edges.get_relationships(
            "file:src/a.py", direction="outgoing"
        )
        assert len(rels) == 1
        assert rels[0]["node_id"] == "file:src/b.py"

    def test_get_relationships_incoming_returns_sources(self, store_with_edges):
        """
        Purpose: Proves incoming direction returns what depends on a node.
        Quality Contribution: "What imports this file?"
        Acceptance Criteria: Returns correct source node_ids (AC7).

        Task: T010
        """
        rels = store_with_edges.get_relationships(
            "file:src/b.py", direction="incoming"
        )
        assert len(rels) == 1
        assert rels[0]["node_id"] == "file:src/a.py"

    def test_get_relationships_both_returns_all(self, store_with_edges):
        """
        Purpose: Proves both direction returns all related nodes.
        Quality Contribution: Complete relationship discovery.
        Acceptance Criteria: Returns both incoming and outgoing (AC7).

        Task: T010
        """
        rels = store_with_edges.get_relationships("file:src/b.py", direction="both")
        assert len(rels) == 2
        node_ids = {r["node_id"] for r in rels}
        assert node_ids == {"file:src/a.py", "file:src/c.py"}

    def test_get_relationships_empty_for_unknown_node(self, store_with_edges):
        """
        Purpose: Proves unknown node returns empty list (not error).
        Quality Contribution: Graceful handling of non-existent nodes.
        Acceptance Criteria: Empty list for unknown node.

        Task: T010
        """
        rels = store_with_edges.get_relationships(
            "file:src/unknown.py", direction="outgoing"
        )
        assert rels == []

    def test_get_relationships_empty_for_node_without_relationships(
        self, store_with_edges
    ):
        """
        Purpose: Proves node without relationships returns empty list.
        Quality Contribution: Backward compatibility (AC8).
        Acceptance Criteria: Empty list for isolated node.

        Task: T010
        """
        rels = store_with_edges.get_relationships(
            "file:src/c.py", direction="outgoing"
        )
        assert rels == []

    def test_get_relationships_includes_source_line(self, store_with_edges):
        """
        Purpose: Proves source_line is included in output (per user clarification).
        Quality Contribution: Documentation discovery navigation.
        Acceptance Criteria: Output includes source_line field.

        Task: T010
        """
        rels = store_with_edges.get_relationships(
            "file:src/a.py", direction="outgoing"
        )
        assert len(rels) == 1
        assert "source_line" in rels[0]
        assert rels[0]["source_line"] == 1

    def test_get_relationships_output_format(self, store_with_edges):
        """
        Purpose: Proves output format matches spec (node_id, edge_type, confidence, source_line).
        Quality Contribution: MCP tool integration.
        Acceptance Criteria: All 4 fields present (per Q6 clarification).

        Task: T010
        """
        rels = store_with_edges.get_relationships(
            "file:src/a.py", direction="outgoing"
        )
        assert len(rels) == 1
        rel = rels[0]
        assert set(rel.keys()) == {"node_id", "edge_type", "confidence", "source_line"}
        assert rel["node_id"] == "file:src/b.py"
        assert rel["edge_type"] == "imports"
        assert rel["confidence"] == 0.9
        assert rel["source_line"] == 1
