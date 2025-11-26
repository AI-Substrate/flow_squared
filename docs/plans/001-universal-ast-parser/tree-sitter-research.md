1. Executive summary

---

* Tree-sitter already gives you a *uniform* structural model: a concrete syntax tree (CST) with the same `Node`, `TreeCursor`, and `Parser` APIs for every grammar. Your universal parser should lean heavily on these APIs, especially `is_named`, `fields`, and static metadata from `node-types.json`. ([tree-sitter.github.io][1])

* The most robust language-agnostic split between “structural” and “syntactic” is:

  * Keep **named** nodes (grammar rules).
  * Drop **anonymous/extra** nodes (punctuation, whitespace, many keywords). Named nodes correspond to meaningful constructs across grammars. ([tree-sitter.github.io][2])

* To avoid `if language == "python"` style special-casing, treat *grammars themselves as data*:

  * Read each language’s `node-types.json` (or similar metadata) to discover node types, supertypes (e.g. `_declaration`), and fields (`name`, `body`, `parameters`, etc.).
  * Run **generic heuristics** over that metadata to classify node kinds into a small universal taxonomy (e.g. `container`, `callable`, `declaration`, `section`, `block`, `mapping`, `sequence`). ([tree-sitter.github.io][3])

* The universal output model should be a **language-agnostic “structure tree”**:

  * Nodes have: `language`, `raw_kind` (tree-sitter type), `category` (from your taxonomy), `label` (name/heading/etc.), `range`, and `children`.
  * This is analogous to what difftastic does by turning all parse trees into s-expressions and what Semgrep does with its “generic AST”, but you stay closer to the CST and avoid per-language code paths. ([wilfred.me.uk][4])

* A practical architecture:

  1. Detect language (via extension map / detector).
  2. Use `tree-sitter-language-pack` to get a `Parser` for that language. ([PyPI][5])
  3. Parse to a tree, walk named nodes using `TreeCursor`.
  4. Score nodes for “structural salience” using generic features (span, depth, fields, supertypes, presence of name-like children).
  5. Build and return a pruned, nested structure tree in your universal schema (JSON/DTO), plus enough raw metadata to refine later.

---

2. Detailed findings (by research question)

---

### Tree-sitter fundamentals

**1. How does tree-sitter’s AST structure work? Universal node properties?**

* Tree-sitter builds a **concrete syntax tree** (CST) for a source file:

  * Each tree has a root `Node` (`tree.root_node` in Python).
  * Every `Node` has:

    * `type`: string node kind (e.g. `class_definition`, `function_declaration`, `atx_heading`, `block`). ([tree-sitter.github.io][1])
    * `is_named`: whether it’s a grammar rule (named) vs literal token (anonymous).
    * `start_byte` / `end_byte` and `start_point` / `end_point` (row/column).
    * `children`, `named_children`, `child_count`, `named_child_count`.
    * `parent`, `next_sibling`, `prev_sibling`, `next_named_sibling`, `prev_named_sibling`.
    * `has_error`, `is_error`, `is_missing`, `is_extra`. ([tree-sitter.github.io][1])

* A **TreeCursor** walks the same tree more efficiently: it always points at a node and supports `goto_first_child`, `goto_next_sibling`, `goto_parent`, etc. ([tree-sitter.github.io][6])

* All grammars compiled with tree-sitter share this shape; the only variation is the `type` strings and field definitions.

**2. Named vs anonymous nodes – which matter?**

* Named nodes:

  * Represent **grammar rules**, e.g. `function_declaration`, `class_definition`, `if_statement`, `atx_heading`.
  * Are included in `node-types.json` with `"named": true`. ([tree-sitter.github.io][3])
  * `Node.is_named` returns `True` for these. ([tree-sitter.github.io][1])

* Anonymous nodes:

  * Represent literal tokens in the grammar: `"+"`, `"("`, `"{"`, `","`, etc.
  * `is_named == False`, and they typically correspond to pure syntax/punctuation. ([tree-sitter.github.io][2])

* For your purposes:

  * **Structural / semantic nodes** ≈ named nodes.
  * **Syntax / punctuation** ≈ anonymous + often `is_extra` nodes (whitespace/comments).

So a first-cut universal filter is “walk only named nodes and ignore extras.”

**3. Traversing parse trees in Python**

From the py-tree-sitter docs: ([tree-sitter.github.io][7])

* **Recursive traversal**:

  * Classic DFS using `node.children` / `node.named_children`.
  * Simple but creates lots of Python objects; fine for moderate file sizes.

* **TreeCursor traversal**:

  * `cursor = root_node.walk()`
  * Then use `goto_first_child`, `goto_next_sibling`, `goto_parent`.
  * Much more efficient; recommended for large trees.

* Hybrid pattern:

  * Use a `TreeCursor` for traversal.
  * Use `cursor.node` to inspect the current node (type, range, etc.).

**4. Getting source text for a node**

* Tree-sitter **does not store the source text** in the tree; only byte ranges are stored. ([Stack Overflow][8])
* py-tree-sitter adds a convenience attribute:

  * `Node.text` returns the node’s text *if* the tree has not been edited. ([tree-sitter.github.io][1])
