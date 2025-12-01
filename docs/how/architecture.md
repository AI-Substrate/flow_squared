# Architecture Overview

fs2 implements **Clean Architecture** with strict dependency boundaries.

## Layer Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Presentation                         │
│                      fs2.cli                            │
└─────────────────────────┬───────────────────────────────┘
                          │ imports
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    Composition                          │
│                  fs2.core.services                      │
└───────────┬─────────────────────────────┬───────────────┘
            │ imports                     │ imports
            ▼                             ▼
┌─────────────────────┐       ┌─────────────────────┐
│     Interface       │       │       Domain        │
│ fs2.core.adapters   │       │   fs2.core.models   │
│   (ABCs only)       │       │  (frozen dataclass) │
└─────────┬───────────┘       └─────────────────────┘
          │ implemented by
          ▼
┌─────────────────────────────────────────────────────────┐
│                   Infrastructure                        │
│          fs2.core.adapters.*_impl.py                    │
│              (imports external SDKs)                    │
└─────────────────────────────────────────────────────────┘
```

## Import Rules

| Layer | Can Import | Cannot Import |
|-------|------------|---------------|
| `cli/` | services, config | adapters/*_impl.py |
| `services/` | adapters (ABCs), models, config | external SDKs |
| `adapters/*.py` (ABCs) | models only | external SDKs, services |
| `adapters/*_impl.py` | ABCs, models, external SDKs | services |
| `models/` | stdlib only | anything from fs2 |
| `config/` | pydantic, stdlib | fs2.core.* |

## Key Principle

**No SDK types in ABCs** - Adapter interfaces use only domain types (`ProcessResult`, `LogEntry`). SDK-specific types stay in `*_impl.py` files.

## Further Reading

- [Adding Services & Adapters](adding-services-adapters.md) - Step-by-step guide
- [Dependency Injection](di.md) - DI patterns
