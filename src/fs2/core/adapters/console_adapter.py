"""ConsoleAdapter ABC interface.

Defines the console I/O interface for Rich wrapping in CLI.

Architecture:
- This file: ABC definition only
- Implementations: console_adapter_rich.py, console_adapter_fake.py, etc.

Per Clean Architecture: Services use this ABC, never Rich/terminal concepts.
The CLI layer injects the appropriate implementation.

See: docs/plans/002-project-skele/project-skele-spec.md § AC2
"""

from abc import ABC, abstractmethod


class ConsoleAdapter(ABC):
    """Abstract base class for console I/O adapters.

    Defines the console interface for CLI output.
    Implementations handle actual terminal I/O (Rich, plain text, etc.).

    Usage in CLI:
        >>> console = RichConsoleAdapter()
        >>> console.stage_banner("DISCOVERY")
        >>> console.print_success("Found 42 files")

    Per AC2: For Rich wrapping in CLI module.
    """

    # =========================================================================
    # Basic Output
    # =========================================================================

    @abstractmethod
    def print(self, message: str, style: str | None = None) -> None:
        """Print a message to the console.

        Args:
            message: Message to print
            style: Optional style hint (e.g., "bold", "dim")
        """
        ...

    @abstractmethod
    def print_line(self) -> None:
        """Print an empty line."""
        ...

    # =========================================================================
    # Status Messages
    # =========================================================================

    @abstractmethod
    def print_success(self, message: str) -> None:
        """Print a success message (green checkmark prefix).

        Args:
            message: Success message to display
        """
        ...

    @abstractmethod
    def print_error(self, message: str) -> None:
        """Print an error message (red text).

        Args:
            message: Error message to display
        """
        ...

    @abstractmethod
    def print_warning(self, message: str) -> None:
        """Print a warning message (yellow text).

        Args:
            message: Warning message to display
        """
        ...

    @abstractmethod
    def print_progress(self, message: str) -> None:
        """Print a progress message (blue text).

        Use for progress updates during long-running operations.

        Args:
            message: Progress message to display
        """
        ...

    @abstractmethod
    def print_info(self, message: str) -> None:
        """Print an info message (dimmed text).

        Args:
            message: Info message to display
        """
        ...

    # =========================================================================
    # Stage Banners
    # =========================================================================

    @abstractmethod
    def stage_banner(self, title: str) -> None:
        """Print a stage banner (horizontal rule with title).

        Includes empty line before for visual separation.
        Used for major stages: CONFIGURATION, DISCOVERY, PARSING, etc.

        Args:
            title: Stage title to display
        """
        ...

    @abstractmethod
    def stage_banner_skipped(self, title: str) -> None:
        """Print a skipped stage banner (dimmed).

        Args:
            title: Stage title to display as skipped
        """
        ...

    # =========================================================================
    # Panels
    # =========================================================================

    @abstractmethod
    def panel(
        self,
        content: str,
        title: str | None = None,
        success: bool = True,
    ) -> None:
        """Print a boxed panel.

        Args:
            content: Multi-line panel content
            title: Optional panel title
            success: If True, use success styling; if False, use warning styling
        """
        ...

    # =========================================================================
    # Input
    # =========================================================================

    @abstractmethod
    def input(self, prompt: str) -> str:
        """Read input from the user.

        Args:
            prompt: Prompt to display before input

        Returns:
            User's input string
        """
        ...
