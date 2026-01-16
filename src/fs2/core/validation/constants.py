"""Constants for configuration validation.

Shared constants used by both CLI and Web validation.
"""

import re

# GitHub documentation URLs
GITHUB_BASE = "https://github.com/AI-Substrate/flow_squared/blob/main"
LLM_DOCS_URL = f"{GITHUB_BASE}/docs/how/user/configuration-guide.md#llm-configuration"
EMBEDDING_DOCS_URL = (
    f"{GITHUB_BASE}/docs/how/user/configuration-guide.md#embedding-configuration"
)
CONFIG_DOCS_URL = f"{GITHUB_BASE}/docs/how/user/configuration-guide.md"

# Placeholder pattern: ${VAR_NAME}
PLACEHOLDER_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")

# Secret detection patterns
SK_PREFIX_PATTERN = re.compile(r"^sk-")
LONG_SECRET_MIN_LENGTH = 64

# Fields that typically contain secrets
SECRET_FIELD_NAMES = frozenset(
    {"api_key", "secret", "password", "token", "key"}
)
