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
| [TDD](docs/how/tdd.md) | Test structure, fixtures, fakes |
| [Dependency Injection](docs/how/di.md) | DI patterns |
| [Adding Services & Adapters](docs/how/adding-services-adapters.md) | Step-by-step guide |

## Canonical Example

See `tests/docs/test_sample_adapter_pattern.py` for 19 tests demonstrating the full composition pattern.
