"""Unit tests for SmartContentStage.

Purpose: Verifies SmartContentStage correctly:
1. Merges prior smart_content from context.prior_nodes (Subtask 001)
2. Calls SmartContentService.process_batch() for generation (T001)
3. Handles missing service gracefully (T002)
4. Records metrics and handles errors (T001)

Per Subtask 001: Graph Loading for Smart Content Preservation.
Enables hash-based skip logic (AC5/AC6) by preserving smart_content across scans.

Per Phase 6 Tasks:
- T001: Tests for stage.process() calling batch processing
- T002: Tests for graceful skip when service is None
- T003: Implementation with asyncio.run() bridge

Per Alignment Brief:
- Merge logic copies prior smart_content/smart_content_hash if content_hash matches
- Uses dataclasses.replace() for CodeNode immutability (CD03)
- Handles prior_nodes=None gracefully (first scan case)
- Stage reads smart_content_service from context (per Session 2 Insight #3)
"""

from dataclasses import replace

from fs2.config.objects import ScanConfig
from fs2.core.models.code_node import CodeNode
from fs2.core.services.pipeline_context import PipelineContext


def _make_file_node(
    file_path: str = "test.py",
    content: str = "# test",
    smart_content: str | None = None,
    smart_content_hash: str | None = None,
) -> CodeNode:
    """Helper to create a file CodeNode for testing."""
    node = CodeNode.create_file(
        file_path=file_path,
        language="python",
        ts_kind="module",
        start_byte=0,
        end_byte=len(content),
        start_line=1,
        end_line=content.count("\n") + 1,
        content=content,
    )
    # Update smart_content fields if provided
    if smart_content is not None or smart_content_hash is not None:
        node = replace(
            node,
            smart_content=smart_content,
            smart_content_hash=smart_content_hash,
        )
    return node


