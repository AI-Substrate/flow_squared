# Research Dossier: Tree-Sitter AST + LSP Integration for Call Detection

**Generated**: 2026-01-23T22:31:14Z  
**Research Query**: "How current node extraction works (existing AST with tree-sitter) and what LSP needs, and how to bring the two worlds together"  
**FlowSpace**: Available  
**Findings**: 70+ from 7 parallel subagents  

---

## Executive Summary

### The Core Problem

The LSP integration for "what do I call" detection was fundamentally flawed:
- **Naive approach**: Scanned every line in function bodies at 8 fixed column positions (4,8,12,16,20,24,28,32)
- **Result**: Hundreds of thousands of useless LSP `get_definition` queries
- **99%+ returned None** because random column positions don't contain call expressions
- **Fix applied**: Removed line-scanning; only `get_references` (who calls me) remains active

### The Missing Piece

**LSP `get_definition` must be called at CALL SITE positions** — the exact (line, column) where a function call like `foo()` appears in the source code. Tree-sitter already parses these positions; we just need to extract and use them.

### Key Insights

1. **Tree-sitter already provides call expression positions** — node type `call` (Python) or `call_expression` (TS/Go) with exact `start_point` (line, column)
2. **CodeNode currently skips call expressions** — category filter extracts only `type`, `callable`, `section`, `block`
3. **Two viable solutions exist**: 
   - A) Extract call positions during ParsingStage (enrich CodeNode)
   - B) Re-parse content in RelationshipExtractionStage to find calls on-demand

### Quick Stats

| Metric | Value |
|--------|-------|
| Languages affected | Python, TypeScript, JavaScript, Go, C# |
| Call node types | `call` (Python), `call_expression` (TS/JS/Go) |
| Current extraction | SKIPPED (category filter line 642) |
| LSP queries saved | ~100,000+ per scan |
| Tree-sitter position format | 0-indexed (row, column) |
| LSP position format | 0-indexed (line, character) |

---

## Part 1: How Current AST Extraction Works

### 1.1 Architecture Overview

```
┌─────────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   DiscoveryStage    │────▶│   ParsingStage   │────▶│ RelationshipStage   │
│   (find files)      │     │   (tree-sitter)  │     │ (LSP + text)        │
└─────────────────────┘     └──────────────────┘     └─────────────────────┘
         │                          │                         │
         ▼                          ▼                         ▼
   scan_results              context.nodes              context.relationships
   (file paths)              (CodeNode list)            (CodeEdge list)
```

### 1.2 Tree-Sitter Parser Flow (ast_parser_impl.py)

```python
# Language detection: 154 extension mappings
EXTENSION_TO_LANGUAGE = {".py": "python", ".ts": "typescript", ...}

# Parser initialization (cached per language)
parser = get_parser(language)  # From tree_sitter_language_pack
tree = parser.parse(content.encode("utf-8"))

# Node extraction: recursive traversal
def _extract_nodes(node, file_path, language, ...):
    for child in node.children:
        if not child.is_named:
            continue  # Skip punctuation/anonymous
        
        ts_kind = child.type        # e.g., "function_definition"
        category = classify_node(ts_kind)  # → "callable"
        
        # ⚠️ THE FILTER THAT SKIPS CALLS
        if category not in ("type", "callable", "section", "block"):
            self._extract_nodes(child, ...)  # Recurse but don't extract
            continue
        
        # Create CodeNode for structural elements only
        code_node = CodeNode.create_callable(...)
        nodes.append(code_node)
```

### 1.3 What Gets Extracted vs Skipped

| Node Type | ts_kind Example | Category | Extracted? |
|-----------|-----------------|----------|------------|
| Function | `function_definition` | `callable` | ✅ YES |
| Class | `class_definition` | `type` | ✅ YES |
| Method | `function_definition` | `callable` | ✅ YES |
| **Call** | `call` / `call_expression` | `expression` | ❌ **SKIPPED** |
| Assignment | `assignment` | `statement` | ❌ SKIPPED |
| Import | `import_statement` | `statement` | ❌ SKIPPED |

**Key Finding (IA-10)**: Call expressions flow through recursion but **never create CodeNodes**. They're classified as `expression` which is not in the extraction filter.

### 1.4 CodeNode Model (25 Fields)

