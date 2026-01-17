"""ConfigInspectorService - Read-only configuration inspection.

Per Phase 1 Foundation:
- AC-16: Never mutate os.environ
- AC-02: Source attribution tracking
- AC-03: Placeholder state detection
- AC-15: Secret masking (never show actual values)

CRITICAL: Use dotenv_values() ONLY - never load_dotenv().
Per Critical Discovery 01: load_dotenv() mutates os.environ.

Per Critical Insight #2: Stateless - always loads fresh on each call.
Per Critical Insight #5: Show placeholders literally, resolution state only.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values


class PlaceholderState(Enum):
    """State of a ${VAR} placeholder in configuration.

    RESOLVED: Env var exists and has a value
    UNRESOLVED: Env var not set or empty
    """

    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


@dataclass
class ConfigValue:
    """Attribution data for a single configuration value.

    Attributes:
        value: The raw value (placeholder syntax preserved, never actual secrets)
        source: Where this value came from ("user", "project", "env", "default")
        source_file: Path to the file containing this value (None for defaults)
        override_chain: List of (source, value) tuples that were overridden
        is_secret: True if this field is a secret (api_key, password, etc.)
    """

    value: Any
    source: str
    source_file: Path | None = None
    override_chain: list[tuple[str, Any]] = field(default_factory=list)
    is_secret: bool = False


@dataclass
class InspectionResult:
    """Result of configuration inspection.

    Attributes:
        attribution: Dict mapping dot-notation keys to ConfigValue
        raw_config: The merged raw config dict (with placeholder syntax preserved)
        placeholder_states: Dict mapping keys with placeholders to their state
        errors: List of any errors encountered during inspection
    """

    attribution: dict[str, ConfigValue] = field(default_factory=dict)
    raw_config: dict[str, Any] = field(default_factory=dict)
    placeholder_states: dict[str, PlaceholderState] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


# Regex for ${VAR} placeholder detection
_PLACEHOLDER_PATTERN = re.compile(r"\$\{([^}]+)\}")

# Fields that should be marked as secrets
_SECRET_FIELD_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "api-key",
        "secret",
        "password",
        "token",
        "credential",
        "credentials",
        "private_key",
        "privatekey",
    }
)


def _is_secret_field(key: str) -> bool:
    """Check if a config key represents a secret field.

    Args:
        key: Dot-notation config key (e.g., "llm.api_key")

    Returns:
        True if the field name suggests it's a secret.
    """
    # Get the last part of the key (the field name)
    field_name = key.split(".")[-1].lower()
    return field_name in _SECRET_FIELD_NAMES


def _load_yaml_safe(path: Path) -> tuple[dict[str, Any], list[str]]:
    """Load YAML file safely with error capture.

    Args:
        path: Path to YAML file

    Returns:
        Tuple of (config_dict, errors_list)
    """
    if not path.exists():
        return {}, []

    try:
        with open(path) as f:
            data = yaml.safe_load(f)
            return data if data else {}, []
    except yaml.YAMLError as e:
        return {}, [f"YAML parse error in {path}: {e}"]
    except PermissionError:
        return {}, [f"Permission denied reading {path}"]
    except OSError as e:
        return {}, [f"Error reading {path}: {e}"]


def _flatten_dict(
    d: dict[str, Any],
    parent_key: str = "",
    sep: str = ".",
) -> dict[str, Any]:
    """Flatten nested dict to dot-notation keys.

    Args:
        d: Dictionary to flatten
        parent_key: Parent key prefix
        sep: Separator between key levels

    Returns:
        Flat dict with dot-notation keys.

    Example:
        {"llm": {"timeout": 30}} -> {"llm.timeout": 30}
    """
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _unflatten_dict(flat_dict: dict[str, Any], sep: str = ".") -> dict[str, Any]:
    """Unflatten dot-notation keys back to nested dict.

    Args:
        flat_dict: Dict with dot-notation keys
        sep: Separator between key levels

    Returns:
        Nested dictionary.
    """
    result: dict[str, Any] = {}
    for key, value in flat_dict.items():
        parts = key.split(sep)
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            if not isinstance(current[part], dict):
                # Skip keys that would overwrite non-dict values
                break
            current = current[part]
        else:
            # Only set value if we traversed all intermediate parts
            current[parts[-1]] = value
    return result


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dicts, overlay wins at leaf level.

    Does not mutate inputs.
    """
    import copy

    result = copy.deepcopy(base)
    for key, overlay_value in overlay.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(overlay_value, dict)
        ):
            result[key] = _deep_merge(result[key], overlay_value)
        else:
            result[key] = copy.deepcopy(overlay_value)
    return result


