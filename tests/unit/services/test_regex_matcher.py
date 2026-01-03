"""Tests for RegexMatcher - regex pattern matching with timeout protection.

TDD tests for Phase 2: Text/Regex Matchers.

Per tasks.md:
- T002: Basic matching tests
- T003: Timeout handling tests
- T004: Invalid regex error handling tests
- T009: Node ID scoring priority tests (added later)

Per DYK-P2-02: Line numbers must be absolute file-level lines.
Per DYK-P2-05: Snippet contains full matched line.
Per DYK-P2-06: Pattern compilation optimization (compile once, search many).
Per DYK-P3-01: Tests are async for compatibility with SemanticMatcher.
"""

import pytest

from fs2.core.models.code_node import CodeNode
from fs2.core.models.search import QuerySpec, SearchMode

# ============================================================================
# Test Fixtures - Helper functions to create test nodes
# ============================================================================


def create_node(
    node_id: str,
    content: str | None = None,
    smart_content: str | None = None,
    start_line: int = 1,
    end_line: int = 10,
) -> CodeNode:
    """Create a test CodeNode with minimal required fields."""
    return CodeNode(
        node_id=node_id,
        category=node_id.split(":")[0],  # Extract category from node_id
        ts_kind="function_definition",
        name=node_id.split(":")[-1] if ":" in node_id else node_id,
        qualified_name=node_id.split(":")[-1] if ":" in node_id else node_id,
        start_line=start_line,
        end_line=end_line,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=len(content) if content else 0,
        content=content or "",
        content_hash="test_hash",
        signature=None,
        language="python",
        is_named=True,
        field_name=None,
        smart_content=smart_content,
    )


def create_multiline_node(
    node_id: str,
    content: str,
    start_line: int = 10,
) -> CodeNode:
    """Create a CodeNode with multiline content and calculated end_line."""
    line_count = content.count("\n") + 1
    return create_node(
        node_id=node_id,
        content=content,
        start_line=start_line,
        end_line=start_line + line_count - 1,
    )


# ============================================================================
# T002: Basic Matching Tests
# ============================================================================


