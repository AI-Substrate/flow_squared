"""NodeIdDetector - detects explicit fs2 node_id patterns in text.

Scans text content for explicit node_id patterns like:
- file:src/app.py
- callable:src/lib/resolver.py:calculate_confidence
- class:src/lib/parser.py:Parser
- method:src/lib/parser.py:Parser.detect_language
- type:src/models/types.py:ImportInfo

All matches return CodeEdge instances with:
- edge_type: EdgeType.REFERENCES (explicit reference)
- confidence: 1.0 (highest confidence for explicit patterns)
- resolution_rule: "nodeid:explicit"

Pattern ported from 022 experiment: 01_nodeid_detection.py
"""

import re

from fs2.core.models.code_edge import CodeEdge
from fs2.core.models.edge_type import EdgeType


class NodeIdDetector:
    """Detects explicit fs2 node_id patterns in text content.

    Uses regex pattern to find node_id references with format:
    (file|callable|type|class|method):path(:symbol)?

    Returns CodeEdge instances with confidence=1.0 for all matches.
    """

    # Node ID regex pattern per 022 experiment Finding 10
    # Matches: file:path, callable:path:name, type:path:name, class:path:name, method:path:name
    # Word boundaries (\b) prevent matching URLs or other colon-separated text
    # Path segment includes hyphens for package names like my-cool-lib
    NODE_ID_PATTERN = re.compile(
        r'\b(file|callable|type|class|method):[\w./-]+(?::[\w.]+)?\b'
    )

    def detect(self, source_file: str, content: str) -> list[CodeEdge]:
        """Detect explicit node_id patterns in text content.

        Args:
            source_file: Source file path (e.g., "file:README.md")
            content: Text content to scan

        Returns:
            List of CodeEdge instances for each node_id pattern found.
            Empty list if no patterns detected.

        Example:
            >>> detector = NodeIdDetector()
            >>> edges = detector.detect(
            ...     "file:README.md",
            ...     "See `file:src/app.py` for details"
            ... )
            >>> len(edges)
            1
            >>> edges[0].target_node_id
            'file:src/app.py'
            >>> edges[0].confidence
            1.0
        """
        # Validate inputs
        if not isinstance(source_file, str):
            raise TypeError(f'source_file must be string, got {type(source_file).__name__}')
        if not isinstance(content, str):
            raise TypeError(f'content must be string, got {type(content).__name__}')

        edges: list[CodeEdge] = []

        # Split content into lines for line number tracking
        lines = content.split('\n')

        for line_num, line in enumerate(lines, start=1):
            # Find all node_id patterns in this line
            for match in self.NODE_ID_PATTERN.finditer(line):
                node_id = match.group(0)

                # Create CodeEdge for this match
                edge = CodeEdge(
                    source_node_id=source_file,
                    target_node_id=node_id,
                    edge_type=EdgeType.REFERENCES,
                    confidence=1.0,  # Explicit node_ids have highest confidence
                    source_line=line_num,
                    resolution_rule="nodeid:explicit",
                )
                edges.append(edge)

        return edges
