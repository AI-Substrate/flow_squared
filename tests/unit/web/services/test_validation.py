"""Tests for ValidationService - Web UI validation composition layer.

Full TDD tests for the ValidationService which composes:
- ConfigInspectorService (read-only config inspection)
- Shared validation module (core validation logic)

Per Critical Insight #1: ValidationService is a thin wrapper that:
- Uses ConfigInspectorService to get config data
- Passes config to shared validation functions
- Returns structured ValidationResult

Per Critical Insight #2: No caching - each call loads fresh config.
"""

import pytest

from fs2.web.services.config_inspector import (
    ConfigValue,
    InspectionResult,
    PlaceholderState,
)


# =============================================================================
# VALIDATION RESULT DATACLASS TESTS
# =============================================================================


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_given_healthy_result_when_access_then_has_correct_properties(self):
        """
        Purpose: Verifies ValidationResult structure for healthy config.
        Quality Contribution: Foundation for service return type.
        """
        from fs2.web.services.validation import ValidationResult

        result = ValidationResult(
            status="healthy",
            llm_configured=True,
            llm_provider="azure",
            embedding_configured=True,
            embedding_mode="azure",
            issues=[],
            suggestions=[],
            warnings=[],
        )

        assert result.status == "healthy"
        assert result.llm_configured is True
        assert result.llm_provider == "azure"
        assert result.embedding_configured is True
        assert result.issues == []

    def test_given_error_result_when_access_then_has_issues(self):
        """
        Purpose: Verifies ValidationResult with issues.
        """
        from fs2.web.services.validation import ValidationResult

        result = ValidationResult(
            status="error",
            llm_configured=False,
            llm_misconfigured=True,
            llm_issues=["base_url is required"],
            embedding_configured=False,
            issues=["LLM misconfigured: base_url is required"],
            suggestions=["Add base_url to llm section"],
            warnings=[],
        )

        assert result.status == "error"
        assert result.llm_misconfigured is True
        assert len(result.issues) == 1
        assert "base_url" in result.issues[0]

    def test_given_warning_result_when_access_then_has_unresolved_placeholders(self):
        """
        Purpose: Verifies ValidationResult with placeholder warnings.
        """
        from fs2.web.services.validation import ValidationResult

        result = ValidationResult(
            status="warning",
            llm_configured=True,
            embedding_configured=True,
            unresolved_placeholders=[
                {"name": "AZURE_KEY", "path": "llm.api_key", "resolved": False}
            ],
            issues=[],
            suggestions=["Set AZURE_KEY environment variable"],
            warnings=[],
        )

        assert result.status == "warning"
        assert len(result.unresolved_placeholders) == 1
        assert result.unresolved_placeholders[0]["name"] == "AZURE_KEY"


# =============================================================================
# VALIDATION SERVICE COMPOSITION TESTS
# =============================================================================


class TestValidationServiceComposition:
    """Tests for ValidationService composing inspector + validation."""

    def test_given_fake_inspector_when_validate_then_uses_inspector_data(self):
        """
        Purpose: Verifies ValidationService calls ConfigInspectorService.
        Quality Contribution: Ensures proper composition.
        """
        from fs2.web.services.config_inspector_fake import FakeConfigInspectorService
        from fs2.web.services.validation import ValidationService

        # Setup fake with config data
        fake_inspector = FakeConfigInspectorService()
        fake_inspector.set_result(
            InspectionResult(
                raw_config={
                    "llm": {
                        "provider": "azure",
                        "base_url": "https://test.azure.com",
                        "azure_deployment_name": "gpt-4",
                        "azure_api_version": "2024-02-01",
                    }
                },
                attribution={},
                placeholder_states={},
            )
        )

        service = ValidationService(inspector=fake_inspector)
        result = service.validate()

        # Verify inspector was called
        assert "inspect" in fake_inspector.call_history
        assert result.llm_configured is True

    def test_given_missing_llm_section_when_validate_then_not_configured(self):
        """
        Purpose: Verifies detection of missing LLM config.
        """
        from fs2.web.services.config_inspector_fake import FakeConfigInspectorService
        from fs2.web.services.validation import ValidationService

        fake_inspector = FakeConfigInspectorService()
        fake_inspector.set_result(
            InspectionResult(
                raw_config={"scan": {"scan_paths": ["."]}},
                attribution={},
                placeholder_states={},
            )
        )

        service = ValidationService(inspector=fake_inspector)
        result = service.validate()

        assert result.llm_configured is False
        assert result.llm_misconfigured is False

    def test_given_misconfigured_llm_when_validate_then_returns_issues(self):
        """
        Purpose: Verifies detection of misconfigured LLM.
        """
        from fs2.web.services.config_inspector_fake import FakeConfigInspectorService
        from fs2.web.services.validation import ValidationService

        fake_inspector = FakeConfigInspectorService()
        fake_inspector.set_result(
            InspectionResult(
                raw_config={
                    "llm": {
                        "provider": "azure",
                        # Missing base_url, deployment_name, api_version
                    }
                },
                attribution={},
                placeholder_states={},
            )
        )

        service = ValidationService(inspector=fake_inspector)
        result = service.validate()

        assert result.llm_configured is False
        assert result.llm_misconfigured is True
        assert result.status == "error"
        assert len(result.llm_issues) >= 1


