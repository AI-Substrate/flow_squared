"""fs2 doctor command implementation.

Diagnostic command that displays configuration health status including:
- Config file discovery (all 5 locations)
- Merge chain with source attribution and override warnings
- LLM and embedding provider status
- Placeholder resolution validation
- Literal secret detection
- YAML and schema validation
"""

import os
import re
from pathlib import Path
from typing import Any, Annotated

import typer
import yaml
from dotenv import dotenv_values
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fs2.config.paths import get_project_config_dir, get_user_config_dir
from fs2.config.loaders import load_yaml_config, deep_merge

console = Console()

# GitHub documentation URLs
GITHUB_BASE = "https://github.com/AI-Substrate/flow_squared/blob/main"
LLM_DOCS_URL = f"{GITHUB_BASE}/docs/how/user/configuration-guide.md#llm-configuration"
EMBEDDING_DOCS_URL = f"{GITHUB_BASE}/docs/how/user/configuration-guide.md#embedding-configuration"
CONFIG_DOCS_URL = f"{GITHUB_BASE}/docs/how/user/configuration-guide.md"

# Placeholder pattern: ${VAR_NAME}
PLACEHOLDER_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")

# Secret detection patterns
SK_PREFIX_PATTERN = re.compile(r"^sk-")
LONG_SECRET_MIN_LENGTH = 64


def discover_config_files() -> dict[str, dict[str, Any]]:
    """Discover all 5 config file locations and their existence status.

    Returns:
        Dictionary with keys for each config location containing:
        - exists: bool - whether file exists
        - path: str - full path to file
    """
    user_config_dir = get_user_config_dir()
    project_config_dir = get_project_config_dir()

    return {
        "user_config": {
            "exists": (user_config_dir / "config.yaml").exists(),
            "path": str(user_config_dir / "config.yaml"),
        },
        "user_secrets": {
            "exists": (user_config_dir / "secrets.env").exists(),
            "path": str(user_config_dir / "secrets.env"),
        },
        "project_config": {
            "exists": (project_config_dir / "config.yaml").exists(),
            "path": str(project_config_dir / "config.yaml"),
        },
        "project_secrets": {
            "exists": (project_config_dir / "secrets.env").exists(),
            "path": str(project_config_dir / "secrets.env"),
        },
        "dotenv": {
            "exists": (Path.cwd() / ".env").exists(),
            "path": str(Path.cwd() / ".env"),
        },
    }


def _load_config_safely(path: Path) -> tuple[dict[str, Any] | None, list[dict]]:
    """Load YAML config with error handling.

    Returns:
        Tuple of (config dict or None, list of errors)
    """
    errors = []
    if not path.exists():
        return None, errors

    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as e:
        errors.append({
            "type": "yaml_syntax",
            "file": str(path),
            "message": f"Encoding error: {e}",
            "line": 1,
        })
        return None, errors

    try:
        data = yaml.safe_load(content)
        return data if data else {}, errors
    except yaml.YAMLError as e:
        line = getattr(e, "problem_mark", None)
        line_num = line.line + 1 if line else 1
        errors.append({
            "type": "yaml_syntax",
            "file": str(path),
            "message": str(e),
            "line": line_num,
            "line_number": line_num,
        })
        return None, errors


def compute_merge_chain() -> dict[str, Any]:
    """Compute the merge chain showing config from each source.

    Returns:
        Dictionary with configs from each source and final merged result.
    """
    user_config_dir = get_user_config_dir()
    project_config_dir = get_project_config_dir()

    user_config = load_yaml_config(user_config_dir / "config.yaml")
    project_config = load_yaml_config(project_config_dir / "config.yaml")

    # Merge user -> project (project wins)
    merged = deep_merge(user_config, project_config)

    return {
        "user_config": user_config,
        "project_config": project_config,
        "final": merged,
    }


