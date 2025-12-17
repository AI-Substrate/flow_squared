"""TreeNode domain model for tree rendering.

Provides a recursive structure for representing code trees.
Used by TreeService.build_tree() to return a complete tree structure
that CLI can render without knowing the tree-building algorithm.

Design:
- Frozen dataclass for immutability
- Recursive structure (children are also TreeNodes)
- Uses tuple for children to maintain immutability
- Contains CodeNode data plus children references
"""

from __future__ import annotations

from dataclasses import dataclass

from fs2.core.models.code_node import CodeNode


@dataclass(frozen=True)
class TreeNode:
    """A node in the tree structure for rendering.

    Recursive structure: each TreeNode contains its CodeNode data
    and a tuple of child TreeNodes. Uses tuple instead of list
    for immutability (frozen dataclass).

    Attributes:
        node: The CodeNode data for this tree node.
        children: Tuple of child TreeNodes (may be empty).
        hidden_children_count: Count of children hidden by depth limit (0 if not at limit).

    Example:
        ```python
        # Tree with two levels
        child1 = TreeNode(node=child_code_node, children=())
        child2 = TreeNode(node=child_code_node2, children=())
        root = TreeNode(node=parent_code_node, children=(child1, child2))

        # Recursive traversal
        def render(tree_node: TreeNode, depth: int = 0) -> None:
            print("  " * depth + tree_node.node.name)
            for child in tree_node.children:
                render(child, depth + 1)
            if tree_node.hidden_children_count > 0:
                print(f"  [{tree_node.hidden_children_count} children hidden]")
        ```
    """

    node: CodeNode
    children: tuple[TreeNode, ...] = ()
    hidden_children_count: int = 0
