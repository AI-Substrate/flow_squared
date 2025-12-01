# fs2 Architecture

> System structure, boundaries, and interaction contracts implementing the [Constitution](../rules/constitution.md).

**Version**: 1.0.0
**Last Updated**: 2025-12-01

---

## 1. High-Level Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  CLI (Typer + Rich)                                         │   │
│  │  - Argument parsing                                          │   │
│  │  - User interaction                                          │   │
│  │  - Output formatting                                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        COMPOSITION LAYER                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Services                                                    │   │
│  │  - Business logic orchestration                              │   │
│  │  - Dependency coordination                                   │   │
│  │  - Error handling & retry                                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
┌──────────────────────┐ ┌──────────────────┐ ┌──────────────────────┐
│   INTERFACE LAYER    │ │   DOMAIN LAYER   │ │   CONFIG LAYER       │
│ ┌──────────────────┐ │ │ ┌──────────────┐ │ │ ┌──────────────────┐ │
│ │ Adapter ABCs     │ │ │ │ Models       │ │ │ │ ConfigService    │ │
│ │ Repository ABCs  │ │ │ │ (frozen)     │ │ │ │ Config Objects   │ │
│ │ (no SDKs)        │ │ │ │ (no logic)   │ │ │ │ (Pydantic)       │ │
│ └──────────────────┘ │ │ └──────────────┘ │ │ └──────────────────┘ │
└──────────────────────┘ └──────────────────┘ └──────────────────────┘
                    │                                   │
                    ▼                                   │
┌──────────────────────────────────────────────────────────────────────┐
│                      INFRASTRUCTURE LAYER                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Adapter Implementations (*_impl.py)                         │    │
│  │  - External SDKs (OpenAI, Azure, etc.)                       │    │
│  │  - Database connections                                       │    │
│  │  - HTTP clients                                               │    │
│  │  - File system access                                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Layer Responsibilities

### 2.1 Presentation Layer (`src/fs2/cli/`)

**Purpose**: User interaction and output formatting.

**Responsibilities**:
- Parse command-line arguments (Typer)
- Format output for terminal (Rich)
- Handle user prompts and confirmations
- Display errors in user-friendly format

**Allowed Dependencies**:
- Services (via ABC interfaces)
- Models (for display)
- Config (for CLI-specific settings)

**Forbidden Dependencies**:
- Adapter implementations
- Repository implementations
- External SDKs

### 2.2 Composition Layer (`src/fs2/core/services/`)

**Purpose**: Business logic orchestration.

**Responsibilities**:
- Coordinate adapter and repository calls
- Implement retry logic and error handling
- Enforce business rules
- Aggregate results from multiple sources

**Allowed Dependencies**:
- Adapter ABCs (interfaces only)
- Repository ABCs (interfaces only)
- Models
- ConfigurationService (registry)

**Forbidden Dependencies**:
- Adapter implementations (`*_impl.py`)
- External SDKs
- Database drivers

### 2.3 Interface Layer (`src/fs2/core/adapters/`, `src/fs2/core/repos/`)

**Purpose**: Define contracts for external integrations.

**ABCs Contain**:
- Abstract method signatures
- Docstrings explaining contracts
- Domain types only (no SDK types)

**Forbidden in ABCs**:
- External SDK imports
- Implementation details
- Concrete business logic

### 2.4 Domain Layer (`src/fs2/core/models/`)

**Purpose**: Shared data structures.

**Characteristics**:
- Frozen dataclasses (`@dataclass(frozen=True)`)
- No business logic
- Importable by all layers
- Pure value objects

**Forbidden**:
- Imports from services, adapters, repos
- Methods with side effects
- Mutable state

### 2.5 Config Layer (`src/fs2/config/`)

**Purpose**: Configuration loading and validation.

**Characteristics**:
- Pydantic models for type safety
- Multi-source loading (YAML, env, secrets)
- Placeholder expansion (`${VAR}`)
- Fail-fast validation

**Forbidden**:
- Imports from `fs2.core.*`
- Business logic
- External SDK types

### 2.6 Infrastructure Layer (`src/fs2/core/adapters/*_impl.py`)

**Purpose**: External system integration.

**Allowed**:
- External SDK imports
- HTTP clients
- Database drivers
- File system access

**Responsibilities**:
- Translate SDK exceptions to domain exceptions
- Convert SDK types to domain types
- Handle connection management
- Implement retry/circuit breaker patterns

