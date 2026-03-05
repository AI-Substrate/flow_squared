# Research Report: Server Mode for fs2

**Generated**: 2026-03-05T03:05:00Z
**Research Query**: "Consider options for adding a server mode to fs2. Needs to scale to hundreds of sites, database for smart content/vectors/graphs, management dashboard, full CLI compatibility via --fs2-remote endpoint."
**Mode**: Pre-Plan (branch-detected: 028-server-mode)
**Location**: docs/plans/028-server-mode/research-dossier.md
**FlowSpace**: Available ✅
**Findings**: 71 total (IA:10, DC:10, PS:10, QT:10, IC:10, DE:10, PL:15, DB:8) — deduplicated below

## Executive Summary

### What It Does (Current State)
fs2 is a local-first code intelligence tool that scans repositories, builds AST-based graph structures with AI-generated summaries and vector embeddings, then serves queries (tree, search, get_node) via CLI and MCP STDIO protocol. All data persists as NetworkX pickle files in `.fs2/graph.pickle`.

### Business Purpose (Server Mode)
Transform fs2 from a single-machine tool into a **multi-tenant server** capable of hosting hundreds of indexed sites, enabling teams to upload pre-scanned graphs and query them remotely via the same CLI/MCP interface using `--fs2-remote <endpoint>`.

### Key Insights
1. **Architecture is ready**: Clean Architecture with ABC interfaces means server mode requires new adapter _implementations_ (RemoteGraphStore, RemoteSearchService), not architectural changes.
2. **Pickle won't scale**: Current pickle format stores everything (graph structure + content + embeddings) in a single binary blob — no partial loading, no concurrent writes, no indexing.
3. **Scanning must stay local**: Source code never leaves the client machine (security/IP concerns). Server receives pre-scanned graphs via upload.

### Quick Stats
- **Components**: ~60 source files, ~40 classes, ~200 functions
- **Dependencies**: NetworkX, Pydantic, Typer, Rich, FastMCP, tree-sitter, OpenAI/Azure SDKs
- **Test Coverage**: ~80% overall; comprehensive fakes for all adapters
- **Complexity**: High — clean but deep (7-layer scan pipeline, 4-mode search, multi-graph caching)
- **Prior Learnings**: 15 relevant discoveries from plans 003-023
- **Domains**: 8 natural domains identified (no formal domain registry)

---

## How It Currently Works

### Entry Points

| Entry Point | Type | Location | Purpose |
|------------|------|----------|---------|
| `fs2 scan` | CLI Command | `cli/scan.py` | Build/update graph from source files |
| `fs2 tree` | CLI Command | `cli/tree.py` | Hierarchical code exploration |
| `fs2 search` | CLI Command | `cli/search.py` | Text/regex/semantic code search |
| `fs2 get-node` | CLI Command | `cli/get_node.py` | Retrieve single code node |
| `fs2 mcp` | MCP Server | `mcp/server.py` | AI agent interface (STDIO JSON-RPC) |
| `fs2 watch` | CLI Command | `cli/watch.py` | File watcher for auto-rescan |

### Core Execution Flow

1. **Scan Pipeline** (`scan_pipeline.py`):
   - DiscoveryStage → finds files (respects .gitignore)
   - ParsingStage → tree-sitter AST → CodeNode objects
   - SmartContentStage → LLM-generated descriptions (hash-based skip)
   - EmbeddingStage → vector generation (content-type aware chunking)
   - StorageStage → `graph_store.save()` → `.fs2/graph.pickle`

2. **Query Path** (tree/search/get_node):
   - CLI resolves graph via `resolve_graph_from_context()`
   - GraphService loads graph (lazy + cached with staleness detection)
   - Service executes query against in-memory NetworkX DiGraph
   - Results formatted and returned

### Data Flow
```
Source Files → FileScanner → ASTParser → CodeNode[]
    → SmartContentService (LLM) → CodeNode[].smart_content
    → EmbeddingService (OpenAI/Azure) → CodeNode[].embedding
    → NetworkXGraphStore.save() → .fs2/graph.pickle

.fs2/graph.pickle → NetworkXGraphStore.load() → nx.DiGraph
    → TreeService.build_tree() / SearchService.search() / GetNodeService
    → CLI output / MCP JSON-RPC response
```