```python
@dataclass(frozen=True)
class CodeNode:
    # Identity
    node_id: str          # "callable:src/app.py:MyClass.add"
    category: str         # "callable", "type", "file", "section", "block"
    ts_kind: str          # "function_definition" (grammar-specific)
    
    # Location (declaration only)
    start_line: int       # 1-indexed
    end_line: int         # 1-indexed
    start_column: int     # 0-indexed
    end_column: int       # 0-indexed
    
    # Content
    content: str          # Full source text
    signature: str        # First line(s) of declaration
    
    # Hierarchy
    parent_node_id: str | None  # For parent-child edges
```

**Gap Identified (CN-04)**: CodeNode stores **declaration location only**. There is no field for storing multiple call site positions within a function body.

---

## Part 2: What LSP Needs

### 2.1 LSP Position Requirements

```python
# LSP get_definition signature
def get_definition(file_path: str, line: int, column: int) -> list[CodeEdge]

# ⚠️ CRITICAL: line and column must point at a CALL SITE
# Example: For code `result = calculate(x, y)`
#                            ^--- Column 9 (where 'calculate' starts)
#                   ^--- Line 5 (0-indexed)

# ❌ WRONG: Query at function definition line
lsp.get_definition("app.py", 10, 0)  # Line 10: def calculate(x, y):
# Returns: Nothing useful (already at definition)

# ✅ CORRECT: Query at call expression position
lsp.get_definition("app.py", 5, 9)   # Line 5: result = calculate(x, y)
# Returns: EdgeType.CALLS pointing to definition location
```

### 2.2 LSP Position Conventions

| Aspect | Convention |
|--------|------------|
| Line indexing | 0-indexed (line 0 = first line) |
| Column indexing | 0-indexed (column 0 = first character) |
| File format | Relative path from project root |
| Return format | `list[CodeEdge]` with source_line, target_line |

### 2.3 What LSP `get_references` Already Works For

The current implementation correctly uses `get_references`:

```python
# In RelationshipExtractionStage._extract_lsp_relationships
reference_edges = self._lsp_adapter.get_references(
    file_path=file_path,
    line=node.start_line,  # ✅ Works: query at definition
    column=0,              # ✅ Works: start of line
)
# Returns: All locations that CALL this function
```

**Why it works**: `get_references` finds "who calls me" by querying at the **definition position**. The LSP server knows what symbol is defined there and can find all references to it.

### 2.4 Why `get_definition` Failed

The removed code attempted:

```python
# ❌ REMOVED: Naive line-scanning approach
for line_num in range(node.start_line, node.end_line + 1):
    for column in [4, 8, 12, 16, 20, 24, 28, 32]:  # Fixed positions
        edges = lsp.get_definition(file_path, line_num, column)
        # 99%+ return None because column doesn't hit a call
```

**Problems**:
1. Most column positions don't contain call expressions
2. For a function with 50 lines, this generates 50 × 8 = 400 queries per function
3. For 6000+ nodes, this generates 2.4M+ useless LSP queries

---

## Part 3: Tree-Sitter Call Expression Analysis

### 3.1 Call Node Types by Language

| Language | Call Node Type | Example Code | Node Text |
|----------|----------------|--------------|-----------|
| Python | `call` | `foo(x, y)` | `foo(x, y)` |
| TypeScript | `call_expression` | `bar.method()` | `bar.method()` |
| JavaScript | `call_expression` | `fetch(url)` | `fetch(url)` |
| Go | `call_expression` | `fmt.Println(x)` | `fmt.Println(x)` |
| Terraform | `function_call` | `lookup(map, key)` | `lookup(map, key)` |

### 3.2 Tree-Sitter Position Data

Every tree-sitter node provides exact positions:

```python
# Python tree-sitter node
call_node.type          # "call"
call_node.start_point   # (row=5, column=12) - 0-indexed
call_node.end_point     # (row=5, column=25)
call_node.text          # b"calculate(x, y)"
call_node.is_named      # True
```

**Direct Mapping to LSP**: 
- `call_node.start_point[0]` → LSP `line` (both 0-indexed)
- `call_node.start_point[1]` → LSP `column` (both 0-indexed)

### 3.3 Finding Call Expressions in Function Bodies

Tree-sitter query pattern to find all calls within a function:

```python
def extract_calls_from_function(function_node) -> list[tuple[int, int]]:
    """Extract (line, column) positions of all call expressions."""
    calls = []
    
    def visit(node):
        # Python: "call", TS/JS/Go: "call_expression"
        if node.type in ("call", "call_expression", "function_call"):
            calls.append((node.start_point[0], node.start_point[1]))
        
        for child in node.children:
            visit(child)
    
    visit(function_node)
    return calls
```

