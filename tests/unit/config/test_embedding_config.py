"""Tests for ChunkConfig and EmbeddingConfig.

Phase 1: Core Infrastructure - Embedding configuration tests.
Purpose: Verify ChunkConfig and EmbeddingConfig validation and defaults.

Per Plan 1.1: Content-type aware configuration pattern.
Per DYK-3: overlap_tokens >= 0 (0 is valid for smart_content).
Per DYK-4: Retry configuration (max_retries, base_delay, max_delay).
"""

import pytest
from pydantic import ValidationError


@pytest.mark.unit
class TestChunkConfigDefaults:
    """T002: Tests for ChunkConfig default values."""

    def test_given_valid_args_when_constructed_then_stores_values(self):
        """
        Purpose: Proves ChunkConfig stores max_tokens and overlap_tokens.
        Quality Contribution: Ensures basic construction works.
        Acceptance Criteria: Values are stored correctly.

        Task: T002
        """
        from fs2.config.objects import ChunkConfig

        # Arrange / Act
        config = ChunkConfig(max_tokens=400, overlap_tokens=50)

        # Assert
        assert config.max_tokens == 400
        assert config.overlap_tokens == 50


@pytest.mark.unit
class TestChunkConfigValidation:
    """T002: Tests for ChunkConfig validation rules."""

    def test_given_max_tokens_zero_when_constructed_then_validation_error(self):
        """
        Purpose: Proves max_tokens must be positive.
        Quality Contribution: Prevents invalid chunk sizes.
        Acceptance Criteria: max_tokens=0 raises ValidationError.

        Task: T002
        """
        from fs2.config.objects import ChunkConfig

        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="max_tokens"):
            ChunkConfig(max_tokens=0, overlap_tokens=10)

    def test_given_max_tokens_negative_when_constructed_then_validation_error(self):
        """
        Purpose: Proves max_tokens must be positive.
        Quality Contribution: Prevents invalid chunk sizes.
        Acceptance Criteria: max_tokens=-1 raises ValidationError.

        Task: T002
        """
        from fs2.config.objects import ChunkConfig

        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="max_tokens"):
            ChunkConfig(max_tokens=-1, overlap_tokens=10)

    def test_given_overlap_exceeds_max_when_constructed_then_validation_error(self):
        """
        Purpose: Proves overlap_tokens must be less than max_tokens.
        Quality Contribution: Prevents invalid overlap configurations.
        Acceptance Criteria: overlap >= max raises ValidationError.

        Task: T002
        """
        from fs2.config.objects import ChunkConfig

        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="overlap"):
            ChunkConfig(max_tokens=100, overlap_tokens=100)

        with pytest.raises(ValidationError, match="overlap"):
            ChunkConfig(max_tokens=100, overlap_tokens=150)

    def test_given_overlap_zero_when_constructed_then_succeeds(self):
        """
        Purpose: Per DYK-3: Proves overlap_tokens=0 is valid for smart_content.
        Quality Contribution: Documents that 0 is intentionally allowed.
        Acceptance Criteria: ChunkConfig(max_tokens=8000, overlap_tokens=0) succeeds.

        Task: T002
        """
        from fs2.config.objects import ChunkConfig

        # Arrange / Act
        config = ChunkConfig(max_tokens=8000, overlap_tokens=0)

        # Assert
        assert config.max_tokens == 8000
        assert config.overlap_tokens == 0

    def test_given_overlap_negative_when_constructed_then_validation_error(self):
        """
        Purpose: Per DYK-3: Proves overlap_tokens must be >= 0.
        Quality Contribution: Prevents invalid negative overlap.
        Acceptance Criteria: overlap_tokens=-1 raises ValidationError.

        Task: T002
        """
        from fs2.config.objects import ChunkConfig

        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="overlap"):
            ChunkConfig(max_tokens=100, overlap_tokens=-1)


