"""Documentation Test: The Complete Adapter Pattern

This test file serves as executable documentation for fs2's adapter pattern.
Read this file to understand how to:

1. Define an adapter ABC (interface)
2. Implement a Fake adapter for testing
3. Use ConfigurationService for dependency injection
4. Create services that use adapters
5. Test services with FakeConfigurationService

The SampleAdapter + SampleService are intentionally complete to serve as templates.
Copy this pattern for production adapters and services.

Architecture Overview:
```
┌─────────────────────────────────────────────────────────────┐
│                     Composition Root                         │
│  (creates ConfigurationService, adapters, services)          │
│                                                              │
│  # Config service loads YAML/env OR use Fake for tests      │
│  config = FakeConfigurationService(                          │
│      SampleServiceConfig(retry_count=3),                    │
│      SampleAdapterConfig(prefix="prod"),                    │
│  )                                                           │
│                                                              │
│  # Adapter receives registry, gets its own config internally │
│  adapter = FakeSampleAdapter(config)                        │
│                                                              │
│  # Service receives registry, gets its own config internally │
│  service = SampleService(config=config, adapter=adapter)    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     SampleService                            │
│       (receives ConfigurationService, NOT direct config)     │
│                                                              │
│   class SampleService:                                       │
│       def __init__(self, config: ConfigurationService, ...): │
│           # Service gets its OWN config - no concept leakage │
│           self._service_config = config.require(SampleServiceConfig)│
│           self._adapter = adapter                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    SampleAdapter (ABC)                       │
│          (interface only, no implementation)                 │
│                                                              │
│   class SampleAdapter(ABC):                                  │
│       @abstractmethod                                        │
│       def process(self, data, context) -> ProcessResult     │
│       def validate(self, data) -> bool                       │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│    FakeSampleAdapter     │    │   ProductionAdapter      │
│    (for testing)         │    │   (wraps real SDK)       │
│                          │    │                          │
│  - Receives registry     │    │  - Receives registry     │
│  - Gets own config       │    │  - Gets own config       │
│  - No external deps      │    │  - Imports SDK           │
└──────────────────────────┘    └──────────────────────────┘
```

CRITICAL PRINCIPLE: No Concept Leakage
- Composition root passes ConfigurationService (registry), NOT extracted configs
- Services/Adapters call config.require() internally to get their typed configs
- The composition root doesn't know what configs each component needs

Files in this pattern:
- src/fs2/config/objects.py                    - Config types (SampleServiceConfig, SampleAdapterConfig)
- src/fs2/core/adapters/sample_adapter.py      - ABC interface
- src/fs2/core/adapters/sample_adapter_fake.py - Fake implementation
- src/fs2/core/services/sample_service.py      - Service using the adapter
"""

import pytest

from fs2.config.objects import SampleAdapterConfig, SampleServiceConfig
from fs2.config.service import FakeConfigurationService
from fs2.core.adapters.exceptions import AdapterError
from fs2.core.adapters.sample_adapter_fake import FakeSampleAdapter
from fs2.core.models.process_result import ProcessResult
from fs2.core.services.sample_service import SampleService

# =============================================================================
# PART 1: Basic Adapter Usage with ConfigurationService
# =============================================================================


