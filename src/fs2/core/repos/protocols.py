"""
Repository protocol definitions (ABC interfaces).

This module defines abstract base classes for all repositories in the system.
Repositories provide data access abstractions, hiding storage implementation details.

Architecture Rules:
- Repositories MUST NOT import from services (no upward dependencies)
- Repositories MUST NOT expose database/HTTP types in their interfaces
- Interface methods use domain language (find_by_id, save) not SQL/HTTP
- All repositories inherit from ABC with @abstractmethod decorators
- Each repository has a corresponding Fake implementation for testing

Phase 2+ will add repository interfaces as needed.

See: docs/plans/002-project-skele/project-skele-spec.md § AC4
"""
