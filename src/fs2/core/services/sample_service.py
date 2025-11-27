"""SampleService - Canonical example of a service with injected dependencies.

This is the complete end-to-end example demonstrating:
1. Service receives ConfigurationService (registry) AND adapter via constructor
2. Service calls config.require() internally to get its typed config
3. Service depends on ABC types, not implementations
4. Service uses domain types only (ProcessResult, AdapterError)
5. Service is testable via FakeConfigurationService + fake adapters

Architecture:
```
┌─────────────────────────────────────────────────────────────┐
│                     Composition Root                         │
│                                                              │
│  # Create config service (loads YAML/env automatically)      │
│  config = FS2ConfigurationService()                         │
│                                                              │
│  # Create adapter (gets its own config from registry)        │
│  adapter = FakeSampleAdapter(config)                        │
│                                                              │
│  # Create service - receives registry, NOT extracted config  │
│  service = SampleService(                                    │
│      config=config,    # The registry, not SampleServiceConfig│
│      adapter=adapter,                                        │
│  )                                                           │
│                                                              │
│  # Service internally does:                                  │
│  #   self._service_config = config.require(SampleServiceConfig)│
└─────────────────────────────────────────────────────────────┘
```

CRITICAL: The composition root passes ConfigurationService (the registry),
NOT specific config types. Extracting SampleServiceConfig beforehand would
be CONCEPT LEAKAGE - the composition root shouldn't know what configs
SampleService needs internally. That's SampleService's business.

See tests/docs/test_sample_adapter_pattern.py for usage examples.
"""

from typing import TYPE_CHECKING, Any

from fs2.config.objects import SampleServiceConfig
from fs2.core.adapters.exceptions import AdapterError
from fs2.core.adapters.sample_adapter import SampleAdapter
from fs2.core.models.process_result import ProcessResult

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


class SampleService:
    """Sample service demonstrating the full composition pattern.

    This service shows:
    - Constructor receives ConfigurationService (registry), not specific config
    - Service calls config.require() internally (no concept leakage)
    - Depending on ABC (SampleAdapter), not implementation
    - Using domain types (ProcessResult, AdapterError)
    - Config-driven behavior (no hardcoded logic)
    - Testability via FakeConfigurationService + fake adapters

    Usage:
        ```python
        # In composition root - pass registry, NOT extracted config
        config = FS2ConfigurationService()
        adapter = FakeSampleAdapter(config)  # Adapter also gets registry

        service = SampleService(
            config=config,   # Registry, not SampleServiceConfig!
            adapter=adapter,
        )

        # Use the service
        result = service.process("input data")
        ```

    Testing:
        ```python
        # In tests - use FakeConfigurationService
        config = FakeConfigurationService(
            SampleServiceConfig(retry_count=3),
            SampleAdapterConfig(simulate_error="Network timeout"),
        )
        adapter = FakeSampleAdapter(config)

        service = SampleService(config=config, adapter=adapter)

        result = service.process("data")
        assert result.success is False
        assert "Network timeout" in result.error
        ```
    """

    def __init__(
        self,
        config: "ConfigurationService",
        adapter: SampleAdapter,
    ):
        """Initialize service with config registry and adapter.

        Args:
            config: ConfigurationService registry (NOT SampleServiceConfig).
                    Service will call config.require(SampleServiceConfig) internally.
            adapter: Adapter for external operations (ABC type, not impl).

        Raises:
            MissingConfigurationError: If SampleServiceConfig not in registry.
        """
        # Service gets its own config - composition root doesn't extract it
        self._service_config = config.require(SampleServiceConfig)
        self._adapter = adapter

    def process(
        self,
        data: str,
        context: dict[str, Any] | None = None,
    ) -> ProcessResult:
        """Process data through the adapter with configured behavior.

        This method demonstrates:
        - Optional validation before processing
        - Retry logic controlled by config
        - Context passing for traceability
        - Proper error handling

        Args:
            data: Input data to process
            context: Optional trace context (trace_id, user_id, etc.)

        Returns:
            ProcessResult with success/failure and metadata
        """
        import time

        start_time = time.time() if self._service_config.include_timing else None

        # Validate if configured
        if self._service_config.validate_before_process:
            try:
                self._adapter.validate(data)
            except AdapterError as e:
                return ProcessResult.fail(
                    error=f"Validation failed: {e}",
                    stage="validation",
                )

        # Process with retry
        last_error: str | None = None
        attempts = self._service_config.retry_count + 1  # +1 for initial attempt

        for attempt in range(attempts):
            result = self._adapter.process(data, context=context)

            if result.success:
                # Add timing if configured
                if self._service_config.include_timing and start_time:
                    duration_ms = (time.time() - start_time) * 1000
                    return ProcessResult.ok(
                        value=result.value,
                        duration_ms=duration_ms,
                        attempts=attempt + 1,
                        **result.metadata,
                    )
                return result

            last_error = result.error

            # Don't retry on last attempt
            if attempt < attempts - 1:
                continue

        # All attempts failed
        return ProcessResult.fail(
            error=last_error or "Unknown error",
            attempts=attempts,
            stage="processing",
        )

    def validate_only(self, data: str) -> ProcessResult:
        """Validate data without processing.

        Useful for pre-flight checks or form validation.

        Args:
            data: Input data to validate

        Returns:
            ProcessResult indicating validation success/failure
        """
        try:
            self._adapter.validate(data)
            return ProcessResult.ok(value="Valid", stage="validation")
        except AdapterError as e:
            return ProcessResult.fail(error=str(e), stage="validation")

    def process_batch(
        self,
        items: list[str],
        context: dict[str, Any] | None = None,
    ) -> list[ProcessResult]:
        """Process multiple items.

        Demonstrates batch operations with the adapter pattern.

        Args:
            items: List of items to process
            context: Shared context for all items

        Returns:
            List of ProcessResult, one per item
        """
        results = []
        for i, item in enumerate(items):
            item_context = {
                **(context or {}),
                "batch_index": i,
                "batch_size": len(items),
            }
            result = self.process(item, context=item_context)
            results.append(result)
        return results