class TestSmartContentStageMergeLogic:
    """Tests for merging prior smart_content from context.prior_nodes.

    Per Subtask 001: When content_hash matches between fresh node and prior node,
    copy smart_content and smart_content_hash from prior to fresh.
    """

    def test_given_matching_hash_when_merging_then_copies_smart_content(self):
        """
        Purpose: Verifies merge copies smart_content when content_hash matches.
        Quality Contribution: Enables hash-based skip logic (AC5/AC6).
        Acceptance Criteria: Fresh node gets prior's smart_content and hash.

        Why: Hash match means content unchanged, reuse prior summary.
        Contract: If content_hash matches, copy smart_content + smart_content_hash.
        """
        from fs2.core.services.stages.smart_content_stage import SmartContentStage

        # Fresh node from parsing (no smart_content)
        fresh_node = _make_file_node(
            file_path="unchanged.py",
            content="# unchanged content",
        )

        # Prior node with smart_content (same content_hash because same content)
        prior_node = _make_file_node(
            file_path="unchanged.py",
            content="# unchanged content",
            smart_content="This file contains unchanged content.",
            smart_content_hash=fresh_node.content_hash,  # Must match fresh
        )

        # Set up context with prior_nodes
        context = PipelineContext(scan_config=ScanConfig())
        context.nodes = [fresh_node]
        context.prior_nodes = {prior_node.node_id: prior_node}

        # Create stage and call merge (note: we're testing merge_prior_smart_content directly)
        stage = SmartContentStage()
        merged_nodes = stage._merge_prior_smart_content(
            nodes=context.nodes,
            prior_nodes=context.prior_nodes,
        )

        # Verify smart_content was copied
        assert len(merged_nodes) == 1
        merged = merged_nodes[0]
        assert merged.smart_content == "This file contains unchanged content."
        assert merged.smart_content_hash == fresh_node.content_hash

    def test_given_different_hash_when_merging_then_skips_copy(self):
        """
        Purpose: Verifies merge skips copy when content_hash differs.
        Quality Contribution: Changed files get regenerated.
        Acceptance Criteria: Fresh node keeps smart_content=None.

        Why: Hash differs means content changed, must regenerate.
        Contract: If content_hash differs, don't copy smart_content.
        """
        from fs2.core.services.stages.smart_content_stage import SmartContentStage

        # Fresh node with NEW content
        fresh_node = _make_file_node(
            file_path="changed.py",
            content="# updated content v2",
        )

        # Prior node with OLD content (different content_hash)
        prior_node = _make_file_node(
            file_path="changed.py",
            content="# original content v1",  # Different content!
            smart_content="This was the old summary.",
            smart_content_hash="old_hash_that_wont_match",
        )

        # Set up context
        context = PipelineContext(scan_config=ScanConfig())
        context.nodes = [fresh_node]
        context.prior_nodes = {prior_node.node_id: prior_node}

        stage = SmartContentStage()
        merged_nodes = stage._merge_prior_smart_content(
            nodes=context.nodes,
            prior_nodes=context.prior_nodes,
        )

        # Verify smart_content was NOT copied (content changed)
        merged = merged_nodes[0]
        assert merged.smart_content is None
        assert merged.smart_content_hash is None

    def test_given_new_file_when_merging_then_skips_copy(self):
        """
        Purpose: Verifies merge skips copy for new files not in prior_nodes.
        Quality Contribution: New files get smart_content generated.
        Acceptance Criteria: Fresh node keeps smart_content=None.

        Why: New file has no prior state, must generate.
        Contract: If node_id not in prior_nodes, don't copy.
        """
        from fs2.core.services.stages.smart_content_stage import SmartContentStage

        # Fresh node for a brand new file
        fresh_node = _make_file_node(
            file_path="brand_new.py",
            content="# brand new file",
        )

        # Prior nodes don't include this file
        other_prior = _make_file_node(
            file_path="other.py",
            content="# other",
            smart_content="Other file summary.",
            smart_content_hash="some_hash",
        )

        context = PipelineContext(scan_config=ScanConfig())
        context.nodes = [fresh_node]
        context.prior_nodes = {other_prior.node_id: other_prior}

        stage = SmartContentStage()
        merged_nodes = stage._merge_prior_smart_content(
            nodes=context.nodes,
            prior_nodes=context.prior_nodes,
        )

        # Verify no copy (new file)
        merged = merged_nodes[0]
        assert merged.smart_content is None
        assert merged.smart_content_hash is None

    def test_given_prior_nodes_none_when_merging_then_returns_unchanged(self):
        """
        Purpose: Verifies merge handles first-scan case (prior_nodes=None).
        Quality Contribution: First scans work without error.
        Acceptance Criteria: Nodes returned unchanged, no error.

        Why: First scan has no prior graph, prior_nodes=None.
        Contract: If prior_nodes is None, return nodes unchanged.
        """
        from fs2.core.services.stages.smart_content_stage import SmartContentStage

        fresh_node = _make_file_node(
            file_path="first_scan.py",
            content="# first scan file",
        )

        context = PipelineContext(scan_config=ScanConfig())
        context.nodes = [fresh_node]
        context.prior_nodes = None  # First scan!

        stage = SmartContentStage()
        merged_nodes = stage._merge_prior_smart_content(
            nodes=context.nodes,
            prior_nodes=context.prior_nodes,
        )

        # Verify unchanged (no error)
        assert len(merged_nodes) == 1
        merged = merged_nodes[0]
        assert merged.smart_content is None
        assert merged.smart_content_hash is None
        assert merged.node_id == fresh_node.node_id

    def test_given_multiple_nodes_when_merging_then_handles_each_correctly(self):
        """
        Purpose: Verifies merge handles mix of unchanged, changed, and new nodes.
        Quality Contribution: Batch processing works correctly.
        Acceptance Criteria: Each node type handled appropriately.

        Why: Real scans have mix of unchanged/changed/new files.
        Contract: Merge logic applies per-node independently.
        """
        from fs2.core.services.stages.smart_content_stage import SmartContentStage

        # Unchanged file (should copy)
        unchanged_fresh = _make_file_node("unchanged.py", "# same")
        unchanged_prior = _make_file_node(
            "unchanged.py",
            "# same",
            smart_content="Unchanged summary.",
            smart_content_hash=unchanged_fresh.content_hash,
        )

        # Changed file (should NOT copy)
        changed_fresh = _make_file_node("changed.py", "# new version")
        changed_prior = _make_file_node(
            "changed.py",
            "# old version",
            smart_content="Old summary.",
            smart_content_hash="old_hash",
        )

        # New file (should NOT copy)
        new_fresh = _make_file_node("brand_new.py", "# new file")

        context = PipelineContext(scan_config=ScanConfig())
        context.nodes = [unchanged_fresh, changed_fresh, new_fresh]
        context.prior_nodes = {
            unchanged_prior.node_id: unchanged_prior,
            changed_prior.node_id: changed_prior,
        }

        stage = SmartContentStage()
        merged_nodes = stage._merge_prior_smart_content(
            nodes=context.nodes,
            prior_nodes=context.prior_nodes,
        )

        # Verify each node handled correctly
        assert len(merged_nodes) == 3

        # Find each node by node_id (which contains file_path)
        result_unchanged = next(
            n for n in merged_nodes if n.node_id == "file:unchanged.py"
        )
        result_changed = next(n for n in merged_nodes if n.node_id == "file:changed.py")
        result_new = next(n for n in merged_nodes if n.node_id == "file:brand_new.py")

        # Unchanged: copied
        assert result_unchanged.smart_content == "Unchanged summary."

        # Changed: not copied
        assert result_changed.smart_content is None

        # New: not copied
        assert result_new.smart_content is None


