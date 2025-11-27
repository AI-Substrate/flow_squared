"""FakeSampleAdapter - Test double demonstrating the adapter implementation pattern.

This is the canonical example of how to implement an adapter ABC.
Use this as a template for production adapters.

Architecture:
- Inherits from SampleAdapter ABC
- Receives ConfigurationService (registry) via constructor
- Adapter calls config.require() internally to get its typed config
- No external SDK dependencies (it's a fake)
- Production adapters follow the same pattern but wrap real SDKs

Pattern demonstrates:
1. Constructor receives ConfigurationService (registry), NOT extracted config
2. Adapter calls config.require(SampleAdapterConfig) internally
3. Methods use config to determine behavior
4. Returns domain types (ProcessResult), not SDK types
5. Raises domain exceptions (AdapterError), not SDK exceptions

CRITICAL: The composition root passes ConfigurationService (the registry),
NOT specific config types. Extracting SampleAdapterConfig beforehand would
be CONCEPT LEAKAGE - the composition root shouldn't know what configs
FakeSampleAdapter needs internally. That's FakeSampleAdapter's business.
"""

from typing import TYPE_CHECKING, Any

from fs2.config.objects import SampleAdapterConfig
from fs2.core.adapters.exceptions import AdapterError
from fs2.core.adapters.sample_adapter import SampleAdapter
from fs2.core.models.process_result import ProcessResult

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


class FakeSampleAdapter(SampleAdapter):
    """Fake implementation of SampleAdapter for testing.

    This implementation demonstrates the full adapter pattern:
    - Constructor receives ConfigurationService (registry), not specific config
    - Adapter calls config.require() internally (no concept leakage)
    - Domain-only return types (ProcessResult)
    - Domain-only exceptions (AdapterError)
    - Behavior controlled by config (no hardcoded logic)

    Usage in tests:
        ```python
        # Use FakeConfigurationService with typed configs
        config = FakeConfigurationService(
            SampleAdapterConfig(prefix="test", max_length=100),
        )

        # Adapter receives registry, gets its own config internally
        adapter = FakeSampleAdapter(config)

        # Use adapter
        result = adapter.process("hello")
        assert result.success
        assert result.value == "test: hello"
        ```

    Usage with FS2ConfigurationService (production pattern):
        ```python
        # In composition root - pass registry, NOT extracted config
        config = FS2ConfigurationService()  # Loads YAML/env
        adapter = FakeSampleAdapter(config)  # Gets its own config internally

        # Inject adapter into service (service also gets registry)
        service = SampleService(config=config, adapter=adapter)
        ```
    """

    def __init__(self, config: "ConfigurationService"):
        """Initialize with ConfigurationService registry.

        Args:
            config: ConfigurationService registry (NOT SampleAdapterConfig).
                    Adapter will call config.require(SampleAdapterConfig) internally.

        Raises:
            MissingConfigurationError: If SampleAdapterConfig not in registry.
        """
        # Adapter gets its own config - composition root doesn't extract it
        self._adapter_config = config.require(SampleAdapterConfig)
        self._call_history: list[dict[str, Any]] = []

    @property
    def call_history(self) -> list[dict[str, Any]]:
        """Access recorded calls for test assertions.

        Returns:
            List of dicts with 'method', 'args', 'kwargs' for each call.
        """
        return self._call_history

    def process(
        self, input_data: str, context: dict[str, Any] | None = None
    ) -> ProcessResult:
        """Process input data according to configuration.

        Behavior controlled by config:
        - config.prefix: Prepended to output
        - config.simulate_error: Returns failure if set
        - config.fail_on_empty: Fails on empty input if True

        Args:
            input_data: The data to process
            context: Optional context (trace_id, user_id, etc.)

        Returns:
            ProcessResult with success/failure and metadata
        """
        # Record the call for test verification
        self._call_history.append(
            {
                "method": "process",
                "args": (input_data,),
                "kwargs": {"context": context},
            }
        )

        # Check for simulated error (useful for testing error paths)
        if self._adapter_config.simulate_error:
            return ProcessResult.fail(
                error=self._adapter_config.simulate_error,
                input_data=input_data,
            )

        # Validate first (demonstrates validate + process flow)
        try:
            self.validate(input_data)
        except AdapterError as e:
            return ProcessResult.fail(error=str(e), input_data=input_data)

        # Process the data
        output = f"{self._adapter_config.prefix}: {input_data}"

        return ProcessResult.ok(
            value=output,
            input_data=input_data,
            context=context or {},
        )

    def validate(self, input_data: str) -> bool:
        """Validate input according to configuration.

        Behavior controlled by config:
        - config.fail_on_empty: Raises if input is empty
        - config.max_length: Raises if input exceeds max (0 = unlimited)

        Args:
            input_data: The data to validate

        Returns:
            True if valid

        Raises:
            AdapterError: If validation fails with actionable message
        """
        # Record the call
        self._call_history.append(
            {
                "method": "validate",
                "args": (input_data,),
                "kwargs": {},
            }
        )

        # Check empty
        if self._adapter_config.fail_on_empty and not input_data.strip():
            raise AdapterError(
                "Input cannot be empty. "
                "Provide non-whitespace input or set fail_on_empty=False in config."
            )

        # Check length
        if (
            self._adapter_config.max_length > 0
            and len(input_data) > self._adapter_config.max_length
        ):
            raise AdapterError(
                f"Input exceeds maximum length of {self._adapter_config.max_length}. "
                f"Got {len(input_data)} characters. "
                "Truncate input or increase max_length in config."
            )

        return True
