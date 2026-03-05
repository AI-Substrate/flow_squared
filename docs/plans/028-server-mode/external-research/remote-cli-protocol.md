# Protocol Design for Dual-Mode Code Intelligence APIs: Local and Remote Operation

This comprehensive report addresses the architectural and design considerations for building a code intelligence tool that operates seamlessly in both local-only and remote-hybrid modes. The analysis synthesizes protocol selection, endpoint design, transparent switching mechanisms, payload handling strategies, authentication patterns, and caching architectures to guide implementation decisions for a Python-based CLI tool consuming a code graph service.

## Executive Summary

Building a code intelligence tool that transparently switches between local file-system operations and remote server queries requires careful protocol selection, thoughtful API design, and robust connection management. **For this specific use case, REST APIs emerge as the primary choice for the Python CLI consumer**, complemented by GraphQL for complex querying scenarios when clients need fine-grained control, and gRPC considered only for high-performance internal service-to-service communication where binary efficiency is paramount. The architecture should employ Clean Architecture principles with protocol-independent Abstract Base Classes (ABCs) that enable seamless adapter swapping via dependency injection, persistent connection pooling through HTTPX with careful timeout configuration, chunked uploads for large graph payloads, cursor-based pagination for tree traversals, ETag-based validation for client-side caching, and graceful offline fallback mechanisms that cache critical responses locally. Authentication should leverage API keys for programmatic access with optional OAuth2 Device Flow for interactive MCP agent scenarios, while enterprise deployments require TLS certificate validation and proxy/firewall awareness.

## API Protocol Selection: REST, GraphQL, and gRPC Trade-offs

### Understanding the Operational Context

Before selecting a protocol, the operational context demands examination. The code intelligence tool must serve three distinct consumers: a Python CLI tool making synchronous or asynchronous requests, an MCP protocol agent making JSON-RPC calls over stdio, and potentially web-based IDE plugins making browser-based requests.[1][27] The workload characteristics include hierarchical tree queries returning 1000+ nodes, full-text and regex search with filtering and pagination, semantic search capabilities (which require sophisticated query logic), large binary payload uploads (50-500MB), and medium-sized content retrieval (up to 500KB per response). Different consumers have different expectations: the CLI tool expects simplicity and low overhead, the MCP agent expects JSON-RPC compatibility, and web consumers expect standard HTTP patterns.[26]

### REST API Characteristics and Suitability

**REST remains the optimal choice for the primary Python CLI consumer and MCP protocol integration.** REST APIs use standard HTTP methods (GET, POST, PUT, DELETE) mapped to resource operations and are universally supported across platforms, languages, and infrastructure components.[1][13][16] For the code intelligence tool, REST excels because it enables natural resource mapping: repositories become `/v1/graphs/{graph_id}`, nodes become `/v1/graphs/{graph_id}/nodes/{node_id}`, and search operations become `/v1/graphs/{graph_id}/search`. The ubiquitous HTTP foundation means caching infrastructure (CDNs, reverse proxies, browser caches) work transparently without special configuration.[4][13]

REST's strength for this use case lies in simplicity and ecosystem maturity. Python's requests library and HTTPX client are battle-tested and widely understood.[7][8][10] The HTTP/1.1 protocol is simple enough that even low-level debugging with curl or browser developer tools is straightforward. Rate limiting is easily implemented through standard HTTP headers like `X-RateLimit-Remaining` and `Retry-After`.[36] The stateless nature of REST aligns perfectly with the scaling requirements of a multi-tenant server hosting hundreds of repositories.[1][27]

However, REST's limitations for code intelligence queries are substantial. The over-fetching problem appears immediately: a request for a node's metadata should not require downloading its entire source code, yet REST endpoint design often conflates these concerns. The under-fetching problem compounds: fetching a tree of related nodes requires multiple round-trips when following parent-child relationships.[1][3][6] REST's solution—creating separate endpoints like `/nodes/{id}/children` or `/nodes/{id}/related`—leads to endpoint proliferation, versioning challenges, and API surface area explosion. The uniform interface constraint means POST requests for side-effect-free queries (like complex searches) feel semantically wrong, though pragmatically they work.[4]

For a tool making hundreds of tree traversal queries during analysis, the inability to specify "return nodes with depth 1-3, but only include name and type fields" without multiple endpoints becomes painful. Query complexity that changes frequently—different clients need different subsets of node fields—creates maintenance overhead.[1][3]

### GraphQL as a Flexible Complement

**GraphQL should be introduced as a complementary API layer for complex querying scenarios, particularly when clients require fine-grained control over returned fields and relationships.** GraphQL is an excellent fit for the code intelligence domain because queries naturally express hierarchical data retrieval.[1][3][50] A single GraphQL query can express "fetch the tree starting at node X to depth 3, but for each node include only id, name, type, and file_path; and for leaf nodes also include source code if the file is less than 10KB" without requiring multiple round-trips or endpoint proliferation.[1][3][50]

GraphQL's resolver architecture aligns well with a graph database backend. Each field in the schema has an associated resolver function that knows how to retrieve that specific data.[3][6] For code intelligence, this means the schema naturally mirrors the graph structure: nodes have parent relationships, child relationships, references, and invocations.[50] Clients specify exactly what fields they need, reducing over-fetching.[1][3][6]

The adoption consideration is pragmatic: implement GraphQL if the complexity of client requests justifies it, but not as the primary API. GraphQL's learning curve, tooling maturity, and operational complexity exceed REST.[1][3] Implementing authentication, authorization, rate limiting, and caching in GraphQL requires more infrastructure than REST.[1][3] However, if a significant percentage of CLI operations involve complex traversals with varying field requirements, GraphQL provides substantial value.[1][3][50]

A hybrid approach works well: expose critical operations through simple REST endpoints (`/graphs/{id}/tree`, `/graphs/{id}/search`) and provide a GraphQL endpoint at `/graphql` for power users and sophisticated clients that need maximum flexibility.[4][50]

### gRPC for Internal Service Communication Only

**gRPC should not be the primary API exposed to the CLI tool or MCP agent, but should be considered for internal service-to-service communication within the server infrastructure.** gRPC uses HTTP/2 with binary Protocol Buffers, achieving roughly 5-10x performance advantage over REST for large payloads and streaming scenarios.[1][4][27] The language-agnostic interface definition language enables client library generation in any language.[1][4][27][30]

However, gRPC's drawbacks are disqualifying for the CLI consumer use case. gRPC requires special software on both client and server; the Python CLI tool would need additional grpcio and grpcio-tools dependencies.[1][4][27] gRPC's binary format makes debugging difficult—examining a gRPC request in transit requires specialized tools rather than curl or browser developer tools.[1][4][27] The HTTP/2 requirement adds complexity, particularly in enterprise environments with non-standard proxy configurations.[1][4] Most critically, gRPC is tightly coupled: client and server must share `.proto` files, making client-side upgrades dependent on schema synchronization.[1][27]

