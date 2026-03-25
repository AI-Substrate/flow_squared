# Code Review: Simple Mode — Local LLM Smart Content

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/034-local-llm-smart-content/local-llm-smart-content-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/034-local-llm-smart-content/local-llm-smart-content-spec.md
**Phase**: Simple Mode
**Date**: 2026-03-15
**Reviewer**: Automated (plan-7-v2)
**Testing Approach**: Hybrid (spec requested Full TDD; evidence pack demonstrates mixed automated + manual verification)

## A) Verdict

**REQUEST_CHANGES**

Blocking issues remain in the runtime error path and the touched-file quality gate. Real Ollama transport failures/timeouts do not hit the intended actionable handlers, and the new adapter test file does not pass Ruff.

**Key failure areas**:
- **Implementation**: `LocalOllamaAdapter` catches builtin `TimeoutError`/`ConnectionError`, but the OpenAI SDK actually raises `APITimeoutError`/`APIConnectionError`, so AC04 and AC12 fail in practice.
- **Domain compliance**: `src/fs2/cli/scan.py` still instantiates adapter implementations inside the CLI layer instead of delegating to the existing service factory, extending the known RF-02 drift hazard.
- **Testing**: The scoped Ruff gate fails, and AC01/AC06/AC10 still rely mostly on manual/execution-log evidence.
- **Doctrine**: `docs/how/user/registry.yaml` was not updated, so MCP docs discovery cannot surface `local-llm.md` and still describes configuration as Azure/OpenAI-centric.

## B) Summary

This phase is close, but it is not approval-ready. The main runtime bug is in `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/llm_adapter_local.py`: reviewer-run probes showed that real closed-port and timeout failures are wrapped by the OpenAI SDK as `openai.APIConnectionError` and `openai.APITimeoutError`, so the current specific handlers never run and users receive generic fallback messaging instead of the actionable Ollama guidance promised by AC04 and AC12. The new adapter/config/service wiring otherwise follows the existing LLM-adapter pattern and the anti-reinvention pass found no genuine duplication. Evidence quality is mixed: focused pytest passed, but Ruff fails on the new adapter test file, docs discovery is incomplete because the docs registry was not updated, and several acceptance criteria still rely on execution-log claims rather than reproducible artifacts.

## C) Checklist

**Testing Approach: Hybrid**

- [ ] RED→GREEN evidence recorded for new tests
- [x] Core validation tests present
- [ ] Critical failure paths covered with faithful SDK exception types
- [ ] Key manual verification points backed by reproducible artifacts

Universal (all approaches):
- [x] Only in-scope files changed
- [ ] Linters/type checks clean (scoped Ruff run fails)
- [ ] Domain compliance checks pass (CLI still reaches into adapter implementations)

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | HIGH | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/llm_adapter_local.py:124-152` | error-handling | Real OpenAI SDK transport exceptions bypass the intended Ollama-specific handlers, so connection/timeouts fall through to the generic fallback message. | Catch `openai.APIConnectionError` and `openai.APITimeoutError`, then update tests to use the same exception types. |
| F002 | HIGH | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_llm_adapter_local.py:56,160-171,195-204,225-236,258-267` | doctrine | The new adapter test file fails the repository Ruff gate (`F401`, `SIM117`, `UP041`), so the phase is not lint-clean. | Remove the unused import, flatten the nested `with` blocks, and use builtin `TimeoutError` in the test file until `uv run ruff check ...` passes. |
| F003 | MEDIUM | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/registry.yaml:23-37` | scope | The new `local-llm.md` guide is not registered for MCP docs discovery, and `configuration-guide` metadata still advertises Azure/OpenAI only. | Add a `local-llm` registry entry, refresh `configuration-guide` summary/tags for local/Ollama support, and rebuild docs discovery artifacts. |
| F004 | MEDIUM | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/scan.py:607-625` | pattern | The phase adds another provider branch to the CLI-side smart-content factory instead of reusing `LLMService.create()`, preserving the RF-02 drift hazard documented in the plan. | Refactor `_create_smart_content_service()` to obtain the LLM path through `LLMService.create(config)` and keep adapter selection out of the CLI layer. |

## E) Detailed Findings

### E.1) Implementation Quality

