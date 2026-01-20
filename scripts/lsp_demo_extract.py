#!/usr/bin/env python3
"""LSP Demo: Extract cross-file relationships from source files.

This script demonstrates the SolidLspAdapter by:
1. Parsing a source file to find all name references
2. Calling LSP get_definition() for each name
3. Collecting and displaying cross-file edges

Supports: Python, TypeScript, Go, C#

Usage:
    python scripts/lsp_demo_extract.py [file_path] [--lang LANG]
    
    If no file_path given, defaults to src/fs2/core/adapters/log_adapter_console.py
    If no --lang given, auto-detects from file extension
    
Examples:
    python scripts/lsp_demo_extract.py  # Default Python file
    python scripts/lsp_demo_extract.py tests/fixtures/lsp/go_project/cmd/server/main.go
    python scripts/lsp_demo_extract.py tests/fixtures/lsp/typescript_multi_project/packages/client/utils.ts
    python scripts/lsp_demo_extract.py tests/fixtures/lsp/csharp_multi_project/src/Api/Models.cs
"""

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fs2.config.objects import LspConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter

# Language detection from file extension
EXTENSION_TO_LANG = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".cs": "csharp",
}


@dataclass
class NameLocation:
    """A name reference found in the source file."""
    name: str
    line: int  # 0-indexed
    column: int  # 0-indexed
    context: str  # surrounding code snippet


class NameFinder(ast.NodeVisitor):
    """AST visitor to find all Name nodes (variable/module references). Python only."""
    
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


