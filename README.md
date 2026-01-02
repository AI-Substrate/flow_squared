# Flowspace2 (fs2)

A Python project skeleton implementing **Clean Architecture** with strict dependency boundaries.

## Quick Start

```bash
# Clone and install
git clone <repo-url>
cd flow_squared
uv sync --extra dev

# Run tests
just test          # All tests (209+)
just test-unit     # Unit tests only
just lint          # Ruff linting
just fix           # Auto-fix + format
```

## Project Structure

```
src/fs2/
├── cli/              # Presentation layer (Typer + Rich)
├── core/
│   ├── models/       # Domain models (frozen dataclasses)
│   ├── services/     # Composition layer
│   ├── adapters/     # ABC interfaces + implementations
│   └── repos/        # Repository interfaces
└── config/           # Pydantic-settings configuration
```

## Scanning

Scan your codebase to build a queryable code graph:

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

See [Scanning Guide](docs/how/scanning.md) for details on node types, troubleshooting, and advanced configuration.

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

See [Embeddings Guide](docs/how/embeddings/) for detailed configuration, provider setup, and architecture.

## MCP Server (AI Agent Integration)

Start the MCP server for Claude Code, Claude Desktop, GitHub Copilot, or other MCP-compatible clients:

```bash
fs2 mcp
```

**Prerequisites**: Run `fs2 scan` first to index your codebase.

### Option 1: Local Install (Recommended for Daily Use)

**Claude Code**:
```bash
# Add fs2 MCP server (available across all projects)
claude mcp add fs2 --scope user -- fs2 mcp

# Verify it's configured
claude mcp list
```

**Claude Desktop** (`~/.config/claude/claude_desktop_config.json`):
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

### Option 2: Zero-Install with uvx

No local installation required. Requires [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

```bash
# Run fs2 commands directly from GitHub
uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 --help
uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 mcp

# Skip update checks (use cached version)
uvx --offline --from git+https://github.com/AI-Substrate/flow_squared fs2 mcp

# Pin to specific commit for reproducibility
uvx --from git+https://github.com/AI-Substrate/flow_squared@main fs2 mcp
```

> First run builds from source (~30-60s). Subsequent runs use cache and are near-instant.

**Permanent install** (faster startup, no update checks):
```bash
# Install fs2 permanently (self-bootstrapping)
uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 install

# Now use directly
fs2 --help
fs2 mcp

# Update to latest
fs2 upgrade
```

**Claude Desktop with uvx**:
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

### Available Tools

| Tool | Purpose |
|------|---------|
| `tree` | Explore codebase structure as a hierarchical tree |
| `get_node` | Retrieve complete source code for a specific node |
| `search` | Find code by text, regex, or semantic meaning |

See [MCP Server Guide](docs/how/mcp-server-guide.md) for detailed documentation on all clients and tools.

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

## Key Patterns

- **ABC-based interfaces** with `@abstractmethod` for explicit contracts
- **Fakes over mocks** for testing
- **ConfigurationService** registry pattern (no singletons)
- **No concept leakage** - components get their own configs internally

## Documentation

| Guide | Description |
|-------|-------------|
| [Architecture](docs/how/architecture.md) | Layer diagram, import rules |
| [Configuration](docs/how/configuration.md) | Multi-source config, env vars |
| [Scanning](docs/how/scanning.md) | File scanning and code graph generation |
| [Embeddings](docs/how/embeddings/) | Semantic embeddings for code search |
| [MCP Server](docs/how/mcp-server-guide.md) | AI agent integration (Claude, Copilot, etc.) |
| [TDD](docs/how/tdd.md) | Test structure, fixtures, fakes |
| [Dependency Injection](docs/how/di.md) | DI patterns |
| [Adding Services & Adapters](docs/how/adding-services-adapters.md) | Step-by-step guide |

## Canonical Example

See `tests/docs/test_sample_adapter_pattern.py` for 19 tests demonstrating the full composition pattern.