def _find_overrides(
    base: dict[str, Any],
    overlay: dict[str, Any],
    path: str = "",
) -> list[dict[str, Any]]:
    """Find leaf values in overlay that override values in base.

    Args:
        base: Base config (lower priority)
        overlay: Overlay config (higher priority)
        path: Current path prefix for nested keys

    Returns:
        List of override descriptions
    """
    overrides = []

    for key, overlay_value in overlay.items():
        current_path = f"{path}.{key}" if path else key

        if key in base:
            base_value = base[key]

            if isinstance(base_value, dict) and isinstance(overlay_value, dict):
                # Recurse into nested dicts
                overrides.extend(_find_overrides(base_value, overlay_value, current_path))
            elif base_value != overlay_value:
                # Leaf value override
                overrides.append({
                    "path": current_path,
                    "base_value": base_value,
                    "override_value": overlay_value,
                })

    return overrides


def detect_overrides() -> list[dict[str, Any]]:
    """Detect when project config overrides user config values.

    Returns:
        List of overrides with path, base value, and override value.
    """
    chain = compute_merge_chain()
    user_config = chain["user_config"]
    project_config = chain["project_config"]

    return _find_overrides(user_config, project_config)


def _validate_llm_config(config: dict[str, Any]) -> tuple[bool, bool, list[str]]:
    """Validate LLM configuration.

    Returns:
        Tuple of (is_configured, is_misconfigured, list of issues)
    """
    llm = config.get("llm")
    if not llm:
        return False, False, []

    provider = llm.get("provider")
    if not provider:
        return False, True, ["Missing 'provider' field"]

    issues = []
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


def _validate_embedding_config(config: dict[str, Any]) -> tuple[bool, bool, list[str]]:
    """Validate embedding configuration.

    Returns:
        Tuple of (is_configured, is_misconfigured, list of issues)
    """
    embedding = config.get("embedding")
    if not embedding:
        return False, False, []

    mode = embedding.get("mode")
    if not mode:
        return False, True, ["Missing 'mode' field"]

    issues = []
    if mode == "azure":
        azure = embedding.get("azure", {})
        if not azure.get("endpoint"):
            issues.append("azure.endpoint is required when mode=azure")
        if not azure.get("api_key"):
            issues.append("azure.api_key is required when mode=azure")

    if issues:
        return False, True, issues

    return True, False, []


def check_provider_status() -> dict[str, dict[str, Any]]:
    """Check configuration status for LLM and embedding providers.

    Returns:
        Dictionary with llm and embedding status including:
        - configured: bool
        - misconfigured: bool (True if section exists but is invalid)
        - provider/mode: str (if configured)
        - issues: list (if misconfigured)
        - docs_url: str (always present)
    """
    chain = compute_merge_chain()
    final_config = chain["final"]

    llm_configured, llm_misconfigured, llm_issues = _validate_llm_config(final_config)
    emb_configured, emb_misconfigured, emb_issues = _validate_embedding_config(final_config)

    return {
        "llm": {
            "configured": llm_configured,
            "misconfigured": llm_misconfigured,
            "provider": final_config.get("llm", {}).get("provider"),
            "issues": llm_issues,
            "docs_url": LLM_DOCS_URL,
        },
        "embedding": {
            "configured": emb_configured,
            "misconfigured": emb_misconfigured,
            "mode": final_config.get("embedding", {}).get("mode"),
            "issues": emb_issues,
            "docs_url": EMBEDDING_DOCS_URL,
        },
    }


def _find_placeholders_in_value(value: Any, path: str = "") -> list[dict[str, str]]:
    """Find ${VAR} placeholders in a config value recursively.

    Returns:
        List of dicts with name and path for each placeholder found.
    """
    placeholders = []

    if isinstance(value, str):
        for match in PLACEHOLDER_PATTERN.finditer(value):
            placeholders.append({
                "name": match.group(1),
                "path": path,
            })
    elif isinstance(value, dict):
        for k, v in value.items():
            current_path = f"{path}.{k}" if path else k
            placeholders.extend(_find_placeholders_in_value(v, current_path))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            current_path = f"{path}[{i}]"
            placeholders.extend(_find_placeholders_in_value(item, current_path))

    return placeholders