gRPC excels for internal service architecture where infrastructure control is complete: microservices calling other microservices within the same data center can benefit substantially from gRPC's performance and typed interface contracts.[1][4][27][30] If the server internally runs multiple microservices (graph computation, semantic indexing, etc.), they should communicate via gRPC. But the boundary between user-facing API and internal services should be REST or GraphQL.[1][27]

### Protocol Recommendation Summary

The recommended protocol strategy is: **(1) REST as the primary API for all CLI and standard HTTP consumers, (2) GraphQL as an optional advanced API for clients requiring complex queries, and (3) gRPC for internal service-to-service communication.** For an MCP protocol consumer, implement it as JSON-RPC over the REST API or create a specific MCP server transport layer that internally calls REST endpoints.[26]

## Concrete API Endpoint Design and Schema Architecture

### RESTful Resource Hierarchy and URL Patterns

The code intelligence API should follow REST principles with a hierarchical resource model that mirrors the actual data structure. The primary resources are graphs (repositories), nodes, and search results. A well-designed URL structure for this domain follows these patterns:[13][16]

```
GET    /v1/graphs                          # List available graphs
GET    /v1/graphs/{graph_id}               # Get graph metadata
POST   /v1/graphs                          # Create/register a new graph
PUT    /v1/graphs/{graph_id}               # Update graph metadata
DELETE /v1/graphs/{graph_id}               # Delete graph (admin only)

GET    /v1/graphs/{graph_id}/nodes/{node_id}        # Get single node with full content
GET    /v1/graphs/{graph_id}/nodes                  # List nodes (with pagination)
GET    /v1/graphs/{graph_id}/tree                   # Get hierarchical tree structure
GET    /v1/graphs/{graph_id}/search                 # Search nodes by pattern
POST   /v1/graphs/{graph_id}/upload                 # Chunked graph upload
GET    /v1/graphs/{graph_id}/upload/{upload_id}     # Get upload status
```

Each endpoint should use nouns (resources) rather than verbs.[16] The HTTP method (GET, POST, PUT, DELETE) communicates the action.[1][16] Versioning is embedded in the URL path (`/v1/`) using URI versioning rather than query parameters or headers, which simplifies routing, caching, and client logic.[13][16] Multiple simultaneous API versions can be maintained, allowing clients to upgrade at their own pace.[13][16]

### Request/Response Schema Design with Content Negotiation

Request schemas should be compact and clear. A tree query request might look like:

```json
GET /v1/graphs/{graph_id}/tree?
    root_node_id=file_src_main_py&
    max_depth=3&
    detail=minimal&
    filter_types=function,class&
    limit=1000&
    cursor=abc123
```

The query parameters control the response shape: `detail` specifies granularity (minimal for ids/names only, normal for metadata, full for source code), `filter_types` limits results to specific node types, and `cursor` handles pagination.[14][17] The `limit` parameter bounds the response size.[14]

Response schemas should nest related data hierarchically but avoid deep nesting that increases parsing overhead. A tree response structure might be:

```json
{
  "data": {
    "tree": [
      {
        "id": "func_calculate_price",
        "type": "function",
        "name": "calculate_price",
        "file_path": "src/pricing.py",
        "line_number": 42,
        "children": [
          {
            "id": "func_get_tax_rate",
            "type": "function",
            "name": "get_tax_rate",
            "file_path": "src/pricing.py",
            "line_number": 58,
            "children": []
          }
        ],
        "source_code": null
      }
    ],
    "total_count": 847,
    "next_cursor": "def456",
    "has_more": true
  },
  "meta": {
    "request_id": "req_12345",
    "timestamp": "2026-03-05T03:12:53Z",
    "server": "code-intelligence-api-prod-3"
  }
}
```

The `data` field contains the requested resource, while `meta` contains metadata about the response itself.[13][16] The `null` source code indicates it wasn't included (because `detail=minimal`), allowing clients to decide whether to fetch it separately.[16]

For large responses, compression becomes critical. The server should support `Accept-Encoding: gzip, deflate, br` headers and compress responses exceeding a threshold (e.g., 1KB).[15][18] HTTPX automatically handles decompression, making this transparent to the client.[8][10]

### Pagination Strategy: Cursor vs. Offset

**Cursor-based pagination is mandatory for this use case; offset-based pagination is unsuitable for code intelligence queries.** Offset pagination ("give me 20 items starting at position 100") has severe performance problems at scale because the database must skip 100 items even when an index exists.[14][17] For a tree with thousands of nodes, offset pagination degrades performance exponentially as clients progress through pages.

Cursor-based pagination uses a position marker (the cursor) that points to a specific record, then requests "give me 20 items after this cursor."[14][17] The cursor is typically an opaque string generated by encoding the last item's unique identifier and sorting key. For a tree with nodes sorted by id and name, the cursor might be base64-encoded JSON like `{"id":"func_calculate_price","name":"calculate_price"}`, allowing the server to efficiently find the next batch using indexed lookups.[14][17]

The response includes `next_cursor` and optionally `prev_cursor` for navigation. Clients should never expose cursors to users; cursors are ephemeral and may change if sorting changes. They cannot be shared or bookmarked reliably.[14] This design choice prevents data inconsistencies when new items are inserted during pagination—the cursor maintains its position relative to the specific record, not relative to an arbitrary row count.[14][17]

A search response with cursor pagination:

```json
{
  "data": {
    "results": [
      {"id": "node_1", "name": "search_results_one", "score": 0.95},
      {"id": "node_2", "name": "search_results_two", "score": 0.87}
    ],
    "pagination": {
      "next_cursor": "eyJpZCI6Im5vZGVfMiIsInNjb3JlIjowLjg3fQ==",
      "total_count": 847,
      "has_more": true,
      "limit": 20
    }
  }
}
```

### Error Response Design and Status Codes

All error responses should follow a consistent structure based on RFC 9457 (Problem Details for HTTP APIs), which provides standardized machine-readable error information. The response includes a machine-readable error code, human-readable message, and detailed context:

```json
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/problem+json

{
  "type": "https://api.code-intelligence.com/errors/invalid-search-syntax",
  "title": "Invalid Search Pattern",
  "status": 422,
  "detail": "The provided regex pattern has unmatched parentheses",
  "instance": "/v1/graphs/repo-123/search",
  "field": "pattern",
  "suggestion": "Did you mean: (?:pattern)?"
}
```

