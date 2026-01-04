"""Shared CLI utilities for fs2 commands.

Per Phase 1 save-to-file plan:
- validate_save_path(): Security function to prevent directory traversal
- safe_write_file(): File write helper with cleanup on error and UTF-8 encoding

Per Insight #2: Wrap file writes in try/except, delete partial file on failure.
Per Insight #3: Always use encoding="utf-8" per JSON spec RFC 8259.
"""

import contextlib
from pathlib import Path

import typer
from rich.console import Console


def validate_save_path(file: Path, console: Console) -> Path:
    """Validate save path is under current working directory.

    Per Critical Finding 01: CLI must have same path validation as MCP.
    Mirrors logic from fs2.mcp.server._validate_save_path().

    Args:
        file: Path to validate (relative or absolute).
        console: Console for error output (should be stderr=True).

    Returns:
        Absolute path if valid.

    Raises:
        typer.Exit: If path escapes working directory (exit code 1).
    """
    cwd = Path.cwd().resolve()
    target = (cwd / file).resolve()

    # Check if target is under or equal to cwd
    try:
        target.relative_to(cwd)
    except ValueError:
        console.print(
            f"[red]Error:[/red] Path '{file}' escapes working directory. "
            "Only paths under the current directory are allowed."
        )
        raise typer.Exit(code=1) from None

    return target


def safe_write_file(path: Path, content: str, console: Console) -> None:
    """Write content to file with error cleanup and UTF-8 encoding.

    Per Insight #2: If write fails midway, delete partial file.
    Per Insight #3: Use encoding="utf-8" per JSON spec RFC 8259.
    Per AC10: Auto-create parent directories if needed.

    Args:
        path: Absolute path to write to.
        content: Content to write.
        console: Console for error output (should be stderr=True).

    Raises:
        typer.Exit: If write fails (exit code 1).
    """
    try:
        # Auto-create parent directories (AC10)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write with explicit UTF-8 encoding (Insight #3)
        path.write_text(content, encoding="utf-8")

    except OSError as e:
        # Cleanup partial file on error (Insight #2)
        if path.exists():
            with contextlib.suppress(OSError):
                path.unlink()

        console.print(f"[red]Error:[/red] Failed to write file: {e}")
        raise typer.Exit(code=1) from None