<!-- USER CONTENT START -->
<!-- Add project-specific layer responsibilities here -->
<!-- USER CONTENT END -->

---

## 3. Dependency Rules

### 3.1 Allowed Dependencies Matrix

| From Layer | To Layer | Allowed |
|------------|----------|---------|
| CLI | Services | Yes (ABCs) |
| CLI | Models | Yes |
| CLI | Config | Yes |
| Services | Adapter ABCs | Yes |
| Services | Repo ABCs | Yes |
| Services | Models | Yes |
| Services | Config | Yes |
| Adapter ABCs | Models | Yes |
| Adapter ABCs | Domain Exceptions | Yes |
| Adapter Impl | ABC | Yes |
| Adapter Impl | SDKs | Yes |
| Adapter Impl | Config | Yes |
| Models | Standard Lib | Yes |

### 3.2 Forbidden Dependencies

| From Layer | To Layer | Reason |
|------------|----------|--------|
| Adapters | Services | Prevents circular deps |
| Repos | Services | Prevents circular deps |
| Models | Core | Models are shared language |
| Config | Core | Config loads before core |
| Services | Adapter Impl | Violates abstraction |
| ABCs | SDKs | Leaks implementation |

### 3.3 Import Guard Pattern

```python
# Use TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService

class SampleAdapter(ABC):
    @abstractmethod
    def __init__(self, config: "ConfigurationService") -> None:
        ...
```

<!-- USER CONTENT START -->
<!-- Add project-specific dependency rules here -->
<!-- USER CONTENT END -->

---

## 4. Data Flow

### 4.1 Request Flow (CLI → Infrastructure)

```
1. CLI receives user command
   └─> Parses arguments via Typer

2. CLI creates/retrieves Service
   └─> Injects ConfigurationService + Adapter ABCs

3. Service executes business logic
   └─> Calls adapter.method(domain_data)

4. Adapter impl handles external call
   └─> Translates domain → SDK types
   └─> Makes SDK call
   └─> Translates SDK → domain types
   └─> Returns ProcessResult
```

### 4.2 Response Flow (Infrastructure → CLI)

```
1. Adapter returns ProcessResult
   └─> Success or failure with domain types

2. Service aggregates/processes results
   └─> Applies business rules
   └─> Returns domain result

3. CLI formats output
   └─> Uses Rich for terminal display
   └─> Shows success/error to user
```

### 4.3 Configuration Flow

```
1. Application starts
   └─> ConfigurationService initializes

2. Config sources loaded (priority order)
   └─> Environment variables (FS2_*)
   └─> Project YAML (.fs2/config.yaml)
   └─> User YAML (~/.config/fs2/config.yaml)
   └─> Defaults in code

3. Placeholder expansion
   └─> ${VAR_NAME} → actual values

4. Validation
   └─> Pydantic validates types
   └─> Security checks (no literal secrets)
   └─> Fail-fast on errors

5. Components request configs
   └─> config.require(ComponentConfig)
   └─> Returns typed config object
```

<!-- USER CONTENT START -->
<!-- Add project-specific data flows here -->
<!-- USER CONTENT END -->

---

## 5. Component Interaction Contracts

### 5.1 ConfigurationService Contract

```python
class ConfigurationService(ABC):
    """Registry for typed configuration objects."""

    @abstractmethod
    def require(self, config_type: type[T]) -> T:
        """
        Get configuration of specified type.

        Returns: Validated config instance
        Raises: MissingConfigurationError if not found
        """
        ...

    @abstractmethod
    def get(self, config_type: type[T]) -> T | None:
        """
        Get configuration or None if not found.

        Returns: Config instance or None
        """
        ...
```

### 5.2 Adapter Contract

```python
class Adapter(ABC):
    """Base contract for all adapters."""

    @abstractmethod
    def __init__(self, config: "ConfigurationService") -> None:
        """
        Initialize with configuration registry.

        Contract:
        - Extract own config via config.require(AdapterConfig)
        - Do NOT store ConfigurationService reference
        - Initialize any SDK clients
        """
        ...
```

### 5.3 ProcessResult Contract

```python
@dataclass(frozen=True)
class ProcessResult:
    """
    Immutable result of adapter/service operations.

    Contract:
    - success=True: value contains result, error is None
    - success=False: error contains message, value may be None
    - Use ok()/fail() factory methods
    """
    success: bool
    value: Any = None
    error: str | None = None
```

