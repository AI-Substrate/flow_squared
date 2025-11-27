"""Service composition layer - business logic orchestration.

Architecture:
- Services receive adapters and config via constructor (DI)
- Services depend on adapter ABCs, not implementations
- Services use domain types only (ProcessResult, not SDK types)
- Services are testable via fake adapters

Public API:
- SampleService: Canonical example demonstrating the full pattern
- SampleServiceConfig: Configuration for SampleService

See tests/docs/test_sample_adapter_pattern.py for complete usage documentation.
"""

from fs2.core.services.sample_service import SampleService, SampleServiceConfig

__all__ = [
    "SampleService",
    "SampleServiceConfig",
]