### 3.4 Tree-Sitter Call Node Structure

```json
{
  "type": "call",
  "text": "super().add(a, b)",
  "start_point": {"row": 53, "column": 24},
  "end_point": {"row": 53, "column": 39},
  "children": [
    {"type": "attribute", "text": "super().add"},
    {"type": "argument_list", "text": "(a, b)"}
  ]
}
```

**Key Fields**:
- `start_point`: Exact position for LSP query
- `children[0]`: The callee (function/method being called)
- `children[1]`: The arguments

---

## Part 4: Solution Design

### 4.1 Two Architectural Options

#### Option A: Enrich CodeNode During ParsingStage

**Approach**: Extract call expressions during initial AST parsing and store positions in CodeNode.

```python
@dataclass(frozen=True)
class CodeNode:
    # ... existing fields ...
    
    # NEW: Call site positions within this node's content
    call_sites: tuple[tuple[int, int], ...] | None = None
    # Format: ((line1, col1), (line2, col2), ...)
```

**Pros**:
- Single parse pass
- Call positions available to all downstream stages
- Immutable, fits frozen dataclass pattern

**Cons**:
- Changes CodeNode model (migration needed)
- Increases memory per node
- May include calls we don't care about

#### Option B: Re-Parse in RelationshipExtractionStage

**Approach**: When processing a callable node, re-parse its content to find calls on-demand.

```python
def _extract_lsp_relationships(self, node: CodeNode, all_nodes: list[CodeNode]):
    # ... existing references code ...
    
    # NEW: Find what this function calls
    if node.category == "callable" and node.content:
        call_positions = self._extract_call_positions(node.content, node.language)
        
        for line, column in call_positions:
            # Adjust line to be relative to file, not node
            file_line = node.start_line + line
            
            edges = self._lsp_adapter.get_definition(
                file_path=file_path,
                line=file_line - 1,  # Convert to 0-indexed
                column=column,
            )
            raw_edges.extend(edges)
```

**Pros**:
- No CodeNode model changes
- Only parses content when LSP is available
- Lazy evaluation (only for callable nodes)

**Cons**:
- Re-parses content that was already parsed
- Tree-sitter parser needed in RelationshipExtractionStage

### 4.2 Recommended Solution: Option B (Re-Parse On-Demand)

**Rationale**:
1. **Minimal change**: No model migrations, no graph schema changes
2. **Isolation**: Call extraction stays in relationship stage where it belongs
3. **Efficiency**: Only parses ~1000-2000 callable nodes, not all 6000+ nodes
4. **Graceful degradation**: Works even if LSP unavailable (just skips)

### 4.3 Implementation Plan

```python
# In RelationshipExtractionStage

def __init__(
    self,
    lsp_adapter: LspAdapter | None = None,
    ast_parser: ASTParser | None = None,  # NEW: For call extraction
    ...
):
    self._ast_parser = ast_parser

def _extract_call_positions(
    self, 
    content: str, 
    language: str
) -> list[tuple[int, int]]:
    """Extract all call expression positions from code content.
    
    Returns:
        List of (line, column) tuples, both 0-indexed.
    """
    parser = get_parser(language)
    tree = parser.parse(content.encode("utf-8"))
    
    calls = []
    CALL_TYPES = {"call", "call_expression", "function_call"}
    
    def visit(node):
        if node.type in CALL_TYPES and node.is_named:
            calls.append((node.start_point[0], node.start_point[1]))
        for child in node.children:
            visit(child)
    
    visit(tree.root_node)
    return calls

def _extract_lsp_relationships(self, node: CodeNode, all_nodes: list[CodeNode]):
    # ... existing get_references code (lines 263-272) ...
    
    # NEW: Get definitions for calls made by this function
    if node.content and self._ast_parser:
        call_positions = self._extract_call_positions(node.content, node.language)
        
        for rel_line, column in call_positions:
            # Convert relative line (within content) to file line
            file_line = node.start_line + rel_line
            
            try:
                definition_edges = self._lsp_adapter.get_definition(
                    file_path=file_path,
                    line=file_line - 1,  # Convert 1-indexed to 0-indexed
                    column=column,
                )
                raw_edges.extend(definition_edges)
            except Exception as e:
                logger.debug("get_definition failed at %s:%d:%d: %s", 
                           file_path, file_line, column, e)
```

### 4.4 Edge Type Mapping

| Query | Direction | EdgeType | Resolution Rule |
|-------|-----------|----------|-----------------|
| `get_references` | Who calls me | `REFERENCES` | `lsp:references` |
| `get_definition` | What do I call | `CALLS` | `lsp:definition` |

