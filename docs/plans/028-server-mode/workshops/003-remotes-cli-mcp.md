# Workshop: How Remotes Work in CLI and MCP Server

**Type**: CLI Flow + API Contract
**Plan**: 028-server-mode
**Spec**: [server-mode-spec.md](../server-mode-spec.md)
**Created**: 2026-03-06
**Status**: Draft

**Related Documents**:
- [Workshop 001: Database Schema](001-database-schema.md)
- [Workshop 002: Prototype Validation](002-prototype-validation.md)
- [External Research: Remote CLI Protocol](../external-research/remote-cli-protocol.md)

**Domain Context**:
- **Primary Domain**: cli-presentation (modify), configuration (modify)
- **Related Domains**: server (consume via HTTP), graph-storage (RemoteGraphStore)

---

## Purpose

Design how `fs2` CLI commands and MCP tools transparently query remote servers. Defines the named remote registry (config), inline URL support, multi-remote search, and how `resolve_graph_from_context()` changes to support remote graph resolution. This workshop locks the CLI contract before Phase 5 implementation.

## Key Questions Addressed

- How does a user configure named remotes?
- How does `--remote` flag interact with `--graph-name`?
- How does multi-remote search work (search across multiple servers)?
- How does the MCP server switch between local and remote?
- How does `resolve_graph_from_context()` change?
- What happens when a remote is unreachable?

---

## Overview

fs2 remotes are named server connections stored in config, similar to git remotes. Users can also pass raw URLs inline. The `--remote` flag is the single entry point — if the value starts with `http://` or `https://`, it's treated as a URL; otherwise, it's looked up in the config registry.

## Command Summary

| Command | Purpose |
|---------|---------|
| `fs2 tree --remote work --graph repo-name` | Query remote server's graph |
| `fs2 search --remote work "pattern"` | Search across all graphs on remote |
| `fs2 search --remote work,oss "pattern"` | Search across multiple remotes |
| `fs2 search --remote http://localhost:8000 "pattern"` | Ad-hoc URL remote |
| `fs2 list-graphs --remote work` | List graphs available on remote |
| `fs2 list-remotes` | Show all configured remotes |
| `fs2 get-node --remote work --graph repo "node_id"` | Fetch node from remote |
| `fs2 mcp --remote work` | Start MCP server backed by remote |

---

## Remote Configuration

### Config Model: `RemotesConfig`

```yaml
# ~/.config/fs2/config.yaml (user-level — available everywhere)
remotes:
  servers:
    - name: "work"
      url: "https://fs2.mycompany.com"
      api_key: "fs2_abc123..."  # Optional — for future auth
      description: "Company fs2 server"

    - name: "oss"
      url: "https://community-fs2.dev"
      description: "Open source community graphs"

    - name: "local"
      url: "http://localhost:8000"
      description: "Local dev server"
```

```yaml
# .fs2/config.yaml (project-level — can add project-specific remotes)
remotes:
  servers:
    - name: "staging"
      url: "https://staging-fs2.mycompany.com"
      api_key: "fs2_staging..."
```

**Merge behavior**: User + project remotes are **concatenated** (same as `OtherGraphsConfig.graphs`). Project remotes override user remotes if same name.

### Pydantic Models

```python
class RemoteServer(BaseModel):
    """A single remote fs2 server."""
    name: str              # Unique identifier
    url: str               # Base URL (must start with http:// or https://)
    api_key: str | None = None  # Optional auth key
    description: str | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("Remote URL must start with http:// or https://")
        return v.rstrip("/")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if v == "local":
            raise ValueError("'local' is reserved for the project graph")
        return v


class RemotesConfig(BaseModel):
    """Configuration for remote fs2 servers."""
    __config_path__: ClassVar[str] = "remotes"

    servers: list[RemoteServer] = []
```

### Environment Variable Override

```bash
# Single remote via env (quick setup, no config file needed)
FS2_REMOTES__SERVERS__0__NAME=work
FS2_REMOTES__SERVERS__0__URL=https://fs2.mycompany.com
FS2_REMOTES__SERVERS__0__API_KEY=fs2_abc123
```

---

## The `--remote` Flag

### Resolution Logic

```
--remote value received
    │
    ├─ starts with http:// or https://
    │   └─ Treat as inline URL → create ephemeral RemoteServer(name="_inline", url=value)
    │
    ├─ contains ","
    │   └─ Split by comma → resolve each name → multi-remote mode
    │
    └─ single name
        └─ Look up in RemotesConfig.servers by name
            ├─ Found → use that RemoteServer
            └─ Not found → error: "Unknown remote 'xxx'. Run 'fs2 list-remotes' to see available remotes."
```

### Flag Placement (Global Option)

