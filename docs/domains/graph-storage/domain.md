# Domain: Graph Storage

**Slug**: graph-storage
**Type**: infrastructure
**Created**: 2026-03-05
**Created By**: extracted from existing codebase
**Status**: active

## Purpose

Owns the persistence and retrieval of code intelligence graphs — the directed graph of CodeNode objects with parent-child edges, metadata, and embedding vectors. This domain provides the data access layer that all query services (tree, search, get-node) and the scan pipeline depend on. Without it, there is no persistent code intelligence data.

## Concepts

| Concept | Entry Point | What It Does |
|---------|-------------|-------------|
| Persist a code graph | `GraphStore.save(path)` | Serialize a graph of CodeNodes + edges to durable storage |
| Load a code graph | `GraphStore.load(path)` | Restore a graph from storage with security validation |
| Query graph nodes | `GraphStore.get_node(id)` | Retrieve individual nodes, children, or parents by ID |
| Manage multiple graphs | `GraphService.get_graph(name)` | Thread-safe access to default + named external graphs with caching |
| List available graphs | `GraphService.list_graphs()` | Discover configured graphs with availability status |

### Persist a code graph

Used by the scan pipeline's StorageStage after all nodes have been parsed and enriched. The stage iterates all CodeNodes, adds them and their edges, then calls save().

```python
from fs2.core.repos import GraphStore
store.add_node(code_node)
store.add_edge(parent_id, child_id)
store.save(Path(".fs2/graph.pickle"))
```

### Load a code graph

Used by GraphService and lazy-loading services. Load validates the pickle via RestrictedUnpickler (whitelisted types only) and checks format version compatibility.

```python
store = NetworkXGraphStore(config)
store.load(Path(".fs2/graph.pickle"))
node = store.get_node("file:src/main.py")
```

### Manage multiple graphs

GraphService provides thread-safe (RLock), cached access to graphs. Staleness detection (mtime + size) triggers reload. Named graphs come from OtherGraphsConfig.

```python
graph_service = GraphService(config)
store = graph_service.get_graph("default")  # or "shared-lib"
graphs = graph_service.list_graphs()  # [GraphInfo(...), ...]
```

## Boundary

### Owns
- Graph persistence format (pickle, metadata, versioning)
- CodeNode and ContentType data models
- Graph CRUD operations (add_node, add_edge, get_node, get_children, get_parent, get_all_nodes)
- Multi-graph resolution, caching, and staleness detection
- RestrictedUnpickler security whitelist
- Graph-related exceptions (GraphStoreError, GraphNotFoundError, UnknownGraphError, GraphFileNotFoundError)
- Pipeline StorageStage (writes scan results to graph)
- PipelineContext graph-related fields

### Does NOT Own
- CLI commands (cli-presentation domain)
- MCP tools (cli-presentation domain)
- Search logic (search domain)
- Scan pipeline orchestration (indexing — not yet a formal domain)
- Embedding generation (embedding — not yet a formal domain)
- Configuration system (configuration domain)

## Contracts (Public Interface)

| Contract | Type | Consumers | Description |
|----------|------|-----------|-------------|
| `GraphStore` (ABC) | Repository Interface | SearchService, TreeService, GetNodeService, GraphUtilitiesService, StorageStage, GraphService | 10 abstract methods for graph CRUD + persistence |
| `GraphService` | Service | CLI (tree, search, get-node, list-graphs), MCP (all tools) | Multi-graph management with caching |
| `CodeNode` | Frozen Dataclass | All services, matchers, CLI, MCP | 20+ field universal code element model |
| `ContentType` | Enum | EmbeddingService (chunking strategy), ASTParser | CODE vs CONTENT classification |
| `GraphConfig` | Pydantic Model | GraphService, scan pipeline | `graph_path` default |
| `OtherGraphsConfig` | Pydantic Model | GraphService | External graph references |

## Composition (Internal)

| Component | Role | Depends On |
|-----------|------|------------|
| `GraphStore` (ABC) | Repository contract | CodeNode, ConfigurationService |
| `NetworkXGraphStore` | Production adapter | networkx, pickle, RestrictedUnpickler, ScanConfig |
| `FakeGraphStore` | Test double | GraphStore ABC |
| `GraphService` | Multi-graph service | GraphStore, GraphConfig, OtherGraphsConfig, ConfigurationService |
| `FakeGraphService` | Test double | GraphService pattern |
| `GraphUtilitiesService` | Analysis helper | GraphStore, GraphConfig, ConfigurationService |
| `CodeNode` | Data model | ContentType |
| `StorageStage` | Pipeline stage | GraphStore, PipelineContext |
| `PipelineContext` | Mutable state carrier | GraphStore (optional field) |

## Source Location

Primary: `src/fs2/core/repos/` + `src/fs2/core/models/` + `src/fs2/core/services/graph_*`

| File | Role | Notes |
|------|------|-------|
| `src/fs2/core/repos/graph_store.py` | ABC | 10 abstract methods |
| `src/fs2/core/repos/graph_store_impl.py` | Production adapter | NetworkX + pickle |
| `src/fs2/core/repos/graph_store_fake.py` | Test double | In-memory dict |
| `src/fs2/core/repos/__init__.py` | Module exports | |
| `src/fs2/core/models/code_node.py` | Core model | 20+ fields, frozen |
| `src/fs2/core/models/content_type.py` | Enum | CODE / CONTENT |
| `src/fs2/core/services/graph_service.py` | Multi-graph service | RLock caching |
| `src/fs2/core/services/graph_service_fake.py` | Test double | |
| `src/fs2/core/services/graph_utilities_service.py` | Analysis service | Extension summaries |
| `src/fs2/core/services/stages/storage_stage.py` | Pipeline stage | Writes to GraphStore |
| `src/fs2/core/services/pipeline_context.py` | Pipeline state | graph_store field |
| `src/fs2/config/objects.py` | Config models | GraphConfig, OtherGraph, OtherGraphsConfig, ScanConfig |
| `src/fs2/core/adapters/exceptions.py` | Exceptions | GraphStoreError, GraphNotFoundError |
| `tests/unit/repos/test_graph_store.py` | Unit tests | ABC contract |
| `tests/unit/repos/test_graph_store_impl.py` | Unit tests | NetworkXGraphStore |
| `tests/unit/repos/test_graph_store_fake.py` | Unit tests | FakeGraphStore |
| `tests/unit/services/test_graph_service.py` | Unit tests | Multi-graph, caching |

## Dependencies

### This Domain Depends On
- **configuration** — ConfigurationService for typed config access (GraphConfig, ScanConfig, OtherGraphsConfig)
- **networkx** (external) — DiGraph in-memory structure
- **pickle** (stdlib) — Serialization format

### Domains That Depend On This
- **search** — SearchService consumes GraphStore for node retrieval and parent traversal
- **cli-presentation** (informal) — CLI commands and MCP tools consume GraphService
- **indexing** (informal) — ScanPipeline creates and writes to GraphStore

## History

| Plan | What Changed | Date |
|------|-------------|------|
| 003-fs2-base | Initial GraphStore ABC + NetworkXGraphStore | 2024 |
| 023-multi-graphs | GraphService, OtherGraphsConfig, named graph resolution | 2025 |
| *(extracted)* | Domain extracted from existing codebase | 2026-03-05 |
