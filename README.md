# Flowspace2 (fs2)

fs2 parses your codebase into individual code elements — functions, classes, methods, types — using tree-sitter grammars for 55+ languages. Each element can be enriched with an AI-generated summary and vector embeddings, producing a searchable code graph with cross-file relationship tracking. Query by text, regex, or meaning through the CLI, or expose the graph to AI coding agents as an MCP server.

## Key Capabilities

**Structural parsing** — fs2 uses tree-sitter to parse source files into individual code elements: functions, classes, methods, types, and blocks. Each element becomes a node in a directed graph with its source code, signature, qualified name, and line position. This works across 55+ languages with no per-language configuration.

**AI-generated summaries** — Each node can be summarized by an LLM in a concise description of what it does. These summaries power semantic search — you can search for "JWT token validation" and find the right function even if the code never uses those words.

**Semantic search** — Search by meaning, not just text. fs2 embeds both raw code and AI summaries, then searches both to find the best match. Text and regex modes are also available for exact pattern matching.

**Cross-file relationships** — SCIP-based import and call resolution maps references across files. See what calls a function, what it depends on, and how modules connect. Supports Python, TypeScript, JavaScript, Go, and C#.

**Multi-repository** — Configure multiple codebases as named graphs and query across all of them from one installation. Useful for monorepos, shared libraries, or legacy systems spanning many repositories.

## How It Works

fs2 processes your code through a six-stage pipeline:

1. **Scan** — Discovers source files, respecting `.gitignore` and configurable scan paths
2. **Parse** — tree-sitter breaks each file into individual code elements (nodes)
3. **Relate** — SCIP resolves cross-file imports, calls, and type references into graph edges
4. **Summarize** — An LLM generates a concise summary for each node
5. **Embed** — Vector embeddings are created for both raw code and summaries
6. **Store** — The graph is persisted to `.fs2/graph.pickle`

The graph is then queryable via CLI commands (`fs2 search`, `fs2 tree`, `fs2 get-node`) or through MCP tools for AI coding agents. Steps 3–5 are optional and can be disabled individually.

## When to Use fs2

fs2 is not a replacement for grep or ripgrep — those are fast text search tools and they're great at what they do. fs2 is for when you need to understand code structure, not just find text.