### Current Storage Format
```python
# graph.pickle contains:
(metadata_dict, networkx.DiGraph)

# metadata_dict:
{
    "format_version": "1.0",
    "created_at": "ISO-8601",
    "node_count": int,
    "edge_count": int,
    "embedding_model": str,  # optional
    "smart_content_model": str,  # optional
}

# Each node in DiGraph contains a CodeNode with 17+ fields:
# - node_id, category, ts_kind, name, qualified_name
# - content, content_hash, signature, language
# - start_line, end_line, start_column, end_column, start_byte, end_byte
# - parent_node_id, is_named, field_name
# - embedding: tuple[tuple[float, ...], ...] | None  (chunk-level, 1024-dim)
# - smart_content: str | None
# - smart_content_embedding: tuple[tuple[float, ...], ...] | None
# - embedding_hash, embedding_chunk_offsets, content_type, truncated
```

---

## Architecture & Design

### Component Map

```
┌─────────────────────────────────────────────────────┐
│  Presentation Layer (CLI + MCP)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Typer CLI │  │ FastMCP  │  │ Future: HTTP API │  │
│  └─────┬────┘  └─────┬────┘  └────────┬─────────┘  │
│        │              │                │             │
├────────┼──────────────┼────────────────┼─────────────┤
│  Service Layer (Business Logic)                      │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐        │
│  │TreeService│  │SearchSvc │  │ ScanPipeline│        │
│  └─────┬────┘  └─────┬────┘  └──────┬─────┘        │
│        │              │              │               │
├────────┼──────────────┼──────────────┼───────────────┤
│  Adapter Layer (External Wrappers)                   │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐        │
│  │LLMAdapter│  │EmbedAdapt│  │FileScanner │        │
│  └──────────┘  └──────────┘  └────────────┘        │
│                                                      │
├──────────────────────────────────────────────────────┤
│  Repository Layer (Data Access)                      │
│  ┌──────────────────────────────────────────┐       │
│  │ GraphStore ABC → NetworkXGraphStore      │       │
│  │                → FakeGraphStore (tests)  │       │
│  │                → [RemoteGraphStore] NEW  │       │
│  └──────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────┘
```

### Key Interfaces That Need Remote Implementations

| Interface | Current Impl | Remote Impl Needed | Strategy |
|-----------|-------------|-------------------|----------|
| **GraphStore** | NetworkXGraphStore (pickle) | RemoteGraphStore (HTTP) | YES — core data access |
| **EmbeddingAdapter** | Azure/OpenAI | Server-side proxy | MAYBE — depends on architecture |
| **SearchService** | Local matchers | Remote semantic search | PARTIAL — semantic only |
| **GraphService** | File-based caching | Remote graph catalog | YES — multi-tenant |
| **ConfigurationService** | Local YAML/env | Split client/server | YES — credential separation |

### Design Patterns Available for Reuse

1. **ABC + Injection**: All services receive interfaces, not implementations → easy to swap local/remote
2. **Adapter Pattern**: External SDKs wrapped in ABCs → add HTTP client adapter
3. **Repository Pattern**: GraphStore abstracts persistence → add database backend
4. **Error Translation**: MCP's `translate_error()` → reuse for HTTP error responses
5. **Fake Pattern**: Every adapter has test double → create FakeRemoteGraphStore
6. **Configuration Registry**: Pydantic typed configs → add ServerConfig, RemoteConfig
7. **Lazy Singleton + RLock**: Thread-safe graph caching → reuse for concurrent server requests
8. **Async-First**: LLM/Embedding adapters are async → natural fit for async HTTP framework

---

## Dependencies & Integration

### What Would Change for Server Mode

#### Server-Side New Dependencies
| Library | Purpose | Why |
|---------|---------|-----|
| **FastAPI** or similar | HTTP API framework | Async, Pydantic-native, OpenAPI docs |
| **Database** (see below) | Graph + vector + content storage | Replace pickle for multi-tenant scale |
| **Redis** (optional) | Distributed caching + pub/sub | Graph staleness, session management |
| **Auth library** | API key / JWT | Multi-tenant access control |

