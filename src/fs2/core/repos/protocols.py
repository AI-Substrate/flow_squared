"""
Repository protocol definitions (ABC interfaces).

This module defines abstract base classes and protocols for all repositories
in the system. Repositories provide data access abstractions, hiding storage
implementation details.

Architecture Rules:
- Repositories MUST NOT import from services (no upward dependencies)
- Repositories MUST NOT expose database/HTTP types in their interfaces
- Interface methods use domain language (find_by_id, save) not SQL/HTTP
- All repositories inherit from ABC with @abstractmethod decorators
- Each repository has a corresponding Fake implementation for testing

See: docs/plans/002-project-skele/project-skele-spec.md § AC4
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ConnectionProvider(Protocol):
    """Protocol for async database connection access.

    Decouples graph-storage and search domains from the server.Database class,
    preventing reverse dependencies. Any class with a matching
    ``connection()`` async context manager satisfies this protocol.

    Structural subtyping: no inheritance needed — just implement
    a ``connection()`` method that returns an async context manager.
    """

    def connection(self) -> Any: ...
