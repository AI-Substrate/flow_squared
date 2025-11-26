# Tree-sitter Exploration Findings

**Analysis Date**: 2025-11-26
**Formats Analyzed**: 16 (Python, JS, TS, Go, Rust, C++, C#, Dart, Markdown, Terraform, Dockerfile, YAML, JSON, TOML, SQL, Shell)
**Package Version**: tree-sitter-language-pack==0.11.0

---

## Executive Summary

Tree-sitter grammars are **more consistent than expected**, with clear patterns that make a universal abstraction **feasible**. The key insight is that most structural variation is in **naming conventions**, not **structural organization**. All grammars produce hierarchical ASTs with named vs anonymous node distinction, consistent position/byte metadata, and predictable parent-child relationships.

**Recommendation**: Build a universal parser using:
1. `is_named` filter to focus on structural nodes
2. Suffix-based type classification (`*_definition`, `*_declaration`, etc.)
3. Common field names (`name`, `body`, `parameters`) for extraction
4. Format-family groupings for specialized handling where needed

---

## Answers to Spec's 10 Open Questions

### Q1: Node Naming Consistency

**Finding**: Naming conventions are **format-family consistent**, not universal.

| Family | Pattern | Examples |
|--------|---------|----------|
| Python/Dart | `*_definition` | `class_definition`, `function_definition` |
| JS/TS/Go/Rust/C++/C# | `*_declaration` | `class_declaration`, `function_declaration` |
| Rust | `*_item` | `struct_item`, `function_item`, `impl_item` |
| C++ | `*_specifier` | `class_specifier`, `enum_specifier` |
| SQL/Shell | `*_statement` | `select_statement`, `if_statement` |

**Action**: Use suffix-based classification. Map all `*_definition`, `*_declaration`, `*_item`, `*_specifier` patterns to a universal `declaration` category.

### Q2: Field Availability

**Finding**: Field richness varies **dramatically** by grammar.

| Category | Examples | Field Count | Common Fields |
|----------|----------|-------------|---------------|
| Rich | Go, TS, Rust, C++ | 20-26 | name, body, parameters, left, right |
| Medium | Python, JS, Dart | 15-19 | name, body, parameters |
| Sparse | JSON, YAML, HCL | 2-7 | key, value |
| None | TOML | 0 | (uses children only) |

**Action**: Don't rely on field names for all grammars. Use hybrid approach:
- Check for field `name` first
- Fall back to child traversal with type heuristics

### Q3: Hierarchy Representation

**Finding**: **100% consistent** - all grammars use nested `children` arrays.

Every node has:
- `children[]` containing all child nodes
- `is_named` distinguishing structural vs syntactic nodes
- `type` identifying the node kind

No grammars use "flat with parent pointers" or other alternative representations.

**Action**: Traverse via `children[]` universally. Filter by `is_named=true` for structural elements.

### Q4: Taxonomy Feasibility

**Finding**: **Yes, feasible** with format families.

Proposed universal categories:
```
container    → module, program, source_file, document, config_file, stream
definition   → *_definition, *_declaration, *_item, *_specifier
callable     → function_*, method_*, *_signature
type         → class_*, struct_*, interface_*, enum_*, type_*
statement    → *_statement
expression   → *_expression
literal      → string, number, boolean, null, identifier
block        → *_block, body, compound_statement
```

### Q5: Markdown Structure

**Finding**: Markdown produces **flat headings**, not nested sections.

```json
// sample_repo/markdown/sample.md produces:
{
  "type": "document",
  "children": [
    {"type": "atx_heading"},      // # Section 1
    {"type": "paragraph"},
    {"type": "atx_heading"},      // ## Subsection 1.1
    {"type": "paragraph"},
    {"type": "atx_heading"},      // ### Subsection 1.1.1
    ...
  ]
}
```

No `section` nodes - just flat `atx_heading` nodes with level determined by leading `#` count.

**Action**: For Markdown, post-process headings into nested sections based on heading level. Tree-sitter gives us the raw structure; nesting must be inferred.

### Q6: Configuration Format Consistency

**Finding**: YAML, JSON, TOML, HCL use **different but mappable** structures.

| Format | Object/Map Type | Array Type | Key-Value Pattern |
|--------|----------------|------------|-------------------|
| JSON | `object` | `array` | child with `field_name: "key"` + `field_name: "value"` |
| YAML | `block_mapping` | `block_sequence` | `block_mapping_pair` with key/value fields |
| TOML | `table` | `array` | `pair` with implicit key from position |
| HCL | `block` | `tuple` | `attribute` with key/val fields |

**Action**: Create config-family adapter that normalizes to `{type: "mapping", entries: [{key, value}]}`.

### Q7: Metadata Richness

**Finding**: Metadata richness correlates with grammar maturity.

Richest (most semantic info):
- TypeScript (type annotations, modifiers, decorators)
- C# (attributes, modifiers, generics)
- Rust (visibility, lifetimes, attributes)

Leanest (minimal):
- JSON (just structure)
- TOML (structure only)
- Dockerfile (instruction-focused)

**Action**: Extract what's available; don't require specific metadata fields.

### Q8: Edge Cases

**Finding**: Several challenging patterns identified.

| Pattern | Challenge | Format(s) |
|---------|-----------|-----------|
| Nested functions | Functions inside functions | Python, JS, Go |
| Anonymous functions | Lambda/arrow/closure | JS, TS, Rust, Dart |
| Multi-stage builds | Logical groupings (FROM-based) | Dockerfile |
| Decorated definitions | Decorators wrapping other nodes | Python, TS, Dart |
| Module references | Cross-file dependencies | Terraform, Go |
| Async/await | Async modifiers | All modern languages |

**Action**: Handle via parent context. E.g., `function_definition` inside `function_definition` = nested function.

### Q9: Byte vs Line Ranges

**Finding**: **100% availability** - all grammars provide both.

Every node has:
- `start_byte`, `end_byte` - byte offsets
- `start_point`, `end_point` - {row, column} (0-indexed)

**Action**: Include both in universal output. Use bytes for text extraction, points for UI.

### Q10: Universal Abstraction Viability

**Finding**: **YES, viable** with caveats.

Viable because:
1. All grammars produce hierarchical trees
2. `is_named` universally separates structure from syntax
3. Consistent metadata (bytes, points, children)
4. Suffix patterns enable type classification

Caveats:
1. Can't expect identical node types across formats
2. Some grammars have no field names (must use positional children)
3. Markdown needs post-processing for section nesting
4. Config formats need normalization layer

---

## Statistical Analysis

### Output Sizes

| Format | Nodes | Named Nodes | Unique Types | Source Lines |
|--------|-------|-------------|--------------|--------------|
| Python | 545 | 363 (67%) | 44 | 85 |
| JavaScript | 684 | 376 (55%) | 50 | 107 |
| TypeScript | 1110 | 630 (57%) | 78 | 149 |
| Go | 1191 | 763 (64%) | 71 | 171 |
| Rust | 1820 | 1010 (55%) | 87 | 202 |
| C++ | 1732 | 1039 (60%) | 83 | 214 |
| C# | 1744 | 1061 (61%) | 86 | 238 |
| Dart | 1823 | 1114 (61%) | 121 | 237 |
| Markdown | 567 | 261 (46%) | 36 | 152 |
| Terraform | 1696 | 1368 (81%) | 40 | 230 |
| Dockerfile | 471 | 274 (58%) | 33 | 159 |
| YAML | 1454 | 1219 (84%) | 27 | 229 |
| JSON | 1185 | 542 (46%) | 11 | 165 |
| TOML | 1128 | 581 (52%) | 17 | 233 |
| SQL | 2175 | 1755 (81%) | 171 | 351 |
| Shell | 2396 | 1472 (61%) | 49 | 444 |

**Observation**: Named node ratio ranges from 46% (JSON, Markdown) to 84% (YAML). Config formats have higher ratios because they have less punctuation syntax.

### Root Node Types

| Root Type | Languages |
|-----------|-----------|
| `module` | Python |
| `program` | JavaScript, TypeScript, Dart, SQL, Bash |
| `source_file` | Go, Rust, Dockerfile |
| `translation_unit` | C++ |
| `compilation_unit` | C# |
| `document` | Markdown, JSON, TOML |
| `config_file` | HCL (Terraform) |
| `stream` | YAML |

**Observation**: 8 distinct root types across 16 formats. Must handle dynamically, not hardcoded.

### Common Field Names (Found in 5+ grammars)

```
name          → 14/16 grammars (not JSON, TOML)
body          → 11/16 grammars
left/right    → 13/16 grammars
arguments     → 10/16 grammars
parameters    → 9/16 grammars
condition     → 8/16 grammars
key/value     → 7/16 grammars
operator      → 9/16 grammars
```

---

## Recommended Production Architecture

Based on these findings, here's the recommended approach:

### 1. Universal Node Model

```python
@dataclass
class UniversalNode:
    # Identity
    type: str              # Original tree-sitter type
    category: str          # Normalized category (definition, callable, etc.)

    # Source location (always available)
    start_byte: int
    end_byte: int
    start_line: int        # 1-indexed for humans
    end_line: int
    start_column: int
    end_column: int

    # Content
    text: str | None       # For leaf/small nodes
    name: str | None       # Extracted via field or heuristic

    # Structure
    children: list[UniversalNode]
    is_named: bool

    # Grammar info
    language: str
    field_name: str | None  # Relationship to parent
```

### 2. Category Classification

```python
def classify_node(node_type: str, language: str) -> str:
    """Map tree-sitter node type to universal category."""

    # Direct mappings
    if node_type in ('module', 'program', 'source_file', 'document',
                     'compilation_unit', 'translation_unit', 'config_file', 'stream'):
        return 'container'

    # Suffix patterns
    if node_type.endswith(('_definition', '_declaration', '_item', '_specifier')):
        if 'function' in node_type or 'method' in node_type:
            return 'callable'
        if any(x in node_type for x in ('class', 'struct', 'interface', 'enum', 'type')):
            return 'type'
        return 'definition'

    if node_type.endswith('_statement'):
        return 'statement'

    if node_type.endswith('_expression'):
        return 'expression'

    if node_type.endswith('_block') or node_type == 'body':
        return 'block'

    # Literals
    if node_type in ('string', 'number', 'integer', 'float', 'boolean',
                     'true', 'false', 'null', 'none', 'identifier'):
        return 'literal'

    return 'other'
```

### 3. Name Extraction

```python
def extract_name(node, source: bytes) -> str | None:
    """Extract the 'name' of a node using available methods."""

    # Method 1: Check for 'name' field
    for child in node.children:
        if child.field_name == 'name':
            return source[child.start_byte:child.end_byte].decode()

    # Method 2: Type-specific heuristics
    if node.type in ('class_definition', 'class_declaration'):
        # Usually: class NAME ...
        for child in node.named_children:
            if child.type == 'identifier':
                return source[child.start_byte:child.end_byte].decode()

    # Method 3: First identifier child
    for child in node.named_children:
        if child.type == 'identifier':
            return source[child.start_byte:child.end_byte].decode()

    return None
```

### 4. Format Family Handlers

For specialized handling:

```python
FORMAT_FAMILIES = {
    'code_oop': ['python', 'javascript', 'typescript', 'dart', 'csharp', 'java'],
    'code_systems': ['go', 'rust', 'cpp', 'c'],
    'config_kv': ['json', 'yaml', 'toml', 'hcl'],
    'markup': ['markdown', 'html', 'xml'],
    'query': ['sql'],
    'shell': ['bash', 'fish', 'powershell'],
    'iac': ['dockerfile', 'hcl'],
}
```

---

## Gotchas and Warnings

1. **TOML has no field names** - Must use positional child access
2. **Markdown headings are flat** - Need post-processing for nesting
3. **Dockerfile stages aren't grouped** - FROM instructions don't create containers
4. **C# grammar is `csharp`** - Not `c_sharp` as some docs suggest
5. **Terraform uses `hcl` grammar** - Not `terraform`
6. **Anonymous nodes dominate** - 35-54% of nodes are syntax (punctuation)
7. **SQL has 171 unique types** - Most complex grammar by far
8. **YAML uses `stream` root** - Multi-document aware, not single document

---

## Next Steps

1. **Implement UniversalNode model** with category classification
2. **Build name extraction** with field → heuristic fallback
3. **Create format family adapters** for specialized handling
4. **Add Markdown section nesting** post-processor
5. **Test on real-world files** beyond samples
6. **Benchmark performance** for large files

---

## Appendix: Sample jq Queries

```bash
# Get all class/function definitions
cat outputs/python_sample.json | jq '.. | select(.type? | test("class_|function_")?) | {type, name: .children[]? | select(.field_name == "name") | .text}'

# Count nodes by category
cat outputs/go_sample.json | jq '[.. | .type? // empty | if endswith("_declaration") then "declaration" elif endswith("_expression") then "expression" elif endswith("_statement") then "statement" else "other" end] | group_by(.) | map({category: .[0], count: length})'

# Compare root structures across all files
for f in outputs/*.json; do echo "=== $f ==="; cat "$f" | jq '.root | {type, child_types: [.children[]?.type] | unique}'; done
```
