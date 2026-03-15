"""Tests for treemap layout algorithm.

TDD tests for compute_treemap() — squarified treemap that positions
nodes spatially by directory hierarchy. Pure math, no dependencies.

Tests cover:
- Empty graph
- Single node
- Single directory
- Multiple directories
- Deep nesting
- Canvas coordinate range (0–1000)
- Determinism
- Size scaling (log formula)
"""

import pytest

from fs2.core.models.code_node import CodeNode
from fs2.core.services.report_layout import (
    NodePosition,
    build_directory_tree,
    compute_treemap,
)


def _make_node(
    node_id: str,
    name: str = "foo",
    category: str = "callable",
    file_path: str = "src/a.py",
    start_line: int = 1,
    end_line: int = 10,
) -> CodeNode:
    """Create a minimal CodeNode for treemap testing.

    Uses the correct factory method based on category prefix in node_id.
    """
    if category == "file" or node_id.startswith("file:"):
        return CodeNode.create_file(
            file_path, "python", "python",
            0, 100, start_line, end_line,
            f"# {name}",
        )
    elif category == "type" or node_id.startswith("type:"):
        return CodeNode.create_type(
            file_path, "python", "class", name, name,
            start_line, end_line, 0, 0, 0, 100,
            f"class {name}: pass", f"class {name}",
            parent_node_id=f"file:{file_path}",
        )
    else:
        return CodeNode.create_callable(
            file_path, "python", "function", name, name,
            start_line, end_line, 0, 0, 0, 100,
            f"def {name}(): pass", f"def {name}()",
            parent_node_id=f"file:{file_path}",
        )


@pytest.mark.unit
class TestComputeTreemapEmpty:
    """Edge case: empty input."""

    def test_empty_list(self):
        result = compute_treemap([])
        assert result == {}


@pytest.mark.unit
class TestComputeTreemapSingleNode:
    """Single node fills entire canvas."""

    def test_single_node_fills_canvas(self):
        node = _make_node("file:src/a.py", "a.py", "file", "src/a.py")
        result = compute_treemap([node])
        assert len(result) == 1
        pos = result[node.node_id]
        assert isinstance(pos, NodePosition)
        # Should fill most of the canvas
        assert 0 <= pos.x <= 1000
        assert 0 <= pos.y <= 1000
        assert pos.size > 0


@pytest.mark.unit
class TestComputeTreemapSingleDirectory:
    """Multiple nodes in one directory."""

    def test_nodes_in_same_dir_no_overlap(self):
        nodes = [
            _make_node("callable:src/a.py:foo", "foo", "callable", "src/a.py", 1, 20),
            _make_node("callable:src/a.py:bar", "bar", "callable", "src/a.py", 21, 40),
            _make_node("callable:src/a.py:baz", "baz", "callable", "src/a.py", 41, 50),
        ]
        result = compute_treemap(nodes)
        assert len(result) == 3
        # Check no overlapping positions (all distinct)
        positions = [(p.x, p.y) for p in result.values()]
        assert len(set(positions)) == 3

    def test_all_in_canvas_range(self):
        nodes = [
            _make_node("callable:src/a.py:foo", "foo", "callable", "src/a.py", 1, 20),
            _make_node("callable:src/b.py:bar", "bar", "callable", "src/b.py", 1, 30),
        ]
        result = compute_treemap(nodes)
        for pos in result.values():
            assert 0 <= pos.x <= 1000, f"x={pos.x} out of canvas"
            assert 0 <= pos.y <= 1000, f"y={pos.y} out of canvas"


@pytest.mark.unit
class TestComputeTreemapMultiDirectory:
    """Nodes spread across multiple directories."""

    def test_different_dirs_get_different_regions(self):
        nodes = [
            _make_node("file:src/a.py", "a.py", "file", "src/a.py", 1, 100),
            _make_node("file:lib/b.py", "b.py", "file", "lib/b.py", 1, 100),
        ]
        result = compute_treemap(nodes)
        assert len(result) == 2
        pos_a = result["file:src/a.py"]
        pos_b = result["file:lib/b.py"]
        # Different dirs should have distinct positions
        assert (pos_a.x, pos_a.y) != (pos_b.x, pos_b.y)


