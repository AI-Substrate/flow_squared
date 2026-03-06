# Remote Server Guide

Configure and use remote fs2 servers. Query code graphs hosted on remote servers using the same CLI commands and MCP tools you use locally.

## Overview

By default, fs2 queries local graph files (`.fs2/graph.pickle`). Remote mode lets you:

- **Query team servers** hosting shared code graphs
- **Search across organizations** with multi-remote fan-out
- **Mix local and remote** graphs in MCP mode seamlessly
- **Use inline URLs** for quick one-off queries without config

## Configuring Named Remotes

Named remotes are configured in YAML config files. Both user-level and project-level configs are supported — servers from both are merged (not replaced).

### User-level config (`~/.config/fs2/config.yaml`)

Shared across all projects:

```yaml
remotes:
  servers:
    - name: "work"
      url: "https://fs2.internal.company.com"
      api_key: ${FS2_WORK_API_KEY}
      description: "Internal team server"
    - name: "oss"
      url: "https://fs2-public.example.com"
      description: "Open source graphs"
```

### Project-level config (`.fs2/config.yaml`)

Specific to a single project:

```yaml
remotes:
  servers:
    - name: "staging"
      url: "http://localhost:8000"
      description: "Local dev server"
```

### Config Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique identifier (e.g., "work", "oss"). Used with `--remote`. |
| `url` | Yes | Base URL. Must start with `http://` or `https://`. |
| `api_key` | No | API key for Bearer authentication. Supports `${ENV_VAR}` expansion. |
| `description` | No | Human-readable description shown in `list-remotes`. |

## The `--remote` Flag

Add `--remote` to any query command to route it to a remote server:

```bash
# Named remote (from config)
fs2 tree --remote work --graph my-repo

# Inline URL (no config needed)
fs2 tree --remote http://localhost:8000 --graph my-repo

# Multiple remotes (comma-separated, fan-out search)
fs2 search --remote work,oss "authentication"
```

### Environment Variable

Set `FS2_REMOTE` to avoid passing `--remote` on every command:

```bash
export FS2_REMOTE=work
fs2 tree --graph my-repo          # Uses "work" remote
fs2 search "pattern"              # Uses "work" remote
```

The `--remote` flag takes precedence over `FS2_REMOTE` if both are set.

### Inline URL Support

Any value starting with `http://` or `https://` is treated as an inline URL — no config entry needed:

```bash
fs2 tree --remote http://localhost:8000 --graph my-repo
fs2 search --remote https://fs2.example.com "pattern"
```

### Multi-Remote Comma Syntax

Comma-separated values fan out queries to multiple servers in parallel:

```bash
# Search across two named remotes
fs2 search --remote work,oss "authentication"

# Mix named remotes and inline URLs
fs2 search --remote work,http://localhost:8000 "pattern"
```

Multi-remote search returns merged results from all servers. Each result includes the server name for attribution.

## Commands

### `list-remotes`

Show all configured remotes (does NOT contact servers):

```bash
$ fs2 list-remotes
┌──────────┬───────────────────────────────────┬──────┬─────────────────────┐
│ Name     │ URL                               │ Auth │ Description         │
├──────────┼───────────────────────────────────┼──────┼─────────────────────┤
│ work     │ https://fs2.internal.company.com  │  ✓   │ Internal team server│
│ oss      │ https://fs2-public.example.com    │  —   │ Open source graphs  │
└──────────┴───────────────────────────────────┴──────┴─────────────────────┘
Total: 2 remote(s)

$ fs2 list-remotes --json    # Machine-readable output
```

### `list-graphs --remote`

List graphs available on a remote server (contacts the server):

```bash
$ fs2 list-graphs --remote work
┌─────────────┬────────┬──────────┬─────────────┐
│ Name        │ Nodes  │ Status   │ Description │
├─────────────┼────────┼──────────┼─────────────┤
│ backend-api │ 12,345 │ ready    │ Main API    │
│ shared-lib  │  3,200 │ ready    │ Common utils│
└─────────────┴────────┴──────────┴─────────────┘
```

### `tree --remote`

Query the tree structure of a remote graph:

```bash
# List top-level files
fs2 tree --remote work --graph backend-api

# Filter by pattern
fs2 tree --remote work --graph backend-api --pattern "src/auth/"

# With depth limit
fs2 tree --remote work --graph backend-api --depth 2
```