Status codes should be appropriate: 400 for malformed requests (syntax errors), 401 for authentication failures, 403 for authorization failures (insufficient permissions), 404 for missing resources, 422 for validation failures (semantically invalid but well-formed requests), 429 for rate limit exceeded, and 5xx for server errors. Rate-limited responses should include `Retry-After` header guidance.[36]

### API Versioning Strategy

Use URI versioning (`/v1/`, `/v2/`) rather than query parameter or header versioning. URI versioning makes version boundaries explicit, simplifies caching rules (each version has distinct cache keys), and enables simple load balancer routing.[13][16] When backwards-incompatible changes are necessary, create a new major version and maintain the old version for a deprecation period (typically 6-12 months), allowing clients to upgrade at their pace.[13][16]

Version numbers should follow semantic versioning principles: major versions for breaking changes, minor versions for backwards-compatible additions, and patch versions for bug fixes. The initial release is `/v1/`, and breaking changes increment the major version to `/v2/`.[13][16] Within a version, backwards-compatible additions (new optional parameters, new fields in responses) can be added without version bumps.[13][16]

## Transparent Local/Remote Switching Through Dependency Injection

### Abstract Base Class Protocol Design

The architecture should define protocol-independent Abstract Base Classes (ABCs) that abstract away the distinction between local and remote stores. The primary interface hierarchy separates concerns across multiple tightly-focused protocols:[9]

```python
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

@dataclass(frozen=True)
class Node:
    id: str
    type: str
    name: str
    file_path: str
    line_number: int
    source_code: Optional[str] = None
    metadata: Dict[str, Any] = None

class GraphStore(ABC):
    """Core graph data retrieval interface"""
    
    @abstractmethod
    async def get_node(self, node_id: str, detail: str = 'normal') -> Node:
        """Retrieve a single node. detail: minimal|normal|full"""
        pass
    
    @abstractmethod
    async def get_tree(self, root_node_id: str, max_depth: int = 3,
                       detail: str = 'normal', limit: int = 1000) -> List[Node]:
        """Retrieve hierarchical tree from root node"""
        pass
    
    @abstractmethod
    async def search(self, pattern: str, mode: str = 'auto',
                    limit: int = 100, offset: str = None,
                    filters: Optional[Dict] = None) -> Dict[str, Any]:
        """Search for nodes matching pattern"""
        pass
    
    @abstractmethod
    async def list_graphs(self) -> List[Dict[str, Any]]:
        """List available graphs/repositories"""
        pass

class GraphUpload(ABC):
    """File upload interface for large payloads"""
    
    @abstractmethod
    async def start_upload(self, graph_id: str, 
                          file_size: int) -> str:
        """Initialize chunked upload, returns upload_id"""
        pass
    
    @abstractmethod
    async def upload_chunk(self, upload_id: str, 
                          chunk_index: int, 
                          chunk_data: bytes) -> Dict[str, Any]:
        """Upload a single chunk"""
        pass
    
    @abstractmethod
    async def complete_upload(self, upload_id: str) -> Dict[str, Any]:
        """Finalize upload and process graph"""
        pass
```

These ABCs define contracts independent of implementation details. The `GraphStore` interface specifies what operations are possible without exposing how they're implemented.[9] The async/await syntax indicates these are inherently asynchronous operations, suitable for both local (async file I/O) and remote (HTTP requests) implementations.[9]

### Local Implementation Using Memgraph

The local implementation uses Memgraph (an in-memory graph database) to provide the same `GraphStore` interface:

```python
class LocalGraphStore(GraphStore):
    """Local in-memory graph implementation using Memgraph"""
    
    def __init__(self, connection_string: str = 'localhost:7687'):
        self.connection_string = connection_string
        self.pool: Optional[aiomemgraph.ConnectionPool] = None
    
    async def __aenter__(self):
        self.pool = await aiomemgraph.create_pool(
            host='localhost', port=7687,
            min_size=5, max_size=20
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
    
    async def get_node(self, node_id: str, 
                       detail: str = 'normal') -> Node:
        query = f"""
        MATCH (n) WHERE n.id = $node_id
        RETURN n.id, n.type, n.name, n.file_path, n.line_number
        """ + (", n.source_code" if detail in ['normal', 'full'] else "")
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, {'node_id': node_id})
                result = await cursor.fetchone()
                
                if not result:
                    raise NodeNotFoundError(node_id)
                
                return Node(*result)
    
    async def get_tree(self, root_node_id: str, 
                       max_depth: int = 3,
                       detail: str = 'normal',
                       limit: int = 1000) -> List[Node]:
        # BFS traversal using Cypher query
        query = f"""
        MATCH path = (root)-[*0..{max_depth}]-(n)
        WHERE root.id = $root_id
        RETURN n.id, n.type, n.name, n.file_path, n.line_number
        LIMIT {limit}
        """
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, {'root_id': root_node_id})
                results = await cursor.fetchall()
                return [Node(*row) for row in results]
```

The local implementation uses async context managers (`__aenter__`, `__aexit__`) for resource lifecycle management. Connection pooling minimizes overhead when reusing connections. The same `GraphStore` interface is implemented, making the local and remote implementations interchangeable.[9][42]

### Remote Implementation with HTTPX Client

The remote implementation calls the REST API over HTTP:

```python
class RemoteGraphStore(GraphStore):
    """Remote implementation calling REST API over HTTP"""
    
    def __init__(self, base_url: str, api_key: str, 
                 timeout: float = 30.0):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Authorization": f"Bearer {self.api_key}"},
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def get_node(self, node_id: str, 
                       detail: str = 'normal') -> Node:
        try:
            response = await self.client.get(
                f"/v1/graphs/current/nodes/{node_id}",
                params={"detail": detail}
            )
            response.raise_for_status()
            data = response.json()['data']['node']
            return Node(**data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise NodeNotFoundError(node_id)
            raise
    
    async def get_tree(self, root_node_id: str, 
                       max_depth: int = 3,
                       detail: str = 'normal',
                       limit: int = 1000) -> List[Node]:
        cursor = None
        nodes = []
        
        while True:
            params = {
                "root_node_id": root_node_id,
                "max_depth": max_depth,
                "detail": detail,
                "limit": min(limit, 100)  # Fetch in batches
            }
            if cursor:
                params["cursor"] = cursor
            
            response = await self.client.get(
                f"/v1/graphs/current/tree",
                params=params
            )
            response.raise_for_status()
            data = response.json()['data']
            
            nodes.extend([Node(**n) for n in data['tree']])
            
            if not data['has_more'] or len(nodes) >= limit:
                break
            cursor = data['next_cursor']
        
        return nodes[:limit]
    
    async def search(self, pattern: str, mode: str = 'auto',
                    limit: int = 100, offset: str = None,
                    filters: Optional[Dict] = None) -> Dict[str, Any]:
        params = {
            "pattern": pattern,
            "mode": mode,
            "limit": limit,
        }
        if offset:
            params["cursor"] = offset
        if filters:
            params.update(filters)
        
        response = await self.client.get(
            f"/v1/graphs/current/search",
            params=params
        )
        response.raise_for_status()
        return response.json()['data']
```