# ===========================================================================
# T001: SmartContentStage.process() Tests (Phase 6)
# ===========================================================================


def _create_smart_content_service(*, response: str = "AI summary"):
    """Create SmartContentService with test dependencies."""
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig(max_workers=5))
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_response(response)
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)
    token_counter = FakeTokenCounterAdapter(config)

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )
    return service, llm_adapter


class TestSmartContentStageProcess:
    """Tests for SmartContentStage.process() batch processing (T001).

    Per Phase 6 Tasks:
    - Stage calls SmartContentService.process_batch() on nodes
    - Stage updates context.nodes with enriched nodes
    - Stage records metrics in context.metrics
    - Stage handles errors gracefully
    """

    def test_given_nodes_when_process_then_calls_batch_processing(self):
        """
        Purpose: Verifies stage calls SmartContentService.process_batch() with nodes.
        Quality Contribution: Proves stage delegates to service correctly.
        Acceptance Criteria: process_batch() called with context.nodes.

        Why: Stage must delegate to service for LLM processing.
        Contract: Stage calls process_batch() with nodes needing generation.
        """
        from fs2.core.services.stages.smart_content_stage import SmartContentStage

        service, llm_adapter = _create_smart_content_service(
            response="Generated summary"
        )

        # Create context with nodes and service
        context = PipelineContext(scan_config=ScanConfig())
        node = _make_file_node(
            "test.py",
            "def hello():\n    '''A test function that does something.'''\n    return 'hello world'",
        )
        context.nodes = [node]
        context.smart_content_service = service

        # Process
        stage = SmartContentStage()
        stage.process(context)

        # Verify LLM was called (proves process_batch was invoked)
        assert len(llm_adapter.call_history) == 1

    def test_given_nodes_when_process_then_updates_context_nodes(self):
        """
        Purpose: Verifies stage updates context.nodes with enriched nodes.
        Quality Contribution: Proves nodes get smart_content after processing.
        Acceptance Criteria: context.nodes contain smart_content after process().

        Why: Stage must replace nodes with enriched versions.
        Contract: After process(), nodes have smart_content populated.
        """
        from fs2.core.services.stages.smart_content_stage import SmartContentStage

        service, _ = _create_smart_content_service(response="This is the summary")

        context = PipelineContext(scan_config=ScanConfig())
        node = _make_file_node(
            "test.py",
            "def hello():\n    '''A test function that does something.'''\n    return 'hello world'",
        )
        context.nodes = [node]
        context.smart_content_service = service

        stage = SmartContentStage()
        result_context = stage.process(context)

        # Verify nodes are enriched
        assert len(result_context.nodes) == 1
        assert result_context.nodes[0].smart_content == "This is the summary"

    def test_given_nodes_when_process_then_records_metrics(self):
        """
        Purpose: Verifies stage records smart content metrics in context.metrics.
        Quality Contribution: Enables scan summary to show processing stats.
        Acceptance Criteria: context.metrics contains processed, preserved, errors.

        Why: CLI needs metrics to display in scan summary.
        Contract: Stage sets smart_content_* metrics in context.metrics.
        """
        from fs2.core.services.stages.smart_content_stage import SmartContentStage

        service, _ = _create_smart_content_service(response="Summary")

        context = PipelineContext(scan_config=ScanConfig())
        node = _make_file_node(
            "test.py",
            "def hello():\n    '''A test function that does something.'''\n    return 'hello world'",
        )
        context.nodes = [node]
        context.smart_content_service = service

        stage = SmartContentStage()
        result_context = stage.process(context)

        # Verify metrics recorded (per Session 2 Insight #2: enriched, preserved, errors)
        assert "smart_content_enriched" in result_context.metrics
        assert "smart_content_preserved" in result_context.metrics
        assert "smart_content_errors" in result_context.metrics
        assert result_context.metrics["smart_content_enriched"] == 1
        assert result_context.metrics["smart_content_preserved"] == 0
        assert result_context.metrics["smart_content_errors"] == 0

    def test_given_service_error_when_process_then_appends_to_errors(self):
        """
        Purpose: Verifies stage appends processing errors to context.errors.
        Quality Contribution: Ensures scan doesn't fail on individual node errors.
        Acceptance Criteria: Errors in context.errors, processing continues.

        Why: LLM errors shouldn't fail entire scan.
        Contract: Errors appended to context.errors, scan continues.
        """
        from fs2.core.adapters.exceptions import LLMRateLimitError
        from fs2.core.services.stages.smart_content_stage import SmartContentStage

        service, llm_adapter = _create_smart_content_service()
        llm_adapter.set_error(LLMRateLimitError("Rate limit exceeded"))

        context = PipelineContext(scan_config=ScanConfig())
        node = _make_file_node(
            "test.py",
            "def hello():\n    '''A test function that does something.'''\n    return 'hello world'",
        )
        context.nodes = [node]
        context.smart_content_service = service

        stage = SmartContentStage()
        result_context = stage.process(context)

        # Verify error recorded in metrics, not raised
        assert result_context.metrics["smart_content_errors"] == 1
        # Node should still be in results (without smart_content)
        assert len(result_context.nodes) == 1


