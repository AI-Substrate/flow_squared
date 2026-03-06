# Domain: Configuration

**Slug**: configuration
**Type**: infrastructure
**Created**: 2026-03-05
**Created By**: extracted from existing codebase
**Status**: active

## Purpose

Owns the typed configuration registry — loading settings from multiple sources (YAML files, environment variables, secrets files), merging them with correct precedence, and providing typed access to all consumers via a registry pattern. Every service and adapter in fs2 receives `ConfigurationService` and calls `require(MyConfig)` to get its settings. Without this domain, nothing can be configured.

## Concepts

| Concept | Entry Point | What It Does |
|---------|-------------|-------------|
| Get typed configuration | `config.require(MyConfig)` | Retrieve a validated Pydantic config object by type (raises if missing) |
| Optional configuration | `config.get(MyConfig)` | Retrieve config or None if not set |
| Multi-source loading | `FS2ConfigurationService()` | Load secrets → YAML → env vars with deep merge and placeholder expansion |
| Test configuration | `FakeConfigurationService(configs...)` | Pre-wire configs for testing without files or env vars |
| Server database config | `config.require(ServerDatabaseConfig)` | PostgreSQL connection settings (host, port, pool) for server mode |
| Server storage config | `config.require(ServerStorageConfig)` | Upload staging directory and max upload size for server mode |
| Remote server config | `config.get(RemotesConfig)` | Named remote servers (name, URL, api_key) for CLI --remote and MCP mixed mode |

### Get typed configuration

Services call `config.require(ConfigType)` in their constructor. The registry returns the validated Pydantic model or raises MissingConfigurationError with actionable guidance.

```python
from fs2.config import ConfigurationService
from fs2.config.objects import EmbeddingConfig

class MyService:
    def __init__(self, config: ConfigurationService):
        self._emb = config.require(EmbeddingConfig)
```

### Multi-source loading

FS2ConfigurationService loads from multiple sources with defined precedence. List values (e.g., other_graphs.graphs) are concatenated across sources, not replaced.

```python
from fs2.config import FS2ConfigurationService
config = FS2ConfigurationService()
# Loads: secrets.env → user YAML → project YAML → FS2_* env vars
```

### Test configuration

FakeConfigurationService accepts pre-built config objects. No file I/O, no env vars — pure injection.

```python
from fs2.config import FakeConfigurationService
config = FakeConfigurationService(
    ScanConfig(scan_paths=["./test"]),
    EmbeddingConfig(mode="fake", dimensions=1024)
)
```

## Boundary

### Owns
- ConfigurationService ABC (typed registry pattern: get/set/require)
- FS2ConfigurationService (production: multi-source loading pipeline)
- FakeConfigurationService (test double)
- All Pydantic config models (12 types in objects.py)
- YAML loader, env var parser, secrets loader, deep merge, placeholder expansion
- Config path resolution (user: ~/.config/fs2, project: ./.fs2)
- Config exceptions (MissingConfigurationError, LiteralSecretError, ConfigurationError)
- YAML_CONFIG_TYPES registry (auto-registration of config types)

