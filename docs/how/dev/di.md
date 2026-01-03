# Dependency Injection

fs2 uses **constructor injection** with ABC interfaces.

## Core Pattern

```python
# Services receive ConfigurationService (registry), NOT extracted configs
class MyService:
    def __init__(self, config: ConfigurationService, adapter: MyAdapter):
        self._config = config.require(MyServiceConfig)  # Gets own config
        self._adapter = adapter
```

## No Concept Leakage

The composition root passes the registry - components get their own configs internally:

```python
# CORRECT - No concept leakage
config = FakeConfigurationService(
    MyServiceConfig(retry_count=3),
    MyAdapterConfig(timeout=60),
)
adapter = FakeMyAdapter(config)      # Adapter gets its own config
service = MyService(config, adapter)  # Service gets its own config

# WRONG - Composition root knows too much
service_cfg = config.require(MyServiceConfig)  # Leaks knowledge!
service = MyService(config=service_cfg, ...)   # Tightly coupled
```

## ABC Interfaces

Each adapter has its own ABC file:

| File | Purpose |
|------|---------|
| `log_adapter.py` | ABC definition only |
| `log_adapter_console.py` | ConsoleLogAdapter implementation |
| `log_adapter_fake.py` | FakeLogAdapter for tests |

ABCs import **only domain types** - no SDKs:

```python
# log_adapter.py (ABC)
from fs2.core.models import LogEntry  # Domain type OK
# NO: from openai import Client       # SDK import forbidden
```

## Testing with Fakes

```python
config = FakeConfigurationService(LogAdapterConfig(min_level="INFO"))
logger = FakeLogAdapter(config)

service = MyService(config=config, logger=logger)
service.do_work()

assert len(logger.messages) == 1
assert logger.messages[0].level == LogLevel.INFO
```

## Further Reading

- [Adding Services & Adapters](adding-services-adapters.md) - Complete step-by-step guide
- [Architecture](architecture.md) - Layer diagram