@pytest.mark.unit
class TestEmbeddingConfigDefaults:
    """T003: Tests for EmbeddingConfig default values."""

    def test_given_no_args_when_constructed_then_has_mode_azure(self):
        """
        Purpose: Proves default mode is azure.
        Quality Contribution: Ensures sensible default for most users.
        Acceptance Criteria: mode == "azure".

        Task: T003
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act
        config = EmbeddingConfig()

        # Assert
        assert config.mode == "azure"

    def test_given_no_args_when_constructed_then_has_dimensions_1024(self):
        """
        Purpose: Per Alignment Finding 10: Proves default dimensions is 1024.
        Quality Contribution: Ensures consistent embedding vector size across providers.
        Acceptance Criteria: dimensions == 1024.

        Task: T003 (V6 fix)
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act
        config = EmbeddingConfig()

        # Assert
        assert config.dimensions == 1024

    def test_given_no_args_when_constructed_then_has_batch_size_16(self):
        """
        Purpose: Proves default batch_size follows FlowSpace pattern (API-level batching).
        Quality Contribution: Ensures reasonable batch size for API efficiency.
        Acceptance Criteria: batch_size == 16.

        Task: T003
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act
        config = EmbeddingConfig()

        # Assert
        assert config.batch_size == 16

    def test_given_no_args_when_constructed_then_has_max_concurrent_batches_1(self):
        """
        Purpose: Proves default max_concurrent_batches is sequential (safe default).
        Quality Contribution: Avoids rate limiting with conservative default.
        Acceptance Criteria: max_concurrent_batches == 1.

        Task: T003
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act
        config = EmbeddingConfig()

        # Assert
        assert config.max_concurrent_batches == 1

    def test_given_no_args_when_constructed_then_has_code_chunk_defaults(self):
        """
        Purpose: Per Finding 04: Proves code chunk defaults (400/50).
        Quality Contribution: Ensures optimal chunking for code.
        Acceptance Criteria: code.max_tokens=400, code.overlap_tokens=50.

        Task: T003
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act
        config = EmbeddingConfig()

        # Assert
        assert config.code.max_tokens == 4000
        assert config.code.overlap_tokens == 50

    def test_given_no_args_when_constructed_then_has_documentation_chunk_defaults(self):
        """
        Purpose: Per Finding 04: Proves documentation chunk defaults (4000/120).
        Quality Contribution: Ensures optimal chunking for docs.
        Acceptance Criteria: documentation.max_tokens=4000, documentation.overlap_tokens=120.

        Task: T003
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act
        config = EmbeddingConfig()

        # Assert
        assert config.documentation.max_tokens == 4000
        assert config.documentation.overlap_tokens == 120

    def test_given_no_args_when_constructed_then_has_smart_content_chunk_defaults(self):
        """
        Purpose: Per Finding 04: Proves smart_content chunk defaults (8000/0).
        Quality Contribution: Ensures optimal chunking for smart content.
        Acceptance Criteria: smart_content.max_tokens=8000, smart_content.overlap_tokens=0.

        Task: T003
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act
        config = EmbeddingConfig()

        # Assert
        assert config.smart_content.max_tokens == 8000
        assert config.smart_content.overlap_tokens == 0


@pytest.mark.unit
class TestEmbeddingConfigRetry:
    """T003: Tests for EmbeddingConfig retry configuration per DYK-4."""

    def test_given_no_args_when_constructed_then_has_retry_defaults(self):
        """
        Purpose: Per DYK-4: Proves retry config matches Flowspace pattern.
        Quality Contribution: Ensures sensible retry behavior.
        Acceptance Criteria: max_retries=3, base_delay=2.0, max_delay=60.0.

        Task: T003
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act
        config = EmbeddingConfig()

        # Assert
        assert config.max_retries == 3
        assert config.base_delay == 2.0
        assert config.max_delay == 60.0

    def test_given_negative_max_retries_when_constructed_then_validation_error(self):
        """
        Purpose: Proves max_retries must be >= 0.
        Quality Contribution: Prevents invalid retry config.
        Acceptance Criteria: max_retries=-1 raises ValidationError.

        Task: T003
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="max_retries"):
            EmbeddingConfig(max_retries=-1)

    def test_given_zero_base_delay_when_constructed_then_validation_error(self):
        """
        Purpose: Proves base_delay must be > 0.
        Quality Contribution: Prevents immediate retry hammering.
        Acceptance Criteria: base_delay=0 raises ValidationError.

        Task: T003
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="base_delay"):
            EmbeddingConfig(base_delay=0)

    def test_given_negative_base_delay_when_constructed_then_validation_error(self):
        """
        Purpose: Proves base_delay must be > 0.
        Quality Contribution: Prevents invalid delay.
        Acceptance Criteria: base_delay=-1 raises ValidationError.

        Task: T003
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="base_delay"):
            EmbeddingConfig(base_delay=-1)

    def test_given_max_delay_less_than_base_when_constructed_then_validation_error(
        self,
    ):
        """
        Purpose: Proves max_delay must be >= base_delay.
        Quality Contribution: Ensures valid exponential backoff ceiling.
        Acceptance Criteria: max_delay < base_delay raises ValidationError.

        Task: T003
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="max_delay"):
            EmbeddingConfig(base_delay=10.0, max_delay=5.0)