The remote implementation uses HTTPX with persistent connection pooling (`limits` parameter) to reuse TCP connections across multiple requests.[8][10] The async nature allows multiple concurrent requests without blocking.[8][10] The HTTP client automatically handles compression, decompression, and status code validation.[8][10]

### Dependency Injection Container and Adapter Selection

A dependency injection container manages instantiation based on the `--fs2-remote` flag:

```python
from dependency_injector import containers, providers
from dependency_injector.wiring import inject, Provide

class GraphContainer(containers.DeclarativeContainer):
    config = providers.Configuration()
    
    # Conditional instantiation based on remote flag
    graph_store = providers.Singleton(
        lambda: (
            RemoteGraphStore(
                base_url=GraphContainer.config.remote_url(),
                api_key=GraphContainer.config.api_key()
            ) if GraphContainer.config.use_remote()
            else LocalGraphStore(
                connection_string=GraphContainer.config.local_connection()
            )
        )
    )
    
    graph_upload = providers.Singleton(
        lambda: (
            RemoteGraphUpload(
                base_url=GraphContainer.config.remote_url(),
                api_key=GraphContainer.config.api_key()
            ) if GraphContainer.config.use_remote()
            else LocalGraphUpload()
        )
    )
    
    search_service = providers.Factory(
        SearchService,
        store=graph_store,
        cache=providers.Singleton(ResponseCache)
    )
```

In the CLI entrypoint, configuration flows from the `--fs2-remote` flag:

```python
@app.command()
@inject
def tree_command(
    pattern: str = typer.Argument(...),
    max_depth: int = typer.Option(3),
    fs2_remote: Optional[str] = typer.Option(None, "--fs2-remote"),
    graph_store: GraphStore = Provide[GraphContainer.graph_store]
) -> None:
    """Display hierarchical tree structure"""
    
    container = GraphContainer()
    container.config.use_remote.set(fs2_remote is not None)
    
    if fs2_remote:
        container.config.remote_url.set(fs2_remote)
        container.config.api_key.set(
            os.environ.get('CODE_INTELLIGENCE_API_KEY')
        )
    else:
        container.config.local_connection.set('localhost:7687')
    
    container.wire(modules=[__name__])
    
    async def run():
        async with graph_store as store:
            nodes = await store.get_tree(pattern, max_depth)
            for node in nodes:
                typer.echo(f"{node.name} ({node.type})")
    
    asyncio.run(run())
```

This design achieves three critical goals: (1) **Protocol independence**—the CLI code doesn't know whether it's calling local or remote storage, (2) **Testability**—unit tests can inject mock implementations, and (3) **Flexibility**—switching between local and remote requires only configuration, not code changes.[9][42]

## Large Payload Handling: Compression, Chunking, and Streaming

### Response Compression Strategy

All responses exceeding a threshold (typically 1KB) should be compressed using gzip or brotli.[15][18][48] The HTTP `Content-Encoding` and `Accept-Encoding` headers control compression negotiation. HTTPX handles this transparently:

```python
# Server sets compression minimumCompressionsSize
# HTTPX automatically decompresses responses

response = await client.get(url)  # Transparent decompression
large_response_text = response.text  # Already decompressed
```

For a tree query returning 1000+ nodes in JSON, compression typically achieves 70-85% size reduction, making the difference between a 5MB response and a 750KB response.[15] The CPU cost of compression is negligible compared to network transmission time.[15]

The server-side API Gateway configuration (NGINX, Envoy) should apply compression:

```yaml
# NGINX configuration
gzip on;
gzip_vary on;
gzip_min_length 1000;
gzip_types application/json text/plain;
```

### Chunked Upload for Large Graph Payloads

Uploading a 50-500MB graph file requires chunked upload to handle potential network interruptions and memory constraints. The multipart upload pattern involves three steps: (1) **Initialize** an upload session and get presigned URLs for each chunk, (2) **Upload chunks** in parallel, and (3) **Complete** the upload, signaling the server to assemble and validate.[20]

The upload flow:

```python
class RemoteGraphUpload(GraphUpload):
    async def start_upload(self, graph_id: str, 
                          file_size: int) -> str:
        response = await self.client.post(
            f"/v1/graphs/{graph_id}/upload",
            json={
                "file_size": file_size,
                "chunk_size": 5 * 1024 * 1024  # 5MB chunks
            }
        )
        response.raise_for_status()
        data = response.json()['data']
        return data['upload_id']
    
    async def upload_chunk(self, upload_id: str, 
                          chunk_index: int, 
                          chunk_data: bytes) -> Dict[str, Any]:
        # Server provides presigned URLs to avoid auth overhead
        response = await self.client.post(
            f"/v1/uploads/{upload_id}/chunks/{chunk_index}",
            content=chunk_data,
            headers={"Content-Type": "application/octet-stream"}
        )
        response.raise_for_status()
        return response.json()['data']
    
    async def complete_upload(self, upload_id: str) -> Dict[str, Any]:
        response = await self.client.post(
            f"/v1/uploads/{upload_id}/complete"
        )
        response.raise_for_status()
        return response.json()['data']

async def upload_large_file(store: GraphUpload, 
                           graph_id: str,
                           file_path: str) -> None:
    file_size = os.path.getsize(file_path)
    chunk_size = 5 * 1024 * 1024  # 5MB
    
    upload_id = await store.start_upload(graph_id, file_size)
    
    try:
        with open(file_path, 'rb') as f:
            chunk_index = 0
            tasks = []
            
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                
                # Queue parallel uploads
                tasks.append(
                    store.upload_chunk(upload_id, chunk_index, chunk)
                )
                chunk_index += 1
                
                # Limit concurrent uploads to 4
                if len(tasks) >= 4:
                    await asyncio.gather(*tasks)
                    tasks = []
            
            # Upload remaining chunks
            if tasks:
                await asyncio.gather(*tasks)
        
        # Finalize upload
        result = await store.complete_upload(upload_id)
        print(f"Upload complete: {result}")
    
    except Exception as e:
        print(f"Upload failed: {e}")
        # Server should garbage-collect incomplete uploads
        raise
```

