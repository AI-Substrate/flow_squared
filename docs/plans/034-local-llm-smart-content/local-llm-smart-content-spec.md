# Local LLM Smart Content Generation

**Mode**: Simple
📚 This specification incorporates findings from `exploration.md` and session benchmarks.

## Summary

Enable fs2 to generate high-quality AI-powered smart_content summaries for code nodes using a **local LLM** (via Ollama), eliminating the need for cloud API keys or network access. Users install Ollama, pull a code-focused model, and fs2 automatically generates concise summaries for every class, function, and file during `fs2 scan`. Summaries power semantic search, MCP tool responses, and tree output enrichment.

**WHY**: The current smart_content stage requires Azure/OpenAI API keys, which creates setup friction, costs money, and sends proprietary code to external servers. A local option makes smart content accessible to every user out of the box — same value proposition as local embeddings (plan 032).

## Goals

- **G1**: Users can generate smart_content for all code nodes without API keys or network access
- **G2**: Local LLM integrates with the existing SmartContentStage — no new pipeline stages needed
- **G3**: Configuration follows the same pattern as existing LLM providers (YAML `llm:` section)
- **G4**: Incremental scans skip unchanged nodes (hash-based), making re-scans fast after initial generation
- **G5**: Cross-platform: works on Apple Silicon (Metal), NVIDIA (CUDA), and CPU-only machines via Ollama's auto-detection
- **G6**: Setup instructions are discoverable via `fs2 doctor`, CLI help, MCP server docs, and user guides
- **G7**: `fs2 init` generates a config template with local LLM as the default provider

## Non-Goals

- **NG1**: Embedding Ollama or llama-cpp-python as a Python dependency — Ollama is an external service the user installs separately
- **NG2**: Fine-tuning or training models — we use off-the-shelf models from Ollama's registry
- **NG3**: Replacing the existing Azure/OpenAI providers — local is an additional option, not a replacement
- **NG4**: Prompt engineering optimization in this phase — use the existing SmartContentService prompt templates
- **NG5**: Parallel/batched LLM inference — Ollama serializes requests; parallelism is a future optimization
- **NG6**: Supporting llama-cpp-python as an embedded alternative — future scope if needed

## Target Domains

| Domain | Status | Relationship | Role in This Feature |
|--------|--------|-------------|---------------------|
| adapters | existing | **modify** | Add LocalLLMAdapter implementing LLMAdapter ABC |
| config | existing | **modify** | Extend LLMConfig with "local" provider and local-specific fields |
| services | existing | **modify** | Add "local" branch to LLMService.create() factory |
| cli | existing | **modify** | Update init DEFAULT_CONFIG template, update doctor checks |
| stages | existing | **consume** | SmartContentStage is provider-agnostic (zero changes) |
| docs | existing | **modify** | User guide, configuration guide, MCP help docs |

ℹ️ No domain registry exists. Domains will be identified as part of this spec.

## Complexity

- **Score**: CS-2 (small)
- **Breakdown**: S=1, I=1, D=0, N=0, F=0, T=1 → Total P=3
  - **S=1** (Surface Area): Multiple files but well-scoped — 1 new adapter, config extension, factory clause, docs
  - **I=1** (Integration): One external dependency (Ollama service), but stable OpenAI-compatible API
  - **D=0** (Data/State): No schema changes — CodeNode.smart_content field already exists
  - **N=0** (Novelty): Well-specified — identical pattern to 032-local-embeddings, LLMAdapter ABC already defined
  - **F=0** (Non-Functional): Standard error handling, no security concerns (no API keys)
  - **T=1** (Testing): Unit + integration tests needed, but FakeLLMAdapter already exists
- **Confidence**: 0.90
- **Assumptions**:
  - LLMAdapter ABC and LLMService factory already exist and are stable
  - SmartContentStage is truly provider-agnostic (confirmed by exploration)
  - Ollama's OpenAI-compatible API at `/v1/chat/completions` is stable
- **Dependencies**: Ollama installed on user's machine (external, not a Python dep)
- **Risks**: Ollama not running → graceful error; model not pulled → actionable message
- **Phases**: Single implementation phase (adapter + config + factory + docs)

## Acceptance Criteria

