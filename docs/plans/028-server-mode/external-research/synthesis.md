# Deep Research Synthesis: fs2 Server Mode

**Generated**: 2026-03-05
**Research Topics**: Database Selection | Management Dashboard | Remote CLI Protocol
**Source**: 3 parallel Perplexity Deep Research queries (~165K chars total)
**Full Reports**: `external-research/{database-selection,management-dashboard,remote-cli-protocol}.md`

---

## TL;DR — Three Key Decisions Resolved

| Decision | Recommendation | Confidence |
|----------|---------------|------------|
| **Database** | PostgreSQL + pgvector (single DB for graph + vectors + content) | High ✅ |
| **Dashboard** | FastAPI + Jinja2 + HTMX + Alpine.js (server-rendered, Python-only) | High ✅ |
| **API Protocol** | REST (FastAPI) + httpx client + API key auth | High ✅ |

---

## 1. Database Selection — PostgreSQL + pgvector

### Recommendation
Use **PostgreSQL 15+ with pgvector HNSW** as the single database for all three data types: graph structure (parent-child edges), vector embeddings (1024-dim), and full-text source content.

### Why Not Polyglot?
- At our scale (10-20M nodes), pgvector with HNSW achieves **11.4x higher throughput** than Qdrant (471 QPS vs 41 QPS at 99% recall on 50M vectors)
- Sub-100ms query latency across all percentiles (p50 ~31ms, p95 ~60ms)
- Eliminates operational burden of maintaining 2-3 separate systems
- Python ecosystem support is excellent (asyncpg, psycopg 3, SQLAlchemy)

### Key Design Decisions
| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Multi-tenancy** | Row-Level Security (RLS) | Database-enforced isolation, can't be bypassed by app bugs |
| **Embedding precision** | float16 (halfvec) | 2x storage reduction (40GB→20GB), 50% faster index builds |
| **Graph traversal** | Recursive CTEs with parent_id index | 10-50ms for 4-level traversals, sufficient for code hierarchies |
| **Full-text search** | PostgreSQL trigram indexes | Fast text/regex search; Elasticsearch only if >1s latency |
| **Connection pooling** | psycopg 3 async pool | pool_size=5-10, max_overflow=10-20, pool_pre_ping=True |

### Migration from Pickle
- Use PostgreSQL `COPY` command: imports 10M rows in **14 seconds** (vs 841s for individual inserts)
- Pre-quantize embeddings to float16 during export
- HNSW index build: ~5-6 hours for 10M vectors at 1024-dim with float16
- Gradual rollout: new projects → PostgreSQL first, migrate existing during validation

### Scale Thresholds (When to Reassess)
- **>50M vectors**: Consider dedicated vector DB (Qdrant/Milvus) alongside PostgreSQL
- **>8-level deep traversals**: Consider Neo4j for complex graph queries
- **>1s full-text latency**: Add Elasticsearch as search backend

### Cost Estimate
- Managed PostgreSQL (AWS RDS r6g.xlarge): **$500-800/month** for 10-20M vectors
- 5-10x cheaper than Pinecone/Weaviate managed services

---

## 2. Management Dashboard — FastAPI + HTMX

### Recommendation
**Server-side rendered dashboard** using FastAPI + Jinja2 templates + HTMX + Alpine.js. Layer SQLAdmin/Starlette-Admin for CRUD operations.

### Why This Approach?
- Entire codebase stays in Python (no frontend engineers needed)
- HTMX provides modern interactivity without JavaScript frameworks
- Single deployment unit (one Docker container)
- FastAPI's dependency injection works the same for API and dashboard routes

### Architecture
```
FastAPI Application
├── /api/v1/...          → JSON endpoints (programmatic access)
├── /dashboard/...       → Jinja2+HTMX templates (management UI)
├── /admin/...           → SQLAdmin/Starlette-Admin (CRUD operations)
└── /health, /metrics    → Operational endpoints
```

### Key Component Decisions
| Component | Decision | Rationale |
|-----------|----------|-----------|
| **File upload** | Chunked (tus protocol or custom multipart, 5-20MB chunks) | Handles 50-500MB graphs reliably |
| **Background jobs** | ARQ (Redis-backed) | Lightweight, async-native, simpler than Celery |
| **Real-time status** | Server-Sent Events (SSE) | Simpler than WebSocket, sufficient for status updates |
| **API key management** | Opaque keys (crypto random), store hashed, scope per tenant/site | Standard pattern, Redis rate limiting |
| **Usage metering** | Redis queues → PostgreSQL aggregation → Chart.js visualization | Async tracking, no request latency impact |
| **Dashboard auth** | OAuth2 (GitHub/Google) + JWT sessions (24h) | Leverage existing identity; separate from API key auth |

### Implementation Phases (12 weeks)
1. **Weeks 1-2**: FastAPI skeleton + PostgreSQL multi-tenancy + user auth
2. **Weeks 3-4**: Dashboard CRUD (sites, tenants) with Starlette-Admin
3. **Weeks 5-6**: File upload with chunked uploads + progress
4. **Weeks 7-8**: Background job processing (ARQ) + indexing status (SSE)
5. **Weeks 9-10**: API key management + rate limiting + usage tracking
6. **Weeks 11-12**: OAuth2 integration + role-based authorization

---