| Need | Tool |
|------|------|
| Find a string in files | `grep` / `ripgrep` |
| Find a function by name or meaning | `fs2 search` |
| Understand what a class does | `fs2 get-node` (includes AI summary) |
| Explore codebase structure | `fs2 tree` |
| Navigate cross-file dependencies | `fs2 get-node` (includes relationships) |
| Search across multiple repositories | `fs2 search --graph-name` |
| Give an AI agent structured code context | `fs2 mcp` ([MCP](https://modelcontextprotocol.io/) is the protocol AI agents use to access external tools) |

### Example: Semantic Search

```bash
# Find code by meaning, not just text
$ fs2 search "validates user authentication tokens" --mode semantic
```

Illustrative output:
```
callable:src/auth/jwt.py:JWTValidator.validate_token    (score: 0.87)
  → "Validates a JWT by checking its signature, expiration, and claims
     against the issuer configuration."

callable:src/middleware/auth.py:require_auth              (score: 0.72)
  → "Decorator that extracts the Bearer token from the request header
     and validates it before allowing access."
```

Neither function contains the phrase "authentication tokens" — fs2 found them through their AI-generated summaries.

## Installation

### Prerequisites

fs2 requires [uv](https://docs.astral.sh/uv/), the fast Python package manager:

```bash
# Install uv (macOS/Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with Homebrew
brew install uv
```

### Option 1: Zero-Install with uvx (Recommended)

Run fs2 directly from GitHub with no local installation:

```bash
# Run any fs2 command directly
uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 --help
uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 init
uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 scan
```

> **Note**: First run builds from source (~30-60 seconds). Subsequent runs use cache and are near-instant. Don't Ctrl+C during the first run!

### Option 2: Permanent Install (Faster Daily Use)

After trying fs2 with uvx, install it permanently for instant startup:

```bash
# Self-bootstrapping install (run once)
uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 install

# Now use directly (no uvx prefix needed)
fs2 --help
fs2 --version    # Shows: fs2 v0.1.0 (abc1234)
```

**Upgrade to latest**:
```bash
fs2 upgrade      # Or: fs2 install (same idempotent behavior)
```

### Verify Installation

```bash
fs2 --version
# Output: fs2 v0.1.0 (abc1234)
#         └─ version  └─ git commit (if installed from git)
```

### Installation Methods Summary

| Method | Command | Best For |
|--------|---------|----------|
| **Zero-install** | `uvx --from git+...github...flow_squared fs2` | Trying it out, CI/CD |
| **Permanent** | `fs2 install` (after uvx) | Daily use |
| **Pinned version** | `uvx --from git+...@abc1234 fs2` | Reproducible builds |

See [Developer Setup](#developer-setup) below for contributing.

## Guides

| Guide | Description |
|-------|-------------|
| [CLI Reference](docs/how/user/cli.md) | All commands, options, and output formats |
| [Scanning](docs/how/user/scanning.md) | Build the code graph, configure paths, troubleshoot |
| [MCP Server](docs/how/user/mcp-server-guide.md) | Connect Claude, Copilot, and other AI agents |
| [Configuration Guide](docs/how/user/configuration-guide.md) | LLM, embeddings, secrets, and all config options |
| [Multi-Graph](docs/how/user/multi-graphs.md) | Query multiple codebases from one installation |
| [Agent Integration](docs/how/user/AGENTS.md) | How AI agents should use fs2 tools effectively |

## Quick Diagnostics

If you're having configuration issues, use the doctor command:

```bash
fs2 doctor
```

This displays:
- All config file locations (found/not found)
- LLM and embedding provider status
- Unresolved `${VAR}` placeholders
- YAML syntax and schema validation errors
- Actionable suggestions with documentation links

Example output:
```
╭─ fs2 Configuration Health Check ─╮
│ Current Directory: /my-project   │
╰──────────────────────────────────╯

📁 Configuration Files:
  ✓ ~/.config/fs2/config.yaml
  ✗ ./.fs2/secrets.env (not found)

🔌 Provider Status:
  ✓ LLM: azure (configured)
  ✗ Embeddings: NOT CONFIGURED
    → https://github.com/.../configuration-guide.md

💡 Suggestions:
  • Set AZURE_EMBEDDING_API_KEY to enable embeddings
```

## MCP Server (AI Agent Integration)

Start the MCP server for Claude Code, Claude Desktop, GitHub Copilot, or other MCP-compatible clients:

```bash
fs2 mcp
```

**Prerequisites**: Run `fs2 init` then `fs2 scan` first to index your codebase.

### Claude Code

```bash
# Add fs2 MCP server (available across all projects)
claude mcp add fs2 --scope user -- fs2 mcp

# Or with uvx (no permanent install needed)
claude mcp add fs2 --scope user -- uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 mcp

# Verify configuration
claude mcp list
```

### Claude Desktop

Config location: `~/.config/claude/claude_desktop_config.json` (Linux/macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows)

**With permanent install**:
```json
{
  "mcpServers": {
    "fs2": {
      "command": "fs2",
      "args": ["mcp"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

**With uvx (zero-install)**:
```json
{
  "mcpServers": {
    "fs2": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/AI-Substrate/flow_squared", "fs2", "mcp"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

**Pinned to specific commit** (for reproducibility):
```json
{
  "mcpServers": {
    "fs2": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/AI-Substrate/flow_squared@abc1234", "fs2", "mcp"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

### GitHub Copilot (VS Code)

Create `.vscode/mcp.json` in your project:

```json
{
  "servers": {
    "fs2": {
      "command": "fs2",
      "args": ["mcp"]
    }
  }
}
```

Or with uvx:
```json
{
  "servers": {
    "fs2": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/AI-Substrate/flow_squared", "fs2", "mcp"]
    }
  }
}
```

### Available Tools

| Tool | Purpose |
|------|---------|
| `tree` | Explore codebase structure as a hierarchical tree |
| `get_node` | Retrieve complete source code for a specific node |
| `search` | Find code by text, regex, or semantic meaning |
| `docs_list` | Browse available documentation with optional filtering |
| `docs_get` | Retrieve full document content by ID |

### Documentation Tools

The MCP server includes self-service documentation tools for AI agents:

**Browse documentation**:
```python
# List all documents
docs_list()
# Returns: {"docs": [...], "count": 2}

# Filter by category
docs_list(category="how-to")

# Filter by tags (OR logic - matches ANY tag)
docs_list(tags=["config", "setup"])
```

**Get full document**:
```python
docs_get(id="agents")
# Returns: {"id": "agents", "title": "...", "content": "...", "metadata": {...}}
```

Available documents:
- `agents` - Best practices for AI agents using fs2 tools
- `configuration-guide` - Comprehensive configuration reference

See [Writing New Curated Documentation](docs/how/dev/write-new-content-guide.md) for adding new documents.

See [MCP Server Guide](docs/how/user/mcp-server-guide.md) for detailed documentation.

## Scanning

Scan your codebase to build a queryable code graph.

> **⚠️ Configure LLM & Embeddings First**: For full functionality (smart content summaries and semantic search), set up your API credentials before scanning. See the [Configuration Guide](docs/how/user/configuration-guide.md) for complete setup instructions.
>
> **Quick setup**:
> ```bash
> cp .fs2/config.yaml.example .fs2/config.yaml
> # Edit .fs2/config.yaml with your Azure/OpenAI credentials
> # Or set: FS2_AZURE__EMBEDDING__API_KEY, FS2_AZURE__EMBEDDING__ENDPOINT
> ```
>
> Without configuration, use `fs2 scan --no-embeddings` for basic scanning (no semantic search).

```bash
# Initialize config (first time)
fs2 init

# Run scan
fs2 scan

# Verbose mode (shows per-file progress)
fs2 scan --verbose
```

**Configuration** (`.fs2/config.yaml`):

```yaml
scan:
  scan_paths:
    - "."
  respect_gitignore: true
  max_file_size_kb: 500
```

**Output**: Graph saved to `.fs2/graph.pickle`

See [Scanning Guide](docs/how/user/scanning.md) for details on node types, troubleshooting, and advanced configuration.

## Embeddings

Enable semantic search by generating embeddings for your code:

```yaml
# .fs2/config.yaml
embedding:
  mode: azure  # azure | openai_compatible | fake
  dimensions: 1024
  azure:
    endpoint: "${FS2_AZURE__EMBEDDING__ENDPOINT}"
    api_key: "${FS2_AZURE__EMBEDDING__API_KEY}"
    deployment_name: "text-embedding-3-small"
```

```bash
# Scan with embeddings (default when config exists)
fs2 scan

# Scan without embeddings (faster, no API calls)
fs2 scan --no-embeddings
```

**Content-Type Aware Chunking**: Code uses 400-token chunks for precision, documentation uses 800-token chunks for context.

See the [Configuration Guide](docs/how/user/configuration-guide.md) for detailed embeddings configuration, provider setup, and architecture.

## Cross-File Relationships

fs2 resolves cross-file references (imports, calls, type usage) using [SCIP](https://github.com/sourcegraph/scip) indexers. When enabled, `get_node` output includes a `relationships` field showing which nodes reference and are referenced by the queried node.

### Quick Start

```bash
# Discover language projects in your repo
fs2 discover-projects

# Add detected projects to config
fs2 add-project --all

# Scan with cross-file references
fs2 scan

# View relationships for a node
fs2 get-node "callable:src/service.py:Service.process"
# → includes: relationships: { referenced_by: [...], references: [...] }
```

### Supported Languages

| Language | Indexer | Install |
|----------|---------|---------|
| Python | scip-python | `npm install -g @sourcegraph/scip-python` |
| TypeScript | scip-typescript | `npm install -g @sourcegraph/scip-typescript` |
| JavaScript | scip-typescript | `npm install -g @sourcegraph/scip-typescript` |
| Go | scip-go | `go install github.com/sourcegraph/scip-go/cmd/scip-go@latest` |
| C#/.NET | scip-dotnet | `dotnet tool install --global scip-dotnet` |

### Configuration

```yaml
# .fs2/config.yaml
cross_file_rels:
  enabled: true

projects:
  entries:
    - type: python
      path: .
    - type: typescript
      path: frontend
  auto_discover: true
  scip_cache_dir: .fs2/scip
```

### CLI Flags

```bash
fs2 scan --no-cross-refs              # Skip cross-file resolution
fs2 discover-projects                 # Detect language projects
fs2 add-project 1 2 3                # Add by number from discover output
```

See the [Cross-File Relationships Guide](src/fs2/docs/cross-file-relationships.md) for detailed setup and troubleshooting.

## Language Support

fs2 uses [tree-sitter](https://tree-sitter.github.io/) for parsing. Languages are categorized as:

**Code Languages (40)** - Parsed into functions, classes, methods:
- Systems: C, C++, Rust, Go, Zig, D, Nim
- JVM: Java, Kotlin, Scala, Groovy
- .NET: C#, F#
- Web: JavaScript, TypeScript, TSX, PHP
- Scripting: Python, Ruby, Perl, Lua
- Functional: Haskell, OCaml, Elixir, Erlang, Clojure, Scheme, Racket, Common Lisp
- Mobile: Swift, Dart
- Scientific: R, Julia, MATLAB, Fortran
- GPU/Shaders: CUDA, GLSL, HLSL, WGSL

**File-only Languages** - Summarized as whole documents:
- Config: JSON, YAML, TOML, XML, INI
- Documentation: Markdown, RST, LaTeX
- Infrastructure: Dockerfile, Makefile, Terraform (HCL)
- Shell: Bash, Fish, PowerShell
- Query: SQL, GraphQL

Unknown languages default to file-only (safe).

## Canonical Example

See `tests/docs/test_sample_adapter_pattern.py` for 19 tests demonstrating the full composition pattern.

## Developer Setup

For contributing to fs2:

```bash
git clone https://github.com/AI-Substrate/flow_squared
cd flow_squared
uv sync --extra dev
```

### Development Commands

```bash
# Run tests
just test          # All tests (209+)
just test-unit     # Unit tests only
just test-mcp      # MCP integration tests

# Code quality
just lint          # Ruff linting
just fix           # Auto-fix + format

# Scan this project (dogfooding)
fs2 init
fs2 scan
```

### Project Structure

```
src/fs2/
├── cli/              # Presentation layer (Typer + Rich)
├── core/
│   ├── models/       # Domain models (frozen dataclasses)
│   ├── services/     # Composition layer
│   ├── adapters/     # ABC interfaces + implementations
│   └── repos/        # Repository interfaces
├── mcp/              # MCP server (FastMCP)
└── config/           # Pydantic-settings configuration
```

### Key Patterns

- **ABC-based interfaces** with `@abstractmethod` for explicit contracts
- **Fakes over mocks** for testing
- **ConfigurationService** registry pattern (no singletons)
- **No concept leakage** - components get their own configs internally

### Developer Guides

| Guide | Description |
|-------|-------------|
| [Architecture](docs/how/dev/architecture.md) | Clean Architecture layers, dependency rules |
| [TDD](docs/how/dev/tdd.md) | Test structure, fixtures, fakes over mocks |
| [Dependency Injection](docs/how/dev/di.md) | Constructor injection, ConfigurationService |
| [Adding Services & Adapters](docs/how/dev/adding-services-adapters.md) | Step-by-step guide for new components |
| [LLM Adapter Extension](docs/how/dev/llm-adapter-extension.md) | Add new LLM providers (OpenAI, Anthropic, etc.) |
| [Wormhole MCP](docs/how/user/wormhole-mcp-guide.md) | VS Code LSP integration for development |
