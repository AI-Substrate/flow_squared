#!/usr/bin/env python3
"""LSP Demo: Extract cross-file relationships from a Python file.

This script demonstrates the SolidLspAdapter by:
1. Parsing a Python file with AST to find all name references
2. Calling LSP get_definition() for each name
3. Collecting and displaying cross-file edges

Usage:
    python scripts/lsp_demo_extract.py [file_path]
    
    If no file_path given, defaults to src/fs2/core/adapters/log_adapter_console.py
"""

import ast
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fs2.config.objects import LspConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter


@dataclass
class NameLocation:
    """A name reference found in the source file."""
    name: str
    line: int  # 0-indexed
    column: int  # 0-indexed
    context: str  # surrounding code snippet


class NameFinder(ast.NodeVisitor):
    """AST visitor to find all Name nodes (variable/module references)."""
    
    def __init__(self, source_lines: list[str]):
        self.names: list[NameLocation] = []
        self.source_lines = source_lines
        self._seen: set[tuple[str, int, int]] = set()
    
    def visit_Name(self, node: ast.Name) -> None:
        key = (node.id, node.lineno, node.col_offset)
        if key not in self._seen:
            self._seen.add(key)
            # Get context (the line containing this name)
            line_idx = node.lineno - 1  # AST is 1-indexed
            context = self.source_lines[line_idx].strip() if line_idx < len(self.source_lines) else ""
            
            self.names.append(NameLocation(
                name=node.id,
                line=node.lineno - 1,  # Convert to 0-indexed for LSP
                column=node.col_offset,
                context=context,
            ))
        self.generic_visit(node)
    
    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Also capture attribute access like obj.method."""
        # Get the full chain location (where the attribute name is)
        line_idx = node.lineno - 1
        context = self.source_lines[line_idx].strip() if line_idx < len(self.source_lines) else ""
        
        # Calculate column for the attribute part
        # Note: col_offset points to start of the expression, not the attr
        key = (f".{node.attr}", node.lineno, node.col_offset)
        if key not in self._seen:
            self._seen.add(key)
            self.names.append(NameLocation(
                name=f".{node.attr}",
                line=node.lineno - 1,
                column=node.col_offset,
                context=context,
            ))
        self.generic_visit(node)


def extract_names_from_file(file_path: Path) -> tuple[list[NameLocation], str]:
    """Parse a Python file and extract all name references."""
    source = file_path.read_text()
    tree = ast.parse(source)
    source_lines = source.splitlines()
    
    finder = NameFinder(source_lines)
    finder.visit(tree)
    
    return finder.names, source


def main() -> None:
    # Determine file to analyze
    if len(sys.argv) > 1:
        target_file = Path(sys.argv[1]).resolve()
    else:
        target_file = Path("src/fs2/core/adapters/log_adapter_console.py").resolve()
    
    if not target_file.exists():
        print(f"❌ File not found: {target_file}")
        sys.exit(1)
    
    project_root = Path.cwd().resolve()
    rel_path = str(target_file.relative_to(project_root))
    
    print(f"╔══════════════════════════════════════════════════════════════════╗")
    print(f"║  LSP Demo: Extract Cross-File Relationships                      ║")
    print(f"╚══════════════════════════════════════════════════════════════════╝")
    print(f"\n📁 Target file: {rel_path}")
    print(f"📂 Project root: {project_root}")
    
    # Step 1: Extract names from file
    print(f"\n🔍 Step 1: Parsing AST to find name references...")
    names, source = extract_names_from_file(target_file)
    print(f"   Found {len(names)} name references")
    
    # Show sample of names found
    print(f"\n   Sample names (first 10):")
    for name in names[:10]:
        print(f"   - {name.name:20} @ line {name.line + 1:3}:{name.column:2}  |  {name.context[:50]}...")
    
    # Step 2: Initialize LSP adapter
    print(f"\n⚡ Step 2: Initializing SolidLspAdapter (Pyright)...")
    
    # Create minimal config for LSP
    lsp_config = LspConfig(timeout_seconds=30.0)
    config_service = FakeConfigurationService(lsp_config)
    
    adapter = SolidLspAdapter(config_service)
    
    try:
        adapter.initialize(language="python", project_root=str(project_root))
        print(f"   ✅ LSP server ready")
    except Exception as e:
        print(f"   ❌ LSP initialization failed: {e}")
        sys.exit(1)
    
    # Step 3: Query LSP for definitions
    print(f"\n🔗 Step 3: Querying LSP for cross-file definitions...")
    
    cross_file_edges: list[tuple[NameLocation, str, str]] = []
    same_file_edges: list[tuple[NameLocation, str]] = []
    builtin_or_none: list[NameLocation] = []
    errors: list[tuple[NameLocation, str]] = []
    
    # Filter to interesting names (skip common builtins)
    skip_names = {'True', 'False', 'None', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple'}
    interesting_names = [n for n in names if n.name not in skip_names and not n.name.startswith('_')]
    
    print(f"   Querying {len(interesting_names)} names (skipping builtins)...")
    
    for i, name_loc in enumerate(interesting_names):
        try:
            edges = adapter.get_definition(rel_path, name_loc.line, name_loc.column)
            
            if not edges:
                builtin_or_none.append(name_loc)
            else:
                for edge in edges:
                    target_file_from_edge = edge.target_node_id  # e.g., "file:src/fs2/config/objects.py"
                    if target_file_from_edge.startswith("file:"):
                        target_path = target_file_from_edge[5:]  # strip "file:"
                    else:
                        target_path = target_file_from_edge
                    
                    if target_path != rel_path:
                        cross_file_edges.append((name_loc, target_path, edge.resolution_rule))
                    else:
                        same_file_edges.append((name_loc, target_path))
        
        except Exception as e:
            errors.append((name_loc, str(e)))
        
        # Progress indicator
        if (i + 1) % 20 == 0:
            print(f"   ... processed {i + 1}/{len(interesting_names)}")
    
    # Step 4: Display results
    print(f"\n═══════════════════════════════════════════════════════════════════")
    print(f"📊 RESULTS")
    print(f"═══════════════════════════════════════════════════════════════════")
    
    print(f"\n🔗 Cross-File Relationships ({len(cross_file_edges)} found):")
    print(f"   These are imports/references to other files in the project")
    print(f"   ─────────────────────────────────────────────────────────────")
    
    # Group by target file
    by_target: dict[str, list[tuple[NameLocation, str]]] = {}
    for name_loc, target, rule in cross_file_edges:
        if target not in by_target:
            by_target[target] = []
        by_target[target].append((name_loc, rule))
    
    for target, refs in sorted(by_target.items()):
        print(f"\n   → {target}")
        for name_loc, rule in refs[:5]:  # Show first 5 per target
            print(f"      • {name_loc.name:25} (line {name_loc.line + 1:3}) via {rule}")
        if len(refs) > 5:
            print(f"      ... and {len(refs) - 5} more")
    
    print(f"\n📍 Same-File References: {len(same_file_edges)}")
    print(f"🔧 Builtins/External (no definition found): {len(builtin_or_none)}")
    print(f"❌ Errors: {len(errors)}")
    
    if errors:
        print(f"\n   Errors encountered:")
        for name_loc, err in errors[:5]:
            print(f"   • {name_loc.name} @ line {name_loc.line + 1}: {err[:60]}...")
    
    # Summary
    print(f"\n═══════════════════════════════════════════════════════════════════")
    print(f"📈 SUMMARY")
    print(f"═══════════════════════════════════════════════════════════════════")
    print(f"   File analyzed:     {rel_path}")
    print(f"   Names processed:   {len(interesting_names)}")
    print(f"   Cross-file edges:  {len(cross_file_edges)}")
    print(f"   Unique targets:    {len(by_target)}")
    print(f"   Same-file refs:    {len(same_file_edges)}")
    
    # Cleanup
    adapter.shutdown()
    print(f"\n✅ Done! LSP server shut down.")


if __name__ == "__main__":
    main()
