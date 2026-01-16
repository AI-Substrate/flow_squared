"""Tests for fs2.core.validation - Shared validation module.

Full TDD tests for the shared validation module covering:
- T001: LLM configuration validation
- T001: Embedding configuration validation
- T001: Placeholder detection and resolution status
- T001: Literal secret detection
- T001: Suggestions and warnings generation
- T001: Overall health status computation

Per Critical Insight #1: This module is the single source of truth
for validation logic, used by both CLI (doctor.py) and Web (ValidationService).
"""

import pytest


# =============================================================================
# LLM CONFIGURATION VALIDATION TESTS
# =============================================================================


class TestValidateLLMConfig:
    """Tests for LLM configuration validation."""

    def test_given_azure_complete_config_when_validate_then_is_configured(self):
        """
        Purpose: Verifies complete Azure LLM config passes validation.
        Quality Contribution: Confirms properly configured providers are accepted.
        Acceptance Criteria: AC-06 - Doctor panel shows health status.
        """
        from fs2.core.validation.config_validator import validate_llm_config

        config = {
            "llm": {
                "provider": "azure",
                "base_url": "https://test.openai.azure.com/",
                "azure_deployment_name": "gpt-4",
                "azure_api_version": "2024-02-01",
                "api_key": "${AZURE_OPENAI_API_KEY}",
            }
        }

        is_configured, is_misconfigured, issues = validate_llm_config(config)

        assert is_configured is True
        assert is_misconfigured is False
        assert issues == []

    def test_given_azure_missing_base_url_when_validate_then_is_misconfigured(self):
        """
        Purpose: Verifies missing base_url detected for Azure.
        Quality Contribution: Catches common configuration error.
        Acceptance Criteria: AC-06 - Actionable fix suggestions.
        """
        from fs2.core.validation.config_validator import validate_llm_config

        config = {
            "llm": {
                "provider": "azure",
                "azure_deployment_name": "gpt-4",
                "azure_api_version": "2024-02-01",
            }
        }

        is_configured, is_misconfigured, issues = validate_llm_config(config)

        assert is_configured is False
        assert is_misconfigured is True
        assert any("base_url" in issue for issue in issues)

    def test_given_azure_missing_deployment_name_when_validate_then_is_misconfigured(
        self,
    ):
        """
        Purpose: Verifies missing deployment_name detected for Azure.
        Quality Contribution: Catches required field error.
        """
        from fs2.core.validation.config_validator import validate_llm_config

        config = {
            "llm": {
                "provider": "azure",
                "base_url": "https://test.openai.azure.com/",
                "azure_api_version": "2024-02-01",
            }
        }

        is_configured, is_misconfigured, issues = validate_llm_config(config)

        assert is_configured is False
        assert is_misconfigured is True
        assert any("deployment" in issue.lower() for issue in issues)

    def test_given_azure_missing_api_version_when_validate_then_is_misconfigured(self):
        """
        Purpose: Verifies missing api_version detected for Azure.
        Quality Contribution: Catches required field error.
        """
        from fs2.core.validation.config_validator import validate_llm_config

        config = {
            "llm": {
                "provider": "azure",
                "base_url": "https://test.openai.azure.com/",
                "azure_deployment_name": "gpt-4",
            }
        }

        is_configured, is_misconfigured, issues = validate_llm_config(config)

        assert is_configured is False
        assert is_misconfigured is True
        assert any("api_version" in issue.lower() for issue in issues)

    def test_given_no_llm_section_when_validate_then_not_configured(self):
        """
        Purpose: Verifies no LLM section handled gracefully.
        Quality Contribution: Distinguishes not configured from misconfigured.
        """
        from fs2.core.validation.config_validator import validate_llm_config

        config = {"scan": {"scan_paths": ["."]}}

        is_configured, is_misconfigured, issues = validate_llm_config(config)

        assert is_configured is False
        assert is_misconfigured is False
        assert issues == []

    def test_given_llm_missing_provider_when_validate_then_is_misconfigured(self):
        """
        Purpose: Verifies missing provider field detected.
        Quality Contribution: Provider is required when llm section exists.
        """
        from fs2.core.validation.config_validator import validate_llm_config

        config = {"llm": {"base_url": "https://example.com"}}

        is_configured, is_misconfigured, issues = validate_llm_config(config)

        assert is_configured is False
        assert is_misconfigured is True
        assert any("provider" in issue.lower() for issue in issues)


# =============================================================================
# EMBEDDING CONFIGURATION VALIDATION TESTS
# =============================================================================


