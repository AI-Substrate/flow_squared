"""FakeConsoleAdapter - Test double for console output assertions.

Implements ConsoleAdapter by capturing all output for test assertions.
No actual terminal I/O occurs.

Architecture:
- Inherits from ConsoleAdapter ABC
- Captures all output as strings
- Provides .messages property for test assertions
- Provides .input_responses for pre-programmed input responses
"""

from dataclasses import dataclass

from fs2.core.adapters.console_adapter import ConsoleAdapter


@dataclass
class FakeConsoleMessage:
    """Captured console message for test assertions."""

    method: str
    content: str
    style: str | None = None


class FakeConsoleAdapter(ConsoleAdapter):
    """Test double for ConsoleAdapter that captures output.

    Stores all console output for test assertions.
    Supports pre-programmed input responses.

    Usage:
        >>> console = FakeConsoleAdapter()
        >>> console.print_success("Done!")
        >>> assert len(console.messages) == 1
        >>> assert console.messages[0].method == "print_success"
        >>> assert console.messages[0].content == "Done!"
    """

    def __init__(self) -> None:
        """Initialize with empty message list and input responses."""
        self._messages: list[FakeConsoleMessage] = []
        self._input_responses: list[str] = []
        self._input_index: int = 0

    @property
    def messages(self) -> list[FakeConsoleMessage]:
        """Access captured messages for test assertions.

        Returns:
            List of FakeConsoleMessage instances captured since creation.
        """
        return self._messages

    def add_input_response(self, response: str) -> None:
        """Pre-program an input response.

        Args:
            response: Response to return on next input() call
        """
        self._input_responses.append(response)

    # =========================================================================
    # Basic Output
    # =========================================================================

    def print(self, message: str, style: str | None = None) -> None:
        """Capture print call."""
        self._messages.append(
            FakeConsoleMessage(method="print", content=message, style=style)
        )

    def print_line(self) -> None:
        """Capture empty line."""
        self._messages.append(FakeConsoleMessage(method="print_line", content=""))

    # =========================================================================
    # Status Messages
    # =========================================================================

    def print_success(self, message: str) -> None:
        """Capture success message."""
        self._messages.append(
            FakeConsoleMessage(method="print_success", content=message)
        )

    def print_error(self, message: str) -> None:
        """Capture error message."""
        self._messages.append(FakeConsoleMessage(method="print_error", content=message))

    def print_warning(self, message: str) -> None:
        """Capture warning message."""
        self._messages.append(
            FakeConsoleMessage(method="print_warning", content=message)
        )

    def print_progress(self, message: str) -> None:
        """Capture progress message."""
        self._messages.append(
            FakeConsoleMessage(method="print_progress", content=message)
        )

    def print_info(self, message: str) -> None:
        """Capture info message."""
        self._messages.append(FakeConsoleMessage(method="print_info", content=message))

    # =========================================================================
    # Stage Banners
    # =========================================================================

    def stage_banner(self, title: str) -> None:
        """Capture stage banner."""
        self._messages.append(
            FakeConsoleMessage(method="stage_banner", content=title)
        )

    def stage_banner_skipped(self, title: str) -> None:
        """Capture skipped stage banner."""
        self._messages.append(
            FakeConsoleMessage(method="stage_banner_skipped", content=title)
        )

    # =========================================================================
    # Panels
    # =========================================================================

    def panel(
        self,
        content: str,
        title: str | None = None,
        success: bool = True,
    ) -> None:
        """Capture panel."""
        self._messages.append(
            FakeConsoleMessage(
                method="panel",
                content=content,
                style=f"title={title},success={success}",
            )
        )

    # =========================================================================
    # Input
    # =========================================================================

    def input(self, prompt: str) -> str:
        """Return pre-programmed response or empty string."""
        self._messages.append(FakeConsoleMessage(method="input", content=prompt))
        if self._input_index < len(self._input_responses):
            response = self._input_responses[self._input_index]
            self._input_index += 1
            return response
        return ""