#### Client-Side Changes
| Change | Purpose |
|--------|---------|
| `--fs2-remote <url>` flag | Route queries to remote server |
| `RemoteGraphStore` adapter | HTTP client implementing GraphStore ABC |
| Upload command (`fs2 push`) | Send local graph.pickle to server |
| Graph listing (`fs2 remote list`) | Browse available remote graphs |

### External Dependencies (Current)
| Library | Version | Server Mode Impact |
|---------|---------|-------------------|
| networkx | ≥3.0 | Server-side: replace with DB; client-side: keep for scan |
| pydantic | ≥2.0 | Shared: API schemas + config validation |
| typer | ≥0.9 | Client-only: CLI framework |
| rich | ≥13.0 | Client-only: terminal formatting |
| fastmcp | ≥0.4 | Client-only (or shared if MCP→HTTP bridge) |
| tree-sitter | ≥0.20 | Client-only: AST parsing stays local |
| openai | ≥1.0 | Server-side: embedding + LLM API calls |
| tiktoken | ≥0.5 | Shared: token counting for chunking |

---

## Quality & Testing

### Current State
- **80% test coverage** overall; graph store at 100%
- **Comprehensive fakes**: FakeGraphStore, FakeLLMAdapter, FakeEmbeddingAdapter, FakeConfigurationService
- **3-tier isolation**: Singleton reset, logging handler cleanup, env var clearing
- **MCP protocol tests**: Zero-stdout enforcement, STDIO transport E2E
- **No network tests**: Minimal socket/HTTP testing infrastructure
- **No performance benchmarks**: Slow tests exist but no latency/throughput metrics

### Testing Strategy for Server Mode
- Reuse existing fakes for unit tests
- Add HTTP client/server integration tests
- Add concurrent request tests (thread safety)
- Add graph upload/download round-trip tests
- Performance benchmarks for search latency at scale

---

## Prior Learnings (From Previous Implementations)

### 📚 PL-01: Multi-Graph Caching with RLock (Plan 023)
**Action**: Reuse GraphService's thread-safe caching pattern for concurrent HTTP requests.

### 📚 PL-02: STDIO stderr-Only Logging (Plan 011)
**Action**: Server mode must also enforce clean stdout/stderr separation for JSON API responses.

### 📚 PL-03: Frozen CodeNode + dataclasses.replace() (Plans 003/008/009)
**Action**: Immutability prevents race conditions in concurrent request handlers. Never mutate.

### 📚 PL-04: Async Queue + Worker Pool (Plan 008)
**Action**: Port SmartContentService's asyncio patterns for concurrent server request handling.

### 📚 PL-05: Exception Translation at Boundaries (Plans 003/011)
**Action**: Build HTTP error middleware following MCP's `translate_error()` pattern.

### 📚 PL-08: Lazy Service Initialization (Plans 011/023)
**Action**: Server startup should defer graph loading until first request (critical for containerized deploys).

### 📚 PL-11: Retry with Exponential Backoff (Plans 007/009)
**Action**: Server embedding/LLM calls need retry middleware (3 attempts, 2-60s delays).

### 📚 PL-13: Reserved "default" Graph Name (Plan 023)
**Action**: Server API should reserve "default" for backward-compatible single-graph access.

---

## Domain Context

### Natural Domain Boundaries Identified

| Domain | Core Files | Boundary Quality | Server Impact |
|--------|-----------|-----------------|---------------|
| **Graph Storage** | `repos/graph_store*.py` | ✅ Well-isolated (ABC) | New RemoteGraphStore impl |
| **Search** | `services/search/*.py` | ⚠️ Coupled to GraphStore | Semantic search → server |
| **Indexing** | `services/scan_pipeline.py`, `stages/*.py` | ✅ Well-isolated | LOCAL ONLY (never remote) |
| **Embedding** | `adapters/embedding_adapter*.py`, `services/embedding/` | ✅ ABC pattern | Optionally server-side |
| **Smart Content** | `services/smart_content/*.py`, `adapters/llm_adapter*.py` | ✅ Composable | Server-side LLM execution |
| **Configuration** | `config/*.py` | ✅ Registry pattern | Split client/server configs |
| **CLI/Presentation** | `cli/*.py`, `mcp/*.py` | ✅ Clean separation | New remote flags + HTTP transport |
| **Management** | N/A (new) | 🆕 Does not exist | Dashboard, upload, tenant mgmt |