@pytest.mark.unit
class TestEmbeddingConfigDimensions:
    """T003: Tests for EmbeddingConfig dimensions validation per Alignment Finding 10."""

    def test_given_zero_dimensions_when_constructed_then_validation_error(self):
        """
        Purpose: Proves dimensions must be > 0.
        Quality Contribution: Prevents invalid vector sizes.
        Acceptance Criteria: dimensions=0 raises ValidationError.

        Task: T003 (V6 fix)
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="dimensions"):
            EmbeddingConfig(dimensions=0)

    def test_given_negative_dimensions_when_constructed_then_validation_error(self):
        """
        Purpose: Proves dimensions must be > 0.
        Quality Contribution: Prevents invalid vector sizes.
        Acceptance Criteria: dimensions=-1 raises ValidationError.

        Task: T003 (V6 fix)
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="dimensions"):
            EmbeddingConfig(dimensions=-1)

    def test_given_custom_dimensions_when_constructed_then_uses_custom_value(self):
        """
        Purpose: Proves dimensions can be customized for different providers.
        Quality Contribution: Ensures configuration flexibility.
        Acceptance Criteria: Custom dimensions value is stored.

        Task: T003 (V6 fix)
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act
        config = EmbeddingConfig(dimensions=3072)

        # Assert
        assert config.dimensions == 3072


@pytest.mark.unit
class TestEmbeddingConfigPath:
    """T003: Tests for EmbeddingConfig __config_path__ key binding."""

    def test_given_config_when_checking_path_then_returns_embedding(self):
        """
        Purpose: Proves YAML key binding matches docs/examples (`embedding:`).
        Quality Contribution: Prevents silent config misbinding in production.
        Acceptance Criteria: __config_path__ is "embedding".

        Task: T003
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act / Assert
        assert EmbeddingConfig.__config_path__ == "embedding"


@pytest.mark.unit
class TestEmbeddingConfigCustomOverrides:
    """T003: Tests for custom chunk config overrides."""

    def test_given_custom_code_chunk_when_constructed_then_overrides_defaults(self):
        """
        Purpose: Proves custom ChunkConfig overrides defaults.
        Quality Contribution: Ensures configuration flexibility.
        Acceptance Criteria: Custom values preserved.

        Task: T003
        """
        from fs2.config.objects import ChunkConfig, EmbeddingConfig

        # Arrange
        custom_code = ChunkConfig(max_tokens=200, overlap_tokens=20)

        # Act
        config = EmbeddingConfig(code=custom_code)

        # Assert
        assert config.code.max_tokens == 200
        assert config.code.overlap_tokens == 20
        # Other defaults unchanged
        assert config.documentation.max_tokens == 4000

    def test_given_mode_fake_when_constructed_then_mode_is_fake(self):
        """
        Purpose: Proves mode can be set to fake for testing.
        Quality Contribution: Ensures testing mode is supported.
        Acceptance Criteria: mode="fake" is valid.

        Task: T003
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act
        config = EmbeddingConfig(mode="fake")

        # Assert
        assert config.mode == "fake"

    def test_given_mode_openai_compatible_when_constructed_then_mode_is_openai_compatible(
        self,
    ):
        """
        Purpose: Proves mode can be set to openai_compatible.
        Quality Contribution: Ensures OpenAI-compatible providers supported.
        Acceptance Criteria: mode="openai_compatible" is valid.

        Task: T003
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act
        config = EmbeddingConfig(mode="openai_compatible")

        # Assert
        assert config.mode == "openai_compatible"


