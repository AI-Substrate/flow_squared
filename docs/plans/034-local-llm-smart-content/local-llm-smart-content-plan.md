# Implementation Plan: Local LLM Smart Content Generation

> **Plan ID**: 034-local-llm-smart-content
> **Spec**: `local-llm-smart-content-spec.md`
> **Mode**: Simple (single phase, inline tasks)
> **Status**: COMPLETE

## Summary

Add a local LLM adapter (Ollama) so fs2 generates AI-powered smart_content summaries without API keys or network access. The existing LLM infrastructure (plan 007) provides the adapter ABC, service factory, and SmartContentStage — we just add one new adapter implementation and wire it in.

## Goals Coverage

| Goal | Description | Tasks |
|------|-------------|-------|
| G1 | Smart content without API keys | T04, T06, T11 |
| G2 | Integrates with existing SmartContentStage | T06 (zero stage changes) |
| G3 | Config follows existing LLM pattern | T01, T02 |
| G4 | Incremental hash-based skip | T11 (verify existing behavior) |
| G5 | Cross-platform via Ollama | T04, T10 |
| G6 | Discoverable setup instructions | T08, T10 |
| G7 | Local LLM default in fs2 init | T07 |

## Target Domains

| Domain | Status | Relationship | Tasks |
|--------|--------|-------------|-------|
| adapters | existing | **modify** | T03, T04, T09 |
| config | existing | **modify** | T01, T02 |
| services | existing | **modify** | T05, T06 |
| cli | existing | **modify** | T07, T08 |
| stages | existing | **consume** | — (zero changes) |
| docs | existing | **modify** | T10 |

---

## Research Findings

| ID | Finding | Impact | Source |
|----|---------|--------|--------|
| RF-01 | OpenAI adapter has `base_url` but requires `api_key` — can't reuse for Ollama (no key) | Critical — need new adapter | R-1, F-1 |
| RF-02 | **Second factory in scan.py** duplicates LLMService.create() logic — must add local branch there too OR refactor | Critical — same gotcha as plan 032 | F-5 |
| RF-03 | Timeout validator hardcoded to `1-120s` — local needs up to 300s | Critical — config blocks local use | R-2 |
| RF-04 | Prompt format compatible — SmartContentService sends string, adapter wraps as messages array | Safe — no format mismatch | R-4 |
| RF-05 | Doctor `_test_llm_provider()` auto-tests any provider via LLMService.create() | Positive — AC10 partly free | F-4 |
| RF-06 | LLMService.create() is clean single factory — add elif clause | Low risk | F-3 |
| RF-07 | LocalEmbeddingConfig pattern exists — follow for LocalLLMConfig | Pattern ready | F-2 |

---

## Task Table

| ID | Task | Domain | ACs | Deps | Status |
|----|------|--------|-----|------|--------|
| T01 | Config TDD: Write tests for LLMConfig "local" provider + LocalLLMConfig + timeout 300s validator | config | AC03, AC09 | — | [x] |
| T02 | Config: Extend LLMConfig with "local" provider, add LocalLLMConfig, update timeout validator | config | AC03, AC09 | T01 | [x] |
| T03 | Adapter TDD: Write tests for LocalOllamaAdapter (generate, errors, timeout, provider_name) | adapters | AC02, AC04, AC05, AC08, AC12 | — | [x] |
| T04 | Adapter: Implement LocalOllamaAdapter using httpx to Ollama /v1/chat/completions | adapters | AC02, AC04, AC05, AC08, AC12 | T03 | [x] |
| T05 | Factory TDD: Write tests for LLMService.create() with provider="local" | services | AC03 | T02 | [x] |
| T06 | Factory: Add "local" branch to LLMService.create() AND scan.py _create_smart_content_service() | services | AC03 | T04, T05 | [x] |
| T07 | CLI: Update init.py DEFAULT_CONFIG with local LLM as default provider | cli | AC07 | T02 | [x] |
| T08 | Doctor: Verify fs2 doctor works with local provider (test generation check) | cli | AC10 | T06 | [x] |
| T09 | Exports: Update adapters/__init__.py with LocalOllamaAdapter | adapters | AC01 | T04 | [x] |
| T10 | Docs: Create docs/how/user/local-llm.md + update configuration-guide.md + MCP help | docs | AC11 | T06 | [x] |
| T11 | Integration test: End-to-end scan with local LLM on real codebase | — | AC01, AC06 | T06 | [x] |

---

## Task Details

### T01: Config TDD — Tests for local provider + LocalLLMConfig

**File**: `tests/unit/config/test_llm_config.py` (extend existing)

