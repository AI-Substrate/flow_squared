"""ValidationService - Web UI validation composition layer.

Composes ConfigInspectorService with shared validation module to provide
structured validation results for the web UI.

Per Critical Insight #1: Uses shared validation module (single source of truth).
Per Critical Insight #2: Stateless - always loads fresh config on each call.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

from fs2.core.validation import (
    compute_overall_status,
    detect_literal_secrets,
    validate_embedding_config,
    validate_llm_config,
)
from fs2.web.services.config_inspector import (
    ConfigInspectorService,
    InspectionResult,
    PlaceholderState,
)


class ConfigInspector(Protocol):
    """Protocol for config inspection (allows fake injection)."""

    def inspect(self) -> InspectionResult: ...


@dataclass
class ValidationResult:
    """Result of configuration validation.

    Attributes:
        status: Overall status ("healthy", "warning", "error")
        llm_configured: True if LLM is properly configured
        llm_misconfigured: True if LLM section exists but is invalid
        llm_provider: Provider name if configured (e.g., "azure")
        llm_issues: List of LLM configuration issues
        embedding_configured: True if embedding is properly configured
        embedding_misconfigured: True if embedding section exists but invalid
        embedding_mode: Mode name if configured (e.g., "azure")
        embedding_issues: List of embedding configuration issues
        unresolved_placeholders: List of unresolved placeholder dicts
        literal_secrets: List of detected literal secrets (no actual values)
        issues: Combined list of all issue descriptions
        suggestions: Actionable fix suggestions
        warnings: Non-critical warnings
    """

    status: str = "healthy"
    llm_configured: bool = False
    llm_misconfigured: bool = False
    llm_provider: str | None = None
    llm_issues: list[str] = field(default_factory=list)
    embedding_configured: bool = False
    embedding_misconfigured: bool = False
    embedding_mode: str | None = None
    embedding_issues: list[str] = field(default_factory=list)
    unresolved_placeholders: list[dict[str, Any]] = field(default_factory=list)
    literal_secrets: list[dict[str, Any]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ValidationService:
    """Web UI validation service.

    Composes ConfigInspectorService with shared validation module.
    Returns structured ValidationResult for UI display.

    Usage:
        ```python
        inspector = ConfigInspectorService(...)
        service = ValidationService(inspector=inspector)
        result = service.validate()

        if result.status == "healthy":
            st.success("All checks passed!")
        elif result.status == "warning":
            for s in result.suggestions:
                st.warning(s)
        else:
            for issue in result.issues:
                st.error(issue)
        ```
    """

    def __init__(self, inspector: ConfigInspector | None = None) -> None:
        """Initialize with optional inspector.

        Args:
            inspector: Config inspector service (default: creates new one)
        """
        self._inspector = inspector or ConfigInspectorService()

    def validate(self) -> ValidationResult:
        """Run validation checks and return structured result.

        Returns:
            ValidationResult with status, issues, suggestions, etc.

        Raises:
            Exception: If inspector raises an error.
        """
        # Get config from inspector (may raise)
        inspection = self._inspector.inspect()
        config = inspection.raw_config

        # Validate LLM configuration
        llm_configured, llm_misconfigured, llm_issues = validate_llm_config(config)
        llm_provider = config.get("llm", {}).get("provider") if llm_configured else None

        # Validate embedding configuration
        emb_configured, emb_misconfigured, emb_issues = validate_embedding_config(
            config
        )
        emb_mode = config.get("embedding", {}).get("mode") if emb_configured else None

        # Find unresolved placeholders from inspection result
        unresolved_placeholders = [
            {"name": key.split(".")[-1], "path": key, "resolved": False}
            for key, state in inspection.placeholder_states.items()
            if state == PlaceholderState.UNRESOLVED
        ]

        # Detect literal secrets
        literal_secrets = detect_literal_secrets(config)

        # Build issues list
        issues: list[str] = []
        if llm_misconfigured:
            for issue in llm_issues:
                issues.append(f"LLM misconfigured: {issue}")
        if emb_misconfigured:
            for issue in emb_issues:
                issues.append(f"Embedding misconfigured: {issue}")
        if literal_secrets:
            issues.append("Literal secrets detected in config file")

        # Build suggestions
        suggestions: list[str] = []
        for p in unresolved_placeholders:
            suggestions.append(
                f"Set {p.get('name', 'unknown')} environment variable"
            )
        if llm_misconfigured:
            for issue in llm_issues:
                suggestions.append(f"Fix LLM config: {issue}")
        if emb_misconfigured:
            for issue in emb_issues:
                suggestions.append(f"Fix embedding config: {issue}")

        # Compute overall status
        status = compute_overall_status(
            llm_configured=llm_configured,
            llm_misconfigured=llm_misconfigured,
            embedding_configured=emb_configured,
            embedding_misconfigured=emb_misconfigured,
            unresolved_placeholders=unresolved_placeholders,
            literal_secrets=literal_secrets,
            validation_errors=[],  # Could add YAML/schema errors later
        )

        return ValidationResult(
            status=status,
            llm_configured=llm_configured,
            llm_misconfigured=llm_misconfigured,
            llm_provider=llm_provider,
            llm_issues=llm_issues,
            embedding_configured=emb_configured,
            embedding_misconfigured=emb_misconfigured,
            embedding_mode=emb_mode,
            embedding_issues=emb_issues,
            unresolved_placeholders=unresolved_placeholders,
            literal_secrets=literal_secrets,
            issues=issues,
            suggestions=suggestions,
            warnings=[],
        )
