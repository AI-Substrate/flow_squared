# LLMService with Provider Adapters

**Mode**: Simple

> **This specification incorporates findings from `research-dossier.md`**

---

## Unresolved Research Opportunities

The following external research topics were identified in `research-dossier.md` but not yet addressed:

- **OpenAI SDK Best Practices 2024+**: Current async client patterns, retry configuration, error handling hierarchy
- **Azure OpenAI Content Safety Policies**: Content filter behavior, error codes, graceful handling strategies

Consider running `/deepresearch` prompts (see research-dossier.md) before finalizing architecture.

---

## Research Context

| Aspect | Finding |
|--------|---------|
| **Components affected** | `config/objects.py`, `core/adapters/`, `core/services/`, `core/models/` |
| **Critical dependencies** | `openai` package (AsyncOpenAI, AsyncAzureOpenAI), existing ConfigurationService |
| **Modification risks** | Must follow exact DI pattern (ConfigurationService injection); two-layer security model for API keys |
| **Reference implementation** | Flowspace `src/modules/llm/` (15+ files, 6,282 indexed nodes) |

See `research-dossier.md` for full analysis including 60 findings across 6 research dimensions.

---

## Summary

**WHAT**: Add an LLMService to fs2 that provides provider-agnostic access to large language models through swappable adapters (OpenAI, Azure OpenAI, Mock).

**WHY**: Enable "smart content" generation capabilities (semantic summaries, code analysis) for the FlowSpace code intelligence system. This foundational service unlocks future features like automated documentation, code understanding, and intelligent search.

---

## Goals

1. **Provider Abstraction**: Developers can switch between OpenAI and Azure OpenAI without code changes (configuration-only)
2. **Secure Secret Management**: API keys are never stored as literals; `${ENV_VAR}` placeholders with runtime expansion
3. **Testable Design**: FakeLLMAdapter enables unit testing without external API calls
4. **Clean Architecture Compliance**: Follows fs2's established adapter patterns (ABC + ConfigurationService DI)
5. **Resilient Operations**: Automatic retry with exponential backoff for transient failures (rate limits, server errors)
6. **Graceful Degradation**: Content filter rejections return structured fallback responses, not crashes

---

## Non-Goals

1. **Streaming responses**: Initial implementation returns complete responses only (streaming deferred)
2. **Embedding generation**: Separate EmbeddingAdapter will be added later
3. **Multiple simultaneous providers**: One active provider at a time (no load balancing/failover)
4. **Fine-tuned model management**: Only standard model selection; no fine-tuning workflows
5. **Cost tracking/budgeting**: Token usage is reported but not enforced
6. **Ollama/local models**: Focus on cloud providers first; local models deferred to future phase
7. **Prompt templating service**: Out of scope; callers provide complete prompts

---

## Complexity

**Score**: CS-3 (medium)

**Breakdown**:

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 1 | Multiple files: 3 config classes, 4 adapter files, 1 service, 1 model, exceptions |
| Integration (I) | 2 | External dependency on `openai` SDK; two provider APIs (OpenAI, Azure) |
| Data/State (D) | 0 | No database schemas or migrations; stateless service |
| Novelty (N) | 1 | Well-specified from Flowspace reference, but some SDK version uncertainty |
| Non-Functional (F) | 1 | Security-critical (API key handling); retry logic required |
| Testing/Rollout (T) | 1 | Integration tests needed but can use fake for unit tests |

**Total**: S(1) + I(2) + D(0) + N(1) + F(1) + T(1) = **6** → **CS-3**

**Confidence**: 0.85 (high confidence due to existing Flowspace reference implementation)

**Assumptions**:
- Flowspace patterns translate cleanly to fs2 Clean Architecture
- OpenAI SDK v1.x is stable and well-documented
- Azure content filtering behavior is predictable

**Dependencies**:
- `openai>=1.0.0` package must be added to project
- ConfigurationService and existing adapter patterns are stable

**Risks**:
- SDK version differences between Flowspace reference and current best practices
- Azure content filter edge cases may require iteration

**Phases** (suggested):
1. Configuration & Models (config classes, LLMResponse, exceptions)
2. Adapter ABC & Fake (interface + test double)
3. OpenAI Adapter (first real provider)
4. Azure Adapter (second provider with content filter handling)
5. LLMService Integration (factory, wiring, testing)

---

## Acceptance Criteria

### AC1: Provider-Agnostic Configuration
**Given** a `.fs2/config.yaml` with `llm.provider: openai`
**When** the application starts
**Then** the LLMService uses the OpenAI adapter without code changes