- **F001 (HIGH)** — `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/llm_adapter_local.py:124-152`
  - Reviewer probe against a closed local port showed the OpenAI SDK raises `openai.APIConnectionError`, not builtin `ConnectionError`.
  - Reviewer probe against a slow local test server showed the OpenAI SDK raises `openai.APITimeoutError`, not builtin `TimeoutError`.
  - Reproduced adapter outputs:
    - Connection path: `Ollama error: Connection error.\n  Check that Ollama is running: ollama serve`
    - Timeout path: `Ollama error: Request timed out.\n  Check that Ollama is running: ollama serve`
  - That behavior contradicts both the acceptance criteria and the new troubleshooting docs, which promise actionable install/start guidance for connection failures and timeout-specific guidance for slow models.

### E.2) Domain Compliance

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | Changed files land under the plan’s expected `docs/`, `src/fs2/cli/`, `src/fs2/config/`, `src/fs2/core/adapters/`, `src/fs2/core/services/`, and `tests/` trees. |
| Contract-only imports | ✅ | No new cross-package import leaks beyond the existing public `fs2.*` package layout were introduced. |
| Dependency direction | ❌ | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/scan.py:607-625` still instantiates provider adapters in the CLI layer instead of delegating to `LLMService.create()`. |
| Domain.md updated | ✅ | No `docs/domains/*/domain.md` files exist in this repo, so nothing required updating. |
| Registry current | ✅ | No `docs/domains/registry.md` exists; the spec explicitly states no domain registry exists. |
| No orphan files | ✅ | Every changed implementation file maps cleanly to a target domain from the plan (`docs`, `cli`, `config`, `adapters`, `services`, `tests`). |
| Map nodes current | ✅ | No `docs/domains/domain-map.md` exists, so no node-map update was required. |
| Map edges current | ✅ | No domain map exists, so no edge labeling artifact required an update. |
| No circular business deps | ✅ | No new business-to-business cycle is visible in the changed code. |
| Concepts documented | N/A | No domain contract docs exist in `docs/domains/`, so this check is not applicable in this repo. |

Additional note:
- **F004 (MEDIUM)** — The local-provider branch in `scan.py` extends a known duplicate-factory hazard already called out as RF-02 in the plan. It is not a runtime blocker today, but it keeps the CLI coupled to adapter implementations and increases future drift risk.

### E.3) Anti-Reinvention

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| `LocalOllamaAdapter` | Existing `LLMAdapter` family / local-embedding pattern reused as intended | adapters | ✅ Proceed |
| Local provider config + factory wiring | Expected extension of existing `LLMConfig` + `LLMService.create()` surfaces | config/services | ✅ Proceed |
| `docs/how/user/local-llm.md` | New user-facing setup guide; no genuine duplicate guide found | docs | ✅ Proceed |

No genuine duplication was found.

### E.4) Testing & Evidence

**Coverage confidence**: **51%**

Key evidence notes:
- Focused pytest: `45 passed, 2 skipped, 26 deselected`
- Forced init-template test slice: `6 passed`
- Scoped Ruff run: **failed** with 6 violations in `tests/unit/adapters/test_llm_adapter_local.py`
- AC01/AC06/AC10 evidence remains mostly manual/execution-log based

| AC | Confidence | Evidence |
|----|------------|----------|
| AC01 | 40 | `execution.log.md` claims `826/826` nodes received smart content, but no saved scan transcript or automated local-provider scan-path test was attached. |
| AC02 | 82 | `tests/unit/adapters/test_llm_adapter_local.py::test_local_adapter_generate_returns_llm_response` validates the happy path shape of `LLMResponse`. |
| AC03 | 92 | `tests/unit/config/test_llm_config.py` plus `tests/unit/services/test_llm_service.py::test_llm_service_factory_creates_local` cover config acceptance and factory creation. |
| AC04 | 15 | Reviewer reproduction with real `AsyncOpenAI` transport failures reached the generic fallback path instead of the intended actionable Ollama guidance. |
| AC05 | 72 | Mocked 404-path test verifies `ollama pull <model>` guidance. |
| AC06 | 35 | Incremental skip behavior is asserted only by the execution log; no dedicated scan/re-scan artifact was attached. |
| AC07 | 65 | `init.py` clearly makes local LLM the active default, but there is no explicit plan-034 test asserting that active local block. |
| AC08 | 20 | HTTP/transport coverage uses generic mocked exceptions and does not faithfully represent the SDK exceptions the adapter will actually receive. |
| AC09 | 90 | The adapter constructs itself from `ConfigurationService` and calls `config.require(LLMConfig)`. |
| AC10 | 60 | `execution.log.md` records `HEALTH_CHECK_OK`, but there is no reviewer reproduction or automated local-provider doctor test artifact. |
| AC11 | 20 | The docs file exists, but `flowspace-docs_list()` does not surface `local-llm` and `flowspace-docs_get("local-llm")` returns null. |
| AC12 | 10 | Reviewer reproduction with a slow local server produced the generic fallback message instead of timeout-specific remediation guidance. |

### E.5) Doctrine Compliance

No `docs/project-rules/*.md` files exist, so doctrine was checked against the repo’s visible architecture/lint conventions plus `AGENTS.md` / `CLAUDE.md` guidance.

- **F002 (HIGH)** — `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_llm_adapter_local.py`
  - `uv run ruff check` fails on the new test file with `F401`, `SIM117`, and `UP041` findings.
  - This is a real quality-gate failure, not a style nit.

- **F003 (MEDIUM)** — `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/registry.yaml:23-37`
  - `flowspace-docs_list()` still reports `configuration-guide` as covering only Azure/OpenAI and does not list `local-llm` at all.
  - `flowspace-docs_get("local-llm")` returns null, so the new guide is not discoverable through the docs registry surface the spec explicitly called out.

### E.6) Harness Live Validation

N/A — no harness configured (`/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/project-rules/harness.md` is absent).

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC01 | `fs2 scan` with `llm.provider: local` generates smart content for all code nodes | `execution.log.md` T11 claim only; no saved reviewer-run scan artifact | 40 |
| AC02 | `LocalOllamaAdapter.generate()` returns valid `LLMResponse` | Happy-path adapter unit test | 82 |
| AC03 | `LLMService.create()` returns service with `LocalOllamaAdapter` | Config + factory tests | 92 |
| AC04 | Ollama-not-running path returns actionable `LLMAdapterError` | Reviewer reproduction shows generic fallback, not actionable install/start guidance | 15 |
| AC05 | Missing model suggests `ollama pull <model>` | Mocked 404-path unit test | 72 |
| AC06 | Unchanged nodes skip LLM call on re-scan | Execution-log claim only | 35 |
| AC07 | `fs2 init` makes local provider the default template | Active config diff + generic template tests, but no explicit local-default assertion | 65 |
| AC08 | HTTP errors translate to appropriate adapter errors | Tests use generic exceptions; real transport mapping is incomplete | 20 |
| AC09 | Adapter uses `ConfigurationService` DI via `require()` | Adapter construction + config tests | 90 |
| AC10 | `fs2 doctor` performs connectivity + test generation for local provider | Execution-log `HEALTH_CHECK_OK`; no reviewer rerun artifact | 60 |
| AC11 | MCP/CLI docs surfaces expose setup guidance | New guide exists, but docs registry discovery is incomplete | 20 |
| AC12 | Timeout path returns clear timeout remediation | Reviewer reproduction shows generic fallback instead of timeout-specific guidance | 10 |

**Overall coverage confidence**: **51%**

## G) Commands Executed

```bash
git --no-pager status --short
git --no-pager diff --stat
git --no-pager diff --staged --stat
git --no-pager log --oneline -10
python - <<'PY'  # built scoped diff + manifest at docs/plans/034-local-llm-smart-content/reviews/_computed.diff
...
PY
uv run ruff check src/fs2/config/objects.py src/fs2/core/adapters/llm_adapter_local.py src/fs2/core/services/llm_service.py src/fs2/cli/init.py src/fs2/cli/scan.py tests/unit/adapters/test_llm_adapter_local.py tests/unit/config/test_llm_config.py tests/unit/services/test_llm_service.py tests/unit/cli/test_init_cli.py
uv run python -m pytest -q tests/unit/config/test_llm_config.py tests/unit/adapters/test_llm_adapter_local.py tests/unit/services/test_llm_service.py tests/unit/cli/test_init_cli.py
uv run python -m pytest --override-ini='addopts=' -q tests/unit/cli/test_init_cli.py::TestDefaultConfigTemplate
python - <<'PY'  # inspected OpenAI exception inheritance (APIConnectionError / APITimeoutError)
...
PY
python - <<'PY'  # probed AsyncOpenAI against a closed local port
...
PY
python - <<'PY'  # probed AsyncOpenAI timeout behavior with a slow local test server
...
PY
python - <<'PY'  # reproduced LocalOllamaAdapter closed-port message
...
PY
python - <<'PY'  # reproduced LocalOllamaAdapter timeout message
...
PY
# Additional tool-based checks:
# - flowspace-docs_list()
# - flowspace-docs_get("local-llm")
# - flowspace-docs_get("configuration-guide")
```

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: REQUEST_CHANGES

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/034-local-llm-smart-content/local-llm-smart-content-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/034-local-llm-smart-content/local-llm-smart-content-spec.md
**Phase**: Simple Mode
**Tasks dossier**: inline in plan
**Execution log**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/034-local-llm-smart-content/execution.log.md
**Review file**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/034-local-llm-smart-content/reviews/review.md

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/llm_adapter_local.py | changed | adapters | **Yes** — fix F001 |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_llm_adapter_local.py | changed | tests | **Yes** — fix F002 and align failure-mode mocks with real SDK exceptions |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/registry.yaml | reviewed (supporting) | docs | **Yes** — fix F003 |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/scan.py | changed | cli | Optional but recommended — fix F004 |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/local-llm.md | changed | docs | Update only if runtime error messages are reworded or docs registry changes require metadata sync |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/configuration-guide.md | changed | docs | Refresh registry metadata/tags; content itself is mostly fine |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/config/objects.py | changed | config | No direct fix required from this review |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/llm_service.py | changed | services | No direct fix required from this review |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/init.py | changed | cli | No direct fix required from this review |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/__init__.py | changed | adapters | No direct fix required from this review |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/config/test_llm_config.py | changed | tests | No direct fix required from this review |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_llm_service.py | changed | tests | No direct fix required from this review |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_init_cli.py | reviewed (supporting) | tests | No direct fix required; existing template tests pass |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/cli/test_doctor_llm.py | reviewed (supporting) | tests | No direct fix required; manual evidence remains stronger than automated coverage here |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/034-local-llm-smart-content/execution.log.md | changed | plan-docs | No direct fix required |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/034-local-llm-smart-content/local-llm-smart-content-plan.md | changed | plan-docs | No direct fix required |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/034-local-llm-smart-content/local-llm-smart-content-spec.md | changed | plan-docs | No direct fix required |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/034-local-llm-smart-content/tasks/implementation/tasks.fltplan.md | changed | plan-docs | No direct fix required |

### Required Fixes (if REQUEST_CHANGES)

| # | File (absolute path) | What To Fix | Why |
|---|---------------------|-------------|-----|
| 1 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/adapters/llm_adapter_local.py | Catch real `openai.APIConnectionError` / `openai.APITimeoutError` and preserve actionable Ollama-specific messages. | Current code misses AC04 and AC12 in production. |
| 2 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/adapters/test_llm_adapter_local.py | Use faithful SDK exception types and make the file Ruff-clean. | Current tests miss the real failure mode and fail the quality gate. |
| 3 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/registry.yaml | Register `local-llm.md` and refresh `configuration-guide` metadata/tags for local/Ollama support. | MCP docs discovery currently cannot surface the new guide (AC11 gap). |
| 4 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/scan.py | Prefer `LLMService.create(config)` over direct CLI-layer adapter selection. | Removes the RF-02 duplicate-factory drift hazard. |

### Domain Artifacts to Update (if any)

| File (absolute path) | What's Missing |
|---------------------|----------------|
| N/A | No `docs/domains` registry/map/domain docs exist in this repo, so no domain-artifact update is required for this fix pass. |

### Next Step

`/plan-6-v2-implement-phase --plan /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/034-local-llm-smart-content/local-llm-smart-content-plan.md`
