"""Tests for SmartContentConfig.

T001: SmartContentConfig contract tests.
Purpose: Verify SmartContentConfig defaults, validation, and YAML/env binding.
"""

import pytest
from pydantic import ValidationError


@pytest.mark.unit
class TestSmartContentConfigDefaults:
    """T001: Tests for SmartContentConfig default values."""

    def test_given_no_args_when_constructed_then_has_spec_defaults(self):
        """
        Purpose: Proves SmartContentConfig has sensible defaults per spec.
        Quality Contribution: Prevents missing config causing runtime crashes.
        Acceptance Criteria: Defaults match documented values.

        Task: T001
        """
        from fs2.config.objects import SmartContentConfig

        config = SmartContentConfig()

        assert config.max_workers == 50
        assert config.max_input_tokens == 50000

        assert config.token_limits["file"] == 200
        assert config.token_limits["type"] == 200
        assert config.token_limits["callable"] == 150
        assert config.token_limits["section"] == 150
        assert config.token_limits["block"] == 150
        assert config.token_limits["definition"] == 150
        assert config.token_limits["statement"] == 100
        assert config.token_limits["expression"] == 100
        assert config.token_limits["other"] == 100


@pytest.mark.unit
class TestSmartContentConfigPath:
    """T001: Tests for SmartContentConfig __config_path__ key binding."""

    def test_given_config_when_checking_path_then_returns_smart_content(self):
        """
        Purpose: Proves YAML key binding matches docs/examples (`smart_content:`).
        Quality Contribution: Prevents silent config misbinding in production.
        Acceptance Criteria: __config_path__ is "smart_content".

        Task: T001
        """
        from fs2.config.objects import SmartContentConfig

        assert SmartContentConfig.__config_path__ == "smart_content"


@pytest.mark.unit
class TestSmartContentConfigValidation:
    """T001: Tests for SmartContentConfig validation rules."""

    def test_given_invalid_max_workers_when_constructed_then_validation_error(self):
        """
        Purpose: Proves max_workers lower bound is enforced.
        Quality Contribution: Prevents invalid concurrency config.
        Acceptance Criteria: max_workers < 1 raises ValidationError.

        Task: T001
        """
        from fs2.config.objects import SmartContentConfig

        with pytest.raises(ValidationError):
            SmartContentConfig(max_workers=0)

        with pytest.raises(ValidationError):
            SmartContentConfig(max_workers=-1)


@pytest.mark.unit
class TestSmartContentConfigLoading:
    """T001: Tests for SmartContentConfig YAML/env loading."""

    def test_given_yaml_when_loaded_then_uses_yaml_values(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: Proves ConfigurationService binds SmartContentConfig from YAML.
        Quality Contribution: Prevents config being ignored.
        Acceptance Criteria: YAML values are reflected in required config.

        Task: T001
        """
        from fs2.config.objects import SmartContentConfig
        from fs2.config.service import FS2ConfigurationService

        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            """smart_content:
  max_workers: 10
  max_input_tokens: 1234
scan:
  scan_paths:
    - "."
"""
        )

        monkeypatch.chdir(tmp_path)

        service = FS2ConfigurationService()
        config = service.require(SmartContentConfig)

        assert config.max_workers == 10
        assert config.max_input_tokens == 1234

    def test_given_env_var_when_loaded_then_env_overrides_yaml(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: Proves env var precedence over YAML for SmartContentConfig.
        Quality Contribution: Ensures consistent precedence rules across configs.
        Acceptance Criteria: Env overrides YAML values.

        Task: T001
        """
        from fs2.config.objects import SmartContentConfig
        from fs2.config.service import FS2ConfigurationService

        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            """smart_content:
  max_workers: 10
scan:
  scan_paths:
    - "."
"""
        )

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("FS2_SMART_CONTENT__MAX_WORKERS", "25")

        service = FS2ConfigurationService()
        config = service.require(SmartContentConfig)

        assert config.max_workers == 25
