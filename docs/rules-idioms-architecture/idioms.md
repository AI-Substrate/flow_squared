# fs2 Idioms

> Recurring patterns and examples implementing the [Constitution](../rules/constitution.md) and [Rules](rules.md).

**Version**: 1.0.0
**Last Updated**: 2025-12-01

---

## 1. Adapter Implementation Pattern

### 1.1 ABC Definition

```python
# src/fs2/core/adapters/sample_adapter.py
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from fs2.core.models import ProcessResult

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService

class SampleAdapter(ABC):
    """
    Abstract base class for sample processing adapters.

    Contract:
    - process() returns ProcessResult (never raises for business logic)
    - validate() raises AdapterError on invalid input
    - Implementations receive ConfigurationService, extract own config
    """

    @abstractmethod
    def __init__(self, config: "ConfigurationService") -> None:
        """Initialize with configuration registry."""
        ...

    @abstractmethod
    def process(self, data: str) -> ProcessResult:
        """Process data and return result."""
        ...

    @abstractmethod
    def validate(self, data: str) -> bool:
        """Validate input data. Raises AdapterError on failure."""
        ...
```

### 1.2 Fake Implementation (Test Double)

```python
# src/fs2/core/adapters/sample_adapter_fake.py
from typing import TYPE_CHECKING

from fs2.core.adapters.sample_adapter import SampleAdapter
from fs2.core.adapters.exceptions import AdapterError
from fs2.core.models import ProcessResult

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService

class FakeSampleAdapter(SampleAdapter):
    """
    Fake adapter for testing - captures calls and allows behavior configuration.

    Usage:
        config = FakeConfigurationService(SampleAdapterConfig(simulate_error=False))
        adapter = FakeSampleAdapter(config)
        result = adapter.process("test")
        assert adapter.call_history == [{"method": "process", "data": "test"}]
    """

    def __init__(self, config: "ConfigurationService") -> None:
        from fs2.config.objects import SampleAdapterConfig
        self._config = config.require(SampleAdapterConfig)
        self._call_history: list[dict] = []

    @property
    def call_history(self) -> list[dict]:
        """Access recorded calls for assertions."""
        return self._call_history

    def process(self, data: str) -> ProcessResult:
        self._call_history.append({"method": "process", "data": data})

        if self._config.simulate_error:
            return ProcessResult.fail(
                error="Simulated error",
                details={"data": data}
            )

        return ProcessResult.ok(
            value=f"processed:{data}",
            metadata={"adapter": "fake"}
        )

    def validate(self, data: str) -> bool:
        self._call_history.append({"method": "validate", "data": data})

        if not data or not data.strip():
            raise AdapterError(
                "Input cannot be empty. "
                "Provide non-whitespace input or set fail_on_empty=False in config."
            )

        return True
```

### 1.3 Production Implementation

```python
# src/fs2/core/adapters/sample_adapter_prod.py
from typing import TYPE_CHECKING

from fs2.core.adapters.sample_adapter import SampleAdapter
from fs2.core.adapters.exceptions import AdapterError, AdapterConnectionError
from fs2.core.models import ProcessResult

# SDK imports ONLY in *_impl.py files
from some_sdk import SomeClient, SomeSDKError

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService

class ProdSampleAdapter(SampleAdapter):
    """Production adapter using external SDK."""

    def __init__(self, config: "ConfigurationService") -> None:
        from fs2.config.objects import SampleAdapterConfig
        self._config = config.require(SampleAdapterConfig)
        self._client = SomeClient(
            api_key=self._config.api_key,
            timeout=self._config.timeout
        )

    def process(self, data: str) -> ProcessResult:
        try:
            result = self._client.process(data)
            return ProcessResult.ok(value=result)
        except SomeSDKError as e:
            # Exception translation at adapter boundary
            return ProcessResult.fail(
                error=f"SDK error: {e}",
                details={"original_error": str(e)}
            )

    def validate(self, data: str) -> bool:
        if not data or not data.strip():
            raise AdapterError("Input cannot be empty.")
        return True
```

<!-- USER CONTENT START -->
<!-- Add project-specific adapter patterns here -->
<!-- USER CONTENT END -->

---

## 2. Service Composition Pattern

### 2.1 Service with Injected Dependencies