@pytest.mark.docs
class TestBasicAdapterUsage:
    """How to create and use an adapter with ConfigurationService."""

    def test_create_adapter_with_default_config(self):
        """
        PATTERN: Create adapter with default configuration via FakeConfigurationService.

        The simplest usage - just instantiate with defaults.
        Config controls all behavior, so defaults should be sensible.
        """
        # Arrange: Create config service with adapter config (using defaults)
        config = FakeConfigurationService(SampleAdapterConfig())

        # Act: Create adapter - it receives the registry, gets its own config internally
        adapter = FakeSampleAdapter(config)

        # Assert: Adapter is usable
        result = adapter.process("hello world")

        assert result.success is True
        assert result.value == "processed: hello world"

    def test_create_adapter_with_custom_config(self):
        """
        PATTERN: Customize adapter behavior via configuration.

        All behavior variations come from config, not subclassing.
        This makes adapters predictable and testable.
        """
        # Arrange: Create config service with custom prefix
        config = FakeConfigurationService(SampleAdapterConfig(prefix="CUSTOM"))

        # Act: Create adapter
        adapter = FakeSampleAdapter(config)
        result = adapter.process("data")

        # Assert: Config controls output
        assert result.value == "CUSTOM: data"

    def test_adapter_returns_domain_types_not_sdk_types(self):
        """
        PATTERN: Adapters return domain types, never SDK types.

        ProcessResult is a domain type defined in fs2.core.models.
        It has no external dependencies. Services can use it safely.
        """
        config = FakeConfigurationService(SampleAdapterConfig())
        adapter = FakeSampleAdapter(config)

        # Act
        result = adapter.process("test")

        # Assert: Result is our domain type
        assert isinstance(result, ProcessResult)
        assert hasattr(result, "success")
        assert hasattr(result, "value")
        assert hasattr(result, "error")
        assert hasattr(result, "metadata")


# =============================================================================
# PART 2: Error Handling Pattern
# =============================================================================


@pytest.mark.docs
class TestErrorHandlingPattern:
    """How adapters handle and report errors."""

    def test_validation_raises_domain_exception(self):
        """
        PATTERN: Adapters raise domain exceptions, not SDK exceptions.

        AdapterError is defined in fs2.core.adapters.exceptions.
        Services catch AdapterError, not SDK-specific exceptions.
        Error messages are actionable (tell user how to fix).
        """
        config = FakeConfigurationService(SampleAdapterConfig(fail_on_empty=True))
        adapter = FakeSampleAdapter(config)

        # Act & Assert: Domain exception raised
        with pytest.raises(AdapterError) as exc_info:
            adapter.validate("")

        # Assert: Message is actionable
        assert "cannot be empty" in str(exc_info.value)
        assert "fail_on_empty=False" in str(exc_info.value)  # How to fix

    def test_process_returns_failure_instead_of_raising(self):
        """
        PATTERN: process() returns ProcessResult.fail() for expected failures.

        Use exceptions for unexpected errors (bugs, network issues).
        Use ProcessResult.fail() for expected failures (invalid input).
        This lets callers handle failures without try/except.
        """
        config = FakeConfigurationService(SampleAdapterConfig(fail_on_empty=True))
        adapter = FakeSampleAdapter(config)

        # Act: Process empty input (expected failure)
        result = adapter.process("   ")  # Whitespace only

        # Assert: Failure returned, not raised
        assert result.success is False
        assert result.error is not None
        assert "cannot be empty" in result.error

    def test_simulated_errors_for_testing_error_paths(self):
        """
        PATTERN: Config can simulate errors for testing.

        In tests, you need to verify error handling code paths.
        Instead of mocking, configure the fake to return errors.
        """
        # Arrange: Configure adapter to simulate an error
        config = FakeConfigurationService(
            SampleAdapterConfig(simulate_error="Simulated network timeout")
        )
        adapter = FakeSampleAdapter(config)

        # Act: Any call will return the configured error
        result = adapter.process("valid input")

        # Assert: Error path exercised
        assert result.success is False
        assert result.error == "Simulated network timeout"


# =============================================================================
# PART 3: Context Passing Pattern
# =============================================================================


@pytest.mark.docs
class TestContextPassingPattern:
    """How to pass trace context through adapters."""

    def test_context_flows_through_to_result(self):
        """
        PATTERN: Pass trace context through adapter calls.

        Context (trace_id, user_id, etc.) enables:
        - Distributed tracing
        - Audit logging
        - Debugging

        Adapters pass context to ProcessResult metadata.
        """
        config = FakeConfigurationService(SampleAdapterConfig())
        adapter = FakeSampleAdapter(config)

        # Arrange: Create context
        context = {
            "trace_id": "abc-123",
            "user_id": "user-456",
            "request_id": "req-789",
        }

        # Act: Pass context to adapter
        result = adapter.process("data", context=context)

        # Assert: Context available in result metadata
        assert result.metadata["context"] == context
        assert result.metadata["context"]["trace_id"] == "abc-123"

    def test_context_is_optional(self):
        """
        PATTERN: Context is optional for simpler use cases.

        Not every call needs tracing. Make it optional.
        """
        config = FakeConfigurationService(SampleAdapterConfig())
        adapter = FakeSampleAdapter(config)

        # Act: No context provided
        result = adapter.process("data")

        # Assert: Works without context
        assert result.success is True
        assert result.metadata.get("context") == {}


