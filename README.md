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
| [TDD](docs/how/tdd.md) | Test structure, fixtures, fakes |
| [Dependency Injection](docs/how/di.md) | DI patterns |
| [Adding Services & Adapters](docs/how/adding-services-adapters.md) | Step-by-step guide |

## Canonical Example

See `tests/docs/test_sample_adapter_pattern.py` for 19 tests demonstrating the full composition pattern.