```python
# src/fs2/core/services/sample_service.py
from typing import TYPE_CHECKING

from fs2.core.adapters.sample_adapter import SampleAdapter
from fs2.core.models import ProcessResult

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService

class SampleService:
    """
    Service demonstrating Clean Architecture composition.

    Contract:
    - Receives ConfigurationService (registry) + adapter ABC
    - Extracts own config internally (no concept leakage)
    - Orchestrates adapters to fulfill business logic
    """

    def __init__(
        self,
        config: "ConfigurationService",
        adapter: SampleAdapter
    ) -> None:
        from fs2.config.objects import SampleServiceConfig

        # Extract own config - composition root doesn't know about this
        self._service_config = config.require(SampleServiceConfig)
        self._adapter = adapter

    def process_with_retry(self, data: str) -> ProcessResult:
        """Process data with configurable retry logic."""
        last_result = None

        for attempt in range(self._service_config.retry_count):
            result = self._adapter.process(data)

            if result.success:
                return result

            last_result = result

        return last_result or ProcessResult.fail(
            error="All retries exhausted",
            details={"attempts": self._service_config.retry_count}
        )
```

### 2.2 Composition Root (Wiring)

```python
# Application entry point / composition root
from fs2.config.service import FS2ConfigurationService
from fs2.core.adapters.sample_adapter_fake import FakeSampleAdapter
from fs2.core.services.sample_service import SampleService

# Create registry (loads YAML, env vars, etc.)
config = FS2ConfigurationService()

# Wire dependencies - composition root passes registry
adapter = FakeSampleAdapter(config)  # Adapter gets own config internally
service = SampleService(config=config, adapter=adapter)  # Service gets own config

# Use service
result = service.process_with_retry("test data")
```

<!-- USER CONTENT START -->
<!-- Add project-specific service patterns here -->
<!-- USER CONTENT END -->

---

## 3. Configuration Pattern

### 3.1 Config Type Definition

```python
# src/fs2/config/objects.py
from pydantic import BaseModel, Field

class SampleAdapterConfig(BaseModel):
    """Configuration for SampleAdapter implementations."""

    __config_path__ = "sample.adapter"  # YAML path

    api_key: str = Field(
        default="${SAMPLE_API_KEY}",
        description="API key for external service. Use ${VAR} for env var."
    )
    timeout: int = Field(
        default=30,
        description="Request timeout in seconds."
    )
    simulate_error: bool = Field(
        default=False,
        description="If True, fake adapter returns errors (testing only)."
    )

class SampleServiceConfig(BaseModel):
    """Configuration for SampleService."""

    __config_path__ = "sample.service"

    retry_count: int = Field(
        default=3,
        description="Number of retry attempts on failure."
    )
    fail_on_empty: bool = Field(
        default=True,
        description="If True, raises error on empty input."
    )

# Register in YAML_CONFIG_TYPES list
YAML_CONFIG_TYPES = [
    SampleAdapterConfig,
    SampleServiceConfig,
    # ... other config types
]
```

### 3.2 YAML Configuration

```yaml
# .fs2/config.yaml
sample:
  adapter:
    api_key: ${SAMPLE_API_KEY}  # Placeholder - expanded from env
    timeout: 60
  service:
    retry_count: 5
    fail_on_empty: true
```

### 3.3 Environment Override

```bash
# Environment variables override YAML (leaf-level)
export FS2_SAMPLE__ADAPTER__TIMEOUT=120
export SAMPLE_API_KEY=sk-actual-key

# Result: timeout=120 (env), api_key=sk-actual-key (expanded)
```

<!-- USER CONTENT START -->
<!-- Add project-specific configuration patterns here -->
<!-- USER CONTENT END -->

---

## 4. Testing Patterns

### 4.1 Test with Fakes