Tests to write:
- `test_llm_config_provider_local_valid` — provider="local" accepted
- `test_llm_config_local_requires_base_url` — validation error when base_url missing
- `test_llm_config_local_requires_model` — validation error when model missing
- `test_llm_config_local_no_api_key_required` — api_key=None accepted for local
- `test_llm_config_local_timeout_allows_300s` — timeout=300 accepted for local provider
- `test_llm_config_cloud_timeout_rejects_300s` — timeout=300 rejected for azure/openai
- `test_local_llm_config_defaults` — default base_url, model values

**Pattern**: Follow existing `TestLLMConfigProvider`, `TestLLMConfigAzureFields` classes.

### T02: Config — Extend LLMConfig

**Files**: `src/fs2/config/objects.py`

Changes:
- Add `LocalLLMConfig(BaseModel)` with `base_url`, `model`, `timeout` fields
- Extend provider Literal: `Literal["azure", "openai", "fake", "local"]`
- Add `local: LocalLLMConfig | None = None` field to LLMConfig
- Update `validate_timeout`: use `model_validator(mode="after")` to allow 300s when provider="local"
- Add `validate_local_fields`: require base_url + model when provider="local"

### T03: Adapter TDD — Tests for LocalOllamaAdapter

**File**: `tests/unit/adapters/test_llm_adapter_local.py` (new)

Tests to write:
- `test_local_adapter_provider_name_is_local`
- `test_local_adapter_generate_returns_llm_response` — mock httpx, verify response fields
- `test_local_adapter_connection_refused_raises_adapter_error` — AC04
- `test_local_adapter_model_not_found_raises_with_pull_suggestion` — AC05
- `test_local_adapter_timeout_raises_clear_error` — AC12
- `test_local_adapter_http_error_translates_to_adapter_error` — AC08
- `test_local_adapter_receives_config_service` — AC09
- `test_local_adapter_uses_config_base_url_and_model`

**Pattern**: Mock `httpx.AsyncClient.post()`. Follow `test_llm_adapter_openai.py` structure.

### T04: Adapter — Implement LocalOllamaAdapter

**File**: `src/fs2/core/adapters/llm_adapter_local.py` (new, ~150 lines)

Implementation:
- `class LocalOllamaAdapter(LLMAdapter)` with `provider_name = "local"`
- `__init__(self, config: ConfigurationService)` — extracts LLMConfig, stores LocalLLMConfig
- **DYK-2**: Reuse `openai` SDK (already a dependency) with `api_key="ollama"` sentinel + `base_url` from config — zero new deps, proven retry/timeout logic
- **DYK-5**: Hardcode `api_key="ollama"` in `_get_client()` — don't read from LLMConfig. Empty string crashes SDK with confusing OpenAI error message
- **DYK-3**: `response.usage` null-safety already covered by OpenAI SDK pattern — add test for `usage=None` → `tokens_used=0`
- `_get_client()` — lazy AsyncOpenAI creation with `base_url` from LocalLLMConfig
- `async def generate()` — same pattern as OpenAIAdapter but simpler (no retry needed for local, no content filter)
- Error translation: `ConnectionRefusedError` → actionable "Install/start Ollama" message
- Error translation: 404 model not found → "Run: ollama pull {model}"
- Error translation: timeout → "Increase timeout or use a smaller model"

### T05: Factory TDD — Tests for LLMService.create() local branch

**File**: `tests/unit/services/test_llm_service.py` (extend existing)

Tests to write:
- `test_llm_service_factory_creates_local` — provider="local" returns service with LocalOllamaAdapter

### T06: Factory — Wire local provider into factories

**Files**:
- `src/fs2/core/services/llm_service.py` — add `elif llm_config.provider == "local"` in create()
- `src/fs2/cli/scan.py` — add same branch in `_create_smart_content_service()` (RF-02: second factory!)

**⚠️ RF-02 WARNING**: scan.py has a DUPLICATE factory that creates adapters independently of LLMService.create(). Must add the local branch in BOTH places (same gotcha as plan 032 embeddings).

**⚠️ DYK-1 WARNING**: The scan.py factory has an `else: return None, "unsupported provider"` fallthrough. If the local branch is missing or misspelled, the scan completes successfully with ZERO smart_content and no error — just a quiet status message. Consider refactoring scan.py to call `LLMService.create()` instead of duplicating the if/elif chain.

### T07: CLI — Update DEFAULT_CONFIG

**File**: `src/fs2/cli/init.py`

Changes:
- Add local LLM section as the FIRST (default) option, uncommented
- Comment out Azure/OpenAI sections as alternatives
- Include recommended model: `qwen2.5-coder:7b`
- Include default base_url: `http://localhost:11434`
- **DYK-4**: Grep for tests checking DEFAULT_CONFIG LLM section before changing — same regression risk as plan 032 embedding default change