def _load_all_env_values() -> dict[str, str]:
    """Load all environment values from env files + os.environ (read-only).

    Returns:
        Combined dict of all available environment variables.
    """
    # Start with os.environ
    combined = dict(os.environ)

    # Load env files in precedence order (lower to higher)
    user_config_dir = get_user_config_dir()
    project_config_dir = get_project_config_dir()

    env_files = [
        user_config_dir / "secrets.env",      # lowest priority
        project_config_dir / "secrets.env",
        Path.cwd() / ".env",                  # highest priority
    ]

    for env_file in env_files:
        if env_file.exists():
            values = dotenv_values(env_file)
            combined.update(values)

    return combined


def validate_placeholders() -> list[dict[str, Any]]:
    """Find all ${VAR} placeholders and check if they resolve.

    Checks against os.environ AND values loaded from:
    - ~/.config/fs2/secrets.env
    - .fs2/secrets.env
    - .env

    Returns:
        List of placeholder dicts with name, path, and resolved status.
    """
    chain = compute_merge_chain()
    final_config = chain["final"]

    placeholders = _find_placeholders_in_value(final_config)

    # Load all env values (including from env files)
    all_env_values = _load_all_env_values()

    # Deduplicate by name and add resolved status
    seen = set()
    result = []
    for p in placeholders:
        if p["name"] not in seen:
            seen.add(p["name"])
            result.append({
                "name": p["name"],
                "path": p["path"],
                "resolved": p["name"] in all_env_values,
            })

    return result


def _find_secrets_in_value(
    value: Any, path: str = "", is_secret_field: bool = False
) -> list[dict[str, Any]]:
    """Find literal secrets in config values.

    Returns:
        List of secret warnings (never includes actual values).
    """
    secrets = []

    # Fields that typically contain secrets
    secret_field_names = {"api_key", "secret", "password", "token", "key"}

    if isinstance(value, str):
        # Check for sk-* prefix (OpenAI API key format)
        if SK_PREFIX_PATTERN.match(value):
            secrets.append({
                "path": path,
                "pattern": "sk-*",
                "reason": "OpenAI API key format detected",
            })
        # Check for long strings in secret fields (but not placeholders)
        elif is_secret_field and len(value) >= LONG_SECRET_MIN_LENGTH:
            if not PLACEHOLDER_PATTERN.search(value):
                secrets.append({
                    "path": path,
                    "pattern": f">{LONG_SECRET_MIN_LENGTH} chars",
                    "reason": "Long literal in secret field",
                })
    elif isinstance(value, dict):
        for k, v in value.items():
            current_path = f"{path}.{k}" if path else k
            is_secret = k.lower() in secret_field_names
            secrets.extend(_find_secrets_in_value(v, current_path, is_secret))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            current_path = f"{path}[{i}]"
            secrets.extend(_find_secrets_in_value(item, current_path, is_secret_field))

    return secrets


def detect_literal_secrets() -> list[dict[str, Any]]:
    """Detect literal secrets in config files.

    Returns:
        List of secret warnings (never includes actual values).
    """
    chain = compute_merge_chain()
    final_config = chain["final"]

    return _find_secrets_in_value(final_config)


def get_suggestions() -> list[str]:
    """Get actionable suggestions based on current config state.

    Returns:
        List of suggestion strings.
    """
    suggestions = []
    files = discover_config_files()

    # No configs at all -> suggest init
    if not files["project_config"]["exists"] and not files["user_config"]["exists"]:
        suggestions.append("Run 'fs2 init' to create configuration files")

    # Unresolved placeholders
    placeholders = validate_placeholders()
    unresolved = [p for p in placeholders if not p["resolved"]]
    for p in unresolved:
        suggestions.append(f"Set {p['name']} environment variable to enable {p['path']}")

    return suggestions


