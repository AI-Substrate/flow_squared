"""Configuration validation functions.

Pure validation functions extracted from doctor.py for reuse
across CLI and Web UI.

These functions:
- Take raw config dicts as input
- Return validation results as tuples/lists/dicts
- Have no side effects (no file I/O, no env mutation)
- Do not depend on CLI or Web frameworks

Per Critical Insight #1: Single source of truth prevents drift.
"""

from typing import Any

from fs2.core.validation.constants import (
    LONG_SECRET_MIN_LENGTH,
    PLACEHOLDER_PATTERN,
    SECRET_FIELD_NAMES,
    SK_PREFIX_PATTERN,
)


def validate_llm_config(config: dict[str, Any]) -> tuple[bool, bool, list[str]]:
    """Validate LLM configuration.

    Args:
        config: Raw configuration dictionary (may contain "llm" section)

    Returns:
        Tuple of (is_configured, is_misconfigured, list of issues)
        - is_configured: True if LLM is properly configured
        - is_misconfigured: True if LLM section exists but is invalid
        - issues: List of issue descriptions
    """
    llm = config.get("llm")
    if not llm:
        return False, False, []

    provider = llm.get("provider")
    if not provider:
        return False, True, ["Missing 'provider' field"]

    issues: list[str] = []
    if provider == "azure":
        if not llm.get("base_url"):
            issues.append("base_url is required when provider=azure")
        if not llm.get("azure_deployment_name"):
            issues.append("azure_deployment_name is required when provider=azure")
        if not llm.get("azure_api_version"):
            issues.append("azure_api_version is required when provider=azure")

    if issues:
        return False, True, issues

    return True, False, []


def validate_embedding_config(config: dict[str, Any]) -> tuple[bool, bool, list[str]]:
    """Validate embedding configuration.

    Args:
        config: Raw configuration dictionary (may contain "embedding" section)

    Returns:
        Tuple of (is_configured, is_misconfigured, list of issues)
        - is_configured: True if embedding is properly configured
        - is_misconfigured: True if embedding section exists but is invalid
        - issues: List of issue descriptions
    """
    embedding = config.get("embedding")
    if not embedding:
        return False, False, []

    mode = embedding.get("mode")
    if not mode:
        return False, True, ["Missing 'mode' field"]

    issues: list[str] = []
    if mode == "azure":
        azure = embedding.get("azure", {})
        if not azure.get("endpoint"):
            issues.append("azure.endpoint is required when mode=azure")
        if not azure.get("api_key"):
            issues.append("azure.api_key is required when mode=azure")

    if issues:
        return False, True, issues

    return True, False, []


def find_placeholders_in_value(
    value: Any,
    path: str = "",
) -> list[dict[str, str]]:
    """Find ${VAR} placeholders in a config value recursively.

    Args:
        value: Config value (string, dict, list, or other)
        path: Current path prefix for nested keys

    Returns:
        List of dicts with "name" and "path" for each placeholder found.
    """
    placeholders: list[dict[str, str]] = []

    if isinstance(value, str):
        for match in PLACEHOLDER_PATTERN.finditer(value):
            placeholders.append(
                {
                    "name": match.group(1),
                    "path": path,
                }
            )
    elif isinstance(value, dict):
        for k, v in value.items():
            current_path = f"{path}.{k}" if path else k
            placeholders.extend(find_placeholders_in_value(v, current_path))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            current_path = f"{path}[{i}]"
            placeholders.extend(find_placeholders_in_value(item, current_path))

    return placeholders


def validate_placeholders(
    config: dict[str, Any],
    env_values: dict[str, str | None],
) -> list[dict[str, Any]]:
    """Validate placeholder resolution against environment values.

    Args:
        config: Raw configuration dictionary
        env_values: Dict of available environment variable values

    Returns:
        List of placeholder dicts with name, path, and resolved status.
        Duplicates by name are deduplicated.
    """
    placeholders = find_placeholders_in_value(config)

    # Deduplicate by name and add resolved status
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for p in placeholders:
        if p["name"] not in seen:
            seen.add(p["name"])
            result.append(
                {
                    "name": p["name"],
                    "path": p["path"],
                    "resolved": p["name"] in env_values and bool(env_values[p["name"]]),
                }
            )

    return result


