"""Configuration loading helpers for fs2.

This module provides loading utilities for the ConfigurationService:
- load_secrets_to_env: Load secrets.env files into os.environ
- load_yaml_config: Load YAML config files
- parse_env_vars: Parse FS2_* environment variables
- deep_merge: Merge config dictionaries
- expand_placeholders: Expand ${VAR} placeholders

Per Architecture Decision: ConfigurationService owns the loading pipeline.
Per Insight #2: .env wins over everything (standard dotenv behavior).
"""

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

from fs2.config.paths import get_project_config_dir, get_user_config_dir


def load_secrets_to_env() -> None:
    """Load secrets files into os.environ.

    Loads secrets in precedence order (lowest → highest):
    1. OS environment (already set - base layer)
    2. User secrets (~/.config/fs2/secrets.env)
    3. Project secrets (./.fs2/secrets.env)
    4. Working dir .env (./.env wins over everything)

    Each subsequent file overrides previous values.
    Missing files are silently ignored.

    Per Insight #2: .env wins - use override=True for each load.
    """
    # User secrets (lowest priority of files)
    user_secrets = get_user_config_dir() / "secrets.env"
    if user_secrets.exists():
        load_dotenv(user_secrets, override=True)

    # Project secrets (overrides user)
    project_secrets = get_project_config_dir() / "secrets.env"
    if project_secrets.exists():
        load_dotenv(project_secrets, override=True)

    # Working dir .env (highest priority - wins over everything)
    dotenv_file = Path.cwd() / ".env"
    if dotenv_file.exists():
        load_dotenv(dotenv_file, override=True)


def load_yaml_config(path: Path) -> dict[str, Any]:
    """Load a YAML configuration file.

    Args:
        path: Path to the YAML file to load.

    Returns:
        Parsed YAML as a dictionary, or empty dict if:
        - File doesn't exist
        - File is empty
        - File contains invalid YAML

    Per Architecture Decision: Graceful fallback on missing/invalid files.
    """
    if not path.exists():
        return {}

    try:
        with open(path) as f:
            data = yaml.safe_load(f)
            return data if data else {}
    except yaml.YAMLError as e:
        logger.debug("Failed to parse YAML config at %s: %s", path, e)
        return {}


def parse_env_vars() -> dict[str, Any]:
    """Parse FS2_* environment variables into nested dict.

    Convention:
    - Prefix: All config env vars start with FS2_
    - Nesting: Double underscore __ = nested level (.)
    - Case: Env var is UPPER, config path is lower

    Examples:
        FS2_AZURE__OPENAI__TIMEOUT=120 → {"azure": {"openai": {"timeout": "120"}}}
        FS2_DEBUG=true → {"debug": "true"}

    Returns:
        Nested dictionary built from all FS2_* environment variables.
    """
    result: dict[str, Any] = {}

    for key, value in os.environ.items():
        if not key.startswith("FS2_"):
            continue

        # Remove prefix and convert to lowercase
        config_key = key[4:].lower()  # Remove "FS2_"

        # Split by double underscore for nesting
        parts = config_key.split("__")

        # Build nested structure
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Set the leaf value
        current[parts[-1]] = value

    return result


# Regex for ${VAR} placeholders
_PLACEHOLDER_PATTERN = re.compile(r"\$\{([^}]+)\}")


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries.

    Recursively merges overlay into base. At leaf level, overlay wins.
    Non-overlapping keys from both dicts are preserved.
    Does not mutate the original dictionaries.

    Args:
        base: Base dictionary (lower priority).
        overlay: Overlay dictionary (higher priority).

    Returns:
        New merged dictionary.

    Examples:
        deep_merge({"a": 1}, {"a": 2}) → {"a": 2}
        deep_merge({"a": {"b": 1}}, {"a": {"c": 2}}) → {"a": {"b": 1, "c": 2}}
    """
    import copy

    result = copy.deepcopy(base)

    for key, overlay_value in overlay.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(overlay_value, dict)
        ):
            # Recursively merge nested dicts
            result[key] = deep_merge(result[key], overlay_value)
        else:
            # Overlay wins at leaf level
            result[key] = copy.deepcopy(overlay_value)

    return result


def _expand_string(value: str) -> str:
    """Expand ${VAR} placeholders in a string.

    Missing env vars are left unexpanded (consumer validates).

    Args:
        value: String potentially containing ${VAR} placeholders.

    Returns:
        String with found placeholders replaced, missing ones left as-is.
    """

    def replace_placeholder(match: re.Match) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is None:
            # Leave unexpanded - consumer will validate
            return match.group(0)
        return env_value

    return _PLACEHOLDER_PATTERN.sub(replace_placeholder, value)


def expand_placeholders(config: dict[str, Any]) -> None:
    """Expand ${VAR} placeholders in config dict.

    Recursively processes all string values in the dict,
    replacing ${VAR} with os.environ[VAR] where available.
    Missing env vars are left unexpanded.

    Modifies config in-place.

    Args:
        config: Configuration dictionary to process.

    Per Insight #5: Missing → leave unexpanded (consumer validates).
    """
    for key, value in config.items():
        if isinstance(value, str):
            config[key] = _expand_string(value)
        elif isinstance(value, dict):
            expand_placeholders(value)
