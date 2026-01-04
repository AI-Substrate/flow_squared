"""FakeASTParser - Test double implementing ASTParser ABC.

Provides a configurable fake for testing components that depend on ASTParser.
Follows the established adapter fake pattern with configurable results
and call history recording.

Architecture:
- Inherits from ASTParser ABC
- Receives ConfigurationService (registry) via constructor
- Returns configured results without actual parsing
- Records call history for test verification
- Supports error simulation for testing error paths

Per Critical Finding 01: Receives ConfigurationService, not extracted config.
Per Critical Finding 02: Adapter ABC with Dual Implementation Pattern.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fs2.config.objects import ScanConfig
from fs2.core.adapters.ast_parser import ASTParser
from fs2.core.adapters.exceptions import ASTParserError
from fs2.core.models.code_node import CodeNode

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


class FakeASTParser(ASTParser):
    """Fake implementation of ASTParser for testing.

    This implementation provides deterministic behavior for testing:
    - Returns pre-configured CodeNode list from parse()
    - Returns pre-configured language from detect_language()
    - Records all method calls for verification
    - Supports error simulation via simulate_error_for

    Usage in tests:
        ```python
        config = FakeConfigurationService(ScanConfig())
        parser = FakeASTParser(config)

        # Configure results
        parser.set_results(Path("src/main.py"), [
            CodeNode.create_file(file_path="src/main.py", ...),
        ])

        # Use in test
        results = parser.parse(Path("src/main.py"))
        assert len(results) == 1

        # Verify calls
        assert parser.call_history[0]["method"] == "parse"
        ```
    """

    def __init__(self, config: "ConfigurationService"):
        """Initialize with ConfigurationService registry.

        Args:
            config: ConfigurationService registry.
                    Adapter will call config.require(ScanConfig) internally.

        Raises:
            MissingConfigurationError: If ScanConfig not in registry.
        """
        # Extract config internally (per Critical Finding 01)
        self._scan_config = config.require(ScanConfig)
        self._results_by_path: dict[Path, list[CodeNode]] = {}
        self._languages_by_path: dict[Path, str] = {}
        self._call_history: list[dict[str, Any]] = []
        self.simulate_error_for: set[Path] = set()

    @property
    def call_history(self) -> list[dict[str, Any]]:
        """Access recorded calls for test assertions.

        Returns:
            List of dicts with 'method', 'args' for each call.
        """
        return self._call_history

    def set_results(self, file_path: Path, results: list[CodeNode]) -> None:
        """Configure results to return from parse() for a specific file.

        Args:
            file_path: Path that parse() will be called with.
            results: List of CodeNode to return for that path.
        """
        self._results_by_path[file_path] = results

    def set_language(self, file_path: Path, language: str) -> None:
        """Configure language to return from detect_language() for a path.

        Args:
            file_path: Path to set language for.
            language: Language string to return.
        """
        self._languages_by_path[file_path] = language

    def parse(self, file_path: Path) -> list[CodeNode]:
        """Return configured results without actual parsing.

        Args:
            file_path: Path to "parse" (lookup in configured results).

        Returns:
            List of pre-configured CodeNode objects, or empty list if not configured.

        Raises:
            ASTParserError: If file_path is in simulate_error_for set.
        """
        self._call_history.append(
            {
                "method": "parse",
                "args": {"file_path": file_path},
            }
        )

        if file_path in self.simulate_error_for:
            raise ASTParserError(
                f"Simulated parse error for {file_path}. This is a test double error."
            )

        return self._results_by_path.get(file_path, [])

    def detect_language(self, file_path: Path) -> str | None:
        """Return configured language for a path.

        Args:
            file_path: Path to check.

        Returns:
            Configured language string, or None if not configured.
        """
        self._call_history.append(
            {
                "method": "detect_language",
                "args": {"file_path": file_path},
            }
        )
        return self._languages_by_path.get(file_path)

    def get_skip_summary(self) -> dict[str, int]:
        """Return empty skip summary (fake doesn't track skips).

        Returns:
            Empty dict (fake implementation doesn't skip files).
        """
        self._call_history.append(
            {
                "method": "get_skip_summary",
                "args": {},
            }
        )
        return {}