```python
# tests/unit/services/test_sample_service.py
import pytest
from fs2.config.service import FakeConfigurationService
from fs2.config.objects import SampleServiceConfig, SampleAdapterConfig
from fs2.core.adapters.sample_adapter_fake import FakeSampleAdapter
from fs2.core.services.sample_service import SampleService

def test_given_service_with_fakes_when_processing_then_returns_success():
    """
    Purpose: Verify service correctly orchestrates adapter calls.
    Quality Contribution: Ensures composition pattern works; catches DI errors.
    """
    # Arrange
    config = FakeConfigurationService(
        SampleServiceConfig(retry_count=3),
        SampleAdapterConfig(simulate_error=False),
    )
    adapter = FakeSampleAdapter(config)
    service = SampleService(config=config, adapter=adapter)

    # Act
    result = service.process_with_retry("test data")

    # Assert
    assert result.success is True
    assert "processed:" in result.value
    assert len(adapter.call_history) == 1

def test_given_failing_adapter_when_retrying_then_exhausts_attempts():
    """
    Purpose: Verify retry logic respects configured count.
    Quality Contribution: Prevents infinite retry loops; documents retry behavior.
    """
    # Arrange
    config = FakeConfigurationService(
        SampleServiceConfig(retry_count=3),
        SampleAdapterConfig(simulate_error=True),  # Always fails
    )
    adapter = FakeSampleAdapter(config)
    service = SampleService(config=config, adapter=adapter)

    # Act
    result = service.process_with_retry("test data")

    # Assert
    assert result.success is False
    assert len(adapter.call_history) == 3  # Tried 3 times
```

### 4.2 Test Fixtures (conftest.py)

```python
# tests/conftest.py
import pytest
from fs2.config.service import FakeConfigurationService
from fs2.config.objects import LogAdapterConfig
from fs2.core.adapters.log_adapter_fake import FakeLogAdapter

@pytest.fixture
def clean_config_env(monkeypatch):
    """Clear all FS2_* environment variables to prevent test pollution."""
    import os
    for key in list(os.environ.keys()):
        if key.startswith("FS2_"):
            monkeypatch.delenv(key)

@pytest.fixture
def test_context():
    """Pre-wired DI container for tests."""
    config = FakeConfigurationService(
        LogAdapterConfig(min_level="DEBUG"),
    )
    logger = FakeLogAdapter(config)
    return TestContext(config=config, logger=logger)

class TestContext:
    """Container for test dependencies."""
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
```

### 4.3 Given-When-Then Naming

```python
# Pattern: test_given_<precondition>_when_<action>_then_<outcome>

def test_given_empty_input_when_validating_then_raises_adapter_error():
    """Empty input should fail validation with actionable error."""
    ...

def test_given_valid_config_when_loading_then_returns_typed_object():
    """Valid YAML loads into correct config type."""
    ...

def test_given_env_override_when_loading_then_env_takes_precedence():
    """Environment variables override YAML at leaf level."""
    ...
```

<!-- USER CONTENT START -->
<!-- Add project-specific testing patterns here -->
<!-- USER CONTENT END -->

---

## 5. Domain Model Patterns

### 5.1 Frozen Dataclass

```python
# src/fs2/core/models/process_result.py
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class ProcessResult:
    """
    Immutable result of a processing operation.

    Use factory methods ok() and fail() instead of direct construction.
    """
    success: bool
    value: Any = None
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, value: Any, metadata: dict[str, Any] | None = None) -> "ProcessResult":
        """Create successful result."""
        return cls(success=True, value=value, metadata=metadata or {})

    @classmethod
    def fail(cls, error: str, details: dict[str, Any] | None = None) -> "ProcessResult":
        """Create failure result."""
        return cls(success=False, error=error, details=details or {})
```

### 5.2 IntEnum for Levels

```python
# src/fs2/core/models/log_level.py
from enum import IntEnum

class LogLevel(IntEnum):
    """Log severity levels with natural ordering."""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40

    # IntEnum enables: LogLevel.INFO < LogLevel.ERROR  # True
```

<!-- USER CONTENT START -->
<!-- Add project-specific model patterns here -->
<!-- USER CONTENT END -->

---

## 6. Exception Patterns

### 6.1 Actionable Error Messages

```python
# src/fs2/core/adapters/exceptions.py
class AdapterError(Exception):
    """
    Base exception for adapter errors.

    All messages MUST include fix instructions.
    """
    pass

class AuthenticationError(AdapterError):
    """Authentication failed - include how to fix."""

    def __init__(self, service: str, reason: str):
        super().__init__(
            f"Authentication failed for {service}: {reason}. "
            f"Check your API key in .fs2/secrets.env or set FS2_{service.upper()}__API_KEY."
        )

class AdapterConnectionError(AdapterError):
    """Connection failed - include retry guidance."""

    def __init__(self, service: str, reason: str):
        super().__init__(
            f"Connection to {service} failed: {reason}. "
            f"Check network connectivity and service status. "
            f"Retry with exponential backoff."
        )
```

