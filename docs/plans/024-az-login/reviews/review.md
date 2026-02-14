# Code Review — Azure AD Credential Support (Single Phase)

**Plan**: docs/plans/024-az-login/az-login-plan.md
**Mode**: Simple (Single Phase)
**Diff Range**: `b10755a..913985d` (main → az-login)
**Testing Approach**: Full TDD
**Mock Usage**: Targeted mocks (azure-identity only)
**Reviewed**: 2026-02-14

---

## A) Verdict

**REQUEST_CHANGES**

Two ruff B904 lint violations in production code must be fixed before merge. Change Footnotes Ledger was never populated (plan hygiene). All tests pass; implementation is correct and well-structured.

---

## B) Summary

Implementation adds Azure AD credential support to both LLM and embedding adapters via `DefaultAzureCredential` when no API key is configured. Changes are surgical (~38 LOC across 4 production files), backward-compatible, and well-tested with 9 new unit tests. TDD discipline is documented with RED/GREEN evidence per task. Two ruff B904 lint violations (`raise ... from None` missing) block approval. Change Footnotes Ledger placeholders were never filled in during implementation.

---

## C) Checklist

**Testing Approach: Full TDD**

- [x] Tests precede code (RED-GREEN-REFACTOR evidence) — T001→T002, T003→T004, T005→T006 documented in execution.log.md
- [x] Tests as docs (assertions show behavior) — docstrings include Purpose/Quality Contribution/Acceptance Criteria
- [x] Mock usage matches spec: Targeted — only azure.identity and ConfigurationService mocked
- [x] Negative/edge cases covered — ImportError, empty string, None, key-present, key-absent

**Universal:**

- [ ] ~~BridgeContext patterns followed~~ (N/A — Python project, no VS Code extension code)
- [x] Only in-scope files changed (one exception: scratch test — see PLAN-004)
- [ ] Linters/type checks are clean — **FAIL** (2 ruff B904 violations)
- [x] Absolute paths used (no hidden context)

---

## D) Findings Table

| ID | Severity | File:Lines | Summary | Recommendation |
|----|----------|------------|---------|----------------|
| LINT-001 | HIGH | llm_adapter_azure.py:123-127 | Ruff B904: `raise LLMAdapterError(...)` in `except ImportError` without `from None` | Add `from None` to suppress exception chaining |
| LINT-002 | HIGH | embedding_adapter_azure.py:99-103 | Ruff B904: `raise EmbeddingAdapterError(...)` in `except ImportError` without `from None` | Add `from None` to suppress exception chaining |
| GRAPH-001 | HIGH | az-login-plan.md:215-219 | Change Footnotes Ledger has 4 placeholder entries; never populated by plan-6a | Run plan-6a to populate footnotes with FlowSpace node IDs |
| GRAPH-002 | HIGH | tasks.md:377-379 | Phase Footnote Stubs table is empty | Populate after GRAPH-001 is resolved |
| PLAN-004 | MEDIUM | tests/scratch/test_azure_ad_auth.py | File in diff but not in any task's Absolute Path(s) | Acceptable — scratch exploration documented in execution log. No action needed. |
| PLAN-005 | MEDIUM | az-login-plan.md:9 vs :222 | Status inconsistency: header says DRAFT, footer says COMPLETE | Update header `**Status**: DRAFT` → `**Status**: COMPLETE` |
| PLAN-006 | LOW | embedding_adapter_azure.py:64-67 | Init error message changed (dropped api_key mention) — not in T006 description | Justified by api_key being optional now. Document in task notes. |

---

## E) Detailed Findings

### E.0) Cross-Phase Regression Analysis

Skipped: Simple Mode (single phase).

### E.1) Doctrine & Testing Compliance

#### Graph Integrity

**Verdict: ❌ BROKEN** — Footnotes Ledger never populated.

| Violation | Severity | Link Type | Issue | Fix |
|-----------|----------|-----------|-------|-----|
| GRAPH-001 | HIGH | Footnote↔File | Plan § Change Footnotes Ledger has 4 placeholder entries `[^1]-[^4]` all saying "[To be added during implementation via plan-6a]" | Run `plan-6a` to populate with FlowSpace node IDs for modified files |
| GRAPH-002 | HIGH | Task↔Footnote | Phase Footnote Stubs table in tasks.md is empty — no footnote references in task Notes column | Populate after GRAPH-001 |