# ===========================================================================
# T002: Stage Skip Tests When Service is None
# ===========================================================================


class TestSmartContentStageSkip:
    """Tests for SmartContentStage behavior when service is None (T002).

    Per Phase 6 Tasks:
    - Stage should skip gracefully when smart_content_service is None
    - This happens when --no-smart-content flag is used
    - No ValueError raised; processing continues without smart content
    """

    def test_given_no_service_when_process_then_skips_gracefully(self):
        """
        Purpose: Verifies stage skips processing when service is None.
        Quality Contribution: Enables --no-smart-content flag behavior.
        Acceptance Criteria: No error, nodes unchanged, metrics show skipped.

        Why: --no-smart-content flag sets service to None in context.
        Contract: If service is None, return nodes unchanged without error.
        """
        from fs2.core.services.stages.smart_content_stage import SmartContentStage

        context = PipelineContext(scan_config=ScanConfig())
        node = _make_file_node(
            "test.py",
            "def hello():\n    '''A test function that does something.'''\n    return 'hello world'",
        )
        context.nodes = [node]
        context.smart_content_service = None  # No service!

        stage = SmartContentStage()
        result_context = stage.process(context)

        # Verify nodes unchanged (no smart_content added)
        assert len(result_context.nodes) == 1
        assert result_context.nodes[0].smart_content is None

    def test_given_empty_nodes_when_process_then_returns_immediately(self):
        """
        Purpose: Verifies stage handles empty nodes list efficiently.
        Quality Contribution: No unnecessary processing for empty input.
        Acceptance Criteria: Metrics set to 0, no service call.

        Why: Empty scans should complete quickly.
        Contract: If nodes is empty, return immediately with zero metrics.
        """
        from fs2.core.services.stages.smart_content_stage import SmartContentStage

        service, llm_adapter = _create_smart_content_service()

        context = PipelineContext(scan_config=ScanConfig())
        context.nodes = []  # Empty!
        context.smart_content_service = service

        stage = SmartContentStage()
        result_context = stage.process(context)

        # Verify no LLM calls made
        assert len(llm_adapter.call_history) == 0
        # Verify empty nodes returned
        assert len(result_context.nodes) == 0
        # Verify metrics show zeros
        assert result_context.metrics.get("smart_content_enriched", 0) == 0


class TestSmartContentStageCategoryFilter:
    """Tests for enabled_categories filtering — plan 035."""

    def test_given_enabled_categories_file_when_processing_then_skips_callables(self):
        """Only file nodes get smart content when enabled_categories=["file"].

        Purpose: Proves category filtering works (AC01, AC05)
        """
        from unittest.mock import AsyncMock, MagicMock

        from fs2.config.objects import SmartContentConfig
        from fs2.core.services.stages.smart_content_stage import SmartContentStage

        # Create nodes of different categories
        file_node = _make_file_node(file_path="test.py", content="# test file")
        callable_node = replace(
            file_node,
            node_id="callable:test.py:foo",
            category="callable",
            ts_kind="function_definition",
            name="foo",
            qualified_name="foo",
            content="def foo(): pass",
            content_hash="hash_callable",
        )

        # Mock service with enabled_categories=["file"]
        mock_config = SmartContentConfig(enabled_categories=["file"])
        mock_service = MagicMock()
        mock_service._config = mock_config

        async def capture_batch(nodes, progress_callback=None, courtesy_save=None):
            return {
                "processed": len(nodes),
                "skipped": 0,
                "errors": [],
                "results": {
                    n.node_id: replace(n, smart_content="summary") for n in nodes
                },
                "total": len(nodes),
            }

        mock_service.process_batch = AsyncMock(side_effect=capture_batch)

        context = PipelineContext(scan_config=MagicMock(), graph_path=MagicMock())
        context.nodes = [file_node, callable_node]
        context.smart_content_service = mock_service
        context.prior_nodes = {}

        stage = SmartContentStage()
        result = stage.process(context)

        # File should have smart content, callable should not
        result_map = {n.node_id: n for n in result.nodes}
        file_result = result_map["file:test.py"]
        callable_result = result_map["callable:test.py:foo"]

        assert file_result.smart_content == "summary"
        assert callable_result.smart_content is None

        # process_batch should have received only the file node
        call_args = mock_service.process_batch.call_args
        nodes_sent = call_args[0][0]
        assert len(nodes_sent) == 1
        assert nodes_sent[0].category == "file"
