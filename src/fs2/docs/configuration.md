# Configuration System

fs2 uses a typed configuration system with multi-source loading.

## Precedence (Highest to Lowest)

| Priority | Source | Example |
|----------|--------|---------|
| 1 | Environment variables | `FS2_AZURE__OPENAI__TIMEOUT=60` |
| 2 | Project `.fs2/config.yaml` | `azure.openai.timeout: 60` |
| 3 | User `~/.config/fs2/config.yaml` | Same format |
| 4 | Defaults in code | `timeout: int = 30` |

## Environment Variable Format

```bash
FS2_{SECTION}__{SUBSECTION}__{FIELD}=value

# Examples:
FS2_AZURE__OPENAI__TIMEOUT=60      # azure.openai.timeout
FS2_SAMPLE__SERVICE__RETRY_COUNT=3  # sample.service.retry_count
FS2_LOG__ADAPTER__MIN_LEVEL=INFO    # log.adapter.min_level
```

**Rules**:
- Prefix: `FS2_` (uppercase)
- Nesting: `__` (double underscore) = `.` in YAML
- Case: UPPERCASE in env, lowercase in config path

## Config Types

All config types live in `fs2.config.objects`:

```python
from fs2.config.objects import AzureOpenAIConfig, LogAdapterConfig

# Each has __config_path__ for auto-loading
class LogAdapterConfig(BaseModel):
    __config_path__: ClassVar[str] = "log.adapter"
    min_level: str = "DEBUG"
```

## Usage Pattern

```python
from fs2.config import FS2ConfigurationService
from fs2.config.objects import LogAdapterConfig

config = FS2ConfigurationService()  # Loads all sources
log_config = config.require(LogAdapterConfig)  # Type-safe access
```

## Further Reading

- [Adding Services & Adapters](adding-services-adapters.md) - Config in context
- [.fs2/config.yaml.example](../../.fs2/config.yaml.example) - Example config
