"""RichConsoleAdapter - Rich library implementation for console output.

Implements ConsoleAdapter using the Rich library for beautiful
terminal output with colors, panels, and rules.

Architecture:
- Inherits from ConsoleAdapter ABC
- Wraps Rich Console for all output
- CLI layer creates and injects this implementation
"""

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from fs2.core.adapters.console_adapter import ConsoleAdapter


class RichConsoleAdapter(ConsoleAdapter):
    """Console adapter using Rich library for formatted output.

    Provides colorful, styled terminal output using Rich.
    Used in interactive CLI contexts.

    Usage:
        >>> console = RichConsoleAdapter()
        >>> console.stage_banner("DISCOVERY")
        >>> console.print_success("Found 42 files")
        >>> console.print_error("Failed to parse foo.py")
    """

    def __init__(self) -> None:
        """Initialize with a Rich Console instance."""
        self._console = Console()

    # =========================================================================
    # Basic Output
    # =========================================================================

    def print(self, message: str, style: str | None = None) -> None:
        """Print a message with optional Rich style."""
        if style:
            self._console.print(message, style=style)
        else:
            self._console.print(message)

    def print_line(self) -> None:
        """Print an empty line."""
        self._console.print()

    # =========================================================================
    # Status Messages
    # =========================================================================

    def print_success(self, message: str) -> None:
        """Print success message with green checkmark."""
        self._console.print(f"  [green]✓[/green] {message}")

    def print_error(self, message: str) -> None:
        """Print error message in red."""
        self._console.print(f"  [red]✗[/red] [red]{message}[/red]")

    def print_warning(self, message: str) -> None:
        """Print warning message in yellow."""
        self._console.print(f"  [yellow]![/yellow] [yellow]{message}[/yellow]")

    def print_progress(self, message: str) -> None:
        """Print progress message in blue with empty lines around it."""
        self._console.print()
        self._console.print(f"  [blue]→[/blue] [blue]{message}[/blue]")
        self._console.print()

    def print_info(self, message: str) -> None:
        """Print info message in dimmed style."""
        self._console.print(f"  [dim]{message}[/dim]")

    # =========================================================================
    # Stage Banners
    # =========================================================================

    def stage_banner(self, title: str) -> None:
        """Print a stage banner with cyan rule."""
        self._console.print()
        self._console.print(Rule(f"[bold cyan]{title}[/bold cyan]", style="cyan"))

    def stage_banner_skipped(self, title: str) -> None:
        """Print a skipped stage banner (dimmed)."""
        self._console.print()
        self._console.print(Rule(f"[dim]{title} (skipped)[/dim]", style="dim"))

    # =========================================================================
    # Panels
    # =========================================================================

    def panel(
        self,
        content: str,
        title: str | None = None,
        success: bool = True,
    ) -> None:
        """Print a boxed panel."""
        border_style = "green" if success else "yellow"
        panel_title = f"[bold]{title}[/bold]" if title else None
        self._console.print(
            Panel(content, title=panel_title, border_style=border_style)
        )

    # =========================================================================
    # Input
    # =========================================================================

    def input(self, prompt: str) -> str:
        """Read input from user via Rich console."""
        return self._console.input(prompt)
