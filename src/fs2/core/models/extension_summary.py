"""ExtensionSummary - Domain model for extension breakdown data.

Used by GraphUtilitiesService to report on persisted graph contents.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExtensionSummary:
    """Immutable summary of file/node counts by extension.

    Attributes:
        files_by_ext: Dict mapping extension to unique file count.
        nodes_by_ext: Dict mapping extension to total node count.
    """

    files_by_ext: dict[str, int]
    nodes_by_ext: dict[str, int]

    @property
    def total_files(self) -> int:
        """Total unique files across all extensions."""
        return sum(self.files_by_ext.values())

    @property
    def total_nodes(self) -> int:
        """Total nodes across all extensions."""
        return sum(self.nodes_by_ext.values())
