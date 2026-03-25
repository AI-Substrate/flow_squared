# Reports Feature: Interface Contracts & Data Consumption

## Overview
A "reports" feature in fs2 would consume node data, relationship edges, and aggregation queries from three core interfaces: **GraphStore (ABC)**, **CodeNode** model, and utility services. This document enumerates the interfaces and contracts required.

---

## IC-01: GraphStore ABC – Primary Data Source Interface

**File:** `src/fs2/core/repos/graph_store.py`

**Contract:** Abstract base class defining persistent graph storage. Reports feature reads through this interface exclusively (no direct graph access).

### Public Methods (Reports will use):

```python
def get_node(node_id: str) -> CodeNode | None
def get_all_nodes() -> list[CodeNode]
def get_children(node_id: str) -> list[CodeNode]
def get_parent(node_id: str) -> CodeNode | None
def get_edges(
    node_id: str,
    direction: str = "outgoing",  # "outgoing", "incoming", "both"
    edge_type: str | None = None  # None returns all edges
) -> list[tuple[str, dict[str, Any]]]
def get_all_edges(
    edge_type: str | None = None
) -> list[tuple[str, str, dict[str, Any]]]
def load(path: Path) -> None
def get_metadata() -> dict[str, Any]
```

### Key Contracts for Reports:

- **Node Identity:** Node ID format = `{category}:{file_path}:{qualified_name}` (anonymous nodes use `@line` suffix)
- **Edge Semantics:** Direction is parent → child. `edge_type="references"` marks cross-file relationships
- **Metadata:** Returns dict with keys: `format_version`, `created_at`, `node_count`, `edge_count`
- **Error Handling:** Raises `GraphStoreError` on load failures, returns None/empty list on miss
- **Immutability:** Reports must NOT modify graph via add_node/add_edge (read-only pattern)

---

## IC-02: CodeNode Model – Universal Node Schema

**File:** `src/fs2/core/models/code_node.py`

**Contract:** Frozen dataclass (immutable) representing any structural code element with 23 fields.

### Visualization-Critical Fields:

| Field | Type | Purpose for Reports |
|-------|------|-------------------|
| `node_id` | str | Unique identifier; extract file_path via split(":", 2)[1] |
| `name` | str \| None | Display name (None for anonymous); use qualified_name as fallback |
| `category` | str | Universal type: "file", "callable", "type", "section", "definition", "other" |
| `qualified_name` | str | Hierarchical name within file (e.g., "Calculator.add") |
| `start_line` | int | 1-indexed line (human-readable) for location UI |
| `end_line` | int | 1-indexed end line for span visualization |
| `content` | str | Full source text (embed in detailed reports, truncate for summary) |
| `signature` | str \| None | Declaration first line(s); quick preview without full content |
| `language` | str | Source grammar name (Python, JavaScript, etc.) |
| `smart_content` | str \| None | AI-generated summary (use in smart report mode) |

### Non-Reports Fields (NEVER include in JSON output):

- `embedding`, `smart_content_embedding`: Vectors (data leak risk)
- `content_hash`, `smart_content_hash`: Internal change detection
- `start_byte`, `end_byte`, `start_column`, `end_column`: Tree-sitter internals
- `is_error`, `truncated`, `truncated_at_line`, `content_type`: Implementation details
- `field_name`, `is_named`: Grammar-specific metadata
- `parent_node_id`: Use graph edges instead

### Key Invariants:

- **Language-Agnostic:** Works for Python, JS, Markdown, Terraform, etc. via `classify_node(ts_kind)`
- **Dual Classification:** `ts_kind` (grammar-specific) + `category` (universal)
- **Frozen:** `@dataclass(frozen=True)` — immutable after creation

---

## IC-03: CodeNode Classification – Universal Category Mapping

**File:** `src/fs2/core/models/code_node.py` → `classify_node()` function

**Contract:** Maps tree-sitter node types to universal categories for cross-language filtering.

```python
def classify_node(ts_kind: str) -> str:
    """Returns: "file" | "callable" | "type" | "section" | "statement" | 
                "expression" | "block" | "definition" | "other"
    """
```

### Category Semantics for Reports:

- **"file":** Root containers (module, program, source_file, document)
- **"callable":** Functions, methods, lambdas, procedures
- **"type":** Classes, structs, interfaces, enums, traits
- **"section":** Markdown headings, document sections
- **"statement":** Control flow (if, for, while, etc.)
- **"expression":** Expression nodes
- **"block":** IaC blocks, code blocks, instruction blocks
- **"definition":** Variables, constants, type aliases, declarations
- **"other":** Unrecognized (use `ts_kind` for custom handling)

---

## IC-04: TreeNode – Recursive Report Rendering Model

**File:** `src/fs2/core/models/tree_node.py`