### AC2: Secure API Key Handling
**Given** a config file with `api_key: sk-literal-key-here`
**When** the configuration is loaded
**Then** a `ValidationError` is raised with message "API key must use ${ENV_VAR} syntax"

### AC3: Environment Variable Expansion
**Given** `api_key: ${OPENAI_API_KEY}` in config and `OPENAI_API_KEY=sk-real-key` in environment
**When** the adapter initializes
**Then** the actual key value is used for API calls (not the placeholder string)

### AC4: Fake Adapter for Testing
**Given** a test using `FakeLLMAdapter`
**When** `adapter.generate(prompt)` is called
**Then** the call is recorded in `adapter.call_history` and a configurable response is returned

### AC5: Retry on Rate Limit
**Given** an API call that returns HTTP 429 (rate limit)
**When** the adapter handles the error
**Then** it retries with exponential backoff (delay = 2^attempt + jitter) up to `max_retries`

### AC6: Azure Content Filter Handling
**Given** Azure OpenAI returns a content filter rejection
**When** the adapter processes the response
**Then** it returns `LLMResponse(was_filtered=True, content="[Content filtered]")` instead of raising

### AC7: Exception Translation
**Given** an OpenAI SDK `AuthenticationError`
**When** the adapter catches it
**Then** it raises `LLMAuthenticationError` (domain exception, not SDK exception)

### AC8: Response Model Contract
**Given** a successful API call
**When** the response is returned
**Then** it contains: `content` (str), `tokens_used` (int), `model` (str), `provider` (str), `finish_reason` (str)

### AC9: ConfigurationService DI Pattern
**Given** an adapter constructor
**When** it receives dependencies
**Then** it accepts `ConfigurationService` (not extracted config) and calls `config.require(ConfigType)` internally

### AC10: Async Interface
**Given** the `LLMAdapter` ABC
**When** defining the `generate` method
**Then** it is declared as `async def generate(...)` returning `Awaitable[LLMResponse]`

---

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OpenAI SDK breaking changes | Low | Medium | Pin version, test on upgrade |
| Azure content filter false positives | Medium | Low | Return `was_filtered=True`, log for debugging |
| API key exposure in logs | Medium | High | Never log key values; use masked logging |
| Rate limit exhaustion | Medium | Medium | Exponential backoff with jitter; max_retries config |
| Environment variable not set | High (dev) | Low | Clear error message with fix instructions |

### Assumptions

1. The `openai` Python package provides stable async clients for both OpenAI and Azure
2. Flowspace's retry logic and error handling patterns are appropriate for fs2
3. Users have access to at least one LLM provider (OpenAI or Azure)
4. The ConfigurationService placeholder expansion (`${VAR}`) works as documented
5. Async/await is acceptable throughout the codebase (no sync-only constraints)

---

## Open Questions

1. ~~**[RESOLVED: Token budget enforcement]**~~ Trust caller; pass `max_tokens` directly to API without enforcement

2. ~~**[RESOLVED: Logging verbosity]**~~ Never log prompt/response content (security first); log metadata only (token counts, model, latency)

3. ~~**[RESOLVED: Timeout defaults]**~~ Default timeout is 120 seconds (covers complex GPT-4 + Azure overhead; configurable 1-600s)

4. ~~**[RESOLVED: Mock provider behavior]**~~ FakeLLMAdapter uses `set_response()` pattern; tests explicitly configure expected output; default returns placeholder

---

## ADR Seeds (Optional)

### Decision: Provider Abstraction Pattern

**Decision Drivers**:
- Need to support multiple LLM providers without code changes
- Must follow fs2 Clean Architecture patterns
- External SDKs must not leak into business logic

**Candidate Alternatives**:
- A) **Adapter ABC Pattern** (recommended): Each provider implements `LLMAdapter` ABC, service composes via DI
- B) **Strategy Pattern**: Provider-specific strategies injected at runtime
- C) **Direct SDK Usage**: No abstraction, switch via conditionals (violates Clean Architecture)

**Stakeholders**: Core maintainers, future SmartContent/Embedding service consumers

### Decision: Secret Management Approach

**Decision Drivers**:
- API keys must never appear in git history
- Configuration should be declarative (YAML)
- Runtime must validate secrets exist before API calls

**Candidate Alternatives**:
- A) **Placeholder Expansion** (recommended): `${VAR}` in config, expand at runtime
- B) **Environment-Only**: No config file support, pure env vars
- C) **Secrets File**: Separate encrypted secrets file (over-engineering for current needs)

---

## Unresolved Research

**Topics** (from `research-dossier.md` External Research Opportunities):
1. OpenAI SDK Best Practices 2024+ - async patterns, retry config, error hierarchy
2. Azure OpenAI Content Safety Policies - filter categories, error formats, handling

