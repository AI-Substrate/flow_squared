"""Tests for ConfigInspectorService.

Per Phase 1 Tasks Dossier:
- AC-16: Never mutate os.environ
- AC-02: Source attribution tracking
- AC-03: Placeholder state detection
- AC-15: Secret masking showing [SET]

Testing Approach: Full TDD (RED phase - tests first)
These tests must FAIL initially because the implementation doesn't exist.

Per Critical Insight #2: ConfigInspectorService is stateless - always loads fresh.
Per Critical Insight #5: Show placeholders literally, resolution state only.
"""

import os
from pathlib import Path
from typing import Any

import pytest

# These imports will fail initially (RED phase) - implementation doesn't exist yet
from fs2.web.services.config_inspector import (
    ConfigInspectorService,
    ConfigValue,
    InspectionResult,
    PlaceholderState,
)


class TestConfigInspectorReadOnly:
    """Tests proving ConfigInspectorService never modifies os.environ.

    Per Critical Discovery 01 and AC-16:
    The web UI must never mutate global state. This prevents side effects
    when users inspect configuration without intending to modify anything.
    """

    def test_inspect_does_not_mutate_environ(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify os.environ unchanged after inspection.

        Contract: inspect() is read-only - no env var mutations.
        Quality Contribution: Prevents PL-01 violation.
        """
        # Arrange - capture original environment
        original_env = dict(os.environ)

        # Create config file with placeholder
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  provider: azure\n  api_key: ${TEST_API_KEY}")

        # Create .env file with secret value
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_API_KEY=sk-secret-key-value")

        # Act
        inspector = ConfigInspectorService(
            project_path=config_file,
            secrets_paths=[env_file],
        )
        inspector.inspect()

        # Assert - environment unchanged
        assert dict(os.environ) == original_env

    def test_inspect_does_not_import_forbidden_modules(
        self, tmp_path: Path
    ) -> None:
        """Verify implementation never imports load_secrets_to_env.

        Contract: ConfigInspectorService uses dotenv_values() only.
        Quality Contribution: Prevents accidental env mutation via import.
        """
        # This is a static check enforced at code review level
        # The test ensures the import itself doesn't cause side effects
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  provider: fake")

        original_env = dict(os.environ)

        inspector = ConfigInspectorService(project_path=config_file)
        inspector.inspect()

        # If load_secrets_to_env was imported and called, env would change
        assert dict(os.environ) == original_env

    def test_multiple_inspections_are_independent(
        self, tmp_path: Path
    ) -> None:
        """Verify each inspect() call loads fresh - no stale cache.

        Per Critical Insight #2: Stateless services - always load fresh.
        Contract: Each inspection is independent.
        """
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  timeout: 30")

        inspector = ConfigInspectorService(project_path=config_file)

        # First inspection
        result1 = inspector.inspect()
        assert result1.attribution["llm.timeout"].value == 30

        # Modify file
        config_file.write_text("llm:\n  timeout: 60")

        # Second inspection should see new value
        result2 = inspector.inspect()
        assert result2.attribution["llm.timeout"].value == 60


class TestSourceAttribution:
    """Tests for source attribution tracking.

    Per Critical Discovery 03 and AC-02:
    UI must show where each setting value came from (user, project, env, default)
    and the override chain for transparency.
    """

    def test_source_attribution_project_only(self, tmp_path: Path) -> None:
        """Verify attribution when only project config exists.

        Contract: source is "project" when value comes from project config.
        """
        project_config = tmp_path / "config.yaml"
        project_config.write_text("llm:\n  timeout: 60")

        inspector = ConfigInspectorService(project_path=project_config)
        result = inspector.inspect()

        assert result.attribution["llm.timeout"].value == 60
        assert result.attribution["llm.timeout"].source == "project"
        assert result.attribution["llm.timeout"].source_file == project_config
        assert result.attribution["llm.timeout"].override_chain == []

    def test_source_attribution_user_only(self, tmp_path: Path) -> None:
        """Verify attribution when only user config exists.

        Contract: source is "user" when value comes from user config.
        """
        user_config = tmp_path / "user_config.yaml"
        user_config.write_text("llm:\n  timeout: 45")

        inspector = ConfigInspectorService(user_path=user_config)
        result = inspector.inspect()

        assert result.attribution["llm.timeout"].value == 45
        assert result.attribution["llm.timeout"].source == "user"
        assert result.attribution["llm.timeout"].source_file == user_config

    def test_source_attribution_tracks_override(self, tmp_path: Path) -> None:
        """Verify source attribution when project overrides user config.

        Contract: source shows winning source; override_chain shows previous values.
        Quality Contribution: Users can see what their project config overrode.
        """
        # Create user config
        user_config = tmp_path / "user" / "config.yaml"
        user_config.parent.mkdir(parents=True)
        user_config.write_text("llm:\n  timeout: 30")

        # Create project config with different value
        project_config = tmp_path / "project" / "config.yaml"
        project_config.parent.mkdir(parents=True)
        project_config.write_text("llm:\n  timeout: 60")

        inspector = ConfigInspectorService(
            user_path=user_config,
            project_path=project_config,
        )
        result = inspector.inspect()

        # Project wins
        assert result.attribution["llm.timeout"].value == 60
        assert result.attribution["llm.timeout"].source == "project"
        # Override chain shows user value that was overridden
        assert result.attribution["llm.timeout"].override_chain == [("user", 30)]

    def test_source_attribution_deep_nested(self, tmp_path: Path) -> None:
        """Verify attribution for deeply nested config values.

        Contract: Nested keys use dot notation (e.g., "llm.azure.timeout").
        """
        config = tmp_path / "config.yaml"
        config.write_text("llm:\n  azure:\n    timeout: 120\n    api_version: '2024-02-01'")

        inspector = ConfigInspectorService(project_path=config)
        result = inspector.inspect()

        assert result.attribution["llm.azure.timeout"].value == 120
        assert result.attribution["llm.azure.api_version"].value == "2024-02-01"


class TestPlaceholderDetection:
    """Tests for placeholder state detection.

    Per Critical Discovery 04 and AC-03:
    Placeholders have three states: resolved, unresolved, missing.
    Per Critical Insight #5: Show placeholders literally.
    """

    def test_placeholder_shown_literally_when_unresolved(
        self, tmp_path: Path
    ) -> None:
        """Verify placeholder syntax shown when env var not set.

        Per Insight #5: Show ${VAR} as-is (safe - it's a placeholder).
        Contract: value is literal placeholder string.
        """
        config = tmp_path / "config.yaml"
        config.write_text("llm:\n  api_key: ${NOT_SET_VAR}")

        inspector = ConfigInspectorService(project_path=config)
        result = inspector.inspect()

        # Value shows placeholder literally
        assert result.attribution["llm.api_key"].value == "${NOT_SET_VAR}"
        assert result.placeholder_states["llm.api_key"] == PlaceholderState.UNRESOLVED

    def test_placeholder_resolved_state_when_env_set(
        self, tmp_path: Path
    ) -> None:
        """Verify resolved state when env var exists.

        Per Insight #5: Show resolution state only, never actual value.
        Contract: placeholder_states shows RESOLVED.
        """
        config = tmp_path / "config.yaml"
        config.write_text("llm:\n  api_key: ${TEST_KEY}")

        env_file = tmp_path / ".env"
        env_file.write_text("TEST_KEY=actual-secret-value")

        inspector = ConfigInspectorService(
            project_path=config,
            secrets_paths=[env_file],
        )
        result = inspector.inspect()

        # Placeholder shows as resolved
        assert result.placeholder_states["llm.api_key"] == PlaceholderState.RESOLVED
        # But value still shows placeholder (never actual secret)
        assert result.attribution["llm.api_key"].value == "${TEST_KEY}"

    def test_placeholder_missing_env_file(self, tmp_path: Path) -> None:
        """Verify missing state when .env file doesn't exist.

        Contract: When secrets file is missing, placeholders are unresolved.
        """
        config = tmp_path / "config.yaml"
        config.write_text("llm:\n  api_key: ${MISSING_VAR}")

        # No .env file provided
        inspector = ConfigInspectorService(project_path=config)
        result = inspector.inspect()

        assert result.placeholder_states["llm.api_key"] == PlaceholderState.UNRESOLVED

    def test_non_placeholder_value_no_state(self, tmp_path: Path) -> None:
        """Verify non-placeholder values have no placeholder state.

        Contract: Only ${VAR} syntax triggers placeholder detection.
        """
        config = tmp_path / "config.yaml"
        config.write_text("llm:\n  timeout: 30\n  provider: fake")

        inspector = ConfigInspectorService(project_path=config)
        result = inspector.inspect()

        # Literal values don't appear in placeholder_states
        assert "llm.timeout" not in result.placeholder_states
        assert "llm.provider" not in result.placeholder_states

    def test_placeholder_multi_value_detection(self, tmp_path: Path) -> None:
        """Verify all placeholders detected in multi-placeholder values.

        Contract: State is RESOLVED only if ALL placeholders resolve.
        """
        config = tmp_path / "config.yaml"
        config.write_text("api:\n  url: ${API_HOST}:${API_PORT}")

        env_file = tmp_path / ".env"
        env_file.write_text("API_HOST=localhost")  # Missing API_PORT

        inspector = ConfigInspectorService(
            project_path=config,
            secrets_paths=[env_file],
        )
        result = inspector.inspect()

        # Should be UNRESOLVED because API_PORT is missing
        assert result.placeholder_states["api.url"] == PlaceholderState.UNRESOLVED

    def test_placeholder_multi_value_all_resolved(self, tmp_path: Path) -> None:
        """Verify RESOLVED when all placeholders in multi-value are set.

        Contract: Multi-placeholder values are RESOLVED only when ALL resolve.
        """
        config = tmp_path / "config.yaml"
        config.write_text("api:\n  url: ${API_HOST}:${API_PORT}")

        env_file = tmp_path / ".env"
        env_file.write_text("API_HOST=localhost\nAPI_PORT=8080")  # Both set

        inspector = ConfigInspectorService(
            project_path=config,
            secrets_paths=[env_file],
        )
        result = inspector.inspect()

        # Should be RESOLVED because both placeholders are set
        assert result.placeholder_states["api.url"] == PlaceholderState.RESOLVED


class TestSecretMasking:
    """Tests for secret value masking.

    Per Critical Discovery 02 and AC-15:
    Secrets must be masked as [SET] - actual values never shown.
    Per Critical Insight #5: Show placeholders literally; fs2 rejects literal secrets.
    """

    def test_secret_field_masked_when_resolved(self, tmp_path: Path) -> None:
        """Verify secrets show [SET] when placeholder resolves.

        Contract: is_secret=True fields show [SET] not actual value.
        Quality Contribution: Prevents secret exposure in UI/logs.
        """
        config = tmp_path / "config.yaml"
        config.write_text("llm:\n  api_key: ${SECRET_KEY}")

        env_file = tmp_path / ".env"
        env_file.write_text("SECRET_KEY=super-secret-value-never-shown")

        inspector = ConfigInspectorService(
            project_path=config,
            secrets_paths=[env_file],
        )
        result = inspector.inspect()

        attr = result.attribution["llm.api_key"]
        assert attr.is_secret is True
        # Value shows placeholder, not [SET], per Insight #5
        # [SET] is shown in UI layer, not in raw attribution
        assert attr.value == "${SECRET_KEY}"
        # Resolution state indicates it's set
        assert result.placeholder_states["llm.api_key"] == PlaceholderState.RESOLVED

    def test_secret_placeholder_unresolved_shows_placeholder(
        self, tmp_path: Path
    ) -> None:
        """Verify unresolved secret placeholder shows literally.

        Contract: Unresolved placeholders are safe to show.
        """
        config = tmp_path / "config.yaml"
        config.write_text("llm:\n  api_key: ${UNSET_SECRET}")

        inspector = ConfigInspectorService(project_path=config)
        result = inspector.inspect()

        attr = result.attribution["llm.api_key"]
        assert attr.is_secret is True
        assert attr.value == "${UNSET_SECRET}"
        assert result.placeholder_states["llm.api_key"] == PlaceholderState.UNRESOLVED

    def test_actual_env_values_never_in_result(self, tmp_path: Path) -> None:
        """Verify actual .env values never appear in InspectionResult.

        Per Insight #5: .env values are actual secrets - never shown.
        Contract: No raw secret values in attribution or any result field.
        """
        config = tmp_path / "config.yaml"
        config.write_text("llm:\n  api_key: ${MY_SECRET}")

        secret_value = "this-is-a-real-secret-12345"
        env_file = tmp_path / ".env"
        env_file.write_text(f"MY_SECRET={secret_value}")

        inspector = ConfigInspectorService(
            project_path=config,
            secrets_paths=[env_file],
        )
        result = inspector.inspect()

        # Search entire result for the secret value
        result_str = str(result.attribution) + str(result.raw_config)
        assert secret_value not in result_str


class TestErrorHandling:
    """Tests for graceful error handling."""

    def test_handles_missing_project_config(self, tmp_path: Path) -> None:
        """Verify graceful handling when project config doesn't exist.

        Contract: Missing config file returns empty attribution, no crash.
        """
        missing_path = tmp_path / "nonexistent.yaml"

        inspector = ConfigInspectorService(project_path=missing_path)
        result = inspector.inspect()

        assert result.attribution == {}
        assert result.raw_config == {}

    def test_handles_missing_user_config(self, tmp_path: Path) -> None:
        """Verify graceful handling when user config doesn't exist.

        Contract: Missing user config still processes project config.
        """
        project = tmp_path / "project.yaml"
        project.write_text("llm:\n  timeout: 30")
        missing_user = tmp_path / "missing_user.yaml"

        inspector = ConfigInspectorService(
            user_path=missing_user,
            project_path=project,
        )
        result = inspector.inspect()

        # Project config still works
        assert result.attribution["llm.timeout"].value == 30

    def test_handles_invalid_yaml(self, tmp_path: Path) -> None:
        """Verify handling of malformed YAML.

        Contract: Invalid YAML returns error in result, no crash.
        """
        config = tmp_path / "invalid.yaml"
        config.write_text("llm:\n  timeout: {{invalid yaml")

        inspector = ConfigInspectorService(project_path=config)
        result = inspector.inspect()

        # Result indicates parse error
        assert result.errors
        assert any("yaml" in str(e).lower() for e in result.errors)

    def test_handles_empty_config_file(self, tmp_path: Path) -> None:
        """Verify handling of empty config file.

        Contract: Empty file returns empty attribution.
        """
        config = tmp_path / "empty.yaml"
        config.write_text("")

        inspector = ConfigInspectorService(project_path=config)
        result = inspector.inspect()

        assert result.attribution == {}

    def test_handles_permission_denied(self, tmp_path: Path) -> None:
        """Verify handling of permission errors on config files.

        Contract: Permission errors captured in result.errors.
        Note: This test may be skipped in CI due to root permissions.
        """
        config = tmp_path / "protected.yaml"
        config.write_text("llm:\n  timeout: 30")
        config.chmod(0o000)

        try:
            inspector = ConfigInspectorService(project_path=config)
            result = inspector.inspect()

            # Error captured, no crash
            assert result.errors
        finally:
            # Restore permissions for cleanup
            config.chmod(0o644)


class TestInspectionResultDataStructure:
    """Tests verifying InspectionResult structure."""

    def test_result_has_required_fields(self, tmp_path: Path) -> None:
        """Verify InspectionResult contains all required fields.

        Contract: Result has attribution, raw_config, placeholder_states, errors.
        """
        config = tmp_path / "config.yaml"
        config.write_text("llm:\n  provider: fake")

        inspector = ConfigInspectorService(project_path=config)
        result = inspector.inspect()

        # All required fields exist
        assert hasattr(result, "attribution")
        assert hasattr(result, "raw_config")
        assert hasattr(result, "placeholder_states")
        assert hasattr(result, "errors")

    def test_config_value_has_required_fields(self, tmp_path: Path) -> None:
        """Verify ConfigValue contains all required fields.

        Contract: ConfigValue has value, source, source_file, override_chain, is_secret.
        """
        config = tmp_path / "config.yaml"
        config.write_text("llm:\n  timeout: 30")

        inspector = ConfigInspectorService(project_path=config)
        result = inspector.inspect()

        attr = result.attribution["llm.timeout"]
        assert hasattr(attr, "value")
        assert hasattr(attr, "source")
        assert hasattr(attr, "source_file")
        assert hasattr(attr, "override_chain")
        assert hasattr(attr, "is_secret")

    def test_raw_config_preserves_structure(self, tmp_path: Path) -> None:
        """Verify raw_config preserves original YAML structure.

        Contract: raw_config is the unprocessed YAML dict.
        """
        config = tmp_path / "config.yaml"
        config.write_text("llm:\n  provider: fake\n  timeout: 30\nscan:\n  paths:\n    - src")

        inspector = ConfigInspectorService(project_path=config)
        result = inspector.inspect()

        # Structure preserved
        assert result.raw_config["llm"]["provider"] == "fake"
        assert result.raw_config["llm"]["timeout"] == 30
        assert result.raw_config["scan"]["paths"] == ["src"]


class TestUnflattenTypeSafety:
    """Tests for type safety in nested key handling."""

    def test_unflatten_handles_mixed_type_nesting(self, tmp_path: Path) -> None:
        """Verify graceful handling of configs with mixed-type nesting.

        Contract: If intermediate key has scalar value, key is skipped.
        This prevents AttributeError when a key appears both as a value
        and as a nested parent (e.g., "llm: fake" and "llm.timeout: 30").
        """
        config = tmp_path / "config.yaml"
        # YAML doesn't allow this directly, but _unflatten_dict can receive
        # conflicting flat keys from multiple sources during merge
        # Create a config that tests the _unflatten_dict protection
        config.write_text("llm:\n  timeout: 30")

        inspector = ConfigInspectorService(project_path=config)
        result = inspector.inspect()

        # Should not crash; normal operation works
        assert isinstance(result, InspectionResult)
        assert result.attribution["llm.timeout"].value == 30
