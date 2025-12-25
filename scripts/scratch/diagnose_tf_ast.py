#!/usr/bin/env python3
"""Diagnose tree-sitter HCL AST structure.

Print the actual tree-sitter node structure for HCL blocks
to understand why name extraction isn't working.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from tree_sitter_language_pack import get_parser


def print_tree(node, content: bytes, indent: int = 0):
    """Recursively print tree-sitter AST."""
    prefix = "  " * indent
    text = content[node.start_byte:node.end_byte].decode("utf-8")
    # Truncate text for readability
    if len(text) > 60:
        text = text[:57] + "..."
    text = text.replace("\n", "\\n")

    print(f"{prefix}{node.type}: {repr(text)}")

    for child in node.children:
        print_tree(child, content, indent + 1)


def main():
    print("=" * 80)
    print("TREE-SITTER HCL AST STRUCTURE")
    print("=" * 80)

    # Sample HCL content
    hcl_content = b'''
variable "environment" {
  description = "Deployment environment"
  type        = string
}

resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

data "aws_region" "current" {}

output "vpc_id" {
  value = aws_vpc.main.id
}
'''

    # Parse with tree-sitter-hcl
    parser = get_parser("hcl")
    tree = parser.parse(hcl_content)

    # Print the full tree
    print("\nFull AST:")
    print_tree(tree.root_node, hcl_content)

    # Focus on finding block children
    print("\n" + "-" * 40)
    print("BLOCK CHILDREN ANALYSIS")
    print("-" * 40)

    def find_blocks(node, content):
        if node.type == "block":
            print(f"\nBlock at line {node.start_point[0] + 1}:")
            text = content[node.start_byte:node.end_byte].decode("utf-8")
            print(f"  Full text: {text[:100]}...")
            print(f"  Children ({len(node.children)}):")
            for i, child in enumerate(node.children):
                child_text = content[child.start_byte:child.end_byte].decode("utf-8")
                print(f"    [{i}] {child.type}: {repr(child_text[:40])}")
                # Also show grandchildren for interesting types
                if child.type in ("identifier", "string_lit", "quoted_template"):
                    for gc in child.children:
                        gc_text = content[gc.start_byte:gc.end_byte].decode("utf-8")
                        print(f"        {gc.type}: {repr(gc_text)}")

        for child in node.children:
            find_blocks(child, content)

    find_blocks(tree.root_node, hcl_content)


if __name__ == "__main__":
    main()
