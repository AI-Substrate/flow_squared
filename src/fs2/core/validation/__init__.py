"""fs2.core.validation - Shared validation module.

Single source of truth for configuration validation logic,
used by both CLI (doctor.py) and Web (ValidationService).

Per Critical Insight #1: Extracting validation to a shared module
prevents drift between CLI and Web implementations.

This module exports pure functions - no CLI or web dependencies.
"""

from fs2.core.validation.config_validator import (
    compute_overall_status,
    detect_literal_secrets,
    find_placeholders_in_value,
    get_suggestions,
    get_warnings,
    validate_embedding_config,
    validate_llm_config,
    validate_placeholders,
)
from fs2.core.validation.constants import (
    EMBEDDING_DOCS_URL,
    LLM_DOCS_URL,
    LONG_SECRET_MIN_LENGTH,
    PLACEHOLDER_PATTERN,
    SK_PREFIX_PATTERN,
)

__all__ = [
    # Validators
    "validate_llm_config",
    "validate_embedding_config",
    "validate_placeholders",
    "find_placeholders_in_value",
    "detect_literal_secrets",
    # Suggestions and warnings
    "get_suggestions",
    "get_warnings",
    # Status computation
    "compute_overall_status",
    # Constants
    "LLM_DOCS_URL",
    "EMBEDDING_DOCS_URL",
    "PLACEHOLDER_PATTERN",
    "SK_PREFIX_PATTERN",
    "LONG_SECRET_MIN_LENGTH",
]
