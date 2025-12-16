"""PipelineStage Protocol - Contract for all pipeline stages.

All stages receive and return a PipelineContext, enabling:
- Sequential composition (output of one is input to next)
- Independent testing (mock context in, assert context out)
- Future extensibility (new stages implement same protocol)

Per Alignment Brief:
- Stages use Protocol (simpler than ABC for this use case)
- name property for logging/metrics identification
- process method for context transformation
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from fs2.core.services.pipeline_context import PipelineContext


@runtime_checkable
class PipelineStage(Protocol):
    """Protocol defining the contract for pipeline stages.

    All stages receive and return a PipelineContext, enabling:
    - Sequential composition (output of one is input to next)
    - Independent testing (mock context in, assert context out)
    - Future extensibility (new stages implement same protocol)

    Implementors must provide:
    - name property: Human-readable stage name for logging and metrics
    - process method: Transform context and return it

    Example implementation:
        ```python
        class DiscoveryStage:
            @property
            def name(self) -> str:
                return "discovery"

            def process(self, context: PipelineContext) -> PipelineContext:
                # Use context.file_scanner to discover files
                context.scan_results = context.file_scanner.scan()
                return context
        ```
    """

    @property
    def name(self) -> str:
        """Human-readable stage name for logging and metrics."""
        ...

    def process(self, context: "PipelineContext") -> "PipelineContext":
        """Process the context and return updated context.

        Stages should:
        - Read what they need from context
        - Add their outputs to context
        - Collect errors in context.errors (don't raise for partial failures)
        - Return the (possibly mutated) context

        Args:
            context: Pipeline context with config, adapters, and accumulated results.

        Returns:
            The same context, possibly mutated with stage outputs.
        """
        ...
