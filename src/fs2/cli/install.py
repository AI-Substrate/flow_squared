"""fs2 install/upgrade command implementation.

Provides self-bootstrapping CLI commands that allow users to permanently
install fs2 from a uvx invocation.

Usage:
    # First time (via uvx)
    uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 install

    # After installation
    fs2 install  # upgrades if already installed

Commands:
    install: Checks if fs2 is installed; if not, runs uv tool install; otherwise upgrades
    upgrade: Alias for install (same idempotent behavior)
"""

import json
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, distribution, version

import typer
from rich.console import Console

# Hardcoded GitHub URL - no customization allowed
GITHUB_URL = "git+https://github.com/AI-Substrate/flow_squared"

console = Console()


def _uv_available() -> bool:
    """Check if uv is available on the system."""
    return shutil.which("uv") is not None


def _is_fs2_installed() -> bool:
    """Check if fs2 is installed as a uv tool.

    Returns:
        True if fs2 appears in `uv tool list` output.
    """
    try:
        result = subprocess.run(
            ["uv", "tool", "list"],
            capture_output=True,
            text=True,
            check=False,
        )
        # Look for "fs2 " at start of any line
        return any(line.startswith("fs2 ") for line in result.stdout.splitlines())
    except Exception:
        return False


def _get_version_info() -> tuple[str, str | None, str | None]:
    """Get version information from the installed fs2 package.

    Returns:
        Tuple of (version, commit_short, url).
        commit_short and url may be None if not installed from git.
    """
    try:
        pkg_version = version("fs2")
    except PackageNotFoundError:
        return ("unknown", None, None)

    # Try to get git info from direct_url.json (PEP 610)
    commit_short = None
    url = None

    try:
        dist = distribution("fs2")
        for file in dist.files or []:
            if file.name == "direct_url.json":
                content = file.read_text(encoding="utf-8")
                data = json.loads(content)
                url = data.get("url")
                vcs_info = data.get("vcs_info", {})
                if vcs_info.get("vcs") == "git":
                    commit_id = vcs_info.get("commit_id", "")
                    commit_short = commit_id[:7] if commit_id else None
                break
    except Exception:
        pass

    return (pkg_version, commit_short, url)


def get_version_string() -> str:
    """Get formatted version string for --version flag.

    Returns:
        Formatted version string like "fs2 v0.1.0 (abc1234)"
    """
    pkg_version, commit_short, url = _get_version_info()

    if commit_short:
        return f"fs2 v{pkg_version} ({commit_short})"
    else:
        return f"fs2 v{pkg_version}"


def _run_install() -> int:
    """Run uv tool install for fs2.

    Returns:
        Exit code from uv command.
    """
    console.print("[cyan]i[/cyan] Installing fs2...")

    try:
        result = subprocess.run(
            ["uv", "tool", "install", GITHUB_URL],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            # Check for "already exists" error - needs --force
            if "already exists" in result.stderr:
                console.print(
                    "[yellow]![/yellow] fs2 executable exists but not as uv tool.\n"
                    "  Re-run with: [bold]uv tool install --force "
                    f"{GITHUB_URL}[/bold]"
                )
            else:
                console.print(f"[red]x[/red] Install failed:\n{result.stderr}")
            return result.returncode

        # Success - show version info
        pkg_version, commit_short, _ = _get_version_info()
        version_str = f"v{pkg_version}"
        if commit_short:
            version_str += f" ({commit_short})"

        console.print(
            f"[green]>[/green] Installed fs2 {version_str}\n"
            "  Now available as [bold]'fs2'[/bold] command globally"
        )
        return 0

    except Exception as e:
        console.print(f"[red]x[/red] Install failed: {e}")
        return 1


def _run_upgrade() -> int:
    """Run uv tool upgrade for fs2.

    Returns:
        Exit code from uv command.
    """
    console.print("[cyan]i[/cyan] fs2 already installed, upgrading...")

    try:
        result = subprocess.run(
            ["uv", "tool", "upgrade", "fs2"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            console.print(f"[red]x[/red] Upgrade failed:\n{result.stderr}")
            return result.returncode

        # Check if anything was actually upgraded
        if "Nothing to upgrade" in result.stdout:
            pkg_version, commit_short, _ = _get_version_info()
            version_str = f"v{pkg_version}"
            if commit_short:
                version_str += f" ({commit_short})"
            console.print(f"[green]>[/green] fs2 {version_str} is already up to date")
        else:
            pkg_version, commit_short, _ = _get_version_info()
            version_str = f"v{pkg_version}"
            if commit_short:
                version_str += f" ({commit_short})"
            console.print(f"[green]>[/green] Upgraded fs2 to {version_str}")

        return 0

    except Exception as e:
        console.print(f"[red]x[/red] Upgrade failed: {e}")
        return 1


def install() -> None:
    """Install or upgrade fs2 as a permanent uv tool.

    This command enables self-bootstrapping: run it via uvx to install fs2
    permanently, then use fs2 directly without uvx.

    \b
    First time (via uvx):
        $ uvx --from git+https://github.com/AI-Substrate/flow_squared fs2 install
        i Installing fs2...
        > Installed fs2 v0.1.0 (abc1234)
          Now available as 'fs2' command globally

    \b
    Already installed:
        $ fs2 install
        i fs2 already installed, upgrading...
        > fs2 v0.1.0 (abc1234) is already up to date
    """
    # Check if uv is available
    if not _uv_available():
        if sys.platform == "win32":
            install_hint = 'powershell -c "irm https://astral.sh/uv/install.ps1 | iex"'
        else:
            install_hint = "curl -LsSf https://astral.sh/uv/install.sh | sh"
        console.print(
            "[red]x[/red] uv not found.\n"
            f"  Install uv first: [bold]{install_hint}[/bold]"
        )
        raise typer.Exit(code=1)

    # Check if fs2 is already installed as a uv tool
    exit_code = _run_upgrade() if _is_fs2_installed() else _run_install()

    if exit_code != 0:
        raise typer.Exit(code=exit_code)


# Alias for install - same idempotent behavior
upgrade = install
