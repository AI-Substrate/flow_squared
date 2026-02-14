# Azure AD Credential Support for fs2

**Mode**: Simple
**File Management**: Legacy
**Testing**: Full TDD
**Documentation**: None (config example in workshop is sufficient)

## Research Context

This specification incorporates findings from `research-dossier.md` and two external research files.

- **Components affected**: 2 adapters (`llm_adapter_azure.py`, `embedding_adapter_azure.py`), 1 config model (`objects.py`), 1 build file (`pyproject.toml`)
- **Critical dependencies**: `azure-identity>=1.18.0,<2` (new optional dep), `openai>=1.0.0` (existing, compatible)
- **Modification risks**: Low — `_get_client()` methods are isolated lazy-init with no side effects. `LLMConfig.api_key` is already optional. Only `AzureEmbeddingConfig.api_key` needs a type change.
- **Links**: See [research-dossier.md](research-dossier.md), [workshop](workshops/az-login-changes.md)

## Summary

Azure policy is changing: API keys are being disallowed on certain tenants. Users who run `az login` need fs2 to automatically use their Azure AD token for Azure OpenAI access, without requiring an API key in config. Key-based auth must remain as the default for tenants that still allow keys.

## Goals

- Users with a valid `az login` session can use fs2 without any API key configured
- Users with API keys continue to work exactly as before (zero breaking changes)
- The auth method is implicit: key present = use key, key absent = use Azure AD credentials
- Actionable error message when `azure-identity` is not installed but Azure AD auth is needed
- No new config fields, flags, or auth mode settings

## Non-Goals

- Async `DefaultAzureCredential` (sync is sufficient for fs2's batch workload)
- Managed Identity support testing (works via `DefaultAzureCredential` chain, but not our target use case)
- Sharing a single token provider across LLM and embedding adapters (YAGNI — each adapter creates its own)
- Service principal / certificate auth configuration (works via `DefaultAzureCredential` chain, no fs2 changes needed)
- Migration tooling or config conversion scripts

## Complexity

- **Score**: CS-2 (small)
- **Breakdown**: S=1, I=1, D=0, N=0, F=0, T=1
  - S=1: 4 files across config and adapters
  - I=1: One new external dep (`azure-identity`)
  - D=0: No schema/migration changes
  - N=0: Well-specified, research complete, workshop done
  - F=0: Standard auth pattern, no compliance constraints
  - T=1: Need integration-level tests for the new branch
- **Confidence**: 0.95
- **Assumptions**: `azure-identity` sync credential works with `AsyncAzureOpenAI` (confirmed by external research)
- **Dependencies**: `azure-identity>=1.18.0,<2` package availability
- **Risks**: None significant — surgical change to well-isolated code
- **Phases**: Single phase, no feature flags needed

## Acceptance Criteria

1. **AC1**: When `api_key` is present in config, both LLM and embedding adapters authenticate via API key (existing behavior, unchanged).

2. **AC2**: When `api_key` is absent (not set or `None`) and `azure-identity` is installed, both adapters authenticate via `DefaultAzureCredential` + `get_bearer_token_provider` with scope `https://cognitiveservices.azure.com/.default`.

3. **AC3**: When `api_key` is absent and `azure-identity` is NOT installed, both adapters raise an actionable error: "azure-identity package is required for Azure AD authentication. Install it with: pip install fs2[azure-ad]".

4. **AC4**: `AzureEmbeddingConfig.api_key` accepts `None` (type: `str | None = None`). Existing validation rejects empty strings but allows `None`.

5. **AC5**: `pyproject.toml` includes an `azure-ad` optional dependency group containing `azure-identity>=1.18.0,<2`.

6. **AC6**: All existing tests pass without modification (they use `api_key="test-key"` and mock clients).

7. **AC7**: `api_key` and `azure_ad_token_provider` are never both passed to `AsyncAzureOpenAI` (mutually exclusive).

## Risks & Assumptions

| Risk / Assumption | Impact | Mitigation |
|---|---|---|
| `DefaultAzureCredential` tries 6+ credential sources sequentially; first call can take ~10s if early sources fail | Minor UX delay on first API call | Acceptable for batch workloads. Users can set `AZURE_TOKEN_CREDENTIALS=dev` to skip production credential sources |
| Token refresh blocks the event loop for ~100-500ms every ~30-60 min | Negligible for fs2's scan/embed workload | Documented; switch to async credential if fs2 becomes high-concurrency |
| User must have `Cognitive Services OpenAI User` RBAC role | Auth failure if missing | SDK error message is clear; we don't need to wrap it |

## Open Questions

None. Research and workshop have resolved all design questions.

## ADR Seeds (Optional)

- **Decision Drivers**: Azure tenant policy disabling API keys; need backward-compatible auth
- **Candidate Alternatives**:
  - A: Implicit detection (key present → use it, absent → Azure AD) — **chosen**
  - B: Explicit `auth_mode: key | azure_ad` config field — rejected (YAGNI, adds config complexity)
  - C: Always try Azure AD first, fall back to key — rejected (breaks existing behavior, slower)
- **Stakeholders**: fs2 users on restricted Azure tenants

## External Research

- **Incorporated**:
  - `external-research/azure-identity-version-compat.md` — version pinning, `get_bearer_token_provider()` availability
  - `external-research/async-credential-behavior.md` — sync vs async credential decision, token provider sharing
- **Key Findings**: Sync `DefaultAzureCredential` works with `AsyncAzureOpenAI`. Recommended pin `>=1.18.0,<2`. No cleanup/close needed. Scope must be `https://cognitiveservices.azure.com/.default`.
- **Applied To**: Goals, Complexity, Risks, AC2, AC5

## Unresolved Research

None. All external research opportunities from the dossier have been addressed.

## Workshop Opportunities

Workshop already completed: [az-login-changes.md](workshops/az-login-changes.md)

All design decisions are resolved. No further workshops needed.

## Testing Strategy

- **Approach**: Full TDD
- **Rationale**: Write tests first for each change; small surface area makes TDD natural
- **Focus Areas**:
  - `_get_client()` branches: key-based vs Azure AD credential path
  - `AzureEmbeddingConfig` accepting `api_key=None`
  - `ImportError` handling when `azure-identity` not installed
  - Mutual exclusivity of `api_key` / `azure_ad_token_provider` args
- **Excluded**: Existing adapter behavior (already well-tested with `api_key="test-key"`)
- **Mock Usage**: Targeted mocks — mock `azure-identity` imports (`DefaultAzureCredential`, `get_bearer_token_provider`) only. Use existing fake/mock patterns for everything else.

## Documentation Strategy

- **Location**: None
- **Rationale**: Config change is self-evident (remove `api_key` line). Workshop has the full before/after example. No user-facing docs needed.

## Clarifications

### Session 2026-02-13

| # | Question | Answer | Updated Section |
|---|----------|--------|-----------------|
| Q1 | Workflow mode? | **Simple** — CS-2, single phase, quick path | Spec header |
| Q2 | Testing approach? | **Full TDD** — write tests first | Testing Strategy |
| Q3 | Mock policy? | **Targeted mocks** — mock azure-identity only | Testing Strategy |
| Q4 | Documentation? | **None** — config example in workshop sufficient | Documentation Strategy |

**Coverage Summary**:
- Resolved: Mode, Testing, Mocks, Documentation (4/4)
- Deferred: None
- Outstanding: None