**Note**: These are plan hygiene issues that don't affect code correctness but break graph traversability (file→footnote→task navigation).

#### Authority Conflicts

N/A — Simple Mode, no separate dossier. Plan is the single source of truth.

#### TDD Compliance

**Verdict: ✅ PASS**

- TDD order verified: Tests written first (RED) in T001, T003, T005; implementation follows (GREEN) in T002, T004, T006
- Execution log documents RED (2 failed, 1 passed) → GREEN (all passed) for each pair
- Test names follow Given-When-Then: `test_given_<context>_when_<action>_then_<outcome>`
- Docstrings serve as test documentation with Purpose, Quality Contribution, Acceptance Criteria

#### Mock Usage Compliance

**Verdict: ✅ PASS** (Policy: Targeted mocks)

- Mocks used for: `azure.identity` module (external boundary) ✅
- Mocks used for: `ConfigurationService` (existing pattern, MagicMock with spec) ✅
- Mocks used for: `AsyncAzureOpenAI` constructor (to verify kwargs) ✅
- No internal class/method mocking ✅
- Mock instances: 6 per adapter test class (3 tests × 2 files) — within "targeted" threshold ✅

#### Lint Violations (B904)

**Verdict: ❌ FAIL** — 2 violations

Ruff B (flake8-bugbear) is in the project's lint `select` list. B904 requires `raise ... from err` or `raise ... from None` within `except` clauses.

**LINT-001**: `src/fs2/core/adapters/llm_adapter_azure.py:123-127`
```python
except ImportError:
    raise LLMAdapterError(
        "azure-identity package is required for Azure AD authentication. "
        "Install it with: pip install fs2[azure-ad]"
    )
```
Fix: Add `from None` to suppress the ImportError traceback (the adapter error message is self-contained):
```diff
 except ImportError:
     raise LLMAdapterError(
         "azure-identity package is required for Azure AD authentication. "
         "Install it with: pip install fs2[azure-ad]"
-    )
+    ) from None
```

**LINT-002**: `src/fs2/core/adapters/embedding_adapter_azure.py:99-103`
Same pattern — add `from None`.

### E.2) Semantic Analysis

**Verdict: ✅ PASS** — No semantic issues found.

- Domain logic (key present → use key, key absent → Azure AD) correctly implements the spec
- `DefaultAzureCredential` + `get_bearer_token_provider` pattern matches Microsoft documentation
- Scope string `https://cognitiveservices.azure.com/.default` is correct per external research
- `api_key` and `azure_ad_token_provider` are mutually exclusive via if/else (AC7)
- Config model change (`str` → `str | None = None`) is additive and backward-compatible
- Validator correctly handles None (passes through) and empty string (rejects)

### E.3) Quality & Safety Analysis

**Safety Score: 100/100** (CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0)
**Verdict: APPROVE**

#### Correctness
- if/else branching in `_get_client()` is correct — no path where both `api_key` and `azure_ad_token_provider` are passed ✅
- Lazy import pattern handles `ImportError` correctly ✅
- `DefaultAzureCredential()` created fresh per `_get_client()` call (only once due to `self._client` caching) ✅
- Validator logic `if v is not None and not v.strip()` correctly handles: None → pass, "" → reject, "key" → pass ✅

#### Security
- No secrets in code ✅
- No path traversal ✅
- No injection vulnerabilities ✅
- Credential creation uses well-established SDK pattern ✅
- Scope string is hardcoded (not user-controlled) ✅

#### Performance
- `DefaultAzureCredential()` creation is a one-time cost (client is cached via `self._client`) ✅
- `get_bearer_token_provider()` handles token caching and refresh internally ✅
- No N+1 patterns, no unbounded scans ✅

#### Observability
- Error messages are actionable: "Install it with: pip install fs2[azure-ad]" ✅
- Sovereign cloud comment provides guidance for customization ✅
- No logging changes needed — existing adapter logging covers API call failures ✅

### E.4) Doctrine Evolution Recommendations (Advisory)

**New Rules Candidate:**

| ID | Rule Statement | Evidence | Priority |
|----|---------------|----------|----------|
| RULE-REC-001 | Use `raise ... from None` when re-raising as domain error within `except` blocks | llm_adapter_azure.py:124, embedding_adapter_azure.py:100 | HIGH |

