"""Unit tests for SmartContentStage merge logic.

Purpose: Verifies SmartContentStage correctly merges prior smart_content
from context.prior_nodes before processing.

Per Subtask 001: Graph Loading for Smart Content Preservation.
Enables hash-based skip logic (AC5/AC6) by preserving smart_content across scans.

Per Alignment Brief:
- Merge logic copies prior smart_content/smart_content_hash if content_hash matches
- Uses dataclasses.replace() for CodeNode immutability (CD03)
- Handles prior_nodes=None gracefully (first scan case)
"""

from dataclasses import replace

import pytest

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
        result_unchanged = next(n for n in merged_nodes if n.node_id == "file:unchanged.py")
        result_changed = next(n for n in merged_nodes if n.node_id == "file:changed.py")
        result_new = next(n for n in merged_nodes if n.node_id == "file:brand_new.py")

        # Unchanged: copied
        assert result_unchanged.smart_content == "Unchanged summary."

        # Changed: not copied
        assert result_changed.smart_content is None

        # New: not copied
        assert result_new.smart_content is None
