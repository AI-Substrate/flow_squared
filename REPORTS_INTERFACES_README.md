# Reports Feature Interface Contracts Documentation

## Overview

This documentation package specifies the complete interface contracts and data models that a "reports" feature would consume from fs2's codebase. It covers 10 key interfaces (IC-01 through IC-10) with method signatures, return types, field definitions, and usage patterns.

## Documents in This Package

### 1. **REPORTS_IC_SUMMARY.txt** (341 lines)
**Format:** Plain text with ASCII tables and structured sections
**Audience:** Quick reference, architectural planning, implementation checklist

**Contains:**
- **IC-01 through IC-10:** Concise reference cards with:
  - File locations
  - Critical methods/fields
  - Function signatures
  - Edge semantics and contracts
  - Usage examples and JSON samples
- Design principles for reports implementation (8 core principles)
- Consumption matrix showing which interfaces to use for which reports
- Error handling guidance

**Best for:** Starting implementation, understanding interfaces at a glance, integration planning

### 2. **REPORTS_INTERFACE_CONTRACTS.md** (397 lines)
**Format:** Markdown with nested headings, code blocks, tables
**Audience:** Detailed reference, specification, developer documentation

**Contains:**
- **IC-01 through IC-10:** Full specifications with:
  - Method signatures with type annotations
  - Return type contracts
  - Field descriptions and semantics
  - Security constraints
  - Design principles and invariants
  - Complete JSON serialization examples
- Detailed tables mapping interfaces to use cases
- Summary table with cross-reference matrix
- Security and error handling contracts

**Best for:** In-depth development, specification review, architectural review, API design

---

## The 10 Interface Contracts (Quick Summary)

| ID | Interface | File | Purpose |
|----|-----------|------|---------|
| **IC-01** | GraphStore ABC | `core/repos/graph_store.py` | Primary read-only data source for all graph queries |
| **IC-02** | CodeNode Model | `core/models/code_node.py` | Universal node schema with 23 fields (frozen dataclass) |
| **IC-03** | Classification | `core/models/code_node.py` | Language-agnostic category mapping (file/callable/type/etc.) |
| **IC-04** | TreeNode | `core/models/tree_node.py` | Recursive immutable tree structure for rendering |
| **IC-05** | TreeService | `core/services/tree_service.py` | Single-call tree building with pattern filtering |
| **IC-06** | GetNodeService | `core/services/get_node_service.py` | Individual node retrieval with lazy loading |
| **IC-07** | GraphUtilitiesService | `core/services/graph_utilities_service.py` | Graph analysis: extension summary, file path extraction |
| **IC-08** | Reference Edges | `core/repos/graph_store.py` | Cross-file relationship semantics (get_edges with edge_type) |
| **IC-09** | ScanSummary | `core/models/scan_summary.py` | Post-scan metadata (files, nodes, errors, metrics) |
| **IC-10** | JSON Serialization | `mcp/server.py` | Safe field filtering for API output (min/max detail levels) |

---

## Key Data Flows for Reports Implementation

### 1. **Full Inventory Report**
```
GraphStore.get_all_nodes()
  ↓ per node
  → _code_node_to_dict(..., detail="min")
  → JSON array for report export
```

### 2. **Hierarchical Tree Report**
```
TreeService.build_tree(pattern=".", max_depth=2)
  ↓ returns list[TreeNode]
  → Recursive traversal of .children
  → _code_node_to_dict(..., detail="max", graph_store)
  → JSON tree with relationships
```

### 3. **Cross-File Dependencies Report**
```
GraphStore.get_edges(node_id, direction="outgoing", edge_type="references")
  ↓ returns list[connected_node_ids]
  → Fetch each via GetNodeService.get_node()
  → Aggregate into "references" and "referenced_by" lists
  → _code_node_to_dict includes relationships field
```

### 4. **Scan Summary Report**
```
ScanSummary from ScanPipeline.run()
  ↓ fields: success, files_scanned, nodes_created, errors, metrics
  → GraphUtilitiesService.get_extension_summary()
  ↓ returns ExtensionSummary with files_by_ext, nodes_by_ext
  → Combine into multi-section HTML/JSON report
```

---

## Critical Contracts for Reports

### ✓ Do's
- ✓ Receive `ConfigurationService` (registry) + `GraphStore` (ABC) via dependency injection
- ✓ Use lazy loading (graph loads on first service access)
- ✓ Query through `GraphStore` exclusively (never direct graph access)
- ✓ Use `_code_node_to_dict()` for JSON serialization
- ✓ Filter by `category` (universal) not `ts_kind` (language-specific)
- ✓ Call `get_edges(..., edge_type="references")` for dependency queries
- ✓ Traverse `TreeNode.children` recursively without tree logic
- ✓ Handle `GraphNotFoundError`, `GraphStoreError` gracefully

### ✗ Don'ts
- ✗ Never call `add_node`, `add_edge`, `save`, `clear` on GraphStore (read-only)
- ✗ Never cache graph data (per R3.5; query on-demand)
- ✗ Never include in JSON: embeddings, content_hash, internal metadata
- ✗ Never depend on implementations (NetworkXGraphStore, etc.)
- ✗ Never modify CodeNode fields (frozen dataclass)
- ✗ Never call tree-building logic in CLI (use TreeService instead)