---

## Part 5: Prior Learnings from Previous Plans

### PL-01: LSP Graceful Degradation is Non-Negotiable
**Source**: Plan 025 Phase 1  
**Learning**: Scan pipeline must complete even if LSP fails. All LSP operations must be non-fatal.  
**Action**: Wrap all LSP calls in try/except; log debug, return empty list on failure.

### PL-04: Critical — Stdout Isolation During LSP Import
**Source**: Plan 025 Phase 1  
**Learning**: Any stdout output during LSP import corrupts JSON-RPC communication.  
**Action**: Already implemented via stdout suppression wrapper.

### PL-07: LSP CodeEdge Mapping
**Source**: Plan 025 Phase 8  
**Learning**: LSP responses map cleanly to CodeEdge: `get_definition` → `EdgeType.CALLS`, confidence=1.0.  
**Action**: Use existing CodeEdge model; no changes needed.

### PL-09: Confidence Scoring Tiers
**Source**: Plan 022  
**Learning**: LSP edges get confidence=1.0 (definitive); text patterns get 0.3-0.5.  
**Action**: LSP call detection will produce high-confidence edges.

### PL-15: Language-Agnostic Initialization Wait
**Source**: Plan 025 Phase 1  
**Learning**: LSP servers need 2.0s indexing time before cross-file queries work.  
**Action**: Existing wait mechanism in SolidLSP adapter handles this.

---

## Part 6: Critical Discoveries

### 🚨 CD-01: Call Expressions Are Already Parsed But Discarded

**Impact**: Critical  
**Source**: IA-10, CN-04  
**Evidence**: `ast_parser_impl.py:642` — category filter excludes `expression`

Tree-sitter successfully parses call expressions during ParsingStage, but they're discarded by the category filter. We have all the data; we just need to extract it.

### 🚨 CD-02: Position Conversion Is Straightforward

**Impact**: High  
**Source**: TS-04, LS-04

Both tree-sitter and LSP use 0-indexed positions. The only conversion needed:
- Tree-sitter `start_point[0]` (relative to content) → add `node.start_line - 1` for file position

### 🚨 CD-03: Only Callable Nodes Need Call Extraction

**Impact**: High  
**Source**: RE-08, PS-09

The existing filter `node.category in ("callable", "method", "function")` already restricts processing to ~1000-2000 nodes. Call extraction will only run for these.

---

## Part 7: Recommendations

### If Implementing Call Detection

1. **Use Option B (re-parse on-demand)** — minimal model changes
2. **Add `ast_parser` dependency to RelationshipExtractionStage**
3. **Extract call positions only for callable nodes**
4. **Query LSP `get_definition` at each call position**
5. **Upgrade edges to symbol-level using existing `_upgrade_edge_to_symbol_level()`**

### If Testing

1. **Unit test**: Mock AST parser, verify call positions extracted
2. **Integration test**: Real files, verify edges created for cross-file calls
3. **Validation script**: Count edges before/after, verify improvement

### If Extending

1. **Add language-specific call types as discovered** (e.g., Terraform `function_call`)
2. **Consider caching parsed trees** if performance becomes issue
3. **Track call extraction metrics** (`call_extraction_count`, `call_extraction_errors`)

---

## Appendix: File Inventory

### Core Files for Implementation

| File | Purpose | Key Lines |
|------|---------|-----------|
| `src/fs2/core/services/stages/relationship_extraction_stage.py` | Add call extraction | 230-285 |
| `src/fs2/core/adapters/ast_parser_impl.py` | Understand extraction | 560-680 |
| `src/fs2/core/adapters/lsp_adapter_solidlsp.py` | LSP interface | get_definition method |
| `src/fs2/core/models/code_node.py` | CodeNode structure | 96-200 |

### Test Files

| File | Purpose |
|------|---------|
| `tests/integration/test_lsp_integration.py` | Integration tests |
| `tests/unit/stages/test_relationship_extraction_stage.py` | Unit tests |

---

## Next Steps

**This is a research dossier. No implementation has been started.**

To proceed:
1. Review this dossier and confirm approach
2. Create implementation plan (tasks.md)
3. Implement call extraction in RelationshipExtractionStage
4. Add tests
5. Validate with real codebase scan

---

**Research Complete**: 2026-01-23T22:45:00Z  
**Report Location**: `/workspaces/flow_squared/docs/plans/025-lsp-research/research-dossier-ast-lsp-integration.md`