<!-- USER CONTENT START -->
<!-- Add project-specific contracts here -->
<!-- USER CONTENT END -->

---

## 6. Anti-Patterns (Reviewer Checklist)

### 6.1 Dependency Violations

| Anti-Pattern | Symptom | Fix |
|--------------|---------|-----|
| Service imports SDK | `from openai import ...` in service | Move to adapter impl |
| Adapter imports service | `from fs2.core.services import ...` | Invert dependency |
| Config imports core | `from fs2.core import ...` | Remove import |

### 6.2 Concept Leakage

| Anti-Pattern | Symptom | Fix |
|--------------|---------|-----|
| Composition extracts config | `config.require()` in CLI/main | Move to component |
| SDK type in signature | `def process(client: OpenAI)` | Use domain type |
| SDK exception escapes | `raise OpenAIError` | Translate to domain |

### 6.3 Test Violations

| Anti-Pattern | Symptom | Fix |
|--------------|---------|-----|
| Mock instead of fake | `Mock(spec=Adapter)` | Implement FakeAdapter |
| Network in test | `requests.get()` | Use fake/fixture |
| Shared mutable state | Global modified in test | Use fixtures |

### 6.4 Model Violations

| Anti-Pattern | Symptom | Fix |
|--------------|---------|-----|
| Mutable model | Missing `frozen=True` | Add to @dataclass |
| Logic in model | Methods with side effects | Move to service |
| Model imports core | `from fs2.core.services` | Remove import |

<!-- USER CONTENT START -->
<!-- Add project-specific anti-patterns here -->
<!-- USER CONTENT END -->

---

## 7. Technology Stack

### 7.1 Core Dependencies

| Component | Technology | Purpose |
|-----------|------------|---------|
| Package Manager | uv | Fast, reliable Python packaging |
| Config | Pydantic v2 | Type-safe configuration |
| CLI | Typer | Argument parsing |
| Terminal | Rich | Formatted output |
| Testing | pytest | Test framework |
| Linting | ruff | Fast Python linter |

### 7.2 Python Version

- **Minimum**: Python 3.12
- **Typing**: Modern typing features (generics, unions, etc.)

### 7.3 Project Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project metadata, dependencies |
| `justfile` | Task runner commands |
| `.fs2/config.yaml` | Project configuration |
| `.fs2/secrets.env` | Secret placeholders |

<!-- USER CONTENT START -->
<!-- Add project-specific technology notes here -->
<!-- USER CONTENT END -->

---

## 8. Deployment & Integration

### 8.1 Entry Points

```toml
# pyproject.toml
[project.scripts]
fs2 = "fs2.cli.main:app"
```

### 8.2 Environment Configuration

```bash
# Required environment variables
export FS2_LOG__ADAPTER__MIN_LEVEL=INFO

# Optional overrides
export FS2_SAMPLE__ADAPTER__TIMEOUT=60
```

### 8.3 Development Setup

```bash
# Install dependencies
uv sync --extra dev

# Run tests
just test

# Lint code
just lint

# Auto-fix
just fix
```

<!-- USER CONTENT START -->
<!-- Add project-specific deployment notes here -->
<!-- USER CONTENT END -->

---

## 9. Extension Points

### 9.1 Adding New Adapter

1. Create ABC in `src/fs2/core/adapters/{name}_adapter.py`
2. Create fake in `src/fs2/core/adapters/{name}_adapter_fake.py`
3. Create impl in `src/fs2/core/adapters/{name}_adapter_{impl}.py`
4. Add config type in `src/fs2/config/objects.py`
5. Register in `YAML_CONFIG_TYPES`
6. Write tests in `tests/unit/adapters/`

### 9.2 Adding New Service

1. Create service in `src/fs2/core/services/{name}_service.py`
2. Define dependencies (adapter ABCs, config)
3. Add config type if needed
4. Write tests with fakes in `tests/unit/services/`

### 9.3 Adding New Model

1. Create frozen dataclass in `src/fs2/core/models/{name}.py`
2. Export from `src/fs2/core/models/__init__.py`
3. Write tests in `tests/unit/models/`

See [Adding Services & Adapters](../how/adding-services-adapters.md) for detailed guide.

<!-- USER CONTENT START -->
<!-- Add project-specific extension patterns here -->
<!-- USER CONTENT END -->

---

*See [Constitution](../rules/constitution.md) for principles.*
*See [Rules](rules.md) for normative statements.*
*See [Idioms](idioms.md) for implementation examples.*