class TestRegexMatcherBasicMatching:
    """Basic regex pattern matching tests (T002)."""

    @pytest.mark.asyncio
    async def test_simple_pattern_matches_node_id(self) -> None:
        """Proves basic regex matching against node_id works (AC03).

        Purpose: Core functionality - regex pattern finds matching nodes.
        Quality Contribution: Validates fundamental regex matching.
        Acceptance Criteria: Pattern matches expected node_id.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        nodes = [create_node("callable:test.py:SearchService")]

        results = await matcher.match(
            QuerySpec(pattern="Service", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 1
        assert results[0].node_id == "callable:test.py:SearchService"

    @pytest.mark.asyncio
    async def test_pattern_matches_content(self) -> None:
        """Proves regex matching against content field works (AC04).

        Purpose: Search all text fields - content field matching.
        Quality Contribution: Validates multi-field search.
        Acceptance Criteria: Pattern found in content produces match.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        nodes = [
            create_node(
                "callable:test.py:process",
                content="def process(data):\n    return authenticate(data)",
            )
        ]

        results = await matcher.match(
            QuerySpec(pattern="authenticate", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 1
        assert results[0].match_field == "content"

    @pytest.mark.asyncio
    async def test_pattern_matches_smart_content(self) -> None:
        """Proves regex matching against smart_content field works (AC04).

        Purpose: Search all text fields - smart_content field matching.
        Quality Contribution: Validates AI summary is searchable.
        Acceptance Criteria: Pattern found in smart_content produces match.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        nodes = [
            create_node(
                "callable:test.py:func",
                content="def func(): pass",
                smart_content="Handles authentication and authorization flow",
            )
        ]

        results = await matcher.match(
            QuerySpec(pattern="authorization", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 1
        assert results[0].match_field == "smart_content"

    @pytest.mark.asyncio
    async def test_case_sensitive_matching_by_default(self) -> None:
        """Proves regex mode is case-sensitive by default.

        Purpose: Regex mode respects case.
        Quality Contribution: Predictable regex behavior.
        Acceptance Criteria: Lowercase pattern doesn't match uppercase.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        nodes = [create_node("callable:test.py:SearchService")]

        results = await matcher.match(
            QuerySpec(pattern="searchservice", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 0  # Case-sensitive, no match

    @pytest.mark.asyncio
    async def test_case_insensitive_flag_in_pattern(self) -> None:
        """Proves (?i) flag enables case-insensitive matching.

        Purpose: Regex supports inline case-insensitive flag.
        Quality Contribution: User can control case sensitivity.
        Acceptance Criteria: (?i) pattern matches regardless of case.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        nodes = [create_node("callable:test.py:SearchService")]

        results = await matcher.match(
            QuerySpec(pattern="(?i)searchservice", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_empty_results_when_no_matches(self) -> None:
        """Proves non-matching pattern returns empty list.

        Purpose: No matches is a valid result, not an error.
        Quality Contribution: Clean handling of no-match case.
        Acceptance Criteria: Empty list returned, no exception.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        nodes = [create_node("callable:test.py:func")]

        results = await matcher.match(
            QuerySpec(pattern="nonexistent_pattern_xyz", mode=SearchMode.REGEX),
            nodes,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_multiple_nodes_matched(self) -> None:
        """Proves multiple nodes can match the same pattern.

        Purpose: Pattern can match across multiple nodes.
        Quality Contribution: Multi-node search works.
        Acceptance Criteria: All matching nodes returned.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        nodes = [
            create_node("callable:test.py:ServiceA"),
            create_node("callable:test.py:ServiceB"),
            create_node("callable:test.py:Helper"),
        ]

        results = await matcher.match(
            QuerySpec(pattern="Service", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 2
        node_ids = {r.node_id for r in results}
        assert "callable:test.py:ServiceA" in node_ids
        assert "callable:test.py:ServiceB" in node_ids


# ============================================================================
# T003: Timeout Handling Tests
# ============================================================================


class TestRegexMatcherTimeout:
    """Timeout protection tests for catastrophic backtracking (T003).

    Per Discovery 04: Use regex module with timeout parameter.
    """

    @pytest.mark.asyncio
    async def test_timeout_returns_empty_not_exception(self) -> None:
        """Proves catastrophic backtracking is handled gracefully (Discovery 04).

        Purpose: ReDoS patterns don't hang the system.
        Quality Contribution: Prevents denial of service.
        Acceptance Criteria: Returns empty/partial results, no hang.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=0.1)  # Short timeout

        # Known ReDoS pattern - causes catastrophic backtracking
        evil_pattern = r"(a+)+$"

        # Content designed to trigger backtracking
        nodes = [create_node("test:node", content="a" * 30 + "X")]

        # Should not hang, should return within timeout
        results = await matcher.match(
            QuerySpec(pattern=evil_pattern, mode=SearchMode.REGEX),
            nodes,
        )

        # Graceful degradation - empty results, no exception
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_normal_patterns_not_affected_by_timeout(self) -> None:
        """Proves normal patterns work fine with timeout protection.

        Purpose: Timeout protection doesn't break normal use.
        Quality Contribution: Performance not degraded for valid patterns.
        Acceptance Criteria: Normal patterns match successfully.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        nodes = [
            create_node(
                "callable:test.py:process",
                content="def process():\n    return result",
            )
        ]

        results = await matcher.match(
            QuerySpec(pattern=r"def\s+\w+", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 1


# ============================================================================
# T004: Invalid Regex Error Handling Tests
# ============================================================================


class TestRegexMatcherErrorHandling:
    """Invalid regex pattern error handling tests (T004).

    Per AC03: Clear error messages for invalid patterns.
    """

    @pytest.mark.asyncio
    async def test_invalid_regex_raises_clear_error(self) -> None:
        """Proves invalid regex raises SearchError with clear message (AC03).

        Purpose: User gets actionable error for bad patterns.
        Quality Contribution: Good UX for invalid input.
        Acceptance Criteria: SearchError raised with descriptive message.
        """
        from fs2.core.services.search.exceptions import SearchError
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        nodes = [create_node("test:node")]

        with pytest.raises(SearchError) as exc_info:
            await matcher.match(
                QuerySpec(pattern="[invalid", mode=SearchMode.REGEX),
                nodes,
            )

        assert "Invalid regex pattern" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_unclosed_group_error(self) -> None:
        """Proves unclosed group regex raises clear error.

        Purpose: Common regex mistake gets clear error.
        Quality Contribution: Helps users fix patterns.
        Acceptance Criteria: Error mentions pattern issue.
        """
        from fs2.core.services.search.exceptions import SearchError
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        nodes = [create_node("test:node")]

        with pytest.raises(SearchError) as exc_info:
            await matcher.match(
                QuerySpec(pattern="(unclosed", mode=SearchMode.REGEX),
                nodes,
            )

        assert "Invalid regex pattern" in str(exc_info.value)


# ============================================================================
# DYK-P2-02: Absolute File-Level Line Extraction Tests
# ============================================================================


class TestRegexMatcherLineExtraction:
    """Line number extraction tests (DYK-P2-02).

    Per DYK-P2-02: match_start_line/match_end_line must be absolute file lines.
    This enables sed -n 'Np' accuracy.
    """

    @pytest.mark.asyncio
    async def test_match_start_line_is_absolute_file_line(self) -> None:
        """Proves match_start_line is absolute file line, not relative.

        Purpose: Line numbers work with sed/editor navigation.
        Quality Contribution: Enables `sed -n '142p' file.py` accuracy.
        Acceptance Criteria: match_start_line = node.start_line + relative offset.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)

        # Node starts at line 140, match on line 3 within node = file line 142
        content = "line 1\nline 2\nTARGET match here\nline 4"
        nodes = [create_multiline_node("callable:test.py:func", content, start_line=140)]

        results = await matcher.match(
            QuerySpec(pattern="TARGET", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 1
        # Line 3 of content (0-indexed: 2 newlines before TARGET)
        # Absolute: 140 + 2 = 142
        assert results[0].match_start_line == 142

    @pytest.mark.asyncio
    async def test_match_end_line_for_multiline_match(self) -> None:
        """Proves match_end_line is correctly calculated for multiline matches.

        Purpose: Multiline regex matches report correct end line.
        Quality Contribution: Accurate line range for multi-line matches.
        Acceptance Criteria: match_end_line = match_start_line + lines spanned.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)

        # Match spans 3 lines - use (?s) DOTALL flag so .* matches newlines
        content = "line 1\nSTART of\nmultiline\nmatch END\nline 5"
        nodes = [create_multiline_node("callable:test.py:func", content, start_line=10)]

        results = await matcher.match(
            QuerySpec(pattern=r"(?s)START.*END", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 1
        # START is at line 11 (10 + 1 newline before it)
        assert results[0].match_start_line == 11
        # END is at line 13 (10 + 3 newlines before it)
        assert results[0].match_end_line == 13

    @pytest.mark.asyncio
    async def test_single_line_match_has_same_start_and_end(self) -> None:
        """Proves single-line match has equal start and end lines.

        Purpose: Single-line matches are clean.
        Quality Contribution: Consistent line reporting.
        Acceptance Criteria: match_start_line == match_end_line.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        content = "line 1\nMATCH here\nline 3"
        nodes = [create_multiline_node("callable:test.py:func", content, start_line=100)]

        results = await matcher.match(
            QuerySpec(pattern="MATCH", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 1
        assert results[0].match_start_line == 101
        assert results[0].match_end_line == 101


# ============================================================================
# DYK-P2-04: smart_content and None Handling Tests
# ============================================================================


class TestRegexMatcherSmartContentHandling:
    """smart_content special handling tests (DYK-P2-04).

    Per DYK-P2-04: smart_content matches use node's full line range.
    """

    @pytest.mark.asyncio
    async def test_smart_content_match_uses_node_full_range(self) -> None:
        """Proves smart_content matches use node.start_line to node.end_line.

        Purpose: AI summaries don't map to file lines precisely.
        Quality Contribution: Honest representation per Phase 0 DYK-05.
        Acceptance Criteria: match lines = node's full range.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        nodes = [
            create_node(
                "callable:test.py:func",
                content="def func(): pass",
                smart_content="Authentication and session management",
                start_line=50,
                end_line=60,
            )
        ]

        results = await matcher.match(
            QuerySpec(pattern="session", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 1
        assert results[0].match_field == "smart_content"
        # Should use node's full range since smart_content doesn't map to lines
        assert results[0].match_start_line == 50
        assert results[0].match_end_line == 60

    @pytest.mark.asyncio
    async def test_none_content_handled_gracefully(self) -> None:
        """Proves content=None doesn't crash, searches smart_content.

        Purpose: Graceful handling when content is None.
        Quality Contribution: Robust against missing data.
        Acceptance Criteria: No crash, still searches smart_content.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)

        # Create node with content=None but has smart_content
        node = CodeNode(
            node_id="callable:test.py:func",
            category="callable",
            ts_kind="function_definition",
            name="func",
            qualified_name="func",
            start_line=1,
            end_line=10,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=0,
            content="",  # Empty content
            content_hash="hash",
            signature=None,
            language="python",
            is_named=True,
            field_name=None,
            smart_content="Searchable summary text",
        )

        results = await matcher.match(
            QuerySpec(pattern="Searchable", mode=SearchMode.REGEX),
            [node],
        )

        assert len(results) == 1
        assert results[0].match_field == "smart_content"


# ============================================================================
# DYK-P2-05: Snippet Extraction Tests
# ============================================================================


class TestRegexMatcherSnippetExtraction:
    """Snippet field extraction tests (DYK-P2-05).

    Per DYK-P2-05: snippet contains full line where match starts.
    """

    @pytest.mark.asyncio
    async def test_snippet_contains_full_matched_line(self) -> None:
        """Proves snippet contains the complete line with the match.

        Purpose: CLI-friendly context around match.
        Quality Contribution: User sees match in context.
        Acceptance Criteria: snippet = full line containing match start.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        content = "line 1\nhere is the MATCH on this line\nline 3"
        nodes = [create_multiline_node("test:node", content)]

        results = await matcher.match(
            QuerySpec(pattern="MATCH", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 1
        assert results[0].snippet == "here is the MATCH on this line"

    @pytest.mark.asyncio
    async def test_snippet_for_node_id_match(self) -> None:
        """Proves node_id matches use node_id as snippet.

        Purpose: For node_id matches, show the node_id itself.
        Quality Contribution: Meaningful snippet for identity matches.
        Acceptance Criteria: snippet = node_id.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        nodes = [create_node("callable:test.py:SearchService")]

        results = await matcher.match(
            QuerySpec(pattern="SearchService", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 1
        # For node_id matches, snippet should be the node_id
        assert results[0].snippet == "callable:test.py:SearchService"

    @pytest.mark.asyncio
    async def test_snippet_multiline_match_shows_first_line(self) -> None:
        """Proves multiline matches show only first matched line in snippet.

        Purpose: Keep snippet simple and predictable.
        Quality Contribution: CLI-friendly output.
        Acceptance Criteria: snippet = first line of match only.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        content = "line 1\nSTART of match\ncontinues here\nENDS here\nline 5"
        nodes = [create_multiline_node("test:node", content)]

        # Use (?s) DOTALL flag so .* matches newlines
        results = await matcher.match(
            QuerySpec(pattern=r"(?s)START.*ENDS", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 1
        # Should show first line of the match
        assert results[0].snippet == "START of match"


# ============================================================================
# T009: Node ID Scoring Priority Tests
# ============================================================================


class TestRegexMatcherScoring:
    """Scoring tests for node ID priority (T009).

    Per AC02: node_id matches have higher priority than content.
    Per DYK-P2-03: Score hierarchy - node_id exact=1.0, partial=0.8, content=0.5.
    """

    @pytest.mark.asyncio
    async def test_node_id_partial_match_scores_0_8(self) -> None:
        """Proves partial node_id match scores 0.8 (AC02, DYK-P2-03).

        Purpose: Node ID matches get higher priority.
        Quality Contribution: "Class:Name" pattern surfaces the class first.
        Acceptance Criteria: score = 0.8 for partial node_id match.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        nodes = [create_node("callable:test.py:SearchService")]

        results = await matcher.match(
            QuerySpec(pattern="Service", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 1
        assert results[0].match_field == "node_id"
        assert results[0].score == 0.8  # Partial match in node_id

    @pytest.mark.asyncio
    async def test_content_match_scores_0_5(self) -> None:
        """Proves content match scores 0.5 (DYK-P2-03).

        Purpose: Content matches rank lower than node_id matches.
        Quality Contribution: Predictable ranking behavior.
        Acceptance Criteria: score = 0.5 for content match.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        nodes = [
            create_node(
                "callable:test.py:process",
                content="def process():\n    return authenticate()",
            )
        ]

        results = await matcher.match(
            QuerySpec(pattern="authenticate", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 1
        assert results[0].match_field == "content"
        assert results[0].score == 0.5

    @pytest.mark.asyncio
    async def test_smart_content_match_scores_0_5(self) -> None:
        """Proves smart_content match scores 0.5 (DYK-P2-03).

        Purpose: AI summaries rank same as content.
        Quality Contribution: Consistent scoring for text fields.
        Acceptance Criteria: score = 0.5 for smart_content match.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        nodes = [
            create_node(
                "callable:test.py:func",
                content="def func(): pass",
                smart_content="Handles authentication flow",
            )
        ]

        results = await matcher.match(
            QuerySpec(pattern="authentication", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 1
        assert results[0].match_field == "smart_content"
        assert results[0].score == 0.5

    @pytest.mark.asyncio
    async def test_node_id_match_wins_over_content(self) -> None:
        """Proves node_id match has priority over content match (DYK-P2-03).

        Purpose: When pattern matches both fields, node_id wins.
        Quality Contribution: Identity-based search is preferred.
        Acceptance Criteria: match_field = node_id even if pattern in content.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        # Pattern "Service" appears in BOTH node_id AND content
        nodes = [
            create_node(
                "callable:test.py:SearchService",
                content="class SearchService:\n    pass",
            )
        ]

        results = await matcher.match(
            QuerySpec(pattern="Service", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 1
        # node_id match wins (0.8 > 0.5)
        assert results[0].match_field == "node_id"
        assert results[0].score == 0.8

    @pytest.mark.asyncio
    async def test_highest_score_wins_among_multiple_nodes(self) -> None:
        """Proves nodes are returned but caller must sort by score.

        Purpose: Multiple matches returned, caller sorts.
        Quality Contribution: Validates score-based ranking potential.
        Acceptance Criteria: All matching nodes returned, higher scores exist.
        """
        from fs2.core.services.search.regex_matcher import RegexMatcher

        matcher = RegexMatcher(timeout=2.0)
        nodes = [
            # This one has pattern in node_id (score 0.8)
            create_node("callable:test.py:AuthService"),
            # This one has pattern only in content (score 0.5)
            create_node(
                "callable:test.py:process",
                content="uses AuthService internally",
            ),
        ]

        results = await matcher.match(
            QuerySpec(pattern="AuthService", mode=SearchMode.REGEX),
            nodes,
        )

        assert len(results) == 2
        # Both returned, first node should have higher score
        scores = {r.node_id: r.score for r in results}
        assert scores["callable:test.py:AuthService"] == 0.8
        assert scores["callable:test.py:process"] == 0.5