```python
# src/fs2/cli/main.py
@app.callback()
def main(
    ctx: typer.Context,
    graph_file: str | None = None,
    graph_name: str | None = None,
    remote: str | None = typer.Option(
        None, "--remote", "-r",
        help="Remote server name or URL. Comma-separated for multi-remote.",
        envvar="FS2_REMOTE",
    ),
    version: bool = False,
):
    ctx.obj = CLIContext(
        graph_file=graph_file,
        graph_name=graph_name,
        remote=remote,  # NEW
    )
```

### Interaction Matrix

| `--remote` | `--graph-name` | Behavior |
|------------|----------------|----------|
| ❌ | ❌ | Local default graph (unchanged) |
| ❌ | `lib` | Local named graph (unchanged, via OtherGraphsConfig) |
| `work` | ❌ | All graphs on `work` remote |
| `work` | `repo-x` | Specific graph `repo-x` on `work` remote |
| `work,oss` | ❌ | Search all graphs across both remotes |
| `work,oss` | `repo-x` | Search `repo-x` on whichever remote has it |
| `http://...` | ❌ | All graphs on inline URL |
| `http://...` | `repo-x` | Specific graph on inline URL |

---

## CLI Command Examples

### `fs2 list-remotes`

```
$ fs2 list-remotes

  Name     URL                              Description
  ────     ───                              ───────────
  work     https://fs2.mycompany.com        Company fs2 server
  oss      https://community-fs2.dev        Open source community graphs
  local    http://localhost:8000            Local dev server

  3 remotes configured (from ~/.config/fs2/config.yaml)
```

### `fs2 list-graphs --remote work`

```
$ fs2 list-graphs --remote work

  Remote: work (https://fs2.mycompany.com)

  Name              Nodes   Embedding Model              Status   Updated
  ────              ─────   ───────────────              ──────   ───────
  api-gateway       12,841  text-embedding-3-small       ready    2h ago
  shared-lib        3,204   text-embedding-3-small       ready    1d ago
  frontend          45,102  text-embedding-3-small       ready    3h ago

  3 graphs available
```

### `fs2 search --remote work "authentication"`

```
$ fs2 search --remote work "authentication"

  Remote: work (https://fs2.mycompany.com)
  Searching all 3 graphs...

  ── api-gateway (12,841 nodes) ──────────────────────────────────

  1. method:src/auth/jwt_handler.py:JWTHandler.validate  [0.92]
     Validates JWT tokens and extracts claims...

  2. class:src/auth/middleware.py:AuthMiddleware  [0.89]
     FastAPI middleware that enforces authentication...

  ── shared-lib (3,204 nodes) ────────────────────────────────────

  3. method:src/auth/base.py:BaseAuthProvider.authenticate  [0.87]
     Abstract authentication provider...

  3 results across 2 graphs (47ms)
```

### `fs2 search --remote work --graph api-gateway "authentication"`

```
$ fs2 search --remote work --graph api-gateway "authentication"

  Remote: work (https://fs2.mycompany.com)
  Graph: api-gateway

  1. method:src/auth/jwt_handler.py:JWTHandler.validate  [0.92]
     ...

  2 results (23ms)
```

### `fs2 search --remote work,oss "error handling"`

```
$ fs2 search --remote work,oss "error handling"

  Searching 2 remotes (6 graphs total)...

  ── work / api-gateway ──────────────────────────────────────────

  1. class:src/errors/handler.py:GlobalErrorHandler  [0.94]
     ...

  ── oss / python-patterns ───────────────────────────────────────

  2. method:src/patterns/error_handling.py:retry_with_backoff  [0.88]
     ...

  5 results across 2 remotes (89ms)
```

### Error: Remote Unreachable

```
$ fs2 search --remote work "pattern"

  ✗ Remote 'work' unreachable at https://fs2.mycompany.com
    Connection refused. Check the URL or server status.
    Run 'fs2 list-remotes' to see configured remotes.
```

### Error: Unknown Remote Name

```
$ fs2 search --remote typo "pattern"

  ✗ Unknown remote 'typo'.
    Available remotes: work, oss, local
    Run 'fs2 list-remotes' to see configured remotes.
    Tip: Use a URL directly: --remote http://your-server:8000
```

---

## `resolve_graph_from_context()` Changes

The existing function returns `(ConfigurationService, GraphStore)`. For remote mode, it returns a `RemoteGraphStore` (HTTP client implementing GraphStore).