Parallel uploads significantly improve throughput. Uploading a 500MB file in 5MB chunks (100 total) with 4 concurrent uploads completes in roughly 25 chunk-times, versus 100 chunk-times sequentially.[20] The parallel strategy provides resilience: if one chunk fails, only that chunk needs re-upload, not the entire file.[20]

### Streaming Large Content Retrieval

For the `get_node` operation with `detail=full` (returning up to 500KB of source code), streaming prevents memory buffering of the entire response:

```python
async def get_node_streaming(self, node_id: str, 
                            detail: str = 'full') -> Node:
    """Stream large source code without buffering entire response"""
    
    async with self.client.stream(
        'GET',
        f"/v1/graphs/current/nodes/{node_id}",
        params={"detail": detail}
    ) as response:
        response.raise_for_status()
        
        # Stream response body
        buffer = b''
        decoder = json.JSONDecoder()
        
        async for chunk in response.aiter_bytes():
            buffer += chunk
            
            # Attempt to parse complete JSON objects
            try:
                obj, idx = decoder.raw_decode(buffer.decode('utf-8'))
                buffer = buffer[len(buffer.encode('utf-8')[:idx]):]
                
                # Process parsed object without keeping full buffer
                return Node(**obj['data']['node'])
            except json.JSONDecodeError:
                # Incomplete object, keep buffering
                pass
        
        # Handle final buffer
        if buffer:
            obj = json.loads(buffer)
            return Node(**obj['data']['node'])
```

HTTPX's `stream()` context manager reads chunks without buffering the entire response.[8][10] This pattern is particularly important for the tree operation returning thousands of nodes: streaming prevents memory spikes while maintaining a reasonable per-chunk buffer size (e.g., 64KB).[8][10]

## Authentication Design: API Keys and OAuth2 Device Flow

### API Key Authentication for CLI Tools

For command-line usage, API key authentication is pragmatic. The API key is typically stored in a configuration file (never committed to version control):

```ini
# ~/.config/code-intelligence/config.ini
[api]
api_key = skc_prod_abcdef123456
remote_url = https://code-intelligence.example.com
graph_id = my-repository
```

The key is passed as a Bearer token in the Authorization header:

```python
headers = {"Authorization": f"Bearer {api_key}"}
```

API keys should be long, cryptographically random strings (at least 32 bytes of entropy) to prevent guessing.[19][22] Keys can be scoped to specific permissions: a key might be read-only for searches and trees but not allow uploads or deletions.[19][22]

Key rotation is critical for security. The server should support multiple active keys per user, with old keys gradually deactivated after a grace period. The CLI can detect key expiration from HTTP 401 responses and prompt for key refresh.[19][22]

### OAuth2 Device Flow for MCP Agents

The Model Context Protocol (MCP) server consuming the code intelligence API may run in an environment without browser access (e.g., within an IDE server or AI agent). OAuth2 Device Flow (RFC 8628) is designed for this scenario.[22]

The flow:

```python
class ManagedAuthFlow:
    async def authenticate_device(self, client_id: str) -> str:
        """Use OAuth2 Device Flow for non-interactive auth"""
        
        # Step 1: Device requests authorization
        device_response = await httpx.AsyncClient().post(
            'https://auth.example.com/device',
            json={"client_id": client_id}
        )
        device_code = device_response.json()['device_code']
        user_code = device_response.json()['user_code']
        
        # Step 2: Display user code for manual authorization
        print(f"Authorize at: https://auth.example.com/authorize")
        print(f"Enter code: {user_code}")
        
        # Step 3: Poll for token until user authorizes
        client = httpx.AsyncClient()
        
        while True:
            token_response = await client.post(
                'https://auth.example.com/token',
                json={
                    "client_id": client_id,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
                }
            )
            
            if token_response.status_code == 200:
                token_data = token_response.json()
                return token_data['access_token']
            elif token_response.status_code == 403:
                # User hasn't authorized yet
                await asyncio.sleep(5)
            else:
                raise AuthenticationError(token_response.text)
```

Device Flow is designed for this use case: the device (MCP server) requests authorization, displays a user code for the operator to enter on a web portal, and polls for token completion.[22] The operator authorizes the device from any browser, and the token is delivered to the polling device.[22]

### TLS Certificate Validation for Self-Hosted Servers

For self-hosted deployments, TLS certificate validation prevents man-in-the-middle attacks. HTTPX validates TLS certificates by default, but custom certificate stores can be provided:

```python
# For self-signed certificates in development
import ssl

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE  # WARNING: Insecure, dev only

client = httpx.AsyncClient(verify=ssl_context)

# For custom CA certificate
ssl_context = ssl.create_default_context()
ssl_context.load_verify_locations('custom-ca.crt')

client = httpx.AsyncClient(verify=ssl_context)
```

In production, proper certificate validation is essential.[37][40] The CLI should fail with clear error messages if TLS validation fails, preventing silent credential exposure.[37][40]

## Client-Side Caching Strategies

### Cache Key Generation with Graph Version Hash

Client-side caching must account for graph updates. Using a **graph version hash** in the cache key ensures stale data is discarded when the graph changes:[21][45][48]

```python
class ResponseCache:
    def __init__(self, cache_dir: str = '~/.cache/code-intelligence'):
        self.cache_dir = Path(cache_dir).expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.graph_version_cache = {}
    
    async def get_graph_version(self, graph_id: str) -> str:
        """Fetch or cache the graph version hash"""
        
        if graph_id in self.graph_version_cache:
            return self.graph_version_cache[graph_id]
        
        # Fetch from server (minimal overhead)
        response = await client.get(
            f"/v1/graphs/{graph_id}",
            params={"fields": "version_hash"}
        )
        version_hash = response.json()['data']['version_hash']
        self.graph_version_cache[graph_id] = version_hash
        
        return version_hash
    
    def _cache_key(self, graph_id: str, operation: str, 
                   params: Dict) -> str:
        """Generate cache key including graph version"""
        
        version = self.graph_version_cache.get(graph_id, 'unknown')
        param_str = json.dumps(params, sort_keys=True)
        key_data = f"{graph_id}:{version}:{operation}:{param_str}"
        
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    async def get(self, graph_id: str, operation: str, 
                  params: Dict) -> Optional[Dict]:
        """Retrieve cached response if available and fresh"""
        
        version = await self.get_graph_version(graph_id)
        cache_key = self._cache_key(graph_id, operation, params)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
        
        # Check if cache entry is recent (TTL)
        mtime = cache_file.stat().st_mtime
        age_seconds = time.time() - mtime
        
        if age_seconds > 3600:  # 1 hour TTL
            return None
        
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None
    
    async def set(self, graph_id: str, operation: str, 
                  params: Dict, response: Dict) -> None:
        """Cache a response with version hash"""
        
        version = await self.get_graph_version(graph_id)
        cache_key = self._cache_key(graph_id, operation, params)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(response, f)
        except Exception as e:
            print(f"Cache write failed: {e}")
```