class TestValidateEmbeddingConfig:
    """Tests for embedding configuration validation."""

    def test_given_azure_embedding_complete_when_validate_then_is_configured(self):
        """
        Purpose: Verifies complete Azure embedding config passes.
        Quality Contribution: Confirms properly configured embeddings.
        """
        from fs2.core.validation.config_validator import validate_embedding_config

        config = {
            "embedding": {
                "mode": "azure",
                "azure": {
                    "endpoint": "https://test.openai.azure.com",
                    "api_key": "${AZURE_EMBEDDING_API_KEY}",
                    "deployment_name": "text-embedding-3-small",
                },
            }
        }

        is_configured, is_misconfigured, issues = validate_embedding_config(config)

        assert is_configured is True
        assert is_misconfigured is False
        assert issues == []

    def test_given_azure_missing_endpoint_when_validate_then_is_misconfigured(self):
        """
        Purpose: Verifies missing endpoint detected.
        Quality Contribution: Catches required embedding config.
        """
        from fs2.core.validation.config_validator import validate_embedding_config

        config = {
            "embedding": {
                "mode": "azure",
                "azure": {
                    "api_key": "${AZURE_EMBEDDING_API_KEY}",
                },
            }
        }

        is_configured, is_misconfigured, issues = validate_embedding_config(config)

        assert is_configured is False
        assert is_misconfigured is True
        assert any("endpoint" in issue.lower() for issue in issues)

    def test_given_azure_missing_api_key_when_validate_then_is_misconfigured(self):
        """
        Purpose: Verifies missing api_key detected.
        Quality Contribution: Catches required field.
        """
        from fs2.core.validation.config_validator import validate_embedding_config

        config = {
            "embedding": {
                "mode": "azure",
                "azure": {
                    "endpoint": "https://test.openai.azure.com",
                },
            }
        }

        is_configured, is_misconfigured, issues = validate_embedding_config(config)

        assert is_configured is False
        assert is_misconfigured is True
        assert any("api_key" in issue.lower() for issue in issues)

    def test_given_no_embedding_section_when_validate_then_not_configured(self):
        """
        Purpose: Verifies no embedding section handled gracefully.
        """
        from fs2.core.validation.config_validator import validate_embedding_config

        config = {"scan": {"scan_paths": ["."]}}

        is_configured, is_misconfigured, issues = validate_embedding_config(config)

        assert is_configured is False
        assert is_misconfigured is False
        assert issues == []

    def test_given_embedding_missing_mode_when_validate_then_is_misconfigured(self):
        """
        Purpose: Verifies missing mode field detected.
        """
        from fs2.core.validation.config_validator import validate_embedding_config

        config = {
            "embedding": {
                "azure": {
                    "endpoint": "https://test.openai.azure.com",
                }
            }
        }

        is_configured, is_misconfigured, issues = validate_embedding_config(config)

        assert is_configured is False
        assert is_misconfigured is True
        assert any("mode" in issue.lower() for issue in issues)


# =============================================================================
# PLACEHOLDER DETECTION TESTS
# =============================================================================


class TestFindPlaceholders:
    """Tests for placeholder detection in config values."""

    def test_given_single_placeholder_when_find_then_returns_name_and_path(self):
        """
        Purpose: Verifies single placeholder detected correctly.
        Quality Contribution: Foundation for placeholder validation.
        """
        from fs2.core.validation.config_validator import find_placeholders_in_value

        value = "${MY_API_KEY}"
        path = "llm.api_key"

        placeholders = find_placeholders_in_value(value, path)

        assert len(placeholders) == 1
        assert placeholders[0]["name"] == "MY_API_KEY"
        assert placeholders[0]["path"] == "llm.api_key"

    def test_given_multiple_placeholders_in_string_when_find_then_returns_all(self):
        """
        Purpose: Verifies multiple placeholders in one string detected.
        Quality Contribution: Handles complex placeholder patterns.
        """
        from fs2.core.validation.config_validator import find_placeholders_in_value

        value = "https://${HOST}:${PORT}/api"
        path = "server.url"

        placeholders = find_placeholders_in_value(value, path)

        assert len(placeholders) == 2
        names = [p["name"] for p in placeholders]
        assert "HOST" in names
        assert "PORT" in names

    def test_given_nested_dict_when_find_then_returns_all_with_paths(self):
        """
        Purpose: Verifies placeholders found in nested config.
        Quality Contribution: Works with real config structures.
        """
        from fs2.core.validation.config_validator import find_placeholders_in_value

        value = {
            "llm": {"api_key": "${LLM_KEY}"},
            "embedding": {"azure": {"api_key": "${EMB_KEY}"}},
        }

        placeholders = find_placeholders_in_value(value)

        assert len(placeholders) == 2
        paths = [p["path"] for p in placeholders]
        assert "llm.api_key" in paths
        assert "embedding.azure.api_key" in paths

    def test_given_no_placeholders_when_find_then_returns_empty(self):
        """
        Purpose: Verifies no false positives.
        """
        from fs2.core.validation.config_validator import find_placeholders_in_value

        value = "just a regular string"

        placeholders = find_placeholders_in_value(value)

        assert placeholders == []

    def test_given_list_values_when_find_then_returns_with_indices(self):
        """
        Purpose: Verifies placeholders in lists detected with index paths.
        """
        from fs2.core.validation.config_validator import find_placeholders_in_value

        value = ["${VAR1}", "literal", "${VAR2}"]
        path = "items"

        placeholders = find_placeholders_in_value(value, path)

        assert len(placeholders) == 2
        paths = [p["path"] for p in placeholders]
        assert "items[0]" in paths
        assert "items[2]" in paths


