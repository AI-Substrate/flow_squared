"""Tests for GraphStore ABC contract.

Tasks: T001-T003
Purpose: Verify GraphStore ABC defines correct interface.
"""

import pytest
from abc import ABC


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