### Key Architectural Principle
> **Scanning stays local. Everything else can be remote.**
> Source code never leaves the client machine. The server receives pre-built graph artifacts.

---

## Critical Discoveries

### 🚨 Critical Finding 01: Pickle Cannot Scale to Hundreds of Sites
**Impact**: Critical
**What**: Current storage is a single pickle file per site. Loading requires deserializing the entire graph into memory. With 100s of sites (potentially 100K+ nodes each), this means:
- ~50-500MB per graph file
- Full RAM load per query
- No partial loading / lazy evaluation
- No concurrent write access
- No indexing for fast lookups
**Required Action**: Replace pickle with a database that supports indexed queries, partial loading, and concurrent access.

### 🚨 Critical Finding 02: Semantic Search Requires Full Graph in Memory
**Impact**: Critical
**What**: SemanticMatcher iterates ALL nodes' embedding chunks to compute cosine similarity. No vector index exists — it's brute-force linear scan.
**Required Action**: Vector database with ANN (Approximate Nearest Neighbor) indexing is essential for server mode. Current O(N×C) per query (N nodes × C chunks) won't scale.

### 🚨 Critical Finding 03: No Authentication/Authorization System Exists
**Impact**: Critical
**What**: No concept of users, tenants, API keys, or access control anywhere in the codebase.
**Required Action**: Multi-tenant server needs auth from day one. API key per tenant minimum.

### 🚨 Critical Finding 04: Multi-Graph Support Provides Foundation
**Impact**: High (positive)
**What**: Plan 023 already established GraphService with named graph resolution, caching, and staleness detection. This directly maps to a multi-tenant catalog.
**Required Action**: Extend GraphService to support remote graph catalog with server-side metadata.

### 🚨 Critical Finding 05: Clean Architecture Makes Server Mode Feasible
**Impact**: High (positive)
**What**: Every critical service uses ABC interfaces with dependency injection. Adding remote implementations requires zero changes to business logic.
**Required Action**: Implement RemoteGraphStore, configure via RemoteConfig in Pydantic settings.

---

## External Research Opportunities

### Research Opportunity 1: Database Selection for Combined Graph + Vector + Content Storage

**Why Needed**: fs2 stores three types of data that are currently co-located in pickle: (1) graph structure with parent-child edges, (2) vector embeddings for semantic search, (3) full source content + AI summaries. The server needs a database that can handle all three efficiently at scale (100s of sites, millions of nodes).

**Impact on Plan**: This is the #1 architectural decision — everything else depends on database choice.
**Source Findings**: IA-01, IA-06, IA-10, DC-04, IC-01

**Ready-to-use prompt:**
```
/deepresearch "Database selection for a multi-tenant code intelligence server.

CONTEXT:
- Currently stores code graph (NetworkX DiGraph with parent-child edges), vector embeddings (1024-dim, chunk-level), and full source content + AI summaries in a single pickle file per project
- Need to scale to 100s of projects (sites), each with 10K-200K nodes
- Each node has: node_id (string), 17+ fields including full source content (up to 500KB), embedding vectors (tuple of 1024-dim float tuples), AI summary text
- Queries: hierarchical tree traversal (parent/children), semantic vector search (cosine similarity with ANN), text/regex search across content, metadata filtering
- Multi-tenant: each tenant owns multiple projects, needs isolation
- Must support: upload (batch import), incremental update, concurrent reads, occasional writes

RESEARCH QUESTIONS:
1. PostgreSQL + pgvector vs dedicated vector DB (Milvus/Qdrant/Weaviate) + relational DB — which approach better serves combined graph + vector + content queries?
2. Can a single database handle all three data types, or is a polyglot approach (graph DB + vector DB + document store) better?
3. What are the performance characteristics of pgvector at 10M+ vectors with 1024 dimensions?
4. How does SQLite (local) + PostgreSQL (server) dual-mode work for tools that need both local and remote operation?
5. What about embedded databases like DuckDB or LanceDB for the vector component?
6. Multi-tenant isolation strategies: schema-per-tenant vs row-level security vs separate databases?
7. What's the migration path from pickle files to the chosen database?

CONSTRAINTS:
- Python ecosystem (asyncpg, sqlalchemy, etc.)
- Self-hostable (no vendor lock-in required, but managed options appreciated)
- Must support both self-hosted and cloud deployment
- Budget-conscious: prefer open-source with optional managed tiers"
```

