# Flowspace2 (fs2)

Code intelligence for your codebase. Scan, search, and explore code with AI agents via MCP.

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
| [Agent Integration](docs/how/user/AGENTS.md) | How AI agents should use fs2 tools effectively |

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