The version hash is a simple hash of the graph's metadata, computed server-side whenever the graph is updated. Using it in the cache key ensures that when the graph version changes (new commits, new analysis), cached data is automatically invalidated without requiring explicit cache invalidation commands.[21][45][48]

### ETag Validation and HTTP 304 Responses

For responses that change infrequently (metadata endpoints, immutable historical queries), ETag validation provides efficient cache revalidation:[21][45]

```python
class ETAGCache:
    def __init__(self, cache_file: str = '~/.cache/code-intelligence/etags.db'):
        import sqlite3
        self.db = sqlite3.connect(cache_file)
        self.db.execute("""
        CREATE TABLE IF NOT EXISTS etags (
            url TEXT PRIMARY KEY,
            etag TEXT,
            data TEXT,
            timestamp REAL
        )
        """)
        self.db.commit()
    
    async def get_with_validation(self, client: httpx.AsyncClient, 
                                  url: str) -> Dict:
        """Fetch with ETag validation for 304 responses"""
        
        cursor = self.db.execute(
            "SELECT etag, data, timestamp FROM etags WHERE url = ?",
            (url,)
        )
        row = cursor.fetchone()
        
        headers = {}
        if row:
            etag, cached_data, timestamp = row
            headers['If-None-Match'] = etag
            age_seconds = time.time() - timestamp
            
            if age_seconds < 300:  # 5 minute TTL
                return json.loads(cached_data)
        
        response = await client.get(url, headers=headers)
        
        if response.status_code == 304:
            # Server says cached data is still valid
            cursor = self.db.execute(
                "SELECT data FROM etags WHERE url = ?", (url,)
            )
            cached_data = cursor.fetchone()
            return json.loads(cached_data)
        
        response.raise_for_status()
        data = response.json()
        
        # Update ETag cache
        etag = response.headers.get('ETag', '')
        self.db.execute(
            "INSERT OR REPLACE INTO etags VALUES (?, ?, ?, ?)",
            (url, etag, json.dumps(data), time.time())
        )
        self.db.commit()
        
        return data
```

ETag validation reduces bandwidth: if the response hasn't changed, the server returns an empty 304 Not Modified response instead of re-sending the entire body.[21][45] This is particularly valuable for expensive metadata queries that change infrequently.[21]

### Selective Caching by Response Characteristics

Not all responses should be cached. The caching strategy should be selective:[45][48]

- **Cache indefinitely**: immutable historical data (commit hashes, file versions), reference data (supported node types)
- **Cache with version hash invalidation**: search results, tree queries, analysis data
- **Cache with TTL**: graph metadata (version info, last update time)
- **Don't cache**: current user context, real-time streaming data, temporary upload status
- **Cache with revalidation**: large responses that change infrequently (detailed node analysis)

A cache configuration system:

```python
CACHE_CONFIG = {
    'list_graphs': {
        'strategy': 'ttl',
        'ttl_seconds': 600,
        'max_size_bytes': 1_000_000
    },
    'get_node': {
        'strategy': 'version_hash',
        'max_size_bytes': 500_000
    },
    'search': {
        'strategy': 'version_hash',
        'max_size_bytes': 10_000_000
    },
    'get_tree': {
        'strategy': 'version_hash',
        'max_size_bytes': 50_000_000
    },
    'upload_status': {
        'strategy': 'no_cache'
    }
}

class CacheManager:
    async def handle_response(self, operation: str, 
                             graph_id: str,
                             params: Dict,
                             response: Dict) -> Dict:
        """Apply appropriate caching strategy"""
        
        config = CACHE_CONFIG.get(operation, {})
        strategy = config.get('strategy', 'no_cache')
        
        if strategy == 'no_cache':
            return response
        
        # Check size limits
        response_size = len(json.dumps(response).encode('utf-8'))
        max_size = config.get('max_size_bytes', 100_000_000)
        
        if response_size > max_size:
            print(f"Response too large ({response_size} > {max_size}), skipping cache")
            return response
        
        if strategy == 'ttl':
            await self.ttl_cache.set(operation, params, response)
        elif strategy == 'version_hash':
            await self.version_cache.set(graph_id, operation, params, response)
        elif strategy == 'etag':
            # Server provides ETag, handled in client
            pass
        
        return response
```

This selective approach prevents unbounded cache growth while maximizing hit rates for expensive queries.[45][48]

## Offline Fallback and Resilience Patterns

### Graceful Degradation When Remote Unavailable

When the remote server is unreachable, the CLI should gracefully degrade to cached data with clear user feedback:

```python
class ResilientGraphStore:
    def __init__(self, remote_store: GraphStore, 
                 cache: ResponseCache):
        self.remote = remote_store
        self.cache = cache
    
    async def get_node(self, node_id: str, 
                       detail: str = 'normal',
                       allow_stale: bool = False) -> Node:
        """Try remote, fallback to cache if unavailable"""
        
        try:
            return await self.remote.get_node(node_id, detail)
        except httpx.ConnectError as e:
            print(f"⚠️  Cannot connect to remote server: {e}")
            
            # Try cache
            cached = await self.cache.get(
                'get_node', 
                {'node_id': node_id, 'detail': detail}
            )
            
            if cached:
                cache_age = time.time() - cached['_timestamp']
                print(f"📦 Using cached response (age: {cache_age:.0f}s)")
                return Node(**cached['data'])
            
            raise OfflineError(
                f"Cannot reach remote server and no cached data for {node_id}. "
                f"Try again when connection is restored."
            )
    
    async def search(self, pattern: str, 
                    mode: str = 'auto',
                    limit: int = 100,
                    offset: str = None) -> Dict:
        """Search with offline fallback"""
        
        try:
            return await self.remote.search(pattern, mode, limit, offset)
        except httpx.ConnectError:
            # Semantic search requires remote neural model, cannot fallback
            if mode in ['semantic', 'auto']:
                raise OfflineError(
                    f"Semantic search requires connection to remote server. "
                    f"Try text or regex search for offline operation."
                )
            
            # Text/regex search can use cached results
            print(f"📦 Searching cached data (offline mode)")
            return await self._search_local_cache(pattern, mode, limit)
    
    async def _search_local_cache(self, pattern: str, 
                                 mode: str,
                                 limit: int) -> Dict:
        """Search across all cached results locally"""
        
        import re
        import glob
        
        results = []
        cache_dir = self.cache.cache_dir
        
        for cache_file in glob.glob(str(cache_dir / "*.json")):
            try:
                with open(cache_file, 'r') as f:
                    cached = json.load(f)
                
                if 'data' not in cached or 'tree' not in cached['data']:
                    continue
                
                for node in cached['data']['tree']:
                    # Local matching
                    if mode == 'text':
                        matches = pattern.lower() in node.get('name', '').lower()
                    elif mode == 'regex':
                        matches = re.search(pattern, node.get('name', ''))
                    else:
                        matches = False
                    
                    if matches:
                        results.append(node)
                        if len(results) >= limit:
                            break
                
                if len(results) >= limit:
                    break
            
            except Exception:
                continue
        
        return {
            'results': results[:limit],
            'total_count': len(results),
            'offline': True
        }
```