# =============================================================================
# PART 4: Testing Services with Fake Adapters
# =============================================================================


@pytest.mark.docs
class TestServiceWithFakeAdapter:
    """How to test services using FakeConfigurationService and fake adapters.

    SampleService is defined in src/fs2/core/services/sample_service.py.
    It demonstrates:
    - Constructor receives ConfigurationService (registry), NOT direct config
    - Service calls config.require() internally (no concept leakage)
    - Depending on ABC, not implementation
    - Config-driven behavior (retry, validation, timing)
    """

    def test_service_with_successful_adapter(self):
        """
        PATTERN: Test service happy path with FakeConfigurationService.

        1. Create FakeConfigurationService with both configs
        2. Create fake adapter (receives registry)
        3. Create service (receives same registry)
        4. Call service and verify result

        CRITICAL: Both adapter and service receive the SAME registry.
        They each call config.require() internally for their own config.
        """
        # Arrange: Create config service with BOTH service and adapter configs
        config = FakeConfigurationService(
            SampleServiceConfig(validate_before_process=True),
            SampleAdapterConfig(prefix="service-test"),
        )

        # Create adapter - receives registry, gets its own config internally
        adapter = FakeSampleAdapter(config)

        # Create service - receives SAME registry, gets its own config internally
        service = SampleService(config=config, adapter=adapter)

        # Act
        result = service.process("hello")

        # Assert
        assert result.success is True
        assert result.value == "service-test: hello"

    def test_service_handles_adapter_validation_error(self):
        """
        PATTERN: Test service error handling with configured fake.

        Configure fake to fail, then verify service handles it.
        """
        # Arrange: Configure to fail on empty
        config = FakeConfigurationService(
            SampleServiceConfig(validate_before_process=True),
            SampleAdapterConfig(fail_on_empty=True),
        )
        adapter = FakeSampleAdapter(config)
        service = SampleService(config=config, adapter=adapter)

        # Act: Pass invalid input
        result = service.process("")

        # Assert: Service handled the error
        assert result.success is False
        assert "Validation failed" in result.error

    def test_service_retry_behavior(self):
        """
        PATTERN: Test service retry logic via config.

        Service behavior comes from SampleServiceConfig, not hardcoded.
        """
        # Arrange: Configure adapter to fail, service to retry
        config = FakeConfigurationService(
            SampleServiceConfig(
                retry_count=2,  # Will try 3 times total
                validate_before_process=False,
            ),
            SampleAdapterConfig(simulate_error="Temporary failure"),
        )
        adapter = FakeSampleAdapter(config)
        service = SampleService(config=config, adapter=adapter)

        # Act
        result = service.process("data")

        # Assert: All retries exhausted
        assert result.success is False
        assert result.metadata.get("attempts") == 3  # 1 initial + 2 retries

    def test_service_with_timing_enabled(self):
        """
        PATTERN: Config can enable optional features like timing.
        """
        # Arrange: Enable timing
        config = FakeConfigurationService(
            SampleServiceConfig(include_timing=True),
            SampleAdapterConfig(prefix="timed"),
        )
        adapter = FakeSampleAdapter(config)
        service = SampleService(config=config, adapter=adapter)

        # Act
        result = service.process("data")

        # Assert: Timing metadata included
        assert result.success is True
        assert "duration_ms" in result.metadata

    def test_verify_adapter_was_called_correctly(self):
        """
        PATTERN: Verify adapter calls using call_history.

        FakeSampleAdapter records all calls for verification.
        Use this to ensure service calls adapter correctly.
        """
        # Arrange
        config = FakeConfigurationService(
            SampleServiceConfig(validate_before_process=True),
            SampleAdapterConfig(),
        )
        adapter = FakeSampleAdapter(config)
        service = SampleService(config=config, adapter=adapter)

        # Act
        service.process("test-data")

        # Assert: Check call history
        # Service validates first (if configured), then calls process()
        # process() also calls validate() internally
        validate_calls = [c for c in adapter.call_history if c["method"] == "validate"]
        process_calls = [c for c in adapter.call_history if c["method"] == "process"]

        assert len(validate_calls) >= 1  # At least service's validate call
        assert len(process_calls) == 1
        assert process_calls[0]["args"] == ("test-data",)

    def test_service_batch_processing(self):
        """
        PATTERN: Services can provide batch operations.

        SampleService.process_batch() shows how to handle multiple items.
        """
        # Arrange
        config = FakeConfigurationService(
            SampleServiceConfig(validate_before_process=False),
            SampleAdapterConfig(prefix="batch"),
        )
        adapter = FakeSampleAdapter(config)
        service = SampleService(config=config, adapter=adapter)

        # Act: Process multiple items
        results = service.process_batch(["a", "b", "c"])

        # Assert: All processed
        assert len(results) == 3
        assert all(r.success for r in results)
        assert results[0].value == "batch: a"
        assert results[1].value == "batch: b"
        assert results[2].value == "batch: c"

    def test_service_validate_only(self):
        """
        PATTERN: Services can expose adapter methods selectively.

        SampleService.validate_only() wraps adapter.validate()
        for pre-flight checks.
        """
        # Arrange
        config = FakeConfigurationService(
            SampleServiceConfig(),
            SampleAdapterConfig(max_length=10),
        )
        adapter = FakeSampleAdapter(config)
        service = SampleService(config=config, adapter=adapter)

        # Act: Validate without processing
        valid_result = service.validate_only("short")
        invalid_result = service.validate_only("this is way too long")

        # Assert
        assert valid_result.success is True
        assert invalid_result.success is False
        assert "exceeds maximum length" in invalid_result.error