**Impact**:
- May affect error handling implementation details
- Could influence retry configuration defaults
- Might reveal SDK features that simplify implementation

**Recommendation**: Consider addressing before architecture phase (plan-3) to reduce implementation uncertainty. Ready-to-use `/deepresearch` prompts are available in the research dossier.

---

## Testing Strategy

- **Approach**: Full TDD
- **Rationale**: Security-critical API key handling and retry logic benefit from comprehensive test coverage; ABC interface contract is highly testable
- **Focus Areas**:
  - API key validation (reject literals, expand placeholders)
  - Retry logic with exponential backoff
  - Exception translation (SDK → domain exceptions)
  - FakeLLMAdapter behavior and call history tracking
  - ConfigurationService DI pattern compliance
- **Excluded**: N/A (will use real Azure OpenAI endpoint for this implementation)
- **Mock Usage**: Targeted mocks (B)
  - **Policy**: Create `FakeLLMAdapter` with `set_response()` pattern; tests explicitly control output
  - **Location**: Lives alongside real implementations in `core/adapters/llm_adapter_fake.py`
  - **Purpose**: Available for other projects/tests needing LLM service isolation
  - **This Project**: Unit/integration tests mock SDK; real API testing via scratch scripts only

---

## Documentation Strategy

- **Location**: docs/how/ only (B)
- **Rationale**: Foundational infrastructure requires detailed setup and extension guides; not a quick-start feature
- **Target Audience**: Developers integrating with or extending the LLM service
- **Planned Content**:
  - `docs/how/llm-service-setup.md` — Environment config, API keys, provider switching
  - `docs/how/llm-adapter-extension.md` — How to add new providers (following ABC pattern)
- **Maintenance**: Update when adding new providers or changing config patterns

---

## Clarifications

### Session 2025-12-18

**Q1: Workflow Mode**
- **Answer**: A (Simple)
- **Rationale**: Strong Flowspace reference implementation reduces discovery; clear patterns allow streamlined execution
- **Impact**: Single-phase plan, inline tasks, plan-4/plan-5 optional

**Q2: Testing Strategy**
- **Answer**: A (Full TDD)
- **Rationale**: Security-critical handling and testable ABC interface warrant comprehensive coverage
- **Impact**: Tests written before/alongside implementation; all ACs have corresponding tests

**Q3: Mock/Stub/Fake Policy**
- **Answer**: B (Targeted mocks)
- **Rationale**: Create FakeLLMAdapter with `set_response()` pattern for reuse; unit/integration tests mock SDK; real API testing via scratch scripts
- **Impact**: FakeLLMAdapter lives in `llm_adapter_fake.py`; tests control output explicitly via `set_response()`

**Q4: Documentation Strategy**
- **Answer**: B (docs/how/ only)
- **Rationale**: Foundational infrastructure needs detailed guides, not quick-start
- **Impact**: Create `docs/how/llm-service-setup.md` and `docs/how/llm-adapter-extension.md`

**Q5: Timeout Defaults**
- **Answer**: B (120 seconds)
- **Rationale**: Complex GPT-4 prompts + Azure content filter overhead need longer timeout; primary use case is smart content generation
- **Impact**: `LLMAdapterConfig.timeout` defaults to 120; range 1-600s; users can tune down if needed

**Q6: Logging Verbosity**
- **Answer**: A (Never log content)
- **Rationale**: Security first; prompts/responses may contain sensitive code or data
- **Impact**: Log metadata only (token counts, model, latency); no prompt/response content in logs

**Q7: Token Budget Enforcement**
- **Answer**: A (Trust caller)
- **Rationale**: Keep service simple; callers are responsible for their token usage
- **Impact**: Pass `max_tokens` directly to API; no validation or clamping

---

## Coverage Summary

| Category | Status | Details |
|----------|--------|---------|
| Workflow Mode | **Resolved** | Simple mode selected |
| Testing Strategy | **Resolved** | Full TDD with targeted fakes |
| Mock Policy | **Resolved** | FakeLLMAdapter with reversed content |
| Documentation | **Resolved** | docs/how/ only |
| Timeout | **Resolved** | 30 seconds default |
| Logging | **Resolved** | Never log content (security) |
| Token Budget | **Resolved** | Trust caller |
| Unresolved Research | **Deferred** | OpenAI SDK + Azure content filter (low risk) |

**All critical ambiguities resolved. Specification ready for architecture.**

---

**Specification Status**: Ready for architecture
**Next Step**: Run `/plan-3-architect` to generate the implementation plan
