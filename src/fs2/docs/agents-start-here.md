# Getting Started with fs2

This guide helps AI agents (and humans) set up fs2 from scratch. If you're reading this via `fs2 docs agents-start-here` or MCP `docs_get("agents-start-here")`, you're already on the right track.

## What is fs2?

fs2 (Flowspace2) indexes your codebase into a searchable graph of code symbols. It provides:

- **Tree navigation**: Explore file → class → method hierarchies
- **Text/regex search**: Find code by exact match or pattern
- **Semantic search**: Search by meaning (requires LLM provider)
- **Smart content**: AI-generated summaries of code (requires LLM provider)
- **MCP server**: Native tool access for AI agents

## Setup Journey

### Phase 1: Orient

```bash
fs2 agents-start-here       # See what's set up, what to do next
fs2 docs                    # List all available documentation
```

### Phase 2: Initialize & Configure

```bash
fs2 init                           # Create .fs2/config.yaml
fs2 docs configuration-guide       # Read provider setup options (Azure, OpenAI)
# Edit .fs2/config.yaml if you want LLM providers
fs2 doctor                         # Validate configuration
fs2 doctor llm                     # Test live provider connections
```

### Phase 3: Scan & Connect MCP

```bash
fs2 scan                           # Index the codebase
fs2 docs mcp-server-guide          # Read MCP setup instructions
# Configure your MCP client (e.g., claude mcp add fs2 -- fs2 mcp)
```

## Quick Reference

| Command | Purpose |
|---------|---------|
| `fs2 agents-start-here` | Orientation and next steps |
| `fs2 docs` | List all documentation |
| `fs2 docs <id>` | Read a specific document |
| `fs2 docs --json` | Machine-readable doc listing |
| `fs2 init` | Create config file |
| `fs2 doctor` | Validate configuration |
| `fs2 scan` | Index codebase |
| `fs2 mcp` | Start MCP server |

## After MCP is Connected

Once MCP is running, read `fs2 docs agents` for tool usage guidance (tree, search, get_node, docs_list, docs_get).
