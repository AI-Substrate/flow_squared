"""Configuration error hierarchy for fs2.

Provides actionable error messages for configuration issues.

Error Type Guidelines (per Insight #7):
| Error Type               | Use For                                          |
|--------------------------|--------------------------------------------------|
| pydantic.ValidationError | Missing required field, wrong type               |
| LiteralSecretError       | Literal secret in config                         |
| MissingConfigurationError| Missing env var in placeholder expansion         |

Per Finding 05: Errors must include actionable guidance.
"""


class ConfigurationError(Exception):
    """Base configuration error with actionable guidance.

    All configuration errors should provide clear instructions
    on how to fix the issue.
    """


class MissingConfigurationError(ConfigurationError):
    """Missing configuration value.

    Raised when a required configuration value is missing,
    typically during placeholder expansion when the referenced
    environment variable is not set.
    """

    def __init__(self, key: str, sources: list[str]):
        """Create actionable error message.

        Args:
            key: The configuration key or environment variable name
            sources: List of sources where the value could be set
        """
        self.key = key
        self.sources = sources
        msg = f"Missing configuration: {key}\n"
        msg += "Set one of:\n"
        for src in sources:
            msg += f"  - {src}\n"
        super().__init__(msg)


class LiteralSecretError(ConfigurationError):
    """Literal secret detected in configuration.

    Raised when a configuration value appears to be a literal
    secret (e.g., starts with 'sk-' or is unusually long).
    Secrets should use ${ENV_VAR} placeholders instead.
    """

    def __init__(self, field: str):
        """Create actionable error message.

        Args:
            field: The field name containing the literal secret
        """
        self.field = field
        msg = f"Literal secret detected in '{field}'\n"
        msg += f"Use placeholder: ${{{field.upper()}}}\n"
        msg += f"Then set environment variable: {field.upper()}=<your-secret>"
        super().__init__(msg)