@pytest.mark.unit
class TestComputeTreemapDeepNesting:
    """Deep directory hierarchies."""

    def test_deep_path_in_canvas(self):
        nodes = [
            _make_node(
                "callable:src/fs2/core/services/deep/module.py:func",
                "func", "callable",
                "src/fs2/core/services/deep/module.py", 1, 20,
            ),
        ]
        result = compute_treemap(nodes)
        assert len(result) == 1
        pos = list(result.values())[0]
        assert 0 <= pos.x <= 1000
        assert 0 <= pos.y <= 1000


@pytest.mark.unit
class TestComputeTreemapDeterminism:
    """Same input always produces same output."""

    def test_deterministic(self):
        nodes = [
            _make_node("callable:src/a.py:foo", "foo", "callable", "src/a.py", 1, 20),
            _make_node("callable:src/b.py:bar", "bar", "callable", "src/b.py", 1, 30),
            _make_node("callable:lib/c.py:baz", "baz", "callable", "lib/c.py", 1, 10),
        ]
        r1 = compute_treemap(nodes)
        r2 = compute_treemap(nodes)
        for nid in r1:
            assert r1[nid].x == r2[nid].x
            assert r1[nid].y == r2[nid].y
            assert r1[nid].size == r2[nid].size


@pytest.mark.unit
class TestComputeTreemapSize:
    """Node size uses log formula: max(4, min(14, 3 + log2(lines+1)*1.5))."""

    def test_small_node_minimum_size(self):
        """1-line function gets minimum size of 4."""
        node = _make_node("callable:src/a.py:tiny", "tiny", "callable", "src/a.py", 1, 1)
        result = compute_treemap([node])
        pos = result[node.node_id]
        assert pos.size == pytest.approx(4.0, abs=0.5)

    def test_large_node_bigger_size(self):
        """500-line file gets larger size."""
        node = _make_node("file:src/big.py", "big.py", "file", "src/big.py", 1, 500)
        result = compute_treemap([node])
        pos = result[node.node_id]
        assert pos.size > 4.0

    def test_size_capped_at_14(self):
        """Even huge files cap at 14."""
        node = _make_node("file:src/huge.py", "huge.py", "file", "src/huge.py", 1, 100000)
        result = compute_treemap([node])
        pos = result[node.node_id]
        assert pos.size <= 14.0


@pytest.mark.unit
class TestComputeTreemapMixedCategories:
    """Mixed node categories positioned correctly."""

    def test_mixed_categories(self):
        nodes = [
            _make_node("file:src/a.py", "a.py", "file", "src/a.py", 1, 50),
            _make_node("callable:src/a.py:foo", "foo", "callable", "src/a.py", 1, 20),
            _make_node("type:src/a.py:Bar", "Bar", "type", "src/a.py", 25, 50),
        ]
        result = compute_treemap(nodes)
        assert len(result) == 3
        for pos in result.values():
            assert 0 <= pos.x <= 1000
            assert 0 <= pos.y <= 1000


@pytest.mark.unit
class TestBuildDirectoryTree:
    """Tests for the shared build_directory_tree utility."""

    def test_groups_by_directory(self):
        nodes = [
            _make_node("file:src/a.py", "a.py", "file", "src/a.py"),
            _make_node("file:lib/b.py", "b.py", "file", "lib/b.py"),
        ]
        tree = build_directory_tree(nodes)
        assert "src" in tree
        assert "lib" in tree
        assert len(tree["src"]["__nodes__"]) == 1
        assert len(tree["lib"]["__nodes__"]) == 1

    def test_root_level_files(self):
        node = _make_node("file:setup.py", "setup.py", "file", "setup.py")
        tree = build_directory_tree([node])
        assert len(tree["__nodes__"]) == 1