---

## Security & Data Privacy Constraints

### Embedding Leakage Prevention
The `_code_node_to_dict()` function explicitly filters fields to prevent exposing:
- `embedding`: Raw vector embeddings (1024-dimensional)
- `smart_content_embedding`: AI summary embeddings
- `embedding_hash`: Staleness detection hash
- `content_hash`, `smart_content_hash`: Internal change detection

**Why:** External consumers (reports, APIs, exports) never need these fields. Exposing embeddings is a data privacy and IP risk.

### JSON Output Levels
- **"min" detail (7 fields):** Compact summary (node_id, name, category, content, signature, start_line, end_line)
- **"max" detail (12 fields):** Full metadata (adds: smart_content, language, parent_node_id, qualified_name, ts_kind)
- **relationships (optional):** Cross-file references (referenced_by, references) — only when graph_store provided

---

## Node ID Semantics

### Format
```
{category}:{file_path}:{qualified_name}
```

### Examples
```
file:src/main.py                          # File node
callable:src/calc.py:Calculator           # Type node (class)
callable:src/calc.py:Calculator.add       # Callable node (method)
section:docs/README.md:Overview            # Document section
```

### Extraction
```python
# Extract file_path from node_id
parts = node_id.split(":", 2)  # Split into max 3 parts
file_path = parts[1]           # Result: "src/calc.py"
```

---

## Graph Edge Semantics

### Containment Edges (Hierarchy)
```python
# Parent → Child direction (implicit)
graph_store.add_edge(parent_id="type:src/calc.py:Calculator",
                     child_id="callable:src/calc.py:Calculator.add")
# No edge_type kwarg (defaults to containment/hierarchy)
```

### Reference Edges (Cross-File)
```python
# Query cross-file dependencies
refs_outgoing = graph_store.get_edges(
    "callable:src/calc.py:Calculator.add",
    direction="outgoing",
    edge_type="references"  # IMPORTANT: filter by edge_type
)
# Returns: [("callable:src/util.py:format_number", {"edge_type": "references"}), ...]
```

---

## Example: Implementing a Simple "Dependencies Report"

```python
from fs2.config.service import ConfigurationService
from fs2.core.repos.graph_store import GraphStore
from fs2.mcp.server import _code_node_to_dict

def generate_dependencies_report(config: ConfigurationService, 
                                graph_store: GraphStore,
                                node_id: str) -> dict:
    """Generate "what does this node reference" report."""
    
    # Load graph (lazy)
    graph_store.load(config.require(GraphConfig).graph_path)
    
    # Fetch target node
    node = graph_store.get_node(node_id)
    if not node:
        return {"error": f"Node not found: {node_id}"}
    
    # Query cross-file references
    outgoing_edges = graph_store.get_edges(
        node_id, 
        direction="outgoing", 
        edge_type="references"
    )
    
    # Build report
    references = []
    for target_node_id, edge_data in outgoing_edges:
        target = graph_store.get_node(target_node_id)
        if target:
            references.append(_code_node_to_dict(target, detail="min"))
    
    return {
        "source": _code_node_to_dict(node, detail="max", graph_store=graph_store),
        "references": references,
        "count": len(references)
    }
```

---

## Error Handling

| Exception | When Raised | Handling |
|-----------|-----------|----------|
| `GraphNotFoundError` | Graph file doesn't exist | Suggest `fs2 scan` |
| `GraphStoreError` | Graph file corrupted/unreadable | Show in error section |
| `MissingConfigurationError` | Config not in registry | Check initialization |
| `UnknownGraphError` | Named graph not configured | List available graphs |

---

## References & Related Documentation

- **Graph Store Implementation:** `src/fs2/core/repos/graph_store_impl.py` (NetworkXGraphStore)
- **Cross-File Relationships:** `src/fs2/core/services/stages/cross_file_rels_stage.py`
- **Scan Pipeline:** `src/fs2/core/services/scan_pipeline.py`
- **Configuration:** `src/fs2/config/objects.py`, `src/fs2/config/service.py`
- **Rules & Constraints:** `rules.md` (R3.5: No graph data caching)

---

## Document Version
- **Created:** March 2024
- **Scope:** fs2 031-cross-file-rels-take-2
- **Interface Contracts:** IC-01 through IC-10 (10 specifications)
- **Total Coverage:** 738 lines across 2 documents

## Quick Start for Developers

1. **Start with:** `REPORTS_IC_SUMMARY.txt` — get the big picture (10-15 min read)
2. **Deep dive into:** `REPORTS_INTERFACE_CONTRACTS.md` — specification details (30-45 min read)
3. **Code review:** Read actual files in order:
   - `src/fs2/core/repos/graph_store.py` (ABC definition)
   - `src/fs2/core/models/code_node.py` (Data model + classification)
   - `src/fs2/core/models/tree_node.py` (Tree structure)
   - `src/fs2/core/services/tree_service.py` (Tree building)
   - `src/fs2/core/services/graph_utilities_service.py` (Analysis utilities)
4. **Implement:** Create reports service with DI, use interfaces, query via services