class ConfigInspectorService:
    """Read-only configuration inspection service.

    Inspects configuration from user and project YAML files plus
    secrets from .env files without modifying os.environ.

    Key features:
    - Source attribution: Track where each value came from
    - Placeholder detection: Identify ${VAR} syntax and resolution state
    - Secret masking: Never expose actual secret values
    - Stateless: Each inspect() call loads fresh from disk

    Usage:
        ```python
        # Use defaults (recommended)
        inspector = ConfigInspectorService()
        result = inspector.inspect()

        # Or specify paths explicitly
        inspector = ConfigInspectorService(
            user_path=Path("~/.config/fs2/config.yaml"),
            project_path=Path(".fs2/config.yaml"),
            secrets_paths=[Path(".env"), Path(".fs2/secrets.env")],
        )
        result = inspector.inspect()

        # Check where a value came from
        print(result.attribution["llm.timeout"].source)  # "project"

        # Check placeholder state
        print(result.placeholder_states["llm.api_key"])  # RESOLVED
        ```

    CRITICAL: Never imports or calls load_secrets_to_env() or load_dotenv().
    Uses dotenv_values() which returns a dict without env mutation.
    """

    def __init__(
        self,
        user_path: Path | None = None,
        project_path: Path | None = None,
        secrets_paths: list[Path] | None = None,
        use_defaults: bool = True,
    ) -> None:
        """Initialize inspector with config and secrets paths.

        Args:
            user_path: Path to user config YAML (e.g., ~/.config/fs2/config.yaml)
            project_path: Path to project config YAML (e.g., .fs2/config.yaml)
            secrets_paths: List of .env files to check for placeholder resolution
                          (checked in order, last wins)
            use_defaults: If True and paths not specified, use standard fs2 paths
        """
        if use_defaults:
            # Import here to avoid circular imports
            from fs2.config.paths import get_project_config_dir, get_user_config_dir

            # Use standard fs2 config paths if not specified
            if user_path is None:
                user_path = get_user_config_dir() / "config.yaml"
            if project_path is None:
                project_path = get_project_config_dir() / "config.yaml"
            if secrets_paths is None:
                # Standard secrets locations (project .env and secrets.env files)
                project_dir = get_project_config_dir()
                secrets_paths = [
                    Path.cwd() / ".env",  # Project root .env
                    project_dir / "secrets.env",  # .fs2/secrets.env
                    get_user_config_dir() / "secrets.env",  # ~/.config/fs2/secrets.env
                ]

        self._user_path = user_path
        self._project_path = project_path
        self._secrets_paths = secrets_paths or []

    def inspect(self) -> InspectionResult:
        """Inspect configuration with source attribution.

        Loads all config files fresh (stateless - per Insight #2).
        Checks placeholder resolution using dotenv_values() (no env mutation).

        Returns:
            InspectionResult with attribution, raw_config, placeholder_states, errors.
        """
        result = InspectionResult()

        # Load user config
        user_config: dict[str, Any] = {}
        if self._user_path:
            user_config, errors = _load_yaml_safe(self._user_path)
            result.errors.extend(errors)

        # Load project config
        project_config: dict[str, Any] = {}
        if self._project_path:
            project_config, errors = _load_yaml_safe(self._project_path)
            result.errors.extend(errors)

        # Load secrets from .env files (read-only - dotenv_values)
        secrets: dict[str, str | None] = {}
        for secrets_path in self._secrets_paths:
            if secrets_path.exists():
                # dotenv_values() returns dict WITHOUT mutating os.environ
                env_values = dotenv_values(secrets_path)
                secrets.update(env_values)

        # Flatten configs for key-by-key comparison
        user_flat = _flatten_dict(user_config)
        project_flat = _flatten_dict(project_config)

        # Merge configs (project overrides user)
        merged_flat = {**user_flat, **project_flat}

        # Build attribution for each key
        for key, value in merged_flat.items():
            is_secret = _is_secret_field(key)

            # Determine source and build override chain
            if key in project_flat:
                source = "project"
                source_file = self._project_path
                override_chain: list[tuple[str, Any]] = []
                if key in user_flat and user_flat[key] != value:
                    override_chain.append(("user", user_flat[key]))
            else:
                source = "user"
                source_file = self._user_path
                override_chain = []

            result.attribution[key] = ConfigValue(
                value=value,
                source=source,
                source_file=source_file,
                override_chain=override_chain,
                is_secret=is_secret,
            )

            # Check for placeholders
            if isinstance(value, str):
                # Find ALL placeholders in value (handles multi-placeholder values)
                matches = _PLACEHOLDER_PATTERN.findall(value)
                if matches:
                    # Check if ALL placeholders are resolved
                    all_resolved = all(
                        var_name in secrets and secrets[var_name]
                        for var_name in matches
                    )
                    if all_resolved:
                        result.placeholder_states[key] = PlaceholderState.RESOLVED
                    else:
                        result.placeholder_states[key] = PlaceholderState.UNRESOLVED

        # Build raw_config (nested structure for UI display)
        result.raw_config = _deep_merge(user_config, project_config)

        return result
