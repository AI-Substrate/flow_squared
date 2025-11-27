# Adding Services, Adapters, and Configuration

This guide explains how to add new services, adapters, and their configuration to fs2 following Clean Architecture principles.

**Canonical Example**: `tests/docs/test_sample_adapter_pattern.py`

---

## Table of Contents

1. [Core Principles](#core-principles)
2. [File Locations](#file-locations)
3. [Step-by-Step: Adding a New Adapter](#step-by-step-adding-a-new-adapter)
4. [Step-by-Step: Adding a New Service](#step-by-step-adding-a-new-service)
5. [Testing Pattern](#testing-pattern)
6. [Common Mistakes to Avoid](#common-mistakes-to-avoid)

---

## Core Principles

### 1. No Concept Leakage

The composition root passes `ConfigurationService` (registry) to all components. Components call `config.require(TheirConfigType)` internally. **The composition root doesn't know what configs each component needs.**

```python
# WRONG - Concept leakage (composition root extracts config)
service_config = config.require(MyServiceConfig)  # Leaks knowledge
service = MyService(config=service_config, adapter=adapter)

# CORRECT - No concept leakage (component gets its own config)
service = MyService(config=config, adapter=adapter)  # Pass registry
# Inside MyService.__init__:
#   self._service_config = config.require(MyServiceConfig)
```

### 2. Config Types Live in `fs2.config.objects`

All Pydantic config models with `__config_path__` belong in `src/fs2/config/objects.py`. This enables:
- Auto-loading from YAML/env during `FS2ConfigurationService.__init__()`
- Registration in `YAML_CONFIG_TYPES`
- Clean import from a single location

### 3. Dependency Flow

```
fs2.config.objects  ←  fs2.core.services  ←  fs2.core.adapters
       ↑                      ↑                      ↑
       │                      │                      │
   Config types          Service logic         Adapter ABCs
   (Pydantic)           (uses adapters)        (interfaces)
```

Services and adapters import config types from `fs2.config.objects`.

### 4. ABCs in Separate Files

Each adapter ABC lives in its own file:
- `src/fs2/core/adapters/sample_adapter.py` - ABC only
- `src/fs2/core/adapters/sample_adapter_fake.py` - Fake implementation
- `src/fs2/core/adapters/sample_adapter_prod.py` - Production implementation (if applicable)

---

## File Locations

| Component | Location | Example |
|-----------|----------|---------|
| Config type | `src/fs2/config/objects.py` | `SampleServiceConfig`, `SampleAdapterConfig` |
| Adapter ABC | `src/fs2/core/adapters/{name}_adapter.py` | `SampleAdapter` |
| Adapter Fake | `src/fs2/core/adapters/{name}_adapter_fake.py` | `FakeSampleAdapter` |
| Adapter Prod | `src/fs2/core/adapters/{name}_adapter_prod.py` | `ProdSampleAdapter` |
| Service | `src/fs2/core/services/{name}_service.py` | `SampleService` |
| Tests | `tests/docs/test_{name}_pattern.py` | Documentation tests |
| Unit Tests | `tests/unit/adapters/test_{name}.py` | Unit tests |

---

## Step-by-Step: Adding a New Adapter

### Step 1: Define the Config Type

Add to `src/fs2/config/objects.py`:

```python
class MyAdapterConfig(BaseModel):
    """Configuration for MyAdapter implementations.

    Loaded from YAML or environment variables.
    Path: my.adapter (e.g., FS2_MY__ADAPTER__TIMEOUT)

    Attributes:
        timeout: Request timeout in seconds.
        endpoint: API endpoint URL.
    """

    __config_path__: ClassVar[str] = "my.adapter"

    timeout: int = 30
    endpoint: str | None = None
```

Register it in `YAML_CONFIG_TYPES`:

```python
YAML_CONFIG_TYPES: list[type[BaseModel]] = [
    AzureOpenAIConfig,
    SampleServiceConfig,
    SampleAdapterConfig,
    MyAdapterConfig,  # Add here
]
```

### Step 2: Define the ABC

Create `src/fs2/core/adapters/my_adapter.py`:

```python
"""MyAdapter - Abstract base class for my functionality."""

from abc import ABC, abstractmethod
from typing import Any

from fs2.core.models.process_result import ProcessResult


class MyAdapter(ABC):
    """ABC for my adapter implementations.

    Implementations receive ConfigurationService via constructor and
    call config.require(MyAdapterConfig) internally.
    """

    @abstractmethod
    def do_something(self, data: str, context: dict[str, Any] | None = None) -> ProcessResult:
        """Do something with data.

        Args:
            data: Input data to process.
            context: Optional trace context.

        Returns:
            ProcessResult with success/failure and metadata.
        """
```

### Step 3: Implement the Fake

Create `src/fs2/core/adapters/my_adapter_fake.py`:

```python
"""FakeMyAdapter - Test double for MyAdapter."""

from typing import TYPE_CHECKING, Any

from fs2.config.objects import MyAdapterConfig
from fs2.core.adapters.my_adapter import MyAdapter
from fs2.core.models.process_result import ProcessResult

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


class FakeMyAdapter(MyAdapter):
    """Fake implementation of MyAdapter for testing."""

    def __init__(self, config: "ConfigurationService"):
        """Initialize with ConfigurationService registry.

        Args:
            config: ConfigurationService registry (NOT MyAdapterConfig).
        """
        # Adapter gets its own config internally
        self._adapter_config = config.require(MyAdapterConfig)
        self._call_history: list[dict[str, Any]] = []

    def do_something(self, data: str, context: dict[str, Any] | None = None) -> ProcessResult:
        """Fake implementation that records calls."""
        self._call_history.append({
            "method": "do_something",
            "args": (data,),
            "kwargs": {"context": context},
        })

        # Return configurable result
        return ProcessResult.ok(
            value=f"processed: {data}",
            context=context or {},
        )
```

### Step 4: Update Exports

Add to `src/fs2/core/adapters/__init__.py`:

```python
from fs2.core.adapters.my_adapter import MyAdapter

__all__ = [
    # ... existing exports ...
    "MyAdapter",
]
```

---

## Step-by-Step: Adding a New Service

### Step 1: Define the Config Type

Add to `src/fs2/config/objects.py`:

```python
class MyServiceConfig(BaseModel):
    """Configuration for MyService.

    Loaded from YAML or environment variables.
    Path: my.service (e.g., FS2_MY__SERVICE__RETRY_COUNT)
    """

    __config_path__: ClassVar[str] = "my.service"

    retry_count: int = 0
    enable_feature: bool = True
```

Register in `YAML_CONFIG_TYPES`.

### Step 2: Implement the Service

Create `src/fs2/core/services/my_service.py`:

```python
"""MyService - Service demonstrating the composition pattern."""

from typing import TYPE_CHECKING, Any

from fs2.config.objects import MyServiceConfig
from fs2.core.adapters.my_adapter import MyAdapter
from fs2.core.models.process_result import ProcessResult

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


class MyService:
    """Service that uses MyAdapter with injected configuration."""

    def __init__(
        self,
        config: "ConfigurationService",
        adapter: MyAdapter,
    ):
        """Initialize with ConfigurationService and adapter.

        Args:
            config: ConfigurationService registry (NOT MyServiceConfig).
            adapter: Adapter implementing MyAdapter ABC.
        """
        # Service gets its own config internally - no concept leakage
        self._service_config = config.require(MyServiceConfig)
        self._adapter = adapter

    def process(self, data: str, context: dict[str, Any] | None = None) -> ProcessResult:
        """Process data through the adapter."""
        # Use config to control behavior
        if self._service_config.enable_feature:
            return self._adapter.do_something(data, context)
        return ProcessResult.ok(value="feature disabled")
```

### Step 3: Update Exports

Add to `src/fs2/core/services/__init__.py`:

```python
from fs2.core.services.my_service import MyService

__all__ = [
    # ... existing exports ...
    "MyService",
]
```

---

## Testing Pattern

### Use FakeConfigurationService

```python
import pytest

from fs2.config.objects import MyAdapterConfig, MyServiceConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.my_adapter_fake import FakeMyAdapter
from fs2.core.services.my_service import MyService


@pytest.mark.docs
def test_my_service_end_to_end():
    """
    PATTERN: Full composition with FakeConfigurationService.

    1. Create FakeConfigurationService with ALL needed configs
    2. Create adapter - receives registry
    3. Create service - receives SAME registry
    4. Both get their own configs internally
    """
    # Arrange: Create config service with both configs
    config = FakeConfigurationService(
        MyServiceConfig(enable_feature=True),
        MyAdapterConfig(timeout=60),
    )

    # Create adapter - gets its own config internally
    adapter = FakeMyAdapter(config)

    # Create service - gets its own config internally
    service = MyService(config=config, adapter=adapter)

    # Act
    result = service.process("test data")

    # Assert
    assert result.success is True
    assert "processed" in result.value
```

### Test Error Scenarios

```python
def test_service_handles_adapter_error():
    """Configure fake to simulate errors."""
    config = FakeConfigurationService(
        MyServiceConfig(),
        MyAdapterConfig(simulate_error="Connection timeout"),
    )
    adapter = FakeMyAdapter(config)
    service = MyService(config=config, adapter=adapter)

    result = service.process("data")

    assert result.success is False
    assert "timeout" in result.error
```

---

## Common Mistakes to Avoid

### 1. Direct Config Injection (Concept Leakage)

```python
# WRONG
adapter_config = config.require(MyAdapterConfig)
adapter = FakeMyAdapter(adapter_config)  # Direct injection

# CORRECT
adapter = FakeMyAdapter(config)  # Pass registry
```

### 2. Config Types in Core Modules

```python
# WRONG - Config type defined in adapter file
class MyAdapterConfig(BaseModel):  # In my_adapter_fake.py
    ...

# CORRECT - Config type in fs2.config.objects
from fs2.config.objects import MyAdapterConfig
```

### 3. Missing YAML_CONFIG_TYPES Registration

If your config has `__config_path__`, it must be in `YAML_CONFIG_TYPES` to auto-load from YAML/env.

### 4. Importing ConfigurationService at Module Level

```python
# WRONG - Creates circular import
from fs2.config.service import ConfigurationService

class MyService:
    def __init__(self, config: ConfigurationService): ...

# CORRECT - Use TYPE_CHECKING
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService

class MyService:
    def __init__(self, config: "ConfigurationService"): ...
```

---

## Canonical Reference

See `tests/docs/test_sample_adapter_pattern.py` for the complete working example with:
- 19 tests demonstrating every pattern
- Full documentation in docstrings
- Error handling patterns
- Batch processing patterns
- Call history verification