1. **AC01**: Given Ollama is running with a model pulled, when a user configures `llm.provider: local` and runs `fs2 scan`, then smart_content is generated for all code nodes
2. **AC02**: Given a local LLM adapter, when `generate()` is called, then it returns a valid `LLMResponse` with content, tokens_used, model, provider="local", and finish_reason
3. **AC03**: Given `llm.provider: local` in config, when `LLMService.create()` is called, then it returns an LLMService with a LocalLLMAdapter
4. **AC04**: Given Ollama is not running, when the adapter attempts to connect, then it raises `LLMAdapterError` with an actionable message including setup instructions
5. **AC05**: Given the requested model is not available in Ollama, when generation is attempted, then the error message suggests `ollama pull <model>`
6. **AC06**: Given a node's content_hash matches its smart_content_hash from a prior scan, when scanning, then the LLM is NOT called for that node (hash-based skip)
7. **AC07**: Given `fs2 init` is run in a new project, then the generated `.fs2/config.yaml` includes local LLM as the default provider with Ollama endpoint and recommended model
8. **AC08**: Given the local LLM adapter, when it receives an HTTP error from Ollama, then it translates the error to the appropriate LLMAdapterError subclass (connection error, timeout, etc.)
9. **AC09**: Given the adapter receives ConfigurationService, when generate() is called, then it extracts LLMConfig via `config.require(LLMConfig)` — no config leakage
10. **AC10**: Given `fs2 doctor` is run with local LLM configured, then it checks Ollama connectivity, model availability, AND performs a test generation with a small prompt to verify the model works end-to-end
11. **AC11**: Given a user reads the MCP server help or CLI docs, then they can find setup instructions for local LLM smart content generation
12. **AC12**: Given the local adapter, when the timeout is exceeded, then a clear timeout error is raised (not a generic connection error)

## Risks & Assumptions

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Ollama not installed by user | Medium | Low | Clear error message with install URL; `fs2 doctor` checks |
| Model not pulled | Medium | Low | Error suggests `ollama pull qwen2.5-coder:7b` |
| Ollama service not running | Medium | Low | Connection error → "Start Ollama: `ollama serve`" |
| First scan takes ~2.5 hours for large codebases | Certain | Medium | Progress reporting; incremental scans are fast; accepted trade-off |
| Summary quality varies by model | Low | Medium | Default to qwen2.5-coder:7b (benchmarked); temperature=0.1 |
| Ollama API breaks compatibility | Very Low | High | We use stable /v1/chat/completions endpoint (OpenAI-compatible) |

**Assumptions**:
- Users are willing to install Ollama separately (not bundled)
- The existing SmartContentService prompt templates produce good results with local models
- Ollama handles GPU auto-detection (Metal/CUDA/CPU) — we don't need to manage devices
- The existing LLMConfig timeout max is 120s for cloud providers; local provider allows up to 300s

## Open Questions

*All resolved — see Clarifications.*

## Testing Strategy

- **Approach**: Full TDD
- **Rationale**: Existing LLM adapter tests follow Full TDD with GIVEN_WHEN_THEN naming; this adapter follows the same pattern
- **Focus Areas**: Adapter generate() contract, config validation (local provider fields), factory wiring, error translation (connection refused, timeout, model not found), doctor checks
- **Mock Usage**: Targeted mocks — mock HTTP calls to Ollama API only. Use real config objects, FakeLLMAdapter for service-level tests
- **Excluded**: SmartContentStage tests (zero changes), prompt template tests (NG4)

## Documentation Strategy

- **Location**: Hybrid — `docs/how/user/local-llm.md` (new user guide) + `docs/how/user/configuration-guide.md` (update LLM section) + MCP server help docs
- **Rationale**: User explicitly requested setup instructions be discoverable via MCP server and CLI help commands

## Workshop Opportunities

| Topic | Type | Why Workshop | Key Questions |
|-------|------|--------------|---------------|
| Prompt templates for local models | Integration Pattern | Local models may need different prompt formatting than GPT-4 (e.g., ChatML vs plain) | Do existing templates work with Qwen2.5-Coder? Need model-specific prompts? |

## Clarifications

### Session 2026-03-15

| # | Question | Answer | Spec Impact |
|---|----------|--------|-------------|
| Q1 | Workflow Mode | **Simple** — single phase, inline tasks | Added `**Mode**: Simple` to header |
| Q2 | Testing Strategy | **Full TDD** — tests first for adapter, config, factory | Added `## Testing Strategy` section |
| Q3 | Mock Usage | **Targeted mocks** — mock HTTP calls to Ollama only | Added to Testing Strategy |
| Q4 | Documentation Strategy | **Hybrid** — user guide + config guide + MCP help | Added `## Documentation Strategy` section |
| Q5 | Domain Review | **Confirmed as-is** — all existing, no contract-breaking changes | No changes needed |
| Q6 | OQ1: Timeout max | **Increase to 300s for local provider only** | Updated Assumptions; timeout validator needs conditional logic |
| Q7 | OQ2: Doctor check depth | **Full test generation** with small prompt | Updated AC10 to include test generation |