## 3. Remote CLI Protocol — REST + httpx

### Recommendation
**REST API** with FastAPI server + **httpx AsyncClient** on the CLI side. API key authentication. Transparent local/remote switching via adapter pattern.

### Why REST Over GraphQL/gRPC?
- Universal tooling (curl, Postman, browser)
- FastAPI generates OpenAPI docs automatically
- HTTP caching (ETag, If-None-Match) works natively
- CLI tools primarily make simple, well-defined queries
- gRPC adds protobuf complexity; GraphQL adds query language complexity

### API Design
```
# Graph Management
GET    /api/v1/graphs                          → list available graphs
POST   /api/v1/graphs/{tenant}/{name}/upload   → upload graph pickle
DELETE /api/v1/graphs/{tenant}/{name}           → remove graph

# Query Operations
GET    /api/v1/graphs/{name}/tree?pattern=...&max_depth=...&detail=...
GET    /api/v1/graphs/{name}/search?pattern=...&mode=...&limit=...&offset=...
GET    /api/v1/graphs/{name}/nodes/{node_id}?detail=...

# Authentication
Header: Authorization: Bearer fs2_<api_key>
```

### Transparent Local/Remote Switching
```python
# Same ABC interface, different implementations
class GraphStore(ABC):  # existing
    ...

class NetworkXGraphStore(GraphStore):  # existing local impl
    ...

class RemoteGraphStore(GraphStore):    # NEW remote impl
    def __init__(self, base_url: str, api_key: str, client: httpx.AsyncClient): ...
    async def get_node(self, node_id: str) -> CodeNode | None:
        response = await self.client.get(f"{self.base_url}/nodes/{node_id}")
        return CodeNode(**response.json()) if response.status_code == 200 else None
```

**Injection**: Based on `--fs2-remote` flag or `FS2_REMOTE_URL` env var, dependency injection creates RemoteGraphStore instead of NetworkXGraphStore.

### Key Technical Decisions
| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **HTTP client** | httpx (AsyncClient) | Requests-like API, HTTP/2, sync+async modes |
| **Authentication** | API key in config/env + OAuth2 device flow | Non-interactive for MCP, interactive for CLI |
| **Compression** | gzip/brotli (Accept-Encoding) | 70-85% reduction for code content |
| **Caching** | ETag + graph version hash + disk cache | Auto-invalidate on re-index |
| **Large uploads** | Chunked (5-20MB) with resumability | 50-500MB graph files |
| **Pagination** | Cursor-based for search, depth-limited for tree | Stable pagination, lazy tree expansion |
| **Offline fallback** | Local cache serves stale data with warning | Degraded but functional |
| **Timeouts** | connect=5s, read=30s, write=60s (upload: 300s) | Large responses need generous timeouts |

### MCP Integration
MCP server (FastMCP) routes to local or remote based on config:
```python
# In MCP dependencies.py
if config.remote_url:
    return RemoteGraphStore(config.remote_url, config.api_key, httpx_client)
else:
    return NetworkXGraphStore()  # existing local path
```

---

## Cross-Cutting Concerns

### Security
- **Source code isolation**: Tenant data in separate RLS-enforced rows
- **API keys**: Stored hashed (bcrypt), scoped per tenant/site
- **Upload validation**: RestrictedUnpickler for graph files (prevent arbitrary code execution)
- **TLS**: Required for all remote connections; self-signed cert support for enterprise

### Monitoring
- PostgreSQL: pg_stat_statements, connection pool metrics
- API: request latency (p50/p95/p99), error rates, per-tenant usage
- Background jobs: queue depth, processing time, failure rate

### Deployment
- **Self-hosted**: Docker Compose (FastAPI + PostgreSQL + Redis)
- **Cloud**: Kubernetes + managed PostgreSQL (RDS/Cloud SQL) + managed Redis (ElastiCache)
- **Serverless option**: Neon (serverless PostgreSQL) + Cloud Run

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| pgvector HNSW index build time (5-6h) | Blocks re-indexing | Build in background, swap atomically |
| Large graph upload failures | Poor UX | Chunked upload with resumability |
| Connection pool exhaustion under load | Service degradation | Pool monitoring + auto-scaling |
| Stale client cache after re-index | Wrong results | ETag + graph version hash invalidation |
| Pickle deserialization attacks | Security breach | RestrictedUnpickler whitelist on server |
| Enterprise proxy/firewall blocking | Adoption barrier | Configurable proxy, TLS options |

---

## Recommended Implementation Order

1. **Phase 1 — Server Skeleton**: FastAPI + PostgreSQL + pgvector + auth + graph upload
2. **Phase 2 — Database Backend**: Schema design, COPY-based import, HNSW indexes
3. **Phase 3 — Remote CLI**: `--fs2-remote` flag + RemoteGraphStore + httpx client
4. **Phase 4 — Management Dashboard**: HTMX dashboard + SSE status + API key mgmt
5. **Phase 5 — MCP Remote Bridge**: MCP tools → HTTP → server
6. **Phase 6 — Polish**: Caching, compression, monitoring, docs

---

*Full research reports with detailed code examples, benchmarks, and citations are in:*
- `external-research/database-selection.md` (42K chars)
- `external-research/management-dashboard.md` (61K chars)
- `external-research/remote-cli-protocol.md` (63K chars)