### Research Opportunity 2: Management Dashboard Architecture for Multi-Tenant Code Intelligence

**Why Needed**: The server needs a management interface for uploading/removing sites, monitoring indexing status, managing API keys, and viewing usage metrics. No admin UI exists in the current codebase.

**Impact on Plan**: Determines frontend technology, admin API design, and operational patterns.
**Source Findings**: DE-10, DB-08

**Ready-to-use prompt:**
```
/deepresearch "Management dashboard architecture for a Python-based multi-tenant API server.

CONTEXT:
- Python backend (FastAPI likely) serving code intelligence queries
- Need admin dashboard for: upload/manage indexed sites, API key management, usage monitoring, re-indexing triggers
- Tenants manage their own sites (CRUD) via dashboard
- Backend already uses Pydantic models extensively

RESEARCH QUESTIONS:
1. Best approach for admin dashboard with FastAPI backend: embedded (Jinja2/HTMX), separate SPA (React/Vue), or admin framework (Django Admin standalone, Starlette Admin)?
2. What are modern lightweight admin panel options for Python APIs (2024-2025)?
3. How to implement file upload (graph pickle files, 50-500MB) with progress tracking?
4. Real-time indexing status: WebSocket vs SSE vs polling?
5. API key management patterns (generation, rotation, scoping per tenant/site)
6. Usage metering and billing integration approaches"
```

### Research Opportunity 3: Remote CLI Protocol Design (--fs2-remote)

**Why Needed**: The CLI needs to transparently switch between local and remote graph access. This requires a well-designed API contract that maps current GraphStore/SearchService/TreeService operations to HTTP endpoints.

**Impact on Plan**: Determines API design, client SDK, and backward compatibility story.
**Source Findings**: IC-01 through IC-07, PS-01, DB-07

**Ready-to-use prompt:**
```
/deepresearch "API design for a code intelligence tool that needs both local and remote operation modes.

CONTEXT:
- Python CLI tool (Typer) that currently operates on local files
- Need to add --remote <url> flag that routes all queries to a server instead
- Current operations: tree(pattern, max_depth) → hierarchical view, search(pattern, mode, limit) → results with scores, get_node(node_id) → full source code, list_graphs() → available repositories
- MCP protocol (JSON-RPC over STDIO) is also a consumer — needs to work with remote graphs
- Server hosts 100s of repositories, each with their own graph

RESEARCH QUESTIONS:
1. REST vs GraphQL vs gRPC for code intelligence queries? (tree traversal, filtered search, node retrieval)
2. How to handle large response payloads (get_node can return 500KB of source code)?
3. Pagination strategies for search results and tree expansion
4. How to implement transparent local/remote switching in Python CLI (adapter pattern, config-driven)?
5. Authentication flow for CLI tools (API key in config, oauth device flow, etc.)
6. Caching strategy for client-side: which responses to cache, TTL, invalidation?
7. Streaming vs batch for large tree responses?"
```

---

## Recommendations

### If Modifying This System (Server Mode)
1. **Start with database selection** — this is the #1 decision that gates everything else
2. **Implement RemoteGraphStore first** — the ABC pattern makes this surgical
3. **Keep scanning local** — source code never leaves the client machine
4. **Use push model** — client scans → `fs2 push` uploads graph to server
5. **Add `--fs2-remote` flag** to CLI — transparent local/remote switching
6. **Multi-tenant from day one** — API keys, tenant isolation, graph namespacing

### Architecture Suggestion