**Contract:** Immutable recursive structure for rendering code trees without algorithmic logic in CLI.

```python
@dataclass(frozen=True)
class TreeNode:
    node: CodeNode                          # The actual code node
    children: tuple[TreeNode, ...] = ()     # Recursive children (tuple for immutability)
    hidden_children_count: int = 0          # Children hidden by depth limit
```

### Contracts for Reports:

- **Immutability:** Frozen dataclass; safe to cache/serialize
- **Recursive:** Reports traverse `.children` recursively to render tree
- **Metadata:** `hidden_children_count > 0` signals truncation for UI (show "...N more")
- **Empty Case:** `children=()` indicates leaf node

---

## IC-05: TreeService – Tree Building & Filtering API

**File:** `src/fs2/core/services/tree_service.py`

**Contract:** Orchestrates graph → tree transformation. Reports use this for hierarchical navigation.

```python
class TreeService:
    def __init__(
        self,
        config: ConfigurationService,        # Registry (extracts GraphConfig internally)
        graph_store: GraphStore,             # ABC interface (NOT implementation)
    ) -> None: ...
    
    def build_tree(
        self,
        pattern: str = ".",                  # Filter pattern (".", glob, substring, node_id, or folder)
        max_depth: int = 0,                  # 0 = unlimited depth
    ) -> list[TreeNode]:
        """Returns filtered tree roots ready for rendering. Handles folder synthesis."""
```

### Pattern Syntax for Reports:

- **"."**: Match all nodes (full tree view)
- **"ClassName"**: Substring match
- **"*.py"**: Glob pattern
- **"file:src/main.py:ClassName.method"**: Exact node_id
- **"src/models/"**: Folder (returns contents)

### Key Guarantees:

- Lazy-loads graph on first call
- Single call returns complete tree (no multi-step traversal needed)
- Thread-safe (safe for report generation in background task)

---

## IC-06: GetNodeService – Individual Node Retrieval

**File:** `src/fs2/core/services/get_node_service.py`

**Contract:** Single-node retrieval with lazy graph loading.

```python
class GetNodeService:
    def __init__(
        self,
        config: ConfigurationService,
        graph_store: GraphStore,
    ) -> None: ...
    
    def get_node(node_id: str) -> CodeNode | None:
        """Retrieve by node_id. Auto-loads graph on first call."""
```

### Usage for Reports:

- Fetch specific node for detail view
- Navigate cross-file references via node_id
- Validate node existence before report generation

---

## IC-07: GraphUtilitiesService – Graph Summary & Analysis

**File:** `src/fs2/core/services/graph_utilities_service.py`

**Contract:** Reusable analytics on persisted graph state (post-scan data, not transient).

```python
class GraphUtilitiesService:
    def __init__(
        self,
        config: ConfigurationService,
        graph_store: GraphStore,
    ) -> None: ...
    
    def get_extension_summary() -> ExtensionSummary:
        """Aggregate file/node counts by extension."""
    
    @staticmethod
    def extract_file_path(node_id: str) -> str:
        """Extract file path from node_id. Raises ValueError on invalid format."""
```

### ExtensionSummary Return Contract:

```python
@dataclass(frozen=True)
class ExtensionSummary:
    files_by_ext: dict[str, int]     # Extension → unique file count
    nodes_by_ext: dict[str, int]     # Extension → total node count
    
    @property
    def total_files(self) -> int:    # Convenience aggregate
    @property
    def total_nodes(self) -> int:    # Convenience aggregate
```

### Example Report Use:

```python
# Scan summary report
service = GraphUtilitiesService(config, graph_store)
summary = service.get_extension_summary()
for ext, count in summary.files_by_ext.items():
    print(f"{ext}: {count} files, {summary.nodes_by_ext.get(ext, 0)} nodes")
```

---

## IC-08: Cross-File Relationships – Reference Edge Semantics

**File:** `src/fs2/core/repos/graph_store.py` (get_edges) + `src/fs2/mcp/server.py` (_code_node_to_dict)

**Contract:** Reports query reference edges between nodes across files using edge_type attribute.

### Reference Edge Query Pattern:

```python
# Get nodes that reference this node
incoming = graph_store.get_edges(
    node_id="callable:src/calc.py:Calc.add",
    direction="incoming",
    edge_type="references"
)
# Returns: list[tuple[str, dict[str, Any]]]
# Example: [("callable:src/main.py:main", {"edge_type": "references"})]

# Get nodes this node references
outgoing = graph_store.get_edges(
    node_id="callable:src/calc.py:Calc.add",
    direction="outgoing",
    edge_type="references"
)
```

### Edge Data Contract:

- **Containment edges** (parent → child): No edge_data kwargs; implicitly hierarchical
- **Reference edges** (cross-file): `edge_type="references"`; may have future attributes (impact, confidence, etc.)
- **Direction Invariant:** Edge direction is source → target (parent → child for containment)