**Positive Alignment:**
- Implementation follows Clean Architecture: lazy import at adapter level, domain errors from `exceptions.py` ✅
- Fakes-over-mocks partially followed: used MagicMock with spec= (acceptable for ConfigurationService) ✅
- ABC interface contracts honored: no changes to `LLMAdapter` or `EmbeddingAdapter` ABCs ✅

---

## F) Coverage Map

| AC | Description | Test(s) | Confidence |
|----|-------------|---------|------------|
| AC1 | api_key present → key-based auth | `test_given_api_key_when_get_client_then_uses_key_not_token_provider` (LLM + Embedding) | 100% — explicit assertion `call_kwargs["api_key"] == "test-key"` |
| AC2 | api_key absent + azure-identity → Azure AD | `test_given_no_api_key_and_azure_identity_when_get_client_then_uses_token_provider` (LLM + Embedding) | 100% — asserts `azure_ad_token_provider` in kwargs, `api_key` NOT in kwargs, correct scope |
| AC3 | api_key absent + no azure-identity → error | `test_given_no_api_key_and_no_azure_identity_when_get_client_then_raises_error` (LLM + Embedding) | 100% — asserts correct error type with `match="azure-identity"` |
| AC4 | AzureEmbeddingConfig.api_key accepts None | `test_given_no_api_key_when_constructed_then_defaults_to_none`, `test_given_explicit_none_...`, `test_given_empty_string_...` | 100% — 3 tests cover default, explicit None, empty string rejection |
| AC5 | pyproject.toml azure-ad dep group | Verified in diff: `azure-ad = ["azure-identity>=1.18.0,<2"]` | 100% — structural verification |
| AC6 | All existing tests pass | T008 evidence: 65 passed, 1 skipped (baseline was 56+1) | 100% — regression suite run |
| AC7 | Mutual exclusivity | `test_given_api_key_..._uses_key_not_token_provider` + `test_given_no_api_key_..._uses_token_provider` | 100% — both directions explicitly assert absence of the other param |

**Overall Coverage Confidence: 100%** — All 7 acceptance criteria have explicit, named tests with direct behavioral assertions.

---

## G) Commands Executed

```bash
# Tests (all pass)
.venv/bin/python -m pytest tests/unit/config/test_embedding_config.py tests/unit/adapters/test_llm_adapter_azure.py tests/unit/adapters/test_embedding_adapter_azure.py -v --tb=short
# Result: 65 passed, 1 skipped

# Lint (2 violations)
.venv/bin/python -m ruff check src/fs2/config/objects.py src/fs2/core/adapters/llm_adapter_azure.py src/fs2/core/adapters/embedding_adapter_azure.py
# Result: 2 B904 errors

# Diff
git diff b10755a..913985d --unified=3 --no-color
```

---

## H) Decision & Next Steps

**Verdict: REQUEST_CHANGES**

**Blocking (must fix):**
1. Fix 2 ruff B904 violations: add `from None` to both `raise` statements in `except ImportError` blocks
2. Run `plan-6a` to populate Change Footnotes Ledger and Phase Footnote Stubs

**Non-blocking (recommended):**
3. Update plan header `**Status**: DRAFT` → `**Status**: COMPLETE` (consistency)

**After fixes:** Re-run `/plan-7-code-review` to verify clean lint, then APPROVE → merge.

---

## I) Footnotes Audit

| Diff-Touched Path | Footnote Tag(s) | Node-ID Link(s) |
|-------------------|-----------------|------------------|
| `src/fs2/config/objects.py` | _(none)_ | _(none — ledger not populated)_ |
| `src/fs2/core/adapters/llm_adapter_azure.py` | _(none)_ | _(none — ledger not populated)_ |
| `src/fs2/core/adapters/embedding_adapter_azure.py` | _(none)_ | _(none — ledger not populated)_ |
| `pyproject.toml` | _(none)_ | _(none — ledger not populated)_ |
| `tests/unit/config/test_embedding_config.py` | _(none)_ | _(none — ledger not populated)_ |
| `tests/unit/adapters/test_llm_adapter_azure.py` | _(none)_ | _(none — ledger not populated)_ |
| `tests/unit/adapters/test_embedding_adapter_azure.py` | _(none)_ | _(none — ledger not populated)_ |
| `tests/scratch/test_azure_ad_auth.py` | _(none)_ | _(not in task table)_ |

**⚠️ All 4 production files and 3 test files lack footnote entries.** The Change Footnotes Ledger contains only placeholder text.
