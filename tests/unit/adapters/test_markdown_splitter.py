"""Tests for MarkdownSectionSplitter.

Full TDD — these tests are written before the implementation.
Each test uses real markdown fixture files from tests/fixtures/markdown/.
"""

from pathlib import Path

import pytest

from fs2.core.adapters.markdown_splitter import MarkdownSectionSplitter
from fs2.core.models.code_node import CodeNode
from fs2.core.models.content_type import ContentType

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "markdown"


@pytest.fixture
def splitter() -> MarkdownSectionSplitter:
    return MarkdownSectionSplitter()


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# --- AC-01: Basic H2 splitting ---


class TestBasicH2Splitting:
    def test_creates_sections_for_each_h2(self, splitter: MarkdownSectionSplitter):
        content = _load("basic_h2.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        # Preamble + 4 H2 headings = 5
        assert len(section_nodes) == 5

    def test_section_names_match_heading_text(self, splitter: MarkdownSectionSplitter):
        content = _load("basic_h2.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        names = [n.name for n in section_nodes]
        assert names == [
            "Sample Plan Document",  # preamble (H1 title)
            "Executive Summary",
            "Technical Context",
            "Implementation Phases",
            "Testing Philosophy",
        ]

    def test_section_node_ids_are_correct(self, splitter: MarkdownSectionSplitter):
        content = _load("basic_h2.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        assert section_nodes[0].node_id == "section:docs/plan.md:Sample Plan Document"
        assert section_nodes[1].node_id == "section:docs/plan.md:Executive Summary"
        assert section_nodes[2].node_id == "section:docs/plan.md:Technical Context"


# --- AC-03: Section content spans ---


class TestSectionContent:
    def test_section_content_includes_h3_subsections(self, splitter: MarkdownSectionSplitter):
        content = _load("basic_h2.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        tech_context = next(n for n in section_nodes if n.name == "Technical Context")
        assert "### Current System State" in tech_context.content
        assert "### Integration Requirements" in tech_context.content

    def test_section_content_ends_before_next_h2(self, splitter: MarkdownSectionSplitter):
        content = _load("basic_h2.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        exec_summary = next(n for n in section_nodes if n.name == "Executive Summary")
        assert "## Technical Context" not in exec_summary.content


# --- AC-04: Preamble ---


class TestPreamble:
    def test_preamble_uses_h1_title(self, splitter: MarkdownSectionSplitter):
        content = _load("preamble_with_h1.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        preamble = section_nodes[0]
        assert preamble.name == "My Plan Title"

    def test_preamble_falls_back_to_preamble_name(self, splitter: MarkdownSectionSplitter):
        content = _load("preamble_without_h1.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        preamble = section_nodes[0]
        assert preamble.name == "Preamble"

    def test_preamble_content_captured(self, splitter: MarkdownSectionSplitter):
        content = _load("preamble_with_h1.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        preamble = section_nodes[0]
        assert "**Created**: 2026-01-21" in preamble.content

    def test_basic_h2_preamble_captured(self, splitter: MarkdownSectionSplitter):
        content = _load("basic_h2.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        # Preamble should be first section (H1 title)
        preamble = section_nodes[0]
        assert preamble.name == "Sample Plan Document"
        # Total: preamble + 4 H2 sections = 5
        assert len(section_nodes) == 5


# --- AC-05: Code block awareness ---


class TestCodeBlockAwareness:
    def test_h2_inside_backtick_code_block_ignored(self, splitter: MarkdownSectionSplitter):
        content = _load("code_blocks.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        names = [n.name for n in section_nodes]
        assert "This is NOT a heading" not in names
        assert "Also NOT a heading" not in names

    def test_h2_inside_tilde_code_block_ignored(self, splitter: MarkdownSectionSplitter):
        content = _load("code_blocks.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        names = [n.name for n in section_nodes]
        assert "Also NOT a heading" not in names

    def test_real_sections_around_code_blocks(self, splitter: MarkdownSectionSplitter):
        content = _load("code_blocks.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        names = [n.name for n in section_nodes]
        # Preamble (H1: "Code Block Test") + 3 real H2 sections
        assert "Code Block Test" in names
        assert "Real Section Before Code" in names
        assert "Real Section After Code" in names
        assert "Final Section" in names


# --- AC-06: Node attributes ---


class TestNodeAttributes:
    def test_section_has_correct_content_type(self, splitter: MarkdownSectionSplitter):
        content = _load("basic_h2.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        for node in section_nodes:
            assert node.content_type == ContentType.CONTENT

    def test_section_has_correct_language(self, splitter: MarkdownSectionSplitter):
        content = _load("basic_h2.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        for node in section_nodes:
            assert node.language == "markdown"

    def test_section_has_correct_category(self, splitter: MarkdownSectionSplitter):
        content = _load("basic_h2.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        for node in section_nodes:
            assert node.category == "section"

    def test_section_has_parent_node_id(self, splitter: MarkdownSectionSplitter):
        content = _load("basic_h2.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        for node in section_nodes:
            assert node.parent_node_id == "file:docs/plan.md"

    def test_section_signature_is_heading_line(self, splitter: MarkdownSectionSplitter):
        content = _load("basic_h2.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        exec_summary = next(n for n in section_nodes if n.name == "Executive Summary")
        assert exec_summary.signature == "## Executive Summary"


# --- AC-07: Accurate line and byte positions ---


class TestPositions:
    def test_section_start_line_matches(self, splitter: MarkdownSectionSplitter):
        content = _load("basic_h2.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        # Find "Executive Summary" — should start on the line containing "## Executive Summary"
        exec_summary = next(n for n in section_nodes if n.name == "Executive Summary")
        lines = content.split("\n")
        expected_line = next(
            i + 1 for i, line in enumerate(lines) if line == "## Executive Summary"
        )
        assert exec_summary.start_line == expected_line

    def test_byte_offsets_match_utf8(self, splitter: MarkdownSectionSplitter):
        content = _load("utf8_content.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        for node in section_nodes:
            # Verify byte offsets align with actual content position
            content_bytes = content.encode("utf-8")
            section_bytes = content_bytes[node.start_byte : node.end_byte]
            assert section_bytes.decode("utf-8") == node.content


# --- AC-08: No H2s = no sections ---


class TestNoH2s:
    def test_no_h2_returns_empty_list(self, splitter: MarkdownSectionSplitter):
        content = _load("no_h2.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        assert len(nodes) == 0

    def test_h1_only_returns_empty_list(self, splitter: MarkdownSectionSplitter):
        content = _load("h1_only.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        assert len(nodes) == 0


# --- AC-02: Duplicate heading disambiguation ---


class TestDuplicateHeadings:
    def test_first_occurrence_keeps_clean_name(self, splitter: MarkdownSectionSplitter):
        content = _load("duplicate_headings.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        tasks_nodes = [n for n in section_nodes if "Tasks" in n.qualified_name]
        assert tasks_nodes[0].qualified_name == "Tasks"

    def test_duplicates_get_line_suffix(self, splitter: MarkdownSectionSplitter):
        content = _load("duplicate_headings.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        tasks_nodes = [n for n in section_nodes if "Tasks" in n.qualified_name]
        # 3 "## Tasks" headings — first clean, second and third with @line
        assert len(tasks_nodes) == 3
        assert tasks_nodes[0].qualified_name == "Tasks"
        assert "@" in tasks_nodes[1].qualified_name
        assert "@" in tasks_nodes[2].qualified_name

    def test_duplicate_node_ids_are_unique(self, splitter: MarkdownSectionSplitter):
        content = _load("duplicate_headings.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        node_ids = [n.node_id for n in section_nodes]
        assert len(node_ids) == len(set(node_ids)), f"Duplicate node IDs found: {node_ids}"


# --- AC-11: Edge cases ---


class TestEdgeCases:
    def test_empty_file(self, splitter: MarkdownSectionSplitter):
        content = _load("empty.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        assert len(nodes) == 0

    def test_codeblock_only_file(self, splitter: MarkdownSectionSplitter):
        content = _load("codeblock_only.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        assert len(nodes) == 0

    def test_consecutive_h2_produces_empty_sections(self, splitter: MarkdownSectionSplitter):
        content = _load("consecutive_h2.md")
        nodes = splitter.split("docs/plan.md", content, parent_node_id="file:docs/plan.md")
        section_nodes = [n for n in nodes if n.category == "section"]
        # Preamble + 4 H2 sections = 5, some may have minimal content
        assert len(section_nodes) == 5
        # All should have valid content (even if just the heading line)
        for node in section_nodes:
            assert len(node.content) > 0