---

## IC-09: ScanSummary – Post-Scan Metadata

**File:** `src/fs2/core/models/scan_summary.py`

**Contract:** Immutable report of pipeline execution results.

```python
@dataclass(frozen=True)
class ScanSummary:
    success: bool                 # True if no errors
    files_scanned: int            # File count from discovery
    nodes_created: int            # CodeNode count from parsing
    errors: list[str]             # Collected error messages
    metrics: dict[str, Any]       # Per-stage metrics (timing, counts)
```

### Reports Integration:

- Use `success` flag to show scan health
- Display `files_scanned` and `nodes_created` in summary section
- List `errors` in "Issues" report section
- Show `metrics` in "Performance" detail section

---

## IC-10: MCP Server JSON Serialization – Report Output Format

**File:** `src/fs2/mcp/server.py` → `_code_node_to_dict()`

**Contract:** Explicit field filtering for secure JSON serialization (prevents embedding leakage).

```python
def _code_node_to_dict(
    node: CodeNode,
    detail: Literal["min", "max"] = "min",
    graph_store: "GraphStore | None" = None,
) -> dict[str, Any]:
    """Convert CodeNode to JSON-safe dict with field filtering.
    
    detail="min" (7 fields): node_id, name, category, content, signature, start_line, end_line
    detail="max" (12 fields): + smart_content, language, parent_node_id, qualified_name, ts_kind
    relationships (optional): + relationships.referenced_by, relationships.references
    
    NEVER included: embedding, smart_content_embedding, content_hash, etc.
    """
```

### JSON Output Examples:

**Minimal Detail (Report Summary):**
```json
{
  "node_id": "callable:src/calc.py:Calculator.add",
  "name": "add",
  "category": "callable",
  "content": "def add(self, a, b):\n    return a + b",
  "signature": "def add(self, a, b):",
  "start_line": 15,
  "end_line": 16
}
```

**Max Detail (Report Full Node):**
```json
{
  "node_id": "callable:src/calc.py:Calculator.add",
  "name": "add",
  "category": "callable",
  "content": "def add(self, a, b):\n    return a + b",
  "signature": "def add(self, a, b):",
  "start_line": 15,
  "end_line": 16,
  "smart_content": "Adds two numbers and returns the result.",
  "language": "python",
  "parent_node_id": "type:src/calc.py:Calculator",
  "qualified_name": "Calculator.add",
  "ts_kind": "function_definition",
  "relationships": {
    "referenced_by": ["callable:src/main.py:main"],
    "references": []
  }
}
```

### Security Contract:

- **Never include vectors** (embedding, smart_content_embedding)
- **Never include hashes** (content_hash, smart_content_hash, embedding_hash)
- **Filter internal fields** (start_byte, end_byte, start_column, end_column, is_named, field_name, is_error)
- **Relationships always query graph** (not cached in node)

---

## Summary Table: What Reports Feature Consumes

| Interface | Method/Model | Purpose | Example |
|-----------|-------------|---------|---------|
| **GraphStore** | `get_all_nodes()` | Fetch all nodes for full report | Generate inventory |
| **GraphStore** | `get_edges(..., edge_type="references")` | Query cross-file relationships | Show "uses/used by" |
| **CodeNode** | Fields: category, name, signature, start_line | Display basic node info | Tree rendering |
| **CodeNode** | smart_content | AI-generated summary | Annotated reports |
| **TreeService** | `build_tree(pattern, max_depth)` | Hierarchical navigation | Navigate via tree UI |
| **GetNodeService** | `get_node(node_id)` | Fetch single node detail | Show node page |
| **GraphUtilitiesService** | `get_extension_summary()` | Language breakdown | Summary stats |
| **ScanSummary** | All fields | Post-scan status | Scan report |
| **TreeNode** | Recursive children structure | Render without logic | Output tree JSON |
| **_code_node_to_dict** | JSON serialization | Safe report output | API responses |

---

## Design Principles for Reports Implementation

1. **Dependency Injection:** Reports service receives `ConfigurationService` + `GraphStore` (ABC), not implementations
2. **Lazy Loading:** Services auto-load graph on first access; reports don't manage lifecycle
3. **Read-Only:** Reports never call `add_node`, `add_edge`, `save`, `clear` (no mutations)
4. **No Caching:** Per R3.5, all graph access through GraphStore on-demand (enable real-time updates)
5. **Security:** Use `_code_node_to_dict` for JSON output (prevents embedding/hash leakage)
6. **Thread-Safe:** Services use lazy loading + RLock; safe for background report generation
7. **Language-Agnostic:** Use `category` (universal) not `ts_kind` (grammar-specific) for filtering
8. **Error Handling:** Catch `GraphNotFoundError`, `GraphStoreError`, `MissingConfigurationError`

