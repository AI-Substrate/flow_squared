# LLMService with Provider Adapters Implementation Plan

**Mode**: Simple
**Plan Version**: 1.1.0
**Created**: 2025-12-18
**Spec**: [./llm-service-spec.md](./llm-service-spec.md)
**Research**: [./research-dossier.md](./research-dossier.md)
**Detailed Dossier**: [./tasks.md](./tasks.md) *(Updated config structure, alignment brief, test plan)*
**Status**: READY

> **Config Update (v1.1)**: Simplified to single `LLMConfig` at path `llm` with unified fields. See [tasks.md](./tasks.md) for updated task breakdown and alignment brief.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Critical Research Findings](#critical-research-findings)
3. [Implementation](#implementation)
4. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

**Problem**: fs2 needs to integrate with LLM providers (OpenAI, Azure OpenAI) to enable "smart content" generation capabilities for code analysis, but currently has no LLM infrastructure.

**Solution**: Implement an LLMService with provider-agnostic adapter pattern following fs2's Clean Architecture principles. Create `LLMAdapter` ABC with OpenAI, Azure, and Fake implementations, plus configuration classes with two-layer secret security (Pydantic validators + runtime expansion).

**Expected Outcome**: Developers can switch between OpenAI and Azure OpenAI providers via configuration only, with secure API key handling, retry logic for transient failures, and a FakeLLMAdapter for testing.

---

## Critical Research Findings

> **Note**: This plan incorporates 60 findings from `research-dossier.md` plus 16 implementation/risk discoveries.

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | **Two-Layer Security Model**: API keys must use `${ENV_VAR}` placeholders; Pydantic validators reject literals at config time, expansion at runtime | Implement `@field_validator("api_key")` that rejects strings starting with `sk-` or >10 chars without `${` |
| 02 | Critical | **ConfigurationService DI Pattern**: Adapters receive registry, call `config.require()` internally—no concept leakage | Constructor signature: `def __init__(self, config: ConfigurationService)`, NOT extracted config |
| 03 | Critical | **Async-First Design**: LLM calls are I/O bound; must use `AsyncOpenAI`/`AsyncAzureOpenAI` | All adapter methods must be `async def`; **establish async-all-the-way pattern** for fs2 (CLI commands use `asyncio.run()`) |
| 04 | High | **Exception Translation Boundary**: SDK exceptions must not leak into services | Create `LLMAdapterError` hierarchy; catch generic `Exception`, inspect `status_code` attribute (401=auth, 429=rate limit, 400+content_filter=filtered); **never import SDK exception types** |
| 05 | High | **Exponential Backoff Required**: Rate limits (429) and server errors (502/503) need retry with jitter | Implement `delay = base * (2^attempt) + random.uniform(0, 1)` up to `max_retries` |
| 06 | High | **Azure Content Filter Handling**: Azure may reject with content filter; must return graceful response | Detect via `status_code=400` + "content_filter" in error message; return `LLMResponse(was_filtered=True, content="")` |
| 07 | High | **Environment Variable Validation**: Unexpanded `${VAR}` placeholders must fail loudly | Add post-expansion validation in adapter `__init__` to reject api_key containing `${` |
| 08 | High | **AzureOpenAIConfig Already Exists**: `YAML_CONFIG_TYPES` already has AzureOpenAIConfig at path `azure.openai` | Use DIFFERENT path `llm.azure` for new LLM-specific Azure config to avoid conflict |
| 09 | Medium | **FakeLLMAdapter Uses set_response() Pattern**: Tests explicitly configure expected response via `adapter.set_response()`; default returns placeholder | Implement `set_response()` method; default response is placeholder; tests control output explicitly |
| 10 | Medium | **Logging Security**: Never log prompt/response content per spec Q6 | Log only metadata: token counts, model, latency, provider—never content |
| 11 | Medium | **Timeout Default 120s**: Default timeout is 120 seconds (covers complex GPT-4 prompts + Azure content filter overhead) | Set `timeout: int = 120` in LLMAdapterConfig with range validation 1-600 |
| 12 | Medium | **Trust Caller Token Budget**: Per spec Q7, pass `max_tokens` directly without enforcement | No validation/clamping of max_tokens; pass through to API |
| 13 | Low | **pyproject.toml Needs openai**: External dependency `openai>=1.0.0` not yet added | Add to `[project.dependencies]` in pyproject.toml |
| 14 | High | **Async-All-The-Way Architecture**: fs2 currently has zero async patterns | LLMAdapter establishes async-all-the-way pattern; CLI commands wrap with `asyncio.run()`; future services follow this pattern |

---

## Implementation

**Objective**: Implement LLMService with OpenAI and Azure adapters following fs2 Clean Architecture patterns, with Full TDD approach.

**Testing Approach**: Full TDD (from spec)
- Write tests FIRST for each component
- All acceptance criteria have corresponding tests
- Unit/integration tests: Mock OpenAI SDK (no real API calls)
- Real API testing: Manual via scratch scripts or CLI commands during dev

**Mock Usage**: Targeted (from spec, clarified)
- Create `FakeLLMAdapter` returning reversed content for reuse by other projects
- Unit tests: Mock `openai` SDK to test error paths, retry logic, etc.
- Integration tests: Mock SDK for CI reliability (no external dependencies)
- Real API verification: Manual scratch scripts in `tests/scratch/` for dev-time validation

---

### Tasks

> **Note**: The authoritative task breakdown is in [tasks.md](./tasks.md). This summary reflects the unified LLMConfig structure.

| Status | ID | Task | CS | Type | Dependencies | Validation | Notes |
|--------|-----|------|----|------|--------------|------------|-------|
| [ ] | T001 | Add `openai>=1.0.0` + `pytest-asyncio>=0.23`; configure async test mode | 2 | Setup | -- | `uv sync` succeeds; async tests execute | Finding 13, Insight 01 |
| [ ] | T002 | Write tests for LLMConfig with all fields + secret validation | 2 | Test | T001 | Tests fail (RED); reject `sk-*` literals | TDD |
| [ ] | T003 | Implement LLMConfig in objects.py at path `llm` | 2 | Core | T002 | T002 tests pass (GREEN); cross-field validation | Finding 01, Insight 02 |
| [ ] | T004 | Register LLMConfig in YAML_CONFIG_TYPES | 1 | Core | T003 | Config auto-loaded from YAML | -- |
| [ ] | T005 | Write tests for LLMResponse frozen dataclass | 1 | Test | -- | Tests fail (RED); immutable | TDD |
| [ ] | T006 | Implement LLMResponse dataclass | 1 | Core | T005 | T005 tests pass (GREEN); frozen=True | Finding 04 |
| [ ] | T007 | Write tests for LLM exception hierarchy | 1 | Test | -- | Tests fail (RED); inheritance verified | TDD |
| [ ] | T008 | Add LLMAdapterError hierarchy to exceptions.py | 2 | Core | T007 | T007 tests pass (GREEN); 4 classes | Finding 04 |
| [ ] | T009 | Write tests for LLMAdapter ABC interface | 2 | Test | T006 | Tests fail (RED); async generate() | AC10 |
| [ ] | T010 | Implement LLMAdapter ABC | 2 | Core | T009,T006 | T009 tests pass (GREEN) | AC10 |
| [ ] | T011 | Write tests for FakeLLMAdapter (set_response pattern) | 2 | Test | T010,T003 | Tests fail (RED); set_response() | AC4, Finding 09 |
| [ ] | T012 | Implement FakeLLMAdapter | 2 | Core | T011 | T011 tests pass (GREEN) | AC4 |
| [ ] | T013 | Write tests for OpenAIAdapter with DI pattern | 2 | Test | T010,T003 | Tests fail (RED); ConfigurationService | AC9 |
| [ ] | T014 | Write tests for OpenAI retry + status-code translation | 2 | Test | T013,T008 | Tests fail (RED); backoff on 429 | AC5, AC7, Insight 03 |
| [ ] | T015 | Implement OpenAIAdapter | 3 | Core | T013,T014 | T013+T014 pass (GREEN); getattr pattern | Insight 03, 04 |
| [ ] | T016 | Write tests for AzureAdapter content filter | 2 | Test | T010,T003 | Tests fail (RED); was_filtered=True | AC6, Insight 05 |
| [ ] | T017 | Implement AzureOpenAIAdapter | 3 | Core | T016,T008 | T016 tests pass (GREEN); base_url→azure_endpoint | Insight 02, 04, 05 |
| [ ] | T018 | Write tests for LLMService factory pattern | 2 | Test | T010,T003 | Tests fail (RED); factory creates adapters | AC1, AC9 |
| [ ] | T019 | Implement LLMService | 2 | Core | T018 | T018 tests pass (GREEN) | AC1, AC9 |
| [ ] | T020 | Integration test with mocked SDK | 2 | Test | T017,T019 | Full flow works; SDK mocked | AC8 |
| [ ] | T021 | Create scratch script for real Azure API | 1 | Dev | T017 | Manual dev script; not in CI | Dev workflow |
| [ ] | T022 | Update adapters/__init__.py exports | 1 | Core | T010,T012,T015,T017 | All LLM adapters importable | Cleanup |
| [ ] | T023 | Create .fs2/secrets.env.example | 1 | Config | -- | Example file exists | Setup |
| [ ] | T024 | Update .fs2/config.yaml.example with LLM section | 1 | Config | T004 | LLM config documented | Setup |
| [ ] | T025 | Create docs/how/llm-service-setup.md | 2 | Docs | T019 | Setup guide documented | Doc Strategy |
| [ ] | T026 | Create docs/how/llm-adapter-extension.md | 2 | Docs | T010 | Extension guide documented | Doc Strategy |

**Total**: 26 tasks | **See** [tasks.md](./tasks.md) **for full details including absolute paths and subtasks**

---

### Acceptance Criteria

- [ ] **AC1**: Provider-agnostic configuration — switching `llm.provider` changes adapter without code changes
- [ ] **AC2**: Secure API key handling — literal `sk-*` keys rejected with clear error message
- [ ] **AC3**: Environment variable expansion — `${OPENAI_API_KEY}` expanded to actual value at runtime
- [ ] **AC4**: FakeLLMAdapter — `set_response()` controls output, tracks call history, default returns placeholder
- [ ] **AC5**: Retry on rate limit — exponential backoff (2^attempt + jitter) up to max_retries on 429
- [ ] **AC6**: Azure content filter — returns `was_filtered=True` instead of raising on content filter rejection
- [ ] **AC7**: Exception translation — `status_code=401` → `LLMAuthenticationError`, `429` → `LLMRateLimitError` (no SDK exception imports)
- [ ] **AC8**: Response model contract — `content`, `tokens_used`, `model`, `provider`, `finish_reason` fields present
- [ ] **AC9**: ConfigurationService DI — adapters receive registry, call `config.require()` internally
- [ ] **AC10**: Async interface — `generate()` is `async def` returning `Awaitable[LLMResponse]`

---

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OpenAI SDK breaking changes | Low | Low | Status-code-based error handling decouples from SDK exception types; HTTP codes are stable |
| Azure content filter false positives | Medium | Low | Return `was_filtered=True`; log for debugging |
| API key exposure in logs | Medium | High | Never log content; only metadata (per Q6) |
| Rate limit exhaustion | Medium | Medium | Exponential backoff with jitter; max_retries config |
| Env var not set at runtime | High (dev) | Low | Clear error message with fix instructions |
| Async-all-the-way refactor scope | Medium | Medium | Establishes project-wide async pattern; document in docs/how/; CLI uses `asyncio.run()` wrapper |

---

## Change Footnotes Ledger

[^1]: [To be added during implementation via plan-6a]
[^2]: [To be added during implementation via plan-6a]
[^3]: [To be added during implementation via plan-6a]
[^4]: [To be added during implementation via plan-6a]
[^5]: [To be added during implementation via plan-6a]

---

## Critical Insights Discussion

**Session**: 2025-12-18
**Context**: LLMService Implementation Plan v1.0 (Simple Mode, 30 tasks)
**Analyst**: AI Clarity Agent
**Reviewer**: Development Team
**Format**: Water Cooler Conversation (5 Critical Insights)

### Insight 1: Async-All-The-Way Architecture

**Did you know**: Introducing async adapters creates a fundamental challenge—existing fs2 code is 100% sync, with no pattern for how sync code calls async methods.

**Implications**:
- Every caller of LLMService needs async handling
- CLI commands need `asyncio.run()` wrapper
- This establishes the async pattern for entire project

**Options Considered**:
- Option A: Async CLI Commands - CLI uses `asyncio.run()` wrapper
- Option B: Sync Wrapper Methods - Add `generate_sync()` convenience methods
- Option C: Async Context Manager - Explicit async boundaries
- Option D: Defer Decision - Build async, figure out calling later

**AI Recommendation**: Option B (Sync Wrapper Methods)
- Reasoning: Simplest integration, existing code patterns unchanged

**Discussion Summary**: User chose Option A (async-all-the-way) instead—better long-term architecture even if it requires refactoring. Clean async patterns from the start.

**Decision**: Async-all-the-way architecture; CLI commands use `asyncio.run()`

**Action Items**:
- [x] Updated Finding 03 and 14 to reflect async-all-the-way pattern
- [x] Updated Risks table with architectural decision

**Affects**: Finding 03, Finding 14, Risks table, future CLI patterns

---

### Insight 2: SDK Mocking vs Real API Testing

**Did you know**: "No mocks during implementation" + "real Azure API" means every test run costs money and depends on Azure availability—problematic for TDD's fast feedback loops.

**Implications**:
- Development costs accumulate with test runs
- CI/CD needs Azure credentials and budget
- Can't test error paths (429, 502) without actually triggering them
- Can't develop offline

**Options Considered**:
- Option A: Clarify "No Mocks" Scope - SDK mocking okay for unit tests
- Option B: Real API for All Tests - Maximum confidence, high cost
- Option C: Hybrid Approach - Mock SDK for unit tests, real API for integration
- Option D: Record/Replay with VCR - Record responses, replay in tests

**AI Recommendation**: Option C (Hybrid Approach)
- Reasoning: TDD needs fast feedback; T024 already exists for real API

**Discussion Summary**: User clarified: unit and integration tests should NOT call real API. Real API testing is manual via scratch scripts during dev.

**Decision**: Mock SDK for unit/integration tests; real API via scratch scripts only

**Action Items**:
- [x] Updated Testing Approach section
- [x] Updated Mock Usage section
- [x] Changed T024 from "real Azure" to "mocked SDK full flow"
- [x] Added T025a for scratch script real API testing

**Affects**: Testing Approach, Mock Usage, T024, new T025a

---

### Insight 3: FakeLLMAdapter Response Strategy

**Did you know**: Returning reversed content (`prompt[::-1]`) breaks any test that expects to parse JSON, code, or structured data from LLM responses.

**Implications**:
- Tests parsing LLM output can't use FakeLLMAdapter
- Future SmartContentService needs parseable responses
- Reversed JSON is invalid JSON

**Options Considered**:
- Option A: Keep Reversed, Document Limitation
- Option B: Configurable Response Mode - reversed/echo/fixed/json_template
- Option C: Echo Mode - Return prompt as-is
- Option D: Fixed Response with set_response() - Tests control exactly what they get

**AI Recommendation**: Option B (Configurable Response Mode)
- Reasoning: Flexibility for different test scenarios

**Discussion Summary**: User chose Option D—explicit is better than magic. Tests should configure exactly what they need.

**Decision**: FakeLLMAdapter uses `set_response()` pattern; default returns placeholder

**Action Items**:
- [x] Updated Finding 09
- [x] Updated T015, T016 task descriptions
- [x] Updated AC4 acceptance criteria
- [x] Updated spec Q3 and Testing Strategy

**Affects**: Finding 09, T015, T016, AC4, spec updates

---

### Insight 4: Exception Translation SDK Coupling

**Did you know**: Importing SDK exception types (`from openai import AuthenticationError`) creates tight coupling—if SDK changes exception names in v2.0, our adapters break.

**Implications**:
- SDK version pins become critical
- Upgrades require adapter changes
- Domain exceptions coupled to SDK implementation

**Options Considered**:
- Option A: Strict Version Pinning - `openai>=1.0.0,<2.0.0`
- Option B: Catch-All with Introspection - Inspect error attributes
- Option C: HTTP Status Code Based - Check `e.status_code` (401, 429, etc.)
- Option D: Accept Coupling, Document Upgrade Path

**AI Recommendation**: Option A + D Combined
- Reasoning: SDK is stable; direct imports cleaner than introspection

**Discussion Summary**: User firmly rejected any SDK coupling—Clean Architecture means no external types in domain. Status-code-based approach only.

**Decision**: Status-code-based exception translation; never import SDK exception types

**Action Items**:
- [x] Updated Finding 04 with "never import SDK exception types"
- [x] Updated Finding 06 for status-code-based content filter detection
- [x] Updated T018 task description
- [x] Updated AC7 acceptance criteria
- [x] Reduced SDK risk impact in Risks table

**Affects**: Finding 04, Finding 06, T018, AC7, Risks table

---

### Insight 5: Timeout Default Too Short

**Did you know**: The 30-second default timeout may cause legitimate GPT-4 complex prompts to fail—especially on Azure where content filtering adds 5-15 seconds overhead.

**Implications**:
- Smart content generation for large files may timeout
- Azure slower than direct OpenAI
- Retry on timeout wastes time (same request, same timeout)

**Options Considered**:
- Option A: Increase to 60 seconds
- Option B: Increase to 120 seconds - Matches Azure recommendations
- Option C: Keep 30s, Document Limitation
- Option D: Different Defaults per Provider

**AI Recommendation**: Option B (120 seconds)
- Reasoning: Primary use case is smart content; Azure is the stated provider

**Discussion Summary**: User agreed with recommendation—default should work for primary use case.

**Decision**: Default timeout is 120 seconds (range 1-600s)

**Action Items**:
- [x] Updated Finding 11 to 120s default
- [x] Updated spec Q5 clarification

**Affects**: Finding 11, spec Q5

---

## Session Summary

**Insights Surfaced**: 5 critical insights identified and discussed
**Decisions Made**: 5 architectural decisions reached
**Action Items Created**: All completed inline during session
**Areas Updated**:
- `llm-service-plan.md`: Findings 03, 04, 06, 09, 11, 14; Tasks T015-T018, T024, T025a; AC4, AC7; Risks table; Testing Approach; Mock Usage
- `llm-service-spec.md`: Q3, Q5, Testing Strategy, Open Questions

**Shared Understanding Achieved**: ✓

**Confidence Level**: High - Key architectural decisions made with clear rationale

**Notes**:
- Async-all-the-way is a significant architectural commitment but correct for I/O-heavy codebase
- Status-code-based error handling aligns perfectly with Clean Architecture principles
- set_response() pattern for FakeLLMAdapter is more explicit and flexible than magic behaviors

---

**Next steps:**
- **Ready to implement**: `/plan-6-implement-phase --plan "docs/plans/007-llm-service/llm-service-plan.md"`
- **Optional validation**: `/plan-4-complete-the-plan` (recommended for CS-3 tasks)
- **Optional task expansion**: `/plan-5-phase-tasks-and-brief` (if you want a separate dossier)
