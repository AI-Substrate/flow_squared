"""
Stub for serena.text_utils.

Provides MatchedConsecutiveLines class used for extracting context around code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class LineType(Enum):
    """Line type classification for matched lines."""

    BEFORE_MATCH = "before"
    MATCH = "match"
    AFTER_MATCH = "after"


@dataclass
class TextLine:
    """A single line of text with metadata."""

    line_number: int
    content: str
    match_type: LineType

    def format_line(self, include_line_numbers: bool = True) -> str:
        """Format the line for display."""
        if include_line_numbers:
            return f"{self.line_number:4d} | {self.content}"
        return self.content


@dataclass
class MatchedConsecutiveLines:
    """
    Represents a collection of consecutive lines found in a text file.

    May include lines before, after, and matched lines.
    """

    lines: list[TextLine]
    source_file_path: str | None = None

    # Set in post-init
    lines_before_matched: list[TextLine] = field(default_factory=list)
    matched_lines: list[TextLine] = field(default_factory=list)
    lines_after_matched: list[TextLine] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Categorize lines by their match type."""
        for line in self.lines:
            if line.match_type == LineType.BEFORE_MATCH:
                self.lines_before_matched.append(line)
            elif line.match_type == LineType.MATCH:
                self.matched_lines.append(line)
            elif line.match_type == LineType.AFTER_MATCH:
                self.lines_after_matched.append(line)

        if not self.matched_lines:
            raise ValueError("At least one matched line is required")

    @property
    def start_line(self) -> int:
        """Get the first line number."""
        return self.lines[0].line_number

    @property
    def end_line(self) -> int:
        """Get the last line number."""
        return self.lines[-1].line_number

    @property
    def num_matched_lines(self) -> int:
        """Get the number of matched lines."""
        return len(self.matched_lines)

    def to_display_string(self, include_line_numbers: bool = True) -> str:
        """Format all lines for display."""
        return "\n".join(line.format_line(include_line_numbers) for line in self.lines)

    @classmethod
    def from_file_contents(
        cls,
        file_contents: str,
        line: int,
        context_lines_before: int = 0,
        context_lines_after: int = 0,
        source_file_path: str | None = None,
    ) -> "MatchedConsecutiveLines":
        """
        Create a MatchedConsecutiveLines from file contents.

        Args:
            file_contents: The full file contents as a string
            line: The 0-indexed line number to match
            context_lines_before: Number of lines before the match to include
            context_lines_after: Number of lines after the match to include
            source_file_path: Optional path to the source file

        Returns:
            MatchedConsecutiveLines instance with the requested context
        """
        line_contents = file_contents.split("\n")
        start_lineno = max(0, line - context_lines_before)
        end_lineno = min(len(line_contents) - 1, line + context_lines_after)

        text_lines: list[TextLine] = []

        # Lines before the match
        for lineno in range(start_lineno, line):
            text_lines.append(
                TextLine(
                    line_number=lineno,
                    content=line_contents[lineno],
                    match_type=LineType.BEFORE_MATCH,
                )
            )

        # The matched line
        if line < len(line_contents):
            text_lines.append(
                TextLine(
                    line_number=line,
                    content=line_contents[line],
                    match_type=LineType.MATCH,
                )
            )

        # Lines after the match
        for lineno in range(line + 1, end_lineno + 1):
            text_lines.append(
                TextLine(
                    line_number=lineno,
                    content=line_contents[lineno],
                    match_type=LineType.AFTER_MATCH,
                )
            )

        return cls(
            lines=text_lines,
            source_file_path=source_file_path,
        )