def _find_secrets_in_value(
    value: Any,
    path: str = "",
    is_secret_field: bool = False,
) -> list[dict[str, Any]]:
    """Find literal secrets in config values.

    Returns:
        List of secret warnings (never includes actual values).
    """
    secrets: list[dict[str, Any]] = []

    if isinstance(value, str):
        # Check for sk-* prefix (OpenAI API key format)
        if SK_PREFIX_PATTERN.match(value):
            secrets.append(
                {
                    "path": path,
                    "pattern": "sk-*",
                    "reason": "OpenAI API key format detected",
                }
            )
        # Check for long strings in secret fields (but not placeholders)
        elif (
            is_secret_field
            and len(value) >= LONG_SECRET_MIN_LENGTH
            and not PLACEHOLDER_PATTERN.search(value)
        ):
            secrets.append(
                {
                    "path": path,
                    "pattern": f">{LONG_SECRET_MIN_LENGTH} chars",
                    "reason": "Long literal in secret field",
                }
            )
    elif isinstance(value, dict):
        for k, v in value.items():
            current_path = f"{path}.{k}" if path else k
            is_secret = k.lower() in SECRET_FIELD_NAMES
            secrets.extend(_find_secrets_in_value(v, current_path, is_secret))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            current_path = f"{path}[{i}]"
            secrets.extend(_find_secrets_in_value(item, current_path, is_secret_field))

    return secrets


def detect_literal_secrets(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect literal secrets in config.

    Args:
        config: Raw configuration dictionary

    Returns:
        List of secret warnings (never includes actual values).
    """
    return _find_secrets_in_value(config)


def get_suggestions(
    config_exists: bool,
    unresolved_placeholders: list[dict[str, Any]],
) -> list[str]:
    """Get actionable suggestions based on current config state.

    Args:
        config_exists: True if any config file exists
        unresolved_placeholders: List of unresolved placeholder dicts

    Returns:
        List of suggestion strings.
    """
    suggestions: list[str] = []

    # No configs at all -> suggest init
    if not config_exists:
        suggestions.append("Run 'fs2 init' to create configuration files")

    # Unresolved placeholders
    for p in unresolved_placeholders:
        if not p.get("resolved", True):
            suggestions.append(
                f"Set {p['name']} environment variable to enable {p.get('path', 'configuration')}"
            )

    return suggestions


def get_warnings(
    overrides: list[dict[str, Any]],
    has_user_config: bool,
    has_project_config: bool,
) -> list[str]:
    """Get warnings based on current config state.

    Args:
        overrides: List of override dicts with path, base_value, override_value
        has_user_config: True if user config exists
        has_project_config: True if project config exists

    Returns:
        List of warning strings.
    """
    warnings: list[str] = []

    # Central config exists but no local .fs2/
    if has_user_config and not has_project_config:
        warnings.append(
            "User config exists but no local .fs2/ folder. "
            "Run 'fs2 init' to create project-specific config."
        )

    # Override warnings
    for o in overrides:
        warnings.append(
            f"Local config overrides '{o['path']}': "
            f"{o['base_value']} → {o['override_value']}"
        )

    return warnings


def compute_overall_status(
    llm_configured: bool,
    llm_misconfigured: bool,
    embedding_configured: bool,
    embedding_misconfigured: bool,
    unresolved_placeholders: list[dict[str, Any]],
    literal_secrets: list[dict[str, Any]],
    validation_errors: list[dict[str, Any]],
) -> str:
    """Compute overall configuration health status.

    Args:
        llm_configured: True if LLM is properly configured
        llm_misconfigured: True if LLM section exists but is invalid
        embedding_configured: True if embedding is properly configured
        embedding_misconfigured: True if embedding section exists but is invalid
        unresolved_placeholders: List of unresolved placeholder dicts
        literal_secrets: List of detected literal secrets
        validation_errors: List of validation error dicts

    Returns:
        Status string: "healthy", "warning", or "error"
    """
    # Critical errors
    if llm_misconfigured or embedding_misconfigured:
        return "error"
    if literal_secrets:
        return "error"
    if validation_errors:
        return "error"

    # Warnings
    if unresolved_placeholders:
        return "warning"
    if not llm_configured or not embedding_configured:
        return "warning"

    return "healthy"