### Does NOT Own
- Individual config consumers (services read config but don't own the registry)
- Config file templates (operational concern, not domain logic)
- Dependency injection container (core/dependencies.py wraps config, but injection is app-level)

## Contracts (Public Interface)

| Contract | Type | Consumers | Description |
|----------|------|-----------|-------------|
| `ConfigurationService` (ABC) | Interface | All services, adapters, repos (~73 files) | `get(T)`, `require(T)`, `set(T)` |
| `FS2ConfigurationService` | Implementation | CLI main, MCP server, DI container | Production multi-source loader |
| `FakeConfigurationService` | Test Double | All unit tests | Pre-wired config injection |
| `GraphConfig` | Pydantic Model | graph-storage domain | `graph_path` |
| `ScanConfig` | Pydantic Model | graph-storage, indexing | scan_paths, max_file_size_kb |
| `SearchConfig` | Pydantic Model | search domain | regex_timeout, parent_penalty |
| `EmbeddingConfig` | Pydantic Model | embedding services | mode, dimensions, batch_size, chunk configs |
| `LLMConfig` | Pydantic Model | LLM services | provider, model, timeouts |
| `SmartContentConfig` | Pydantic Model | smart content service | max_workers, token limits |
| `OtherGraphsConfig` | Pydantic Model | graph-storage domain | External graph list |
| `WatchConfig` | Pydantic Model | watch service | debounce, timeout |
| `ServerDatabaseConfig` | Pydantic Model | server domain | DB host, port, pool settings, conninfo |
| `ServerStorageConfig` | Pydantic Model | server domain | Upload staging directory, max upload size |
| `RemotesConfig` | Pydantic Model | cli-presentation, MCP server | Named remote server list |
| `RemoteServer` | Pydantic Model | cli-presentation, MCP server | Single remote: name, url, api_key, description |
| `MissingConfigurationError` | Exception | All consumers | Actionable error with sources |

## Composition (Internal)

| Component | Role | Depends On |
|-----------|------|------------|
| `ConfigurationService` (ABC) | Registry contract | — |
| `FS2ConfigurationService` | Production impl | loaders, paths, objects, exceptions |
| `FakeConfigurationService` | Test impl | ConfigurationService ABC |
| `loaders.py` | Multi-source loading | yaml, os, pathlib |
| `paths.py` | Path resolution | XDG spec, pathlib |
| `objects.py` | 14 config models | Pydantic BaseModel |
| `models.py` | Legacy settings | Pydantic BaseSettings |
| `exceptions.py` | Error types | — |
| `docs_registry.py` | Doc registry | Pydantic BaseModel |

## Source Location

Primary: `src/fs2/config/`

| File | Role | Notes |
|------|------|-------|
| `src/fs2/config/service.py` | ABC + implementations | ConfigurationService, FS2ConfigurationService, FakeConfigurationService |
| `src/fs2/config/objects.py` | Config models | 12 Pydantic models, YAML_CONFIG_TYPES registry |
| `src/fs2/config/models.py` | Legacy settings | FS2Settings (BaseSettings) |
| `src/fs2/config/loaders.py` | Loading pipeline | YAML, env, secrets, merge, expand |
| `src/fs2/config/paths.py` | Path resolution | User + project config dirs |
| `src/fs2/config/exceptions.py` | Exceptions | 3 exception types |
| `src/fs2/config/docs_registry.py` | Doc registry | DocumentEntry, DocsRegistry |
| `src/fs2/config/__init__.py` | Public exports | |
| `tests/unit/config/` | Tests | 40+ test files |

## Dependencies

### This Domain Depends On
- **pydantic** (external) — BaseModel, validation, field types
- **pyyaml** (external) — YAML parsing
- **python-dotenv** (external) — .env file loading

### Domains That Depend On This
- **graph-storage** — GraphConfig, ScanConfig, OtherGraphsConfig
- **search** — SearchConfig
- **Every service and adapter** — all receive ConfigurationService via constructor injection

## History

| Plan | What Changed | Date |
|------|-------------|------|
| 003-fs2-base | Initial ConfigurationService + loaders | 2024 |
| 023-multi-graphs | OtherGraphsConfig, list concatenation in deep merge | 2025 |
| 024-az-login | Azure credential config | 2025 |
| 027-openrouter-provider | OpenAI-compatible config | 2025 |
| *(extracted)* | Domain extracted from existing codebase | 2026-03-05 |
| 028-server-mode (Phase 1) | Added ServerDatabaseConfig + ServerStorageConfig for server mode | 2026-03-05 |
| 028-server-mode (Phase 5) | Added RemotesConfig + RemoteServer for named remotes | 2026-03-05 |
