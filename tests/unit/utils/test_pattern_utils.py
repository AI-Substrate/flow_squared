"""Unit tests for pattern normalization utilities.

TDD RED phase tests for normalize_filter_pattern() function.
These tests define expected behavior before implementation.

Per DYK-001: Algorithm uses GLOB-DETECTION-FIRST approach.
Per DYK-002: Trailing glob patterns like test_* are converted.
Per DYK-003: fnmatch format assumption is explicitly tested.
Per DYK-005: Question mark glob patterns are tested.
"""

from __future__ import annotations

import re

import pytest

from fs2.core.utils.pattern_utils import normalize_filter_pattern


@pytest.mark.unit
class TestPatternNormalizationConversion:
    """Test glob->regex conversion with backward compatibility."""

    @pytest.mark.parametrize(
        "input_pattern,expected",
        [
            # Glob patterns starting with * - converted with anchor
            ("*.py", r".*\.py(?:$|:)"),
            ("*.gd", r".*\.gd(?:$|:)"),
            ("*.cs", r".*\.cs(?:$|:)"),
            ("*.md", r".*\.md(?:$|:)"),
            # Trailing glob (DYK-002: ends with * but not .*)
            ("test_*", r"test_.*(?:$|:)"),
            ("src/*", r"src/.*(?:$|:)"),
            # Question mark glob (DYK-005: ? wildcard)
            # ? in glob matches any single char, becomes . in regex
            ("file?.py", r"file.\.py(?:$|:)"),
            ("test_?.cs", r"test_.\.cs(?:$|:)"),
            # Extension patterns - escaped and anchored
            (".py", r"\.py(?:$|:)"),
            (".gd", r"\.gd(?:$|:)"),
            (".cs", r"\.cs(?:$|:)"),
            (".ts", r"\.ts(?:$|:)"),
        ],
    )
    def test_glob_patterns_converted(self, input_pattern: str, expected: str) -> None:
        """Glob patterns are converted to regex with (?:$|:) anchor."""
        result = normalize_filter_pattern(input_pattern)
        assert result == expected

    @pytest.mark.parametrize(
        "pattern",
        [
            "Calculator.*",  # Valid regex with .*
            ".*test.*",  # Match anything with test
            "src/",  # Simple substring
            "^class:",  # Anchored regex
            r"\.py$",  # Explicit end anchor
            "auth",  # Simple substring
            "(auth|calc)",  # Alternation
        ],
    )
    def test_regex_patterns_pass_through_unchanged(self, pattern: str) -> None:
        """CRITICAL: Existing regex patterns must not be converted."""
        result = normalize_filter_pattern(pattern)
        assert result == pattern

    @pytest.mark.parametrize("pattern", ["", " ", "\t", "  \t  "])
    def test_empty_patterns_rejected(self, pattern: str) -> None:
        """Empty or whitespace-only patterns raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            normalize_filter_pattern(pattern)

    def test_fnmatch_format_assumption(self) -> None:
        """Verify fnmatch output format matches expected patterns (DYK-003).

        Python <3.14 uses \\Z, Python 3.14+ uses \\z. Both are handled
        by _convert_glob_to_regex.
        """
        import fnmatch

        result = fnmatch.translate("*.py")
        assert result in (r"(?s:.*\.py)\Z", r"(?s:.*\.py)\z"), (
            f"fnmatch format changed! Got: {result}"
        )


@pytest.mark.unit
class TestPatternMatching:
    """Verify converted patterns match expected node_ids."""

    @pytest.mark.parametrize(
        "pattern,node_id,should_match",
        [
            # File nodes (extension at end)
            (".cs", "file:src/Foo.cs", True),
            (".cs", "file:src/Foo.css", False),  # .cs should NOT match .css
            (".py", "file:src/test.py", True),
            (".ts", "file:src/index.ts", True),
            (
                ".ts",
                "file:src/typescript/foo.py",
                False,
            ),  # .ts shouldn't match "typescript"
            # Symbol nodes (extension before :)
            (".cs", "type:src/Foo.cs:FooClass", True),
            (".py", "callable:src/test.py:TestClass.method", True),
            # Glob patterns with *
            ("*.gd", "file:scripts/player.gd", True),
            ("*.gd", "callable:scripts/player.gd:Player.move", True),
            ("*.py", "file:src/test.py", True),
            ("*.py", "callable:src/test.py:func", True),
            ("*.cs", "file:src/Foo.cs", True),
            ("*.cs", "file:src/Foo.css", False),  # *.cs should NOT match .css
            # Trailing globs
            ("test_*", "file:src/test_utils.py", True),
            ("test_*", "file:src/utils.py", False),
            ("src/*", "file:src/foo.py", True),
            ("src/*", "file:tests/foo.py", False),
        ],
    )
    def test_pattern_matches_node_ids(
        self, pattern: str, node_id: str, should_match: bool
    ) -> None:
        """Converted patterns correctly match/reject node_ids."""
        regex = normalize_filter_pattern(pattern)
        match = re.search(regex, node_id)
        assert bool(match) == should_match, (
            f"Pattern '{pattern}' (regex: '{regex}') "
            f"{'should' if should_match else 'should not'} match '{node_id}'"
        )


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_invalid_regex_raises_value_error(self) -> None:
        """Invalid patterns that aren't valid globs or regex raise ValueError."""
        # [invalid is invalid as both glob and regex
        with pytest.raises(ValueError, match="Invalid pattern"):
            normalize_filter_pattern("[invalid")

    def test_double_star_not_supported(self) -> None:
        """Double-star recursive glob is not explicitly supported.

        ** is invalid regex, so it will be treated as a glob pattern.
        We just need to ensure it doesn't crash - behavior may vary.
        """
        # This should not raise an exception - either convert or pass through
        result = normalize_filter_pattern("**/*.py")
        assert isinstance(result, str)

    def test_extension_with_hyphen_not_matched(self) -> None:
        """Extension patterns only match word characters (limitation per R08).

        .py-old won't match ^\\.\\w+$ so it falls through to regex handling.
        As regex, it would match any char + py-old, so user should use
        explicit regex \\.py-old if needed.
        """
        # .py-old is not a simple extension pattern, treated as regex
        result = normalize_filter_pattern(".py-old")
        # Should pass through as-is (valid regex) or convert appropriately
        assert isinstance(result, str)
