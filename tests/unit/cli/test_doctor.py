"""Tests for fs2 doctor CLI command.

Full TDD tests for the doctor command covering:
- T002: Config file discovery (all 5 locations)
- T003: Merge chain computation and override detection
- T004: Provider status detection (LLM/embedding)
- T005: Placeholder validation
- T006: Literal secret detection
- T007: Edge cases (no config, central-only, warnings)
- T022: YAML syntax validation
- T023: Pydantic schema validation
- T024: Provider-specific validation
"""

from typer.testing import CliRunner

runner = CliRunner()


# =============================================================================
# T002: CONFIG FILE DISCOVERY TESTS
# =============================================================================


class TestConfigDiscovery:
    """T002: Tests for config file discovery (all 5 locations)."""

    def test_given_all_configs_exist_when_doctor_then_shows_all_found(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies doctor detects all 5 config file locations.
        Quality Contribution: Ensures complete config visibility.
        Acceptance Criteria: AC-02 - Lists all config files found.
        """
        from fs2.cli.doctor import discover_config_files

        # Setup: Create fake home and project directories
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        user_config_dir = fake_home / ".config" / "fs2"
        user_config_dir.mkdir(parents=True)
        (user_config_dir / "config.yaml").write_text("scan:\n  scan_paths: ['.']")
        (user_config_dir / "secrets.env").write_text("API_KEY=test")

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text("scan:\n  scan_paths: ['.']")
        (fs2_dir / "secrets.env").write_text("PROJECT_KEY=test")
        (project_dir / ".env").write_text("DOT_ENV_KEY=test")

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        files = discover_config_files()

        assert files["user_config"]["exists"] is True
        assert files["user_secrets"]["exists"] is True
        assert files["project_config"]["exists"] is True
        assert files["project_secrets"]["exists"] is True
        assert files["dotenv"]["exists"] is True

    def test_given_no_configs_exist_when_doctor_then_shows_all_missing(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies doctor handles missing config files gracefully.
        Quality Contribution: Ensures clear feedback when no configs exist.
        Acceptance Criteria: AC-02 - Shows not found status.
        """
        from fs2.cli.doctor import discover_config_files

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        files = discover_config_files()

        assert files["user_config"]["exists"] is False
        assert files["user_secrets"]["exists"] is False
        assert files["project_config"]["exists"] is False
        assert files["project_secrets"]["exists"] is False
        assert files["dotenv"]["exists"] is False

    def test_given_xdg_config_home_set_when_doctor_then_uses_xdg_path(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies doctor respects XDG_CONFIG_HOME.
        Quality Contribution: Ensures XDG compliance.
        Acceptance Criteria: AC-02 - Uses XDG path when set.
        """
        from fs2.cli.doctor import discover_config_files

        xdg_config = tmp_path / "xdg_config"
        xdg_config.mkdir()
        fs2_config = xdg_config / "fs2"
        fs2_config.mkdir()
        (fs2_config / "config.yaml").write_text("scan:\n  scan_paths: ['.']")

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))

        files = discover_config_files()

        assert files["user_config"]["exists"] is True
        assert str(xdg_config) in files["user_config"]["path"]

    def test_given_partial_configs_when_doctor_then_shows_mixed_status(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies doctor handles partial config setups.
        Quality Contribution: Ensures accurate per-file status.
        Acceptance Criteria: AC-02 - Shows correct status per file.
        """
        from fs2.cli.doctor import discover_config_files

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        user_config_dir = fake_home / ".config" / "fs2"
        user_config_dir.mkdir(parents=True)
        (user_config_dir / "config.yaml").write_text("scan:\n  scan_paths: ['.']")
        # No secrets.env

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text("scan:\n  scan_paths: ['.']")
        # No secrets.env, no .env

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        files = discover_config_files()

        assert files["user_config"]["exists"] is True
        assert files["user_secrets"]["exists"] is False
        assert files["project_config"]["exists"] is True
        assert files["project_secrets"]["exists"] is False
        assert files["dotenv"]["exists"] is False

    def test_given_config_files_when_doctor_then_includes_paths(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies discovered files include full paths.
        Quality Contribution: Enables user to locate files.
        Acceptance Criteria: AC-02 - File paths are included.
        """
        from fs2.cli.doctor import discover_config_files

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        user_config_dir = fake_home / ".config" / "fs2"
        user_config_dir.mkdir(parents=True)
        (user_config_dir / "config.yaml").write_text("scan:\n  scan_paths: ['.']")

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        files = discover_config_files()

        assert "path" in files["user_config"]
        assert "config.yaml" in files["user_config"]["path"]


# =============================================================================
# T003: MERGE CHAIN COMPUTATION TESTS
# =============================================================================


class TestMergeChain:
    """T003: Tests for merge chain computation and override detection."""

    def test_given_multi_layer_configs_when_compute_then_returns_chain(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies merge chain is computed correctly.
        Quality Contribution: Ensures precedence visibility.
        Acceptance Criteria: AC-03 - Displays merge chain.
        """
        from fs2.cli.doctor import compute_merge_chain

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        user_config_dir = fake_home / ".config" / "fs2"
        user_config_dir.mkdir(parents=True)
        (user_config_dir / "config.yaml").write_text(
            "scan:\n  max_file_size_kb: 500\n  respect_gitignore: true"
        )

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text("scan:\n  max_file_size_kb: 1000")

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        chain = compute_merge_chain()

        assert "user_config" in chain
        assert "project_config" in chain
        assert chain["final"]["scan"]["max_file_size_kb"] == 1000
        assert chain["final"]["scan"]["respect_gitignore"] is True

    def test_given_project_overrides_user_when_compute_then_detects_override(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies override detection works.
        Quality Contribution: Warns about unintentional overrides.
        Acceptance Criteria: AC-04 - Warns when local overrides central.
        """
        from fs2.cli.doctor import detect_overrides

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        user_config_dir = fake_home / ".config" / "fs2"
        user_config_dir.mkdir(parents=True)
        (user_config_dir / "config.yaml").write_text("scan:\n  max_file_size_kb: 500")

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text("scan:\n  max_file_size_kb: 1000")

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        overrides = detect_overrides()

        assert len(overrides) >= 1
        # Find the override for max_file_size_kb
        override_found = any("max_file_size_kb" in o["path"] for o in overrides)
        assert override_found

    def test_given_no_overrides_when_compute_then_returns_empty(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies no false override warnings.
        Quality Contribution: Avoids noise when configs are independent.
        Acceptance Criteria: AC-04 - No warning when no overrides.
        """
        from fs2.cli.doctor import detect_overrides

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        user_config_dir = fake_home / ".config" / "fs2"
        user_config_dir.mkdir(parents=True)
        (user_config_dir / "config.yaml").write_text("scan:\n  max_file_size_kb: 500")

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        # Different keys - no override
        (fs2_dir / "config.yaml").write_text("scan:\n  follow_symlinks: true")

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        overrides = detect_overrides()

        # No overrides for existing keys
        max_file_size_overrides = [
            o for o in overrides if "max_file_size_kb" in o.get("path", "")
        ]
        assert len(max_file_size_overrides) == 0

    def test_given_nested_override_when_compute_then_includes_full_path(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies nested overrides include full path.
        Quality Contribution: Clear identification of override location.
        Acceptance Criteria: AC-04 - Override path is complete.
        """
        from fs2.cli.doctor import detect_overrides

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        user_config_dir = fake_home / ".config" / "fs2"
        user_config_dir.mkdir(parents=True)
        (user_config_dir / "config.yaml").write_text(
            "embedding:\n  azure:\n    deployment_name: prod-model"
        )

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text(
            "embedding:\n  azure:\n    deployment_name: dev-model"
        )

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        overrides = detect_overrides()

        deployment_override = next(
            (o for o in overrides if "deployment_name" in o.get("path", "")), None
        )
        assert deployment_override is not None
        assert "embedding" in deployment_override["path"]
        assert "azure" in deployment_override["path"]


# =============================================================================
# T004: PROVIDER STATUS DETECTION TESTS
# =============================================================================


class TestProviderStatus:
    """T004: Tests for provider status detection (LLM/embedding)."""

    def test_given_llm_configured_when_check_then_shows_configured(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies LLM detection when fully configured.
        Quality Contribution: Confirms LLM is ready to use.
        Acceptance Criteria: AC-05 - Shows LLM status.
        """
        from fs2.cli.doctor import check_provider_status

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text(
            """llm:
  provider: azure
  api_key: ${AZURE_OPENAI_API_KEY}
  base_url: https://test.openai.azure.com/
  azure_deployment_name: gpt-4
  azure_api_version: 2024-02-01
"""
        )

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")

        status = check_provider_status()

        assert status["llm"]["configured"] is True
        assert status["llm"]["provider"] == "azure"

    def test_given_llm_not_configured_when_check_then_shows_not_configured(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies LLM detection when not configured.
        Quality Contribution: Guides user to configure LLM.
        Acceptance Criteria: AC-05, AC-07 - Shows not configured with docs link.
        """
        from fs2.cli.doctor import check_provider_status

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text("scan:\n  scan_paths: ['.']")

        monkeypatch.chdir(project_dir)

        status = check_provider_status()

        assert status["llm"]["configured"] is False
        assert "docs_url" in status["llm"]

    def test_given_embedding_configured_when_check_then_shows_configured(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies embedding detection when fully configured.
        Quality Contribution: Confirms embeddings are ready.
        Acceptance Criteria: AC-06 - Shows embedding status.
        """
        from fs2.cli.doctor import check_provider_status

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text(
            """embedding:
  mode: azure
  azure:
    endpoint: https://test.openai.azure.com
    api_key: ${AZURE_EMBEDDING_API_KEY}
    deployment_name: text-embedding-3-small
"""
        )

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("AZURE_EMBEDDING_API_KEY", "test-key")

        status = check_provider_status()

        assert status["embedding"]["configured"] is True
        assert status["embedding"]["mode"] == "azure"

    def test_given_embedding_not_configured_when_check_then_shows_docs_link(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies embedding docs link when not configured.
        Quality Contribution: Guides user to configure embeddings.
        Acceptance Criteria: AC-07 - Shows clickable GitHub URL.
        """
        from fs2.cli.doctor import check_provider_status

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text("scan:\n  scan_paths: ['.']")

        monkeypatch.chdir(project_dir)

        status = check_provider_status()

        assert status["embedding"]["configured"] is False
        assert "github.com" in status["embedding"]["docs_url"]
        assert "configuration" in status["embedding"]["docs_url"].lower()


# =============================================================================
# T005: PLACEHOLDER VALIDATION TESTS
# =============================================================================


class TestPlaceholderValidation:
    """T005: Tests for placeholder validation."""

    def test_given_resolved_placeholder_when_validate_then_shows_resolved(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies resolved placeholders are marked correctly.
        Quality Contribution: Confirms env vars are set.
        Acceptance Criteria: AC-08 - Shows resolved status.
        """
        from fs2.cli.doctor import validate_placeholders

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text(
            "llm:\n  api_key: ${MY_API_KEY}\n  base_url: ${MY_ENDPOINT}"
        )

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("MY_API_KEY", "secret-key")
        monkeypatch.setenv("MY_ENDPOINT", "https://example.com")

        placeholders = validate_placeholders()

        my_api_key = next((p for p in placeholders if p["name"] == "MY_API_KEY"), None)
        my_endpoint = next(
            (p for p in placeholders if p["name"] == "MY_ENDPOINT"), None
        )

        assert my_api_key is not None
        assert my_api_key["resolved"] is True
        assert my_endpoint is not None
        assert my_endpoint["resolved"] is True

    def test_given_unresolved_placeholder_when_validate_then_shows_unresolved(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies unresolved placeholders are marked correctly.
        Quality Contribution: Warns about missing env vars.
        Acceptance Criteria: AC-08 - Shows unresolved status.
        """
        from fs2.cli.doctor import validate_placeholders

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text("llm:\n  api_key: ${MISSING_API_KEY}")

        monkeypatch.chdir(project_dir)
        monkeypatch.delenv("MISSING_API_KEY", raising=False)

        placeholders = validate_placeholders()

        missing = next(
            (p for p in placeholders if p["name"] == "MISSING_API_KEY"), None
        )

        assert missing is not None
        assert missing["resolved"] is False

    def test_given_no_placeholders_when_validate_then_returns_empty(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies no placeholders returns empty list.
        Quality Contribution: Clean output when no placeholders.
        Acceptance Criteria: AC-08 - Empty list when none found.
        """
        from fs2.cli.doctor import validate_placeholders

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text("scan:\n  scan_paths: ['.']")

        monkeypatch.chdir(project_dir)

        placeholders = validate_placeholders()

        assert placeholders == []


# =============================================================================
# T006: LITERAL SECRET DETECTION TESTS
# =============================================================================


class TestSecretDetection:
    """T006: Tests for literal secret detection."""

    def test_given_sk_prefix_in_config_when_check_then_warns(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies sk-* prefix detection.
        Quality Contribution: Prevents committing OpenAI keys.
        Acceptance Criteria: AC-13 - Warns about sk-* prefix.
        """
        from fs2.cli.doctor import detect_literal_secrets_in_config as detect_literal_secrets

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text(
            "llm:\n  api_key: sk-1234567890abcdefghijklmnopqrstuvwxyz"
        )

        monkeypatch.chdir(project_dir)

        secrets = detect_literal_secrets()

        assert len(secrets) >= 1
        sk_secret = next((s for s in secrets if "sk-" in s.get("pattern", "")), None)
        assert sk_secret is not None
        # Should NOT include actual value
        assert "1234567890" not in str(sk_secret)

    def test_given_long_string_in_secret_field_when_check_then_warns(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies >64 char string detection.
        Quality Contribution: Catches long literal secrets.
        Acceptance Criteria: AC-13 - Warns about >64 char strings.
        """
        from fs2.cli.doctor import detect_literal_secrets_in_config as detect_literal_secrets

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        long_secret = "a" * 100  # 100 characters
        (fs2_dir / "config.yaml").write_text(f"llm:\n  api_key: {long_secret}")

        monkeypatch.chdir(project_dir)

        secrets = detect_literal_secrets()

        # Should detect long literal
        assert len(secrets) >= 1

    def test_given_placeholder_when_check_then_no_warning(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies placeholders don't trigger false warnings.
        Quality Contribution: No noise for properly configured secrets.
        Acceptance Criteria: AC-13 - No warning for placeholders.
        """
        from fs2.cli.doctor import detect_literal_secrets_in_config as detect_literal_secrets

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text("llm:\n  api_key: ${AZURE_OPENAI_API_KEY}")

        monkeypatch.chdir(project_dir)

        secrets = detect_literal_secrets()

        # Should not detect placeholder as secret
        assert len(secrets) == 0


# =============================================================================
# T007: EDGE CASES TESTS
# =============================================================================


class TestEdgeCases:
    """T007: Tests for edge cases (no config, central-only, warnings)."""

    def test_given_no_configs_when_doctor_then_suggests_init(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies init suggestion when no configs exist.
        Quality Contribution: Guides new users.
        Acceptance Criteria: AC-09 - Suggests fs2 init.
        """
        from fs2.cli.doctor import get_suggestions

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        suggestions = get_suggestions()

        init_suggestion = next((s for s in suggestions if "init" in s.lower()), None)
        assert init_suggestion is not None

    def test_given_central_only_when_doctor_then_warns_no_local(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies warning when central exists but no local.
        Quality Contribution: Warns about potential wrong directory.
        Acceptance Criteria: AC-10 - Warns when no local .fs2/.
        """
        from fs2.cli.doctor import get_warnings

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        user_config_dir = fake_home / ".config" / "fs2"
        user_config_dir.mkdir(parents=True)
        (user_config_dir / "config.yaml").write_text("scan:\n  scan_paths: ['.']")

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        # No .fs2/ directory

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        warnings = get_warnings()

        local_warning = next(
            (w for w in warnings if ".fs2" in w.lower() or "local" in w.lower()), None
        )
        assert local_warning is not None

    def test_given_healthy_config_when_doctor_then_exit_0(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies exit code 0 when healthy.
        Quality Contribution: Clear success signal.
        Acceptance Criteria: AC-12 - Exit 0 when healthy.
        """
        from fs2.cli.main import app

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text("scan:\n  scan_paths: ['.']")

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 0

    def test_given_issues_when_doctor_then_exit_1(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies exit code 1 when issues found.
        Quality Contribution: Clear failure signal for CI.
        Acceptance Criteria: AC-12 - Exit 1 when issues.
        """
        from fs2.cli.main import app

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        # Invalid config with literal secret
        (fs2_dir / "config.yaml").write_text(
            "llm:\n  api_key: sk-invalid-key-that-should-not-be-here"
        )

        monkeypatch.chdir(project_dir)
        monkeypatch.setenv("NO_COLOR", "1")

        result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 1


# =============================================================================
# T022: YAML SYNTAX VALIDATION TESTS
# =============================================================================


class TestYAMLValidation:
    """T022: Tests for YAML syntax validation."""

    def test_given_malformed_yaml_when_doctor_then_shows_error(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies YAML syntax errors are caught.
        Quality Contribution: Clear error for invalid YAML.
        Acceptance Criteria: AC-32 - Catches syntax errors.
        """
        from fs2.cli.doctor import validate_configs

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        # Invalid YAML (tab instead of spaces)
        (fs2_dir / "config.yaml").write_text("scan:\n\tscan_paths: ['.']")

        monkeypatch.chdir(project_dir)

        errors = validate_configs()

        yaml_error = next((e for e in errors if e["type"] == "yaml_syntax"), None)
        assert yaml_error is not None

    def test_given_yaml_error_when_doctor_then_shows_line_number(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies line number in YAML error.
        Quality Contribution: Helps locate error quickly.
        Acceptance Criteria: AC-33 - Shows line number.
        """
        from fs2.cli.doctor import validate_configs

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        # Invalid YAML on line 3
        (fs2_dir / "config.yaml").write_text(
            "scan:\n  scan_paths:\n    - bad: yaml: here"
        )

        monkeypatch.chdir(project_dir)

        errors = validate_configs()

        yaml_error = next((e for e in errors if e["type"] == "yaml_syntax"), None)
        assert yaml_error is not None
        assert "line" in yaml_error or "line_number" in yaml_error

    def test_given_encoding_issue_when_doctor_then_shows_error(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies encoding issues are handled.
        Quality Contribution: Clear error for encoding problems.
        Acceptance Criteria: AC-32, AC-33 - Handles encoding.
        """
        from fs2.cli.doctor import validate_configs

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        # Write binary garbage
        (fs2_dir / "config.yaml").write_bytes(b"\xff\xfe\x00\x00scan:\n")

        monkeypatch.chdir(project_dir)

        errors = validate_configs()

        # Should have some error
        assert len(errors) >= 1

    def test_given_valid_yaml_when_doctor_then_no_syntax_error(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies valid YAML passes.
        Quality Contribution: No false positives.
        Acceptance Criteria: AC-32 - No error for valid YAML.
        """
        from fs2.cli.doctor import validate_configs

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text("scan:\n  scan_paths:\n    - '.'")

        monkeypatch.chdir(project_dir)

        errors = validate_configs()

        yaml_errors = [e for e in errors if e["type"] == "yaml_syntax"]
        assert len(yaml_errors) == 0


# =============================================================================
# T023: PYDANTIC SCHEMA VALIDATION TESTS
# =============================================================================


class TestPydanticValidation:
    """T023: Tests for pydantic schema validation."""

    def test_given_wrong_type_when_doctor_then_shows_error(self, tmp_path, monkeypatch):
        """
        Purpose: Verifies type errors are caught.
        Quality Contribution: Clear error for type mismatches.
        Acceptance Criteria: AC-34 - Shows field path and expected type.
        """
        from fs2.cli.doctor import validate_configs

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        # max_file_size_kb should be int, not string
        (fs2_dir / "config.yaml").write_text("scan:\n  max_file_size_kb: not_a_number")

        monkeypatch.chdir(project_dir)

        errors = validate_configs()

        schema_error = next(
            (e for e in errors if e["type"] == "schema_validation"), None
        )
        assert schema_error is not None
        assert "max_file_size_kb" in schema_error.get("field", "")

    def test_given_invalid_value_when_doctor_then_shows_field_path(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies field path in schema error.
        Quality Contribution: Helps locate invalid field.
        Acceptance Criteria: AC-34 - Shows full field path.
        """
        from fs2.cli.doctor import validate_configs

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        # timeout should be 1-120
        (fs2_dir / "config.yaml").write_text("llm:\n  provider: azure\n  timeout: 500")

        monkeypatch.chdir(project_dir)

        errors = validate_configs()

        schema_error = next(
            (e for e in errors if e["type"] == "schema_validation"), None
        )
        assert schema_error is not None
        assert "timeout" in schema_error.get(
            "field", ""
        ) or "timeout" in schema_error.get("message", "")

    def test_given_nested_invalid_value_when_doctor_then_shows_full_path(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies nested field path in error.
        Quality Contribution: Clear path for nested config.
        Acceptance Criteria: AC-34 - Shows nested path.
        """
        from fs2.cli.doctor import validate_configs

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        # dimensions should be positive
        (fs2_dir / "config.yaml").write_text(
            "embedding:\n  mode: azure\n  dimensions: -1"
        )

        monkeypatch.chdir(project_dir)

        errors = validate_configs()

        schema_error = next(
            (e for e in errors if e["type"] == "schema_validation"), None
        )
        assert schema_error is not None

    def test_given_valid_schema_when_doctor_then_no_schema_error(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies valid schema passes.
        Quality Contribution: No false positives.
        Acceptance Criteria: AC-34 - No error for valid schema.
        """
        from fs2.cli.doctor import validate_configs

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text("scan:\n  max_file_size_kb: 1000")

        monkeypatch.chdir(project_dir)

        errors = validate_configs()

        schema_errors = [e for e in errors if e["type"] == "schema_validation"]
        assert len(schema_errors) == 0


# =============================================================================
# T024: PROVIDER-SPECIFIC VALIDATION TESTS
# =============================================================================


class TestProviderValidation:
    """T024: Tests for provider-specific validation."""

    def test_given_azure_missing_endpoint_when_doctor_then_shows_error(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies Azure endpoint requirement.
        Quality Contribution: Catches missing Azure config.
        Acceptance Criteria: AC-35 - Azure needs endpoint.
        """
        from fs2.cli.doctor import validate_provider_requirements

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        # Azure without endpoint
        (fs2_dir / "config.yaml").write_text(
            """llm:
  provider: azure
  api_key: ${AZURE_OPENAI_API_KEY}
  azure_deployment_name: gpt-4
  azure_api_version: 2024-02-01
"""
        )

        monkeypatch.chdir(project_dir)

        errors = validate_provider_requirements()

        endpoint_error = next(
            (
                e
                for e in errors
                if "base_url" in e.get("field", "")
                or "endpoint" in e.get("message", "").lower()
            ),
            None,
        )
        assert endpoint_error is not None

    def test_given_azure_missing_deployment_when_doctor_then_shows_error(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies Azure deployment name requirement.
        Quality Contribution: Catches missing Azure config.
        Acceptance Criteria: AC-35 - Azure needs deployment name.
        """
        from fs2.cli.doctor import validate_provider_requirements

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        # Azure without deployment_name
        (fs2_dir / "config.yaml").write_text(
            """llm:
  provider: azure
  api_key: ${AZURE_OPENAI_API_KEY}
  base_url: https://test.openai.azure.com/
  azure_api_version: 2024-02-01
"""
        )

        monkeypatch.chdir(project_dir)

        errors = validate_provider_requirements()

        deployment_error = next(
            (
                e
                for e in errors
                if "deployment" in e.get("field", "").lower()
                or "deployment" in e.get("message", "").lower()
            ),
            None,
        )
        assert deployment_error is not None

    def test_given_embedding_azure_missing_endpoint_when_doctor_then_shows_error(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies Azure embedding endpoint requirement.
        Quality Contribution: Catches missing embedding config.
        Acceptance Criteria: AC-36 - Embedding Azure needs endpoint.
        """
        from fs2.cli.doctor import validate_provider_requirements

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        # Azure embedding without endpoint
        (fs2_dir / "config.yaml").write_text(
            """embedding:
  mode: azure
  azure:
    api_key: ${AZURE_EMBEDDING_API_KEY}
"""
        )

        monkeypatch.chdir(project_dir)

        errors = validate_provider_requirements()

        endpoint_error = next(
            (
                e
                for e in errors
                if "endpoint" in e.get("field", "").lower()
                or "endpoint" in e.get("message", "").lower()
            ),
            None,
        )
        assert endpoint_error is not None

    def test_given_misconfigured_provider_when_doctor_then_shows_misconfigured(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies distinction between not configured and misconfigured.
        Quality Contribution: Clear status message.
        Acceptance Criteria: AC-38 - Distinguishes not configured vs misconfigured.
        """
        from fs2.cli.doctor import check_provider_status

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        # Azure missing required fields
        (fs2_dir / "config.yaml").write_text(
            """llm:
  provider: azure
  api_key: ${AZURE_OPENAI_API_KEY}
"""
        )

        monkeypatch.chdir(project_dir)

        status = check_provider_status()

        assert status["llm"]["configured"] is False
        assert status["llm"].get("misconfigured") is True or "missing" in str(
            status["llm"].get("issues", [])
        )

    def test_given_provider_error_when_doctor_then_shows_docs_link(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies docs link in validation error.
        Quality Contribution: Actionable guidance.
        Acceptance Criteria: AC-37 - Includes docs link.
        """
        from fs2.cli.doctor import validate_provider_requirements

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        # Incomplete Azure config
        (fs2_dir / "config.yaml").write_text(
            """llm:
  provider: azure
  api_key: ${AZURE_OPENAI_API_KEY}
"""
        )

        monkeypatch.chdir(project_dir)

        errors = validate_provider_requirements()

        assert len(errors) >= 1
        # Should have docs link in at least one error
        has_docs_link = any(
            "docs_url" in e or "github" in str(e).lower() for e in errors
        )
        assert has_docs_link

    def test_given_complete_azure_config_when_doctor_then_no_provider_error(
        self, tmp_path, monkeypatch
    ):
        """
        Purpose: Verifies complete Azure config passes.
        Quality Contribution: No false positives.
        Acceptance Criteria: AC-35 - No error when complete.
        """
        from fs2.cli.doctor import validate_provider_requirements

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        fs2_dir = project_dir / ".fs2"
        fs2_dir.mkdir()
        (fs2_dir / "config.yaml").write_text(
            """llm:
  provider: azure
  api_key: ${AZURE_OPENAI_API_KEY}
  base_url: https://test.openai.azure.com/
  azure_deployment_name: gpt-4
  azure_api_version: 2024-02-01
"""
        )

        monkeypatch.chdir(project_dir)

        errors = validate_provider_requirements()

        llm_errors = [e for e in errors if "llm" in e.get("field", "").lower()]
        assert len(llm_errors) == 0