class TestValidatePlaceholders:
    """Tests for placeholder resolution validation."""

    def test_given_resolved_placeholder_when_validate_then_marked_resolved(self):
        """
        Purpose: Verifies resolved placeholders identified.
        """
        from fs2.core.validation.config_validator import validate_placeholders

        config = {"llm": {"api_key": "${MY_KEY}"}}
        env_values = {"MY_KEY": "secret-value"}

        result = validate_placeholders(config, env_values)

        my_key = next((p for p in result if p["name"] == "MY_KEY"), None)
        assert my_key is not None
        assert my_key["resolved"] is True

    def test_given_unresolved_placeholder_when_validate_then_marked_unresolved(self):
        """
        Purpose: Verifies unresolved placeholders identified.
        """
        from fs2.core.validation.config_validator import validate_placeholders

        config = {"llm": {"api_key": "${MISSING_KEY}"}}
        env_values = {}

        result = validate_placeholders(config, env_values)

        missing = next((p for p in result if p["name"] == "MISSING_KEY"), None)
        assert missing is not None
        assert missing["resolved"] is False

    def test_given_duplicate_placeholder_when_validate_then_deduplicated(self):
        """
        Purpose: Verifies duplicate placeholders appear once.
        """
        from fs2.core.validation.config_validator import validate_placeholders

        config = {
            "llm": {"api_key": "${SHARED_KEY}"},
            "embedding": {"api_key": "${SHARED_KEY}"},
        }
        env_values = {"SHARED_KEY": "value"}

        result = validate_placeholders(config, env_values)

        shared_keys = [p for p in result if p["name"] == "SHARED_KEY"]
        assert len(shared_keys) == 1


# =============================================================================
# LITERAL SECRET DETECTION TESTS
# =============================================================================


class TestDetectLiteralSecrets:
    """Tests for literal secret detection."""

    def test_given_sk_prefix_when_detect_then_warns(self):
        """
        Purpose: Verifies sk-* prefix (OpenAI key format) detected.
        Quality Contribution: Prevents committing API keys.
        """
        from fs2.core.validation.config_validator import detect_literal_secrets

        config = {"llm": {"api_key": "sk-1234567890abcdefghijklmn"}}

        secrets = detect_literal_secrets(config)

        assert len(secrets) >= 1
        sk_secret = next((s for s in secrets if "sk-" in s.get("pattern", "")), None)
        assert sk_secret is not None
        assert "1234567890" not in str(sk_secret)  # Never expose actual value

    def test_given_long_secret_in_secret_field_when_detect_then_warns(self):
        """
        Purpose: Verifies long strings (>64 chars) in secret fields detected.
        """
        from fs2.core.validation.config_validator import detect_literal_secrets

        long_secret = "a" * 100
        config = {"llm": {"api_key": long_secret}}

        secrets = detect_literal_secrets(config)

        assert len(secrets) >= 1

    def test_given_placeholder_in_secret_field_when_detect_then_no_warning(self):
        """
        Purpose: Verifies placeholders don't trigger false warnings.
        """
        from fs2.core.validation.config_validator import detect_literal_secrets

        config = {"llm": {"api_key": "${AZURE_OPENAI_API_KEY}"}}

        secrets = detect_literal_secrets(config)

        assert len(secrets) == 0

    def test_given_short_value_in_secret_field_when_detect_then_no_warning(self):
        """
        Purpose: Verifies short values don't trigger false warnings.
        """
        from fs2.core.validation.config_validator import detect_literal_secrets

        config = {"llm": {"api_key": "test"}}  # Short test value

        secrets = detect_literal_secrets(config)

        # Short value without sk- prefix should not trigger
        sk_secrets = [s for s in secrets if "sk-" in s.get("pattern", "")]
        assert len(sk_secrets) == 0


# =============================================================================
# SUGGESTIONS GENERATION TESTS
# =============================================================================


