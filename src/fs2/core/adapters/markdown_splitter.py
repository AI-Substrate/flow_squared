"""Hand-rolled markdown section splitter.

Splits markdown files into section nodes at H2 (##) heading boundaries.
Bypasses tree-sitter entirely — uses a simple line-by-line scan.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from fs2.core.models.code_node import CodeNode


class MarkdownSectionSplitter:
    """Split markdown files into CodeNode sections at H2 heading boundaries.

    Each H2 heading becomes a separate ``section:`` node. Content between
    H2 headings (including H3/H4 subsections) is captured in the parent
    H2 section. Content before the first H2 (the preamble) is captured
    as a section named after the H1 title, or "Preamble" if no H1 exists.

    Headings inside fenced code blocks (``` or ~~~) are ignored.
    """

    _H2_PATTERN = re.compile(r"^## (.+)$")
    _H1_PATTERN = re.compile(r"^# (.+)$")
    _FENCE_PATTERN = re.compile(r"^(`{3,}|~{3,})")

    def split(
        self,
        file_path: str,
        content: str,
        parent_node_id: str | None = None,
    ) -> list[CodeNode]:
        """Split markdown content into section CodeNodes.

        Args:
            file_path: Relative POSIX path to the file.
            content: Full file content as string.
            parent_node_id: Node ID of the parent file node.

        Returns:
            List of section CodeNodes. Empty if no H2 headings found.
        """
        # Normalize path to POSIX
        file_path = PurePosixPath(file_path).as_posix()

        lines = content.split("\n")
        if not lines or (len(lines) == 1 and not lines[0].strip()):
            return []

        content_bytes = content.encode("utf-8")

        sections: list[_SectionData] = []
        h1_title: str | None = None
        in_code_block = False
        fence_char: str | None = None
        fence_len: int = 0

        # Track where each section starts
        current_section_start: int | None = None
        current_heading: str | None = None
        has_h2 = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Track fenced code blocks with proper fence matching
            fence_match = self._FENCE_PATTERN.match(stripped)
            if fence_match:
                fence_str = fence_match.group(1)
                if not in_code_block:
                    in_code_block = True
                    fence_char = fence_str[0]
                    fence_len = len(fence_str)
                elif fence_str[0] == fence_char and len(fence_str) >= fence_len:
                    in_code_block = False
                    fence_char = None
                    fence_len = 0
                continue

            if in_code_block:
                continue

            # Check for H1 (only capture first one for preamble naming)
            if h1_title is None:
                h1_match = self._H1_PATTERN.match(line)
                if h1_match:
                    h1_title = h1_match.group(1).strip()

            # Check for H2
            h2_match = self._H2_PATTERN.match(line)
            if h2_match and not line.startswith("### "):
                has_h2 = True

                # Close previous section (or preamble)
                if current_section_start is not None:
                    sections.append(
                        _SectionData(
                            name=current_heading,  # type: ignore[arg-type]
                            start_line=current_section_start,
                            end_line=i - 1,
                            is_preamble=current_heading is None,
                        )
                    )
                elif i > 0:
                    # Preamble: content before first H2
                    sections.append(
                        _SectionData(
                            name=None,
                            start_line=0,
                            end_line=i - 1,
                            is_preamble=True,
                        )
                    )

                current_heading = h2_match.group(1).strip()
                current_section_start = i

        # No H2 headings found → return empty
        if not has_h2:
            return []

        # Close final section
        if current_section_start is not None:
            sections.append(
                _SectionData(
                    name=current_heading,
                    start_line=current_section_start,
                    end_line=len(lines) - 1,
                    is_preamble=False,
                )
            )

        # Build CodeNode objects with deduplication
        seen_names: dict[str, int] = {}
        nodes: list[CodeNode] = []

        for section in sections:
            # Determine name
            if section.is_preamble:
                name = h1_title if h1_title else "Preamble"
            else:
                name = section.name or "Untitled"

            # Build qualified_name with dedup
            qualified_name = name
            if name in seen_names:
                seen_names[name] += 1
                # Use start_line + 1 for 1-indexed line number
                qualified_name = f"{name}@{section.start_line + 1}"
            else:
                seen_names[name] = 1

            # Compute content and byte offsets
            section_lines = lines[section.start_line : section.end_line + 1]
            section_content = "\n".join(section_lines)

            # Strip trailing empty lines from content for cleanliness
            while section_content.endswith("\n\n"):
                section_content = section_content[:-1]

            # Byte offsets - compute from original content bytes
            start_byte = len("\n".join(lines[: section.start_line]).encode("utf-8"))
            if section.start_line > 0:
                start_byte += 1  # account for the newline before this section

            end_byte = start_byte + len(section_content.encode("utf-8"))

            # Signature is the heading line
            if section.is_preamble:
                sig_line = lines[section.start_line].strip()
                signature = sig_line if sig_line else "Preamble"
            else:
                signature = f"## {name}"

            nodes.append(
                CodeNode.create_section(
                    file_path=file_path,
                    language="markdown",
                    ts_kind="section",
                    name=name,
                    qualified_name=qualified_name,
                    start_line=section.start_line + 1,  # 1-indexed
                    end_line=section.end_line + 1,  # 1-indexed
                    start_column=0,
                    end_column=len(lines[section.end_line]) if section.end_line < len(lines) else 0,
                    start_byte=start_byte,
                    end_byte=end_byte,
                    content=section_content,
                    signature=signature,
                    parent_node_id=parent_node_id,
                )
            )

        return nodes


class _SectionData:
    """Internal data holder for section boundaries during scanning."""

    __slots__ = ("name", "start_line", "end_line", "is_preamble")

    def __init__(
        self,
        name: str | None,
        start_line: int,
        end_line: int,
        is_preamble: bool,
    ):
        self.name = name
        self.start_line = start_line
        self.end_line = end_line
        self.is_preamble = is_preamble