### 6.2 Exception Translation

```python
# In adapter implementation
def call_external_service(self, data: str) -> ProcessResult:
    try:
        result = self._sdk_client.process(data)
        return ProcessResult.ok(result)
    except SDKAuthError as e:
        raise AuthenticationError("external_service", str(e)) from e
    except SDKConnectionError as e:
        raise AdapterConnectionError("external_service", str(e)) from e
    except SDKError as e:
        # Generic SDK error - still translate
        return ProcessResult.fail(
            error=f"Service error: {e}",
            details={"sdk_error_type": type(e).__name__}
        )
```

<!-- USER CONTENT START -->
<!-- Add project-specific exception patterns here -->
<!-- USER CONTENT END -->

---

## 7. Complexity Score Calibration Examples

| Task | S | I | D | N | F | T | Total | CS |
|------|---|---|---|---|---|---|-------|-----|
| Rename constant in one file | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **CS-1** (trivial) |
| Add Field to existing config | 1 | 0 | 0 | 0 | 0 | 1 | 2 | **CS-1** (trivial) |
| New adapter using existing ABC | 1 | 1 | 0 | 1 | 0 | 1 | 4 | **CS-2** (small) |
| Add new endpoint with existing patterns | 1 | 1 | 1 | 1 | 0 | 1 | 5 | **CS-3** (medium) |
| Integrate new external API | 2 | 2 | 0 | 1 | 1 | 1 | 7 | **CS-3** (medium) |
| Add caching layer | 2 | 1 | 1 | 1 | 1 | 2 | 8 | **CS-4** (large) |
| New service with schema migration | 2 | 2 | 2 | 2 | 1 | 2 | 11 | **CS-5** (epic) |

**Scoring Guide**:
- **S (Surface)**: 0=one file, 1=multiple files, 2=cross-cutting
- **I (Integration)**: 0=internal only, 1=one external, 2=multiple externals
- **D (Data/State)**: 0=none, 1=minor tweaks, 2=migration/concurrency
- **N (Novelty)**: 0=well-specified, 1=some ambiguity, 2=significant discovery
- **F (NFR)**: 0=standard, 1=moderate constraints, 2=strict requirements
- **T (Testing)**: 0=unit only, 1=integration/e2e, 2=staged rollout

<!-- USER CONTENT START -->
<!-- Add project-specific complexity examples here -->
<!-- USER CONTENT END -->

---

## 8. Directory Conventions

```
src/fs2/
├── cli/                    # Presentation layer (Typer + Rich)
│   └── main.py            # CLI entry point
├── core/
│   ├── models/            # Domain models (frozen dataclasses)
│   │   ├── __init__.py    # Re-exports all models
│   │   ├── log_level.py   # LogLevel IntEnum
│   │   ├── log_entry.py   # LogEntry frozen dataclass
│   │   └── process_result.py
│   ├── services/          # Composition layer
│   │   └── sample_service.py
│   ├── adapters/          # External integrations
│   │   ├── exceptions.py  # AdapterError hierarchy
│   │   ├── log_adapter.py           # ABC
│   │   ├── log_adapter_console.py   # Impl
│   │   ├── log_adapter_fake.py      # Test double
│   │   ├── sample_adapter.py        # ABC
│   │   └── sample_adapter_fake.py   # Test double
│   └── repos/             # Data access
│       └── protocols.py   # Repository ABCs
└── config/                # Configuration
    ├── __init__.py        # Exports
    ├── service.py         # ConfigurationService
    ├── objects.py         # Config type definitions
    ├── loaders.py         # Loading pipeline
    ├── paths.py           # Path resolution
    └── exceptions.py      # Config errors

tests/
├── conftest.py           # Shared fixtures
├── unit/
│   ├── adapters/         # Adapter tests
│   ├── config/           # Config tests
│   ├── models/           # Model tests
│   └── services/         # Service tests
├── docs/                 # Documentation tests
│   └── test_sample_adapter_pattern.py  # Canonical example
└── scratch/              # Exploration (excluded from CI)
```

<!-- USER CONTENT START -->
<!-- Add project-specific directory conventions here -->
<!-- USER CONTENT END -->