@pytest.mark.unit
class TestEmbeddingConfigLoading:
    """T003: Tests for EmbeddingConfig YAML/env loading."""

    def test_given_yaml_when_loaded_then_uses_yaml_values(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: Proves ConfigurationService binds EmbeddingConfig from YAML.
        Quality Contribution: Prevents config being ignored.
        Acceptance Criteria: YAML values are reflected in required config.

        Task: T003
        """
        from fs2.config.objects import EmbeddingConfig
        from fs2.config.service import FS2ConfigurationService

        # Arrange
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            """embedding:
  mode: fake
  batch_size: 32
  max_retries: 5
  base_delay: 1.0
  max_delay: 30.0
  code:
    max_tokens: 300
    overlap_tokens: 30
scan:
  scan_paths:
    - "."
"""
        )
        monkeypatch.chdir(tmp_path)

        # Act
        service = FS2ConfigurationService()
        config = service.require(EmbeddingConfig)

        # Assert
        assert config.mode == "fake"
        assert config.batch_size == 32
        assert config.max_retries == 5
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0
        assert config.code.max_tokens == 300
        assert config.code.overlap_tokens == 30

    def test_given_env_var_when_loaded_then_env_overrides_yaml(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: Proves env var precedence over YAML for EmbeddingConfig.
        Quality Contribution: Ensures consistent precedence rules across configs.
        Acceptance Criteria: Env overrides YAML values.

        Task: T003
        """
        from fs2.config.objects import EmbeddingConfig
        from fs2.config.service import FS2ConfigurationService

        # Arrange
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            """embedding:
  batch_size: 32
scan:
  scan_paths:
    - "."
"""
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("FS2_EMBEDDING__BATCH_SIZE", "64")

        # Act
        service = FS2ConfigurationService()
        config = service.require(EmbeddingConfig)

        # Assert
        assert config.batch_size == 64


@pytest.mark.unit
class TestAzureEmbeddingConfigDefaults:
    """T001: Tests for AzureEmbeddingConfig nested configuration per DYK-1."""

    def test_given_endpoint_and_api_key_when_constructed_then_stores_values(self):
        """
        Purpose: Per DYK-1: Proves AzureEmbeddingConfig stores connection details.
        Quality Contribution: Enables Azure adapter to connect.
        Acceptance Criteria: endpoint, api_key, deployment_name, api_version stored.

        Task: T001
        """
        from fs2.config.objects import AzureEmbeddingConfig

        # Arrange / Act
        config = AzureEmbeddingConfig(
            endpoint="https://my-resource.openai.azure.com",
            api_key="test-api-key",
            deployment_name="text-embedding-3-small",
            api_version="2024-02-01",
        )

        # Assert
        assert config.endpoint == "https://my-resource.openai.azure.com"
        assert config.api_key == "test-api-key"
        assert config.deployment_name == "text-embedding-3-small"
        assert config.api_version == "2024-02-01"

    def test_given_only_required_fields_when_constructed_then_uses_defaults(self):
        """
        Purpose: Proves AzureEmbeddingConfig has sensible defaults.
        Quality Contribution: Minimizes required config for simple setups.
        Acceptance Criteria: deployment_name and api_version have defaults.

        Task: T001
        """
        from fs2.config.objects import AzureEmbeddingConfig

        # Arrange / Act
        config = AzureEmbeddingConfig(
            endpoint="https://my-resource.openai.azure.com",
            api_key="test-api-key",
        )

        # Assert
        assert config.deployment_name == "text-embedding-3-small"
        assert config.api_version == "2024-02-01"


@pytest.mark.unit
class TestAzureEmbeddingConfigValidation:
    """T001: Tests for AzureEmbeddingConfig validation rules."""

    def test_given_empty_endpoint_when_constructed_then_validation_error(self):
        """
        Purpose: Proves endpoint cannot be empty.
        Quality Contribution: Fails fast on misconfiguration.
        Acceptance Criteria: Empty endpoint raises ValidationError.

        Task: T001
        """
        from fs2.config.objects import AzureEmbeddingConfig

        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="endpoint"):
            AzureEmbeddingConfig(
                endpoint="",
                api_key="test-api-key",
            )

    def test_given_empty_api_key_when_constructed_then_validation_error(self):
        """
        Purpose: Proves api_key cannot be empty.
        Quality Contribution: Fails fast on misconfiguration.
        Acceptance Criteria: Empty api_key raises ValidationError.

        Task: T001
        """
        from fs2.config.objects import AzureEmbeddingConfig

        # Arrange / Act / Assert
        with pytest.raises(ValidationError, match="api_key"):
            AzureEmbeddingConfig(
                endpoint="https://my-resource.openai.azure.com",
                api_key="",
            )


