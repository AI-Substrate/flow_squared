"""
Adapter protocol definitions (ABC interfaces).

This module defines abstract base classes for all adapters in the system.
Adapters wrap external SDKs and services, exposing only domain types.

Architecture Rules:
- Adapters MUST NOT import from services (no upward dependencies)
- Adapters MUST NOT expose vendor SDK types in their interfaces
- All adapters inherit from ABC with @abstractmethod decorators
- Each adapter has a corresponding Fake implementation for testing

Phase 2 will add:
- LogAdapter: Logging interface (debug, info, warning, error)

See: docs/plans/002-project-skele/project-skele-spec.md § AC4, AC7
"""