def extract_names_regex(file_path: Path, language: str) -> tuple[list[NameLocation], str]:
    """Extract identifiers using regex patterns for non-Python languages."""
    source = file_path.read_text()
    source_lines = source.splitlines()
    names: list[NameLocation] = []
    seen: set[tuple[str, int, int]] = set()
    
    # Language-specific identifier patterns
    if language == "go":
        # Go: function calls, type references, package.Identifier
        patterns = [
            r'\b([A-Z][a-zA-Z0-9_]*)\b',  # Exported identifiers (capitalized)
            r'(\w+)\.([A-Z][a-zA-Z0-9_]*)',  # package.Exported
            r'\b(\w+)\s*\(',  # function calls
        ]
    elif language in ("typescript", "javascript"):
        # TypeScript/JS: imports, function calls, class references
        patterns = [
            r'import\s+\{([^}]+)\}',  # named imports
            r'import\s+(\w+)\s+from',  # default imports
            r'\b([A-Z][a-zA-Z0-9_]*)\b',  # PascalCase (classes, types)
            r'(\w+)\s*\(',  # function calls
        ]
    elif language == "csharp":
        # C#: class references, method calls, using statements
        patterns = [
            r'using\s+([\w.]+);',  # using statements
            r'\b([A-Z][a-zA-Z0-9_]*)\b',  # PascalCase identifiers
            r'new\s+([A-Z][a-zA-Z0-9_]*)',  # constructor calls
            r'(\w+)\s*\(',  # method calls
        ]
    else:
        patterns = [r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b']  # fallback
    
    for line_idx, line in enumerate(source_lines):
        for pattern in patterns:
            for match in re.finditer(pattern, line):
                # Get the matched identifier
                for group_idx in range(1, match.lastindex + 1 if match.lastindex else 1):
                    name = match.group(group_idx)
                    if name and len(name) > 1:  # Skip single chars
                        # For import lists, split by comma
                        if ',' in name:
                            for part in name.split(','):
                                part = part.strip()
                                if part:
                                    col = line.find(part)
                                    key = (part, line_idx, col)
                                    if key not in seen:
                                        seen.add(key)
                                        names.append(NameLocation(
                                            name=part,
                                            line=line_idx,
                                            column=col if col >= 0 else 0,
                                            context=line.strip(),
                                        ))
                        else:
                            col = match.start(group_idx)
                            key = (name, line_idx, col)
                            if key not in seen:
                                seen.add(key)
                                names.append(NameLocation(
                                    name=name,
                                    line=line_idx,
                                    column=col,
                                    context=line.strip(),
                                ))
    
    return names, source


def detect_language(file_path: Path) -> str:
    """Detect language from file extension."""
    ext = file_path.suffix.lower()
    return EXTENSION_TO_LANG.get(ext, "python")


def get_project_root_for_language(file_path: Path, language: str) -> Path:
    """Find appropriate project root based on language markers."""
    current = file_path.parent
    
    # Language-specific project markers
    markers = {
        "python": ["pyproject.toml", "setup.py", "requirements.txt"],
        "typescript": ["tsconfig.json", "package.json"],
        "javascript": ["package.json", "jsconfig.json"],
        "go": ["go.mod"],
        "csharp": ["*.sln", "*.csproj"],
    }
    
    lang_markers = markers.get(language, [])
    
    while current != current.parent:
        for marker in lang_markers:
            if "*" in marker:
                if list(current.glob(marker)):
                    return current
            elif (current / marker).exists():
                return current
        current = current.parent
    
    # Fallback to cwd
    return Path.cwd().resolve()


def main() -> None:
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="LSP Demo: Extract cross-file relationships from source files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/lsp_demo_extract.py
  python scripts/lsp_demo_extract.py tests/fixtures/lsp/go_project/cmd/server/main.go
  python scripts/lsp_demo_extract.py tests/fixtures/lsp/typescript_multi_project/packages/client/utils.ts
  python scripts/lsp_demo_extract.py tests/fixtures/lsp/csharp_multi_project/src/Api/Models.cs
  python scripts/lsp_demo_extract.py --lang python src/fs2/cli/main.py
        """,
    )
    parser.add_argument(
        "file", 
        nargs="?", 
        default="src/fs2/core/adapters/log_adapter_console.py",
        help="Source file to analyze (default: log_adapter_console.py)"
    )
    parser.add_argument(
        "--lang", 
        choices=["python", "typescript", "go", "csharp", "javascript"],
        help="Language (auto-detected from extension if not specified)"
    )
    args = parser.parse_args()
    
    # Determine file to analyze
    target_file = Path(args.file).resolve()
    
    if not target_file.exists():
        print(f"❌ File not found: {target_file}")
        sys.exit(1)
    
    # Detect or use specified language
    language = args.lang or detect_language(target_file)
    
    # Find project root based on language
    project_root = get_project_root_for_language(target_file, language)
    
    try:
        rel_path = str(target_file.relative_to(project_root))
    except ValueError:
        # File not under project root, use absolute
        rel_path = str(target_file)
    
    # Language display names
    lang_display = {
        "python": "Python (Pyright)",
        "typescript": "TypeScript (tsserver)",
        "javascript": "JavaScript (tsserver)",
        "go": "Go (gopls)",
        "csharp": "C# (Roslyn)",
    }
    
    print(f"╔══════════════════════════════════════════════════════════════════╗")
    print(f"║  LSP Demo: Extract Cross-File Relationships                      ║")
    print(f"╚══════════════════════════════════════════════════════════════════╝")
    print(f"\n📁 Target file: {rel_path}")
    print(f"📂 Project root: {project_root}")
    print(f"🔤 Language: {lang_display.get(language, language)}")
    
    # Step 1: Extract names from file
    print(f"\n🔍 Step 1: Parsing source to find name references...")
    if language == "python":
        names, source = extract_names_from_file(target_file)
    else:
        names, source = extract_names_regex(target_file, language)
    print(f"   Found {len(names)} name references")
    
    # Show sample of names found
    print(f"\n   Sample names (first 10):")
    for name in names[:10]:
        ctx = name.context[:50] + "..." if len(name.context) > 50 else name.context
        print(f"   - {name.name:20} @ line {name.line + 1:3}:{name.column:2}  |  {ctx}")
    
    # Step 2: Initialize LSP adapter
    print(f"\n⚡ Step 2: Initializing SolidLspAdapter ({lang_display.get(language, language)})...")
    
    # Create minimal config for LSP
    lsp_config = LspConfig(timeout_seconds=30.0)
    config_service = FakeConfigurationService(lsp_config)
    
    adapter = SolidLspAdapter(config_service)
    
    try:
        adapter.initialize(language=language, project_root=str(project_root))
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
    
    # Filter to interesting names (skip common builtins/keywords)
    skip_names_by_lang = {
        "python": {'True', 'False', 'None', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple', 'self', 'cls'},
        "typescript": {'true', 'false', 'null', 'undefined', 'string', 'number', 'boolean', 'any', 'void', 'this', 'const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while', 'import', 'export', 'from', 'async', 'await'},
        "javascript": {'true', 'false', 'null', 'undefined', 'this', 'const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while', 'import', 'export', 'from', 'async', 'await'},
        "go": {'true', 'false', 'nil', 'string', 'int', 'bool', 'error', 'func', 'return', 'if', 'else', 'for', 'range', 'package', 'import', 'var', 'const', 'type', 'struct', 'interface', 'defer', 'go', 'chan', 'select', 'case', 'default', 'break', 'continue'},
        "csharp": {'true', 'false', 'null', 'string', 'int', 'bool', 'void', 'var', 'class', 'public', 'private', 'protected', 'static', 'return', 'if', 'else', 'for', 'foreach', 'while', 'using', 'namespace', 'new', 'this', 'base', 'async', 'await', 'Task'},
    }
    skip_names = skip_names_by_lang.get(language, set())
    interesting_names = [n for n in names if n.name not in skip_names and not n.name.startswith('_') and len(n.name) > 1]
    
    print(f"   Querying {len(interesting_names)} names (skipping keywords/builtins)...")
    
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
    print(f"   Language:          {lang_display.get(language, language)}")
    print(f"   Names processed:   {len(interesting_names)}")
    print(f"   Cross-file edges:  {len(cross_file_edges)}")
    print(f"   Unique targets:    {len(by_target)}")
    print(f"   Same-file refs:    {len(same_file_edges)}")
    
    # Cleanup
    adapter.shutdown()
    print(f"\n✅ Done! LSP server shut down.")


if __name__ == "__main__":
    main()