* Robust pattern:

  * Keep the original source bytes `source: bytes`.
  * Use `start_byte`, `end_byte` to slice: `source[node.start_byte:node.end_byte]`.

This makes your universal model straightforward: you derive text lazily from ranges when needed.

---

### Cross-grammar consistency

**5. Common naming patterns across grammars**

Looking across grammar docs and node-types examples: ([tree-sitter.github.io][3])

* Very common patterns:

  * Declarations/definitions: `*_declaration`, `*_definition`.
  * Statements: `*_statement`.
  * Blocks/bodies: `*_block`, `*_body`.
  * Expressions: `*_expression`.
  * Identifiers / names: `identifier`, `property_identifier`, `tag_name`, `heading`, etc.

* There are also **supertypes**:

  * E.g. in JavaScript, `_declaration` supertype wraps `class_declaration`, `function_declaration`, etc. ([tree-sitter.github.io][3])
  * Grammars can mark supertypes, so node-types JSON contains abstract categories like `_expression`, `_type`, `_declaration`.

Pattern-based rules on these strings go a long way in a generic classifier.

**6. Representing hierarchy in different grammars**

* Imperative/OOP languages (Python, JS, Java, C#, etc.):

  * Root node often `module`, `program`, `source_file`, or similar.
  * Direct children: top-level declarations (`class_definition`, `function_definition`, `lexical_declaration`, etc.).
  * Classes/functions have `body` fields pointing to a `block` or `suite` node. ([tree-sitter.github.io][3])

* Markdown:

  * Grammar distinguishes block structure (`source_file` → `section` → `heading` + content). ([Docs.rs][9])
  * Some Markdown grammars historically treated headings as flat leaf blocks; more recent ones add `section` nodes for hierarchical grouping. ([GitHub][10])

* HCL/Terraform:

  * Key constructs: `block`, `attribute`, `object`, `array`, etc. Lexical structure is nested blocks and attributes. ([Docs.rs][11])

* Dockerfile:

  * Grammar has per-instruction node types like `from_instruction`, `run_instruction`, `cmd_instruction`, etc. These are essentially top-level statements. (The language pack vendors `dockerfile` grammar; the underlying grammar uses those kinds of names.) ([PyPI][5])

Hierarchies are thus always encoded via parent/child relationships over *named nodes*; the concept of “section” vs “block” vs “class” is expressed through type names and fields, not via a different data model.

**7. Structural vs syntactic nodes**

From Tree-sitter docs and tools like ast-grep: ([ast-grep.github.io][12])

* Named vs anonymous is the first structural filter.
* Within named nodes:

  * **Structural**: nodes that:

    * Span multiple lines or many descendants.
    * Are supertypes (`_declaration`, `_expression`) or declarations/definitions.
    * Have fields named `name`, `body`, `parameters`, `block`, `value`, etc.
  * **Syntactic-but-named**: many helper nodes like `argument_list`, `parameter_list`, `binary_expression` — they’re named but typically not “top-level structure” for navigation/folding.

node-types.json gives you:

* For each node `type`, whether it’s named, and what fields and children it can have.
* Supertypes to group declarations, expressions, types, etc. ([tree-sitter.github.io][3])

This is enough to design a *generic* heuristic that recognises “likely structural” nodes.

**8. Containers and “bodies”**

* In node-types JSON, container nodes usually:

  * Have a `fields.body` with `required: true` pointing at some block-type node (method bodies, class bodies). ([tree-sitter.github.io][3])
  * Or have `children.multiple: true` and many descendants (e.g. arrays, lists, sections).

* Markdown:

  * `section` nodes: `heading` plus content nodes. ([GitHub][13])

* HCL/Terraform:

  * `block` node types: child fields for `labels`, `body`; `body` contains `attribute` or nested `block`. ([Docs.rs][11])

This suggests a generic pattern: *nodes with named children in a `body`/`block`/“content-like” field and many descendants are structural containers*.

---

### Practical implementation

**9. Using tree-sitter-language-pack**

From the PyPI and GitHub docs: ([PyPI][5])

* Install:

  ```bash
  uv add tree-sitter==0.25.2 tree-sitter-language-pack==0.11.0
  ```

* API:

  ```python
  from tree_sitter_language_pack import get_binding, get_language, get_parser

  python_binding = get_binding("python")   # low-level C binding
  python_lang = get_language("python")     # tree_sitter.Language
  python_parser = get_parser("python")     # tree_sitter.Parser
  ```

* Pros:

  * 160+ languages bundled; no compiling grammars.
  * Uses vanilla `tree_sitter` Python bindings under the hood.

* For your universal parser, `get_parser(lang_name)` is the minimal entry point.

**10. Detecting language/grammar from file path**

* `tree-sitter-language-pack` itself does **not** provide extension detection; it only exposes language keys like `"python"`, `"javascript"`, `"markdown"`, `"hcl"`, `"dockerfile"`. ([PyPI][5])

Options:

1. **Static mapping table** in your project:

   * Map from extension or filename to language key, e.g.:

     * `.py` → `python`
     * `.js` / `.jsx` → `javascript`
     * `.ts` / `.tsx` → `typescript` or `tsx`
     * `.tf` → `hcl`
     * `Dockerfile` / `dockerfile` → `dockerfile`
     * `.md` → `markdown`
   * This satisfies “no per-language branches” at parsing level: the mapping can be declarative data, not code.

2. **External detectors**:

   * GitHub Linguist / `enry`-style detection or something like `pygments` or `chardet` + heuristics.

Given your stack, I’d start with a **simple extension→language registry JSON** inside your repo; the universal parser API just takes `language_key` and doesn’t care how it was computed.

**11. Performance profile**

From Tree-sitter docs and practitioner write-ups: ([tree-sitter.github.io][14])

* Parsing is extremely fast; it’s designed to run incrementally on keystrokes in editors.
* Memory:

  * Trees are compact and immutable; each node is a small C structure.
  * Python overhead is mainly from materialising `Node` wrappers as you traverse.

Implications:

* Use `TreeCursor` or `Node.walk()` to avoid creating too many Python objects.
* Avoid:

  * Deep recursion on very large trees (Python recursion limit).
  * Building your *own* heavyweight AST copies when you only need ranges and types.

For large files:

* Prefer a **stream-like traversal** (cursor) that yields your higher-level structural nodes and discards the rest.
* Don’t store the full CST in Python-side data structures unless you must; keep references (node IDs, ranges) instead.

**12. Handling syntax errors**

Tree-sitter is designed to operate on incomplete / syntactically invalid code. ([Hacker News][15])

* Error representation:

  * `Node.is_error`: node itself is an error.
  * `Node.has_error`: node contains errors somewhere below.
  * `Node.is_missing`: parser inserted a placeholder node to recover.
* Strategy:

  * Tree is still usable; simply treat `ERROR` nodes as structural boundaries or skip them.
  * In your structure tree:

    * Include a `has_errors` flag per structural node (derived from `node.has_error`).
    * Optionally keep `error_ranges` for diagnostics.

---

### Universal hierarchy design

**13. Strategies for language-agnostic AST abstractions**

Patterns from existing tools:

* **Semgrep generic AST**:

  * Parses code into language-specific ASTs.
  * Maps them into a “generic AST” – essentially the union of all language ASTs – with common node categories (assignments, calls, declarations, etc.). ([Semgrep][16])
  * Requires per-language mapping code.

* **ast-grep**:

  * Treats tree-sitter CST as base.
  * Derives a lighter-weight AST by keeping only **named nodes** and using node kinds + fields as core concepts. ([ast-grep.github.io][12])

* **Difftastic**:

  * Converts tree-sitter parse trees into **s-expressions** (everything is a list/atom) so diffing logic is language-agnostic. ([wilfred.me.uk][4])

* **GitHub Semantic**:

  * Generates per-language Haskell syntax types from tree-sitter grammars, then does cross-language analysis on a more generic intermediate representation. ([GitHub][17])

* **Symflower / type providers**:

  * Generate type ASTs and visitors from `node-types.json` so one framework can work with any grammar. ([Symflower][18])

Your constraints (“no per-language special cases”) suggest:

* Use **node-types metadata as the abstraction layer**:

  1. Parse `node-types.json` for each language once (build-time step).
  2. Auto-derive:

     * Which node types are “entities” (have a `name` field).
     * Which are “containers” (have `body` / block-like fields or many children).
     * Which are “supertypes” for declarations/expressions.
  3. Serialize per-language *classification tables* (data, not code).
  4. At runtime, load this table; your universal parser uses the same structural algorithm for all languages.

**14. Lessons from ctags, LSP, and similar tools**

* **Universal-ctags**:

  * Core is generic, but symbol extraction is defined per-language via regexes and parser definitions with a generic concept of “tag kinds” (function, class, variable, etc.). ([Medium][19])

* **Neovim tree-sitter ecosystem / Nova / kit**:

  * They use **tree-sitter queries** per language (e.g. highlight.scm, locals.scm, injections.scm, textobjects.scm) to define what counts as a symbol, fold, or text object. ([GitHub][20])
  * Core engine is generic; semantics come from language-specific query files (data).

Key takeaway for you:

> The successful multi-language tools keep the engine generic and use per-language *data* (node-types metadata and queries) to define semantics. Your universal parser should follow that architecture even if you initially rely only on heuristics.

**15. Taxonomy of “structural” node types**

A practical, language-agnostic taxonomy:

* `document` – root node (file/module/document).
* `section` – headings/sections/regions (Markdown sections, HTML `<section>`/`<article>`, Terraform top-level blocks).
* `container` – nodes that hold other declarations or statements (class, struct, namespace, module, object, Terraform `resource` block).
* `callable` – functions, methods, lambdas, procedures (nodes with parameters and a body).
* `declaration` – variable/field/const declarations, type declarations.
* `block` – lexical blocks or statement blocks (e.g. `{ ... }`, `suite` nodes).
* `mapping` – mapping/dictionary/object-like constructs (JSON objects, YAML mappings, HCL objects).
* `sequence` – lists/arrays (JSON/YAML lists, argument lists if you choose).
* `directive` – configuration directives or single-line commands (Dockerfile instructions, shell commands).
* `leaf_entity` – identifiers or headings that may stand alone (e.g. top-level `heading` or `tag` with no nested content).

The universal structure node schema can have:

```json
{
  "language": "python",
  "raw_kind": "class_definition",
  "category": "container",
  "label": "MyClass",
  "range": {
    "start": {"row": 1, "column": 0, "byte": 0},
    "end":   {"row": 20, "column": 0, "byte": 345}
  },
  "name_range": {...},
  "children": [ ... ],
  "has_errors": false
}
```

---

3. Code examples (Python, using tree-sitter-language-pack)

---

These examples assume:

```bash
uv init
uv add tree-sitter==0.25.2 tree-sitter-language-pack==0.11.0
```

And Python 3.11+.

### Example 1: Basic parsing

```python
from pathlib import Path
from tree_sitter_language_pack import get_parser

def parse_file(path: str, language: str):
    """
    Parse a file with tree-sitter-language-pack and print root + immediate children.
    """
    parser = get_parser(language)
    source_bytes = Path(path).read_bytes()

    tree = parser.parse(source_bytes)
    root = tree.root_node

    print(f"Language: {language}")
    print(f"Root type: {root.type}, named={root.is_named}")
    print("Immediate named children:")
    for child in root.named_children:
        start = child.start_point
        end = child.end_point
        print(
            f"  - {child.type} "
            f"[{start.row}:{start.column} – {end.row}:{end.column}] "
            f"named={child.is_named}"
        )

if __name__ == "__main__":
    # Examples:
    parse_file("example.py", "python")
    parse_file("example.js", "javascript")
    parse_file("README.md", "markdown")
```

### Example 2: Tree traversal and node collection

```python
from typing import Iterable, List
from tree_sitter_language_pack import get_parser
from tree_sitter import Node, Tree

def parse_source(source: str, language: str) -> Tree:
    parser = get_parser(language)
    return parser.parse(source.encode("utf8"))

# --- Recursive traversal ---

def walk_recursive(node: Node, depth: int = 0) -> None:
    indent = "  " * depth
    print(f"{indent}{node.type} (named={node.is_named})")
    for child in node.children:
        walk_recursive(child, depth + 1)

# --- TreeCursor traversal ---

def walk_with_cursor(root: Node) -> None:
    cursor = root.walk()

    def print_current():
        node = cursor.node
        depth = cursor.depth
        indent = "  " * depth
        print(f"{indent}{node.type} (named={node.is_named})")

    # Pre-order DFS using cursor
    visited_children = set()

    print_current()
    if cursor.goto_first_child():
        while True:
            print_current()
            if cursor.goto_first_child():
                continue
            while not cursor.goto_next_sibling():
                if not cursor.goto_parent():
                    return

# --- Collect all nodes of a given type (by name) ---

def find_nodes_of_type(root: Node, type_name: str) -> List[Node]:
    matches: List[Node] = []

    def recurse(node: Node):
        if node.type == type_name:
            matches.append(node)
        for child in node.children:
            recurse(child)

    recurse(root)
    return matches


if __name__ == "__main__":
    python_code = """
class Foo:
    def bar(self, x):
        return x + 1
"""
    tree = parse_source(python_code, "python")
    root = tree.root_node

    print("=== Recursive traversal ===")
    walk_recursive(root)

    print("\n=== Cursor traversal ===")
    walk_with_cursor(root)

    print("\n=== All function defs ===")
    funcs = find_nodes_of_type(root, "function_definition")
    for fn in funcs:
        print(fn.type, fn.start_point, fn.end_point)
```

### Example 3: Node inspection

```python
from tree_sitter_language_pack import get_parser
from tree_sitter import Node
from pathlib import Path
from dataclasses import dataclass

@dataclass
class NodeInfo:
    type: str
    start_row: int
    start_col: int
    end_row: int
    end_col: int
    text: str
    named_children_types: list[str]
    parent_type: str | None


def inspect_node(node: Node, source_bytes: bytes) -> NodeInfo:
    start = node.start_point
    end = node.end_point
    # Prefer slicing over node.text for clarity and control
    snippet = source_bytes[node.start_byte:node.end_byte].decode("utf8", errors="replace")

    named_children_types = [child.type for child in node.named_children]
    parent_type = node.parent.type if node.parent is not None else None

    return NodeInfo(
        type=node.type,
        start_row=start.row,
        start_col=start.column,
        end_row=end.row,
        end_col=end.column,
        text=snippet,
        named_children_types=named_children_types,
        parent_type=parent_type,
    )


def demo_inspect(path: str, language: str):
    parser = get_parser(language)
    source_bytes = Path(path).read_bytes()
    tree = parser.parse(source_bytes)
    root = tree.root_node

    # Take first named child as an example
    node = root.named_children[0] if root.named_children else root
    info = inspect_node(node, source_bytes)

    print(f"Type: {info.type}")
    print(f"Range: ({info.start_row}, {info.start_col}) -> ({info.end_row}, {info.end_col})")
    print(f"Parent type: {info.parent_type}")
    print(f"Named children: {info.named_children_types}")
    print("Source text:")
    print(info.text)


if __name__ == "__main__":
    demo_inspect("example.py", "python")
```

### Example 4: Cross-language comparison (Python / JS / Markdown)

```python
from tree_sitter_language_pack import get_parser

def summarize_top_level(language: str, source: str):
    parser = get_parser(language)
    tree = parser.parse(source.encode("utf8"))
    root = tree.root_node

    print(f"=== {language} ===")
    print(f"Root: {root.type}")
    for child in root.named_children:
        print(f"  - {child.type} [{child.start_point.row}:{child.start_point.column}"
              f"–{child.end_point.row}:{child.end_point.column}]")
    print()

if __name__ == "__main__":
    python_src = """
class Foo:
    def bar(self, x):
        return x + 1
"""
    js_src = """
class Foo {
  bar(x) {
    return x + 1;
  }
}
"""
    md_src = """
# Foo

## Bar

Some text here.
"""

    summarize_top_level("python", python_src)
    summarize_top_level("javascript", js_src)
    summarize_top_level("markdown", md_src)
```

Typical output (conceptually):

* Python:

  * Root: `module` or `source_file`
  * Child: `class_definition` → contains `function_definition` children.

* JavaScript:

  * Root: `program`
  * Child: `class_declaration` → contains `method_definition`.

* Markdown:

  * Root: `document` or `source_file`
  * Children: `atx_heading`, `section` (depending on grammar).

You can see that **node types differ** but the structural pattern “top-level container with nested items” is similar.

### Example 5: Structural node identification (generic heuristic)

This is a *prototype* demonstrating how you might pick “structural” nodes without language-specific branches, using only type names, span, and children.

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
from tree_sitter_language_pack import get_parser
from tree_sitter import Node, Tree

@dataclass
class StructuralNode:
    language: str
    raw_kind: str          # node.type
    category: str          # from taxonomy (approx)
    label: str | None
    start_row: int
    start_col: int
    end_row: int
    end_col: int
    children: List["StructuralNode"] = field(default_factory=list)


NAME_HINTS = ("name", "identifier", "heading", "tag_name", "label")

def guess_category(node: Node) -> str:
    kind = node.type.lower()

    if node.parent is None:
        return "document"

    if "class" in kind:
        return "container"
    if "function" in kind or "method" in kind or "lambda" in kind or "arrow_function" in kind:
        return "callable"
    if "block" in kind or "suite" in kind or "body" in kind:
        return "block"
    if "section" in kind or "heading" in kind:
        return "section"
    if "object" in kind or "mapping" in kind or "dict" in kind:
        return "mapping"
    if "array" in kind or "list" in kind or "sequence" in kind:
        return "sequence"
    if "declaration" in kind or "definition" in kind:
        return "declaration"
    if "instruction" in kind or "command" in kind:
        return "directive"

    # Fallback: treat large spans as containers, others as generic
    line_span = node.end_point.row - node.start_point.row
    if line_span >= 3 and len(node.named_children) >= 2:
        return "container"

    return "other"


def guess_label(node: Node) -> str | None:
    # Heuristic: look for child types that sound like "name" or identifiers
    for child in node.named_children:
        child_kind = child.type.lower()
        if any(hint in child_kind for hint in NAME_HINTS):
            # Use node text slice as label
            return child.text.decode("utf8", errors="replace") if hasattr(child, "text") else None
    return None


def is_structural(node: Node) -> bool:
    if not node.is_named or node.is_extra:
        return False

    # Skip very small nodes (single-token expressions, etc.)
    line_span = node.end_point.row - node.start_point.row
    if line_span == 0 and len(node.named_children) <= 1:
        return False

    # Top-level named children are always structural
    if node.parent is not None and node.parent.parent is None:
        return True

    # Nodes with many named descendants are structural
    if len(node.named_children) >= 2:
        return True

    # Nodes whose kind suggests structure
    cat = guess_category(node)
    return cat in {"document", "container", "callable", "section", "block", "mapping", "sequence"}


def build_structure_tree(language: str, tree: Tree) -> StructuralNode:
    root = tree.root_node

    def build(node: Node) -> StructuralNode | None:
        if not is_structural(node) and node.parent is not None:
            # Recurse into children but don't emit this node
            structural_children = []
            for child in node.named_children:
                child_struct = build(child)
                if child_struct is not None:
                    structural_children.append(child_struct)
            # Flatten: pass children up
            if structural_children:
                # Attach children directly to parent in caller
                # Caller will extend its children with this list
                # Implementation detail: handled in caller
                pass
            return None

        cat = guess_category(node)
        label = guess_label(node)
        struct = StructuralNode(
            language=language,
            raw_kind=node.type,
            category=cat,
            label=label,
            start_row=node.start_point.row,
            start_col=node.start_point.column,
            end_row=node.end_point.row,
            end_col=node.end_point.column,
        )
        for child in node.named_children:
            child_struct = build(child)
            if child_struct is not None:
                struct.children.append(child_struct)
        return struct

    result = build(root)
    assert result is not None
    return result


if __name__ == "__main__":
    examples = {
        "python": """
class Foo:
    def bar(self, x):
        return x + 1
""",
        "javascript": """
class Foo {
  bar(x) {
    return x + 1;
  }
}
""",
        "markdown": """
# Foo

## Bar

Some text
""",
        "dockerfile": """
FROM python:3.11-slim
RUN pip install uv
CMD ["python", "main.py"]
""",
    }

    for lang, src in examples.items():
        parser = get_parser(lang)
        tree = parser.parse(src.encode("utf8"))
        struct = build_structure_tree(lang, tree)
        print(f"=== {lang} structure tree ===")

        def print_struct(n: StructuralNode, depth: int = 0):
            indent = "  " * depth
            label = f" {n.label!r}" if n.label else ""
            print(f"{indent}{n.category}:{label} ({n.raw_kind})")
            for c in n.children:
                print_struct(c, depth + 1)

        print_struct(struct)
        print()
```

This is crude but honors your constraint: **no `if language == ...` branches**. You can refine the heuristics and later plug in metadata from `node-types.json` to improve accuracy.

---

4. Recommended architecture: universal structure tree

---

Putting this together, here is a concrete architecture you can design toward.

### 4.1. Data model

**Core DTOs**

In Python-ish pseudocode (but language-agnostic conceptually):

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional

class StructuralCategory(str, Enum):
    DOCUMENT   = "document"
    SECTION    = "section"
    CONTAINER  = "container"
    CALLABLE   = "callable"
    DECLARATION = "declaration"
    BLOCK      = "block"
    MAPPING    = "mapping"
    SEQUENCE   = "sequence"
    DIRECTIVE  = "directive"
    OTHER      = "other"

@dataclass
class Position:
    row: int
    column: int
    byte: int

@dataclass
class Range:
    start: Position
    end: Position

@dataclass
class StructuralNode:
    language: str
    raw_kind: str              # node.type
    category: StructuralCategory
    label: Optional[str]
    range: Range
    name_range: Optional[Range]
    has_errors: bool
    children: List["StructuralNode"] = field(default_factory=list)

@dataclass
class FileStructure:
    language: str
    root: StructuralNode
```

Key design points:

* Always include `raw_kind` and language so you can inspect the original CST when needed.
* `category` is your universal taxonomy.
* `label` is a human-friendly display name (class name, function name, heading text, block label, etc.).
* `range` and `name_range` rely on tree-sitter’s byte/point ranges; textual extraction is a separate concern.

### 4.2. Pipeline (per file)

1. **Language detection**

   * Input: file path, optional override language key.
   * Output: language key compatible with `get_parser`.

2. **Parsing**

   * `parser = get_parser(language_key)`
   * `tree = parser.parse(source_bytes)`

3. **Error analysis**

   * Check `tree.root_node.has_error` to set top-level `has_errors`.
   * Optionally build a list of error nodes/ranges.

4. **Structural classification**

   * Load language-specific **classification metadata** (if available) precomputed from `node-types.json`:

     * For each `type`, store:

       * `is_entity` (has `name` field).
       * `is_container` (has `body`/block fields or long `children`).
       * `supertype` membership (`_declaration`, `_expression`, etc.).
   * If metadata not available, fall back to heuristics on `node.type` and child structure as in Example 5.

5. **Structure tree construction**

   * Pre-order traversal with `TreeCursor`, visiting only `is_named` nodes.
   * For each candidate:

     * Compute `category` from metadata/heuristics.
     * Compute `label` by examining `name` fields or identifier-like children.
     * Attach as child of the nearest ancestor node whose category you treat as a container/section.

6. **Output**

   * Serialize `FileStructure` to JSON.
   * Optionally provide back-references to original tree-sitter node IDs or byte ranges for later navigation.

### 4.3. No per-language code constraint

To keep per-language specialization in *data* rather than code:

* Introduce a `language_metadata/` folder in your repo containing JSON for each language, generated offline from:

  * `node-types.json` (from each grammar repo). ([tree-sitter.github.io][3])
  * A generic analysis script that:

    * Marks node types with `name` fields as entities.
    * Marks node types with `body` / `block` fields as containers.
    * Detects `_declaration` / `_expression` supertypes to tag them.

Your runtime engine:

* Knows nothing about Python vs JavaScript vs Terraform; it only:

  * Reads `language_metadata[language_key]`.
  * Applies the same classification algorithm for all languages.

That satisfies “single parser” in the architectural sense.

---

5. Risk assessment

---

**1. Common mistakes with tree-sitter in Python**

* **Byte vs character offsets**:

  * Node ranges are in **bytes** and points (row/column).
  * If you index the decoded string by characters using byte offsets, you risk slicing in the middle of multi-byte UTF-8 code points.
  * Mitigation: always slice the original `bytes` with `start_byte/end_byte` and then decode.

* **Excessive Python-side trees**:

  * Building large Python object graphs mirroring the entire CST is unnecessary and memory-heavy.
  * Mitigation: store only structural nodes plus ranges; keep a pointer to the tree if needed, not every node.

* **Grammar loading failures / ABI mismatches**:

  * Using mismatched versions of `tree-sitter` and compiled grammars can cause errors (e.g. language ABI version > library). ([tree-sitter.github.io][7])
  * Mitigation: use `tree-sitter-language-pack` which aligns with `tree-sitter 0.25.x` and Python 3.10+. ([PyPI][5])

* **Ignoring `has_error`/`is_missing`**:

  * If you treat trees as always valid, you may misinterpret malformed regions.
  * Mitigation: propagate `has_errors` and treat `ERROR` nodes explicitly in your structure.

**2. Pitfalls in cross-grammar abstraction**

* **Over-generalizing**:

  * Forcing everything into “class/function” buckets will distort Markdown, Terraform, Dockerfile semantics.
  * Mitigation: use more abstract categories (`section`, `container`, `directive`, `mapping`) and keep `raw_kind` around.

* **Under-generalizing**:

  * Defining dozens of categories to capture every nuance will defeat the purpose of a universal model.
  * Mitigation: keep core taxonomy small (~8–10 categories) and introduce optional tags or attributes for nuance.

* **Assumed consistency**:

  * Not all grammars follow the same naming conventions; some may use `subroutine`, `procedure`, `resource`, etc.
  * Mitigation: rely on **fields** and **supertypes** in node-types JSON (e.g., `fields.name`, `fields.parameters`, `fields.body`) more than substring matches. ([tree-sitter.github.io][3])

**3. Performance anti-patterns**

* Traversing using `node.child(i)` in tight loops instead of `children`/`walk()` (logarithmic vs linear access). ([tree-sitter.github.io][1])
* Parsing the same file multiple times instead of reusing `Tree` and incremental parsing.
* Doing heavy substring extraction (`decode` on large subtrees) when you only need ranges/metadata.

**4. Node-type assumptions that break**

* “All languages have classes” – many don’t (Bash, JSON, YAML).
* “Functions look the same” – signature syntax varies widely; some languages use separate nodes for `params`, others inline.
* “Nesting implies lexical containment” – Markdown headings may not be represented as container nodes; older grammars treat headings as flat blocks. ([GitHub][10])

Mitigation: treat your universal model as **approximate structure**; keep raw CST details available for advanced use cases.

---

6. Integration considerations

---

### Development workflow

* **Exploratory Jupyter notebooks**:

  * Use notebooks to:

    * Inspect parse trees for various languages.
    * Prototype heuristics for `is_structural`, `guess_category`, and `guess_label`.
    * Visualize structure trees.

* **Production code layout** (Python project):

  ```
  universal_parser/
    __init__.py
    languages/
      __init__.py
      registry.py          # extension ↔ language mapping
      metadata/
        python.json
        javascript.json
        markdown.json
        ...
    model.py               # StructuralNode, enums, ranges
    tree_sitter_adapter.py # thin wrapper around tree-sitter-language-pack
    classifier.py          # heuristics + metadata-based classification
    builder.py             # turns Node → StructuralNode tree
    cli.py                 # optional command-line interface
    tests/
      test_python_structure.py
      test_markdown_structure.py
      ...
  ```

* Keep **all direct tree-sitter usage** behind `tree_sitter_adapter.py`, so if you change bindings or language pack, the rest of the code is insulated.

### Testing strategy

* **Golden snapshot tests**:

  * For each language, keep small fixtures and expected structure-tree JSON.
  * On changes to heuristics or grammars, diff the JSON.
  * For example:

    * `tests/fixtures/python/class_methods.py`
    * `tests/expected/python/class_methods.json`

* **Grammar version updates**:

  * When `tree-sitter-language-pack` is upgraded:

    * Re-generate `language_metadata/*` from updated node-types.json files.
    * Re-run snapshot tests to catch changed node types.

* **Cross-language regression**:

  * Design test suites that assert *invariants* across languages:

    * Root category must be `document`.
    * Every child range must be contained within its parent.
    * No overlapping siblings.

### Future extensions

* **Support for new languages**:

  * Add entry to extension→language registry.
  * Generate metadata from `node-types.json`.
  * Run generic tests; no code changes needed in core engine.

* **Custom queries (“find all async functions”)**:

  * Tree-sitter’s query language is excellent for expressing such patterns. ([tree-sitter.github.io][21])
  * You can:

    * Maintain generic queries, e.g. `(function_declaration (modifiers (modifier) @mod) ...) @async` per language, but that *is* per-language data.
    * Or expose a lower-level query API for advanced users and keep your universal model as a separate layer.

* **Query language relevance to your use case**:

  * For structure parsing alone, you don’t *have* to use queries: walking the tree is enough.
  * For more semantic features (find calls, references, patterns), queries are the standard approach and integrate naturally.

---

7. Next steps (exploration phase)

---

A concrete plan for the next 1–2 iterations:

1. **Bootstrap the repo**

   * Set up `uv` project.
   * Add dependencies: `tree-sitter`, `tree-sitter-language-pack`.
   * Implement minimal wrapper: `get_parser(language)` and `parse_file(path, language)`.

2. **Build a “structure inspector” notebook**

   * For 5–6 languages (Python, JS/TS, Markdown, HCL, Dockerfile, YAML):

     * Parse sample files.
     * Pretty-print named nodes (type, range, depth).
     * Experiment with `is_structural` heuristics until results look reasonable.

3. **Prototype the universal structure model**

   * Implement `StructuralNode` and `FileStructure`.
   * Implement `build_structure_tree(language, tree)` using only heuristics (like Example 5).
   * Serialize to JSON and review results manually.

4. **Introduce metadata-driven classification**

   * Write an offline script that:

     * Downloads or reads each language’s `node-types.json`.
     * Produces per-language metadata JSON (`language_metadata/{lang}.json`) with properties inferred from fields and supertypes. ([tree-sitter.github.io][3])
   * Update `classifier.py` to use metadata when available, fallback to heuristics otherwise.

5. **Establish snapshot tests**

   * Pick a dozen fixtures across formats.
   * Record structure-tree JSON outputs as golden files.
   * Integrate into CI.

6. **Evaluate and refine**

   * Inspect where heuristics misclassify nodes (especially in Markdown, Terraform, and Dockerfile).
   * Adjust taxonomy and scoring rules, keeping core categories stable.

If you like, the next step can be to design the precise JSON schema for `language_metadata/*` (fields, supertypes, scoring weights) and sketch how the offline generator would analyze `node-types.json` to fill it.

[1]: https://tree-sitter.github.io/py-tree-sitter/classes/tree_sitter.Node.html "Node — py-tree-sitter 0.25.2 documentation"
[2]: https://tree-sitter.github.io/py-tree-sitter/classes/tree_sitter.Node.html?utm_source=chatgpt.com "Node — py-tree-sitter 0.25.2 documentation"
[3]: https://tree-sitter.github.io/tree-sitter/using-parsers/6-static-node-types "Static Node Types - Tree-sitter"
[4]: https://www.wilfred.me.uk/blog/2022/09/06/difftastic-the-fantastic-diff/?utm_source=chatgpt.com "Difftastic, the Fantastic Diff – Wilfred Hughes::Blog"
[5]: https://pypi.org/project/tree-sitter-language-pack/ "tree-sitter-language-pack · PyPI"
[6]: https://tree-sitter.github.io/py-tree-sitter/classes/tree_sitter.TreeCursor.html "TreeCursor — py-tree-sitter 0.25.2 documentation"
[7]: https://tree-sitter.github.io/py-tree-sitter/ "py-tree-sitter — py-tree-sitter 0.25.2 documentation"
[8]: https://stackoverflow.com/questions/63635500/how-to-get-the-values-from-nodes-in-tree-sitter?utm_source=chatgpt.com "How to get the values from nodes in tree-sitter?"
[9]: https://docs.rs/tree-sitter-md?utm_source=chatgpt.com "tree_sitter_md - Rust"
[10]: https://github.com/ikatyang/tree-sitter-markdown/issues/19?utm_source=chatgpt.com "Hierarchical syntax tree · Issue #19 · ikatyang/tree-sitter- ..."
[11]: https://docs.rs/tree-sitter-hcl?utm_source=chatgpt.com "tree_sitter_hcl - Rust"
[12]: https://ast-grep.github.io/advanced/core-concepts.html?utm_source=chatgpt.com "Core Concepts in ast-grep's Pattern"
[13]: https://github.com/nvim-treesitter/nvim-treesitter/issues/2145?utm_source=chatgpt.com "[markdown] Allow to fold headers · Issue #2145 · nvim- ..."
[14]: https://tree-sitter.github.io/tree-sitter/using-parsers/?utm_source=chatgpt.com "Using Parsers - Tree-sitter"
[15]: https://news.ycombinator.com/item?id=26225298&utm_source=chatgpt.com "Tree-sitter: an incremental parsing system for programming ..."
[16]: https://semgrep.dev/blog/2020/type-awareness-in-semantic-grep?utm_source=chatgpt.com "Type-awareness in semantic grep"
[17]: https://github.com/github/semantic?utm_source=chatgpt.com "github/semantic: Parsing, analyzing, and comparing source ..."
[18]: https://symflower.com/en/company/blog/2023/parsing-code-with-tree-sitter/?utm_source=chatgpt.com "TreeSitter - the holy grail of parsing source code"
[19]: https://medium.com/%40linz07m/lesser-known-but-useful-universal-ctags-flags-with-examples-fbc0266f4dfe?utm_source=chatgpt.com "Lesser-Known but Useful Universal Ctags Flags with ..."
[20]: https://github.com/nvim-treesitter/nvim-treesitter?utm_source=chatgpt.com "Nvim Treesitter configurations and abstraction layer"
[21]: https://tree-sitter.github.io/tree-sitter/using-parsers/queries/1-syntax.html?utm_source=chatgpt.com "Query Syntax - Tree-sitter"