def get_warnings() -> list[str]:
    """Get warnings based on current config state.

    Returns:
        List of warning strings.
    """
    warnings = []
    files = discover_config_files()

    # Central config exists but no local .fs2/
    if files["user_config"]["exists"] and not files["project_config"]["exists"]:
        warnings.append(
            "User config exists but no local .fs2/ folder. "
            "Run 'fs2 init' to create project-specific config."
        )

    # Override warnings
    overrides = detect_overrides()
    for o in overrides:
        warnings.append(
            f"Local config overrides '{o['path']}': "
            f"{o['base_value']} → {o['override_value']}"
        )

    return warnings


def validate_configs() -> list[dict[str, Any]]:
    """Validate all config files for YAML syntax and schema errors.

    Returns:
        List of error dicts with type, file, message, and optional line/field.
    """
    errors = []

    user_config_dir = get_user_config_dir()
    project_config_dir = get_project_config_dir()

    # Check user config
    user_config_path = user_config_dir / "config.yaml"
    if user_config_path.exists():
        config, yaml_errors = _load_config_safely(user_config_path)
        errors.extend(yaml_errors)
        if config:
            errors.extend(_validate_schema(config, str(user_config_path)))

    # Check project config
    project_config_path = project_config_dir / "config.yaml"
    if project_config_path.exists():
        config, yaml_errors = _load_config_safely(project_config_path)
        errors.extend(yaml_errors)
        if config:
            errors.extend(_validate_schema(config, str(project_config_path)))

    return errors


def _validate_schema(config: dict[str, Any], file_path: str) -> list[dict[str, Any]]:
    """Validate config against Pydantic schemas.

    Returns:
        List of schema validation errors.
    """
    errors = []

    # Import config models
    from fs2.config.objects import ScanConfig, LLMConfig, EmbeddingConfig

    # Validate scan config
    if "scan" in config:
        try:
            ScanConfig(**config["scan"])
        except ValidationError as e:
            for err in e.errors():
                field_path = ".".join(str(x) for x in err["loc"])
                errors.append({
                    "type": "schema_validation",
                    "file": file_path,
                    "field": f"scan.{field_path}",
                    "message": err["msg"],
                    "expected_type": err.get("type", "unknown"),
                })

    # Validate LLM config
    if "llm" in config:
        try:
            LLMConfig(**config["llm"])
        except ValidationError as e:
            for err in e.errors():
                field_path = ".".join(str(x) for x in err["loc"])
                errors.append({
                    "type": "schema_validation",
                    "file": file_path,
                    "field": f"llm.{field_path}",
                    "message": err["msg"],
                    "expected_type": err.get("type", "unknown"),
                })

    # Validate embedding config
    if "embedding" in config:
        try:
            EmbeddingConfig(**config["embedding"])
        except ValidationError as e:
            for err in e.errors():
                field_path = ".".join(str(x) for x in err["loc"])
                errors.append({
                    "type": "schema_validation",
                    "file": file_path,
                    "field": f"embedding.{field_path}",
                    "message": err["msg"],
                    "expected_type": err.get("type", "unknown"),
                })

    return errors