```
┌─────────────┐         ┌──────────────────────────────┐
│ Client      │         │ Server                        │
│             │  HTTP   │                               │
│ fs2 scan    │────────>│ /api/graphs/{tenant}/{name}   │
│ fs2 push    │  upload │   → Database (graph+vectors)  │
│             │         │                               │
│ fs2 tree    │────────>│ /api/tree                     │
│ fs2 search  │  query  │ /api/search                   │
│ fs2 get-node│         │ /api/node/{id}                │
│             │         │                               │
│ fs2 mcp     │────────>│ Same API (MCP → HTTP bridge)  │
│ (--remote)  │         │                               │
│             │         │ ┌──────────────────────┐      │
│             │         │ │ Management Dashboard │      │
│             │         │ │ - Upload/remove sites│      │
│             │         │ │ - API key management │      │
│             │         │ │ - Usage monitoring   │      │
│             │         │ └──────────────────────┘      │
└─────────────┘         └──────────────────────────────┘
```

### Database Decision Framework

| Approach | Pros | Cons | Best For |
|----------|------|------|----------|
| **PostgreSQL + pgvector** | Single DB, mature, SQL, ACID, self-hostable | Vector perf at very large scale | <1M vectors, want simplicity |
| **PostgreSQL + Qdrant/Milvus** | Best vector perf, specialized ANN | Two systems to manage | >1M vectors, perf-critical |
| **SQLite (local) + PostgreSQL (server)** | Dual-mode: local dev + server prod | Two codepaths | Gradual migration |
| **LanceDB** | Embedded vector DB, columnar, fast | Newer, less ecosystem | Hybrid local/server |

### Suggested Phased Approach
1. **Phase 0**: Database selection research (deepresearch prompts above)
2. **Phase 1**: Server skeleton (FastAPI + auth + graph upload endpoint)
3. **Phase 2**: Database backend (replace pickle on server side)
4. **Phase 3**: Remote CLI (`--fs2-remote` flag + RemoteGraphStore)
5. **Phase 4**: Management dashboard
6. **Phase 5**: MCP remote bridge (MCP tools → HTTP → server)

---

## Appendix: File Inventory

### Core Files Affected by Server Mode
| File | Purpose | Server Impact |
|------|---------|---------------|
| `core/repos/graph_store.py` | GraphStore ABC | Add RemoteGraphStore |
| `core/repos/graph_store_impl.py` | NetworkX pickle impl | Server replaces with DB |
| `core/services/graph_service.py` | Multi-graph caching | Extend for remote catalog |
| `core/services/search/search_service.py` | Search orchestration | Semantic → server-side |
| `core/services/search/semantic_matcher.py` | Vector brute-force | Replace with DB ANN index |
| `mcp/server.py` | MCP STDIO server | Add remote graph support |
| `mcp/dependencies.py` | Lazy DI singletons | Add remote config path |
| `cli/main.py` | CLI entry point | Add --fs2-remote flag |
| `config/objects.py` | Config models | Add ServerConfig, RemoteConfig |

### New Files Needed
| File | Purpose |
|------|---------|
| `core/repos/graph_store_remote.py` | HTTP client implementing GraphStore ABC |
| `server/app.py` | FastAPI server application |
| `server/routes/*.py` | API endpoint handlers |
| `server/database/*.py` | Database models and migrations |
| `server/auth.py` | API key authentication |
| `server/dashboard/` | Management UI |
| `config/remote_config.py` | Remote endpoint configuration |

---

**Research Complete**: 2026-03-05T03:05:00Z
**Report Location**: docs/plans/028-server-mode/research-dossier.md

---

## Next Steps

**External Research Suggested** (3 opportunities identified):
1. **Database Selection** — run `/deepresearch` prompt in Research Opportunity 1
2. **Management Dashboard** — run `/deepresearch` prompt in Research Opportunity 2
3. **Remote CLI Protocol** — run `/deepresearch` prompt in Research Opportunity 3

Save results to: `docs/plans/028-server-mode/external-research/[topic-slug].md`

- **Next step (with research)**: Run `/deepresearch` prompts, then `/plan-1b-specify`
- **Next step (skip research)**: Run `/plan-1b-specify "fs2 server mode"` to create specification