The resilient store layer transparently falls back to cache when the remote is unavailable. Users see clear indication that they're in offline mode, and operations that genuinely require remote connectivity (semantic search) fail with helpful messages rather than hanging.

### Exponential Backoff with Jitter for Retries

When the remote server is temporarily unavailable (429 Too Many Requests, 503 Service Unavailable), exponential backoff prevents overwhelming the server with retry attempts:[33][36]

```python
async def fetch_with_backoff(client: httpx.AsyncClient,
                            url: str,
                            max_retries: int = 5) -> httpx.Response:
    """Fetch with exponential backoff and jitter"""
    
    import random
    
    for attempt in range(max_retries):
        try:
            response = await client.get(url)
            
            # Success or client error (4xx)
            if response.status_code < 500:
                return response
            
            # Server error (5xx) - retry
            if response.status_code in [429, 503]:
                raise httpx.HTTPStatusError(response)
        
        except httpx.HTTPStatusError as e:
            if attempt == max_retries - 1:
                raise
            
            # Calculate backoff with jitter
            base_delay = 2 ** attempt  # 1, 2, 4, 8, 16
            jitter = random.uniform(0, 0.1 * base_delay)
            delay = base_delay + jitter
            
            # Check Retry-After header
            retry_after = e.response.headers.get('Retry-After')
            if retry_after:
                try:
                    delay = float(retry_after)
                except ValueError:
                    pass
            
            print(f"Attempt {attempt + 1}/{max_retries} failed, "
                  f"retrying in {delay:.1f}s...")
            await asyncio.sleep(delay)
        
        except httpx.ConnectError:
            if attempt == max_retries - 1:
                raise
            
            delay = 2 ** attempt + random.uniform(0, 0.1 * (2 ** attempt))
            print(f"Connection failed, retrying in {delay:.1f}s...")
            await asyncio.sleep(delay)
    
    raise RuntimeError("Max retries exceeded")
```

The exponential backoff formula \(delay = base^{attempt} + jitter\)[33][36] prevents the "thundering herd" problem where all clients retry simultaneously. Jitter (random variation) ensures clients don't synchronize their retries.[33][36] The Retry-After header, if present, overrides the calculated delay.[33][36]

## Implementation Pitfalls and Solutions

### HTTPX vs AIOHTTP Client Selection

**Recommendation: Use HTTPX for new projects.** Both are async HTTP clients, but HTTPX provides a cleaner API with better ergonomics:[7][8][10]

| Aspect | HTTPX | AIOHTTP |
|--------|-------|---------|
| API Familiarity | Requests-like (easy transition) | Custom, lower-level |
| HTTP/2 Support | Native | Limited |
| Sync/Async | Both (AsyncClient and sync) | Async only |
| Performance (100 concurrent) | ~10.22 seconds | ~3.79 seconds faster |
| Type Hints | Full | Partial |
| WebSocket | No | Yes |

AIOHTTP is faster for extreme concurrency (1000+ simultaneous requests) but HTTPX suffices for CLI tools making 10-100 concurrent requests.[7][8][10] HTTPX's requests-compatible API reduces learning curve,[8] and native HTTP/2 support provides better performance than AIOHTTP's HTTP/1.1-only baseline.[8][10]

### Connection Pooling Configuration

HTTPX's `Limits` parameter controls connection behavior:

```python
limits = httpx.Limits(
    max_connections=100,           # Max total connections
    max_keepalive_connections=20,  # Max idle keep-alives
    keepalive_expiry=5.0           # Close idle after 5s
)

client = httpx.AsyncClient(limits=limits)
```

For CLI tools making burst requests (user runs `tree` command, which internally issues 5-10 concurrent API calls), `max_keepalive_connections=20` is excessive. The recommendation is `max_connections=10, max_keepalive_connections=4` to balance responsiveness with resource usage.[8][10]

### Timeout Configuration for Large Responses

Timeouts must account for large responses. A default 30-second timeout is too short for a 500MB chunked upload or a tree query returning 10,000 nodes:

```python
# Different timeouts for different operations
TIMEOUT_CONFIG = {
    'metadata': 5.0,              # Fast operations
    'search': 30.0,               # Normal queries
    'get_node': 60.0,             # May fetch large source
    'tree': 120.0,                # Tree can be slow
    'upload': 300.0,              # Large uploads
}

async def make_request(operation: str, url: str, **kwargs) -> httpx.Response:
    timeout = TIMEOUT_CONFIG.get(operation, 30.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.get(url, **kwargs)
```

The timeout should be a `Timeout` object distinguishing connect, read, write, and pool timeouts:[8]

```python
timeout = httpx.Timeout(
    10.0,  # connect timeout
    read=60.0  # read timeout (important for large responses)
)
```

### Rate Limiting and Quota Management

The server enforces rate limits via `X-RateLimit-*` headers. The client should respect these limits:

```python
class RateLimitManager:
    def __init__(self):
        self.limits = {}  # {endpoint: (remaining, reset_time)}
    
    async def handle_response(self, response: httpx.Response) -> None:
        """Update rate limit state from response headers"""
        
        remaining = response.headers.get('X-RateLimit-Remaining')
        reset = response.headers.get('X-RateLimit-Reset')
        
        if remaining and reset:
            endpoint = response.request.url.path
            self.limits[endpoint] = (int(remaining), int(reset))
    
    async def wait_if_needed(self, endpoint: str) -> None:
        """Sleep if approaching rate limit"""
        
        if endpoint not in self.limits:
            return
        
        remaining, reset_time = self.limits[endpoint]
        
        if remaining < 5:  # Threshold
            wait_seconds = reset_time - time.time()
            if wait_seconds > 0:
                print(f"⏸️  Rate limit approaching, waiting {wait_seconds:.0f}s")
                await asyncio.sleep(wait_seconds + 1)
```

The manager prevents hitting hard limits by proactively waiting when quota is low.[33][36]

### Proxy and Firewall Enterprise Compatibility