def validate_provider_requirements() -> list[dict[str, Any]]:
    """Validate provider-specific requirements.

    Returns:
        List of provider validation errors with docs links.
    """
    chain = compute_merge_chain()
    final_config = chain["final"]

    errors = []

    # LLM provider validation
    llm = final_config.get("llm", {})
    provider = llm.get("provider")
    if provider == "azure":
        if not llm.get("base_url"):
            errors.append({
                "type": "provider_requirement",
                "field": "llm.base_url",
                "message": "base_url (endpoint) is required for Azure OpenAI",
                "docs_url": LLM_DOCS_URL,
            })
        if not llm.get("azure_deployment_name"):
            errors.append({
                "type": "provider_requirement",
                "field": "llm.azure_deployment_name",
                "message": "azure_deployment_name is required for Azure OpenAI",
                "docs_url": LLM_DOCS_URL,
            })
        if not llm.get("azure_api_version"):
            errors.append({
                "type": "provider_requirement",
                "field": "llm.azure_api_version",
                "message": "azure_api_version is required for Azure OpenAI",
                "docs_url": LLM_DOCS_URL,
            })

    # Embedding provider validation
    embedding = final_config.get("embedding", {})
    mode = embedding.get("mode")
    if mode == "azure":
        azure = embedding.get("azure", {})
        if not azure.get("endpoint"):
            errors.append({
                "type": "provider_requirement",
                "field": "embedding.azure.endpoint",
                "message": "azure.endpoint is required for Azure embeddings",
                "docs_url": EMBEDDING_DOCS_URL,
            })
        if not azure.get("api_key"):
            errors.append({
                "type": "provider_requirement",
                "field": "embedding.azure.api_key",
                "message": "azure.api_key is required for Azure embeddings",
                "docs_url": EMBEDDING_DOCS_URL,
            })

    return errors


def _has_critical_issues() -> bool:
    """Check if there are any critical issues that warrant exit code 1.

    Returns:
        True if critical issues found.
    """
    # Literal secrets are critical
    if detect_literal_secrets():
        return True

    # Schema validation errors are critical
    config_errors = validate_configs()
    if any(e["type"] == "yaml_syntax" for e in config_errors):
        return True
    if any(e["type"] == "schema_validation" for e in config_errors):
        return True

    # Provider requirement errors when provider is specified but incomplete
    provider_errors = validate_provider_requirements()
    if provider_errors:
        return True

    return False


