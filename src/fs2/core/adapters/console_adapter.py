"""ConsoleAdapter ABC interface.

Defines the console I/O interface for Rich wrapping in CLI.

Architecture:
- This file: ABC definition only
- Implementations: console_adapter_rich.py, console_adapter_fake.py, etc.

See: docs/plans/002-project-skele/project-skele-spec.md § AC2
"""

from abc import ABC, abstractmethod


class ConsoleAdapter(ABC):
    """Abstract base class for console I/O adapters.

    Defines the console interface for Rich wrapping in CLI.
    Implementations handle actual terminal I/O.

    Per AC2: For Rich wrapping in CLI module.
    """

    @abstractmethod
    def print(self, message: str, style: str | None = None) -> None:
        """Print a message to the console.

        Args:
            message: Message to print
            style: Optional Rich style string (e.g., "bold red")
        """
        ...

    @abstractmethod
    def input(self, prompt: str) -> str:
        """Read input from the user.

        Args:
            prompt: Prompt to display before input

        Returns:
            User's input string
        """
        ...