Enterprise networks often route traffic through HTTP proxies. HTTPX handles proxies transparently:[8]

```python
# Via environment variables
import os
os.environ['HTTP_PROXY'] = 'http://proxy.company.com:8080'
os.environ['HTTPS_PROXY'] = 'http://proxy.company.com:8080'

client = httpx.AsyncClient()  # Automatically uses proxy

# Or explicit configuration
client = httpx.AsyncClient(
    proxies='http://proxy.company.com:8080',
    verify='/path/to/company-ca.crt'  # Custom CA for MITM inspection
)
```

Self-signed certificates from proxy inspection require custom CA certificates:[37][40] The proxy decrypts HTTPS traffic, re-encrypts it with its own certificate, and presents that certificate to the client. The client must trust the company's CA certificate for TLS validation to pass.[37][40]

## Conclusion

Designing a dual-mode API for code intelligence tools requires balancing simplicity, performance, and flexibility. **REST APIs provide the optimal foundation for CLI and standard HTTP consumers**, offering universal support, transparent caching, and straightforward debugging. GraphQL complements REST for clients requiring complex queries with fine-grained field selection, while gRPC remains useful only for internal service-to-service communication.

The architecture should employ Clean Architecture principles with protocol-independent ABCs enabling seamless switching between local and remote implementations through dependency injection. This design achieves three critical properties: (1) protocol independence—business logic doesn't know whether queries are local or remote, (2) testability—unit tests inject mock implementations without infrastructure, and (3) operational flexibility—switching modes requires only configuration changes.

Large payload handling requires thoughtful attention to compression (gzip/brotli reducing traffic 70-85%), chunked uploads enabling parallelism and resilience, and streaming preventing memory exhaustion. Client-side caching using graph version hashes invalidates stale data automatically, while ETag validation and TTL-based caching reduce bandwidth. Offline fallback with local cache provides degraded service when the remote is unavailable, though semantic operations genuinely requiring remote computation should fail with helpful messages rather than degrade silently.

Authentication through API keys suits programmatic CLI access, while OAuth2 Device Flow handles MCP agents and non-interactive scenarios. Implementation requires careful attention to HTTPX configuration (connection pooling, timeouts), exponential backoff with jitter for resilience, and proxy/firewall compatibility in enterprise environments.

The most common failure modes—inadequate timeout configuration, connection pool saturation during bursts, missing rate limit handling, and insufficient distinction between cacheable and non-cacheable operations—are entirely preventable through deliberate architectural choices described throughout this report. Success requires treating the protocol as a first-class design concern, not an afterthought, and validating assumptions through load testing before production deployment.

Citations:
[1] https://camunda.com/blog/2023/06/rest-vs-graphql-vs-grpc-which-api-for-your-project/
[2] https://grpc.io/docs/languages/python/quickstart/
[3] https://www.ibm.com/think/topics/graphql-vs-rest-api
[4] https://www.baeldung.com/rest-vs-graphql-vs-grpc
[5] https://grpc.io/docs/languages/python/basics/
[6] https://www.coursera.org/articles/graphql-vs-rest-apis
[7] https://www.speakeasy.com/blog/python-http-clients-requests-vs-httpx-vs-aiohttp
[8] https://www.python-httpx.org
[9] https://breadcrumbscollector.tech/python-the-clean-architecture-in-2021/
[10] https://github.com/oxylabs/httpx-vs-requests-vs-aiohttp
[11] https://pypi.org/project/httpx/
[12] https://rothl.com/blog/clean-architecture-python-guide
[13] https://learn.microsoft.com/en-us/azure/architecture/best-practices/api-design
[14] https://embedded.gusto.com/blog/api-pagination/
[15] https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-gzip-compression-decompression.html
[16] https://stackoverflow.blog/2020/03/02/best-practices-for-rest-api-design/
[17] https://www.youtube.com/watch?v=zwDIN04lIpc
[18] https://oneuptime.com/blog/post/2026-01-30-build-api-compression-headers/view
[19] https://igventurelli.io/how-oauth2-differs-from-api-keys-understanding-secure-api-authentication/
[20] https://googleapis.github.io/google-api-python-client/docs/media.html
[21] https://www.jonoalderson.com/performance/http-caching/
[22] https://auth0.com/blog/why-migrate-from-api-keys-to-oauth2-access-tokens/
[23] https://github.com/mesuutt/python-chunked-upload-example
[24] https://oneuptime.com/blog/post/2026-01-30-browser-caching-configuration/view
[25] https://dev.to/meseta/explaining-typer-and-fastapi-dependency-injection-and-rolling-your-own-in-python-2bf2
[26] https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
[27] https://aws.amazon.com/compare/the-difference-between-grpc-and-rest/
[28] https://github.com/fastapi/typer/issues/80
[29] https://github.com/modelcontextprotocol/python-sdk/issues/934
[30] https://cloud.google.com/blog/products/api-management/understanding-grpc-openapi-and-rest-and-when-to-use-them
[31] https://docs.python.org/3/library/http.client.html
[32] https://community.jmp.com/t5/Discussions/HTTP-request-get-file-download-Operation-timed-out-after-60000/td-p/224384
[33] https://substack.thewebscraping.club/p/rate-limit-scraping-exponential-backoff
[34] https://dev.to/devfan/5-awesome-python-http-clients-1ldm
[35] https://community.grafana.com/t/how-best-to-tackle-tests-that-download-very-large-files/99351
[36] https://developer.vonage.com/en/blog/respect-api-rate-limits-with-a-backoff-dr
[37] https://snyk.io/blog/implementing-tls-ssl-python/
[38] https://oneuptime.com/blog/post/2026-01-25-http-proxy-aiohttp-python/view
[39] https://python-dependency-injector.ets-labs.org/providers/async.html
[40] https://docs.python.org/3/library/ssl.html
[41] https://docs.socket.dev/docs/socket-firewall-enterprise-proxy-client-setup
[42] https://oneuptime.com/blog/post/2026-02-03-python-dependency-injection/view
[43] https://simonwillison.net/2021/Jun/25/streaming-large-api-responses/
[44] https://daverog.wordpress.com/2012/11/13/rdf-tree-developer-friendly-graph-data/
[45] https://www.speakeasy.com/api-design/caching
[46] https://www.comtrade360.com/insights/file-streaming-rest-api-python/
[47] https://discuss.jsonapi.org/t/representing-tree-data-that-includes-resource-links/2029
[48] https://oneuptime.com/blog/post/2026-02-09-api-gateway-caching-strategies/view
[49] https://github.com/modelcontextprotocol/servers/issues/2216
[50] https://wundergraph.com/blog/four_ways_to_stitch_integrate_compose_and_federate_multiple_graphql_apis
