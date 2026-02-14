# Azure AD Credential Support — Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-02-13
**Spec**: [./az-login-spec.md](./az-login-spec.md)
**Workshop**: [./workshops/az-login-changes.md](./workshops/az-login-changes.md)
**Research**: [./research-dossier.md](./research-dossier.md)
**Status**: COMPLETE

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Research Findings](#critical-research-findings)
3. [Testing Philosophy](#testing-philosophy)
4. [Implementation](#implementation)
5. [Change Footnotes Ledger](#change-footnotes-ledger)

## Executive Summary

Azure policy is disabling API keys on certain tenants. Users who `az login` need fs2 to
use their Azure AD token for Azure OpenAI access. The design rule is simple: **key present
→ use it; key absent → use `az login` credentials.** This requires branching `_get_client()`
in two adapters, making one config field optional, and adding an optional dependency. ~38
lines changed across 4 files, zero new files or abstractions.

## Critical Research Findings

Sourced from [research-dossier.md](./research-dossier.md), [workshop](./workshops/az-login-changes.md),
and [external research](./external-research/).

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | `_get_client()` in both adapters is the only code that constructs `AsyncAzureOpenAI` — isolated, lazy-init, no side effects | Branch on `api_key` presence inside `_get_client()` only |
| 02 | Critical | `api_key` and `azure_ad_token_provider` are mutually exclusive in `AsyncAzureOpenAI` — passing both causes undefined behavior | Never pass both params; use if/else branching |
| 03 | Critical | `azure-identity` is NOT a dependency — no references exist anywhere in codebase | Lazy-import inside `_get_client()` else branch; handle `ImportError` |
| 04 | High | `LLMConfig.api_key` is already `str \| None = None` with `if api_key is not None:` guard at adapter init (line 73) | No changes needed to LLM config or LLM adapter init |
| 05 | High | `AzureEmbeddingConfig.api_key` is `str` (required) with validator rejecting empty strings | Change to `str \| None = None`, update validator to accept `None` |
| 06 | High | Sync `DefaultAzureCredential` works with `AsyncAzureOpenAI` — SDK auto-detects via `inspect.isawaitable()` | Use sync credential (simpler, no lifecycle management) |
| 07 | High | Correct scope is `https://cognitiveservices.azure.com/.default` (NOT `openai.azure.com`) | Hardcode scope string in both adapters |
| 08 | High | `get_bearer_token_provider()` available since azure-identity 1.15.0; pin `>=1.18.0,<2` for improved caching | Add `azure-ad` optional dep group in pyproject.toml |
| 09 | Medium | All existing tests use `api_key="test-key"` with mocked clients | Existing tests pass unchanged — they always hit the key-present branch |
| 10 | Medium | Test pattern: `patch.object(adapter, "_get_client", ...)` for mocking client | New tests should mock at import level for `azure.identity`, not `_get_client` |
| 11 | Medium | Error classes: `LLMAdapterError`, `EmbeddingAdapterError` in `fs2.core.adapters.exceptions` | Use these for `ImportError` wrapping with actionable install message |
| 12 | Low | Embedding adapter init error message (line 64-67) says "Set embedding.azure.api_key" | Consider updating to mention Azure AD alternative (nice-to-have) |

## Testing Philosophy

### Testing Approach

- **Selected Approach**: Full TDD
- **Mock Usage**: Targeted mocks — mock `azure-identity` imports only (`DefaultAzureCredential`,
  `get_bearer_token_provider`). Use existing `MagicMock(spec=ConfigurationService)` patterns
  for config. Do not mock anything else.
- **Focus Areas**:
  - `_get_client()` branches: key-based vs Azure AD credential path
  - `AzureEmbeddingConfig` accepting `api_key=None`
  - `ImportError` handling when `azure-identity` not installed
  - Mutual exclusivity of `api_key` / `azure_ad_token_provider` args
- **Excluded**: Existing adapter behavior (already well-tested with `api_key="test-key"`)

### TDD Cycle

1. Write tests FIRST (RED) — tests fail because feature not yet implemented
2. Implement minimal code (GREEN) — make tests pass
3. Verify no regressions — run full existing test suite

## Implementation (Single Phase)

**Objective**: Add Azure AD credential support via `DefaultAzureCredential` when no API key
is configured, maintaining full backward compatibility with key-based auth.

**Testing Approach**: Full TDD
**Mock Usage**: Targeted mocks (azure-identity only)

### Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|----|------|----|------|--------------|-------------------|------------|-------|
| [x] | T001 | Write tests for `AzureEmbeddingConfig` accepting `api_key=None` | 1 | Test | -- | /Users/jak/github/fs2-az-login/tests/unit/config/test_embedding_config.py | 3 new tests: accepts None, defaults to None, still rejects empty string. All FAIL (RED). | AC4 |
| [x] | T002 | Make `AzureEmbeddingConfig.api_key` optional (`str \| None = None`) and update validator | 1 | Core | T001 | /Users/jak/github/fs2-az-login/src/fs2/config/objects.py | T001 tests pass (GREEN). Existing config tests still pass. | AC4 |
| [x] | T003 | Write tests for LLM adapter `_get_client()` Azure AD branch | 2 | Test | -- | /Users/jak/github/fs2-az-login/tests/unit/adapters/test_llm_adapter_azure.py | 3 new tests: (1) no key + azure-identity → uses token provider, (2) no key + no azure-identity → raises `LLMAdapterError` with install message, (3) key present → passes `api_key` only (no `azure_ad_token_provider`). All FAIL (RED). | AC2, AC3, AC7 |
| [x] | T004 | Implement LLM adapter `_get_client()` branching | 1 | Core | T003 | /Users/jak/github/fs2-az-login/src/fs2/core/adapters/llm_adapter_azure.py | T003 tests pass (GREEN). | AC2, AC3, AC7 |
| [x] | T005 | Write tests for Embedding adapter `_get_client()` Azure AD branch | 2 | Test | T002 | /Users/jak/github/fs2-az-login/tests/unit/adapters/test_embedding_adapter_azure.py | 3 new tests: same pattern as T003 but with `EmbeddingAdapterError`. All FAIL (RED). | AC2, AC3, AC7 |
| [x] | T006 | Implement Embedding adapter `_get_client()` branching | 1 | Core | T005 | /Users/jak/github/fs2-az-login/src/fs2/core/adapters/embedding_adapter_azure.py | T005 tests pass (GREEN). | AC2, AC3, AC7 |
| [x] | T007 | Add `azure-ad` optional dependency group to pyproject.toml | 1 | Config | -- | /Users/jak/github/fs2-az-login/pyproject.toml | `azure-ad = ["azure-identity>=1.18.0,<2"]` group present. | AC5 |
| [x] | T008 | Run full test suite — verify zero regressions | 1 | Verify | T002, T004, T006, T007 | -- | `pytest tests/ -v` passes 100%. All existing tests unchanged and passing. | AC1, AC6 |

### Test Examples (Write First — T001)

```python
# tests/unit/config/test_embedding_config.py — new tests for AC4

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
```

### Test Examples (Write First — T003)

```python
# tests/unit/adapters/test_llm_adapter_azure.py — new tests for AC2, AC3, AC7

@pytest.mark.unit
class TestAzureAdapterAzureADAuth:
    """Tests for Azure AD credential support in _get_client()."""

    def test_given_no_api_key_and_azure_identity_when_get_client_then_uses_token_provider(self):
        """
        Purpose: Proves Azure AD auth path when api_key absent.
        Quality Contribution: Core AC2 — DefaultAzureCredential flow.
        Acceptance Criteria: AsyncAzureOpenAI called with azure_ad_token_provider, NOT api_key.
        """
        # Mock azure.identity at import level
        mock_credential = MagicMock()
        mock_token_provider = MagicMock()

        with patch.dict("sys.modules", {
            "azure": MagicMock(),
            "azure.identity": MagicMock(
                DefaultAzureCredential=MagicMock(return_value=mock_credential),
                get_bearer_token_provider=MagicMock(return_value=mock_token_provider),
            ),
        }):
            # ... create adapter with api_key=None
            # ... call _get_client()
            # ... assert AsyncAzureOpenAI called with azure_ad_token_provider=mock_token_provider
            # ... assert api_key NOT in call kwargs
            pass

    def test_given_no_api_key_and_no_azure_identity_when_get_client_then_raises_error(self):
        """
        Purpose: Proves actionable error when azure-identity not installed.
        Quality Contribution: Core AC3 — clear install instructions.
        Acceptance Criteria: LLMAdapterError with 'pip install fs2[azure-ad]' message.
        """
        # ... create adapter with api_key=None
        # ... mock import to raise ImportError
        # ... assert LLMAdapterError raised with install message
        pass

    def test_given_api_key_when_get_client_then_uses_key_not_token_provider(self):
        """
        Purpose: Proves mutual exclusivity (AC7) — key present means no token provider.
        Quality Contribution: Prevents undefined AsyncAzureOpenAI behavior.
        Acceptance Criteria: api_key passed, azure_ad_token_provider NOT passed.
        """
        # ... create adapter with api_key="test-key"
        # ... call _get_client()
        # ... assert api_key="test-key" in call, no azure_ad_token_provider
        pass
```

### Acceptance Criteria

- [x] **AC1**: api_key present → key-based auth (existing behavior unchanged)
- [x] **AC2**: api_key absent + azure-identity installed → Azure AD auth via `DefaultAzureCredential`
- [x] **AC3**: api_key absent + azure-identity NOT installed → actionable `LLMAdapterError`/`EmbeddingAdapterError`
- [x] **AC4**: `AzureEmbeddingConfig.api_key` accepts `None` (type: `str | None = None`)
- [x] **AC5**: `pyproject.toml` has `azure-ad` optional dep group with `azure-identity>=1.18.0,<2`
- [x] **AC6**: All existing tests pass without modification
- [x] **AC7**: `api_key` and `azure_ad_token_provider` never both passed to `AsyncAzureOpenAI`

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Mocking `sys.modules` for azure-identity import tests is fragile | Medium | Low | Use `unittest.mock.patch.dict("sys.modules", ...)` — well-established pattern |
| Existing tests break due to config model change | Low | High | `AzureEmbeddingConfig` change is additive (None default); existing tests always pass `api_key="test-key"` |
| `DefaultAzureCredential` scope string wrong | Low | High | Hardcode `https://cognitiveservices.azure.com/.default` per external research |

## Change Footnotes Ledger

[^1]: Task T002 - Made AzureEmbeddingConfig.api_key optional
  - `file:src/fs2/config/objects.py`

[^2]: Task T004 - Added Azure AD auth branch to LLM adapter
  - `callable:src/fs2/core/adapters/llm_adapter_azure.py:AzureOpenAIAdapter._get_client`

[^3]: Task T006 - Added Azure AD auth branch to Embedding adapter
  - `callable:src/fs2/core/adapters/embedding_adapter_azure.py:AzureEmbeddingAdapter._get_client`

[^4]: Task T007 - Added azure-ad optional dependency group
  - `file:pyproject.toml`

---

**Status**: COMPLETE — All tasks done, all ACs verified, Azure AD auth tested end-to-end.

**Next steps:**
- **Commit**: Stage and commit all changes on `az-login` branch
- **PR**: Create pull request to merge into `main`
- **Separate issue**: `max_tokens` vs `max_completion_tokens` bug in LLM adapter (pre-existing, not Azure AD related)