### `search --remote`

Search across remote graphs:

```bash
# Text search on a specific graph
fs2 search --remote work --graph backend-api "UserService"

# Semantic search across all graphs on a remote
fs2 search --remote work "authentication flow" --mode semantic

# Regex search across multiple remotes
fs2 search --remote work,oss "class.*Controller" --mode regex

# Multi-graph on a single remote
fs2 search --remote work --graph backend-api,shared-lib "validate"
```

### `get-node --remote`

Retrieve full source code for a specific node:

```bash
fs2 get-node --remote work --graph backend-api \
  "class:src/auth/service.py:AuthService"
```

## MCP Mixed Mode

When remotes are configured, the MCP server automatically discovers remote graphs and makes them available alongside local graphs. AI agents don't need to know whether a graph is local or remote — `graph_name` routes automatically.

### How It Works

1. MCP server starts and reads `RemotesConfig`
2. For each configured remote, it queries `list-graphs` to discover available graphs
3. Remote graphs are prefixed with the remote name: `work/backend-api`, `work/shared-lib`
4. Local graphs keep their existing names: `default`, `shared-lib`
5. When a tool call specifies `graph_name="work/backend-api"`, MCP routes to the remote
6. When `graph_name="default"` or `None`, MCP uses the local graph

### MCP Tool Examples

```python
# List all graphs (local + remote)
list_graphs()
# Returns: default (local), work/backend-api (remote), work/shared-lib (remote)

# Query a remote graph
tree(pattern="src/", graph_name="work/backend-api")

# Search across a remote graph
search(pattern="auth", graph_name="work/backend-api")

# Get a node from a remote graph
get_node(node_id="class:src/auth.py:Auth", graph_name="work/backend-api")
```

### No Configuration Needed by Agents

AI agents call the same MCP tools with the same parameters. The only difference is the `graph_name` value — remote graphs use the `remote_name/graph_name` format. The `list_graphs` tool shows all available graphs so agents can discover what's available.

## Error Troubleshooting

### Connection Refused

```
RemoteClientError: Connection refused to "work" (https://fs2.internal.company.com)
```

**Cause**: Server is not running or unreachable.
**Fix**:
1. Verify the server is running: `curl https://fs2.internal.company.com/health`
2. Check the URL in your config: `fs2 list-remotes`
3. Check network/firewall/VPN access

### Authentication Failed

```
RemoteClientError: 401 Unauthorized from "work"
```

**Cause**: Missing or invalid API key.
**Fix**:
1. Verify your API key is set: check `api_key` in config or `${FS2_WORK_API_KEY}` env var
2. Check if the key has expired with your server admin
3. Regenerate the key from the server dashboard

### Request Timeout

```
RemoteClientError: Request timed out after 30.0s to "work"
```

**Cause**: Server is slow or overloaded.
**Fix**:
1. Check server health: `curl https://fs2.internal.company.com/health`
2. Try a simpler query to verify connectivity
3. Contact the server operator if the issue persists

### Remote Not Found

```
Error: Remote "xyz" not found in config.
Configured remotes: work, oss
Add it to ~/.config/fs2/config.yaml or use an inline URL.
```

**Cause**: The named remote doesn't exist in any config file.
**Fix**:
1. Check spelling: `fs2 list-remotes`
2. Add it to `~/.config/fs2/config.yaml` or `.fs2/config.yaml`
3. Or use an inline URL: `--remote http://the-server-url`

### Graph Not Found on Remote

```
RemoteClientError: Graph "my-repo" not found on "work"
```

**Cause**: The graph hasn't been uploaded to that server.
**Fix**:
1. List available graphs: `fs2 list-graphs --remote work`
2. Upload the graph through the server dashboard
3. Check the graph name spelling (names are case-sensitive)

## Quick Reference

| Action | Command |
|--------|---------|
| List configured remotes | `fs2 list-remotes` |
| List remote graphs | `fs2 list-graphs --remote work` |
| Query remote tree | `fs2 tree --remote work --graph repo` |
| Search remote | `fs2 search --remote work "pattern"` |
| Get remote node | `fs2 get-node --remote work --graph repo "node_id"` |
| Multi-remote search | `fs2 search --remote work,oss "pattern"` |
| Inline URL | `fs2 tree --remote http://localhost:8000 --graph repo` |
| Env var | `export FS2_REMOTE=work` |