```python
def resolve_graph_from_context(
    ctx: typer.Context,
) -> tuple[ConfigurationService, GraphStore]:
    """Resolve graph source: local file, named graph, or remote server."""

    cli_ctx: CLIContext = ctx.obj
    config = get_config()

    # Priority 1: Remote mode
    if cli_ctx.remote:
        remotes = resolve_remotes(cli_ctx.remote, config)
        graph_name = cli_ctx.graph_name  # Optional filter

        if len(remotes) == 1:
            store = RemoteGraphStore(
                base_url=remotes[0].url,
                api_key=remotes[0].api_key,
                graph_name=graph_name,
            )
        else:
            # Multi-remote: composite store that fans out queries
            store = MultiRemoteGraphStore(
                remotes=remotes,
                graph_name=graph_name,
            )
        return config, store

    # Priority 2: Explicit graph file (unchanged)
    if cli_ctx.graph_file:
        ...

    # Priority 3: Named graph (unchanged)
    if cli_ctx.graph_name:
        ...

    # Priority 4: Default graph (unchanged)
    ...
```

### `resolve_remotes()` Helper

```python
def resolve_remotes(
    remote_str: str, config: ConfigurationService
) -> list[RemoteServer]:
    """Resolve --remote flag to list of RemoteServer objects."""
    remotes_config = config.get(RemotesConfig)
    servers = remotes_config.servers if remotes_config else []

    parts = [p.strip() for p in remote_str.split(",")]
    result = []

    for part in parts:
        if part.startswith(("http://", "https://")):
            # Inline URL
            result.append(RemoteServer(name="_inline", url=part))
        else:
            # Named lookup
            match = next((s for s in servers if s.name == part), None)
            if not match:
                names = ", ".join(s.name for s in servers) or "(none configured)"
                raise SystemExit(
                    f"Unknown remote '{part}'. Available: {names}\n"
                    f"Tip: Use a URL directly: --remote http://your-server:8000"
                )
            result.append(match)

    return result
```

---

## RemoteGraphStore (HTTP Client)

Implements `GraphStore` ABC by making HTTP calls to the server's REST API.

```python
class RemoteGraphStore(GraphStore):
    """GraphStore backed by a remote fs2 server via HTTP."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        graph_name: str | None = None,
    ):
        self._base_url = base_url
        self._api_key = api_key
        self._graph_name = graph_name
        self._client = httpx.Client(
            base_url=base_url,
            headers=self._auth_headers(),
            timeout=30.0,
        )

    def _auth_headers(self) -> dict:
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return {}

    def get_node(self, node_id: str) -> CodeNode | None:
        """GET /api/v1/graphs/{name}/nodes/{node_id}"""
        resp = self._client.get(
            f"/api/v1/graphs/{self._graph_name}/nodes/{node_id}"
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return CodeNode(**resp.json())

    def get_children(self, node_id: str) -> list[CodeNode]:
        """GET /api/v1/graphs/{name}/tree?pattern={node_id}&max_depth=1"""
        ...

    def get_all_nodes(self) -> list[CodeNode]:
        """GET /api/v1/graphs/{name}/nodes (paginated)"""
        ...

    def save(self, path) -> None:
        """No-op — remote is read-only from CLI perspective."""
        pass

    def load(self, path) -> None:
        """No-op — remote is always-on."""
        pass
```

### MultiRemoteGraphStore

For comma-separated remotes, fans out queries:

```python
class MultiRemoteGraphStore(GraphStore):
    """Composite store that queries multiple remotes."""

    def __init__(self, remotes: list[RemoteServer], graph_name: str | None):
        self._stores = [
            RemoteGraphStore(r.url, r.api_key, graph_name)
            for r in remotes
        ]

    def get_all_nodes(self) -> list[CodeNode]:
        """Aggregate nodes from all remotes."""
        all_nodes = []
        for store in self._stores:
            all_nodes.extend(store.get_all_nodes())
        return all_nodes
```

---

## MCP Server Remote Mode

### Configuration

```bash
# Start MCP server backed by a remote
fs2 mcp --remote work

# Start MCP server backed by multiple remotes
fs2 mcp --remote work,oss
```

### How It Works

The MCP server's tools (`tree`, `search`, `get_node`, `list_graphs`) already go through `GraphStore`. When `--remote` is set, the MCP server wires a `RemoteGraphStore` instead of `NetworkXGraphStore`.

```python
# src/fs2/mcp/server.py — modified initialization
def create_mcp_graph_store(remote: str | None = None) -> GraphStore:
    if remote:
        config = get_config()
        remotes = resolve_remotes(remote, config)
        if len(remotes) == 1:
            return RemoteGraphStore(remotes[0].url, remotes[0].api_key)
        return MultiRemoteGraphStore(remotes)
    else:
        return get_graph_store()  # Local (unchanged)
```

### MCP Tool Behavior