### T08: Doctor — Verify local provider check

**File**: `src/fs2/cli/doctor.py` (may need no changes per RF-05)

Verify:
- `fs2 doctor llm` works with provider=local
- Test generation sends small prompt to Ollama
- Error messages are actionable when Ollama not running

If doctor already auto-tests via LLMService.create() (RF-05), this may be verification-only.

### T09: Exports — Update __init__.py

**File**: `src/fs2/core/adapters/__init__.py`

Changes:
- Add `from fs2.core.adapters.llm_adapter_local import LocalOllamaAdapter`
- Add to `__all__` list

### T10: Docs — User guide + config guide + MCP help

**Files**:
- `docs/how/user/local-llm.md` (new) — Quick start, install Ollama, pull model, configure fs2, run scan
- `docs/how/user/configuration-guide.md` (update) — Add local LLM section parallel to local embeddings section
- MCP help docs — Ensure `fs2 doctor` and setup instructions are discoverable

### T11: Integration test — End-to-end verification

Manual verification (not automated — requires running Ollama):
- Configure local LLM in a test project
- Run `fs2 scan` — verify smart_content populated
- Run `fs2 scan` again — verify hash-based skip (AC06)
- Run `fs2 doctor llm` — verify connectivity + test generation (AC10)
- Verify summaries appear in `fs2 tree` and `fs2 search`

---

## Architecture

```
.fs2/config.yaml          src/fs2/config/            src/fs2/core/adapters/
┌──────────────┐          ┌────────────────────┐     ┌──────────────────────────┐
│ llm:         │──parse──▶│ LLMConfig          │     │ LLMAdapter (ABC)         │
│   provider:  │          │   provider: "local" │     │   ├─ OpenAIAdapter       │
│     local    │          │   local:            │     │   ├─ AzureOpenAIAdapter  │
│   local:     │          │     LocalLLMConfig  │     │   ├─ FakeLLMAdapter      │
│     base_url │          │       base_url      │     │   └─ LocalOllamaAdapter  │◀─NEW
│     model    │          │       model         │     └──────────────────────────┘
└──────────────┘          └────────┬───────────┘                   │
                                   │                               │
                    src/fs2/core/services/          ┌──────────────┴──────┐
                    ┌──────────────────────┐        │ Ollama Service      │
                    │ LLMService.create()  │──if───▶│ localhost:11434     │
                    │   provider=="local"  │ local  │ /v1/chat/completions│
                    └──────────┬───────────┘        └─────────────────────┘
                               │
                    ┌──────────┴───────────┐
                    │ SmartContentService   │  ← ZERO CHANGES
                    │   .process_batch()   │
                    └──────────┬───────────┘
                               │
                    ┌──────────┴───────────┐
                    │ SmartContentStage     │  ← ZERO CHANGES
                    │   .process(context)   │
                    └──────────────────────┘
```

---

## Progress

- Tasks: 11/11 complete
- ACs verified: 12/12
- Status: **COMPLETE** — committed and pushed (`1dd2a7f`)
- Tests: 1736 passed, 0 failed (+17 new tests from baseline 1698)
- Lint: clean (`uv run ruff check` passes all touched files)

## Fixes

| ID | Created | Summary | Domain(s) | Status | Source |
|----|---------|---------|-----------|--------|--------|
| FX001 | 2026-03-15 | Review fixes (exception handling, ruff, docs registry, factory refactor) + "just works" UX (Ollama auto-detect, smart_content default, init messaging) | adapters, cli, docs, tests | **Complete** | plan-7-v2 review + workshop 001 |

## Changes by Domain

| Domain | Files Changed | What |
|--------|--------------|------|
| **adapters** | `llm_adapter_local.py` (new), `__init__.py` | New LocalOllamaAdapter, catches `APIConnectionError`/`APITimeoutError`, exports |
| **config** | `objects.py` | "local" provider, merged `validate_provider_fields`, 300s timeout for local |
| **services** | `llm_service.py`, `smart_content_service.py` | Factory wiring + progress reports every item |
| **cli** | `scan.py`, `init.py` | Factory refactored to `LLMService.create()`, Ollama auto-detect, smart_content default |
| **docs** | `local-llm.md` (new), `configuration-guide.md`, `registry.yaml` | User guide, config guide updated, MCP docs registered |
| **tests** | `test_llm_adapter_local.py` (new), `test_llm_config.py`, `test_llm_service.py` | 17 new tests: adapter, config, factory |