# =============================================================================
# PART 5: Configuration Integration Pattern
# =============================================================================


@pytest.mark.docs
class TestConfigurationIntegration:
    """How adapters integrate with ConfigurationService."""

    def test_adapter_config_from_dict(self):
        """
        PATTERN: Create adapter config from dictionary.

        In production, FS2ConfigurationService loads from YAML/env.
        This shows the dict -> config object -> FakeConfigurationService flow.
        """
        # Simulate config loaded from YAML
        config_dict = {
            "prefix": "from-yaml",
            "max_length": 100,
            "fail_on_empty": False,
        }

        # Create config from dict (like FS2ConfigurationService would)
        adapter_config = SampleAdapterConfig(**config_dict)

        # Create config service and adapter
        config = FakeConfigurationService(adapter_config)
        adapter = FakeSampleAdapter(config)
        result = adapter.process("")  # Empty allowed

        # Assert: Config applied
        assert result.success is True
        assert result.value == "from-yaml: "

    def test_different_configs_for_different_environments(self):
        """
        PATTERN: Same adapter, different config per environment.

        Dev: Lenient validation, verbose prefix
        Prod: Strict validation, minimal prefix
        Test: Whatever the test needs
        """
        # Dev config
        dev_config = FakeConfigurationService(
            SampleAdapterConfig(
                prefix="[DEV]",
                max_length=0,  # Unlimited
                fail_on_empty=False,  # Lenient
            )
        )

        # Prod config
        prod_config = FakeConfigurationService(
            SampleAdapterConfig(
                prefix="",
                max_length=1000,  # Limited
                fail_on_empty=True,  # Strict
            )
        )

        # Same adapter class, different behavior
        dev_adapter = FakeSampleAdapter(dev_config)
        prod_adapter = FakeSampleAdapter(prod_config)

        # Dev allows empty
        assert dev_adapter.process("").success is True

        # Prod rejects empty
        assert prod_adapter.process("").success is False


# =============================================================================
# SUMMARY: The Complete Pattern
# =============================================================================