| MCP Tool | Local Mode | Remote Mode |
|----------|-----------|-------------|
| `tree(pattern)` | NetworkXGraphStore | RemoteGraphStore → `GET /api/v1/graphs/{name}/tree` |
| `search(pattern)` | SearchService (in-memory) | RemoteGraphStore → `GET /api/v1/search` |
| `get_node(id)` | NetworkXGraphStore | RemoteGraphStore → `GET /api/v1/graphs/{name}/nodes/{id}` |
| `list_graphs()` | GraphService (local files) | RemoteGraphStore → `GET /api/v1/graphs` |

AI agents using MCP tools see **identical response formats** regardless of mode (AC13).

### MCP Config for Claude/AI

```json
{
  "mcpServers": {
    "fs2-local": {
      "command": "fs2",
      "args": ["mcp"]
    },
    "fs2-work": {
      "command": "fs2",
      "args": ["mcp", "--remote", "work"]
    }
  }
}
```

This lets an AI agent have **both local and remote** available simultaneously — different MCP server instances.

---

## API Endpoints (Server Side)

These are what `RemoteGraphStore` calls. Phase 4 builds these.

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/graphs` | List all graphs |
| GET | `/api/v1/graphs/{name}/tree?pattern=&max_depth=` | Tree query |
| GET | `/api/v1/graphs/{name}/nodes/{node_id}` | Get single node |
| GET | `/api/v1/search?pattern=&mode=&graph=&limit=` | Multi-graph search |
| GET | `/api/v1/graphs/{name}/nodes` | All nodes (paginated) |

### Response Format Parity

Server responses use the **same JSON shape** as local CLI output. Example for `get_node`:

```json
{
  "node_id": "class:src/auth.py:AuthService",
  "category": "type",
  "ts_kind": "class_definition",
  "name": "AuthService",
  "qualified_name": "AuthService",
  "start_line": 15,
  "end_line": 89,
  "content": "class AuthService:\n    ...",
  "smart_content": "AuthService handles JWT-based auth...",
  "language": "python",
  "graph_name": "api-gateway"
}
```

---

## Error Handling

| Scenario | HTTP Status | CLI Behavior |
|----------|-------------|-------------|
| Remote unreachable | Connection error | `✗ Remote 'work' unreachable at <url>` + exit 1 |
| Remote returns 500 | 500 | `✗ Server error on 'work': <detail>` + exit 1 |
| Graph not found on remote | 404 | `✗ Graph 'xxx' not found on remote 'work'` + exit 1 |
| Invalid API key | 401 | `✗ Authentication failed for 'work'. Check api_key in config.` + exit 1 |
| Timeout (>30s) | Timeout | `✗ Request timed out for 'work'. Try again or check server.` + exit 1 |
| Partial failure (multi) | Mixed | Show results from successful remotes, warn about failed ones |

### Partial Failure in Multi-Remote

```
$ fs2 search --remote work,oss "pattern"

  ⚠ Remote 'oss' unreachable — skipping (https://community-fs2.dev)

  ── work / api-gateway ──────────────────────────────────────────

  1. class:src/auth.py:AuthService  [0.94]
     ...

  2 results from 1 of 2 remotes (1 unreachable)
```

---

## Locked Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| R1 | Named remotes in config, like git remotes | Familiar UX, persistent, shareable |
| R2 | Inline URL also supported (`--remote http://...`) | Ad-hoc usage without config changes |
| R3 | URL detection heuristic: starts with `http://`/`https://` = URL, else = name | Simple, unambiguous |
| R4 | Comma-separated for multi-remote | Concise, familiar from `--graph name1,name2` pattern |
| R5 | `RemotesConfig` at path `remotes` in YAML | Consistent with other config models |
| R6 | User + project remotes concatenated (project wins on name collision) | Same merge as `OtherGraphsConfig` |
| R7 | MCP server supports `--remote` flag | AI agents get remote access via separate MCP instances |
| R8 | Partial failure in multi-remote: warn and continue | Don't fail entire search because one remote is down |
| R9 | `RemoteGraphStore` uses sync `httpx.Client` (CLI is sync) | Matches existing CLI sync patterns |

## Open Questions

### Q1: Should `fs2 search` without `--graph` search ALL graphs on the remote?

**RESOLVED**: Yes — matches the local behavior where search scans the current graph. On a remote, "current" = all accessible graphs. Use `--graph name` to narrow.

### Q2: Should remotes support graph name prefixing (`work/repo-name`)?

**OPEN**: Could allow `fs2 get-node work/api-gateway "node_id"` instead of `--remote work --graph api-gateway`. Deferred — add if user feedback demands it.

### Q3: Should there be a `fs2 remote add/remove` command?

**OPEN**: Git has `git remote add`. We could add `fs2 remote add work https://...` as sugar for editing config YAML. Low priority — config file is fine for v1.
