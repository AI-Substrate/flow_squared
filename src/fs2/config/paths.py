"""XDG path resolution for fs2 configuration.

This module provides path helpers following XDG Base Directory spec.

Per Insight #3: CWD-relative path for project; XDG for user config.
Use XDG_CONFIG_HOME with ~/.config fallback.

Functions:
    get_user_config_dir: Returns user config directory (~/.config/fs2 or XDG)
    get_project_config_dir: Returns project config directory (./.fs2)
"""

import os
from pathlib import Path


def get_user_config_dir() -> Path:
    """Get the user configuration directory following XDG spec.

    Returns:
        Path to user config dir:
        - $XDG_CONFIG_HOME/fs2 if XDG_CONFIG_HOME is set
        - ~/.config/fs2 otherwise

    Examples:
        >>> get_user_config_dir()
        PosixPath('/home/user/.config/fs2')
    """
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "fs2"
    return Path.home() / ".config" / "fs2"


def get_project_config_dir() -> Path:
    """Get the project configuration directory.

    Returns:
        Path to .fs2 directory relative to current working directory.

    Examples:
        >>> get_project_config_dir()
        PosixPath('/workspaces/myproject/.fs2')
    """
    return Path.cwd() / ".fs2"