class TestValidationServicePlaceholders:
    """Tests for placeholder validation in service."""

    def test_given_unresolved_placeholder_when_validate_then_status_warning(self):
        """
        Purpose: Verifies unresolved placeholders cause warning status.
        """
        from fs2.web.services.config_inspector_fake import FakeConfigInspectorService
        from fs2.web.services.validation import ValidationService

        fake_inspector = FakeConfigInspectorService()
        fake_inspector.set_result(
            InspectionResult(
                raw_config={
                    "llm": {
                        "provider": "azure",
                        "base_url": "https://test.azure.com",
                        "azure_deployment_name": "gpt-4",
                        "azure_api_version": "2024-02-01",
                        "api_key": "${AZURE_KEY}",
                    },
                    "embedding": {
                        "mode": "azure",
                        "azure": {
                            "endpoint": "https://test.azure.com",
                            "api_key": "${EMB_KEY}",
                            "deployment_name": "embed-3",
                        },
                    },
                },
                attribution={},
                placeholder_states={"llm.api_key": PlaceholderState.UNRESOLVED},
            )
        )

        service = ValidationService(inspector=fake_inspector)
        result = service.validate()

        assert result.status == "warning"
        assert len(result.unresolved_placeholders) >= 1

    def test_given_resolved_placeholders_when_validate_then_no_warning(self):
        """
        Purpose: Verifies resolved placeholders don't cause warnings.
        """
        from fs2.web.services.config_inspector_fake import FakeConfigInspectorService
        from fs2.web.services.validation import ValidationService

        fake_inspector = FakeConfigInspectorService()
        fake_inspector.set_result(
            InspectionResult(
                raw_config={
                    "llm": {
                        "provider": "azure",
                        "base_url": "https://test.azure.com",
                        "azure_deployment_name": "gpt-4",
                        "azure_api_version": "2024-02-01",
                    },
                    "embedding": {
                        "mode": "azure",
                        "azure": {
                            "endpoint": "https://test.azure.com",
                            "api_key": "${EMB_KEY}",
                            "deployment_name": "embed-3",
                        },
                    },
                },
                attribution={},
                placeholder_states={"llm.api_key": PlaceholderState.RESOLVED},
            )
        )

        service = ValidationService(inspector=fake_inspector)
        result = service.validate()

        # Should be healthy because placeholders are resolved
        assert result.status == "healthy"


class TestValidationServiceSecrets:
    """Tests for literal secret detection in service."""

    def test_given_sk_prefix_in_config_when_validate_then_error_status(self):
        """
        Purpose: Verifies sk-* prefix detection causes error.
        """
        from fs2.web.services.config_inspector_fake import FakeConfigInspectorService
        from fs2.web.services.validation import ValidationService

        fake_inspector = FakeConfigInspectorService()
        fake_inspector.set_result(
            InspectionResult(
                raw_config={
                    "llm": {
                        "provider": "azure",
                        "base_url": "https://test.azure.com",
                        "azure_deployment_name": "gpt-4",
                        "azure_api_version": "2024-02-01",
                        "api_key": "sk-1234567890abcdef",  # Literal secret!
                    },
                    "embedding": {
                        "mode": "azure",
                        "azure": {
                            "endpoint": "https://test.azure.com",
                            "api_key": "${EMB_KEY}",
                            "deployment_name": "embed-3",
                        },
                    },
                },
                attribution={},
                placeholder_states={},
            )
        )

        service = ValidationService(inspector=fake_inspector)
        result = service.validate()

        assert result.status == "error"
        assert len(result.literal_secrets) >= 1


class TestValidationServiceOverallStatus:
    """Tests for overall status computation."""

    def test_given_fully_healthy_when_validate_then_status_healthy(self):
        """
        Purpose: Verifies healthy status when all checks pass.
        """
        from fs2.web.services.config_inspector_fake import FakeConfigInspectorService
        from fs2.web.services.validation import ValidationService

        fake_inspector = FakeConfigInspectorService()
        fake_inspector.set_result(
            InspectionResult(
                raw_config={
                    "llm": {
                        "provider": "azure",
                        "base_url": "https://test.azure.com",
                        "azure_deployment_name": "gpt-4",
                        "azure_api_version": "2024-02-01",
                    },
                    "embedding": {
                        "mode": "azure",
                        "azure": {
                            "endpoint": "https://test.azure.com",
                            "api_key": "${EMB_KEY}",
                            "deployment_name": "embed-3",
                        },
                    },
                },
                attribution={},
                placeholder_states={},
            )
        )

        service = ValidationService(inspector=fake_inspector)
        result = service.validate()

        assert result.status == "healthy"
        assert result.llm_configured is True
        assert result.embedding_configured is True
        assert result.issues == []

    def test_given_no_providers_when_validate_then_status_warning(self):
        """
        Purpose: Verifies warning when no providers configured.
        """
        from fs2.web.services.config_inspector_fake import FakeConfigInspectorService
        from fs2.web.services.validation import ValidationService

        fake_inspector = FakeConfigInspectorService()
        fake_inspector.set_result(
            InspectionResult(
                raw_config={"scan": {"scan_paths": ["."]}},
                attribution={},
                placeholder_states={},
            )
        )

        service = ValidationService(inspector=fake_inspector)
        result = service.validate()

        assert result.status == "warning"
        assert result.llm_configured is False
        assert result.embedding_configured is False


class TestValidationServiceErrorHandling:
    """Tests for error handling in validation service."""

    def test_given_inspector_error_when_validate_then_propagates_error(self):
        """
        Purpose: Verifies errors from inspector are handled.
        """
        from fs2.web.services.config_inspector_fake import FakeConfigInspectorService
        from fs2.web.services.validation import ValidationService

        fake_inspector = FakeConfigInspectorService()
        fake_inspector.simulate_error = ValueError("Test inspector error")

        service = ValidationService(inspector=fake_inspector)

        with pytest.raises(ValueError, match="Test inspector error"):
            service.validate()