def _render_output() -> None:
    """Render the doctor output using Rich."""
    cwd = Path.cwd()

    # Header panel
    console.print(Panel(
        f"[bold]Current Directory:[/bold] {cwd}",
        title="fs2 Configuration Health Check",
        border_style="blue",
    ))
    console.print()

    # Config files section with hierarchy
    console.print("[bold]📁 Configuration Files:[/bold]")
    files = discover_config_files()
    console.print()

    # Config (YAML) - highest priority first
    console.print("  [dim]Config (YAML) - first wins:[/dim]")
    user_cfg = files["user_config"]
    proj_cfg = files["project_config"]
    user_status = "[green]✓[/green]" if user_cfg["exists"] else "[red]✗[/red]"
    proj_status = "[green]✓[/green]" if proj_cfg["exists"] else "[red]✗[/red]"

    # Find FS2_* environment variables
    fs2_env_vars = {k: v for k, v in os.environ.items() if k.startswith("FS2_")}

    # Display in priority order (highest first)
    if fs2_env_vars:
        console.print(f"    1. [green]✓[/green] Environment (FS2_*) - {len(fs2_env_vars)} set")
        for var_name, var_value in sorted(fs2_env_vars.items()):
            # Mask values that look like secrets
            if "KEY" in var_name or "SECRET" in var_name or "PASSWORD" in var_name:
                display_value = "****"
            else:
                display_value = var_value if len(var_value) <= 40 else var_value[:37] + "..."
            console.print(f"       [dim]{var_name}={display_value}[/dim]")
    else:
        console.print("    1. [dim]✗ Environment (FS2_*) - none set[/dim]")
    console.print(f"    2. {proj_status} {proj_cfg['path']}")
    console.print(f"    3. {user_status} {user_cfg['path']}")
    console.print()

    # Secrets (ENV) - highest priority first
    console.print("  [dim]Secrets (ENV) - first wins:[/dim]")
    user_sec = files["user_secrets"]
    proj_sec = files["project_secrets"]
    dotenv = files["dotenv"]
    user_sec_status = "[green]✓[/green]" if user_sec["exists"] else "[red]✗[/red]"
    proj_sec_status = "[green]✓[/green]" if proj_sec["exists"] else "[red]✗[/red]"
    dotenv_status = "[green]✓[/green]" if dotenv["exists"] else "[red]✗[/red]"
    console.print(f"    1. {dotenv_status} {dotenv['path']}")
    console.print(f"    2. {proj_sec_status} {proj_sec['path']}")
    console.print(f"    3. {user_sec_status} {user_sec['path']}")
    console.print()

    # Provider status section
    console.print("[bold]🔌 Provider Status:[/bold]")
    providers = check_provider_status()

    llm = providers["llm"]
    if llm["configured"]:
        console.print(f"  [green]✓[/green] LLM: {llm['provider']} (configured)")
    elif llm["misconfigured"]:
        console.print(f"  [red]✗[/red] LLM: {llm['provider']} (misconfigured)")
        for issue in llm["issues"]:
            console.print(f"      {issue}")
        console.print(f"    → {llm['docs_url']}", soft_wrap=True)
    else:
        console.print("  [red]✗[/red] LLM: NOT CONFIGURED")
        console.print(f"    → {llm['docs_url']}", soft_wrap=True)

    emb = providers["embedding"]
    if emb["configured"]:
        console.print(f"  [green]✓[/green] Embeddings: {emb['mode']} (configured)")
    elif emb["misconfigured"]:
        console.print(f"  [red]✗[/red] Embeddings: {emb['mode']} (misconfigured)")
        for issue in emb["issues"]:
            console.print(f"      {issue}")
        console.print(f"    → {emb['docs_url']}", soft_wrap=True)
    else:
        console.print("  [red]✗[/red] Embeddings: NOT CONFIGURED")
        console.print(f"    → {emb['docs_url']}", soft_wrap=True)
    console.print()

    # Placeholders section
    placeholders = validate_placeholders()
    if placeholders:
        console.print("[bold]🔐 Secrets & Placeholders:[/bold]")
        for p in placeholders:
            status = "[green]✓[/green]" if p["resolved"] else "[red]✗[/red] NOT FOUND"
            console.print(f"  {status} ${{{p['name']}}} → {'resolved' if p['resolved'] else 'NOT FOUND'}")
        console.print()

    # Warnings section
    warnings = get_warnings()
    secrets = detect_literal_secrets()
    if warnings or secrets:
        console.print("[bold]⚠️  Warnings:[/bold]")
        for w in warnings:
            console.print(f"  • {w}")
        for s in secrets:
            console.print(f"  • [red]Literal secret detected[/red] at '{s['path']}' ({s['reason']})")
        console.print()

    # Validation errors section
    config_errors = validate_configs()
    provider_errors = validate_provider_requirements()
    all_errors = config_errors + provider_errors
    if all_errors:
        console.print("[bold]❌ Validation Errors:[/bold]")
        for e in all_errors:
            if e["type"] == "yaml_syntax":
                console.print(f"  • YAML error in {e['file']} line {e.get('line', '?')}: {e['message']}")
            elif e["type"] == "schema_validation":
                console.print(f"  • Schema error: {e['field']} - {e['message']}")
            elif e["type"] == "provider_requirement":
                console.print(f"  • Missing: {e['field']} - {e['message']}")
                console.print(f"    → {e['docs_url']}", soft_wrap=True)
        console.print()

    # Suggestions section
    suggestions = get_suggestions()
    if suggestions:
        console.print("[bold]💡 Suggestions:[/bold]")
        for s in suggestions:
            console.print(f"  • {s}")


def doctor() -> None:
    """Check fs2 configuration health.

    Displays configuration status including:
    - All config file locations (found/not found)
    - LLM and embedding provider status
    - Placeholder resolution status
    - Warnings about literal secrets
    - Actionable suggestions

    \b
    Example:
        $ fs2 doctor
        [Shows configuration health status]
    """
    _render_output()

    if _has_critical_issues():
        raise typer.Exit(1)
