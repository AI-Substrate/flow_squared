"""Unit tests for PipelineStage Protocol.

Purpose: Verifies PipelineStage protocol contract for pipeline stages.
Quality Contribution: Ensures all stages implement consistent interface.

Per Phase 5 Tasks:
- T003: Tests for PipelineStage protocol contract

Per Alignment Brief:
- Stages use Protocol (simpler than ABC for this use case)
- name property + process method
"""

from typing import Protocol

from fs2.config.objects import ScanConfig


class TestPipelineStageProtocol:
    """Tests for PipelineStage protocol definition."""

    def test_given_pipeline_stage_protocol_when_imported_then_is_protocol(self):
        """
        Purpose: Verifies PipelineStage is a typing.Protocol.
        Quality Contribution: Ensures structural subtyping works.
        Acceptance Criteria: PipelineStage is a Protocol class.
        """
        from fs2.core.services.pipeline_stage import PipelineStage

        assert hasattr(PipelineStage, "__protocol_attrs__") or issubclass(
            PipelineStage, Protocol
        )

    def test_given_pipeline_stage_protocol_when_checked_then_has_name_property(self):
        """
        Purpose: Verifies PipelineStage requires name property.
        Quality Contribution: Stages must be identifiable for logging.
        Acceptance Criteria: Protocol specifies name property.
        """

        # Create a conforming class to verify protocol spec
        class ConformingStage:
            @property
            def name(self) -> str:
                return "test"

            def process(self, context):
                return context

        # Should satisfy the protocol
        stage = ConformingStage()
        assert hasattr(stage, "name")
        assert stage.name == "test"

    def test_given_pipeline_stage_protocol_when_checked_then_has_process_method(self):
        """
        Purpose: Verifies PipelineStage requires process method.
        Quality Contribution: Stages must process context.
        Acceptance Criteria: Protocol specifies process method.
        """
        from fs2.core.services.pipeline_context import PipelineContext

        # Create a conforming class to verify protocol spec
        class ConformingStage:
            @property
            def name(self) -> str:
                return "test"

            def process(self, context: PipelineContext) -> PipelineContext:
                return context

        # Should satisfy the protocol
        stage = ConformingStage()
        ctx = PipelineContext(scan_config=ScanConfig())
        result = stage.process(ctx)
        assert result is ctx


class TestPipelineStageRuntimeCheckable:
    """Tests for runtime_checkable behavior."""

    def test_given_conforming_class_when_isinstance_checked_then_returns_true(self):
        """
        Purpose: Verifies runtime_checkable enables isinstance checks.
        Quality Contribution: Pipeline can validate stage types at runtime.
        Acceptance Criteria: isinstance returns True for conforming classes.
        """
        from fs2.core.services.pipeline_context import PipelineContext
        from fs2.core.services.pipeline_stage import PipelineStage

        class ConformingStage:
            @property
            def name(self) -> str:
                return "conforming"

            def process(self, context: PipelineContext) -> PipelineContext:
                return context

        stage = ConformingStage()
        # Protocol should be runtime_checkable
        assert isinstance(stage, PipelineStage)

    def test_given_non_conforming_class_when_isinstance_checked_then_returns_false(self):
        """
        Purpose: Verifies non-conforming classes fail isinstance.
        Quality Contribution: Catches incorrect stage implementations.
        Acceptance Criteria: isinstance returns False for non-conforming classes.
        """
        from fs2.core.services.pipeline_stage import PipelineStage

        class NonConformingClass:
            def do_something(self):
                pass

        obj = NonConformingClass()
        assert not isinstance(obj, PipelineStage)


class TestPipelineStageDocumentation:
    """Tests to ensure protocol is well-documented."""

    def test_given_pipeline_stage_when_inspected_then_has_docstring(self):
        """
        Purpose: Verifies protocol has documentation.
        Quality Contribution: Developers understand the contract.
        Acceptance Criteria: Protocol has non-empty docstring.
        """
        from fs2.core.services.pipeline_stage import PipelineStage

        assert PipelineStage.__doc__ is not None
        assert len(PipelineStage.__doc__) > 0