---

## 9. CLI Command Pattern

### 9.1 Save-to-File Pattern

Commands outputting structured data (JSON) MUST support both stdout and file output per R9.5:

```python
# src/fs2/cli/example_command.py
"""Example command with save-to-file support.

Per R9.5: CLI documentation requirements.
Per R9.1: Standard option naming (--json, --file, --detail).
"""

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from fs2.cli.utils import safe_write_file, validate_save_path

# Separate consoles: stdout for JSON, stderr for messages
console = Console()
stderr_console = Console(stderr=True)

def example_command(
    pattern: Annotated[str, typer.Argument(help="Filter pattern")],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON instead of text (for scripting)"),
    ] = False,
    file: Annotated[
        Path | None,
        typer.Option(
            "--file", "-f",
            help="Write JSON to file instead of stdout (path validated for security).",
        ),
    ] = None,
) -> None:
    """Command with structured output.

    \b
    Examples:
        $ fs2 example              # Text output to stdout
        $ fs2 example --json       # JSON to stdout (for piping)
        $ fs2 example --json --file results.json  # JSON to file
        $ fs2 example --json | jq  # Pipe to jq
    """
    # ... business logic to produce data ...
    data = {"result": "example"}

    if json_output or file:
        # Convert to JSON envelope
        envelope = {"results": data}
        json_str = json.dumps(envelope, indent=2, default=str)

        if file:
            # Validate path (prevents directory traversal)
            absolute_path = validate_save_path(file, stderr_console)
            # Write with error handling (cleans up on failure)
            safe_write_file(absolute_path, json_str, stderr_console)
            # Confirmation on stderr (keeps stdout clean for piping)
            stderr_console.print(f"[green]✓[/green] Wrote results to {file}")
        else:
            # Use raw print() for clean JSON output
            print(json_str)
    else:
        # Rich text output for humans
        console.print("Results here")
```

**Key Principles**:
- Use raw `print()` for JSON (enables piping to jq)
- Use `Console(stderr=True)` for status/error messages
- Validate save paths with `validate_save_path()` (security)
- Write files safely with `safe_write_file()` (error cleanup)
- Document JSON envelope structure in `docs/how/cli.md`

### 9.2 Exit Code Pattern

All CLI commands MUST use consistent exit codes:

```python
from rich.console import Console
import typer

stderr_console = Console(stderr=True)

def command():
    """Command with proper exit codes."""

    # User error (missing config, bad input) → exit 1
    if not config_exists():
        stderr_console.print("[red]Error:[/red] No configuration found.")
        stderr_console.print("Run [bold]fs2 init[/bold] first.")
        raise typer.Exit(code=1)

    # System error (I/O failure, corruption) → exit 2
    try:
        load_graph()
    except CorruptedGraphError as e:
        stderr_console.print(f"[red]Error:[/red] Graph corrupted: {e}")
        stderr_console.print("Run [bold]fs2 scan[/bold] to rebuild.")
        raise typer.Exit(code=2)

    # Success → exit 0 (implicit or explicit)
    raise typer.Exit(code=0)
```

### 9.3 Documentation Docstring Pattern

Every CLI command MUST have a docstring with examples:

```python
def search(
    pattern: str,
    mode: str = "auto",
) -> None:
    """Search the code graph.

    Searches using text, regex, or semantic matching.

    \b
    Arguments:
        pattern  Search pattern (text, regex, or query)

    \b
    Options:
        --mode   Search mode: auto, text, regex, semantic

    \b
    Examples:
        $ fs2 search "authentication"
        $ fs2 search "def.*test" --mode regex
        $ fs2 search "error handling" --mode semantic

    \b
    Exit Codes:
        0  Success
        1  User error (missing graph, invalid pattern)
        2  System error (corrupted graph)
    """
    ...
```

**Note**: Use `\b` to preserve Rich formatting in `--help` output.

<!-- USER CONTENT START -->
<!-- Add project-specific CLI patterns here -->
<!-- USER CONTENT END -->

---

*See [Constitution](../rules/constitution.md) for principles.*
*See [Rules](rules.md) for normative statements.*
*See [Architecture](architecture.md) for structural boundaries.*
*See [CLI Reference](../how/cli.md) for command documentation.*