@pytest.mark.docs
def test_complete_pattern_summary():
    """
    THE COMPLETE ADAPTER + SERVICE PATTERN - Summary

    FILES:
    - src/fs2/config/objects.py                    -> Config types
    - src/fs2/core/adapters/sample_adapter.py      -> ABC interface
    - src/fs2/core/adapters/sample_adapter_fake.py -> Fake implementation
    - src/fs2/core/services/sample_service.py      -> Service using adapter

    1. DEFINE CONFIG TYPES (config/objects.py):
       - Pydantic BaseModel with __config_path__
       - Validation via @field_validator
       - Registered in YAML_CONFIG_TYPES for auto-loading

    2. DEFINE ADAPTER ABC (sample_adapter.py):
       - Abstract methods only
       - Domain types only (ProcessResult, not SDK types)
       - No implementation details

    3. IMPLEMENT FAKE ADAPTER (sample_adapter_fake.py):
       - Inherits from ABC
       - Constructor receives ConfigurationService (registry)
       - Calls config.require(SampleAdapterConfig) internally
       - Behavior controlled by config
       - Records calls for test verification
       - Raises AdapterError, not SDK exceptions

    4. IMPLEMENT PRODUCTION ADAPTER (sample_adapter_prod.py - future):
       - Same pattern as Fake
       - Constructor receives ConfigurationService
       - Wraps real SDK
       - Translates SDK exceptions -> AdapterError
       - Translates SDK types -> domain types

    5. DEFINE SERVICE (sample_service.py):
       - Constructor receives ConfigurationService (registry) AND adapter
       - Calls config.require(SampleServiceConfig) internally
       - Depends on adapter ABC, not implementation
       - Config controls service behavior (retry, timing, etc.)
       - Uses domain types only

    6. WIRE IN COMPOSITION ROOT:
       ```python
       # Production: FS2ConfigurationService loads from YAML/env
       config = FS2ConfigurationService()

       # Testing: FakeConfigurationService with explicit configs
       config = FakeConfigurationService(
           SampleServiceConfig(retry_count=3),
           SampleAdapterConfig(prefix="prod"),
       )

       # Create adapter - receives registry
       adapter = FakeSampleAdapter(config)  # or ProductionAdapter(config)

       # Create service - receives SAME registry
       service = SampleService(config=config, adapter=adapter)

       # Use service
       result = service.process("data")
       ```

    7. CRITICAL: NO CONCEPT LEAKAGE
       - Composition root passes ConfigurationService (registry)
       - NEVER extract configs for components
       - Components call config.require() internally
       - Composition root doesn't know what configs each component needs

    This test passes if you've read and understood the pattern!
    """
    # This test exists as documentation
    assert True, "You've learned the complete adapter + service pattern!"


@pytest.mark.docs
def test_end_to_end_example():
    """
    COMPLETE END-TO-END EXAMPLE

    This test demonstrates the entire pattern in one place.
    Copy this as a starting point for new adapters/services.
    """
    # =================================================================
    # STEP 1: Create ConfigurationService with all needed configs
    # =================================================================
    # In production: config = FS2ConfigurationService()  # Loads from YAML/env
    # In tests: use FakeConfigurationService with explicit configs
    config = FakeConfigurationService(
        SampleServiceConfig(
            retry_count=1,
            validate_before_process=True,
            include_timing=True,
        ),
        SampleAdapterConfig(
            prefix="example",
            max_length=100,
            fail_on_empty=True,
        ),
    )

    # =================================================================
    # STEP 2: Create adapter - receives registry, gets its own config
    # =================================================================
    adapter = FakeSampleAdapter(config)

    # =================================================================
    # STEP 3: Create service - receives SAME registry AND adapter
    # =================================================================
    service = SampleService(config=config, adapter=adapter)

    # =================================================================
    # STEP 4: Use the service
    # =================================================================
    # Happy path
    result = service.process("Hello, World!", context={"user_id": "123"})

    assert result.success is True
    assert result.value == "example: Hello, World!"
    assert "duration_ms" in result.metadata  # Timing enabled

    # Error path
    error_result = service.process("")  # Empty input

    assert error_result.success is False
    assert "Validation failed" in error_result.error

    # Batch processing
    batch_results = service.process_batch(["a", "b", "c"])

    assert len(batch_results) == 3
    assert all(r.success for r in batch_results)