@pytest.mark.unit
class TestAzureEmbeddingConfigOptionalApiKey:
    """Tests for AzureEmbeddingConfig accepting api_key=None (AC4)."""

    def test_given_no_api_key_when_constructed_then_defaults_to_none(self):
        """
        Purpose: Proves api_key defaults to None when omitted.
        Quality Contribution: Enables Azure AD auth path.
        Acceptance Criteria: api_key is None.
        """
        from fs2.config.objects import AzureEmbeddingConfig

        config = AzureEmbeddingConfig(
            endpoint="https://test.openai.azure.com"
        )
        assert config.api_key is None

    def test_given_explicit_none_api_key_when_constructed_then_accepts(self):
        """
        Purpose: Proves explicit None is accepted.
        Quality Contribution: Validates config model change.
        Acceptance Criteria: No ValidationError raised.
        """
        from fs2.config.objects import AzureEmbeddingConfig

        config = AzureEmbeddingConfig(
            endpoint="https://test.openai.azure.com",
            api_key=None,
        )
        assert config.api_key is None

    def test_given_empty_string_api_key_when_constructed_then_rejects(self):
        """
        Purpose: Proves empty string still rejected (existing behavior).
        Quality Contribution: Prevents accidental empty key auth.
        Acceptance Criteria: ValidationError raised.
        """
        from fs2.config.objects import AzureEmbeddingConfig

        with pytest.raises(ValidationError, match="api_key"):
            AzureEmbeddingConfig(
                endpoint="https://test.openai.azure.com",
                api_key="",
            )


@pytest.mark.unit
class TestEmbeddingConfigAzureNested:
    """T001: Tests for azure nested config in EmbeddingConfig per DYK-1."""

    def test_given_no_azure_config_when_constructed_then_azure_is_none(self):
        """
        Purpose: Proves azure config is optional by default.
        Quality Contribution: Allows mode=fake without azure config.
        Acceptance Criteria: azure is None when not provided.

        Task: T001
        """
        from fs2.config.objects import EmbeddingConfig

        # Arrange / Act
        config = EmbeddingConfig(mode="fake")

        # Assert
        assert config.azure is None

    def test_given_azure_config_when_constructed_then_stores_azure(self):
        """
        Purpose: Proves azure nested config is stored correctly.
        Quality Contribution: Enables complete Azure configuration.
        Acceptance Criteria: Nested azure config accessible.

        Task: T001
        """
        from fs2.config.objects import AzureEmbeddingConfig, EmbeddingConfig

        # Arrange
        azure_config = AzureEmbeddingConfig(
            endpoint="https://my-resource.openai.azure.com",
            api_key="test-api-key",
        )

        # Act
        config = EmbeddingConfig(mode="azure", azure=azure_config)

        # Assert
        assert config.azure is not None
        assert config.azure.endpoint == "https://my-resource.openai.azure.com"
        assert config.azure.api_key == "test-api-key"

    def test_given_yaml_with_azure_when_loaded_then_azure_nested_config_loaded(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: Proves nested azure config loads from YAML.
        Quality Contribution: Validates YAML binding works with nesting.
        Acceptance Criteria: embedding.azure.* fields loaded correctly.

        Task: T001
        """
        from fs2.config.objects import EmbeddingConfig
        from fs2.config.service import FS2ConfigurationService

        # Arrange
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            """embedding:
  mode: azure
  azure:
    endpoint: https://test.openai.azure.com
    api_key: yaml-api-key
    deployment_name: my-embedding-model
    api_version: "2024-06-01"
scan:
  scan_paths:
    - "."
"""
        )
        monkeypatch.chdir(tmp_path)

        # Act
        service = FS2ConfigurationService()
        config = service.require(EmbeddingConfig)

        # Assert
        assert config.mode == "azure"
        assert config.azure is not None
        assert config.azure.endpoint == "https://test.openai.azure.com"
        assert config.azure.api_key == "yaml-api-key"
        assert config.azure.deployment_name == "my-embedding-model"
        assert config.azure.api_version == "2024-06-01"

    def test_given_env_with_azure_when_loaded_then_azure_nested_config_loaded(
        self, tmp_path, monkeypatch, clean_config_env
    ):
        """
        Purpose: Proves nested azure config loads from env vars.
        Quality Contribution: Validates env binding works with nesting.
        Acceptance Criteria: FS2_EMBEDDING__AZURE__* fields loaded correctly.

        Task: T001
        """
        from fs2.config.objects import EmbeddingConfig
        from fs2.config.service import FS2ConfigurationService

        # Arrange
        config_dir = tmp_path / ".fs2"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(
            """scan:
  scan_paths:
    - "."
"""
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("FS2_EMBEDDING__MODE", "azure")
        monkeypatch.setenv(
            "FS2_EMBEDDING__AZURE__ENDPOINT", "https://env.openai.azure.com"
        )
        monkeypatch.setenv("FS2_EMBEDDING__AZURE__API_KEY", "env-api-key")

        # Act
        service = FS2ConfigurationService()
        config = service.require(EmbeddingConfig)

        # Assert
        assert config.mode == "azure"
        assert config.azure is not None
        assert config.azure.endpoint == "https://env.openai.azure.com"
        assert config.azure.api_key == "env-api-key"