class TestGetSuggestions:
    """Tests for actionable suggestions generation."""

    def test_given_unresolved_placeholder_when_get_suggestions_then_suggests_set_env(
        self,
    ):
        """
        Purpose: Verifies suggestion to set env var for unresolved placeholder.
        """
        from fs2.core.validation.config_validator import get_suggestions

        unresolved_placeholders = [
            {"name": "MY_API_KEY", "path": "llm.api_key", "resolved": False}
        ]
        config_exists = True

        suggestions = get_suggestions(
            config_exists=config_exists, unresolved_placeholders=unresolved_placeholders
        )

        assert any("MY_API_KEY" in s for s in suggestions)

    def test_given_no_config_when_get_suggestions_then_suggests_init(self):
        """
        Purpose: Verifies init suggestion when no config exists.
        """
        from fs2.core.validation.config_validator import get_suggestions

        suggestions = get_suggestions(config_exists=False, unresolved_placeholders=[])

        assert any("init" in s.lower() for s in suggestions)

    def test_given_healthy_config_when_get_suggestions_then_empty(self):
        """
        Purpose: Verifies no suggestions for healthy config.
        """
        from fs2.core.validation.config_validator import get_suggestions

        suggestions = get_suggestions(config_exists=True, unresolved_placeholders=[])

        assert suggestions == []


# =============================================================================
# WARNINGS GENERATION TESTS
# =============================================================================


class TestGetWarnings:
    """Tests for warnings generation."""

    def test_given_override_when_get_warnings_then_warns(self):
        """
        Purpose: Verifies warning when project overrides user config.
        """
        from fs2.core.validation.config_validator import get_warnings

        overrides = [
            {"path": "llm.timeout", "base_value": 30, "override_value": 60}
        ]
        has_user_config = True
        has_project_config = True

        warnings = get_warnings(
            overrides=overrides,
            has_user_config=has_user_config,
            has_project_config=has_project_config,
        )

        assert any("llm.timeout" in w for w in warnings)

    def test_given_user_only_no_project_when_get_warnings_then_warns_no_local(self):
        """
        Purpose: Verifies warning when user config exists but no project config.
        """
        from fs2.core.validation.config_validator import get_warnings

        warnings = get_warnings(
            overrides=[],
            has_user_config=True,
            has_project_config=False,
        )

        assert any("local" in w.lower() or ".fs2" in w for w in warnings)


# =============================================================================
# OVERALL HEALTH STATUS TESTS
# =============================================================================


class TestComputeOverallStatus:
    """Tests for overall health status computation."""

    def test_given_no_issues_when_compute_then_healthy(self):
        """
        Purpose: Verifies healthy status when no issues.
        """
        from fs2.core.validation.config_validator import compute_overall_status

        status = compute_overall_status(
            llm_configured=True,
            llm_misconfigured=False,
            embedding_configured=True,
            embedding_misconfigured=False,
            unresolved_placeholders=[],
            literal_secrets=[],
            validation_errors=[],
        )

        assert status == "healthy"

    def test_given_misconfigured_provider_when_compute_then_error(self):
        """
        Purpose: Verifies error status when provider misconfigured.
        """
        from fs2.core.validation.config_validator import compute_overall_status

        status = compute_overall_status(
            llm_configured=False,
            llm_misconfigured=True,
            embedding_configured=True,
            embedding_misconfigured=False,
            unresolved_placeholders=[],
            literal_secrets=[],
            validation_errors=[],
        )

        assert status == "error"

    def test_given_unresolved_placeholder_when_compute_then_warning(self):
        """
        Purpose: Verifies warning status for unresolved placeholders.
        """
        from fs2.core.validation.config_validator import compute_overall_status

        status = compute_overall_status(
            llm_configured=True,
            llm_misconfigured=False,
            embedding_configured=True,
            embedding_misconfigured=False,
            unresolved_placeholders=[{"name": "MISSING", "resolved": False}],
            literal_secrets=[],
            validation_errors=[],
        )

        assert status == "warning"

    def test_given_literal_secret_when_compute_then_error(self):
        """
        Purpose: Verifies error status when literal secrets found.
        """
        from fs2.core.validation.config_validator import compute_overall_status

        status = compute_overall_status(
            llm_configured=True,
            llm_misconfigured=False,
            embedding_configured=True,
            embedding_misconfigured=False,
            unresolved_placeholders=[],
            literal_secrets=[{"path": "llm.api_key", "pattern": "sk-*"}],
            validation_errors=[],
        )

        assert status == "error"

    def test_given_not_configured_when_compute_then_warning(self):
        """
        Purpose: Verifies warning status when providers not configured.
        """
        from fs2.core.validation.config_validator import compute_overall_status

        status = compute_overall_status(
            llm_configured=False,
            llm_misconfigured=False,
            embedding_configured=False,
            embedding_misconfigured=False,
            unresolved_placeholders=[],
            literal_secrets=[],
            validation_errors=[],
        )

        assert status == "warning"
